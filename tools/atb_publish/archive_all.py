"""
archive_all.py -- Historical backfill: build DOCX + PDF companion files for
every existing ATB issue found in atb/issues/, archive them, and rebuild the
master index for every year touched.

Usage:
    python tools/atb_publish/archive_all.py [--force] [--no-drive]

Idempotent: safe to re-run. Issues whose source hash hasn't changed since
the last run are skipped (unless --force).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from archive_issue import archive_issue  # noqa: E402
from build_master_index import build_master_index  # noqa: E402
from inventory_atb import discover  # noqa: E402
from sync_google_drive import sync_year  # noqa: E402


def main():
    force = "--force" in sys.argv
    sync_drive = "--no-drive" not in sys.argv

    inv = discover()
    print(f"Discovered {inv['count']} canonical ATB issue(s).")
    for exc in inv["exceptions"]:
        print(f"EXCEPTION: {exc['path']} -- {exc['reason']}")

    results = []
    years_touched = set()
    for item in inv["issues"]:
        r = archive_issue(item["path"], item["issue_number"], force=force)
        results.append(r)
        years_touched.add(int(item["issue_number"].split("-")[1]))

    ok = [r for r in results if r["status"] in ("OK", "SKIPPED_UNCHANGED")]
    built = [r for r in results if r["status"] == "OK"]
    skipped = [r for r in results if r["status"] == "SKIPPED_UNCHANGED"]
    failed = [r for r in results if r["status"] not in ("OK", "SKIPPED_UNCHANGED")]

    for year in sorted(years_touched):
        idx = build_master_index(year)
        print(f"Master index rebuilt for {year}: {idx['issue_count']} issues indexed.")

    drive_results = {}
    if sync_drive:
        for year in sorted(years_touched):
            dr = sync_year(year)
            drive_results[year] = dr["status"]
            print(f"Google Drive sync {year}: {dr['status']}")

    print()
    print("=== HISTORICAL ARCHIVE SUMMARY ===")
    print(f"Issues discovered: {inv['count']}")
    print(f"Issues archived (built or already current): {len(ok)}  (newly built: {len(built)}, unchanged/skipped: {len(skipped)})")
    print(f"DOCX count: {len(ok)}   PDF count: {len(ok)}   HTML count: {len(ok)}")
    print(f"Exceptions: {len(inv['exceptions'])}")
    if failed:
        print(f"FAILED issues: {len(failed)}")
        for r in failed:
            print(f"  {r['issue_number']}: {r['status']}")
    if sync_drive:
        print(f"Drive sync results: {drive_results}")

    sys.exit(0 if not failed else 2)


if __name__ == "__main__":
    main()
