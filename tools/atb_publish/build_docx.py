"""
build_docx.py -- Render a canonical ATB issue dict (from parse_atb.py) into a
print-formatted, US Letter, Liberty CTI-branded Word document (.docx).

Usage:
    python build_docx.py path/to/issue.html out.docx
    (or import build_docx(issue_dict, out_path) programmatically)
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).parent))
from parse_atb import parse_issue  # noqa: E402

# ---------------------------------------------------------------------------
# Palette (restrained Liberty CTI print system)
# ---------------------------------------------------------------------------
NAVY = RGBColor(0x14, 0x22, 0x33)       # body text
CHARCOAL = RGBColor(0x2A, 0x2A, 0x2A)
GOLD = RGBColor(0xA6, 0x7C, 0x2E)       # accent / headings
GOLD_DARK = RGBColor(0x7A, 0x5A, 0x1E)
BLUE = RGBColor(0x1F, 0x5C, 0x8C)       # judgments / info
RED = RGBColor(0xA3, 0x2A, 0x22)        # genuine warnings only
GRAY = RGBColor(0x5C, 0x5C, 0x5C)       # captions / meta
LIGHT_RULE = RGBColor(0xC9, 0xC9, 0xC9)

FONT_BODY = "Georgia"
FONT_HEAD = "Calibri"
FONT_MONO = "Consolas"


def _set_cell_bg(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _set_cell_border(cell, color="CCCCCC", sz="4"):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), sz)
        el.set(qn("w:color"), color)
        borders.append(el)
    tcPr.append(borders)


def add_runs(paragraph, runs: list[dict], base_color=NAVY, base_size=10.5, mono_size=8):
    if not runs:
        return
    for r in runs:
        text = r["text"]
        if text == "":
            continue
        if text == "\n":
            paragraph.add_run().add_break()
            continue
        run = paragraph.add_run(text)
        run.font.name = FONT_MONO if r.get("mono") else FONT_BODY
        run.font.size = Pt(mono_size if r.get("mono") else base_size)
        run.bold = bool(r.get("bold"))
        run.italic = bool(r.get("italic"))
        run.font.color.rgb = GOLD_DARK if r.get("mono") else base_color
        if r.get("link"):
            run.underline = True
            run.font.color.rgb = BLUE


def add_section_label(doc, text, color=GOLD):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text.upper())
    run.font.name = FONT_HEAD
    run.font.size = Pt(8.5)
    run.bold = True
    run.font.color.rgb = color
    run.font.name = FONT_HEAD
    # letter-spacing approximation not natively supported; keep as-is
    return p


def add_heading(doc, block):
    level = block["level"]
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16 if level <= 2 else 10)
    p.paragraph_format.space_after = Pt(6)
    if level <= 2:
        p.paragraph_format.border_bottom = None
        _add_bottom_border(p, "A67C2E", "6")
    run = p.add_run(block["text"])
    run.font.name = FONT_HEAD
    run.font.size = Pt(15 if level == 1 else (13.5 if level == 2 else 11.5))
    run.bold = True
    run.font.color.rgb = NAVY if level >= 3 else GOLD_DARK
    return p


def _add_bottom_border(paragraph, color, sz):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def add_paragraph_block(doc, block):
    style = block.get("style")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    color = GRAY if style == "legal" else NAVY
    size = 8 if style == "legal" else 10.5
    add_runs(p, block["runs"], base_color=color, base_size=size)
    if style == "legal":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def add_callout(doc, block, border_color=BLUE, label_color=None):
    label_color = label_color or border_color
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    _set_cell_bg(cell, "F5F1E8")
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "24")
    hexcol = "%02X%02X%02X" % (border_color[0], border_color[1], border_color[2])
    left.set(qn("w:color"), hexcol)
    borders.append(left)
    for edge in ("top", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "D8D2C2")
        borders.append(el)
    tcPr.append(borders)
    cell.text = ""
    first = True
    if block.get("label"):
        p = cell.paragraphs[0]
        run = p.add_run(block["label"].upper())
        run.bold = True
        run.font.size = Pt(8)
        run.font.name = FONT_HEAD
        run.font.color.rgb = label_color
        first = False
    for para_runs in block["paragraphs"]:
        p = cell.paragraphs[0] if first else cell.add_paragraph()
        first = False
        p.paragraph_format.space_after = Pt(6)
        add_runs(p, para_runs, base_color=NAVY, base_size=10)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return table


def add_judgment_list(doc, block):
    for item in block["items"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(10)
        num_run = p.add_run((item.get("num") or "") + "  ")
        num_run.bold = True
        num_run.font.color.rgb = BLUE
        num_run.font.name = FONT_HEAD
        num_run.font.size = Pt(9.5)
        add_runs(p, item["runs"], base_color=NAVY, base_size=10.5)
        if item.get("uncertainty"):
            up = doc.add_paragraph()
            up.paragraph_format.left_indent = Cm(0.5)
            up.paragraph_format.space_after = Pt(2)
            r = up.add_run("Source basis / uncertainty: " + item["uncertainty"])
            r.italic = True
            r.font.size = Pt(9)
            r.font.color.rgb = GRAY
        if item.get("decision"):
            dp = doc.add_paragraph()
            dp.paragraph_format.left_indent = Cm(0.5)
            dp.paragraph_format.space_after = Pt(6)
            r = dp.add_run("Decision implication: " + item["decision"])
            r.font.size = Pt(9.5)
            r.font.color.rgb = GOLD_DARK


def add_kv_table(doc, block):
    rows = block["rows"]
    if not rows:
        return
    table = doc.add_table(rows=len(rows), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Cm(3.6)
    table.columns[1].width = Cm(12.5)
    for i, row in enumerate(rows):
        lbl_cell, val_cell = table.rows[i].cells
        _set_cell_bg(lbl_cell, "F1ECDD")
        _set_cell_border(lbl_cell)
        _set_cell_border(val_cell)
        lbl_cell.width = Cm(3.6)
        p = lbl_cell.paragraphs[0]
        r = p.add_run(row["label"])
        r.bold = True
        r.font.size = Pt(9)
        r.font.name = FONT_HEAD
        r.font.color.rgb = GOLD_DARK
        vp = val_cell.paragraphs[0]
        add_runs(vp, row["runs"], base_color=NAVY, base_size=9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)


def add_table_rows_block(doc, block):
    rows = block["rows"]
    if not rows:
        return
    table = doc.add_table(rows=len(rows), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.columns[0].width = Cm(3.2)
    table.columns[1].width = Cm(13.0)
    for i, row in enumerate(rows):
        sec_cell, val_cell = table.rows[i].cells
        _set_cell_bg(sec_cell, "EAF0F6")
        _set_cell_border(sec_cell)
        _set_cell_border(val_cell)
        p = sec_cell.paragraphs[0]
        r = p.add_run(row["sector"])
        r.bold = True
        r.font.size = Pt(9)
        r.font.name = FONT_HEAD
        r.font.color.rgb = BLUE
        vp = val_cell.paragraphs[0]
        add_runs(vp, row["runs"], base_color=NAVY, base_size=9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)


def add_indicator_list(doc, block):
    for item in block["items"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"{item.get('id') or ''}  ")
        r.bold = True
        r.font.color.rgb = BLUE
        r.font.size = Pt(9)
        r2 = p.add_run(item.get("title") or "")
        r2.bold = True
        r2.font.size = Pt(10)
        r2.font.color.rgb = NAVY
        if item.get("risk"):
            r3 = p.add_run("   [" + item["risk"] + "]")
            r3.italic = True
            r3.font.size = Pt(9)
            r3.font.color.rgb = GOLD_DARK
        for note in item.get("notes", []):
            np = doc.add_paragraph(style=None)
            np.paragraph_format.left_indent = Cm(0.5)
            np.paragraph_format.space_after = Pt(2)
            nr = np.add_run("→ " + note)
            nr.font.size = Pt(9.5)
            nr.font.color.rgb = NAVY
        for bp in item.get("body_paragraphs", []):
            bpp = doc.add_paragraph()
            bpp.paragraph_format.left_indent = Cm(0.5)
            bpp.paragraph_format.space_after = Pt(2)
            br = bpp.add_run(bp)
            br.font.size = Pt(9.5)
            br.font.color.rgb = NAVY


def add_source_list(doc, block):
    if block.get("header"):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        r = p.add_run(block["header"])
        r.bold = True
        r.font.size = Pt(9)
        r.font.name = FONT_HEAD
        r.font.color.rgb = BLUE
    for e in block["entries"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(1)
        if e.get("label"):
            r = p.add_run(e["label"] + "\n")
            r.font.size = Pt(7.5)
            r.font.name = FONT_HEAD
            r.bold = True
            r.font.color.rgb = GOLD_DARK
        if e.get("title"):
            r2 = p.add_run(e["title"])
            r2.bold = True
            r2.font.size = Pt(10)
            r2.font.color.rgb = NAVY
        if e.get("url_text") or e.get("url_href"):
            up = doc.add_paragraph()
            up.paragraph_format.space_after = Pt(1)
            label = e.get("url_text") or e.get("url_href")
            _add_hyperlink(up, label, e.get("url_href") or "")
        if e.get("note"):
            npar = doc.add_paragraph()
            npar.paragraph_format.space_after = Pt(2)
            nr = npar.add_run(e["note"])
            nr.italic = True
            nr.font.size = Pt(8.5)
            nr.font.color.rgb = GRAY


def _add_hyperlink(paragraph, text, url):
    if not url:
        r = paragraph.add_run(text)
        r.font.size = Pt(8.5)
        r.font.color.rgb = BLUE
        return
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1F5C8C")
    rPr.append(color)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "17")
    rPr.append(sz)
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), FONT_MONO)
    rPr.append(rFonts)
    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def add_watch_list(doc, block):
    for item in block["items"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run((item.get("num") or "") + "  ")
        r.bold = True
        r.font.color.rgb = BLUE
        r.font.size = Pt(9)
        add_runs(p, item["runs"], base_color=NAVY, base_size=9.5)


def add_doctrine_grid(doc, block):
    for item in block["items"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        if item.get("label"):
            r = p.add_run(item["label"].upper() + "\n")
            r.font.size = Pt(7.5)
            r.font.name = FONT_HEAD
            r.font.color.rgb = GRAY
        if item.get("title"):
            r2 = p.add_run(item["title"])
            r2.bold = True
            r2.font.size = Pt(10.5)
            r2.font.color.rgb = NAVY
        for para in item.get("paragraphs", []):
            pp = doc.add_paragraph()
            pp.paragraph_format.space_after = Pt(3)
            add_runs(pp, para, base_color=NAVY, base_size=9.5)


def add_exec_grid(doc, block):
    for item in block["items"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        if item.get("title"):
            r = p.add_run(item["title"])
            r.bold = True
            r.font.size = Pt(10)
            r.font.color.rgb = GOLD_DARK
        for para in item.get("paragraphs", []):
            pp = doc.add_paragraph()
            pp.paragraph_format.space_after = Pt(2)
            add_runs(pp, para, base_color=NAVY, base_size=9.5)
        if item.get("decision"):
            dp = doc.add_paragraph()
            r2 = dp.add_run(item["decision"])
            r2.italic = True
            r2.font.size = Pt(9)
            r2.font.color.rgb = GRAY


def add_generic_list(doc, block):
    for item_runs in block["items"]:
        p = doc.add_paragraph(style="List Bullet" if not block.get("ordered") else "List Number")
        add_runs(p, item_runs, base_color=NAVY, base_size=10)


def add_intel_card(doc, block):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    if block.get("sector"):
        r = p.add_run(block["sector"].upper() + "\n")
        r.bold = True
        r.font.size = Pt(8)
        r.font.name = FONT_HEAD
        r.font.color.rgb = GOLD_DARK
    if block.get("headline"):
        r2 = p.add_run(block["headline"])
        r2.bold = True
        r2.font.size = Pt(11.5)
        r2.font.color.rgb = NAVY
    bp = doc.add_paragraph()
    bp.paragraph_format.space_after = Pt(2)
    add_runs(bp, block["runs"], base_color=NAVY, base_size=10)
    if block.get("source_text"):
        sp = doc.add_paragraph()
        sp.paragraph_format.space_after = Pt(4)
        _add_hyperlink(sp, "Source: " + block["source_text"], block.get("source_href") or "")


BLOCK_RENDERERS = {
    "heading": add_heading,
    "paragraph": add_paragraph_block,
    "judgment_list": add_judgment_list,
    "kv_list": add_kv_table,
    "table_rows": add_table_rows_block,
    "indicator_list": add_indicator_list,
    "source_list": add_source_list,
    "watch_list": add_watch_list,
    "doctrine_grid": add_doctrine_grid,
    "exec_grid": add_exec_grid,
    "generic_list": add_generic_list,
    "intel_card": add_intel_card,
}


def _set_header_footer(section, issue_number: str):
    header = section.header
    hp = header.paragraphs[0]
    hp.text = ""
    hr = hp.add_run(f"LIBERTY CTI  |  THE ALAMO THREAT BRIEF  |  {issue_number or ''}")
    hr.font.size = Pt(8)
    hr.font.name = FONT_HEAD
    hr.font.color.rgb = GRAY
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = fp.add_run("OPEN SOURCE INTELLIGENCE   —   Page ")
    fr.font.size = Pt(7.5)
    fr.font.name = FONT_HEAD
    fr.font.color.rgb = GRAY
    _add_page_number_field(fp)


def _add_page_number_field(paragraph):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)
    run.font.size = Pt(7.5)
    run.font.color.rgb = GRAY


def build_title_block(doc, meta: dict):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("LIBERTY CYBER THREAT INTELLIGENCE")
    r.font.name = FONT_HEAD
    r.font.size = Pt(9.5)
    r.bold = True
    r.font.color.rgb = GOLD_DARK

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_after = Pt(4)
    r2 = p2.add_run("THE ALAMO THREAT BRIEF™")
    r2.font.name = FONT_HEAD
    r2.font.size = Pt(24)
    r2.bold = True
    r2.font.color.rgb = NAVY

    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.space_after = Pt(10)
    r3 = p3.add_run("OPEN SOURCE INTELLIGENCE")
    r3.font.name = FONT_MONO
    r3.font.size = Pt(8)
    r3.font.color.rgb = GRAY

    meta_lines = []
    if meta.get("issue_number"):
        meta_lines.append(("Issue", meta["issue_number"]))
    if meta.get("coverage_period"):
        meta_lines.append(("Coverage Period", meta["coverage_period"]))
    if meta.get("issue_date"):
        meta_lines.append(("Publication Date", meta["issue_date"]))
    if meta.get("dominant_theme"):
        meta_lines.append(("Dominant Judgment", meta["dominant_theme"]))
    elif meta.get("threat_label"):
        meta_lines.append(("Threat Posture", meta["threat_label"][:180]))

    table = doc.add_table(rows=len(meta_lines), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.columns[0].width = Cm(3.4)
    table.columns[1].width = Cm(12.7)
    for i, (lbl, val) in enumerate(meta_lines):
        lc, vc = table.rows[i].cells
        _set_cell_border(lc, "E0DACB")
        _set_cell_border(vc, "E0DACB")
        _set_cell_bg(lc, "F5F1E8")
        lp = lc.paragraphs[0]
        lr = lp.add_run(lbl.upper())
        lr.bold = True
        lr.font.size = Pt(8)
        lr.font.name = FONT_HEAD
        lr.font.color.rgb = GOLD_DARK
        vp = vc.paragraphs[0]
        vr = vp.add_run(val)
        vr.font.size = Pt(9.5)
        vr.font.name = FONT_HEAD
        vr.font.color.rgb = NAVY

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    p4 = doc.add_paragraph()
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r4 = p4.add_run("Executive decision intelligence for Texas critical infrastructure.")
    r4.italic = True
    r4.font.size = Pt(10)
    r4.font.color.rgb = GRAY

    rule = doc.add_paragraph()
    _add_bottom_border(rule, "A67C2E", "10")
    rule.paragraph_format.space_after = Pt(10)


def build_docx_from_issue(issue: dict, out_path: str | Path):
    meta = issue["metadata"]
    doc = Document()

    section = doc.sections[0]
    section.page_height = Cm(27.94)
    section.page_width = Cm(21.59)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.header_distance = Cm(1.0)
    section.footer_distance = Cm(1.0)

    style = doc.styles["Normal"]
    style.font.name = FONT_BODY
    style.font.size = Pt(10.5)
    style.font.color.rgb = NAVY

    _set_header_footer(section, meta.get("issue_number") or "")

    build_title_block(doc, meta)

    for block in issue["blocks"]:
        renderer = BLOCK_RENDERERS.get(block["type"])
        if renderer is None:
            if block["type"] == "callout":
                continue
            if block["type"] == "rule":
                r = doc.add_paragraph()
                _add_bottom_border(r, "CCCCCC", "4")
                continue
            continue
        if block["type"] == "callout":
            label = (block.get("label") or "").upper()
            if "WARNING" in label:
                add_callout(doc, block, border_color=RED, label_color=RED)
            elif label in ("", None) or "TORCH" in label:
                add_callout(doc, block, border_color=GOLD, label_color=GOLD_DARK)
            else:
                add_callout(doc, block, border_color=BLUE, label_color=BLUE)
            continue
        renderer(doc, block)

    footer_note = doc.add_paragraph()
    footer_note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_note.paragraph_format.space_before = Pt(18)
    r = footer_note.add_run(
        "© 2026 Liberty CTI LLC. All rights reserved. The Alamo Threat Brief and its original "
        "analysis may not be reproduced or redistributed without permission. Alamo Threat Brief™ "
        "is a trademark of Liberty CTI LLC. This document is an archival companion to the published "
        "web issue and preserves the assessment as originally issued."
    )
    r.font.size = Pt(7.5)
    r.font.color.rgb = GRAY

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path


def main():
    if len(sys.argv) < 3:
        print("usage: build_docx.py <issue.html> <out.docx>", file=sys.stderr)
        sys.exit(1)
    issue = parse_issue(sys.argv[1])
    out = build_docx_from_issue(issue, sys.argv[2])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
