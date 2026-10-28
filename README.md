# youtube-shorts-bot

## Active thirty-day operation: 28 October–26 November 2026 (US dates)

See [MONTH_PLAN.md](MONTH_PLAN.md) for all 120 distinct briefs (30 per channel). These are researched and compiled into scripts on their due day, not pre-rendered or human-approved videos. `calendar/month.json` is the executable calendar; `month_queue.py` only selects due, unused entries. The existing fixed starter bank remains a bounded fallback.

Research is restricted to US primary-source domains and US search locale. Two distinct primary domains must support the narrated script. Before voice generation, a draft receives source/editorial and exact-image storyboard review; at most two pre-freeze drafts are attempted. Once approved, the source packet, script and selected media hashes are frozen in `compiled_plan.json`. Existing TTS alignment, exact captions, complete-video decode and final rendered-frame reviews still apply. Finance calendar entries explain consumer-finance concepts with labelled animations rather than unrelated repeated balance-sheet charts. No fabricated data graphs.

The daily build starts at **18:00 America/New_York**, aiming to finish before **19:00 Eastern publication**. YouTube receives a private video with a verified `publishAt`; the report correctly says `scheduled`, not `public`, until that time. Manual auto runs remain immediate-public after checks. During EDT, the public target is **04:30 IST next day**; during EST it is **05:30 IST next day**. Late runners publish after checks rather than silently moving to tomorrow. GitHub/provider delays can miss the target.

At 18:15, 19:15 and 20:15 Eastern, visibility-only recovery jobs can finish an already-uploaded video. These jobs never research, render or insert a new video. Per-channel concurrency prevents overlap and duplicate guards remain enabled. The machine and this chat can be offline; GitHub Actions and YouTube perform the scheduled work. All API accounts, credits, authorization and the repository must remain available.

Use repository variable `AUTOMATION_ENABLED=false` to pause scheduled work. After 26 November, scheduled channel jobs stop; add a new reviewed calendar to continue. Video/debug artifacts last three days; JSON/subtitle audit trails last 35 days. Major unresolved source/media/audio failures stop publication; this is not a guarantee of 120 successful or error-free published videos.
