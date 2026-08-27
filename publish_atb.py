#!/usr/bin/env python3
"""
publish_atb.py  —  Publish a new Alamo Threat Brief issue to the Liberty CTI site.

Usage:
    python publish_atb.py "C:/path/to/MM-DD-YYYY.html"
    python publish_atb.py "C:/path/to/MM-DD-YYYY.html" --no-push
    python publish_atb.py "C:/path/to/MM-DD-YYYY.html" --no-deploy

What it does (in order):
  1.  Parses metadata from the source HTML (issue #, week-of, theme, etc.)
  2.  Creates atb/issues/SLUG.html  and  dist/atb/issues/SLUG.html
  3.  Creates dist/atb/YEAR/SLUG/full.html
  4.  Creates dist/atb/YEAR/SLUG/index.html  (paywall — shows Sections I-II, gates III+)
  5.  Creates dist/atb/YEAR/SLUG/meta.json
  6.  Updates atb/index.html and dist/atb/index.html (archive):
        - Adds new month group + rail link if needed, or inserts into existing month
        - Adds issue card with Latest chip; removes chip from previous latest
        - Increments the total-issues stat counter
  7.  Updates index.html and dist/index.html (homepage):
        - Replaces the LCTI:RECENT-ISSUES sentinel block with the 3 most recent issues
          (new issue + previous 2; oldest card dropped)
  8.  Updates every HTML file sitewide:
        - Replaces all 6 nav href formats pointing at old slug → new slug
        - Replaces nav label text (Latest Issue, Week of …)
        - Fixes JS alias array
  9.  git add / commit / push / wrangler deploy  (flags control last two steps)
"""

import argparse
import glob
import io
import json
import os
import re
import subprocess
import sys
from html import unescape
from pathlib import Path

# Ensure stdout handles Unicode on Windows (cp1252 terminals choke on – → etc.)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REPO = Path(__file__).parent

MONTHS_ABBR = ['', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
               'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
MONTHS_FULL = ['', 'January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']


# ── Metadata extraction ────────────────────────────────────────────────────────

def decode_html(s: str) -> str:
    s = re.sub(r'<[^>]+>', '', s)
    return unescape(s).strip()


def extract_meta(src: str, slug: str) -> dict:
    """Parse all needed metadata from the source HTML file."""
    m = {}

    # Date parts from slug: MM-DD-YYYY
    parts = slug.split('-')
    m['slug']       = slug
    m['year']       = int(parts[2])
    m['month_num']  = int(parts[0])
    m['day']        = int(parts[1])
    m['month_abbr'] = MONTHS_ABBR[m['month_num']]
    m['month_full'] = MONTHS_FULL[m['month_num']]

    # Issue number  e.g. ATB-2026-18
    hit = re.search(r'<strong>Issue:</strong>\s*(ATB-[\d-]+)', src)
    m['issue'] = hit.group(1).strip() if hit else f"ATB-{m['year']}-??"

    # Week of (from pill — use coverage range, not just end date)
    hit = re.search(r'<strong>Week of:</strong>\s*([^<]+)</div>', src)
    if hit:
        week_raw   = hit.group(1).strip()
        week_clean = decode_html(week_raw)
        week_clean = re.sub(r'\s*[–\-]+\s*', '–', week_clean)
        m['week_of']   = week_clean
        m['nav_label'] = f'Week of {week_clean}'
    else:
        m['week_of']   = slug
        m['nav_label'] = f'Week of {slug}'

    # Issue date display string (e.g. "11 JULY 2026")
    hit = re.search(
        r'<div class="meta-lbl">Issue Date</div><div class="meta-val">([^<]+)</div>', src)
    m['issue_date_display'] = hit.group(1).strip() if hit else \
        f'{m["day"]} {m["month_abbr"]} {m["year"]}'

    # Dominant theme
    hit = re.search(
        r'<div class="meta-lbl">Dominant Theme</div><div class="meta-val">([^<]+)</div>', src)
    m['dominant_theme'] = decode_html(hit.group(1)).title() if hit else ''

    # Threat banner
    hit = re.search(r'<div class="threat-label">([^<]+)</div>', src)
    m['threat_banner'] = decode_html(hit.group(1)) if hit else ''

    # Brief subtitle (centerpiece title, falls back to dominant theme)
    hit = re.search(r'<div class="centerpiece-title">([^<]+)</div>', src)
    m['brief_title'] = decode_html(hit.group(1)) if hit else m['dominant_theme']

    # Archive card summary — first 2 sentences of intro-deck
    hit = re.search(
        r'<div class="intro-deck">\s*<p><strong>[^<]*</strong>\s*(.*?)</p>', src, re.DOTALL)
    if hit:
        raw = decode_html(hit.group(0))
        raw = re.sub(r'^[^:]+:\s*', '', raw)
        sentences = re.split(r'(?<=[.!?])\s+', raw[:500])
        m['summary'] = ' '.join(sentences[:2])[:280]
    else:
        m['summary'] = m['threat_banner'][:280]

    # Display tags (up to 6, auto-detected from content)
    cl = src.lower()
    tag_map = [
        ('iran',         'Iran'),
        ('russia',       'Russia'),
        ('china',        'China'),
        ('north korea',  'North Korea'),
        ('dprk',         'North Korea'),
        ('ransomware',   'Ransomware'),
        ('cybercrime',   'Cybercrime'),
        ('maritime',     'Maritime'),
        ('water',        'Water'),
        ('ercot',        'ERCOT'),
        ('plc',          'OT/ICS'),
        (' ot ',         'OT/ICS'),
        ('ot/ics',       'OT/ICS'),
        ('energy',       'Energy'),
        ('finance',      'Finance'),
        ('healthcare',   'Healthcare'),
        ('dib',          'DIB'),
        (' ai ',         'AI'),
        ('data center',  'AI'),
        ('supply chain', 'Supply Chain'),
    ]
    seen, tags = set(), []
    for kw, label in tag_map:
        if kw in cl and label not in seen:
            tags.append(label)
            seen.add(label)
    tags.append('Texas')
    m['display_tags'] = tags[:6]

    # data-tags string for archive filter
    def slugify(t):
        return t.lower().replace('/', '-').replace(' ', '-')

    dt = ['latest', 'weekly']
    for t in tags:
        dt.append(slugify(t))
    for kw in ['energy', 'water', 'ot', 'iran', 'russia', 'irgc', 'plc', 'hormuz',
               'maritime', 'finance', 'healthcare', 'dib', 'ai', 'texas', 'ercot',
               'china', 'dprk', 'ransomware', 'supply-chain', 'infrastructure']:
        if kw.replace('-', ' ') in cl or kw in cl:
            if kw not in dt:
                dt.append(kw)
    m['data_tags'] = ' '.join(dict.fromkeys(dt))

    return m


# ── HTML transformations ───────────────────────────────────────────────────────

def normalize_nav_label(html: str, new_label: str) -> str:
    """Replace any 'Latest Issue, Week of …' nav text with the correct label."""
    return re.sub(
        r'Latest Issue,\s*Week of\s*[^<"]+',
        f'Latest Issue, {new_label}',
        html
    )


WARGAME_CTA_PRIMARY = '''  <!-- WARGAME CTA -->
  <div class="wargame-cta" style="margin:40px 0;background:rgba(212,160,64,.05);border:1px solid rgba(212,160,64,.28);border-left:4px solid #d4a040;padding:28px 32px;">
    <div style="font-family:'Share Tech Mono',monospace;font-size:.62rem;letter-spacing:.22em;text-transform:uppercase;color:#d4a040;margin-bottom:10px;">From Warning to Decision</div>
    <h3 style="font-family:'Rajdhani',sans-serif;font-size:1.3rem;font-weight:700;color:#ffffff;margin:0 0 10px;letter-spacing:.01em;">Would your leadership team act in time?</h3>
    <p style="color:#c4d8ee;font-size:.9rem;line-height:1.6;margin:0 0 16px;max-width:640px;">Reading the warning is one thing. Making the decision with incomplete information and the clock running is another.</p>
    <a href="../../crisis-wargame.html" style="font-family:'Share Tech Mono',monospace;font-size:.72rem;letter-spacing:.14em;color:#f0c870;text-decoration:none;border-bottom:1px solid rgba(212,160,64,.4);padding-bottom:2px;">EXECUTIVE CRISIS WARGAMING &rarr;</a>
  </div>

'''

WARGAME_CTA_CLOSING = '''  <!-- WARGAME CTA — CLOSING -->
  <div class="wargame-cta-closing" style="margin:36px 0 8px;padding-top:22px;border-top:1px solid rgba(212,160,64,.15);text-align:center;">
    <p style="color:#8aaece;font-size:.85rem;font-style:italic;margin:0 0 8px;">Test these decisions before they become real.</p>
    <a href="../../crisis-wargame.html" style="font-family:'Share Tech Mono',monospace;font-size:.68rem;letter-spacing:.12em;color:#d4a040;text-decoration:none;">EXECUTIVE CRISIS WARGAMING &rarr;</a>
  </div>

'''

ATB_COPYRIGHT_TEMPLATE = (
    '  <p class="atb-copyright" style="font-family:\'Share Tech Mono\',monospace;'
    'font-size:.72rem;letter-spacing:.04em;color:rgba(244,239,230,.56);'
    'text-align:center;margin:28px 0 4px;">&copy; {year} Liberty CTI LLC. All rights '
    'reserved. The Alamo Threat Brief and its original analysis may not be reproduced '
    'or redistributed without permission.</p>\n\n'
)


def insert_atb_copyright(src: str, year: str) -> str:
    """Insert the ATB-specific copyright/reproduction notice at the end of the
    brief's analytical content, just before the page-body container closes.
    Placed before the '/page-body' close (rather than before the closing
    WARGAME_CTA_CLOSING/footer block) so build_paywall_html's Section III cut
    excludes it from the free paywall preview, matching full-issue-only scope.
    """
    marker = '</div><!-- /page-body -->'
    if marker in src:
        return src.replace(marker, ATB_COPYRIGHT_TEMPLATE.format(year=year) + marker, 1)
    print('  WARNING: page-body closing marker not found — '
          'ATB copyright notice not inserted; add it manually.')
    return src


def insert_wargame_cta(src: str) -> str:
    """Insert the Executive Crisis Wargame CTA at the Decision-Impact -> Action
    transition (before 'Actions This Week'), and a quieter closing CTA at the
    end of the brief (before the site footer). Hrefs are written at atb/issues/
    depth (../../) — make_deep_html's generic href depth-fix rewrites them for
    the atb/YEAR/SLUG/ copy automatically.
    """
    html = src

    primary_anchor = None
    for marker in ('<!-- SECTION VII: ACTIONS THIS WEEK -->',
                   '<!-- SECTION VI: ACTIONS THIS WEEK -->'):
        if marker in html:
            primary_anchor = marker
            break
    if primary_anchor:
        html = html.replace(primary_anchor, WARGAME_CTA_PRIMARY + primary_anchor, 1)
    else:
        print('  WARNING: "Actions This Week" marker not found — '
              'primary wargame CTA not inserted; add it manually.')

    footer_marker = '<!-- LCTI:FOOTER:START -->'
    if footer_marker in html:
        html = html.replace(footer_marker, WARGAME_CTA_CLOSING + footer_marker, 1)
    else:
        print('  WARNING: Footer sentinel not found — '
              'closing wargame CTA not inserted; add it manually.')

    return html


def make_issues_html(src: str, meta: dict) -> str:
    """Transform source for atb/issues/ depth (bare logo → ../../)."""
    html = src
    html = html.replace(
        'src="liberty-cti-emblem.png" class="logo-img"',
        'src="../../liberty-cti-emblem.png" class="logo-img"'
    )
    html = normalize_nav_label(html, meta['nav_label'])
    return html


def make_deep_html(src: str, meta: dict) -> str:
    """Transform source for dist/atb/YEAR/SLUG/ depth (one level deeper)."""
    slug = meta['slug']
    year = meta['year']
    html = src
    html = html.replace(
        'src="liberty-cti-emblem.png" class="logo-img"',
        'src="../../../liberty-cti-emblem.png" class="logo-img"'
    )
    html = html.replace('href="../../', 'href="../../../')
    html = html.replace('src="../../',  'src="../../../')
    html = html.replace('href="../index.html"', 'href="../../index.html"')
    html = html.replace(f'href="{slug}.html"', f'href="/atb/{year}/{slug}/"')
    html = normalize_nav_label(html, meta['nav_label'])
    return html


def build_paywall_html(full_html: str, src_html: str) -> str:
    """Truncate at Section III and append paywall CTA."""
    cut_marker = '<!-- SECTION III'
    cut_pos = full_html.find(cut_marker)
    if cut_pos == -1:
        print('  WARNING: Section III marker not found — full content used without paywall.')
        return full_html

    roman_order = ['III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
    sections_behind = []
    for num, title in re.findall(
            r'<!-- SECTION (I{1,3}V?|V{1,3}I{0,3}|IX|X):\s*([^-\n]+?)\s*-->', src_html):
        if num.strip() in roman_order:
            clean = title.strip().rstrip('-').strip()
            sections_behind.append(f'{num.strip()} &nbsp;·&nbsp; {clean}')

    if not sections_behind:
        sections_behind = ['III &nbsp;·&nbsp; Additional Analysis',
                           'IV &nbsp;·&nbsp; Sector Implications',
                           'V  &nbsp;·&nbsp; Indicators &amp; Warnings']

    last_roman = sections_behind[-1].split(' ')[0]
    range_text  = f'III–{last_roman}'

    items_html = '\n'.join(
        f'      <li style="color:var(--text);font-size:.9rem;padding:8px 12px;'
        f'border:1px solid rgba(212,160,64,.15);background:rgba(212,160,64,.03);">{s}</li>'
        for s in sections_behind
    )

    paywall = f'''  <!-- PAYWALL -->
  <div style="margin:48px 0;background:rgba(212,160,64,.06);border:1px solid rgba(212,160,64,.3);border-left:5px solid var(--gold);padding:36px 40px;">
    <div style="font-family:'Share Tech Mono',monospace;font-size:.6rem;letter-spacing:.2em;color:var(--gold);margin-bottom:14px;text-transform:uppercase;">Free Registration Required</div>
    <h3 style="font-family:'Rajdhani',sans-serif;font-size:1.5rem;font-weight:700;color:var(--white);margin-bottom:12px;">Sections {range_text} are available after free registration</h3>
    <p style="color:var(--text-dim);font-size:.95rem;margin-bottom:20px;">The Alamo Threat Brief is free. Register once to continue with:</p>
    <ul style="list-style:none;padding:0;margin-bottom:28px;display:grid;gap:8px;">
{items_html}
    </ul>
    <a href="./full.html" style="display:inline-flex;align-items:center;gap:10px;background:var(--gold);color:var(--bg);font-family:'Rajdhani',sans-serif;font-size:1rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;text-decoration:none;padding:14px 28px;">Read Full Brief →</a>
    <p style="margin-top:16px;font-family:'Share Tech Mono',monospace;font-size:.65rem;color:var(--text-low);letter-spacing:.08em;">Free weekly Strategic Cyber Intelligence for Texas leaders. Registration required for full access.</p>
  </div>
'''

    pb_end = full_html.find('</div><!-- /page-body -->')
    return full_html[:cut_pos] + paywall + '\n' + full_html[pb_end:]


# ── Archive card builder ───────────────────────────────────────────────────────

def build_archive_card(meta: dict) -> str:
    slug      = meta['slug']
    year      = meta['year']
    tags_html = ''.join(f'<span class="tag">{t}</span>' for t in meta['display_tags'])
    summary   = meta['summary'].replace('"', '&quot;').replace("'", '&#39;')
    search    = (f"{meta['dominant_theme'].lower()} "
                 f"{meta['summary'][:150].lower()} "
                 f"{slug} {meta['issue'].lower()} {meta['data_tags']}")

    return (
        f'        <a class="issue-card" href="{year}/{slug}/index.html"'
        f' data-tags="{meta["data_tags"]}"'
        f' data-sector="all"'
        f' data-search="{search}">\n'
        f'          <div class="issue-date-block">\n'
        f'            <span class="issue-day">{meta["day"]}</span>\n'
        f'            <span class="issue-month">{meta["month_abbr"]}</span>\n'
        f'          </div>\n'
        f'          <div class="issue-main">\n'
        f'            <div class="issue-kicker">{meta["issue"]}'
        f'<span class="status-chip">Latest</span></div>\n'
        f'            <div class="issue-title">{meta["dominant_theme"]}</div>\n'
        f'            <div class="issue-summary">{summary}</div>\n'
        f'            <div class="issue-tags">{tags_html}</div>\n'
        f'          </div>\n'
        f'          <div class="issue-arrow">Open</div>\n'
        f'        </a>'
    )


# ── Archive updater ────────────────────────────────────────────────────────────

def update_archive(archive_path: str, meta: dict) -> None:
    c = open(archive_path, 'r', encoding='utf-8').read()

    # Remove Latest chip from current latest issue
    c = re.sub(r'<span class="status-chip">Latest</span>', '', c)

    # Increment the total-issues stat counter (first occurrence only)
    def inc_stat(mo):
        return f'<span class="stat-num">{int(mo.group(1)) + 1}</span>'
    c = re.sub(r'<span class="stat-num">(\d+)</span>', inc_stat, c, count=1)

    slug       = meta['slug']
    year       = meta['year']
    mon        = meta['month_num']
    month_full = meta['month_full']
    archive_id = f'archive-{year}-{mon:02d}'
    card_html  = build_archive_card(meta)

    if archive_id in c:
        # Month section exists — insert card at the top of month-issues
        c = re.sub(
            rf'(id="{archive_id}"[^>]*>.*?<div class="month-issues">)',
            lambda mo: mo.group(0) + '\n' + card_html,
            c, flags=re.DOTALL, count=1
        )
        # Increment rail count
        c = re.sub(
            rf'(href="#{archive_id}"[^>]*>.*?<strong>)(\d+)(</strong>)',
            lambda mo: mo.group(1) + str(int(mo.group(2)) + 1) + mo.group(3),
            c, flags=re.DOTALL, count=1
        )
        # Increment month-count span
        c = re.sub(
            rf'(id="{archive_id}"[^>]*>.*?<span class="month-count">)(\d+)( issue)',
            lambda mo: mo.group(1) + str(int(mo.group(2)) + 1) + mo.group(3),
            c, flags=re.DOTALL, count=1
        )
    else:
        # New month — find first existing month older than this one
        this_ym = year * 100 + mon
        existing = [
            (int(mo.group(1)) * 100 + int(mo.group(2)),
             f'archive-{mo.group(1)}-{mo.group(2)}')
            for mo in re.finditer(r'id="archive-(\d{4})-(\d{2})"', c)
        ]

        insert_before_id = None
        for ym, aid in sorted(existing, reverse=True):
            if ym < this_ym:
                insert_before_id = aid
                break

        new_rail = (
            f'        <a class="rail-link" href="#{archive_id}" data-month-link="{archive_id}">\n'
            f'          <span>{month_full} {year}</span>\n'
            f'          <strong>1</strong>\n'
            f'        </a>\n'
        )
        new_section = (
            f'      <section class="month-group" id="{archive_id}"'
            f' data-month="{month_full} {year}" data-year="{year}">\n'
            f'        <div class="month-head">\n'
            f'          <div>\n'
            f'            <span class="month-eyebrow">{year}</span>\n'
            f'            <h3>{month_full} {year}</h3>\n'
            f'          </div>\n'
            f'          <span class="month-count">1 issue</span>\n'
            f'        </div>\n'
            f'        <div class="month-issues">\n'
            f'{card_html}\n'
            f'        </div>\n'
            f'      </section>\n'
            f'      '
        )

        if insert_before_id:
            c = re.sub(
                rf'(\s*)(<a class="rail-link" href="#{insert_before_id}")',
                lambda mo: mo.group(1) + new_rail + mo.group(1) + mo.group(2).lstrip(),
                c, count=1
            )
            c = re.sub(
                rf'(<section class="month-group" id="{insert_before_id}")',
                new_section + r'\1',
                c, count=1
            )
        else:
            print(f'  WARNING: Could not find insertion point for {archive_id}')

    open(archive_path, 'w', encoding='utf-8').write(c)


# ── Homepage recent-issues updater ────────────────────────────────────────────

def build_homepage_card(meta: dict, from_root: bool = True) -> str:
    """
    Build a single lcti-issue-card anchor for the homepage Recent Issues strip.
    from_root=True  → href uses root-relative path  atb/2026/{slug}/index.html
    from_root=False → same (dist/index.html also lives at root depth)
    """
    slug  = meta['slug']
    year  = meta['year']
    href  = f'atb/{year}/{slug}/index.html'
    return (
        f'      <a class="lcti-issue-card" href="{href}">\n'
        f'        <span class="lcti-issue-kicker">'
        f'{meta["issue"]} &middot; {meta["week_of"]}</span>\n'
        f'        <h3 class="lcti-issue-title">{meta["dominant_theme"]}</h3>\n'
        f'        <span class="lcti-issue-link">Read the brief &rarr;</span>\n'
        f'      </a>'
    )


def update_homepage(homepage_path: str, meta: dict) -> None:
    """
    Replace the three cards inside LCTI:RECENT-ISSUES:START/END with:
      new card (latest) + the previous two cards (oldest dropped).
    The surrounding CSS and section wrapper are left intact.
    """
    c = open(homepage_path, 'r', encoding='utf-8').read()

    start_tag = '<!-- LCTI:RECENT-ISSUES:START -->'
    end_tag   = '<!-- LCTI:RECENT-ISSUES:END -->'
    start_pos = c.find(start_tag)
    end_pos   = c.find(end_tag)
    if start_pos == -1 or end_pos == -1:
        print(f'  WARNING: RECENT-ISSUES sentinels not found in {homepage_path}')
        return

    block = c[start_pos:end_pos + len(end_tag)]

    # Extract existing cards (grab the first 2 to keep; the 3rd is dropped)
    existing_cards = re.findall(
        r'(<a class="lcti-issue-card".*?</a>)', block, re.DOTALL
    )
    keep_cards = existing_cards[:2]  # previous #1 and #2 become #2 and #3

    new_card  = build_homepage_card(meta)
    cards_html = '\n'.join([new_card] + keep_cards)

    # Rebuild the grid section, preserving the outer structure and CSS
    # Find the grid div and replace its contents
    new_block = re.sub(
        r'(<div class="lcti-issues-grid">).*?(</div>\s*</div>\s*</section>)',
        lambda mo: mo.group(1) + '\n' + cards_html + '\n    ' + mo.group(2),
        block,
        flags=re.DOTALL,
        count=1
    )

    c = c[:start_pos] + new_block + c[end_pos + len(end_tag):]
    open(homepage_path, 'w', encoding='utf-8').write(c)


# ── Sitewide nav update ────────────────────────────────────────────────────────

def update_nav_sitewide(old_slug: str, new_slug: str,
                        new_nav_label: str, new_year: int,
                        skip_files: set) -> int:
    """Replace all nav hrefs and label text pointing at old_slug -> new_slug."""
    old_year = old_slug.split('-')[2]
    new_yr   = str(new_year)
    updated  = []

    for f in glob.glob('**/*.html', recursive=True):
        norm = os.path.normpath(f)
        if norm in skip_files:
            continue
        try:
            c = open(f, 'r', encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        orig = c

        # Six href formats
        c = c.replace(f'href="/atb/{old_year}/{old_slug}/"',
                      f'href="/atb/{new_yr}/{new_slug}/"')
        c = c.replace(f'href="../../issues/{old_slug}.html"',
                      f'href="../../issues/{new_slug}.html"')
        c = c.replace(f'href="../issues/{old_slug}.html"',
                      f'href="../issues/{new_slug}.html"')
        c = c.replace(f'href="issues/{old_slug}.html"',
                      f'href="issues/{new_slug}.html"')
        c = c.replace(f'href="{old_slug}.html"',
                      f'href="{new_slug}.html"')
        c = c.replace(f'href="atb/issues/{old_slug}.html"',
                      f'href="atb/issues/{new_slug}.html"')

        # Nav label text
        c = normalize_nav_label(c, new_nav_label)

        # JS alias
        c = c.replace(f"'{old_slug}.html']", f"'{new_slug}.html']")

        if c != orig:
            open(f, 'w', encoding='utf-8').write(c)
            updated.append(f)

    return len(updated)


# ── Current latest slug ────────────────────────────────────────────────────────

def find_current_latest_slug(archive_path: str) -> str | None:
    """Return the slug of the issue currently marked Latest in the archive."""
    c = open(archive_path, 'r', encoding='utf-8').read()
    mo = re.search(
        r'href="(\d{4}/([\d-]+)/index\.html)"[^>]*>.*?<span class="status-chip">Latest</span>',
        c, re.DOTALL
    )
    return mo.group(2) if mo else None


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Publish a new ATB issue to the Liberty CTI site.')
    parser.add_argument('source', help='Path to source MM-DD-YYYY.html file')
    parser.add_argument('--no-push',   action='store_true', help='Skip git push')
    parser.add_argument('--no-deploy', action='store_true', help='Skip wrangler deploy')
    args = parser.parse_args()

    src_path = Path(args.source)
    if not src_path.exists():
        sys.exit(f'ERROR: Source file not found: {src_path}')

    slug = src_path.stem
    if not re.match(r'^\d{2}-\d{2}-\d{4}$', slug):
        sys.exit(f'ERROR: Filename must be MM-DD-YYYY.html, got: {src_path.name}')

    src = src_path.read_text(encoding='utf-8')
    src = insert_atb_copyright(src, slug[-4:])
    src = insert_wargame_cta(src)

    print(f'\n=== Publishing {slug} ===')

    # 1. Extract metadata
    meta = extract_meta(src, slug)
    print(f'  Issue     : {meta["issue"]}')
    print(f'  Theme     : {meta["dominant_theme"]}')
    print(f'  Week of   : {meta["week_of"]}')
    print(f'  Nav label : {meta["nav_label"]}')

    year = meta['year']

    # 2. Find current latest (for nav replacement)
    archive_root = REPO / 'atb' / 'index.html'
    old_slug = find_current_latest_slug(str(archive_root))
    print(f'  Replacing : {old_slug} -> {slug}')

    # 3. Build transformed HTML variants
    issues_html = make_issues_html(src, meta)
    deep_html   = make_deep_html(src, meta)
    index_html  = build_paywall_html(deep_html, src)

    # 4. Write issue files
    def write(path, content):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content, encoding='utf-8')
        print(f'  Wrote: {path}')

    issues_dir  = REPO / 'atb' / 'issues'
    dist_issues = REPO / 'dist' / 'atb' / 'issues'
    dist_brief  = REPO / 'dist' / 'atb' / str(year) / slug

    write(issues_dir  / f'{slug}.html', issues_html)
    write(dist_issues / f'{slug}.html', issues_html)
    write(dist_brief  / 'full.html',    deep_html)
    write(dist_brief  / 'index.html',   index_html)

    meta_json = {
        'issue':            meta['issue'],
        'publish_date':     f'{meta["day"]} {MONTHS_ABBR[meta["month_num"]].capitalize()} {year}',
        'publish_date_iso': f'{year}-{meta["month_num"]:02d}-{meta["day"]:02d}',
        'week_of':          meta['week_of'],
        'year':             year,
        'slug':             slug,
        'dominant_theme':   meta['dominant_theme'],
        'threat_banner':    meta['threat_banner'],
        'preview_url':      f'/atb/{year}/{slug}/',
        'full_url':         f'/atb/{year}/{slug}/full.html',
    }
    write(dist_brief / 'meta.json',
          json.dumps(meta_json, indent=4, ensure_ascii=False))

    # 5. Update archives
    print('  Updating archives...')
    update_archive(str(REPO / 'atb'  / 'index.html'), meta)
    update_archive(str(REPO / 'dist' / 'atb' / 'index.html'), meta)

    # 6. Update homepage Recent Issues strip (root and dist mirror)
    print('  Updating homepage recent-issues strip...')
    update_homepage(str(REPO / 'index.html'), meta)
    update_homepage(str(REPO / 'dist' / 'index.html'), meta)

    # 7. Update sitewide nav
    # Skip the new issue files (already have correct nav).
    # Do NOT skip archives or homepages — they were written above with old nav.
    skip = {os.path.normpath(str(p)) for p in [
        issues_dir  / f'{slug}.html',
        dist_issues / f'{slug}.html',
        dist_brief  / 'full.html',
        dist_brief  / 'index.html',
    ]}
    if old_slug:
        print('  Updating nav sitewide...')
        n = update_nav_sitewide(old_slug, slug, meta['nav_label'], year, skip)
        print(f'  Nav updated in {n} files')
    else:
        print('  WARNING: No previous latest found — skipping sitewide nav update')

    # 8. Git commit
    msg = (
        f'Publish {meta["issue"]} - {meta["dominant_theme"]} ({meta["issue_date_display"]})\n\n'
        f'- Add atb/issues/{slug}.html and dist mirror\n'
        f'- Add dist/atb/{year}/{slug}/ (full.html, index.html, meta.json)\n'
        f'- Update archive: new card, Latest chip, stat counter\n'
        f'- Update homepage: Recent Issues strip rotated to latest 3\n'
        f'- Update nav sitewide: Latest Issue, {meta["nav_label"]}\n\n'
        f'Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>'
    )

    print('  Staging files...')
    subprocess.run(['git', 'add',
                    f'atb/issues/{slug}.html',
                    f'dist/atb/issues/{slug}.html',
                    f'dist/atb/{year}/{slug}/',
                    'atb/index.html',
                    'dist/atb/index.html',
                    'index.html',
                    'dist/index.html'],
                   cwd=REPO, check=True)
    subprocess.run(['git', 'add', '-u'], cwd=REPO, check=True)

    # Unstage spurious .bak deletions from OneDrive sync
    bak_result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=D'],
        cwd=REPO, capture_output=True, text=True
    )
    bak_files = [f for f in bak_result.stdout.splitlines() if f.endswith('.bak')]
    if bak_files:
        subprocess.run(['git', 'restore', '--staged'] + bak_files, cwd=REPO, check=True)
        print(f'  Unstaged {len(bak_files)} spurious .bak deletions')

    subprocess.run(['git', 'commit', '-m', msg], cwd=REPO, check=True)
    print('  Committed.')

    if not args.no_push:
        subprocess.run(['git', 'push'], cwd=REPO, check=True)
        print('  Pushed.')
    else:
        print('  Skipped push (--no-push).')

    if not args.no_deploy:
        result = subprocess.run(
            'npx wrangler deploy', cwd=REPO, shell=True,
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        print(result.stdout[-800:] if result.stdout else '')
        if result.returncode != 0:
            print('DEPLOY ERROR:', result.stderr[-400:])
        else:
            print('  Deployed.')
    else:
        print('  Skipped deploy (--no-deploy).')

    print(f'\n=== Done: {meta["issue"]} is live ===\n')


if __name__ == '__main__':
    main()
