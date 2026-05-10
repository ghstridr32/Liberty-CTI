#!/usr/bin/env python3
"""
update_atb_dropdown.py
======================

Updates the Alamo Threat Brief dropdown entries inside the nav sync script.

Designed for use with:
    sync_components_atb_dropdown.py

This version assumes your ATB issue files use the naming convention:
    MM-DD-YYYY.html

Examples:
    03-16-2026.html
    03-23-2026.html
    03-30-2026.html

What it updates:
- Desktop ATB dropdown
- Mobile ATB dropdown
- Active-link aliases for ATB pages

USAGE
-----
1) Edit ATB_FILES below (newest first).
2) Put this file in the same folder as sync_components_atb_dropdown.py
3) Run:

    python update_atb_dropdown.py

Optional:
    python update_atb_dropdown.py --target sync_components_atb_dropdown.py
    python update_atb_dropdown.py --dry-run
"""

from __future__ import annotations
import argparse
import re
from datetime import datetime
from pathlib import Path


# ── EDIT THESE EACH WEEK ─────────────────────────────────────
# Keep newest first. First entry becomes "Latest Issue".
ATB_FILES = [
    "04-05-2026.html",
    "03-29-2026.html",
    "03-22-2026.html",
]
# ─────────────────────────────────────────────────────────────


DEFAULT_TARGET = "sync_components_atb_dropdown.py"


def format_label(filename: str) -> str:
    stem = filename.replace(".html", "")
    try:
        dt = datetime.strptime(stem, "%m-%d-%Y")
        return dt.strftime("Week of %b %d, %Y").replace(" 0", " ")
    except ValueError:
        return stem


def build_desktop_block(files: list[str]) -> str:
    latest = files[0]
    lines = [
        f'        <a href="{latest}" role="menuitem" class="lcti-atb-link">Latest Issue — {format_label(latest)}</a>'
    ]
    if len(files) > 1:
        lines.append(
            f'        <a href="{files[1]}" role="menuitem" class="lcti-atb-link">Issue 2 — {format_label(files[1])}</a>'
        )
    if len(files) > 2:
        lines.append(
            f'        <a href="{files[2]}" role="menuitem" class="lcti-atb-link">Issue 3 — {format_label(files[2])}</a>'
        )
    lines.extend([
        '        <div class="drop-divider"></div>',
        '        <a href="atb-archive.html" role="menuitem" class="lcti-atb-link">Archive</a>',
    ])
    return "\n".join(lines)


def build_mobile_block(files: list[str]) -> str:
    latest = files[0]
    lines = [
        f'    <a href="{latest}" class="lcti-atb-link">Latest Issue — {format_label(latest)}</a>'
    ]
    if len(files) > 1:
        lines.append(
            f'    <a href="{files[1]}" class="lcti-atb-link">Issue 2 — {format_label(files[1])}</a>'
        )
    if len(files) > 2:
        lines.append(
            f'    <a href="{files[2]}" class="lcti-atb-link">Issue 3 — {format_label(files[2])}</a>'
        )
    lines.append('    <a href="atb-archive.html" class="lcti-atb-link">Archive</a>')
    return "\n".join(lines)


def build_alias_list(files: list[str]) -> str:
    all_files = files + ["atb-archive.html"]
    return ", ".join([f"'{f}'" for f in all_files])


def update_target(text: str, files: list[str]) -> str:
    if not files:
        raise ValueError("ATB_FILES cannot be empty.")

    desktop_replacement = build_desktop_block(files)
    mobile_replacement = build_mobile_block(files)
    aliases_replacement = build_alias_list(files)

    # Desktop dropdown block
    text, n1 = re.subn(
        r'(?ms)(<a href="alamo-threat-brief\.html" role="menuitem" class="lcti-atb-link">ATB Overview</a>\n\s*<div class="drop-divider"></div>\n\s*<span class="drop-label">Latest Issues</span>\n)(.*?)(\n\s*<div class="drop-divider"></div>\n\s*<a href="atb-archive\.html" role="menuitem" class="lcti-atb-link">Archive</a>)',
        lambda m: m.group(1) + desktop_replacement,
        text,
    )

    # Mobile dropdown block
    text, n2 = re.subn(
        r'(?ms)(<span class="m-group-label lcti-atb-link">Alamo Threat Brief</span>\n\s*<div class="m-sub">\n\s*<a href="alamo-threat-brief\.html" class="lcti-atb-link">ATB Overview</a>\n)(.*?)(\n\s*</div>)',
        lambda m: m.group(1) + mobile_replacement + m.group(3),
        text,
    )

    # Alias block
    text, n3 = re.subn(
        r"(?ms)('alamo-threat-brief\.html':\s*\[)(.*?)(\])",
        lambda m: m.group(1) + aliases_replacement + m.group(3),
        text,
    )

    if n1 == 0:
        raise RuntimeError("Could not find desktop ATB dropdown block in target script.")
    if n2 == 0:
        raise RuntimeError("Could not find mobile ATB dropdown block in target script.")
    if n3 == 0:
        raise RuntimeError("Could not find ATB alias block in target script.")

    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Update ATB dropdown entries in the nav sync script.")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="Target sync script to update.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; do not write changes.")
    args = parser.parse_args()

    target = Path(args.target)

    if not target.exists():
        print(f"ERROR: Target file not found: {target}")
        return 1

    original = target.read_text(encoding="utf-8")
    updated = update_target(original, ATB_FILES)

    if original == updated:
        print("No changes needed. Target already matches ATB_FILES.")
        return 0

    if args.dry_run:
        print(f"Dry run OK. {target.name} would be updated.")
        print("ATB files to use:")
        for i, fname in enumerate(ATB_FILES, start=1):
            slot = "Latest Issue" if i == 1 else f"Issue {i}"
            print(f"  - {slot}: {fname} ({format_label(fname)})")
        return 0

    target.write_text(updated, encoding="utf-8")
    print(f"Updated {target}")
    print("New ATB issues:")
    for i, fname in enumerate(ATB_FILES, start=1):
        slot = "Latest Issue" if i == 1 else f"Issue {i}"
        print(f"  - {slot}: {fname} ({format_label(fname)})")
    print("Archive remains: atb-archive.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
