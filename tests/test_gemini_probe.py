import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('probe', Path(__file__).resolve().parents[1] / 'scripts/gemini_probe.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def response(text, finish='STOP'):
    return SimpleNamespace(text=text, candidates=[SimpleNamespace(finish_reason=finish)])


class ProbeTests(unittest.TestCase):
    def test_truncation_is_not_success_or_server_failure(self):
        self.assertEqual(p.inspect_response(response('READY', 'MAX_TOKENS'), 'minimal_text')['status'], 'TRUNCATED')

    def test_empty_and_invalid_json_are_not_ok(self):
        self.assertEqual(p.inspect_response(response(''), 'minimal_text')['status'], 'EMPTY')
        self.assertEqual(p.inspect_response(response('{"claim_ok":true}'), 'small_json')['status'], 'INVALID_JSON_SCHEMA')

    def test_json_and_expected_answer_pass(self):
        self.assertEqual(p.inspect_response(response('{"claim_ok":true,"reason":"Signed in 1787."}'), 'small_json')['status'], 'OK')
        self.assertEqual(p.inspect_response(response('READY'), 'minimal_text')['status'], 'OK')

    def test_exception_details_are_not_logged(self):
        client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=RuntimeError('secret-value'))))
        with patch('builtins.print') as output:
            result = p.probe(client, 'minimal_text', 'model', 'request', None)
        self.assertEqual(result['status'], 'REQUEST_FAILED')
        self.assertNotIn('secret-value', str(output.call_args))

    def test_missing_key_does_not_construct_client(self):
        with patch.dict(p.os.environ, {'GEMINI_API_KEY': ''}), patch.object(p.genai, 'Client') as client, patch('builtins.print'):
            self.assertEqual(p.main(), 2)
        client.assert_not_called()
