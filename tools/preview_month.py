"""Read-only provider integration test: never creates a YouTube client or uploads."""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import agent_bot as b
from month_queue import due_entries,compile_entry,load_calendar
from auto_pipeline import final_review

logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
key=b.required('CHANNEL_KEY')
b.OUT=Path('output')/key;b.OUT.mkdir(parents=True,exist_ok=True)
day=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
# Preview the first upcoming slot before the monthly window starts. No publication.
day=max(day,load_calendar()['start_date'])
entries=due_entries(key,day,[])
if not entries:
    raise SystemExit('No due calendar brief for this preview date.')
config=dict(b.CHANNELS[key])
try:
    with b.genai.Client(api_key=b.required('GEMINI_API_KEY'),http_options=b.types.HttpOptions(timeout=120000)) as client:
        script,sources=compile_entry(b,client,config,day,[],entries[0])
        credits=b.render(script,config,client)
        report=final_review(b,client,script)
    b.save_json('month_live_preview.json',dict(passed=True,channel=key,calendar_id=entries[0]['id'],
        video_sha256=b.file_hash(b.OUT/'short.mp4'),public_upload=False))
    print(f'PASS {key}: live sources/media, real TTS, rendered MP4 and final quality review; NO YOUTUBE UPLOAD.')
except Exception as exc:
    b.save_json('error.json',dict(type=type(exc).__name__,message=str(exc) if isinstance(exc,RuntimeError) else 'See stage reports; provider or media error.'))
    raise SystemExit('Month live preview failed; inspect its stage reports. No upload occurred.') from None
