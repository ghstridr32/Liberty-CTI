#!/usr/bin/env python3
"""Rebuild the Alamo Threat Brief archive from dated ATB issue files.

The archive should not require hand edits every time a new ATB is added.
This script scans the site for files named MM-DD-YYYY.html, assigns the
sequential ATB issue number from oldest to newest, and refreshes the archive
page content plus the latest-issue CTA/count.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parent
DATED_ATB_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-(\d{4})\.html$", re.IGNORECASE)

ARCHIVE_PAGES = [
    Path("atb") / "index.html",
]

ISSUE_OVERRIDES = {
    "03-16-2026.html": {
        "title": "Texas Critical Infrastructure Threat Baseline",
        "summary": "Establishes the baseline threat picture across Texas energy, healthcare, finance, defense, and technology sectors.",
        "tags": ["energy", "healthcare", "finance", "defense", "texas"],
        "data_tags": "energy healthcare finance defense texas",
        "sector": "cross-sector",
    },
    "03-22-2026.html": {
        "title": "Operation Epic Fury: Cyber Implications for Texas",
        "summary": "Frames cyber escalation dynamics and related threat activity for Texas critical-infrastructure leaders.",
        "tags": ["defense", "iran", "china", "russia", "North Korea", "Cybercrime"],
        "data_tags": "defense iran operations china russia north-korea cybercrime ransomware",
        "sector": "defense",
    },
    "03-29-2026.html": {
        "title": "Iran-Linked Handala Activity and U.S. Healthcare Exposure",
        "summary": "Explains the Handala/Stryker reporting and what it means for healthcare, defense, and financial-sector risk.",
        "tags": ["iran", "healthcare", "defense", "finance"],
        "data_tags": "iran healthcare defense finance",
        "sector": "cross-sector",
    },
    "04-03-2026.html": {
        "title": "Supply-Chain Disruption and Persistent Access Risk",
        "summary": "Hasbro disruption, LiteLLM/Mercor exposure, Nacogdoches breach, and Russian return-to-breach operations.",
        "tags": ["supply chain", "healthcare", "russia", "AI"],
        "data_tags": "supply-chain healthcare russia ai texas defense",
        "sector": "cross-sector",
    },
    "04-12-2026.html": {
        "title": "Active Exploitation, North Korea Crypto Theft, and Infrastructure Risk",
        "summary": "Exploited edge infrastructure, North Korea-linked crypto operations, vulnerability pressure, and cybercrime activity.",
        "tags": ["china", "North Korea", "Cybercrime", "ransomware"],
        "data_tags": "weekly china russia north-korea cybercrime ransomware infrastructure",
        "sector": "all",
    },
    "04-19-2026.html": {
        "title": "Sector Risk: Iran, North Korea, Cybercrime, and AI",
        "summary": "Iranian OT risk, North Korea-linked AI-enabled fraud and crypto activity, cybercrime infrastructure disruption, and Texas sector exposure.",
        "tags": ["iran", "North Korea", "energy", "finance", "AI"],
        "data_tags": "weekly iran north-korea energy finance healthcare defense ai",
        "sector": "all",
    },
    "04-26-2026.html": {
        "title": "Texas Cyber Risk: Multi-Actor Pressure Continues",
        "summary": "Iranian OT warning activity, Texas AI-energy exposure, financial vendor risk, North Korea revenue schemes, and Russian disruptive trends.",
        "tags": ["iran", "russia", "North Korea", "energy", "finance", "AI"],
        "data_tags": "weekly iran russia north-korea energy finance dib ai texas",
        "sector": "all",
    },
    "05-03-2026.html": {
        "title": "Texas Cyber Risk: Developer Pipelines, Energy Logistics, and OT Exposure",
        "summary": "DPRK developer supply-chain activity, Russian energy logistics targeting, Iranian OT pressure, active exploitation, and Texas data-center dependency risk.",
        "tags": ["North Korea", "russia", "iran", "energy", "defense", "AI"],
        "data_tags": "weekly north-korea russia iran energy defense ai data-centers ot texas",
        "sector": "all",
    },
    "05-10-2026.html": {
        "title": "The Federal Posture Just Changed",
        "summary": "CI Fortify, Five Eyes agentic AI guidance, healthcare cyber-resilience readiness, DPRK enforcement, Iranian OT pressure, and edge-device exploitation shift board expectations for Texas operators.",
        "tags": ["CISA", "AI", "healthcare", "energy", "DPRK", "Iran"],
        "data_tags": "weekly cisa ai healthcare energy north-korea iran ot data-centers resilience texas",
        "sector": "all",
    },
    "05-17-2026.html": {
        "title": "Texas Infrastructure Concentration Is the Target",
        "summary": "CI Fortify, ERCOT demand pressure, simultaneous ICS advisories, and continued DPRK enforcement converge on Texas grid, telecom, cloud, MSP, and identity dependency risk.",
        "tags": ["CISA", "ERCOT", "ICS", "energy", "DPRK", "Texas"],
        "data_tags": "weekly cisa ercot ics energy dprk texas infrastructure data-centers cloud msp identity",
        "sector": "all",
    },
    "05-24-2026.html": {
        "title": "Iran's Cyber Campaign Is Wartime Operations",
        "summary": "Iran-linked aviation and oil-and-gas targeting, confirmed PLC disruption context, suspected ATG access, NERC grid warnings, and AI-enabled adversary operations elevate Texas OT and energy-continuity risk.",
        "tags": ["Iran", "energy", "OT", "AI", "NERC", "Texas"],
        "data_tags": "latest weekly iran energy ot ai nerc ercot aviation oil-gas texas governance",
        "sector": "all",
    },
    "05-31-2026.html": {
        "title": "Infrastructure Convergence: Three Adversaries, One Summer",
        "summary": "China infrastructure persistence, Russian hybrid escalation, Iranian Hormuz cable coercion, and ERCOT summer demand pressure converge on Texas continuity, cloud-routing, power, and vendor-access assumptions.",
        "tags": ["China", "Russia", "Iran", "ERCOT", "energy", "AI"],
        "data_tags": "latest weekly china russia iran ercot energy ai cloud-routing continuity texas infrastructure",
        "sector": "all",
    },
}


@dataclass(frozen=True)
class Issue:
    filename: str
    date: datetime
    issue_number: int
    title: str
    summary: str
    tags: list[str]
    data_tags: str
    sector: str


def issue_date(filename: str) -> datetime:
    return datetime.strptime(Path(filename).stem, "%m-%d-%Y")


def source_priority(path: Path) -> int:
    parts = path.parts
    if len(parts) >= 3 and parts[0] == "atb" and parts[1] == "issues":
        return 0
    if len(parts) >= 2 and parts[0] == "Intel Production" and parts[1] == "liberty_cti_briefs":
        return 1
    if len(parts) == 1:
        return 2
    if parts and parts[0] == "April 2026":
        return 3
    return 3


def discover_issue_files(root: Path) -> list[Path]:
    chosen: dict[str, Path] = {}
    candidate_dirs = [
        root / "atb" / "issues",
        root / "Intel Production" / "liberty_cti_briefs",
        root / "April 2026",
    ]
    for directory in candidate_dirs:
        if not directory.exists():
            continue
        for path in directory.glob("*.html"):
            if not DATED_ATB_RE.match(path.name):
                continue
            rel = path.relative_to(root)
            current = chosen.get(path.name)
            if current is None or source_priority(rel) < source_priority(current.relative_to(root)):
                chosen[path.name] = path
    return sorted(chosen.values(), key=lambda p: issue_date(p.name))


def fallback_text(path: Path, issue_number: int) -> tuple[str, str, list[str], str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.IGNORECASE | re.DOTALL)
    title = "The Alamo Threat Brief"
    if h1_match:
        title = re.sub(r"<[^>]+>", "", h1_match.group(1))
        title = re.sub(r"\s+", " ", html.unescape(title)).strip()
    if not title or title.lower() == "the alamo threat brief":
        title = f"The Alamo Threat Brief Issue {issue_number}"
    summary = "Weekly executive warning intelligence for Texas critical infrastructure leaders."
    tags = ["weekly", "texas", "cyber risk"]
    data_tags = "weekly texas cyber-risk"
    return title, summary, tags, data_tags, "all"


def build_issues(root: Path) -> list[Issue]:
    paths = discover_issue_files(root)
    issues: list[Issue] = []
    for number, path in enumerate(paths, start=1):
        override = ISSUE_OVERRIDES.get(path.name)
        if override:
            title = override["title"]
            summary = override["summary"]
            tags = list(override["tags"])
            data_tags = override["data_tags"]
            sector = override["sector"]
        else:
            title, summary, tags, data_tags, sector = fallback_text(path, number)
        issues.append(
            Issue(
                filename=path.name,
                date=issue_date(path.name),
                issue_number=number,
                title=title,
                summary=summary,
                tags=tags,
                data_tags=data_tags,
                sector=sector,
            )
        )
    return issues


def date_label(dt: datetime) -> str:
    return dt.strftime("%d %b %Y").upper()


def tag_html(tags: list[str]) -> str:
    return "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in tags)


def month_key(issue: Issue) -> tuple[int, int]:
    return issue.date.year, issue.date.month


def month_label(year: int, month: int) -> str:
    return datetime(year, month, 1).strftime("%B %Y")


def month_id(year: int, month: int) -> str:
    return f"archive-{year}-{month:02d}"


def group_issues_by_month(issues: list[Issue]) -> OrderedDict[tuple[int, int], list[Issue]]:
    grouped: OrderedDict[tuple[int, int], list[Issue]] = OrderedDict()
    for issue in sorted(issues, key=lambda item: item.date, reverse=True):
        grouped.setdefault(month_key(issue), []).append(issue)
    return grouped


def render_issue_card(issue: Issue, latest: Issue) -> str:
    latest_badge = '<span class="status-chip">Latest</span>' if issue.filename == latest.filename else ""
    searchable = " ".join([issue.title, issue.summary, issue.filename, f"ATB-2026-{issue.issue_number}", *issue.tags])
    stem = Path(issue.filename).stem
    return f'''        <a class="issue-card" href="/atb/2026/{stem}/" data-tags="{html.escape(issue.data_tags)}" data-sector="{html.escape(issue.sector)}" data-search="{html.escape(searchable.lower())}">
          <div class="issue-date-block">
            <span class="issue-day">{issue.date.strftime("%d")}</span>
            <span class="issue-month">{issue.date.strftime("%b").upper()}</span>
          </div>
          <div class="issue-main">
            <div class="issue-kicker">ATB-2026-{issue.issue_number}{latest_badge}</div>
            <div class="issue-title">{html.escape(issue.title)}</div>
            <div class="issue-summary">{html.escape(issue.summary)}</div>
            <div class="issue-tags">{tag_html(issue.tags)}</div>
          </div>
          <div class="issue-arrow">Open</div>
        </a>'''


def render_archive_library(issues: list[Issue]) -> str:
    latest = issues[-1]
    grouped = group_issues_by_month(issues)
    rail_links = []
    month_sections = []
    for (year, month), month_issues in grouped.items():
        label = month_label(year, month)
        anchor = month_id(year, month)
        count = len(month_issues)
        issue_word = "issue" if count == 1 else "issues"
        rail_links.append(
            f'''        <a class="rail-link" href="#{anchor}" data-month-link="{anchor}">
          <span>{html.escape(label)}</span>
          <strong>{count}</strong>
        </a>'''
        )
        cards = "\n".join(render_issue_card(issue, latest) for issue in month_issues)
        month_sections.append(
            f'''      <section class="month-group" id="{anchor}" data-month="{html.escape(label)}" data-year="{year}">
        <div class="month-head">
          <div>
            <span class="month-eyebrow">{year}</span>
            <h3>{html.escape(label)}</h3>
          </div>
          <span class="month-count">{count} {issue_word}</span>
        </div>
        <div class="month-issues">
{cards}
        </div>
      </section>'''
        )
    return f'''<!-- LCTI:ATB_ARCHIVE:START -->
    <div class="archive-library" id="archive-library">
      <aside class="archive-rail" aria-label="Archive months">
        <div class="rail-title">Jump to</div>
{chr(10).join(rail_links)}
      </aside>
      <div class="archive-timeline">
{chr(10).join(month_sections)}
      </div>
    </div>
    <!-- LCTI:ATB_ARCHIVE:END -->'''


def update_archive_page(content: str, issues: list[Issue]) -> str:
    latest = issues[-1]
    updated = content
    latest_stem = Path(latest.filename).stem
    updated = re.sub(
        r'<a class="quick-link" href="[^"]*">(Open Latest Issue|View the latest Alamo Threat Brief)</a>',
        f'<a class="quick-link" href="/atb/2026/{latest_stem}/">View the latest Alamo Threat Brief</a>',
        updated,
        count=1,
    )
    updated = re.sub(
        r'(<span class="stat-num">)\d+(</span><span class="stat-label">Published Briefs</span>)',
        rf'\g<1>{len(issues)}\2',
        updated,
        count=1,
    )
    updated = re.sub(
        r'<span class="eyebrow">CY \d{4}</span>\s*<h2>.*?</h2>',
        '<span class="eyebrow">Briefing Library</span>\n          <h2>Browse by month and year</h2>',
        updated,
        count=1,
        flags=re.DOTALL,
    )
    updated = re.sub(
        r'<p>Open any briefing directly from the list below\..*?</p>',
        '<p>Use the month rail, filters, and search to move quickly from the latest issue to the exact warning your leadership team needs for a decision, briefing, or escalation review.</p>',
        updated,
        count=1,
        flags=re.DOTALL,
    )
    archive_block = render_archive_library(issues) + "\n\n      "
    if "LCTI:ATB_ARCHIVE:START" in updated:
        updated = re.sub(
            r'<!-- LCTI:ATB_ARCHIVE:START -->.*?<!-- LCTI:ATB_ARCHIVE:END -->\s*',
            archive_block,
            updated,
            count=1,
            flags=re.DOTALL,
        )
    else:
        updated = re.sub(
            r'<div class="issue-list" id="issue-list">.*?</div>\s*<div class="mobile-cards" id="mobile-cards">.*?</div>\s*(?=<div class="empty-state" id="empty-state">)',
            archive_block,
            updated,
            count=1,
            flags=re.DOTALL,
        )
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the ATB archive from dated issue pages.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--write", action="store_true", help="Write updates. Without this flag, only report changes.")
    args = parser.parse_args()

    root = args.root.resolve()
    issues = build_issues(root)
    if not issues:
        print("No dated ATB issue files found.")
        return 1

    changed = []
    for rel_page in ARCHIVE_PAGES:
        page = root / rel_page
        if not page.exists():
            continue
        original = page.read_text(encoding="utf-8", errors="ignore")
        updated = update_archive_page(original, issues)
        if updated != original:
            changed.append(rel_page)
            if args.write:
                page.write_text(updated, encoding="utf-8")

    latest = issues[-1]
    mode = "Updated" if args.write else "Would update"
    print(f"{mode} {len(changed)} archive page(s).")
    print(f"Latest: ATB-2026-{latest.issue_number} ({latest.filename}); total issues: {len(issues)}")
    for rel_page in changed:
        print(f" - {rel_page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
