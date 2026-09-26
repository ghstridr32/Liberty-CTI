"""
build_pdf.py -- Render a canonical ATB issue dict (from parse_atb.py) into a
print-formatted, US Letter, Liberty CTI-branded PDF using reportlab (pure
Python, no headless-browser dependency).

Usage:
    python build_pdf.py path/to/issue.html out.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, KeepTogether, NextPageTemplate,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

sys.path.insert(0, str(Path(__file__).parent))
from parse_atb import parse_issue  # noqa: E402

NAVY = colors.HexColor("#142233")
GOLD = colors.HexColor("#A67C2E")
GOLD_DARK = colors.HexColor("#7A5A1E")
BLUE = colors.HexColor("#1F5C8C")
RED = colors.HexColor("#A3221C")
GRAY = colors.HexColor("#5C5C5C")
BG_GOLD = colors.HexColor("#F5F1E8")
BG_BLUE = colors.HexColor("#EAF0F6")
RULE_GOLD = colors.HexColor("#A67C2E")
RULE_LIGHT = colors.HexColor("#CCCCCC")

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"
FONT_I = "Helvetica-Oblique"
FONT_MONO = "Courier"

MARGIN = 2.2 * cm


def runs_to_html(runs: list[dict]) -> str:
    parts = []
    for r in runs:
        text = escape(r["text"]).replace("\n", "<br/>")
        if r.get("mono"):
            text = f'<font face="{FONT_MONO}" size="7" color="#7A5A1E">{text}</font>'
        if r.get("bold"):
            text = f"<b>{text}</b>"
        if r.get("italic"):
            text = f"<i>{text}</i>"
        if r.get("link"):
            href = escape(r["link"], {'"': "&quot;"})
            text = f'<link href="{href}" color="#1F5C8C"><u>{text}</u></link>'
        parts.append(text)
    return "".join(parts) or "&nbsp;"


def style(name, **kw):
    base = dict(fontName=FONT, fontSize=10, leading=14, textColor=NAVY, spaceAfter=6)
    base.update(kw)
    return ParagraphStyle(name, **base)


S_BODY = style("body")
S_LEGAL = style("legal", fontSize=7.5, textColor=GRAY, alignment=TA_CENTER, leading=10)
S_H1 = style("h1", fontName=FONT_B, fontSize=15, textColor=GOLD_DARK, spaceBefore=16, spaceAfter=6)
S_H2 = style("h2", fontName=FONT_B, fontSize=13.5, textColor=GOLD_DARK, spaceBefore=16, spaceAfter=6)
S_H3 = style("h3", fontName=FONT_B, fontSize=11.5, textColor=NAVY, spaceBefore=10, spaceAfter=4)
S_LABEL = style("label", fontName=FONT_B, fontSize=8, textColor=GOLD_DARK, spaceAfter=3)
S_SMALL = style("small", fontSize=9, textColor=NAVY, spaceAfter=3)
S_ITALIC_SMALL = style("italic_small", fontName=FONT_I, fontSize=9, textColor=GRAY, spaceAfter=3, leftIndent=14)
S_INDENT = style("indent", fontSize=9.5, textColor=NAVY, spaceAfter=3, leftIndent=14)
S_TITLE = style("title", fontName=FONT_B, fontSize=25, textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)
S_EYEBROW = style("eyebrow", fontName=FONT_B, fontSize=9.5, textColor=GOLD_DARK, alignment=TA_CENTER, spaceAfter=2)
S_OSI = style("osi", fontName=FONT_MONO, fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceAfter=10)
S_TAGLINE = style("tagline", fontName=FONT_I, fontSize=10.5, textColor=GRAY, alignment=TA_CENTER, spaceBefore=6, spaceAfter=10)


def flow_heading(block):
    level = block["level"]
    st = S_H1 if level == 1 else (S_H2 if level == 2 else S_H3)
    flows = [Paragraph(escape(block["text"]), st)]
    if level <= 2:
        flows.append(HRFlowable(width="100%", thickness=1.2, color=RULE_GOLD, spaceAfter=6))
    return flows


def flow_paragraph(block):
    legal = block.get("style") == "legal"
    st = S_LEGAL if legal else S_BODY
    return [Paragraph(runs_to_html(block["runs"]), st)]


def flow_callout(block):
    label = (block.get("label") or "").upper()
    if "WARNING" in label:
        bar_color, label_color = RED, RED
    elif label in ("", "TORCH FUSION CYCLE"):
        bar_color, label_color = GOLD, GOLD_DARK
    else:
        bar_color, label_color = BLUE, BLUE
    inner = []
    if block.get("label"):
        inner.append(Paragraph(escape(block["label"].upper()), ParagraphStyle("lbl", fontName=FONT_B, fontSize=8, textColor=label_color, spaceAfter=4)))
    for para_runs in block["paragraphs"]:
        inner.append(Paragraph(runs_to_html(para_runs), style("cp", fontSize=10, spaceAfter=5)))
    tbl = Table([[inner]], colWidths=[LETTER[0] - 2 * MARGIN])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_GOLD),
        ("LINEBEFORE", (0, 0), (0, 0), 4, bar_color),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D2C2")),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [tbl, Spacer(1, 8)]


def flow_judgment_list(block):
    flows = []
    for item in block["items"]:
        head = f'<font color="#1F5C8C"><b>{escape(item.get("num") or "")}</b></font>  ' + runs_to_html(item["runs"])
        flows.append(Paragraph(head, style("kj", fontSize=10.5, spaceBefore=8, spaceAfter=2)))
        if item.get("uncertainty"):
            flows.append(Paragraph("Source basis / uncertainty: " + escape(item["uncertainty"]), S_ITALIC_SMALL))
        if item.get("decision"):
            flows.append(Paragraph(f'<font color="#7A5A1E">Decision implication: {escape(item["decision"])}</font>', S_INDENT))
    return flows


def flow_kv_table(block):
    rows = block["rows"]
    if not rows:
        return []
    data = [[Paragraph(escape(r["label"]), style("lbl", fontName=FONT_B, fontSize=8.5, textColor=GOLD_DARK)),
             Paragraph(runs_to_html(r["runs"]), style("val", fontSize=9.5))] for r in rows]
    tbl = Table(data, colWidths=[3.6 * cm, LETTER[0] - 2 * MARGIN - 3.6 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), BG_GOLD),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE_LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [tbl, Spacer(1, 8)]


def flow_table_rows(block):
    rows = block["rows"]
    if not rows:
        return []
    data = [[Paragraph(escape(r["sector"]), style("sec", fontName=FONT_B, fontSize=8.5, textColor=BLUE)),
             Paragraph(runs_to_html(r["runs"]), style("val", fontSize=9.5))] for r in rows]
    tbl = Table(data, colWidths=[3.2 * cm, LETTER[0] - 2 * MARGIN - 3.2 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), BG_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE_LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [tbl, Spacer(1, 8)]


def flow_indicator_list(block):
    flows = []
    for item in block["items"]:
        title_html = f'<font color="#1F5C8C"><b>{escape(item.get("id") or "")}</b></font>  <b>{escape(item.get("title") or "")}</b>'
        if item.get("risk"):
            title_html += f'  <font color="#7A5A1E"><i>[{escape(item["risk"])}]</i></font>'
        flows.append(Paragraph(title_html, style("ind", fontSize=10, spaceBefore=8, spaceAfter=2)))
        for note in item.get("notes", []):
            flows.append(Paragraph("&#8594; " + escape(note), S_INDENT))
        for bp in item.get("body_paragraphs", []):
            flows.append(Paragraph(escape(bp), S_INDENT))
    return flows


def flow_source_list(block):
    flows = []
    if block.get("header"):
        flows.append(Paragraph(escape(block["header"]), style("srchdr", fontName=FONT_B, fontSize=9, textColor=BLUE, spaceBefore=8)))
    for e in block["entries"]:
        parts = []
        if e.get("label"):
            flows.append(Paragraph(escape(e["label"]), style("srclbl", fontName=FONT_B, fontSize=7.5, textColor=GOLD_DARK, spaceBefore=6, spaceAfter=1)))
        if e.get("title"):
            flows.append(Paragraph(f"<b>{escape(e['title'])}</b>", style("srctitle", fontSize=10, spaceAfter=1)))
        if e.get("url_text") or e.get("url_href"):
            label = escape(e.get("url_text") or e.get("url_href") or "")
            href = e.get("url_href")
            if href:
                href_esc = escape(href, {'"': "&quot;"})
                txt = f'<font face="{FONT_MONO}" size="8" color="#1F5C8C"><link href="{href_esc}"><u>{label}</u></link></font>'
            else:
                txt = f'<font face="{FONT_MONO}" size="8" color="#1F5C8C">{label}</font>'
            flows.append(Paragraph(txt, style("srcurl", spaceAfter=1)))
        if e.get("note"):
            flows.append(Paragraph(f"<i>{escape(e['note'])}</i>", style("srcnote", fontSize=8.5, textColor=GRAY, spaceAfter=2)))
    return flows


def flow_watch_list(block):
    flows = []
    for item in block["items"]:
        html = f'<font color="#1F5C8C"><b>{escape(item.get("num") or "")}</b></font>  ' + runs_to_html(item["runs"])
        flows.append(Paragraph(html, style("watch", fontSize=9.5, spaceAfter=4)))
    return flows


def flow_doctrine_grid(block):
    flows = []
    for item in block["items"]:
        if item.get("label"):
            flows.append(Paragraph(escape(item["label"].upper()), style("dlbl", fontName=FONT_B, fontSize=7.5, textColor=GRAY, spaceBefore=8)))
        if item.get("title"):
            flows.append(Paragraph(f"<b>{escape(item['title'])}</b>", style("dtitle", fontSize=10.5)))
        for para in item.get("paragraphs", []):
            flows.append(Paragraph(runs_to_html(para), style("dpara", fontSize=9.5, spaceAfter=3)))
    return flows


def flow_exec_grid(block):
    flows = []
    for item in block["items"]:
        if item.get("title"):
            flows.append(Paragraph(f"<b>{escape(item['title'])}</b>", style("etitle", fontSize=10, textColor=GOLD_DARK, spaceBefore=8, spaceAfter=2)))
        for para in item.get("paragraphs", []):
            flows.append(Paragraph(runs_to_html(para), style("epara", fontSize=9.5, spaceAfter=2)))
        if item.get("decision"):
            flows.append(Paragraph(f"<i>{escape(item['decision'])}</i>", style("edec", fontSize=9, textColor=GRAY, spaceAfter=2)))
    return flows


def flow_generic_list(block):
    flows = []
    for item_runs in block["items"]:
        bullet = "&#8226; " if not block.get("ordered") else "&#8226; "
        flows.append(Paragraph(bullet + runs_to_html(item_runs), style("li", fontSize=10, leftIndent=14, spaceAfter=3)))
    return flows


def flow_intel_card(block):
    flows = []
    head = ""
    if block.get("sector"):
        head += f'<font color="#7A5A1E" size="8"><b>{escape(block["sector"].upper())}</b></font><br/>'
    if block.get("headline"):
        head += f'<b>{escape(block["headline"])}</b>'
    flows.append(Paragraph(head, style("card_head", fontSize=11.5, spaceBefore=10, spaceAfter=3)))
    flows.append(Paragraph(runs_to_html(block["runs"]), style("card_body", fontSize=10, spaceAfter=2)))
    if block.get("source_text"):
        href = block.get("source_href")
        label = escape("Source: " + block["source_text"])
        if href:
            href_esc = escape(href, {'"': "&quot;"})
            txt = f'<font face="{FONT_MONO}" size="8" color="#1F5C8C"><link href="{href_esc}"><u>{label}</u></link></font>'
        else:
            txt = f'<font face="{FONT_MONO}" size="8" color="#1F5C8C">{label}</font>'
        flows.append(Paragraph(txt, style("card_src", spaceAfter=4)))
    return flows


FLOW_BUILDERS = {
    "heading": flow_heading,
    "paragraph": flow_paragraph,
    "callout": flow_callout,
    "judgment_list": flow_judgment_list,
    "kv_list": flow_kv_table,
    "table_rows": flow_table_rows,
    "indicator_list": flow_indicator_list,
    "source_list": flow_source_list,
    "watch_list": flow_watch_list,
    "doctrine_grid": flow_doctrine_grid,
    "exec_grid": flow_exec_grid,
    "generic_list": flow_generic_list,
    "intel_card": flow_intel_card,
}


def build_title_flowables(meta: dict):
    flows = [
        Paragraph("LIBERTY CYBER THREAT INTELLIGENCE", S_EYEBROW),
        Paragraph("THE ALAMO THREAT BRIEF&trade;", S_TITLE),
        Paragraph("OPEN SOURCE INTELLIGENCE", S_OSI),
    ]
    meta_rows = []
    if meta.get("issue_number"):
        meta_rows.append(("ISSUE", meta["issue_number"]))
    if meta.get("coverage_period"):
        meta_rows.append(("COVERAGE PERIOD", meta["coverage_period"]))
    if meta.get("issue_date"):
        meta_rows.append(("PUBLICATION DATE", meta["issue_date"]))
    if meta.get("dominant_theme"):
        meta_rows.append(("DOMINANT JUDGMENT", meta["dominant_theme"]))
    elif meta.get("threat_label"):
        meta_rows.append(("THREAT POSTURE", meta["threat_label"][:180]))
    if meta_rows:
        data = [[Paragraph(lbl, style("mlbl", fontName=FONT_B, fontSize=8, textColor=GOLD_DARK)),
                 Paragraph(escape(val), style("mval", fontSize=9.5))] for lbl, val in meta_rows]
        tbl = Table(data, colWidths=[3.6 * cm, LETTER[0] - 2 * MARGIN - 3.6 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), BG_GOLD),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E0DACB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        flows.append(tbl)
    flows.append(Paragraph("Executive decision intelligence for Texas critical infrastructure.", S_TAGLINE))
    flows.append(HRFlowable(width="100%", thickness=1.4, color=RULE_GOLD, spaceAfter=10))
    return flows


def _header_footer(canvas, doc, issue_number: str):
    canvas.saveState()
    canvas.setFont(FONT_B, 7.5)
    canvas.setFillColor(GRAY)
    canvas.drawCentredString(LETTER[0] / 2, LETTER[1] - 1.1 * cm, f"LIBERTY CTI  |  THE ALAMO THREAT BRIEF  |  {issue_number}")
    canvas.setFont(FONT, 7)
    canvas.drawCentredString(LETTER[0] / 2, 1.1 * cm, f"OPEN SOURCE INTELLIGENCE   —   Page {doc.page}")
    canvas.restoreState()


def build_pdf_from_issue(issue: dict, out_path: str | Path):
    meta = issue["metadata"]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(out_path), pagesize=LETTER,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=1.7 * cm, bottomMargin=1.7 * cm,
        title=f"{meta.get('issue_number','ATB')} — The Alamo Threat Brief",
        author="Liberty CTI",
    )
    frame = Frame(MARGIN, 1.7 * cm, LETTER[0] - 2 * MARGIN, LETTER[1] - 3.4 * cm, id="main")
    issue_no = meta.get("issue_number") or ""
    template = PageTemplate(id="atb", frames=[frame], onPage=lambda c, d: _header_footer(c, d, issue_no))
    doc.addPageTemplates([template])

    story = []
    story.extend(build_title_flowables(meta))

    for block in issue["blocks"]:
        builder = FLOW_BUILDERS.get(block["type"])
        if builder is None:
            if block["type"] == "rule":
                story.append(HRFlowable(width="100%", thickness=0.6, color=RULE_LIGHT, spaceAfter=6))
            continue
        story.extend(builder(block))

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "© 2026 Liberty CTI LLC. All rights reserved. The Alamo Threat Brief and its original "
        "analysis may not be reproduced or redistributed without permission. Alamo Threat Brief™ "
        "is a trademark of Liberty CTI LLC. This document is an archival companion to the published "
        "web issue and preserves the assessment as originally issued.",
        S_LEGAL,
    ))

    doc.build(story)
    return out_path


def main():
    if len(sys.argv) < 3:
        print("usage: build_pdf.py <issue.html> <out.pdf>", file=sys.stderr)
        sys.exit(1)
    issue = parse_issue(sys.argv[1])
    out = build_pdf_from_issue(issue, sys.argv[2])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
