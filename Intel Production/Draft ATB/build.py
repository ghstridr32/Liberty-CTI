#!/usr/bin/env python3
"""
build.py — Alamo Threat Brief build pipeline

Reads inputs/this-week.md, renders into templates/atb_skeleton.html, and
produces the new per-issue directory structure under atb/<year>/<slug>/:

  atb/<year>/<slug>/full.html    — complete brief
  atb/<year>/<slug>/index.html   — public preview (truncated at PREVIEW_CUT + CTA)
  atb/<year>/<slug>/meta.json    — issue metadata for the archive index
  atb/index.html                  — rebuilt public archive listing

Run from this directory:
  python build.py
"""

from __future__ import annotations

import json
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ─── Paywall control ──────────────────────────────────────────────────────────
# PAYWALL_ACTIVE:
#   False → preview period. CTA shows "Read Full Brief → ./full.html".
#           Both index.html and full.html are publicly accessible.
#   True  → paywall enforced. CTA shows "Subscribe" → /members/subscribe.html.
#           Cloudflare Pages Functions gate full.html (Phase 2).
#           Flip to True ONLY after Phase 2 is live and smoke-tested in production.
PAYWALL_ACTIVE = False

# PREVIEW_BANNER_ENABLED:
#   True  → shows a slim banner above the nav during the preview period.
#   False → no banner. Use False once paywall is active.
#   Only rendered when PAYWALL_ACTIVE = False. Ignored when PAYWALL_ACTIVE = True.
PREVIEW_BANNER_ENABLED = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent          # repo root (two levels up from Intel Production/Draft ATB/)
TEMPLATE_DIR = HERE / "templates"
INPUTS_DIR = HERE / "inputs"
ARCHIVE_ROOT = ROOT / "atb"

PREVIEW_CUT = "<!--PREVIEW_CUT-->"


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Date / slug parsing
# ---------------------------------------------------------------------------

def slug_from_publish_date(publish_date_str: str) -> tuple[str, str]:
    """
    Convert '17 May 2026' or '2026-05-17' into ('2026', '05-17-2026').
    Returns (year_str, slug_str).
    """
    for fmt in ("%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            dt = datetime.strptime(publish_date_str.strip(), fmt)
            return str(dt.year), dt.strftime("%m-%d-%Y")
        except ValueError:
            continue
    raise ValueError(f"Could not parse publish_date: {publish_date_str!r}")


# ---------------------------------------------------------------------------
# Preview split
# ---------------------------------------------------------------------------

def build_preview_html(full_html: str, cta_html: str) -> str:
    """
    Split full_html at <!--PREVIEW_CUT--> and stitch the CTA in place of the
    gated content, keeping the footer.
    """
    if PREVIEW_CUT not in full_html:
        raise RuntimeError(
            f"Template is missing the {PREVIEW_CUT} marker. "
            "Add it immediately after the centerpiece's closing </div>."
        )

    before, after = full_html.split(PREVIEW_CUT, 1)

    # Recover footer + closing tags from `after`.
    page_body_end = "<!-- /page-body -->"
    if page_body_end in after:
        idx = after.index(page_body_end)
        closing_div = after.rfind("</div>", 0, idx)
        footer = after[closing_div:]
    else:
        for anchor in ("<footer", "</body>"):
            if anchor in after:
                footer = "</div>" + after[after.index(anchor):]
                break
        else:
            footer = "</div></body></html>"

    return before + cta_html + "\n" + footer


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def write_meta(out_dir: Path, meta: dict) -> None:
    with open(out_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Archive index rebuild
# ---------------------------------------------------------------------------

def rebuild_archive_index(
    archive_root: Path,
    template_path: Path,
    out_path: Path,
) -> None:
    """
    Scan archive_root for all meta.json files, group by year (newest first),
    render archive_index.html template, write to out_path.
    """
    metas: list[dict] = []
    for meta_file in archive_root.rglob("meta.json"):
        with open(meta_file, "r", encoding="utf-8") as f:
            metas.append(json.load(f))

    metas.sort(key=lambda m: m.get("publish_date_iso", ""), reverse=True)

    if not metas:
        latest_date = "No issues yet"
        groups_html = (
            "<p style=\"color:var(--text-low);font-family:'Share Tech Mono',monospace;\">"
            "No issues published yet.</p>"
        )
    else:
        latest_date = metas[0].get("publish_date", "")

        by_year: dict[str, list[dict]] = {}
        for m in metas:
            yr = str(m.get("year") or m.get("publish_date_iso", "")[:4])
            by_year.setdefault(yr, []).append(m)

        parts: list[str] = []
        for year in sorted(by_year.keys(), reverse=True):
            issues = by_year[year]
            count_label = f"{len(issues)} issue{'s' if len(issues) != 1 else ''}"
            cards: list[str] = []
            for m in issues:
                cards.append(
                    f'      <a class="issue-card" href="{m["preview_url"]}">\n'
                    f'        <div class="issue-date">{m["publish_date"]}</div>\n'
                    f'        <div class="issue-body">\n'
                    f'          <div class="issue-id">{m["issue"]} · Week of {m["week_of"]}</div>\n'
                    f'          <div class="issue-banner">{m["threat_banner"]}</div>\n'
                    f'        </div>\n'
                    f'        <div class="issue-arrow">&rarr;</div>\n'
                    f'      </a>'
                )
            parts.append(
                f'  <div class="year-block">\n'
                f'    <div class="year-header">\n'
                f'      <div class="year-label">{year}</div>\n'
                f'      <div class="year-count">{count_label}</div>\n'
                f'    </div>\n'
                f'    <div class="issue-list">\n'
                + "\n".join(cards) + "\n"
                f'    </div>\n'
                f'  </div>'
            )
        groups_html = "\n".join(parts)

    template = load_template(template_path)
    rendered = (
        template
        .replace("{{ISSUE_GROUPS}}", groups_html)
        .replace("{{LATEST_DATE}}", latest_date)
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"  Archive index: {out_path}  ({len(metas)} issues)")


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def parse_inputs(inputs_dir: Path) -> dict:
    """
    Read inputs/this-week.md and extract frontmatter-style key: value pairs.
    Expects lines like:
      issue: ATB-2026-11
      publish_date: 24 May 2026
      week_of: May 17–23, 2026
      threat_banner: This Week's Dominant Theme
      dominant_theme: ...
    """
    md_path = inputs_dir / "this-week.md"
    if not md_path.exists():
        raise FileNotFoundError(f"Missing input file: {md_path}")

    data: dict = {}
    text = md_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip()
    return data


def render_skeleton(skeleton_path: Path, data: dict) -> str:
    """Render the skeleton template with data substitutions."""
    html = load_template(skeleton_path)
    for key, value in data.items():
        html = html.replace(f"{{{{{key}}}}}", value)
    return html


def main() -> int:
    skeleton_path = TEMPLATE_DIR / "atb_skeleton.html"
    cta_template = "preview_cta_paywall.html" if PAYWALL_ACTIVE else "preview_cta_free.html"
    cta_path = TEMPLATE_DIR / cta_template
    archive_template = TEMPLATE_DIR / "archive_index.html"

    if not skeleton_path.exists():
        print(f"ERROR: skeleton template not found: {skeleton_path}")
        print("Run migrate_archive.py first, or create the skeleton manually.")
        return 1

    try:
        data = parse_inputs(INPUTS_DIR)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    rendered_html = render_skeleton(skeleton_path, data)
    cta_html = load_template(cta_path)

    # Inject preview banner into full brief (before <nav>, after <body>)
    if PREVIEW_BANNER_ENABLED and not PAYWALL_ACTIVE:
        banner_path = TEMPLATE_DIR / "preview_banner.html"
        banner_html = load_template(banner_path) if banner_path.exists() else ""
    else:
        banner_html = ""
    if banner_html:
        rendered_html = rendered_html.replace("<body>", "<body>\n" + banner_html, 1)
        rendered_html = rendered_html.replace("<body ", "<body>", 1)  # handle <body class=...> edge case

    year_str, date_slug = slug_from_publish_date(data["publish_date"])

    issue_dir = ARCHIVE_ROOT / year_str / date_slug
    issue_dir.mkdir(parents=True, exist_ok=True)

    full_path = issue_dir / "full.html"
    full_path.write_text(rendered_html, encoding="utf-8")

    preview_html = build_preview_html(rendered_html, cta_html)
    preview_path = issue_dir / "index.html"
    preview_path.write_text(preview_html, encoding="utf-8")

    try:
        publish_dt = datetime.strptime(data["publish_date"], "%d %B %Y")
    except ValueError:
        publish_dt = datetime.strptime(data["publish_date"], "%Y-%m-%d")

    meta = {
        "issue": data.get("issue", ""),
        "publish_date": data.get("publish_date", ""),
        "publish_date_iso": publish_dt.strftime("%Y-%m-%d"),
        "week_of": data.get("week_of", ""),
        "year": int(year_str),
        "slug": date_slug,
        "dominant_theme": data.get("dominant_theme", ""),
        "threat_banner": data.get("threat_banner", ""),
        "preview_url": f"/atb/{year_str}/{date_slug}/",
        "full_url": f"/atb/{year_str}/{date_slug}/full.html",
    }
    write_meta(issue_dir, meta)

    rebuild_archive_index(
        archive_root=ARCHIVE_ROOT,
        template_path=archive_template,
        out_path=ARCHIVE_ROOT / "index.html",
    )

    print(f"  Full brief:  {full_path}")
    print(f"  Preview:     {preview_path}")
    print(f"  Meta:        {issue_dir / 'meta.json'}")

    webbrowser.open(preview_path.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
