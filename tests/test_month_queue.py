import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock,patch
import month_queue as month
import auto_pipeline as auto
import content_bank as bank
from test_content_recovery import b,ROOT

class MonthQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name);self.old=b.OUT;b.OUT=self.out
    def tearDown(self):b.OUT=self.old;self.temp.cleanup()
    def test_exactly_thirty_days_per_channel(self):
        data=month.load_calendar();self.assertEqual(len(data['entries']),120)
        for key in month.RESEARCH_DOMAINS:
            entries=[e for e in data['entries'] if e['channel']==key]
            self.assertEqual(len(entries),30);self.assertEqual(len({e['topic'] for e in entries}),30)
            self.assertTrue(all(e['status']=='research_brief_not_rendered' for e in entries))
    def test_due_selection_never_uses_future_or_published_brief(self):
        recent=[{'snippet':{'description':'Content-Bank-ID: month-ai-02\n'}}]
        result=month.due_entries('ai','2026-10-29',recent)
        self.assertEqual([e['id'] for e in result],['month-ai-01'])
        self.assertEqual(month.due_entries('ai','2026-10-26',[]),[])
        self.assertEqual(month.due_entries('ai','2026-11-27',[]),[])
    def test_today_precedes_bounded_backlog(self):
        result=month.due_entries('finance','2026-11-01',[])
        self.assertEqual([e['date'] for e in result],['2026-11-01','2026-10-31'])
    def test_calendar_window_boundaries(self):
        self.assertTrue(month.scheduled_window('2026-10-28'));self.assertTrue(month.scheduled_window('2026-11-26'))
        self.assertFalse(month.scheduled_window('2026-11-27'))
    def test_duplicate_slots_are_rejected(self):
        data=month.load_calendar();data['entries'][-1]=copy.deepcopy(data['entries'][0])
        path=self.out/'bad.json';path.write_text(json.dumps(data))
        with self.assertRaises(RuntimeError):month.load_calendar(path)
    def test_publication_target_tracks_dst(self):
        self.assertEqual(month.scheduled_publish_at(datetime(2026,10,27,22,tzinfo=timezone.utc)),'2026-10-27T23:00:00Z')
        self.assertEqual(month.scheduled_publish_at(datetime(2026,11,3,23,tzinfo=timezone.utc)),'2026-11-04T00:00:00Z')
        self.assertIsNone(month.scheduled_publish_at(datetime(2026,10,27,23,10,tzinfo=timezone.utc)))
    def test_scheduled_video_remains_private_until_confirmed_publish_at(self):
        yt=Mock();target='2026-10-27T23:00:00Z'
        yt.videos.return_value.list.return_value.execute.return_value={'items':[{'status':{'privacyStatus':'private','publishAt':target}}]}
        with patch.dict(os.environ,{'SCHEDULED_PUBLICATION':'true'}),patch.object(month,'scheduled_publish_at',return_value=target):
            self.assertEqual(auto.set_public(b,yt,'video123'),'video123')
        body=yt.videos.return_value.update.call_args.kwargs['body']['status']
        self.assertEqual(body['privacyStatus'],'private');self.assertEqual(body['publishAt'],target)
        report=json.loads((self.out/'publication.json').read_text())
        self.assertEqual(report['state'],'scheduled');self.assertEqual(report['actual_visibility'],'private')
    def test_unconfirmed_schedule_does_not_report_public(self):
        yt=Mock();yt.videos.return_value.list.return_value.execute.return_value={'items':[{'status':{'privacyStatus':'private'}}]}
        with patch.dict(os.environ,{'SCHEDULED_PUBLICATION':'true'}),patch.object(month,'scheduled_publish_at',return_value='2026-10-27T23:00:00Z'):
            with self.assertRaises(RuntimeError):auto.set_public(b,yt,'video123')
        self.assertNotEqual(json.loads((self.out/'publication.json').read_text())['state'],'public')
    def test_resume_does_not_insert_or_render(self):
        yt=Mock();video={'id':'existing','snippet':{'channelId':'channel','description':'Automation-ID: day\nContent-Bank-ID: month-ai-01\n'},'status':{'privacyStatus':'private','uploadStatus':'processed'}}
        with patch.dict(os.environ,{'YT_CHANNEL_ID':'channel'}),patch.object(auto,'set_public',return_value='existing') as public,patch.object(b,'upload') as upload,patch.object(b,'render') as render,patch.object(b,'summary'):
            self.assertTrue(auto.resume_today(b,yt,[video],'Automation-ID: day'))
            public.assert_called_once_with(b,yt,'existing');upload.assert_not_called();render.assert_not_called()
    def test_research_filters_primary_hosts_and_requires_two_roots(self):
        entry=month.due_entries('ai','2026-10-28',[])[0]
        packets=[[{'url':'https://www.nist.gov/test','content':'evidence','title':'a'}],
                 [{'url':'https://openai.com/test','content':'evidence','title':'b'}]]
        with patch.object(b,'search_sources',side_effect=packets) as search:
            sources=month.collect_sources(b,entry,b.CHANNELS['ai'])
        self.assertEqual(len(sources),2)
        self.assertTrue(all(call.kwargs['recent'] is False for call in search.call_args_list))
        self.assertTrue(all(call.args[1]['domains'] for call in search.call_args_list))
        with patch.object(b,'search_sources',return_value=[{'url':'https://evil.example/test','content':'x'}]):
            with self.assertRaises(bank.ItemRejected):month.collect_sources(b,entry,b.CHANNELS['ai'])
    def test_one_institution_subdomains_are_not_independent(self):
        entry=month.due_entries('psychology','2026-10-28',[])[0]
        with patch.object(b,'search_sources',side_effect=[[{'url':'https://nimh.nih.gov/x','content':'x'}],[{'url':'https://ninds.nih.gov/y','content':'x'}]]):
            with self.assertRaises(bank.ItemRejected):month.collect_sources(b,entry,b.CHANNELS['psychology'])
    def compile_fixture(self,fail_audit=False):
        item=json.loads((ROOT/'content_bank/ai/confident-ai-errors.json').read_text())
        script=b.Script.model_validate(item['plan']['script']);entry=month.due_entries('ai','2026-10-28',[])[0]
        def media(*args):
            b.GENERAL_MEDIA.clear()
            for i in range(1,5):
                path=self.out/f'photo{i}.jpg';b.Image.new('RGB',(20,20),'gray').save(path)
                b.GENERAL_MEDIA[f's{i}']={'path':path,'item':{'pageURL':f'https://pixabay.com/photos/{i}/'}}
            return 'four specific photos and two diagrams'
        with patch.dict(os.environ,{'CHANNEL_KEY':'ai','TAVILY_API_KEY':'test'}),patch.object(month,'collect_sources',return_value=item['plan']['sources']),patch.object(b,'prepare_general_media',side_effect=media),patch.object(b,'generate',return_value=script) as gen,patch.object(bank,'audit_plan',side_effect=bank.ItemRejected('unsupported fact') if fail_audit else None),patch.object(b,'speech') as speech:
            result=month.compile_entry(b,None,copy.deepcopy(b.CHANNELS['ai']),'2026-10-28',[],entry)
            speech.assert_not_called();return result,gen.call_count
    def test_compiler_freezes_reviewed_script_sources_and_asset_hashes(self):
        (script,sources),count=self.compile_fixture()
        self.assertEqual(count,1);plan=json.loads((self.out/'compiled_plan.json').read_text())
        self.assertEqual(plan['script'],script.model_dump());self.assertEqual(plan['sources'],sources)
        self.assertEqual(len(plan['assets']),4)
        record=json.loads((self.out/'bank_plan.json').read_text())
        self.assertEqual(record['plan_sha256'],bank.plan_hash(plan))
        self.assertFalse(record['approval']['human_preview_approved'])
    def test_failed_editorial_audit_never_creates_renderable_script(self):
        with self.assertRaises(bank.ItemRejected):self.compile_fixture(fail_audit=True)
        self.assertFalse((self.out/'bank_plan.json').exists())
    def test_conceptual_finance_routes_to_general_visuals(self):
        scene=Mock(diagram=None);config={**b.CHANNELS['finance'],'visual_mode':'concept'}
        with patch.object(b,'planned_general_visual',return_value='general') as general,patch.object(b,'planned_finance_visual') as numeric:
            self.assertEqual(b.scene_visuals(scene,set(),0,5,config,None),'general')
            general.assert_called_once();numeric.assert_not_called()

    def test_recovery_waits_without_canceling_pending_production(self):
        text=(ROOT/'.github/workflows/daily_run.yml').read_text()
        self.assertIn('cancel-in-progress: false\n      queue: max',text)
        self.assertIn('mode = "resume_today"',text)
        self.assertIn('SCHEDULED_PUBLICATION:',text)

    def test_live_preview_has_no_youtube_credentials(self):
        workflow=(ROOT/'.github/workflows/month_preview.yml').read_text()
        self.assertNotIn('YT_REFRESH_TOKEN',workflow)
        self.assertNotIn('YT_CLIENT_SECRET',workflow)
        script=(ROOT/'tools/preview_month.py').read_text()
        self.assertNotIn('youtube_client(',script)
        self.assertNotIn('publish_checked(',script)

    def test_layout_correction_preserves_all_narrated_claims_and_photo_ids(self):
        item=json.loads((ROOT/'content_bank/ai/confident-ai-errors.json').read_text())
        script=b.Script.model_validate(item['plan']['script'])
        narration=[x.narration for x in script.scenes]
        photos=[x.visual_id for x in script.scenes if not x.diagram]
        for scene in script.scenes:
            scene.visual_query=''
            if scene.diagram:scene.visual_id='wrong-id';scene.archive_id='a99'
        result=month.canonicalize_layout(script,{'topic':'AI token units','archive_query':None})
        self.assertEqual([x.narration for x in result.scenes],narration)
        self.assertEqual([x.visual_id for x in result.scenes if not x.diagram],photos)
        self.assertTrue(all(x.visual_query for x in result.scenes))
        for i,scene in enumerate(result.scenes,1):
            if scene.diagram:self.assertEqual((scene.visual_id,scene.archive_id),(f'diagram-{i}',''))

    def test_format_repair_applies_layout_fix_to_each_returned_draft(self):
        item=json.loads((ROOT/'content_bank/ai/confident-ai-errors.json').read_text())
        valid=b.Script.model_validate(item['plan']['script']);invalid=valid.model_copy(deep=True);invalid.title='bad'
        repaired=valid.model_copy(deep=True)
        for scene in repaired.scenes:
            scene.visual_query=''
            if scene.diagram:scene.visual_id='invalid'
        with patch.object(b,'generate',return_value=repaired) as generate:
            result=b.ensure_valid_script(None,invalid,item['plan']['sources'],canonicalizer=lambda draft:month.canonicalize_layout(draft,{'topic':'AI tokens'}))
        generate.assert_called_once()
        self.assertEqual([s.narration for s in result.scenes],[s.narration for s in valid.scenes])
        self.assertTrue(all(s.visual_query for s in result.scenes))
