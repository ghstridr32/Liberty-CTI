"""
validate_atb.py -- Validate a parsed ATB issue dict (from parse_atb.py) before
companion-document generation: metadata completeness and internal consistency.

This is a pre-flight check, not a content-integrity check (see qa_integrity.py
for post-build comparison against the generated DOCX/PDF).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_atb import parse_issue  # noqa: E402


def validate_issue(issue: dict, expected_issue_number: str | None = None) -> dict:
    meta = issue["metadata"]
    errors = []
    warnings = []

    if not meta.get("issue_number"):
        errors.append("No issue number (ATB-YYYY-N) found in source HTML.")
    elif expected_issue_number and meta["issue_number"] != expected_issue_number:
        warnings.append(
            f"In-page issue number '{meta['issue_number']}' does not match "
            f"date-sequence-derived number '{expected_issue_number}'."
        )

    if not meta.get("issue_date"):
        errors.append("Could not derive publication date from filename (expected MM-DD-YYYY.html).")

    if not meta.get("coverage_period"):
        warnings.append("No coverage period found (neither meta-cell 'Coverage' nor 'Week of' pill).")

    if not meta.get("title_raw") and not meta.get("brand_line"):
        warnings.append("No <title> or <h1> found for the issue.")

    # Standing brand rule (see CLAUDE.md): "The Alamo Threat Brief" carries the
    # trademark symbol in the <title> and masthead heading of every issue.
    for label, text in (("<title>", meta.get("title_raw")), ("masthead <h1>", meta.get("brand_line"))):
        if text and re.search(r"Alamo\s+Threat\s+Brief(?!\s*™)", text):
            warnings.append(f'{label} has "Alamo Threat Brief" without the ™ symbol.')

    if not issue["blocks"]:
        errors.append("No content blocks extracted -- source HTML may be empty or unparseable.")

    if issue.get("_source_text_len", 0) < 500:
        errors.append(f"Extracted source text unusually short ({issue.get('_source_text_len')} chars) -- possible parse failure.")

    block_types = {b["type"] for b in issue["blocks"]}
    if "source_list" not in block_types and "intel_card" not in block_types:
        warnings.append("No sources section detected (no source_list or intel_card blocks).")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "issue_number": meta.get("issue_number") or expected_issue_number,
    }


def main():
    if len(sys.argv) < 2:
        print("usage: validate_atb.py <issue.html> [expected_issue_number]", file=sys.stderr)
        sys.exit(1)
    issue = parse_issue(sys.argv[1])
    expected = sys.argv[2] if len(sys.argv) > 2 else None
    result = validate_issue(issue, expected)
    for e in result["errors"]:
        print(f"ERROR: {e}")
    for w in result["warnings"]:
        print(f"WARNING: {w}")
    print("VALIDATION " + ("PASSED" if result["ok"] else "FAILED"))
    sys.exit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()
