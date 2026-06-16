# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The Liberty CTI marketing/intelligence website — a **static HTML site** (no JS framework, no bundler). Pages are hand-authored `.html` files at the repo root plus the `atb/` tree. Content is cyber threat intelligence for a Texas/San Antonio audience; the flagship product is the **Alamo Threat Brief (ATB)**, a weekly brief. Buyer persona and brand voice are board/GC-level — see the `anthropic-skills:liberty-cti-board-decision` and `anthropic-skills:about-me` skills before writing client-facing copy.

## Critical: the `dist/` mirror

`wrangler.jsonc` sets `assets.directory: "dist"`, so **Cloudflare serves `dist/`, not the repo root.** Root HTML files are copied verbatim into `dist/`. Editing a root file alone does **not** change the live site.

- For a real build, run the pipeline (below) which regenerates `dist/`.
- For a one-off manual edit, you must also mirror it: `cp <file> dist/<file>` before deploying, or the change silently never ships.

## Build pipeline

`build_publish.ps1` (PowerShell) is the canonical build. It wipes `dist/` (preserving `.vercel`), runs the Python generators in order, then copies HTML/XML/TXT, the `atb/` tree, referenced images, and `assets/` into `dist/`:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_publish.ps1
```

The generators it runs (each is also runnable standalone; all default to **dry-run** and need `--write` to apply):

- `python sync_components.py --write` — injects the canonical nav + footer into every managed HTML page, replacing content between sentinel comments (see below). With `--add-sentinels` it inserts the sentinels into pages that lack them. Auto-populates the ATB nav dropdown from the newest `atb/issues/MM-DD-YYYY.html`.
- `python update_atb_archive.py --write` — scans for dated `MM-DD-YYYY.html` issue files, assigns sequential ATB issue numbers oldest→newest, and rebuilds `atb-archive.html` plus the "latest issue" CTA/count.
- `python optimize_site.py` — SEO, accessibility, and image-loading passes over root pages; applies a shared typography override sitewide.
- `optimize_images.ps1` — image optimization.

There are no automated tests, linters, or a `package.json` in this repo. Verification is by building and viewing pages.

## Managed sections (sentinels)

Nav and footer are **generated, not hand-edited**. Every managed page contains:

```
<!-- LCTI:NAV:START -->    ...nav...    <!-- LCTI:NAV:END -->
<!-- LCTI:FOOTER:START --> ...footer... <!-- LCTI:FOOTER:END -->
```

To change the nav or footer, edit the templates inside `sync_components.py` and re-run it — do not edit the rendered nav/footer in individual pages (it will be overwritten on the next sync). Page-specific content lives outside the sentinels.

## ATB (Alamo Threat Brief) layout

- `atb/issues/MM-DD-YYYY.html` — the canonical dated issue files; their dates drive nav, archive, and issue numbering. The **newest** dated file is the "Latest Issue."
- `atb/2026/MM-DD-YYYY/` — per-issue `full.html`, `index.html`, and `meta.json`.
- `atb-archive.html` — generated index; do not hand-edit (rebuilt by `update_atb_archive.py`).
- Generating a new weekly ATB is handled by the `anthropic-skills:weekly-atb-generator` skill.

## Deploy

1. Make edits; run the build pipeline (or manually mirror to `dist/`).
2. Stage **only intended files** — do not `git add -A`. The working tree intermittently shows spurious ATB file deletions from OneDrive sync; restore them first with `git checkout HEAD -- <paths>` so a deploy does not wipe the posted ATB.
3. `git push origin main` — `main` is protected (PR required) but the maintainer has bypass, so a direct push succeeds.
4. `npx wrangler deploy` (wrangler 4.x) — uploads only changed assets from `dist/`.
5. Verify live at `https://liberty-cti.ghstridr32.workers.dev`. `libertycti.com` currently 302-redirects to a link-forwarding host (`libertycti-com.l.ink`), so the workers.dev URL is the reliable canonical endpoint. (In a sandbox, `curl` may fail TLS — use WebFetch to verify.)

## Directories that are not part of the site

These are scratch/archive/working areas and are excluded in `robots.txt`; do not treat them as live pages or include them in builds:

- `Extra/`, `April 2026/` — old page versions and drafts.
- `Intel Production/` — ATB drafting inputs, templates, RSS candidates.
- `Operational Dashboard/` — internal dashboards/mockups.
- `dist/` — generated output (mirror of root + `atb/`); never edit by hand as the source of truth.
- `*.bak` files — local backups, not deployed.

## RSS / intel sourcing

`rss-feeds.json` defines the CTI source feeds (CISA, HHS HC3, vendor threat-intel blogs, Texas regional, geopolitical). `update_rss_collection.ps1` / `install_rss_collection_task.ps1` drive scheduled collection that feeds `Intel Production/rss-candidates.json` for ATB drafting.
