#!/usr/bin/env python3
"""
sync_components_auto_atb_v3.py — Liberty CTI
-----------------------------------------
Injects the canonical nav and footer into every HTML page on the site.

This version automatically populates the Alamo Threat Brief (ATB) dropdown
based on files in the protected ATB issue directory that match the naming convention:

    atb/issues/MM-DD-YYYY.html

Examples:
    03-16-2026.html
    03-23-2026.html
    03-30-2026.html

Behavior
--------
- The newest dated file under /atb/issues/ becomes the ATB "Latest Issue" link.
- Older dated files are not listed individually in the nav dropdown.
- The ATB dropdown keeps only:
    * Latest Issue
    * Archive
- "Alamo Threat Brief" in the top nav stays red.
- The dropdown links are gold, except "Archive" which is a darker red hue.
- The footer also auto-links the newest issue as the ATB entry.
- Active-link highlighting works for:
    * alamo-threat-brief.html
    * atb-archive.html
    * any dated ATB issue like 03-16-2026.html

USAGE
-----
    python sync_components_auto_atb.py                  # dry-run preview
    python sync_components_auto_atb.py --write          # apply changes
    python sync_components_auto_atb.py --write --page index.html
    python sync_components_auto_atb.py --add-sentinels --write

REQUIREMENTS
------------
    Python 3.8+  (no third-party packages needed)

IMPORTANT
---------
Each page must contain sentinel comments for managed sections:

    <!-- LCTI:NAV:START -->    ...nav...    <!-- LCTI:NAV:END -->
    <!-- LCTI:FOOTER:START --> ...footer... <!-- LCTI:FOOTER:END -->
"""

from __future__ import annotations

import re
import sys
import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SITE_ROOT = Path(__file__).parent

SKIP_FILES = {
    "nav-component.html",
}

SKIP_DIRS = {
    ".git",
    ".next",
    "dist",
    "node_modules",
    "out",
}

NAV_START    = "<!-- LCTI:NAV:START -->"
NAV_END      = "<!-- LCTI:NAV:END -->"
FOOTER_START = "<!-- LCTI:FOOTER:START -->"
FOOTER_END   = "<!-- LCTI:FOOTER:END -->"

NAV_PATTERN = re.compile(
    r"<!-- LCTI:NAV:START -->.*?<!-- LCTI:NAV:END -->",
    re.DOTALL
)
FOOTER_PATTERN = re.compile(
    r"<!-- LCTI:FOOTER:START -->.*?<!-- LCTI:FOOTER:END -->",
    re.DOTALL
)

DATED_ATB_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-(\d{4})\.html$", re.IGNORECASE)
ISSUE_ID_ATB_RE = re.compile(r"^ATB-\d{4}-\d+\.html$", re.IGNORECASE)


def find_html_files(root: Path) -> list[Path]:
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            dirname for dirname in dirnames
            if dirname not in SKIP_DIRS and not dirname.lower().startswith("dist ")
        ]
        for filename in sorted(filenames):
            if not filename.lower().endswith(".html"):
                continue
            p = Path(dirpath) / filename
            rel_path = p.relative_to(root)
            rel = str(rel_path)
            if len(rel_path.parts) == 1 and (
                p.name.lower() == "atb-archive.html"
                or DATED_ATB_RE.match(p.name)
                or ISSUE_ID_ATB_RE.match(p.name)
            ):
                continue
            if any(rel == skip or p.name == skip for skip in SKIP_FILES):
                continue
            results.append(p)
    return results


def find_dated_atb_files(root: Path) -> list[Path]:
    """Find dated ATB files in the known source locations.

    Returns root-relative paths so pages in subfolders get correct links.
    """
    chosen: dict[str, tuple[int, datetime, Path]] = {}
    candidate_dirs = [
        root / "atb" / "issues",
        root / "Intel Production" / "liberty_cti_briefs",
        root / "April 2026",
    ]
    for priority, directory in enumerate(candidate_dirs):
        if not directory.exists():
            continue
        for p in sorted(directory.glob("*.html")):
            if p.name in SKIP_FILES or not DATED_ATB_RE.match(p.name):
                continue
            try:
                dt = datetime.strptime(p.stem, "%m-%d-%Y")
                rel = p.relative_to(root)
                current = chosen.get(p.name)
                if current is None or priority < current[0]:
                    chosen[p.name] = (priority, dt, rel)
            except ValueError:
                continue
    dated = sorted(chosen.values(), key=lambda item: item[1], reverse=True)
    return [path for _, _, path in dated]




def format_week_label(filename: str) -> str:
    try:
        stem = Path(filename).stem
        dt = datetime.strptime(stem, "%m-%d-%Y")
        return dt.strftime("Week of %b %d, %Y").replace(" 0", " ")
    except ValueError:
        return filename.replace(".html", "")


def relative_href(current_page: Path, target: str | Path, root: Path) -> str:
    """Build a browser-friendly link relative to the current page."""
    target_text = str(target).replace("\\", "/")
    if target_text.startswith(("http://", "https://", "mailto:", "tel:", "#")):
        return target_text

    target_path = Path(target_text.lstrip("/"))
    if target_path.is_absolute():
        try:
            target_path = target_path.resolve().relative_to(root.resolve())
        except ValueError:
            return target_path.as_posix()

    target_abs = (root / target_path).resolve()
    current_dir = current_page.resolve().parent
    rel = os.path.relpath(target_abs, current_dir).replace("\\", "/")
    if rel == "index.html" and "/" in target_text.strip("/"):
        return "./index.html"
    return rel


def latest_issue_href_for_page(latest_issue_file: Path | None, current_page: Path, root: Path) -> str:
    """Use the protected ATB issue path for public site pages."""
    if not latest_issue_file:
        return relative_href(current_page, "alamo-threat-brief.html", root)

    return relative_href(current_page, latest_issue_file, root)


def relativize_component_links(html: str, current_page: Path, root: Path) -> str:
    site_targets = [
        "index.html",
        "about.html",
        "luis-maldonado.html",
        "angie-maldonado.html",
        "decision-support.html",
        "alamo-threat-brief.html",
        "texas-threat-outlook.html",
        "sector-assessments.html",
        "atb-archive.html",
        "texas-focus.html",
        "energy-ercot.html",
        "defense-dib.html",
        "financial.html",
        "healthcare.html",
        "Energy_data_AI.html",
        "briefing-request.html",
        "contact.html",
        "liberty-cti-emblem.png",
    ]
    for target in site_targets:
        rel = relative_href(current_page, target, root)
        html = html.replace(f'href="{target}"', f'href="{rel}"')
        html = html.replace(f'href="/{target}"', f'href="{rel}"')
        html = html.replace(f"href='{target}'", f"href='{rel}'")
        html = html.replace(f"href='/{target}'", f"href='{rel}'")
        html = html.replace(f'src="{target}"', f'src="{rel}"')
        html = html.replace(f'src="/{target}"', f'src="{rel}"')
        html = html.replace(f"src='{target}'", f"src='{rel}'")
        html = html.replace(f"src='/{target}'", f"src='{rel}'")
    return html


def sync_latest_issue_links(content: str, latest_issue_file: Path | None, current_page: Path, root: Path) -> tuple[str, bool]:
    """Keep content CTAs that say "Latest Issue" or "Latest Brief" pointed at the newest dated ATB."""
    if not latest_issue_file:
        return content, False

    latest_href = latest_issue_href_for_page(latest_issue_file, current_page, root)

    def replace_latest_href(match: re.Match) -> str:
        tag = match.group(0)
        inner = match.group(5)
        visible_text = re.sub(r"<[^>]+>", " ", inner)
        normalized_text = visible_text.lower()
        if (
            "latest issue" not in normalized_text
            and "latest brief" not in normalized_text
            and "latest alamo threat brief" not in normalized_text
        ):
            return tag
        return re.sub(r'href=(["\'])(.*?)\1', f'href="{latest_href}"', tag, count=1, flags=re.IGNORECASE)

    updated = re.sub(
        r'<a\b([^>]*)href=(["\'])(.*?)\2([^>]*)>(.*?)</a>',
        replace_latest_href,
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return updated, updated != content


def build_nav_html(latest_issue_file: Path | None, current_page: Path, root: Path) -> str:
    latest_issue_href = latest_issue_href_for_page(latest_issue_file, current_page, root)
    archive_href = relative_href(current_page, "atb/index.html", root)
    latest_issue_label = f"Latest Issue, {format_week_label(str(latest_issue_file))}" if latest_issue_file else "Latest Issue"

    aliases = [f"'{latest_issue_file.name.lower()}'"] if latest_issue_file else []
    alias_block = ", ".join(aliases)

    html = f"""\
<!-- LCTI:NAV:START -->
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=Instrument+Sans:wght@300;400;500;600&display=swap');
:root{{--nav-h:68px}}
.lcti-nav{{position:fixed;top:0;left:0;right:0;z-index:1000;height:var(--nav-h);display:flex;align-items:center;justify-content:space-between;padding:0 2rem;background:rgba(8,12,16,.97);border-bottom:1px solid rgba(184,150,62,.2);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}}
.lcti-logo{{display:flex;align-items:center;gap:.6rem;text-decoration:none;flex-shrink:0}}
.lcti-logo-emblem{{width:36px;height:36px;object-fit:contain;flex-shrink:0}}
.lcti-logo-wordmark{{font-family:'Playfair Display',serif;font-size:1.125rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#f4efe6;white-space:nowrap;flex-shrink:0}}
.lcti-logo-wordmark span{{color:#b8963e}}
.lcti-logo-rule{{width:1px;height:24px;background:rgba(184,150,62,.3);flex-shrink:0}}
.lcti-logo-slogan{{font-family:'Instrument Sans',sans-serif;font-size:.73rem;letter-spacing:.16em;text-transform:uppercase;color:#b8963e;opacity:.85;line-height:1.45;white-space:normal;max-width:150px}}
.lcti-links{{display:flex;align-items:center;gap:.1rem;list-style:none}}
.lcti-links>li>a,.lcti-links>li>.lcti-drop-toggle{{font-family:'Instrument Sans',sans-serif;font-size:.8125rem;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:rgba(244,239,230,.55);text-decoration:none;padding:.38rem .55rem;border-radius:2px;transition:color .22s;display:flex;align-items:center;gap:.3rem;cursor:pointer;background:none;border:none;white-space:nowrap}}
.lcti-links>li>a:hover,.lcti-links>li>.lcti-drop-toggle:hover,.lcti-links>li>a.active,.lcti-links>li.active>.lcti-drop-toggle{{color:#b8963e}}
.lcti-links>li>a.lcti-atb-link,.lcti-links>li>.lcti-drop-toggle.lcti-atb-link,
.lcti-mobile-menu a.lcti-atb-link,.lcti-mobile-menu .m-group-label.lcti-atb-link{{color:#c0392b !important}}
.lcti-links>li>a.lcti-atb-link:hover,.lcti-links>li>.lcti-drop-toggle.lcti-atb-link:hover,
.lcti-links>li.active>.lcti-drop-toggle.lcti-atb-link,.lcti-links>li>a.lcti-atb-link.active,
.lcti-mobile-menu a.lcti-atb-link:hover{{color:#d6554a !important}}
.lcti-drop-toggle::after{{content:'';display:inline-block;width:0;height:0;border-left:3px solid transparent;border-right:3px solid transparent;border-top:4px solid currentColor;opacity:.55;transition:transform .2s;flex-shrink:0}}
.lcti-drop-item.open>.lcti-drop-toggle::after{{transform:rotate(180deg)}}
.lcti-drop-item{{position:relative}}
.lcti-drop-panel{{display:none;position:absolute;top:calc(100% + 8px);left:0;min-width:260px;background:#080c10;border:1px solid rgba(184,150,62,.2);border-top:2px solid #b8963e;padding:.4rem 0;z-index:200;box-shadow:0 12px 32px rgba(0,0,0,.9)}}
.lcti-drop-item.open .lcti-drop-panel{{display:block}}
.lcti-drop-panel a{{display:block;font-family:'Instrument Sans',sans-serif;font-size:.825rem;font-weight:400;letter-spacing:.1em;text-transform:uppercase;color:rgba(244,239,230,.55);text-decoration:none;padding:.6rem 1.1rem;transition:color .18s,background .18s;border-left:2px solid transparent}}
.lcti-drop-panel a:hover{{color:#b8963e;background:rgba(184,150,62,.07);border-left-color:#b8963e}}
.lcti-drop-panel .drop-label{{font-family:'Instrument Sans',sans-serif;font-size:.625rem;letter-spacing:.22em;text-transform:uppercase;color:#b8963e;opacity:.45;padding:.65rem 1.1rem .25rem;pointer-events:none;display:block}}
.lcti-drop-panel .drop-divider{{height:1px;background:rgba(184,150,62,.2);margin:.3rem 0}}
.lcti-drop-panel a.lcti-archive-link{{color:#8f3a32 !important}}
.lcti-drop-panel a.lcti-archive-link:hover{{color:#a94a40 !important;background:rgba(143,58,50,.08);border-left-color:#8f3a32}}
.lcti-cta{{font-family:'Instrument Sans',sans-serif;font-size:.775rem;font-weight:600;letter-spacing:.13em;text-transform:uppercase;color:#b8963e !important;border:1px solid #b8963e;padding:.42rem .9rem !important;border-radius:2px;transition:background .22s,color .22s;text-decoration:none;white-space:nowrap;margin-left:.35rem}}
.lcti-cta:hover{{background:#b8963e !important;color:#080c10 !important}}
.lcti-burger{{display:none;flex-direction:column;gap:5px;cursor:pointer;padding:4px;background:none;border:none}}
.lcti-burger span{{display:block;width:22px;height:2px;background:#f4efe6;transition:transform .25s,opacity .25s;transform-origin:center}}
.lcti-burger.open span:nth-child(1){{transform:translateY(7px) rotate(45deg)}}
.lcti-burger.open span:nth-child(2){{opacity:0}}
.lcti-burger.open span:nth-child(3){{transform:translateY(-7px) rotate(-45deg)}}
.lcti-mobile-menu{{display:none;position:fixed;top:var(--nav-h);left:0;right:0;background:#080c10;border-bottom:1px solid rgba(184,150,62,.2);padding:1rem 0 1.5rem;z-index:999;max-height:calc(100vh - var(--nav-h));overflow-y:auto}}
.lcti-mobile-menu.open{{display:block}}
.lcti-mobile-menu a{{display:block;font-size:.9rem;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:rgba(244,239,230,.6);text-decoration:none;padding:.8rem 2rem;transition:color .18s}}
.lcti-mobile-menu a:hover{{color:#b8963e}}
.lcti-mobile-menu .m-group-label{{font-family:'Instrument Sans',sans-serif;font-size:.675rem;letter-spacing:.24em;text-transform:uppercase;color:#b8963e;opacity:.5;padding:1.05rem 2rem .35rem;display:block;pointer-events:none}}
.lcti-mobile-menu .m-sub a{{padding-left:3rem;font-size:.8375rem;opacity:.85}}
.lcti-mobile-menu a.lcti-archive-link{{color:#8f3a32 !important}}
.lcti-mobile-menu a.lcti-archive-link:hover{{color:#a94a40 !important}}
.lcti-mobile-menu .m-cta-wrap{{padding:1rem 2rem 0}}
.lcti-mobile-menu .m-cta{{display:block;text-align:center;font-size:.875rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:#b8963e;border:1px solid #b8963e;padding:.75rem 1.5rem;text-decoration:none;transition:background .2s,color .2s}}
.lcti-mobile-menu .m-cta:hover{{background:#b8963e;color:#080c10}}
@media(max-width:960px){{.lcti-links{{display:none}}.lcti-burger{{display:flex}}}}
@media(max-width:400px){{.lcti-logo-rule,.lcti-logo-slogan{{display:none}}}}
</style>

<nav class="lcti-nav" role="navigation" aria-label="Main navigation">
  <a href="index.html" class="lcti-logo" aria-label="Liberty CTI Home">
<img src="liberty-cti-emblem.png" alt="Liberty CTI" class="lcti-logo-emblem" decoding="async" width="489" height="512">
    <div class="lcti-logo-wordmark">Liberty <span>CTI</span></div>
    <div class="lcti-logo-rule"></div>
    <div class="lcti-logo-slogan">Decision intelligence<br>for Texas leaders.</div>
  </a>

  <ul class="lcti-links" role="list">
    <li><a href="index.html">Home</a></li>

    <li class="lcti-drop-item">
      <button class="lcti-drop-toggle" aria-haspopup="true" aria-expanded="false">About</button>
      <div class="lcti-drop-panel" role="menu">
        <a href="about.html" role="menuitem">Company Overview</a>
        <div class="drop-divider"></div>
        <span class="drop-label">Founders</span>
        <a href="luis-maldonado.html" role="menuitem">Lou Maldonado</a>
        <a href="angie-maldonado.html" role="menuitem">Angie Maldonado</a>
      </div>
    </li>

    <li class="lcti-drop-item">
      <button class="lcti-drop-toggle" aria-haspopup="true" aria-expanded="false">Products</button>
      <div class="lcti-drop-panel" role="menu">
        <a href="decision-support.html" role="menuitem">Products &amp; Services</a>
        <div class="drop-divider"></div>
        <span class="drop-label">Core Products</span>
        <a href="alamo-threat-brief.html" role="menuitem">Alamo Threat Brief</a>
        <a href="texas-threat-outlook.html" role="menuitem">Texas Threat Outlook</a>
        <a href="sector-assessments.html" role="menuitem">Sector Assessments</a>
      </div>
    </li>

    <li class="lcti-drop-item">
      <button class="lcti-drop-toggle lcti-atb-link" aria-haspopup="true" aria-expanded="false">Alamo Threat Brief</button>
      <div class="lcti-drop-panel" role="menu">
        <span class="drop-label">Latest Issue</span>
        <a href="{latest_issue_href}" role="menuitem">{latest_issue_label}</a>
        <div class="drop-divider"></div>
        <a href="{archive_href}" role="menuitem" class="lcti-archive-link">Archive</a>
      </div>
    </li>

    <li class="lcti-drop-item">
      <button class="lcti-drop-toggle" aria-haspopup="true" aria-expanded="false">Texas Focus</button>
      <div class="lcti-drop-panel" role="menu">
        <a href="texas-focus.html" role="menuitem">Texas Overview</a>
        <div class="drop-divider"></div>
        <span class="drop-label">Priority Sectors</span>
        <a href="energy-ercot.html" role="menuitem">Energy &amp; ERCOT</a>
        <a href="defense-dib.html" role="menuitem">Defense Industrial Base</a>
        <a href="financial.html" role="menuitem">Financial Services</a>
        <a href="healthcare.html" role="menuitem">Healthcare</a>
        <div class="drop-divider"></div>
        <a href="Energy_data_AI.html" role="menuitem">AI Convergence</a>
      </div>
    </li>

    <li><a href="briefing-request.html" class="lcti-cta">Request an Executive Briefing</a></li>
  </ul>

  <button class="lcti-burger" id="lcti-burger" aria-label="Toggle mobile menu" aria-expanded="false">
    <span></span><span></span><span></span>
  </button>
</nav>

<div class="lcti-mobile-menu" id="lcti-mobile-menu" role="dialog" aria-label="Mobile navigation">
  <a href="index.html">Home</a>

  <span class="m-group-label">About</span>
  <div class="m-sub">
    <a href="about.html">Company Overview</a>
    <a href="luis-maldonado.html">Lou Maldonado</a>
    <a href="angie-maldonado.html">Angie Maldonado</a>
  </div>

  <span class="m-group-label">Products</span>
  <div class="m-sub">
    <a href="decision-support.html">Products &amp; Services</a>
    <a href="alamo-threat-brief.html">Alamo Threat Brief</a>
    <a href="texas-threat-outlook.html">Texas Threat Outlook</a>
    <a href="sector-assessments.html">Sector Assessments</a>
  </div>

  <span class="m-group-label lcti-atb-link">Alamo Threat Brief</span>
  <div class="m-sub">
    <a href="{latest_issue_href}">{latest_issue_label}</a>
    <a href="{archive_href}" class="lcti-archive-link">Archive</a>
  </div>

  <span class="m-group-label">Texas Focus</span>
  <div class="m-sub">
    <a href="texas-focus.html">Texas Overview</a>
    <a href="energy-ercot.html">Energy &amp; ERCOT</a>
    <a href="defense-dib.html">Defense Industrial Base</a>
    <a href="financial.html">Financial Services</a>
    <a href="healthcare.html">Healthcare</a>
    <a href="Energy_data_AI.html">AI Convergence</a>
  </div>

  <div class="m-cta-wrap">
    <a href="briefing-request.html" class="m-cta">Request an Executive Briefing</a>
  </div>
</div>

<script>
(function(){{
  var burger=document.getElementById('lcti-burger');
  var menu=document.getElementById('lcti-mobile-menu');
  if(burger&&menu){{burger.addEventListener('click',function(){{var o=menu.classList.toggle('open');burger.classList.toggle('open',o);burger.setAttribute('aria-expanded',String(o))}});}}
  var drops=document.querySelectorAll('.lcti-drop-item');
  drops.forEach(function(item){{
    var toggle=item.querySelector('.lcti-drop-toggle');
    if(!toggle)return;
    toggle.addEventListener('click',function(e){{
      e.stopPropagation();
      var o=item.classList.toggle('open');
      toggle.setAttribute('aria-expanded',String(o));
      drops.forEach(function(other){{if(other!==item){{other.classList.remove('open');var t=other.querySelector('.lcti-drop-toggle');if(t)t.setAttribute('aria-expanded','false');}}}});
    }});
  }});
  document.addEventListener('click',function(){{drops.forEach(function(item){{item.classList.remove('open');var t=item.querySelector('.lcti-drop-toggle');if(t)t.setAttribute('aria-expanded','false');}});}});

  var path=(window.location.pathname.split('/').pop()||'index.html').toLowerCase();
  var aliases={{
    'alamo-threat-brief.html':[{alias_block}],
    'decision-support.html':['texas-threat-outlook.html','sector-assessments.html']
  }};
  document.querySelectorAll('.lcti-links a,.lcti-mobile-menu a').forEach(function(link){{
    var href=((link.getAttribute('href')||'').split('/').pop()||'').toLowerCase();
    if(href===path || (aliases[href] && aliases[href].indexOf(path)!==-1)){{
      link.classList.add('active');
      var p=link.closest('.lcti-drop-item');
      if(p)p.classList.add('active');
    }}
  }});

  window.addEventListener('resize',function(){{if(window.innerWidth>960){{menu&&menu.classList.remove('open');burger&&burger.classList.remove('open');}}}});
}})();
</script>
<!-- LCTI:NAV:END -->"""
    return relativize_component_links(html, current_page, root)


def build_footer_html(latest_issue_file: Path | None, current_page: Path, root: Path) -> str:
    latest_issue_href = latest_issue_href_for_page(latest_issue_file, current_page, root)
    html = f"""\
<!-- LCTI:FOOTER:START -->
<style>
.lcti-footer{{background:#080c10;border-top:1px solid rgba(184,150,62,0.2);padding:4rem 2.5rem 2rem;font-family:'Instrument Sans',sans-serif}}
.lcti-footer-inner{{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;gap:3rem}}
.lcti-footer-brand-row{{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem}}
.lcti-footer-emblem{{width:36px;height:36px;object-fit:contain}}
.lcti-footer-brand-name{{font-family:'Playfair Display',serif;font-size:1rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#f4efe6}}
.lcti-footer-brand-name span{{color:#b8963e}}
.lcti-footer-tagline{{font-size:1rem;font-weight:500;color:rgba(244,239,230,.78);line-height:1.72;max-width:280px;margin-bottom:1.25rem}}
.lcti-footer-slogan{{font-family:'Instrument Sans',sans-serif;font-size:.94rem;font-weight:500;letter-spacing:.09em;text-transform:uppercase;color:#d4af62;opacity:1}}
.lcti-footer-col-title{{font-family:'Instrument Sans',sans-serif;font-size:.94rem;font-weight:500;letter-spacing:.09em;text-transform:uppercase;color:#d4af62;opacity:1;margin-bottom:.9rem;display:block}}
.lcti-footer-links{{list-style:none}}
.lcti-footer-links li{{margin-bottom:.45rem}}
.lcti-footer-links a{{font-size:.98rem;font-weight:500;line-height:1.55;color:rgba(244,239,230,.74);text-decoration:none;transition:color .2s}}
.lcti-footer-links a:hover{{color:#b8963e}}
.lcti-footer-links a.lcti-atb-link{{color:#d6554a;font-weight:600}}
.lcti-footer-links a.lcti-atb-link:hover{{color:#d6554a}}
.lcti-footer-bottom{{max-width:1100px;margin:3rem auto 0;border-top:1px solid rgba(184,150,62,0.12);padding-top:1.25rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem}}
.lcti-footer-copy{{font-family:'Instrument Sans',sans-serif;font-size:.86rem;font-weight:600;letter-spacing:.04em;color:rgba(244,239,230,.56)}}
@media(max-width:860px){{.lcti-footer-inner{{grid-template-columns:1fr 1fr;gap:2rem}}}}
@media(max-width:520px){{.lcti-footer-inner{{grid-template-columns:1fr}}.lcti-footer{{padding:2.5rem 1.25rem 1.5rem}}.lcti-footer-bottom{{flex-direction:column;align-items:flex-start}}}}
</style>

<footer class="lcti-footer" role="contentinfo">
  <div class="lcti-footer-inner">
    <div>
      <div class="lcti-footer-brand-row">
        <img src="liberty-cti-emblem.png" alt="Liberty CTI" class="lcti-footer-emblem" decoding="async" loading="lazy" width="489" height="512">
        <div class="lcti-footer-brand-name">Liberty <span>CTI</span></div>
      </div>
      <p class="lcti-footer-tagline">Executive decision intelligence for Texas critical infrastructure.</p>
      <div class="lcti-footer-slogan">Know what changed. Decide this week.</div>
    </div>

    <div>
      <span class="lcti-footer-col-title">Products</span>
      <ul class="lcti-footer-links">
        <li><a href="decision-support.html">Products &amp; Services</a></li>
        <li><a href="/alamo-threat-brief.html" class="lcti-atb-link">Alamo Threat Brief</a></li>
        <li><a href="texas-threat-outlook.html">Texas Threat Outlook</a></li>
        <li><a href="sector-assessments.html">Sector Assessments</a></li>
      </ul>
    </div>

    <div>
      <span class="lcti-footer-col-title">Texas Focus</span>
      <ul class="lcti-footer-links">
        <li><a href="texas-focus.html">Texas Overview</a></li>
        <li><a href="energy-ercot.html">Energy &amp; ERCOT</a></li>
        <li><a href="defense-dib.html">Defense Industrial Base</a></li>
        <li><a href="financial.html">Financial Services</a></li>
        <li><a href="healthcare.html">Healthcare</a></li>
        <li><a href="Energy_data_AI.html">AI Convergence</a></li>
      </ul>
    </div>

    <div>
      <span class="lcti-footer-col-title">Connect</span>
      <ul class="lcti-footer-links">
        <li><a href="briefing-request.html">Request an Executive Briefing</a></li>
        <li><a href="briefing-request.html">Discuss a Retainer</a></li>
        <li><a href="contact.html">Contact</a></li>
        <li><a href="mailto:intel@libertycti.com">intel@libertycti.com</a></li>
        <li><a href="https://libertycti.substack.com" target="_blank" rel="noopener">Substack</a></li>
        <li><a href="https://www.linkedin.com/company/libertycti" target="_blank" rel="noopener">LinkedIn</a></li>
        <li><a href="https://x.com/libertycti" target="_blank" rel="noopener">X / Twitter</a></li>
      </ul>
    </div>
  </div>
  <div class="lcti-footer-bottom">
    <div class="lcti-footer-copy">© 2026 Liberty CTI LLC &nbsp;·&nbsp; San Antonio, Texas &nbsp;·&nbsp; libertycti.com</div>
    <div class="lcti-footer-copy">All analysis produced in accordance with accepted national security-grade analytical practices</div>
  </div>
</footer>
<!-- LCTI:FOOTER:END -->"""
    return relativize_component_links(html, current_page, root)


def has_sentinel(content: str, start: str, end: str) -> bool:
    return start in content and end in content


def inject(content: str, pattern: re.Pattern, replacement: str) -> str:
    return pattern.sub(replacement, content)


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(f".{stamp}.bak")
    shutil.copy2(path, bak)
    return bak


def process_file(path: Path, write: bool, backup_files: bool, nav_html: str, footer_html: str, latest_issue_file: Path | None, root: Path) -> dict:
    result = {
        "path": str(path),
        "nav": False,
        "footer": False,
        "latest": False,
        "skipped": False,
        "error": None,
        "backup": None,
    }

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        result["error"] = f"Read error: {e}"
        return result

    has_nav = has_sentinel(content, NAV_START, NAV_END)
    has_footer = has_sentinel(content, FOOTER_START, FOOTER_END)

    new_content = content

    if has_nav:
        new_content = inject(new_content, NAV_PATTERN, nav_html)
        result["nav"] = True

    if has_footer:
        new_content = inject(new_content, FOOTER_PATTERN, footer_html)
        result["footer"] = True

    new_content, latest_changed = sync_latest_issue_links(new_content, latest_issue_file, path, root)
    result["latest"] = latest_changed

    if not has_nav and not has_footer and not latest_changed:
        result["skipped"] = True
        return result

    if new_content == content:
        result["nav"] = False
        result["footer"] = False
        result["latest"] = False
        return result

    if write:
        if backup_files:
            result["backup"] = str(backup(path))
        path.write_text(new_content, encoding="utf-8")

    return result


SENTINEL_NAV_PLACEHOLDER = f"""\
{NAV_START}
<!-- TODO: paste canonical nav here, then run sync_components_auto_atb.py --write -->
{NAV_END}"""

SENTINEL_FOOTER_PLACEHOLDER = f"""\
{FOOTER_START}
<!-- TODO: paste canonical footer here, then run sync_components_auto_atb.py --write -->
{FOOTER_END}"""


def add_sentinels(path: Path, write: bool) -> dict:
    result = {"path": str(path), "nav_wrapped": False, "footer_wrapped": False, "error": None}
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        result["error"] = str(e)
        return result

    new = content

    if NAV_START not in new:
        nav_tag = re.search(r'(<nav[\s>].*?</nav>)', new, re.DOTALL | re.IGNORECASE)
        if nav_tag:
            wrapped = f"{NAV_START}\n{nav_tag.group(1)}\n{NAV_END}"
            new = new[:nav_tag.start()] + wrapped + new[nav_tag.end():]
            result["nav_wrapped"] = True
        else:
            new, count = re.subn(r'(<body[^>]*>)', r'\1\n' + SENTINEL_NAV_PLACEHOLDER, new, count=1)
            if count == 0:
                new = SENTINEL_NAV_PLACEHOLDER + "\n" + new
            result["nav_wrapped"] = True

    if FOOTER_START not in new:
        footer_tag = re.search(r'(<footer[\s>].*?</footer>)', new, re.DOTALL | re.IGNORECASE)
        if footer_tag:
            wrapped = f"{FOOTER_START}\n{footer_tag.group(1)}\n{FOOTER_END}"
            new = new[:footer_tag.start()] + wrapped + new[footer_tag.end():]
            result["footer_wrapped"] = True
        else:
            new, count = re.subn(r'(</body>)', SENTINEL_FOOTER_PLACEHOLDER + r'\n\1', new, count=1)
            if count == 0:
                new = new.rstrip() + "\n" + SENTINEL_FOOTER_PLACEHOLDER + "\n"
            result["footer_wrapped"] = True

    if write and new != content:
        path.write_text(new, encoding="utf-8")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Liberty CTI — sync nav + footer across all HTML pages, with automatic ATB latest issue detection."
    )
    parser.add_argument("--write", action="store_true", help="Apply changes (default is dry-run preview)")
    parser.add_argument("--no-backup", action="store_true", help="Skip .bak backup files when writing")
    parser.add_argument("--page", metavar="FILE", help="Process a single file instead of the whole site")
    parser.add_argument("--add-sentinels", action="store_true", help="Wrap existing nav/footer tags with sentinel comments")
    parser.add_argument("--root", metavar="DIR", default=str(SITE_ROOT), help=f"Site root directory (default: {SITE_ROOT})")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    backup_files = not args.no_backup

    if not root.is_dir():
        print(f"ERROR: Site root not found: {root}")
        sys.exit(1)

    dated_atb_files = find_dated_atb_files(root)
    latest_issue = dated_atb_files[0] if dated_atb_files else None

    if args.page:
        target = Path(args.page)
        if not target.is_absolute():
            target = root / target
        if not target.exists():
            print(f"ERROR: File not found: {target}")
            sys.exit(1)
        files = [target]
    else:
        files = find_html_files(root)

    mode = "WRITE" if args.write else "DRY RUN"
    print(f"\n{'━'*60}")
    print(f"  Liberty CTI — sync_components_auto_atb.py  [{mode}]")
    print(f"  Site root     : {root}")
    print(f"  Files         : {len(files)}")
    print(f"  Latest ATB    : {latest_issue or 'None found (make sure a MM-DD-YYYY.html file exists under this site root)'}")
    if dated_atb_files:
        print(f"  Issue count   : {len(dated_atb_files)}")
    print(f"{'━'*60}\n")

    updated = 0
    skipped = 0
    errors = 0

    for path in files:
        rel = path.relative_to(root)

        if args.add_sentinels:
            r = add_sentinels(path, write=args.write)
            if r["error"]:
                print(f"  ✗  {rel}  —  ERROR: {r['error']}")
                errors += 1
            elif r["nav_wrapped"] or r["footer_wrapped"]:
                tags = []
                if r["nav_wrapped"]:
                    tags.append("nav")
                if r["footer_wrapped"]:
                    tags.append("footer")
                flag = "" if args.write else " [dry run]"
                print(f"  ✎  {rel}  —  sentinels added ({', '.join(tags)}){flag}")
                updated += 1
            else:
                print(f"  ·  {rel}  —  already has sentinels")
                skipped += 1
        else:
            nav_html = build_nav_html(latest_issue, path, root)
            footer_html = build_footer_html(latest_issue, path, root)
            r = process_file(path, write=args.write, backup_files=backup_files, nav_html=nav_html, footer_html=footer_html, latest_issue_file=latest_issue, root=root)
            if r["error"]:
                print(f"  ✗  {rel}  —  ERROR: {r['error']}")
                errors += 1
            elif r["skipped"]:
                print(f"  ·  {rel}  —  no sentinels (skipped)")
                skipped += 1
            elif not r["nav"] and not r["footer"]:
                print(f"  ✓  {rel}  —  already up to date")
                skipped += 1
            else:
                parts = []
                if r["nav"]:
                    parts.append("nav")
                if r["footer"]:
                    parts.append("footer")
                if r.get("latest"):
                    parts.append("latest issue links")
                flag = "" if args.write else " [dry run — not written]"
                bak = f"  →  backup: {Path(r['backup']).name}" if r.get("backup") else ""
                print(f"  ↻  {rel}  —  updated ({', '.join(parts)}){flag}{bak}")
                updated += 1

    print(f"\n{'━'*60}")
    print(f"  Updated : {updated}")
    print(f"  Skipped : {skipped}")
    print(f"  Errors  : {errors}")
    if not args.write and not args.add_sentinels:
        print(f"\n  Run with --write to apply changes.")
    print(f"{'━'*60}\n")


if __name__ == "__main__":
    main()
