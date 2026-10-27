import copy
import contextlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import content_bank as bank
from test_content_recovery import b, ROOT


class ContentBankTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous_out = b.OUT
        b.OUT = self.root / 'output'
        b.OUT.mkdir()

    def tearDown(self):
        b.OUT = self.previous_out
        self.tmp.cleanup()

    def seed(self, key='history', approval='preview'):
        item = json.loads(sorted((bank.ROOT / key).glob('*.json'))[0].read_text())
        item['approval']['status'] = approval
        if approval == 'approved':
            item['approval'].update(preview_run_id='123', approved_plan_sha256=item['plan_sha256'],
                                    release=b.RELEASE,
                                    asset_sha256={a['key']: 'a' * 64 for a in item['plan']['assets']})
        path = self.root / key / (item['id'] + '.json')
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(item))
        return item, path

    def test_preview_plans_cannot_enter_automatic_upload(self):
        self.seed()
        self.assertEqual(len(bank.eligible_items('history', '2026-10-27', [], 'render', self.root)), 1)
        self.assertEqual(bank.eligible_items('history', '2026-10-27', [], 'upload', self.root), [])

    def test_used_and_expired_items_are_not_recycled(self):
        item, _ = self.seed(approval='approved')
        recent = [{'snippet': {'description': 'Content-Bank-ID: ' + item['id'] + '\n'}}]
        self.assertEqual(bank.eligible_items('history', '2026-10-27', recent, 'upload', self.root), [])
        self.assertEqual(bank.eligible_items('history', '2028-01-01', [], 'render', self.root), [])

    def test_changed_text_invalidates_review(self):
        item, path = self.seed()
        item['plan']['script']['scenes'][0]['narration'] = 'Invented new claim.'
        path.write_text(json.dumps(item))
        with self.assertRaisesRegex(RuntimeError, 'changed without'):
            bank.eligible_items('history', '2026-10-27', [], 'render', self.root)

    def test_approved_requires_reviewed_photo_hashes(self):
        item, path = self.seed(approval='approved')
        item['approval']['asset_sha256'] = {}
        path.write_text(json.dumps(item))
        with self.assertRaisesRegex(RuntimeError, 'photos need hashes'):
            bank.eligible_items('history', '2026-10-27', [], 'upload', self.root)

    def test_all_eight_seed_plans_pass_format_sources_and_deterministic_rules(self):
        paths = list(bank.ROOT.glob('*/*.json'))
        self.assertEqual(len(paths), 8)
        for path in paths:
            item = json.loads(path.read_text()); plan = item['plan']
            script = b.Script.model_validate(plan['script'])
            with self.subTest(id=item['id']):
                self.assertEqual(item['plan_sha256'], bank.plan_hash(plan))
                b.validate_script(script, plan['sources'])
                self.assertTrue(all(b.allowed_host(s['url'], b.CHANNELS[item['channel']]['domains']) for s in plan['sources']))
                inventory = {a['key']: dict(kind='photo', query=a['subject_group'], item={'tags': ', '.join(a.get('catalogue_terms', []))}) for a in plan['assets']}
                if item['channel'] == 'history':
                    with patch.dict(b.HISTORY_MEDIA, inventory, clear=True):
                        self.assertEqual(b.history_plan_issues(script), [])
                        self.assertEqual(b.history_evidence_scope_issues(script), [])
                elif item['channel'] == 'finance':
                    with patch.dict(b.FINANCE_MEDIA, inventory, clear=True):
                        b.add_finance_graphics(None, plan['sources'])
                        self.assertEqual(b.finance_plan_issues(script), [])
                        self.assertEqual(b.finance_numeric_issues(script, plan['sources']), [])
                else:
                    with patch.dict(b.GENERAL_MEDIA, inventory, clear=True):
                        self.assertEqual(b.general_plan_issues(script), [])

    def test_failed_item_uses_next_fixed_item_without_rewriting(self):
        first, path = self.seed()
        second = next(json.loads(p.read_text()) for p in sorted((bank.ROOT / 'history').glob('*.json'))
                      if json.loads(p.read_text())['id'] != first['id'])
        (path.parent / (second['id'] + '.json')).write_text(json.dumps(second))
        def prepare(bot, client, item, script, config):
            if item['id'] == first['id']:
                raise bank.ItemRejected('Pinned asset unavailable')
            bot.save_json('bank_assets.json', {'sha256': {}})
        with patch.dict(os.environ, {'CHANNEL_KEY': 'history', 'MODE': 'render'}), patch.object(bank, 'prepare_assets', side_effect=prepare), patch.object(bank, 'audit_plan'), patch.object(b, 'generate') as generate:
            script, _ = bank.make_plan(b, None, b.CHANNELS['history'], '2026-10-27', [], self.root)
        generate.assert_not_called()
        self.assertEqual(script.model_dump(), second['plan']['script'])
        self.assertEqual(json.loads((b.OUT / 'bank_plan.json').read_text())['id'], second['id'])

    def test_empty_bank_does_not_fall_back_to_free_form_generation(self):
        with patch.dict(os.environ, {'CHANNEL_KEY': 'history', 'MODE': 'render'}), patch.object(b, 'generate') as generate:
            with self.assertRaises(bank.BankEmpty):
                bank.make_plan(b, None, b.CHANNELS['history'], '2026-10-27', [], self.root)
        generate.assert_not_called()

    def test_provider_failure_does_not_retry_every_item(self):
        self.seed()
        with patch.dict(os.environ, {'CHANNEL_KEY': 'history', 'MODE': 'render'}), patch.object(bank, 'prepare_assets'), patch.object(bank, 'audit_plan', side_effect=RuntimeError('Gemini temporarily unavailable')) as audit:
            with self.assertRaisesRegex(RuntimeError, 'Gemini temporarily'):
                bank.make_plan(b, None, b.CHANNELS['history'], '2026-10-27', [], self.root)
        self.assertEqual(audit.call_count, 1)
        self.assertEqual(b.OUT, self.root / 'output')

    def test_changed_asset_bytes_are_rejected_before_voice(self):
        item, _ = self.seed(approval='approved')
        asset = item['plan']['assets'][0]
        def download(url, path, **kw):
            path.write_bytes(b'changed photograph bytes')
        with patch.object(bank, 'exact_asset', return_value=('https://tile.loc.gov/photo.jpg', {})), patch.object(b, 'download', side_effect=download):
            with self.assertRaisesRegex(bank.ItemRejected, 'changed bytes'):
                bank.prepare_assets(b, None, item, b.Script.model_validate(item['plan']['script']), b.CHANNELS['history'])

    def test_manual_publish_requires_bank_approval(self):
        item, _ = self.seed()
        (b.OUT / 'bank_plan.json').write_text(json.dumps({'id': item['id'], 'plan_sha256': item['plan_sha256']}))
        with self.assertRaisesRegex(RuntimeError, 'first preview review'):
            bank.verify_approved_preview('history', b.OUT, self.root)

    def test_narration_fingerprint_prevents_same_script_under_new_title(self):
        item, _ = self.seed()
        recent = [{'snippet': {'description': 'Content-Bank-Script: ' + bank.script_hash(item['plan'])}}]
        self.assertEqual(bank.eligible_items('history', '2026-10-27', recent, 'render', self.root), [])

    def test_approval_files_are_mandatory_not_optional_bundle_members(self):
        with patch.dict(os.environ, {'CHANNEL_KEY': 'history'}):
            self.assertIn('bank_plan.json', b.bundle_names())
            self.assertIn('bank_assets.json', b.bundle_names())

    def test_main_empty_bank_does_not_open_a_generation_client(self):
        def preflight(config, services):
            self.assertFalse(services)
            b.save_json('channel_upload_status.json', {'history_complete': True})
            return None, []
        with contextlib.chdir(self.root), patch.dict(sys.modules, {b.__name__: b}), patch.dict(os.environ, {'CHANNEL_KEY': 'history', 'MODE': 'render'}), patch.object(b, 'preflight', side_effect=preflight), patch.object(bank, 'eligible_items', return_value=[]), patch.object(b.genai, 'Client') as client, patch.object(b, 'summary') as summary:
            b.main()
        client.assert_not_called()
        self.assertIn('SKIPPED', summary.call_args.args[0])
