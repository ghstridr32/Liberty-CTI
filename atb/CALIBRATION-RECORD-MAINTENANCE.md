# Maintaining The Calibration Record

`atb/calibration-record-data.json` feeds the "Calibration Record" module on
`atb/index.html` (loaded client-side via `fetch()`, sorted by `status_date`
descending, rendered by the inline `<script>` at the bottom of the
`.calib-section` block). It is a data append, not a full rebuild — do not
regenerate the file from scratch each week.

## After each new ATB issue publishes

1. Open the new issue's Section VIII (Prior Judgment Tracker), or its
   evolved equivalent if the template has changed again.
2. For every prior Key Judgment that section addresses:
   - Find its existing entry in `calibration-record-data.json` by `kj_id`
     (format: `ATB-2026-NN-KJn`).
   - Update `status` (Confirmed / Revised / Unresolved / Tracking /
     Superseded — map only from what the tracker text explicitly states,
     never infer), `status_issue`, `status_date`, `status_url`, and `note`
     (verbatim or close paraphrase of the tracker's own language).
3. Add one new entry per Key Judgment in the new issue's own Section II,
   with `status: "Unresolved / Tracking"`, `status_issue` equal to
   `origin_issue`, and an empty `note` — these are unaddressed until a
   future issue's tracker revisits them.
4. If the new issue's tracker language is ambiguous about which prior KJ
   or issue it refers to, set `"ambiguous": true` and prefix the `note`
   with `AMBIGUOUS:` explaining the uncertainty, exactly as done for the
   three flagged entries in the initial extraction.
5. Validate the JSON (e.g. `python -m json.tool atb/calibration-record-data.json`)
   and mirror the updated file to `dist/atb/calibration-record-data.json`
   per the standard build/deploy process in the root `CLAUDE.md`.

## Before it goes live

Lou spot-checks every new or changed entry — same standard as any other
Calibration Record change: an inaccurate self-grade is worse than no
module at all. Do not deploy a week's update without that review, same as
the initial extraction (see the `<!-- TODO -->` comment above the
`.calib-section` block in `atb/index.html`).
