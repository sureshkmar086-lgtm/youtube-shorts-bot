import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_content_recovery import b, FIXTURES, ROOT


class HistoryStructureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = b.OUT
        b.OUT = Path(self.temp.name)

    def tearDown(self):
        b.OUT = self.previous
        self.temp.cleanup()

    def test_actual_missing_diagrams_are_repaired_before_return(self):
        broken = b.Script.model_validate(json.loads((ROOT / 'tests/fixtures/history_missing_diagrams.json').read_text()))
        fixed = b.Script.model_validate(copy.deepcopy(FIXTURES['history_script']))
        inventory = {s.archive_id: {} for s in fixed.scenes if not s.diagram}
        sources = copy.deepcopy(FIXTURES['history_sources'])
        sources.append(dict(id=3, url='https://www.loc.gov/example', content='Fixture source'))
        with patch.dict(b.HISTORY_MEDIA, inventory, clear=True), patch.object(b, 'generate', return_value=fixed) as generate:
            result = b.ensure_valid_script(None, broken, sources, history=True, visual_context='APPROVED-INVENTORY')
        self.assertEqual(generate.call_count, 1)
        prompt = generate.call_args.args[1]
        self.assertIn('CURRENT NICHE: DARK HISTORY', prompt)
        self.assertIn('APPROVED-INVENTORY', prompt)
        self.assertNotIn('CURRENT NICHE: FINANCE', prompt)
        self.assertEqual(sum(s.diagram is not None for s in result.scenes), 2)

    def test_repeated_missing_diagrams_cannot_pass_format_gate(self):
        broken = b.Script.model_validate(json.loads((ROOT / 'tests/fixtures/history_missing_diagrams.json').read_text()))
        inventory = {s.archive_id: {} for s in broken.scenes if s.archive_id}
        sources = [dict(id=n, url=f'https://example.com/{n}', content='Fixture source') for n in (1, 2, 3)]
        with patch.dict(b.HISTORY_MEDIA, inventory, clear=True), patch.object(b, 'generate', return_value=broken) as generate:
            with self.assertRaisesRegex(RuntimeError, 'History visual structure'):
                b.ensure_valid_script(None, broken, sources, history=True, visual_context='APPROVED-INVENTORY')
        self.assertEqual(generate.call_count, 2)

    def test_selected_niche_rules_do_not_disable_history_diagrams(self):
        history = b.script_visual_rules(history=True)
        finance = b.script_visual_rules(finance=True)
        self.assertIn('TWO non-null diagram objects', history)
        self.assertNotIn('Every diagram MUST be null', history)
        self.assertIn('Every diagram MUST be null', finance)
