#!/usr/bin/env python3
"""
apply_preview_period.py
Updates all existing atb/2026/*/index.html preview files for the preview period:
  1. Replaces the old paywall CTA block with the new free CTA
  2. Injects the preview banner before the first <nav>
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ATB_2026 = ROOT / "atb" / "2026"
TEMPLATE_DIR = ROOT / "Intel Production" / "Draft ATB" / "templates"

FREE_CTA = (TEMPLATE_DIR / "preview_cta_free.html").read_text(encoding="utf-8").strip()
BANNER   = (TEMPLATE_DIR / "preview_banner.html").read_text(encoding="utf-8").strip()

# Match the entire old paywall-cta div (any variant of content inside)
OLD_CTA_RE = re.compile(
    r'<div class="paywall-cta">[\s\S]*?</div>\s*\n?</div>',
    re.MULTILINE,
)


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    # 1. Replace old paywall CTA with free CTA
    if 'class="paywall-cta"' in text:
        text = OLD_CTA_RE.sub(lambda m: FREE_CTA, text, count=1)

    # 2. Inject preview banner before first <nav (if not already present)
    if 'preview-banner' not in text and '<nav' in text:
        text = text.replace('<nav', BANNER + '\n<nav', 1)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    preview_files = sorted(ATB_2026.glob("*/index.html"))
    fixed = 0
    for f in preview_files:
        slug = f.parent.name
        changed = fix_file(f)
        if changed:
            print(f"  FIXED  {slug}/index.html")
            fixed += 1
        else:
            print(f"  skip   {slug}/index.html")
    print(f"\nDone — {fixed}/{len(preview_files)} files updated.")


if __name__ == "__main__":
    main()
