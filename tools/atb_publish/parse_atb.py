"""
parse_atb.py -- Parse an Alamo Threat Brief source HTML file into a canonical,
template-agnostic intermediate representation (a Python dict, JSON-serializable).

Design goal: the ATB template has evolved significantly across issues (ATB-2026-1
uses simple headline cards; later issues use a Section I-IX judgment/governance
structure). Rather than hard-coding one schema, this parser walks the DOM
generically and preserves every piece of visible analytical content as an
ordered list of typed "blocks". Known component classes (key judgments, sources,
governance rows, implications table, etc.) are recognized and rendered as
structured blocks for nicer typesetting; anything unrecognized still falls
through to generic heading/paragraph/list blocks so nothing is silently dropped.

Usage:
    python parse_atb.py path/to/issue.html            # print JSON to stdout
    python parse_atb.py path/to/issue.html out.json    # write JSON to file
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

SKIP_CLASS_SUBSTR = (
    "masthead", "cls-banner", "ticker-strip", "wargame-cta", "nav-links",
)


def _clean_text(s: str) -> str:
    s = s.replace(" ", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    return s.strip()


def extract_runs(el: Tag) -> list[dict]:
    """Walk inline children of el, producing a list of {text,bold,italic,link} runs."""
    runs: list[dict] = []

    def walk(node, bold=False, italic=False, mono=False):
        if isinstance(node, NavigableString):
            if isinstance(node, Comment):
                return
            text = str(node)
            if text:
                runs.append({"text": text, "bold": bold, "italic": italic, "mono": mono, "link": None})
            return
        if not isinstance(node, Tag):
            return
        name = node.name
        cls = " ".join(node.get("class", []))
        b = bold or name in ("strong", "b") or "aq" in cls.split()
        i = italic or name in ("em", "i") or "kj-uncertainty" in cls
        m = mono or "conf" in cls.split()
        if name == "a":
            href = node.get("href", "")
            text = node.get_text()
            if text:
                runs.append({"text": text, "bold": b, "italic": i, "mono": m, "link": href})
            return
        if name == "br":
            runs.append({"text": "\n", "bold": False, "italic": False, "mono": False, "link": None})
            return
        for child in node.children:
            walk(child, b, i, m)

    for child in el.children:
        walk(child)

    # collapse whitespace but keep explicit \n breaks
    cleaned = []
    for r in runs:
        t = r["text"].replace(" ", " ")
        t = re.sub(r"[ \t]+", " ", t)
        if t == "":
            continue
        cleaned.append({**r, "text": t})
    return cleaned


def runs_to_plain(runs: list[dict]) -> str:
    return _clean_text("".join(r["text"] for r in runs))


def has_class(el: Tag, name: str) -> bool:
    return el.has_attr("class") and name in el.get("class", [])


def class_str(el: Tag) -> str:
    return " ".join(el.get("class", [])) if el.has_attr("class") else ""


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def parse_filename_date(path: Path) -> str | None:
    m = re.match(r"(\d{2})-(\d{2})-(\d{4})", path.stem)
    if m:
        mm, dd, yyyy = m.groups()
        return f"{yyyy}-{mm}-{dd}"
    return None


def extract_metadata(soup: BeautifulSoup, path: Path) -> dict:
    meta = {
        "issue_number": None,
        "issue_num_int": None,
        "year": None,
        "title_raw": None,
        "brand_line": None,
        "week_of": None,
        "coverage_period": None,
        "coverage_tags": None,
        "next_issue": None,
        "threat_label": None,
        "dominant_theme": None,
        "sector_focus": None,
        "issue_date": parse_filename_date(path),
        "source_filename": path.name,
    }

    title_tag = soup.find("title")
    if title_tag:
        meta["title_raw"] = _clean_text(title_tag.get_text())

    h1 = soup.find("h1")
    if h1:
        meta["brand_line"] = _clean_text(h1.get_text(" "))

    # Pills (both old and new template use div.pill)
    for pill in soup.select(".pill"):
        txt = _clean_text(pill.get_text(" "))
        if txt.lower().startswith("issue:"):
            m = re.search(r"(ATB-\d{4}-\d+)", txt, re.I)
            if m:
                meta["issue_number"] = m.group(1).upper()
        elif txt.lower().startswith("week of:"):
            meta["week_of"] = txt.split(":", 1)[1].strip()
        elif txt.lower().startswith("coverage:"):
            meta["coverage_tags"] = txt.split(":", 1)[1].strip()
        elif txt.lower().startswith("next issue:"):
            meta["next_issue"] = txt.split(":", 1)[1].strip()

    if not meta["issue_number"]:
        # fall back to title or filename-adjacent search anywhere in doc
        whole = soup.get_text(" ")
        m = re.search(r"(ATB-\d{4}-\d+)", whole)
        if m:
            meta["issue_number"] = m.group(1).upper()

    if meta["issue_number"]:
        m = re.match(r"ATB-(\d{4})-(\d+)", meta["issue_number"])
        if m:
            meta["year"] = int(m.group(1))
            meta["issue_num_int"] = int(m.group(2))

    # meta-cell strip (newer template): Issue Date / Coverage / Dominant Theme / Sector Focus
    for cell in soup.select(".meta-cell"):
        lbl = cell.select_one(".meta-lbl")
        val = cell.select_one(".meta-val")
        if not lbl or not val:
            continue
        lbl_txt = _clean_text(lbl.get_text()).lower()
        val_txt = _clean_text(val.get_text(" "))
        if lbl_txt == "coverage":
            meta["coverage_period"] = val_txt
        elif lbl_txt == "dominant theme":
            meta["dominant_theme"] = val_txt
        elif lbl_txt == "sector focus":
            meta["sector_focus"] = val_txt

    if not meta["coverage_period"]:
        meta["coverage_period"] = meta["week_of"]

    threat = soup.select_one(".threat-label")
    if threat:
        meta["threat_label"] = _clean_text(threat.get_text(" "))

    if meta["year"] is None and meta["issue_date"]:
        meta["year"] = int(meta["issue_date"][:4])

    return meta


# ---------------------------------------------------------------------------
# Content region isolation
# ---------------------------------------------------------------------------

def strip_sentinel_block(html: str, start_marker: str, end_marker: str) -> str:
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
    return pattern.sub("", html)


def get_content_root(soup: BeautifulSoup) -> Tag:
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    for el in list(soup.find_all(True)):
        if not el.parent:
            continue
        cls = class_str(el).lower()
        if any(s in cls for s in SKIP_CLASS_SUBSTR):
            el.decompose()

    body = soup.find("body") or soup
    return body


# ---------------------------------------------------------------------------
# Block-level component handlers (known component classes -> typed blocks)
# ---------------------------------------------------------------------------

def handle_kj_block(el: Tag) -> dict:
    items = []
    for item in el.select(".kj-item"):
        num = item.select_one(".kj-num")
        text_el = item.select_one(".kj-text")
        uncertainty = item.select_one(".kj-uncertainty")
        decision = item.select_one(".decision-line")
        # runs for kj-text excluding the nested uncertainty/decision divs
        text_el_copy = BeautifulSoup(str(text_el), "lxml") if text_el else None
        runs = []
        uncertainty_text = None
        decision_text = None
        if text_el:
            for sub in text_el.find_all(["div"], class_=["kj-uncertainty", "decision-line"]):
                sub.extract()
            runs = extract_runs(text_el)
        if uncertainty:
            uncertainty_text = runs_to_plain(extract_runs(uncertainty))
        if decision:
            decision_text = runs_to_plain(extract_runs(decision))
        items.append({
            "num": _clean_text(num.get_text()) if num else None,
            "runs": runs,
            "uncertainty": uncertainty_text,
            "decision": decision_text,
        })
    return {"type": "judgment_list", "items": items}


def handle_gov_block(el: Tag) -> dict:
    rows = []
    for row in el.select(".gov-row"):
        label = row.select_one(".gov-label")
        content = row.select_one(".gov-content")
        rows.append({
            "label": _clean_text(label.get_text()) if label else "",
            "runs": extract_runs(content) if content else [],
        })
    return {"type": "kv_list", "rows": rows}


def handle_implications_table(el: Tag) -> dict:
    rows = []
    for row in el.select(".implication-row"):
        sector = row.select_one(".implication-sector")
        content = row.select_one(".implication-content")
        sector_txt = _clean_text(sector.get_text(" ")) if sector else ""
        rows.append({
            "sector": sector_txt,
            "runs": extract_runs(content) if content else [],
        })
    return {"type": "table_rows", "rows": rows}


def handle_prq_blocks(container_items: list[Tag]) -> dict:
    items = []
    for el in container_items:
        pid = el.select_one(".prq-id")
        title = el.select_one(".prq-title")
        risk = el.select_one(".prq-risk")
        notes = [
            _clean_text(li.get_text(" "))
            for li in el.select(".prq-indicators li")
        ]
        body_paras = [
            _clean_text(p.get_text(" "))
            for p in el.select(".prq-body p")
        ]
        items.append({
            "id": _clean_text(pid.get_text()) if pid else None,
            "title": _clean_text(title.get_text(" ")) if title else None,
            "risk": _clean_text(risk.get_text(" ")) if risk else None,
            "notes": notes,
            "body_paragraphs": body_paras,
        })
    return {"type": "indicator_list", "items": items}


def handle_src_block(el: Tag) -> dict:
    entries = []
    # newer template: div.src-entry with label/title/url/note
    for entry in el.select(".src-entry"):
        label = entry.select_one(".src-label")
        title = entry.select_one(".src-title")
        url_a = entry.select_one(".src-url") or entry.find("a")
        note = entry.select_one(".src-note")
        entries.append({
            "label": _clean_text(label.get_text()) if label else None,
            "title": _clean_text(title.get_text(" ")) if title else None,
            "url_text": _clean_text(url_a.get_text(" ")) if url_a else None,
            "url_href": url_a.get("href") if url_a else None,
            "note": _clean_text(note.get_text(" ")) if note else None,
        })
    header_txt = None
    hdr = el.select_one(".src-header")
    if hdr:
        header_txt = _clean_text(hdr.get_text(" "))
    # older template: ul.src-list li with strong + a
    if not entries:
        for li in el.select(".src-list li"):
            a = li.find("a")
            strong = li.find("strong") or li.select_one(".src-title")
            entries.append({
                "label": None,
                "title": _clean_text(strong.get_text(" ")) if strong else None,
                "url_text": _clean_text(a.get_text(" ")) if a else None,
                "url_href": a.get("href") if a else None,
                "note": None,
            })
    return {"type": "source_list", "header": header_txt, "entries": entries}


def handle_watch_grid(el: Tag) -> dict:
    items = []
    for item in el.select(".watch-item"):
        num = item.select_one(".watch-num")
        text_el = item.select_one(".watch-text")
        items.append({
            "num": _clean_text(num.get_text()) if num else None,
            "runs": extract_runs(text_el) if text_el else [],
        })
    return {"type": "watch_list", "items": items}


def handle_doctrine_grid(el: Tag) -> dict:
    items = []
    for card in el.select(".doctrine-card"):
        label = card.select_one(".doctrine-label")
        title = card.select_one(".doctrine-title")
        paras = [extract_runs(p) for p in card.find_all("p")]
        items.append({
            "label": _clean_text(label.get_text()) if label else None,
            "title": _clean_text(title.get_text(" ")) if title else None,
            "paragraphs": paras,
        })
    return {"type": "doctrine_grid", "items": items}


def handle_exec_brief(el: Tag) -> dict:
    items = []
    for item in el.select(".exec-item"):
        title = item.select_one(".exec-item-title")
        paras = []
        for p in item.find_all("p", recursive=True):
            if p.find_parent(class_="decision-line"):
                continue
            paras.append(extract_runs(p))
        decision = item.select_one(".decision-line")
        items.append({
            "title": _clean_text(title.get_text(" ")) if title else None,
            "paragraphs": paras,
            "decision": runs_to_plain(extract_runs(decision)) if decision else None,
        })
    return {"type": "exec_grid", "items": items}


def handle_callout(el: Tag, label_override: str | None = None) -> dict:
    label = label_override
    paras = [extract_runs(p) for p in el.find_all("p", recursive=False)]
    if not paras:
        paras = [extract_runs(p) for p in el.find_all("p")]
    return {"type": "callout", "label": label, "paragraphs": paras}


def handle_intel_card(el: Tag) -> dict:
    sector = el.select_one(".sector")
    headline = el.select_one(".headline")
    snippet = el.select_one(".snippet")
    source_link = el.select_one(".source-link") or el.select_one(".source-row a")
    return {
        "type": "intel_card",
        "sector": _clean_text(sector.get_text(" ")) if sector else None,
        "headline": _clean_text(headline.get_text(" ")) if headline else None,
        "runs": extract_runs(snippet) if snippet else [],
        "source_text": _clean_text(source_link.get_text(" ")) if source_link else None,
        "source_href": source_link.get("href") if source_link else None,
    }


KNOWN_CLASS_HANDLERS = {
    "kj-block": handle_kj_block,
    "gov-block": handle_gov_block,
    "implications-table": handle_implications_table,
    "watch-grid": handle_watch_grid,
    "doctrine-grid": handle_doctrine_grid,
    "exec-brief": handle_exec_brief,
    "src-block": handle_src_block,
}

CALLOUT_LABELS = {
    "centerpiece": "CENTERPIECE ANALYSIS",
    "warning-box": "CRITICAL INTELLIGENCE WARNING",
    "assessment-box": "ASSESSMENT",
    "analyst-note": "ANALYST'S NOTE",
    "torch-note": "TORCH FUSION CYCLE",
    "intro-deck": None,
}


# ---------------------------------------------------------------------------
# Generic recursive walk
# ---------------------------------------------------------------------------

def walk_content(root: Tag) -> list[dict]:
    blocks: list[dict] = []
    _walk(root, blocks)
    return blocks


def _walk(el: Tag, blocks: list[dict]):
    for child in el.children:
        if isinstance(child, NavigableString):
            if isinstance(child, Comment):
                continue
            txt = _clean_text(str(child))
            if txt:
                blocks.append({"type": "paragraph", "runs": [{"text": txt, "bold": False, "italic": False, "mono": False, "link": None}]})
            continue
        if not isinstance(child, Tag):
            continue

        name = child.name
        cls = class_str(child)
        cls_tokens = cls.split()

        if name in ("script", "style"):
            continue

        # known component containers (centerpiece grid of prq-blocks is special: multiple siblings)
        matched_class = next((c for c in cls_tokens if c in KNOWN_CLASS_HANDLERS), None)
        if matched_class:
            blocks.append(KNOWN_CLASS_HANDLERS[matched_class](child))
            continue

        if "prq-block" in cls_tokens:
            # consume this and any immediately-following sibling prq-blocks together
            blocks.append(handle_prq_blocks([child]))
            continue

        if any(c in CALLOUT_LABELS for c in cls_tokens):
            label_class = next(c for c in cls_tokens if c in CALLOUT_LABELS)
            blocks.append(handle_callout(child, CALLOUT_LABELS[label_class]))
            continue

        if "intel-card" in cls_tokens or ("card" in cls_tokens and child.select_one(".headline")):
            blocks.append(handle_intel_card(child))
            continue

        if name in ("h1", "h2", "h3", "h4"):
            level = int(name[1])
            blocks.append({"type": "heading", "level": level, "text": _clean_text(child.get_text(" "))})
            continue

        if name == "p":
            runs = extract_runs(child)
            if runs_to_plain(runs):
                para_class = "legal" if any(c in cls_tokens for c in ("atb-copyright", "atb-disclaimer", "atb-source-notice")) else None
                blocks.append({"type": "paragraph", "runs": runs, "style": para_class})
            continue

        if name in ("ul", "ol"):
            items = []
            for li in child.find_all("li", recursive=False):
                items.append(extract_runs(li))
            if items:
                blocks.append({"type": "generic_list", "ordered": name == "ol", "items": items})
            continue

        if name == "hr":
            blocks.append({"type": "rule"})
            continue

        if name in ("div", "section", "article", "header", "main", "span", "strong", "em", "figure"):
            _walk(child, blocks)
            continue

        # unknown tag: try to recurse; if it has no element children, capture text
        if child.find(True) is None:
            txt = _clean_text(child.get_text(" "))
            if txt:
                blocks.append({"type": "paragraph", "runs": extract_runs(child)})
        else:
            _walk(child, blocks)


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------

def parse_issue(html_path: str | Path) -> dict:
    path = Path(html_path)
    raw = path.read_text(encoding="utf-8", errors="replace")

    meta_soup = BeautifulSoup(raw, "lxml")
    metadata = extract_metadata(meta_soup, path)

    content_html = strip_sentinel_block(raw, "<!-- LCTI:NAV:START -->", "<!-- LCTI:NAV:END -->")
    content_html = strip_sentinel_block(content_html, "<!-- LCTI:FOOTER:START -->", "<!-- LCTI:FOOTER:END -->")
    content_html = strip_sentinel_block(content_html, "<!-- LCTI:ARCHIVE_FOOTER_FIX:START -->", "<!-- LCTI:ARCHIVE_FOOTER_FIX:END -->")

    soup = BeautifulSoup(content_html, "lxml")
    root = get_content_root(soup)
    blocks = walk_content(root)

    source_text_len = len(_clean_text(root.get_text(" ")))

    return {
        "metadata": metadata,
        "blocks": blocks,
        "_source_text_len": source_text_len,
        "_source_path": str(path),
    }


def main():
    if len(sys.argv) < 2:
        print("usage: parse_atb.py <issue.html> [out.json]", file=sys.stderr)
        sys.exit(1)
    result = parse_issue(sys.argv[1])
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(out, encoding="utf-8")
    else:
        print(out)


if __name__ == "__main__":
    main()
