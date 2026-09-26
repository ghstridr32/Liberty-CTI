"""
publish_atb.py -- One-command ATB companion-document publication.

    python tools/atb_publish/publish_atb.py ATB-2026-28
    python tools/atb_publish/publish_atb.py atb/issues/09-13-2026.html

Pipeline:
    resolve issue -> validate -> build DOCX -> build PDF -> integrity QA
    -> archive (copy HTML + DOCX + PDF into ATB Archive/<year>/ATB-<year>-NN/)
    -> rebuild that year's master index -> sync that year's archive to
    Google Drive (best-effort; failure is reported, never silent)

FAIL CLOSED: if validation or integrity QA fails, this prints
"ATB COMPANION BUILD FAILED" and exits non-zero. It does not partially
publish and claim success. Web publication of the HTML itself is a separate,
pre-existing step (sync_components.py / build_publish.ps1 / wrangler deploy)
and is not touched or blocked by this script -- see CLAUDE.md for that flow.
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

REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_source(arg: str) -> tuple[Path, str]:
    """Accept either an ATB-YYYY-N issue id or a path to the source HTML."""
    p = Path(arg)
    if p.exists() and p.suffix == ".html":
        inv = discover()
        match = next((i for i in inv["issues"] if Path(i["path"]).resolve() == p.resolve()), None)
        if not match:
            raise SystemExit(
                f"SOURCE NOT FOUND -- {p} is not a date-named file under atb/issues/ "
                f"(cannot determine its issue number)."
            )
        return p, match["issue_number"]

    inv = discover()
    match = next((i for i in inv["issues"] if i["issue_number"].upper() == arg.upper()), None)
    if not match:
        raise SystemExit(f"SOURCE NOT FOUND -- no issue matching '{arg}' in atb/issues/.")
    return Path(match["path"]), match["issue_number"]


def publish(arg: str, force: bool = False, sync_drive: bool = True) -> int:
    source_path, issue_number = resolve_source(arg)
    print(f"Publishing companion files for {issue_number} ({source_path.name})...")

    result = archive_issue(source_path, issue_number, force=force)

    if result["status"] == "VALIDATION_FAILED":
        print("ATB COMPANION BUILD FAILED -- validation failed")
        for e in result["errors"]:
            print(f"  ERROR: {e}")
        return 1

    if result["status"] == "COMPANION_BUILD_FAILED":
        print("ATB COMPANION BUILD FAILED -- integrity QA failed")
        for e in result["qa"]["errors"]:
            print(f"  ERROR: {e}")
        return 1

    year = int(issue_number.split("-")[1])
    idx = build_master_index(year)
    print(f"Master index rebuilt: {idx['docx']}")

    if sync_drive:
        drive_result = sync_year(year)
        print(f"Google Drive sync: {drive_result['status']}")
        if drive_result["status"] != "OK":
            print("  (companion archive is complete locally; Drive sync did not succeed -- see message above)")

    print(f"COMPLETE -- {issue_number} published: HTML + DOCX + PDF, archived at {result['folder']}")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    force = "--force" in sys.argv
    no_drive = "--no-drive" in sys.argv
    arg = [a for a in sys.argv[1:] if not a.startswith("--")][0]
    sys.exit(publish(arg, force=force, sync_drive=not no_drive))


if __name__ == "__main__":
    main()
