"""
inventory_atb.py -- Discover all canonical ATB issue source files and assign
sequential issue numbers by publication date (oldest = ATB-<year>-1), matching
the numbering logic update_atb_archive.py uses for the live site.

Only atb/issues/MM-DD-YYYY.html files are treated as canonical, per CLAUDE.md.
Any other file in atb/issues/ (backups, stray non-date-named files) is reported
as an exception rather than silently included or excluded.

Usage:
    python inventory_atb.py            # print inventory as JSON
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ISSUES_DIR = REPO_ROOT / "atb" / "issues"

DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})\.html$")


def discover() -> dict:
    canonical = []
    exceptions = []

    for p in sorted(ISSUES_DIR.iterdir()):
        if not p.is_file():
            continue
        m = DATE_RE.match(p.name)
        if m:
            mm, dd, yyyy = m.groups()
            canonical.append({
                "path": str(p),
                "filename": p.name,
                "date": f"{yyyy}-{mm}-{dd}",
                "year": int(yyyy),
            })
        elif p.suffix == ".html":
            exceptions.append({"path": str(p), "reason": "non-date-named .html in atb/issues/ -- not treated as canonical source"})
        elif p.suffix == ".bak":
            pass  # expected local backups, not an exception worth reporting
        else:
            exceptions.append({"path": str(p), "reason": "unexpected file type in atb/issues/"})

    canonical.sort(key=lambda d: d["date"])

    by_year: dict[int, list] = {}
    for item in canonical:
        by_year.setdefault(item["year"], []).append(item)

    issues = []
    for year, items in sorted(by_year.items()):
        for i, item in enumerate(items, start=1):
            issues.append({
                **item,
                "issue_number": f"ATB-{year}-{i}",
                "issue_num_int": i,
            })

    return {"issues": issues, "exceptions": exceptions, "count": len(issues)}


def main():
    result = discover()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
