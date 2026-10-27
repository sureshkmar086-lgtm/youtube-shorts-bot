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
