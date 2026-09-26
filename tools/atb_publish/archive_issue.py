"""
archive_issue.py -- Build (or verify up-to-date) the DOCX + PDF companion
files for one ATB issue and place them, together with a copy of the
authoritative source HTML, into the archive folder structure:

  ATB Archive/<year>/ATB-<year>-<NN>/
    ATB-<year>-<n>_<YYYY-MM-DD>_<Short_Title>.docx
    ATB-<year>-<n>_<YYYY-MM-DD>_<Short_Title>.pdf
    <YYYY-MM-DD>_source.html
    meta.json                (bookkeeping: source hash, build timestamp, QA result)

Idempotent: if meta.json already records the same source hash, the issue is
skipped (regeneration only happens when the source HTML changed, or --force
is passed). Never creates "(1)", "final2", etc. -- one issue always maps to
exactly one archive folder and one set of filenames.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_docx import build_docx_from_issue  # noqa: E402
from build_pdf import build_pdf_from_issue  # noqa: E402
from parse_atb import parse_issue  # noqa: E402
from qa_integrity import check_issue_companions  # noqa: E402
from validate_atb import validate_issue  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_ROOT = REPO_ROOT / "ATB Archive"


def slugify_title(meta: dict, max_words: int = 8) -> str:
    text = meta.get("dominant_theme") or meta.get("threat_label") or meta.get("brand_line") or "Issue"
    text = re.sub(r"[^A-Za-z0-9\s-]", " ", text)
    words = [w for w in text.split() if w]
    words = words[:max_words]
    slug = "_".join(w.capitalize() if not w.isupper() else w for w in words)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:80] or "Issue"


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def folder_for(year: int, issue_num_int: int) -> Path:
    return ARCHIVE_ROOT / str(year) / f"ATB-{year}-{issue_num_int:02d}"


def archive_issue(source_path: str | Path, issue_number: str, force: bool = False, verbose: bool = True) -> dict:
    source_path = Path(source_path)
    m = re.match(r"ATB-(\d{4})-(\d+)", issue_number)
    if not m:
        raise ValueError(f"Bad issue number: {issue_number}")
    year, num = int(m.group(1)), int(m.group(2))

    issue = parse_issue(source_path)
    meta = issue["metadata"]

    validation = validate_issue(issue, expected_issue_number=issue_number)
    if not validation["ok"]:
        return {"status": "VALIDATION_FAILED", "issue_number": issue_number, "errors": validation["errors"]}

    out_dir = folder_for(year, num)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.json"
    src_hash = source_hash(source_path)

    if not force and meta_path.exists():
        try:
            prior = json.loads(meta_path.read_text(encoding="utf-8"))
            if prior.get("source_hash") == src_hash and prior.get("qa_passed"):
                if verbose:
                    print(f"{issue_number}: unchanged (hash match) -- skipping rebuild")
                return {"status": "SKIPPED_UNCHANGED", "issue_number": issue_number, "folder": str(out_dir)}
        except (json.JSONDecodeError, OSError):
            pass

    issue_date = meta.get("issue_date") or "unknown-date"
    short_title = slugify_title(meta)
    base_name = f"ATB-{year}-{num}_{issue_date}_{short_title}"

    docx_path = out_dir / f"{base_name}.docx"
    pdf_path = out_dir / f"{base_name}.pdf"
    html_path = out_dir / f"{issue_date}_source.html"

    build_docx_from_issue(issue, docx_path)
    build_pdf_from_issue(issue, pdf_path)
    shutil.copy2(source_path, html_path)

    # remove stale files from a prior title-slug if the theme text changed
    for existing in out_dir.glob(f"ATB-{year}-{num}_*"):
        if existing.name not in (docx_path.name, pdf_path.name):
            existing.unlink()

    qa = check_issue_companions(issue, docx_path, pdf_path)

    result_meta = {
        "issue_number": issue_number,
        "issue_date": issue_date,
        "source_filename": source_path.name,
        "source_hash": src_hash,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "docx_file": docx_path.name,
        "pdf_file": pdf_path.name,
        "html_file": html_path.name,
        "qa_passed": qa["ok"],
        "qa_errors": qa["errors"],
        "qa_warnings": qa["warnings"],
        "validation_warnings": validation["warnings"],
        "title_raw": meta.get("title_raw"),
        "dominant_theme": meta.get("dominant_theme"),
        "coverage_period": meta.get("coverage_period"),
    }
    meta_path.write_text(json.dumps(result_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    status = "OK" if qa["ok"] else "COMPANION_BUILD_FAILED"
    if verbose:
        print(f"{issue_number}: {status}  ->  {out_dir}")
        for e in qa["errors"]:
            print(f"    ERROR: {e}")
        for w in qa["warnings"]:
            print(f"    WARNING: {w}")

    return {"status": status, "issue_number": issue_number, "folder": str(out_dir), "qa": qa}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source_html")
    ap.add_argument("issue_number")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    result = archive_issue(args.source_html, args.issue_number, force=args.force)
    print(json.dumps({k: v for k, v in result.items() if k != "qa"}, indent=2, ensure_ascii=False))
    sys.exit(0 if result["status"] in ("OK", "SKIPPED_UNCHANGED") else 1)


if __name__ == "__main__":
    main()
