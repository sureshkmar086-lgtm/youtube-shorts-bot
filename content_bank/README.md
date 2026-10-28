Monthly operation (28 October–26 November 2026) is documented in [MONTH_PLAN.md](../MONTH_PLAN.md) and [README.md](../README.md). The starter-bank/manual-review details below remain fallback behavior.

# Fixed content bank

Normal `render`/`upload` runs now select a fixed plan from this directory. They do
not search for a trend, invent a new script, reassign images, or rewrite a rejected
script. Gemini remains an independent rejection/checking service, not the author
of the final runtime plan. The old research functions remain for regression work;
the production entry point does not call them.

## Starter collection

Eight source-reviewed starter plans are included: two each for History,
Psychology, Finance and AI. Each has a fixed script, source summaries, exact image
IDs and mappings, a plan digest, and a review expiry. Finance uses the explicitly
dated September 11, 2026 release for Q2 2026, not a claim about today's wealth.
Different plans can share an illustrative image; an individual video never repeats
its photos. This is a finite demonstration collection, not an unlimited daily feed.

The starter plans are `preview`, not approved for automatic upload. Previous
automatic model approvals missed real mistakes; no unreviewed starter is labelled
production-ready. Render and inspect each first preview before promotion.

## What a normal run does

1. Read the visible channel upload history (up to 1000 entries). Stop if it is
   incomplete. Skip already used bank IDs, exact narration fingerprints and titles.
2. Check plan digest, expiry and approval eligibility. Render permits previews;
   automatic upload permits only approved plans with reviewed preview/image hashes.
3. Try at most two unused eligible plans. Download only their exact pinned images.
   No substitute search result is allowed. Recheck catalogue identity/rights and,
   after approval, the exact image bytes.
4. Run format, factual, numeric and storyboard checks on the immutable script.
   A content/media rejection can move to the next fixed plan. A provider/service
   failure stops instead of multiplying requests across the entire bank.
5. Generate speech and render only the selected passing plan. Reject missing or
   changed evidence rather than fabricate a replacement. A post-render/TTS failure
   stops; it does not spend money rendering every remaining plan.
6. If no unused approved plan is available, report `SKIPPED` and make/upload
   nothing. A green skipped workflow is not evidence that a video was created.

## First review and promotion

Run the normal workflow with `main`, selected channel, `render`, empty source run.
Download that artifact. Review the actual MP4, photo direction/date/identity,
script, source evidence, numbers, subtitles and narration. Offline tests are not
a substitute for this editorial review.

After review, a repository editor can seal the exact preview:

```sh
python tools/approve_bank.py --channel history --preview /path/to/extracted-preview --reviewer "Name and date of actual review"
```

The helper checks the bundle, exact script/source digest, audits, full video
decode and asset hashes. It updates only the matching bank JSON. Commit that
reviewed change. Merely changing `status` to `approved` is insufficient: the
reviewed preview run, matching plan digest and all photo hashes are required.
This helper records an editor's review; it cannot perform human editorial review.

`publish` also requires current bank approval matching the preview plan and photo
hashes. YouTube credentials/privacy and `AUTOMATION_ENABLED` are unchanged.
No public upload or scheduled activation is performed by this change.

## Refill and limitations

Add new exact source-backed plans and preview them before approval. Recompute the
plan digest whenever script, evidence, image IDs or mappings change; that does not
carry over the old approval. Keep a useful backlog before enabling a daily feed.
Expired plans or unavailable/changed images require review. Even a fixed bank can
encounter service failures, stale evidence or an editorial mistake; this design
limits invention and fails closed, it does not guarantee perfect content or
YouTube monetization. The two starter plans per channel will run out; they are
never silently recycled.

## Authorized automatic publication

`MODE=auto` opts into machine-reviewed publication without the manual first-preview approval requirement. It accepts the existing fixed, unexpired preview plans; facts are not freely rewritten. Each channel tries at most two eligible plans. A render/audio failure retries rendering once; failed content or final visual quality switches to the next fixed plan in the same run. If all fail, nothing is uploaded.

Final review samples two actual rendered frames per scene and checks scene coverage, captions, charts and major visual defects. Minor cosmetic imperfections are acceptable. This is a bounded automated review, not a claim that all errors are detectable. On success, one private upload is processed, then visibility is changed to public and read back. Processing, upload, or visibility failures never trigger a replacement upload. Reports: `auto_quality.json`, `auto_recovery.json`, `publication.json`.

The schedule now uses auto mode, enabled by default per owner authorization. To pause scheduled jobs, set repository **variable** `AUTOMATION_ENABLED=false` (the legacy secret is no longer used). Manual `render` remains available for previews. There are only two starter plans per channel; once used or expired, the bank skips safely until new content is added. No automatic reuse of published plans.

## Public visibility permission and existing-upload recovery

The OAuth refresh token must be authorized for `https://www.googleapis.com/auth/youtube.force-ssl` (the scope supported by both videos.insert and videos.update). Changing Python scopes cannot grant new consent to old refresh tokens. Keep the existing client ID, secret and channel IDs. In OAuth Playground, use your own OAuth credentials, enter this scope, authorize the correct channel, exchange the code, and replace only that channel's YT_REFRESH_TOKEN_* secret. Repeat for all four channels. Do not paste keys/tokens into chat or repository files.

After reauthorization, manually select `all / release_existing` on main. This operates only on the four exact videos uploaded by run 40449573825, checks channel ownership and the content-bank marker, waits for processing if needed, and changes visibility without TTS, rendering or insertion. Already-public videos are skipped idempotently. `publication.json` includes sanitized HTTP status and API reason codes if publication fails. Platform restrictions can still prevent public visibility and are not bypassed.

Daily production now starts at **18:00 America/New_York**, targeting YouTube publication at **19:00 Eastern**, with timezone-aware GitHub scheduling. This is **04:30 IST the next day during EDT**, and **05:30 IST during EST**. It is a chosen initial Eastern-evening slot, not a claim of measured channel-specific optimal time. Videos become public after rendering, checks and processing; GitHub queues can delay starts. The schedule is not an exact 19:00 publication promise.

