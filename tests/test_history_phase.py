import copy
import json
import unittest
from unittest.mock import patch

from test_content_recovery import b, ROOT


class HistoryPhaseTests(unittest.TestCase):
    def draft(self):
        return b.Script.model_validate(json.loads((ROOT / 'tests/fixtures/history_departure_mismatch.json').read_text()))

    def test_actual_departure_image_cannot_illustrate_arrival(self):
        script = self.draft()
        candidate = {'item': {'tags': 'Loading bus, leaving Manzanar for relocation, Manzanar Relocation Center, California.'},
                     'visible_context': 'People loading baggage and leaving Manzanar.'}
        with patch.dict(b.HISTORY_MEDIA, {'a9': candidate}, clear=True):
            issues = b.history_evidence_scope_issues(script)
            self.assertTrue(any("explicit departure at/from 'manzanar'" in issue for issue in issues))
            script.scenes[2].narration = 'Residents loaded baggage onto a bus as they prepared to leave Manzanar.'
            self.assertFalse(any("explicit departure at/from 'manzanar'" in issue for issue in b.history_evidence_scope_issues(script)))

    def test_source_backed_identifier_is_consistent_in_text_and_speech(self):
        script = self.draft()
        sources = [dict(id=2, content='Executive Order 9066, February 19, 1942. Official source.')]
        before = copy.deepcopy(script)
        b.normalize_order_9066(script, sources)
        self.assertIn('Executive Order 9066', script.title)
        self.assertIn('Executive Order 9066', script.description)
        self.assertIn('Executive Order nine zero six six', script.scenes[0].narration)
        self.assertEqual(script.scenes[1:], before.scenes[1:])
        self.assertEqual(b.normalize_order_9066(copy.deepcopy(script), sources), script)

    def test_missing_or_uncited_evidence_cannot_correct_identifier(self):
        for sources in [[], [dict(id=99, content='Executive Order 9066')]]:
            script = self.draft()
            before = copy.deepcopy(script)
            b.normalize_order_9066(script, sources)
            self.assertEqual(script, before)
        script = self.draft()
        script.scenes[0].narration = 'Executive Order 9102 established a different agency and must not be changed to another number.'
        b.normalize_order_9066(script, [dict(id=2, content='Executive Order 9066')])
        self.assertIn('Executive Order 9102', script.scenes[0].narration)

    def test_wartime_exhibit_is_not_decades_later_redress(self):
        script = self.draft()
        candidate = {'item': {'tags': 'Manzanar museum (Ansel Adams exhibit)', 'date': '1943-01-01'}}
        with patch.dict(b.HISTORY_MEDIA, {'a2': candidate}, clear=True):
            self.assertTrue(any('wartime Manzanar museum' in x for x in b.history_evidence_scope_issues(script)))
            script.scenes[-1].narration = 'An exhibition inside the camp documented aspects of life at Manzanar during the war.'
            self.assertFalse(any('wartime Manzanar museum' in x for x in b.history_evidence_scope_issues(script)))
