"""After visual/source review, seal the exact plan and photo bytes from a preview."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_bot as b
import content_bank as bank


def approve(key, directory, reviewer):
    if not reviewer.strip():
        raise RuntimeError('Name the person who reviewed the actual preview.')
    record = json.loads((directory / 'bank_plan.json').read_text())
    if not str(record.get('render_run_id', '')).isdigit():
        raise RuntimeError('Preview must come from a recorded GitHub render run.')
    item = next((x for x in bank.eligible_items(key, b.datetime.now(b.ZoneInfo('America/New_York')).date().isoformat(), [], 'render')
                 if x['id'] == record['id']), None)
    if item is None or record['plan_sha256'] != item['plan_sha256']:
        raise RuntimeError('Preview does not match the current fixed bank plan.')
    manifest = json.loads((directory / 'bundle.json').read_text())
    if manifest.get('release') != b.RELEASE:
        raise RuntimeError('Preview was made with an older release.')
    old_out = b.OUT
    old_key = os.environ.get('CHANNEL_KEY')
    try:
        b.OUT = directory
        os.environ['CHANNEL_KEY'] = key
        for name in b.bundle_names():
            if b.file_hash(directory / name) != manifest['sha256'].get(name):
                raise RuntimeError('Preview integrity check failed: ' + name)
        script = b.Script.model_validate_json((directory / 'script.json').read_text())
        sources = json.loads((directory / 'research_sources.json').read_text())
        if script.model_dump() != item['plan']['script'] or sources != item['plan']['sources']:
            raise RuntimeError('Preview changed the reviewed plan or evidence.')
        b.validate_script(script, sources)
        audit = b.Audit.model_validate_json((directory / 'fact_check.json').read_text())
        if not b.audit_passes(audit, sources, len(script.scenes)):
            raise RuntimeError('Incomplete factual audit.')
        storyboard = json.loads((directory / 'storyboard_check.json').read_text())
        if not storyboard.get('passed') or storyboard.get('script_sha256') != b.storyboard_signature(script):
            raise RuntimeError('Invalid storyboard audit.')
        b.check_short_file(directory / 'short.mp4')
        assets = json.loads((directory / 'bank_assets.json').read_text())['sha256']
        if set(assets) != {a['key'] for a in item['plan']['assets']} or any(not re.fullmatch(r'[a-f0-9]{64}', value) for value in assets.values()):
            raise RuntimeError('Incomplete reviewed photo hashes.')
        item['approval'] = dict(status='approved', reviewer=reviewer.strip(),
            release=b.RELEASE,
            preview_run_id=str(record['render_run_id']), approved_plan_sha256=item['plan_sha256'], asset_sha256=assets)
        path = bank.ROOT / key / (item['id'] + '.json')
        path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + '\n')
        return path
    finally:
        b.OUT = old_out
        if old_key is None:
            os.environ.pop('CHANNEL_KEY', None)
        else:
            os.environ['CHANNEL_KEY'] = old_key


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channel', required=True, choices=list(b.CHANNELS))
    parser.add_argument('--preview', type=Path, required=True)
    parser.add_argument('--reviewer', required=True)
    args = parser.parse_args()
    print(approve(args.channel, args.preview, args.reviewer))
