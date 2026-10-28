import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_content_recovery import b, FIXTURES


class APIError(Exception):
    def __init__(self, code):
        self.code = code


class ModelRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = b.OUT
        b.OUT = Path(self.tmp.name)
        b.MODEL_SESSION_CHOICE = None

    def tearDown(self):
        b.OUT = self.previous
        b.MODEL_SESSION_CHOICE = None
        self.tmp.cleanup()

    def test_503_fallback_keeps_schema_and_sticks_for_next_call(self):
        client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(
            side_effect=[APIError(503)] * 3 + [SimpleNamespace(text='{"queries":["office desk","adult keyboard","home laptop"]}')] * 2)))
        with patch.dict(b.os.environ, {'GEMINI_MODEL': 'primary', 'GEMINI_FALLBACK_MODEL': 'backup'}), patch.object(b.time, 'sleep') as sleep, patch.object(b.random, 'uniform', return_value=0):
            b.generate(client, 'same evidence', b.StockSearchRepair)
            b.generate(client, 'next audit', b.StockSearchRepair, audit=True)
        calls = client.models.generate_content.call_args_list
        self.assertEqual([c.kwargs['model'] for c in calls], ['primary'] * 3 + ['backup'] * 2)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [15, 30])
        self.assertTrue(all(c.kwargs['config'].response_schema == b.StockSearchRepair for c in calls))

    def test_httpx_read_timeout_retries_and_uses_fallback(self):
        client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(
            side_effect=[b.httpx.ReadTimeout('provider timed out')] * 3 + [SimpleNamespace(text='{"queries":["office desk","adult keyboard","home laptop"]}')])))
        with patch.dict(b.os.environ, {'GEMINI_MODEL':'primary','GEMINI_FALLBACK_MODEL':'backup'}), patch.object(b.time,'sleep'):
            result=b.generate(client,'evidence',b.StockSearchRepair)
        self.assertEqual(len(result.queries),3)
        self.assertEqual([c.kwargs['model'] for c in client.models.generate_content.call_args_list],['primary']*3+['backup'])

    def test_schema_retry_includes_validation_feedback(self):
        client=SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=[
            SimpleNamespace(text='{"queries":["desk"]}'),
            SimpleNamespace(text='{"queries":["office desk","adult keyboard","home laptop"]}') ])))
        with patch.object(b.time,'sleep'):
            result=b.generate(client,'original evidence',b.StockSearchRepair)
        self.assertEqual(len(result.queries),3)
        second=client.models.generate_content.call_args_list[1].kwargs['contents']
        self.assertIn('FORMAT REPAIR',second)
        self.assertIn('original evidence',second)

    def test_persistent_invalid_json_can_fall_back_but_auth_still_cannot(self):
        client=SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=[
            SimpleNamespace(text='{"queries":["desk"]}')]*3+[
            SimpleNamespace(text='{"queries":["office desk","adult keyboard","home laptop"]}') ])))
        with patch.dict(b.os.environ,{'GEMINI_MODEL':'primary','GEMINI_FALLBACK_MODEL':'backup'}), patch.object(b.time,'sleep'):
            b.generate(client,'evidence',b.StockSearchRepair)
        self.assertEqual([c.kwargs['model'] for c in client.models.generate_content.call_args_list],['primary']*3+['backup'])

    def test_auth_error_is_not_retried_or_hidden(self):
        client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=APIError(403))))
        with patch.object(b.time, 'sleep') as sleep, self.assertRaises(RuntimeError):
            b.generate(client, 'evidence', b.StockSearchRepair)
        self.assertEqual(client.models.generate_content.call_count, 1)
        sleep.assert_not_called()

    def test_selected_fallback_can_recover_back_to_original_model(self):
        b.MODEL_SESSION_CHOICE = 'backup'
        client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(
            side_effect=[APIError(503)] * 3 + [SimpleNamespace(text='{"queries":["office desk","adult keyboard","home laptop"]}') ])))
        with patch.dict(b.os.environ, {'GEMINI_MODEL': 'primary', 'GEMINI_FALLBACK_MODEL': 'backup'}), patch.object(b.time, 'sleep'):
            b.generate(client, 'repair draft', b.StockSearchRepair)
        self.assertEqual([c.kwargs['model'] for c in client.models.generate_content.call_args_list], ['backup'] * 3 + ['primary'])
        self.assertEqual(b.MODEL_SESSION_CHOICE, 'primary')

    def test_persistent_outage_is_bounded_and_does_not_log_secret(self):
        client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=APIError(503))))
        with patch.dict(b.os.environ, {'GEMINI_MODEL': 'primary', 'GEMINI_FALLBACK_MODEL': 'backup'}), patch.object(b.time, 'sleep'), self.assertRaises(RuntimeError):
            b.generate(client, 'private-key-do-not-log', b.StockSearchRepair)
        self.assertEqual(client.models.generate_content.call_count, 6)
        report = (b.OUT / 'model_error.json').read_text()
        self.assertNotIn('private-key-do-not-log', report)
        self.assertEqual(len(json.loads(report)['failures']), 6)

    def test_finance_duplicate_diagram_is_removed_without_changing_words(self):
        script = b.Script.model_validate(copy.deepcopy(FIXTURES['history_script']))
        for n, scene in enumerate(script.scenes):
            scene.visual_id = f's{n}'
            scene.diagram = b.ExplainerSpec(kind='comparison', title='Q2 2026', labels=['Assets', 'Debt'], note='Verified values')
        original = [s.narration for s in script.scenes]
        inventory = {s.visual_id: {'kind': 'photo'} for s in script.scenes}
        with patch.dict(b.FINANCE_MEDIA, inventory, clear=True), patch.object(b, 'validate_script'):
            result = b.ensure_valid_script(None, script, [], finance=True)
        self.assertTrue(all(s.diagram is None for s in result.scenes))
        self.assertEqual([s.narration for s in result.scenes], original)


