import copy
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
FIXTURES=json.loads((ROOT/'tests/fixtures/content_failures.json').read_text())
spec=importlib.util.spec_from_file_location('bot',ROOT/'agent_bot.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=b.OUT;b.OUT=Path(self.temp.name)
    def tearDown(self):
        b.OUT=self.old;self.temp.cleanup()
    def test_four_approved_images_can_form_six_scenes(self):
        report=copy.deepcopy(FIXTURES['ai'])
        sources=copy.deepcopy(FIXTURES['ai_sources'])
        brief=b.MediaBrief.model_validate(report['brief'])
        review=b.VisualReview.model_validate(report['review'])
        candidates=[dict(id=r.candidate_id,item={'pageURL':f'https://example.com/{r.candidate_id}'},path=b.OUT/'test.jpg') for r in review.choices]
        def generate(client,prompt,schema,**kw):
            if schema==b.MediaBrief:return brief
            if schema==b.StockSearchRepair:return b.StockSearchRepair(queries=['adult keyboard','office colleagues','desktop computer'])
            raise AssertionError(schema)
        with patch.object(b,'generate',side_effect=generate),patch.object(b,'collect_stock_batch',side_effect=[(candidates,[]),([],[])]) as collect,patch.object(b,'review_stock_batch',return_value=review):
            context=b.prepare_general_media(None,b.CHANNELS['ai'],sources)
        self.assertEqual(collect.call_count,2)
        self.assertEqual(set(b.GENERAL_MEDIA),{'s5','s6','s7','s10'})
        self.assertIn('exactly 6 scenes: 4 different stock photos',context)
    def test_replacement_image_produces_seven_scenes(self):
        report=copy.deepcopy(FIXTURES['ai'])
        sources=copy.deepcopy(FIXTURES['ai_sources'])
        brief=b.MediaBrief.model_validate(report['brief']);review=b.VisualReview.model_validate(report['review'])
        candidates=[dict(id=r.candidate_id,item={'pageURL':f'https://example.com/{r.candidate_id}'},path=b.OUT/'test.jpg') for r in review.choices]
        extra=dict(id=11,item={'pageURL':'https://example.com/new'},path=b.OUT/'new.jpg')
        def generate(client,prompt,schema,**kw):
            return brief if schema==b.MediaBrief else b.StockSearchRepair(queries=['adult keyboard','office colleagues','desktop computer'])
        with patch.object(b,'generate',side_effect=generate),patch.object(b,'collect_stock_batch',side_effect=[(candidates,[]),([extra],[])]),patch.object(b,'review_stock_batch',side_effect=[review,b.VisualReview(choices=[b.VisualChoice(candidate_id=11,approved=True,reason='Adult typing at keyboard')])]):
            context=b.prepare_general_media(None,b.CHANNELS['psychology'],sources)
        self.assertEqual(len(b.GENERAL_MEDIA),5);self.assertIn('exactly 7 scenes: 5 different stock photos',context)
    def test_short_queries(self):
        for query in ['person sitting at kitchen table paying bills','adult looking thoughtfully out apartment window','office workers meeting']:
            self.assertLessEqual(len(b.short_stock_query(query).split()),4)
    def complete_source(self):
        return copy.deepcopy(FIXTURES['complete_finance'])
    def table_html(self):
        source=self.complete_source();table=b.fed_balance_sheet(source)
        headers=['2022','2023','2024','2025','2026:Q1','2026:Q2']
        rows='<tr><th></th>'+''.join(f'<th>{v}</th>' for v in headers)+'</tr>'
        for label in ['Assets','Owner-occupied real estate','Liabilities','Net worth']:
            row=table['rows'][label]['quote'];cells=[x.strip() for x in row.split('|') if x.strip()]
            rows+='<tr>'+''.join(f'<td>{x}</td>' for x in cells)+'</tr>'
        return '<html><script>bad numbers</script><h3>Table 1: Condensed household balance sheet</h3><p>Trillions of dollars</p><table>'+rows+'</table><p>Note: official table</p></html>'
    def test_complete_table_retained_after_large_navigation_prefix(self):
        source=self.complete_source();long='Navigation '*900+source['content']
        retained=b.retained_source_content(long,source['url'])
        parsed=b.fed_balance_sheet(dict(source,content=retained))
        self.assertEqual(parsed['rows']['Net worth']['value'],'195.9')
    def test_direct_html_recovers_actual_truncated_finance_packet(self):
        items=copy.deepcopy(FIXTURES['truncated_finance'])
        document=self.table_html()
        class Response:
            ok=True;status_code=200
            url='https://www.federalreserve.gov/releases/z1/current/recent_developments.htm'
            text=document;content=document.encode()
        with patch.object(b.HTTP,'get',return_value=Response()) as get:
            sources=b.source_packet(b.ensure_finance_evidence(items))
        self.assertEqual(get.call_count,1)
        direct=next(x for x in sources if x.get('retrieval_method')=='direct_official_html')
        self.assertEqual(b.fed_balance_sheet(direct)['rows']['Liabilities']['value'],'21.9')
        # A later search result must not overwrite complete official HTML with
        # the same 6500-character truncated page that caused the real failure.
        truncated=next(x for x in items if x['url']==direct['url'])
        merged=b.source_packet([*sources,truncated])
        preserved=next(x for x in merged if x['url']==direct['url'])
        self.assertEqual(preserved['content'],direct['content'])
        b.FINANCE_MEDIA.clear();b.add_finance_graphics(None,merged)
        self.assertEqual(len(b.FINANCE_MEDIA),3)
    def test_malformed_official_table_not_accepted(self):
        with self.assertRaises(RuntimeError):b.finance_html_source(self.table_html().replace('Net worth','Missing row'),'https://www.federalreserve.gov/releases/z1/current/recent_developments.htm')
    def test_denied_direct_request_uses_full_official_extraction(self):
        complete=self.complete_source()
        class Response:
            ok=True;status_code=200
            def json(self):return {'results':[{'url':complete['url'],'raw_content':complete['content']}],'failed_results':[]}
        with patch.object(b.HTTP,'get',side_effect=b.requests.HTTPError('Denied')),patch.object(b.HTTP,'post',return_value=Response()) as post,patch.dict(b.os.environ,{'TAVILY_API_KEY':'offline-fixture-key'}):
            result=b.ensure_finance_evidence(copy.deepcopy(FIXTURES['truncated_finance']))
        self.assertEqual(result[-1]['retrieval_method'],'full_official_extract')
        self.assertNotIn('query',post.call_args.kwargs['json'])
        self.assertEqual(post.call_args.kwargs['json']['urls'],[complete['url']])
        self.assertEqual(b.fed_balance_sheet(result[-1])['rows']['Net worth']['value'],'195.9')
    def test_visual_repairs_not_exhausted_by_fact_repairs(self):
        script=b.Script.model_validate(FIXTURES['history_script'])
        sources=copy.deepcopy(FIXTURES['history_sources'])
        good=b.Audit.model_validate(FIXTURES['history_audit']);good.passed=True;good.issues=[]
        calls={'audits':0,'visuals':0}
        def generate(client,prompt,schema,**kw):
            if schema==b.Audit:
                calls['audits']+=1;a=copy.deepcopy(good)
                if calls['audits']<3:a.passed=False;a.issues=['Fixture factual issue requiring a supported revision']
                return a
            if schema==b.Script:
                result=copy.deepcopy(script)
                if 'Current repair category: storyboard' in prompt:
                    result.scenes[5].narration='Before the eviction, veterans lived in makeshift camps beside the river while waiting for an early payment.'
                return result
            raise AssertionError(schema)
        def storyboard(*args):
            calls['visuals']+=1
            return ['Scene 6: peaceful camp must not portray active burning.'] if calls['visuals']==1 else []
        inventory={s.archive_id:{} for s in script.scenes if not s.diagram}
        with patch.dict(b.HISTORY_MEDIA,inventory,clear=True),patch.object(b,'prepare_history_package',return_value=('1932 Bonus Army eviction Washington',sources,'Exact approved photo inventory')),patch.object(b,'search_sources',return_value=[]),patch.object(b,'generate',side_effect=generate),patch.object(b,'check_history_storyboard',side_effect=storyboard):
            result,_=b.make_script(None,b.CHANNELS['history'],'2026-10-26',[])
        self.assertEqual(calls,{'audits':4,'visuals':2})
        self.assertTrue(result.scenes[5].narration.startswith('Before the eviction'))

if __name__=='__main__':unittest.main(verbosity=2)
