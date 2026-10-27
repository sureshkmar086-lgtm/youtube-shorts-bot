import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from test_content_recovery import b, ROOT


class CatalogueTravelTests(unittest.TestCase):
    def candidate(self, title='Loading bus, leaving Manzanar for relocation, California.'):
        return {'item': {'tags': title}}

    def test_latest_failed_paraphrase_and_generic_transit_cannot_pass(self):
        for sentence in [
            'Residents lined up with stacked baggage to wait for buses at wartime control administration stations.',
            'People gathered with luggage before boarding a vehicle.',
            'The crowd prepared for transit at a registration facility.',
            'Residents were arriving at Manzanar with their belongings.',
            'Families left their homes and arrived at Manzanar.',
        ]:
            with self.subTest(sentence=sentence):
                self.assertIsNotNone(b.catalogue_travel_issue(self.candidate(), sentence))

    def test_explicit_documented_departure_passes_with_multiple_wordings(self):
        for sentence in [
            'Residents loaded baggage as they prepared to leave Manzanar.',
            'People boarded a bus to depart from Manzanar.',
            'The photograph documents departure from Manzanar.',
        ]:
            with self.subTest(sentence=sentence):
                self.assertIsNone(b.catalogue_travel_issue(self.candidate(), sentence))

    def test_different_places_and_arrival_direction_are_not_hardcoded(self):
        candidate = self.candidate('Departure from Seattle, wartime transport.')
        self.assertIsNone(b.catalogue_travel_issue(candidate, 'Travelers departed from Seattle.'))
        self.assertIsNotNone(b.catalogue_travel_issue(candidate, 'Travelers left Manzanar.'))
        candidate = self.candidate('Arrival at New York, passengers with luggage.')
        self.assertIsNone(b.catalogue_travel_issue(candidate, 'Passengers arrived at New York.'))
        self.assertIsNotNone(b.catalogue_travel_issue(candidate, 'Passengers were leaving New York.'))

    def test_unknown_catalogue_does_not_infer_motion_from_model_reason(self):
        candidate = self.candidate('Camp residents beside a bus.')
        candidate['visible_context'] = 'Model guessed they were leaving Manzanar.'
        self.assertIsNone(b.catalogue_travel_constraint(candidate['item']))
        self.assertIsNone(b.catalogue_travel_issue(candidate, 'Residents stood beside the bus.'))

    def test_wrong_phase_stops_before_ai_can_approve_it(self):
        script = b.Script.model_validate_json((ROOT / 'tests/fixtures/history_departure_mismatch.json').read_text())
        script.scenes[2].narration = 'Residents lined up with stacked baggage to wait for buses at wartime control administration stations.'
        inventory = {s.archive_id: self.candidate('Ordinary archival camp photograph')
                     for s in script.scenes if not s.diagram}
        inventory['a9'] = self.candidate()
        with tempfile.TemporaryDirectory() as temp, patch.object(b, 'OUT', Path(temp)), patch.dict(b.HISTORY_MEDIA, inventory, clear=True), patch.object(b, 'generate') as generate:
            issues = b.check_history_storyboard(None, script, 0)
            report = json.loads((Path(temp) / 'storyboard_check.json').read_text())
        generate.assert_not_called()
        self.assertTrue(issues)
        self.assertFalse(report['passed'])
        check = next(c for c in report['catalogue_travel_checks'] if c['archive_id'] == 'a9')
        self.assertEqual(check['constraint']['direction'], 'departure')
        self.assertEqual(check['constraint']['place'], 'manzanar')
        self.assertTrue(check['issue'])
