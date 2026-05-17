#!/usr/bin/env python3
"""
migrate_archive.py — Phase 1 ATB Paywall migration

Reads every dated flat HTML file from atb/issues/ and creates:
  atb/2026/<MM-DD-YYYY>/full.html    — path-corrected copy of the full brief
  atb/2026/<MM-DD-YYYY>/index.html   — preview truncated at PREVIEW_CUT with CTA
  atb/2026/<MM-DD-YYYY>/meta.json    — issue metadata
  atb/index.html                      — rebuilt archive listing

Run from the repo root or from this script's location:
  python "Intel Production/Draft ATB/scripts/migrate_archive.py"
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
WORKFLOW_DIR = HERE.parent                         # Intel Production/Draft ATB/
ROOT = WORKFLOW_DIR.parent.parent                  # repo root
ARCHIVE_ROOT = ROOT / "atb"
ISSUES_DIR = ROOT / "atb" / "issues"
TEMPLATE_DIR = WORKFLOW_DIR / "templates"

PREVIEW_CUT = "<!--PREVIEW_CUT-->"
DATED_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-(\d{4})\.html$", re.IGNORECASE)

# Metadata from update_atb_archive.py ISSUE_OVERRIDES (source of truth)
ISSUE_META: dict[str, dict] = {
    "03-16-2026.html": {
        "title": "Texas Critical Infrastructure Threat Baseline",
        "week_of": "16 March 2026",
    },
    "03-22-2026.html": {
        "title": "Operation Epic Fury: Cyber Implications for Texas",
        "week_of": "22 March 2026",
    },
    "03-29-2026.html": {
        "title": "Iran-Linked Handala Activity and U.S. Healthcare Exposure",
        "week_of": "29 March 2026",
    },
    "04-03-2026.html": {
        "title": "Supply-Chain Disruption and Persistent Access Risk",
        "week_of": "3 April 2026",
    },
    "04-12-2026.html": {
        "title": "Active Exploitation, North Korea Crypto Theft, and Infrastructure Risk",
        "week_of": "12 April 2026",
    },
    "04-19-2026.html": {
        "title": "Sector Risk: Iran, North Korea, Cybercrime, and AI",
        "week_of": "19 April 2026",
    },
    "04-26-2026.html": {
        "title": "Texas Cyber Risk: Multi-Actor Pressure Continues",
        "week_of": "26 April 2026",
    },
    "05-03-2026.html": {
        "title": "Texas Cyber Risk: Developer Pipelines, Energy Logistics, and OT Exposure",
        "week_of": "3 May 2026",
    },
    "05-10-2026.html": {
        "title": "The Federal Posture Just Changed",
        "week_of": "May 3–10, 2026",
    },
    "05-17-2026.html": {
        "title": "Texas Infrastructure Concentration Is the Target",
        "week_of": "May 10–16, 2026",
    },
}


def fix_relative_paths(html: str) -> str:
    """
    Files moving from atb/issues/<file>.html  (depth 2)
                   to atb/2026/<slug>/full.html (depth 3)
    need one more ../ to reach repo root.
    Replace href="../../ and src="../../ patterns only.
    """
    html = re.sub(r'(href=")(\.\./\.\./)', r'\1../../../', html)
    html = re.sub(r'(src=")(\.\./\.\./)', r'\1../../../', html)
    return html


def _find_closing_div(html: str, after: int) -> int:
    """Return the index just past the </div> that closes the div opened at `after`."""
    depth = 1
    pos = after
    while pos < len(html) and depth > 0:
        open_m = html.find("<div", pos)
        close_m = html.find("</div>", pos)
        if close_m == -1:
            break
        if open_m != -1 and open_m < close_m:
            depth += 1
            pos = open_m + 4
        else:
            depth -= 1
            pos = close_m + 6
    return pos  # points just past the matching </div>


def insert_preview_cut(html: str) -> str:
    """
    Insert <!--PREVIEW_CUT--> using the best available anchor, in priority order:
      1. Before <!-- SECTION I: WHAT CHANGED --> comment  (05-17 format)
      2. After <div class="centerpiece">...</div> closing tag  (05-10 format)
      3. Before first <h2 class="section-head">  (older section-head format)
      4. Before first <h2 class="headline">  (oldest news-story format)
    """
    # 1. Section I comment
    marker = "<!-- SECTION I: WHAT CHANGED -->"
    if marker in html:
        return html.replace(marker, PREVIEW_CUT + "\n  " + marker, 1)

    # 2. After <div class="centerpiece"> closing div (HTML tag only, not CSS)
    cp_match = re.search(r'<div class="centerpiece">', html)
    if cp_match:
        close_end = _find_closing_div(html, cp_match.end())
        if close_end > cp_match.end():
            return html[:close_end] + "\n  " + PREVIEW_CUT + "\n  " + html[close_end:]

    # 3. Before first <h2 class="section-head">
    m = re.search(r'<h2 class="section-head">', html)
    if m:
        return html[: m.start()] + PREVIEW_CUT + "\n  " + html[m.start():]

    # 4. Before first <h2 class="headline"> (oldest format)
    m = re.search(r'<h2 class="headline">', html)
    if m:
        return html[: m.start()] + PREVIEW_CUT + "\n  " + html[m.start():]

    # 5. Before first <div class="section-head"> in HTML body (div-based format)
    for m in re.finditer(r'<div class="section-head">', html):
        # Skip if inside a <style> block
        preceding = html[: m.start()]
        if preceding.count("<style") > preceding.count("</style"):
            continue
        return html[: m.start()] + PREVIEW_CUT + "\n  " + html[m.start():]

    print("  WARNING: Could not find insertion point — PREVIEW_CUT not inserted")
    return html


def build_preview_html(full_html: str, cta_html: str) -> str:
    """Split at PREVIEW_CUT, insert CTA, keep footer."""
    if PREVIEW_CUT not in full_html:
        # No cut marker — return the full brief as preview (safe fallback)
        return full_html

    before, after = full_html.split(PREVIEW_CUT, 1)

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


def extract_week_of_from_html(html: str) -> str:
    """Extract 'Week of: ...' from the issue pill block."""
    m = re.search(
        r'<strong>Week of:</strong>\s*(.*?)</div>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        raw = re.sub(r"<[^>]+>", "", m.group(1))
        raw = raw.replace("&ndash;", "–").replace("&mdash;", "—")
        return raw.strip()
    return ""


def extract_issue_number_from_html(html: str) -> str:
    """Extract 'ATB-2026-N' from the issue pill block."""
    m = re.search(r"(ATB-\d{4}-\d+)", html)
    return m.group(1) if m else ""


def rebuild_archive_index(metas: list[dict], template_path: Path, out_path: Path) -> None:
    metas_sorted = sorted(metas, key=lambda m: m.get("publish_date_iso", ""), reverse=True)

    if not metas_sorted:
        latest_date = "No issues yet"
        groups_html = "<p>No issues published yet.</p>"
    else:
        latest_date = metas_sorted[0].get("publish_date", "")
        by_year: dict[str, list[dict]] = {}
        for m in metas_sorted:
            yr = str(m.get("year") or m.get("publish_date_iso", "")[:4])
            by_year.setdefault(yr, []).append(m)

        parts: list[str] = []
        for year in sorted(by_year.keys(), reverse=True):
            issues = by_year[year]
            count_label = f"{len(issues)} issue{'s' if len(issues) != 1 else ''}"
            cards = [
                f'      <a class="issue-card" href="{m["preview_url"]}">\n'
                f'        <div class="issue-date">{m["publish_date"]}</div>\n'
                f'        <div class="issue-body">\n'
                f'          <div class="issue-id">{m["issue"]} · Week of {m["week_of"]}</div>\n'
                f'          <div class="issue-banner">{m["threat_banner"]}</div>\n'
                f'        </div>\n'
                f'        <div class="issue-arrow">&rarr;</div>\n'
                f'      </a>'
                for m in issues
            ]
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

    template = template_path.read_text(encoding="utf-8")
    rendered = (
        template
        .replace("{{ISSUE_GROUPS}}", groups_html)
        .replace("{{LATEST_DATE}}", latest_date)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"\nArchive index written: {out_path}  ({len(metas_sorted)} issues)")


def migrate_file(
    src: Path,
    issue_number: int,
    cta_html: str,
) -> dict | None:
    """Migrate one flat issue file to the new directory structure."""
    filename = src.name
    stem = src.stem  # MM-DD-YYYY

    try:
        dt = datetime.strptime(stem, "%m-%d-%Y")
    except ValueError:
        print(f"  SKIP {filename} — cannot parse date from name")
        return None

    year_str = str(dt.year)
    slug = stem                              # already MM-DD-YYYY
    issue_dir = ARCHIVE_ROOT / year_str / slug
    issue_dir.mkdir(parents=True, exist_ok=True)

    raw_html = src.read_text(encoding="utf-8", errors="replace")

    # Fix relative paths for new depth
    fixed_html = fix_relative_paths(raw_html)

    # Insert PREVIEW_CUT
    full_html = insert_preview_cut(fixed_html)

    # Write full.html
    full_path = issue_dir / "full.html"
    full_path.write_text(full_html, encoding="utf-8")

    # Write index.html (preview)
    preview_html = build_preview_html(full_html, cta_html)
    preview_path = issue_dir / "index.html"
    preview_path.write_text(preview_html, encoding="utf-8")

    # Build meta
    known = ISSUE_META.get(filename, {})
    threat_banner = known.get("title") or extract_issue_number_from_html(raw_html) or filename
    week_of = known.get("week_of") or extract_week_of_from_html(raw_html) or stem
    issue_id = extract_issue_number_from_html(raw_html) or f"ATB-2026-{issue_number}"
    publish_date = dt.strftime("%d %B %Y")

    meta = {
        "issue": issue_id,
        "publish_date": publish_date,
        "publish_date_iso": dt.strftime("%Y-%m-%d"),
        "week_of": week_of,
        "year": dt.year,
        "slug": slug,
        "dominant_theme": "",
        "threat_banner": threat_banner,
        "preview_url": f"/atb/{year_str}/{slug}/",
        "full_url": f"/atb/{year_str}/{slug}/full.html",
    }
    (issue_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    cut_inserted = PREVIEW_CUT in full_html
    print(
        f"  {filename}  →  atb/{year_str}/{slug}/  "
        f"[{issue_id}]  cut={'yes' if cut_inserted else 'NO'}  "
        f"preview={len(preview_html):,}B  full={len(full_html):,}B"
    )
    return meta


def main() -> int:
    cta_path = TEMPLATE_DIR / "preview_cta.html"
    archive_template = TEMPLATE_DIR / "archive_index.html"

    if not cta_path.exists():
        print(f"ERROR: CTA template not found: {cta_path}")
        return 1
    if not archive_template.exists():
        print(f"ERROR: Archive template not found: {archive_template}")
        return 1
    if not ISSUES_DIR.exists():
        print(f"ERROR: Issues directory not found: {ISSUES_DIR}")
        return 1

    cta_html = cta_path.read_text(encoding="utf-8")

    # Collect and sort dated files
    dated_files = sorted(
        [f for f in ISSUES_DIR.glob("*.html") if DATED_RE.match(f.name)],
        key=lambda p: datetime.strptime(p.stem, "%m-%d-%Y"),
    )

    if not dated_files:
        print(f"No dated ATB HTML files found in {ISSUES_DIR}")
        return 1

    print(f"Migrating {len(dated_files)} issue(s) from {ISSUES_DIR}\n")

    metas: list[dict] = []
    for number, src in enumerate(dated_files, start=1):
        meta = migrate_file(src, number, cta_html)
        if meta:
            metas.append(meta)

    rebuild_archive_index(metas, archive_template, ARCHIVE_ROOT / "index.html")

    print(f"\nDone. {len(metas)} issues migrated.")
    print(f"New structure: {ARCHIVE_ROOT / '2026'}")
    print(f"Archive index: {ARCHIVE_ROOT / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
