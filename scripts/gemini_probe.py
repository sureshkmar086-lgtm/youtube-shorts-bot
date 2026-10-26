"""Five bounded, sequential Gemini probes. Never logs keys or response bodies."""
import io
import json
import os
import time
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel, ValidationError

MODELS = ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite')


class MiniAudit(BaseModel):
    claim_ok: bool
    reason: str


def inspect_response(response, kind):
    candidates = getattr(response, 'candidates', None) or []
    finish = getattr(candidates[0], 'finish_reason', None) if candidates else None
    finish = getattr(finish, 'value', finish)
    text = response.text or ''
    result = {'finish_reason': str(finish or 'UNKNOWN'), 'chars': len(text)}
    if finish == 'MAX_TOKENS':
        return dict(result, status='TRUNCATED')
    if finish != 'STOP':
        return dict(result, status='INCOMPLETE_OR_BLOCKED')
    if not text.strip():
        return dict(result, status='EMPTY')
    if kind == 'small_json':
        try:
            audit = MiniAudit.model_validate_json(text)
        except (ValidationError, ValueError):
            return dict(result, status='INVALID_JSON_SCHEMA')
        if not audit.claim_ok or not audit.reason.strip():
            return dict(result, status='UNEXPECTED_ANSWER')
    elif kind == 'minimal_text' and text.strip().upper().strip('.!') != 'READY':
        return dict(result, status='UNEXPECTED_ANSWER')
    elif kind == 'small_image' and 'blue' not in text.lower():
        return dict(result, status='UNEXPECTED_ANSWER')
    usage = getattr(response, 'usage_metadata', None)
    if usage:
        result['input_tokens'] = getattr(usage, 'prompt_token_count', None)
        result['output_tokens'] = getattr(usage, 'candidates_token_count', None)
        result['thinking_tokens'] = getattr(usage, 'thoughts_token_count', None)
    return dict(result, status='OK')


def probe(client, name, model, contents, config):
    started = time.monotonic()
    result = {'probe': name, 'model': model}
    try:
        response = client.models.generate_content(model=model, contents=contents, config=config)
        result.update(inspect_response(response, name))
    except Exception as exc:
        code = getattr(exc, 'code', None)
        # Exception messages can contain request details; record only safe fields.
        result.update(status='REQUEST_FAILED', exception_type=type(exc).__name__,
                      http_status=code if isinstance(code, int) else None)
    result['milliseconds'] = round((time.monotonic() - started) * 1000)
    print(json.dumps(result), flush=True)
    return result


def main():
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        print('Missing GEMINI_API_KEY repository secret; no requests sent.')
        return 2
    results = []
    # Disable SDK retries to measure each independent request. No TTS/research/upload.
    with genai.Client(api_key=key, http_options=types.HttpOptions(
        timeout=60_000, retry_options=types.HttpRetryOptions(attempts=1))) as client:
        for model in MODELS:
            results.append(probe(client, 'minimal_text', model,
                'Reply with the single word READY.',
                types.GenerateContentConfig(max_output_tokens=1024)))
            time.sleep(3)
            results.append(probe(client, 'small_json', model,
                'Check this claim: The US Constitution was signed in 1787. '
                'Return claim_ok and a short reason.',
                types.GenerateContentConfig(response_mime_type='application/json',
                    response_schema=MiniAudit, max_output_tokens=2048)))
            time.sleep(3)
        buf = io.BytesIO()
        Image.new('RGB', (128, 128), color=(40, 80, 120)).save(buf, format='JPEG')
        results.append(probe(client, 'small_image', MODELS[0],
            [types.Part.from_bytes(data=buf.getvalue(), mime_type='image/jpeg'),
             'Name the dominant basic color of this image in at most two words.'],
            types.GenerateContentConfig(max_output_tokens=1024)))
    report = {'results': results, 'limits':
        'Only five small requests. Success does not establish full-pipeline reliability; '
        'failure does not by itself prove a global outage or free-tier restriction.'}
    Path('gemini_probe_report.json').write_text(json.dumps(report, indent=2))
    summary = ['## Gemini diagnostic', '', '| Probe | Model | Result | HTTP |',
               '|---|---|---|---|']
    for row in results:
        summary.append(f"| {row['probe']} | {row['model']} | {row['status']} | {row.get('http_status', '')} |")
    summary.extend(['', report['limits']])
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write('\n'.join(summary) + '\n')
    return 0 if all(row['status'] == 'OK' for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
