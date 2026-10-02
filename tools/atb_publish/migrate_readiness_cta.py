#!/usr/bin/env python3
"""Replace the retired Executive Crisis Wargame CTAs in published ATB issues.

Every ATB issue now closes on the paid entry engagement: the Executive
Intelligence Baseline + Executive Decision Exercise (decision-readiness.html).
Rewrites, in place, both the mid-brief CTA (before "Actions This Week") and the
closing CTA (before the site footer), preserving each file's relative depth.

    python tools/atb_publish/migrate_readiness_cta.py          # dry run
    python tools/atb_publish/migrate_readiness_cta.py --write  # apply
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PRIMARY_RE = re.compile(
    r'(?:[ \t]*<!-- WARGAME CTA -->\s*)?<div class="wargame-cta"[^>]*>.*?href="((?:\.\./)*)crisis-wargame\.html".*?</a>\s*</div>',
    re.DOTALL,
)
CLOSING_RE = re.compile(
    r'(?:[ \t]*<!-- WARGAME CTA — CLOSING -->\s*)?<div class="wargame-cta-closing"[^>]*>.*?href="((?:\.\./)*)crisis-wargame\.html".*?</a>\s*</div>',
    re.DOTALL,
)
LOOSE_LINK_RE = re.compile(r'href="((?:\.\./)*)crisis-wargame\.html"')

LINK_STYLE_PRIMARY = "font-family:'Share Tech Mono',monospace;font-size:.72rem;letter-spacing:.14em;color:#f0c870;text-decoration:none;border-bottom:1px solid rgba(212,160,64,.4);padding-bottom:2px;"
LINK_STYLE_CLOSING = "font-family:'Share Tech Mono',monospace;font-size:.68rem;letter-spacing:.12em;color:#d4a040;text-decoration:none;"
LINK_TEXT = "EXECUTIVE INTELLIGENCE BASELINE + EXECUTIVE DECISION EXERCISE &rarr;"


def primary_block(prefix: str) -> str:
    return (
        '  <!-- READINESS CTA -->\n'
        '  <div class="readiness-cta" style="margin:40px 0;background:rgba(212,160,64,.05);border:1px solid rgba(212,160,64,.28);border-left:4px solid #d4a040;padding:28px 32px;">\n'
        '    <div style="font-family:\'Share Tech Mono\',monospace;font-size:.62rem;letter-spacing:.22em;text-transform:uppercase;color:#d4a040;margin-bottom:10px;">From Warning to Decision</div>\n'
        '    <h3 style="font-family:\'Rajdhani\',sans-serif;font-size:1.3rem;font-weight:700;color:#ffffff;margin:0 0 10px;letter-spacing:.01em;">Test what this means for your organization.</h3>\n'
        '    <p style="color:#c4d8ee;font-size:.9rem;line-height:1.6;margin:0 0 16px;max-width:640px;">Reading the warning is one thing. Knowing whether your leadership would recognize it, decide in time, and document the call is another. Liberty CTI starts by establishing your decision environment, then tests it under pressure.</p>\n'
        f'    <a href="{prefix}decision-readiness.html" style="{LINK_STYLE_PRIMARY}">{LINK_TEXT}</a>\n'
        '  </div>'
    )


def closing_block(prefix: str) -> str:
    return (
        '  <!-- READINESS CTA — CLOSING -->\n'
        '  <div class="readiness-cta-closing" style="margin:36px 0 8px;padding-top:22px;border-top:1px solid rgba(212,160,64,.15);text-align:center;">\n'
        '    <p style="color:#8aaece;font-size:.85rem;font-style:italic;margin:0 0 8px;">Test what this means for your organization.</p>\n'
        f'    <a href="{prefix}decision-readiness.html" style="{LINK_STYLE_CLOSING}">{LINK_TEXT}</a>\n'
        '  </div>'
    )


def migrate(content: str) -> str:
    content = PRIMARY_RE.sub(lambda m: primary_block(m.group(1)), content)
    content = CLOSING_RE.sub(lambda m: closing_block(m.group(1)), content)
    # Any remaining in-body link to the retired page points at the renamed page.
    content = LOOSE_LINK_RE.sub(lambda m: f'href="{m.group(1)}executive-decision-exercise.html"', content)
    return content


def targets() -> list[Path]:
    files = sorted((ROOT / "atb" / "issues").glob("*.html"))
    files += sorted((ROOT / "atb").glob("[0-9][0-9][0-9][0-9]/*/*.html"))
    return files


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    changed = 0
    for path in targets():
        original = path.read_text(encoding="utf-8")
        updated = migrate(original)
        if updated != original:
            changed += 1
            if args.write:
                path.write_text(updated, encoding="utf-8")
            print(("updated " if args.write else "would update ") + str(path.relative_to(ROOT)))
    print(f"{changed} file(s) {'updated' if args.write else 'to update'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
