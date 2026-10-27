import unittest
from test_content_recovery import b

class ScriptCaptionTests(unittest.TestCase):
    def align(self, text, heard):
        words = [(i*.4, i*.4+.3, t) for i,t in enumerate(heard.split())]
        return b.script_word_times(text, words, len(words)*.4+.1)

    def test_known_history_substitutions_keep_script_and_timing(self):
        result = self.align('shared showers and mess halls inside the camp',
                            'shared showers and nest halls inside the camp')
        self.assertEqual([x[2] for x in result], 'shared showers and mess halls inside the camp'.split())
        self.assertEqual(result[3][:2], (3*.4, 3*.4+.3))
        self.assertEqual([x[2] for x in self.align('the elevated view records rows of barracks inside the camp',
            'the elevated view records rose at barracks inside the camp')],
            'the elevated view records rows of barracks inside the camp'.split())

    def test_acronym_and_punctuation_preserved(self):
        result = self.align('NIMH describes stress as a response.', 'nim describes stress as a response')
        self.assertEqual(result[0][2], 'NIMH')
        self.assertEqual(result[-1][2], 'response.')

    def test_missing_and_extra_words_fail(self):
        for heard in ['the source is', 'the original source is checked']:
            with self.assertRaises(RuntimeError): self.align('the source is checked', heard)

    def test_large_transcript_mismatch_fails(self):
        with self.assertRaises(RuntimeError): self.align('the sources support this claim', 'a person likes those things')

    def test_bad_times_fail(self):
        with self.assertRaises(RuntimeError): b.script_word_times('hello', [(0,2,'hello')],1)

    def test_channels_use_distinct_contextual_assets(self):
        import json
        from pathlib import Path
        root=Path(b.__file__).parent/'content_bank'
        groups={}
        for channel in ['ai','psychology']:
            groups[channel]=set()
            for p in (root/channel).glob('*.json'):
                item=json.loads(p.read_text()); assets=item['plan']['assets']
                self.assertEqual(len({a['id'] for a in assets}),4)
                groups[channel].update(a['id'] for a in assets)
                self.assertEqual(item['approval']['status'],'preview')
        self.assertFalse(groups['ai'] & groups['psychology'])
