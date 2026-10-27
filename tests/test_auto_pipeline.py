import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import auto_pipeline as auto
import content_bank as bank
from test_content_recovery import b

class AutoPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name)
        self.previous=b.OUT;b.OUT=self.out
    def tearDown(self):
        b.OUT=self.previous;self.tmp.cleanup()
    def seed_quality(self):
        (self.out/'short.mp4').write_bytes(b'test-video')
        b.save_json('auto_quality.json',dict(passed=True,video_sha256=b.file_hash(self.out/'short.mp4')))
    def fake_yt(self,privacy='public'):
        yt=Mock();yt.videos.return_value.list.return_value.execute.return_value={'items':[{'status':{'privacyStatus':privacy}}]}
        return yt
    def test_preview_requires_auto_opt_in(self):
        self.assertTrue(bank.eligible_items('psychology','2026-10-27',[],'auto'))
        self.assertFalse(bank.eligible_items('psychology','2026-10-27',[],'upload'))
    def test_upload_stages_private_then_verifies_public(self):
        self.seed_quality();yt=self.fake_yt();body={'status':{'privacyStatus':'public'}}
        with patch.object(b,'upload',return_value='video123') as upload:
            self.assertEqual(auto.publish_checked(b,yt,body),'video123')
            self.assertEqual(upload.call_args.args[1]['status']['privacyStatus'],'private')
        self.assertEqual(body['status']['privacyStatus'],'public')
        self.assertEqual(json.loads((self.out/'publication.json').read_text())['state'],'public')
    def test_processing_failure_never_sets_public(self):
        self.seed_quality();yt=self.fake_yt()
        with patch.object(b,'upload',side_effect=RuntimeError('pending')):
            with self.assertRaises(RuntimeError):auto.publish_checked(b,yt,{'status':{}})
        yt.videos.return_value.update.assert_not_called()
    def test_visibility_failure_never_reuploads(self):
        self.seed_quality();yt=self.fake_yt('private')
        with patch.object(b,'upload',return_value='video123') as upload:
            with self.assertRaises(RuntimeError):auto.publish_checked(b,yt,{'status':{}})
            upload.assert_called_once()
    def test_changed_video_cannot_publish(self):
        self.seed_quality();(self.out/'short.mp4').write_bytes(b'changed')
        with patch.object(b,'upload') as upload:
            with self.assertRaises(RuntimeError):auto.publish_checked(b,self.fake_yt(),{'status':{}})
            upload.assert_not_called()
    def recovery(self,review_effect=None,render_effect=None):
        script=Mock();sources=[];choices=[{'id':'first-plan'},{'id':'second-plan'}]
        def plan(*args,**kwargs):
            b.save_json('script.json',{'candidate':kwargs['only_id']})
            return script,sources
        with patch.dict(os.environ,{'CHANNEL_KEY':'psychology','MODE':'auto'}), patch.object(bank,'eligible_items',return_value=choices), patch.object(bank,'make_plan',side_effect=plan) as make, patch.object(b,'render',side_effect=render_effect) as render, patch.object(auto,'final_review',side_effect=review_effect) as review:
            result=auto.generate_checked(b,None,b.CHANNELS['psychology'],'2026-10-27',[])
            return result,make,render,review
    def test_bad_final_frames_switch_to_next_fixed_plan(self):
        _,make,render,review=self.recovery(review_effect=[auto.QualityRejected('dark image'),{}])
        self.assertEqual(make.call_count,2)
        self.assertEqual(make.call_args.kwargs['only_id'],'second-plan')
        self.assertEqual(b.OUT,self.out)
        self.assertTrue(json.loads((self.out/'auto_recovery.json').read_text())['passed'])
    def test_render_repaired_in_same_candidate(self):
        _,make,render,_=self.recovery(render_effect=[RuntimeError('speech alignment'),[]])
        self.assertEqual(render.call_count,2);self.assertEqual(make.call_count,1)
    def test_all_failed_reviews_stop_without_upload(self):
        with patch.object(b,'upload') as upload:
            with self.assertRaises(RuntimeError):self.recovery(review_effect=auto.QualityRejected('bad visual'))
            upload.assert_not_called()
        self.assertFalse(json.loads((self.out/'auto_recovery.json').read_text())['passed'])
    def test_provider_failure_is_not_rewritten_as_content(self):
        with self.assertRaisesRegex(RuntimeError,'provider unavailable'):
            self.recovery(review_effect=RuntimeError('provider unavailable'))
        self.assertEqual(b.OUT,self.out)
    def test_final_review_requires_complete_scene_coverage(self):
        (self.out/'short.mp4').write_bytes(b'file')
        b.save_json('captions_check.json',dict(passed=True,exact_script_words=True))
        script=Mock();script.scenes=[Mock(narration='A valid claim.')]
        def ffmpeg(args):b.Image.new('RGB',(540,960),'gray').save(args[-1])
        with patch.object(auto,'caption_cues',return_value=[(0,100,'A valid claim.')]),patch.object(auto,'scene_audio_check',return_value={}),patch.object(b,'check_short_file'),patch.object(b,'voice_duration',return_value=5),patch.object(b,'run_ffmpeg',side_effect=ffmpeg),patch.object(b,'generate',return_value=b.VisualReview(choices=[b.VisualChoice(candidate_id=2,approved=True,reason='ok')])),patch.object(b,'storyboard_signature',return_value='hash'):
            with self.assertRaises(auto.QualityRejected):auto.final_review(b,None,script)
        self.assertFalse(json.loads((self.out/'auto_quality.json').read_text())['passed'])

    def test_silent_and_clipped_speech_fail(self):
        import wave
        import numpy as np
        path=self.out/'voice.wav'
        for value in [0,32767]:
            with wave.open(str(path),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(48000)
                wav.writeframes(np.full(4800,value,dtype='<i2').tobytes())
            with self.assertRaises(auto.QualityRejected):auto.scene_audio_check(b,path)

    def test_healthy_audio_passes(self):
        import wave
        import numpy as np
        path=self.out/'voice.wav'
        with wave.open(str(path),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(48000)
            wav.writeframes((np.sin(np.arange(4800)*.1)*8000).astype('<i2').tobytes())
        self.assertGreater(auto.scene_audio_check(b,path)['rms'],.003)

    def test_numbering_format_retries_without_accepting_missing_scenes(self):
        (self.out/'short.mp4').write_bytes(b'file')
        b.save_json('captions_check.json',dict(passed=True,exact_script_words=True))
        script=Mock();script.scenes=[Mock(narration='A valid claim.')]*2
        def ffmpeg(args):b.Image.new('RGB',(540,960),'gray').save(args[-1])
        def verdict(ids):return b.VisualReview(choices=[b.VisualChoice(candidate_id=i,approved=True,reason='checked') for i in ids])
        with patch.object(auto,'caption_cues',return_value=[(0,100,'A valid claim.')]),patch.object(auto,'scene_audio_check',return_value={}),patch.object(b,'check_short_file'),patch.object(b,'voice_duration',return_value=5),patch.object(b,'run_ffmpeg',side_effect=ffmpeg),patch.object(b,'generate',side_effect=[verdict([1,3]),verdict([1,2])]) as generate,patch.object(b,'storyboard_signature',return_value='hash'):
            report=auto.final_review(b,None,script)
            self.assertTrue(report['passed']);self.assertEqual(generate.call_count,2)
            self.assertEqual(report['malformed_id_attempts'],[[1,3]])
            parts=generate.call_args_list[0].args[1]
            self.assertEqual(sum(isinstance(x,b.types.Part) for x in parts),2)

    def test_caption_fragment_context_is_preserved(self):
        path=self.out/'captions.srt'
        path.write_text('1\n00:00:00,100 --> 00:00:01,500\nPOINT NINE TRILLION DOLLARS\n\n2\n00:00:01,500 --> 00:00:02,500\nIN HOUSEHOLD NET WORTH')
        cues=auto.caption_cues(path)
        self.assertEqual(cues[0],(.1,1.5,'POINT NINE TRILLION DOLLARS'))
        self.assertEqual(next(text for a,z,text in cues if a<=1.6<z),'IN HOUSEHOLD NET WORTH')

    def test_existing_video_release_checks_owner_and_never_uploads(self):
        yt=self.fake_yt()
        yt.videos.return_value.list.return_value.execute.side_effect=[{'items':[{'snippet':{
            'channelId':'expected','description':'Content-Bank-ID: confident-ai-errors'},
            'status':{'privacyStatus':'private','uploadStatus':'processed'}}]},
            {'items':[{'status':{'privacyStatus':'public'}}]}]
        with patch.dict(os.environ,{'YT_CHANNEL_ID':'expected'}),patch.object(b,'upload') as upload:
            self.assertEqual(auto.release_existing(b,yt,'ai'),auto.RECOVERY_VIDEOS['ai'])
            upload.assert_not_called()

    def test_recovery_refuses_wrong_channel(self):
        yt=self.fake_yt();yt.videos.return_value.list.return_value.execute.return_value={'items':[{
            'snippet':{'channelId':'wrong','description':'Content-Bank-ID: test'}}]}
        with patch.dict(os.environ,{'YT_CHANNEL_ID':'expected'}):
            with self.assertRaises(RuntimeError):auto.release_existing(b,yt,'ai')
        yt.videos.return_value.update.assert_not_called()

    def test_public_error_report_has_safe_reason_without_token(self):
        yt=self.fake_yt();exc=Exception('SECRET TOKEN MUST NOT BE LOGGED')
        exc.resp=Mock(status=403);exc.content=b'{"error":{"errors":[{"reason":"insufficientPermissions"}]}}'
        yt.videos.return_value.update.return_value.execute.side_effect=exc
        with self.assertRaisesRegex(RuntimeError,'youtube.force-ssl'):auto.set_public(b,yt,'video123')
        data=(self.out/'publication.json').read_text()
        self.assertIn('insufficientPermissions',data);self.assertNotIn('SECRET',data)

    def test_scope_supports_privacy_update(self):
        self.assertEqual(b.SCOPES,['https://www.googleapis.com/auth/youtube.force-ssl'])

    def test_eastern_evening_schedule_tracks_dst(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        workflow=(Path(b.__file__).parent/'.github/workflows/daily_run.yml').read_text()
        self.assertIn('- cron: \"0 19 * * *\"\n      timezone: \"America/New_York\"',workflow)
        event={'timezone':'America/New_York'}
        self.assertEqual(datetime(2026,10,27,19,tzinfo=ZoneInfo(event['timezone'])).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%H:%M'),'04:30')
        self.assertEqual(datetime(2026,11,3,19,tzinfo=ZoneInfo(event['timezone'])).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%H:%M'),'05:30')
