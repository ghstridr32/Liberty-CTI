import os
import re

# ── EDIT THESE EVERY SATURDAY ──────────────────────────────
NEW_ISSUE_FILE   = "04-05-2026.html"          # new ATB filename
NEW_ISSUE_LABEL  = "Week of Apr 5, 2026"       # label shown in dropdown
# ───────────────────────────────────────────────────────────

MAX_DROPDOWN_ITEMS = 4   # cap — oldest issue auto-removed

# All site files to update (script runs from same folder)
SITE_FILES = [
    "index.html",
    "about.html",
    "intelligence.html",
    "texas-focus.html",
    "Energy_data_AI.html",
    "briefing-request.html",
    "contact.html",
    "thank-you.html",
    "threat-brief.html",
    "atb-archive.html",
]

# Build the new dropdown item
NEW_DROPDOWN_ITEM = f'<li><a href="{NEW_ISSUE_FILE}">{NEW_ISSUE_LABEL}</a></li>'

# Pattern: find the full dropdown-menu block inside the ATB nav item
DROPDOWN_PATTERN = re.compile(
    r'(<ul class="dropdown-menu">)(.*?)(</ul>)',
    re.DOTALL
)

# Extract individual <li> items from dropdown inner HTML
LI_PATTERN = re.compile(r'<li>.*?</li>', re.DOTALL)

def update_file(filepath):
    if not os.path.exists(filepath):
        print(f"  SKIP — not found: {filepath}")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    def inject(match):
        opening = match.group(1)
        inner   = match.group(2)
        closing = match.group(3)

        # Don't add duplicate if already present
        if NEW_ISSUE_FILE in inner:
            return match.group(0)

        # Get existing <li> items
        existing_items = LI_PATTERN.findall(inner)

        # Prepend new item, cap to MAX_DROPDOWN_ITEMS
        all_items = [NEW_DROPDOWN_ITEM] + existing_items
        capped_items = all_items[:MAX_DROPDOWN_ITEMS]

        new_inner = "\n        " + "\n        ".join(capped_items) + "\n      "
        return opening + new_inner + closing

    new_html, count = DROPDOWN_PATTERN.subn(inject, html, count=1)

    # Also update the main ATB nav link to point to the latest issue
    new_html = re.sub(
        r'(<a href=")[^"]*("(?:\s+style="color[^"]*")?>Alamo Threat Brief</a>)',
        rf'\g<1>{NEW_ISSUE_FILE}\2',
        new_html
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"  ✓ {filepath}")

print(f"\nAdding {NEW_ISSUE_LABEL} to nav dropdowns (capped to {MAX_DROPDOWN_ITEMS} issues)...\n")
for fname in SITE_FILES:
    update_file(fname)
print(f"\nDone. Open your files to verify.")
