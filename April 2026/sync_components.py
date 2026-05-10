#!/usr/bin/env python3
"""
sync_components.py — Liberty CTI
=================================
Injects the canonical nav and footer into every HTML page on the site.
Run this script whenever you update the nav or footer. It rewrites all
pages in-place, leaving the rest of each file untouched.

USAGE
-----
    python3 sync_components.py                  # dry-run preview
    python3 sync_components.py --write          # apply changes
    python3 sync_components.py --write --page index.html   # single page

REQUIREMENTS
------------
    Python 3.8+  (no third-party packages needed)

HOW IT WORKS
------------
Each HTML page must contain two pairs of sentinel comments:

    <!-- LCTI:NAV:START -->  ...old nav...  <!-- LCTI:NAV:END -->
    <!-- LCTI:FOOTER:START -->  ...old footer...  <!-- LCTI:FOOTER:END -->

This script replaces everything between those sentinels with the
canonical blocks defined in NAV_HTML and FOOTER_HTML below.

Pages that are missing sentinels are reported but never modified.

PATH DEPTH
----------
The nav uses root-relative hrefs (/index.html, /about/about.html …).
If your server serves the site from its root this works everywhere.
For file:// local previews add --local and the script inserts relative
paths based on each file's depth in the folder tree.
"""

import os
import re
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# SITE ROOT — edit this to point at your local website folder
# ─────────────────────────────────────────────────────────────
SITE_ROOT = Path(__file__).parent  # same folder as this script by default

# ─────────────────────────────────────────────────────────────
# FILES TO SKIP (ATB issues, standalone tools, etc.)
# ─────────────────────────────────────────────────────────────
SKIP_FILES = {
    "thank-you.html",           # post-form confirmation page, no full nav needed
    "nav-component.html",       # component reference file, not a real page
    # ATB individual issues use the full nav — only skip if they diverge:
    # "atb/issue-2026-01.html",
}

# ─────────────────────────────────────────────────────────────
# SENTINEL PATTERNS
# ─────────────────────────────────────────────────────────────
NAV_START    = "<!-- LCTI:NAV:START -->"
NAV_END      = "<!-- LCTI:NAV:END -->"
FOOTER_START = "<!-- LCTI:FOOTER:START -->"
FOOTER_END   = "<!-- LCTI:FOOTER:END -->"

NAV_PATTERN    = re.compile(
    r"<!-- LCTI:NAV:START -->.*?<!-- LCTI:NAV:END -->",
    re.DOTALL
)
FOOTER_PATTERN = re.compile(
    r"<!-- LCTI:FOOTER:START -->.*?<!-- LCTI:FOOTER:END -->",
    re.DOTALL
)

# ═════════════════════════════════════════════════════════════
#  CANONICAL NAV
#  Edit this block to change the nav across every page at once.
#  Keep the sentinel comments — they are how the script finds
#  the block on the next run.
# ═════════════════════════════════════════════════════════════
NAV_HTML = """\
<!-- LCTI:NAV:START -->
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{background:#080c10 !important;color:#f4efe6 !important;min-height:100vh;font-family:'Instrument Sans',sans-serif;font-weight:300}
.lcti-canvas{position:fixed;inset:0;z-index:-1;background-color:#080c10;background-image:linear-gradient(rgba(184,150,62,.03) 1px,transparent 1px),linear-gradient(90deg,rgba(184,150,62,.03) 1px,transparent 1px);background-size:64px 64px}
:root{--nav-h:68px}
.lcti-nav{position:fixed;top:0;left:0;right:0;z-index:1000;height:var(--nav-h);display:flex;align-items:center;justify-content:space-between;padding:0 2rem;background:rgba(8,12,16,.97);border-bottom:1px solid rgba(184,150,62,.2);backdrop-filter:blur(12px)}

/* LOGO ROW: emblem | wordmark | rule | slogan */
.lcti-logo{display:flex;align-items:center;gap:.6rem;text-decoration:none;flex-shrink:0}
.lcti-logo-emblem{width:36px;height:36px;object-fit:contain;flex-shrink:0}
.lcti-logo-wordmark{font-family:'Playfair Display',serif;font-size:.9rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#f4efe6;white-space:nowrap;flex-shrink:0}
.lcti-logo-wordmark span{color:#b8963e}
.lcti-logo-rule{width:1px;height:24px;background:rgba(184,150,62,.3);flex-shrink:0}
.lcti-logo-slogan{font-family:'Instrument Sans',sans-serif;font-size:.42rem;letter-spacing:.16em;text-transform:uppercase;color:#b8963e;opacity:.65;line-height:1.5;white-space:normal;max-width:80px}

/* DESKTOP LINKS */
.lcti-links{display:flex;align-items:center;gap:.1rem;list-style:none}
.lcti-links>li>a,.lcti-links>li>.lcti-drop-toggle{font-family:'Instrument Sans',sans-serif;font-size:.65rem;font-weight:500;letter-spacing:.15em;text-transform:uppercase;color:rgba(244,239,230,.55);text-decoration:none;padding:.4rem .65rem;border-radius:2px;transition:color .22s;display:flex;align-items:center;gap:.3rem;cursor:pointer;background:none;border:none;white-space:nowrap}
.lcti-links>li>a:hover,.lcti-links>li>.lcti-drop-toggle:hover,.lcti-links>li>a.active,.lcti-links>li.active>.lcti-drop-toggle{color:#b8963e}
.lcti-drop-toggle::after{content:'';display:inline-block;width:0;height:0;border-left:3px solid transparent;border-right:3px solid transparent;border-top:4px solid currentColor;opacity:.55;transition:transform .2s;flex-shrink:0}
.lcti-drop-item.open>.lcti-drop-toggle::after{transform:rotate(180deg)}
.lcti-drop-item{position:relative}
.lcti-drop-panel{display:none;position:absolute;top:calc(100% + 8px);left:0;min-width:220px;background:#080c10;border:1px solid rgba(184,150,62,.2);border-top:2px solid #b8963e;padding:.4rem 0;z-index:200;box-shadow:0 12px 32px rgba(0,0,0,.9)}
.lcti-drop-item.open .lcti-drop-panel{display:block}
.lcti-drop-panel a{display:block;font-family:'Instrument Sans',sans-serif;font-size:.66rem;font-weight:400;letter-spacing:.12em;text-transform:uppercase;color:rgba(244,239,230,.55);text-decoration:none;padding:.55rem 1.1rem;transition:color .18s,background .18s;border-left:2px solid transparent}
.lcti-drop-panel a:hover{color:#b8963e;background:rgba(184,150,62,.07);border-left-color:#b8963e}
.lcti-drop-panel .drop-label{font-family:'Instrument Sans',sans-serif;font-size:.5rem;letter-spacing:.28em;text-transform:uppercase;color:#b8963e;opacity:.45;padding:.6rem 1.1rem .25rem;pointer-events:none;display:block}
.lcti-drop-panel .drop-divider{height:1px;background:rgba(184,150,62,.2);margin:.3rem 0}
.lcti-cta{font-family:'Instrument Sans',sans-serif;font-size:.62rem;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:#b8963e !important;border:1px solid #b8963e;padding:.4rem 1rem !important;border-radius:2px;transition:background .22s,color .22s;text-decoration:none;white-space:nowrap;margin-left:.4rem}
.lcti-cta:hover{background:#b8963e !important;color:#080c10 !important}
.lcti-burger{display:none;flex-direction:column;gap:5px;cursor:pointer;padding:4px;background:none;border:none}
.lcti-burger span{display:block;width:22px;height:2px;background:#f4efe6;transition:transform .25s,opacity .25s;transform-origin:center}
.lcti-burger.open span:nth-child(1){transform:translateY(7px) rotate(45deg)}
.lcti-burger.open span:nth-child(2){opacity:0}
.lcti-burger.open span:nth-child(3){transform:translateY(-7px) rotate(-45deg)}
.lcti-mobile-menu{display:none;position:fixed;top:var(--nav-h);left:0;right:0;background:#080c10;border-bottom:1px solid rgba(184,150,62,.2);padding:1rem 0 1.5rem;z-index:999;max-height:calc(100vh - var(--nav-h));overflow-y:auto}
.lcti-mobile-menu.open{display:block}
.lcti-mobile-menu a{display:block;font-size:.72rem;font-weight:500;letter-spacing:.18em;text-transform:uppercase;color:rgba(244,239,230,.6);text-decoration:none;padding:.7rem 2rem;transition:color .18s}
.lcti-mobile-menu a:hover{color:#b8963e}
.lcti-mobile-menu .m-group-label{font-family:'Instrument Sans',sans-serif;font-size:.54rem;letter-spacing:.3em;text-transform:uppercase;color:#b8963e;opacity:.5;padding:1rem 2rem .3rem;display:block;pointer-events:none}
.lcti-mobile-menu .m-sub a{padding-left:3rem;font-size:.67rem;opacity:.85}
.lcti-mobile-menu .m-cta-wrap{padding:1rem 2rem 0}
.lcti-mobile-menu .m-cta{display:block;text-align:center;font-size:.7rem;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:#b8963e;border:1px solid #b8963e;padding:.65rem 1.5rem;text-decoration:none;transition:background .2s,color .2s}
.lcti-mobile-menu .m-cta:hover{background:#b8963e;color:#080c10}
@media(max-width:960px){.lcti-links{display:none}.lcti-burger{display:flex}}
@media(max-width:400px){.lcti-logo-rule,.lcti-logo-slogan{display:none}}

/* DEMO */
.demo-stage{position:relative;padding-top:calc(var(--nav-h) + 5rem);padding-bottom:8rem;max-width:860px;margin:0 auto;padding-left:3rem;padding-right:3rem}
.demo-eyebrow{font-family:'Instrument Sans',sans-serif;font-size:.6rem;letter-spacing:.35em;text-transform:uppercase;color:#b8963e;opacity:.6;margin-bottom:1.2rem;display:flex;align-items:center;gap:1rem}
.demo-eyebrow::after{content:'';flex:1;height:1px;background:rgba(184,150,62,.2)}
.demo-h1{font-family:'Playfair Display',serif;font-size:clamp(2rem,5vw,3.5rem);font-weight:900;line-height:1.08;color:#f4efe6;margin-bottom:1.5rem}
.demo-h1 em{font-style:italic;color:#b8963e}
.demo-body{font-size:.9rem;font-weight:300;color:rgba(244,239,230,.5);line-height:1.9;max-width:560px;margin-bottom:2.5rem}
.demo-note{font-family:'Instrument Sans',sans-serif;font-size:.62rem;letter-spacing:.18em;text-transform:uppercase;color:rgba(184,150,62,.45);border:1px solid rgba(184,150,62,.15);padding:.8rem 1.2rem;display:inline-block}
.annotation{margin-top:2.5rem;background:rgba(184,150,62,.05);border:1px solid rgba(184,150,62,.18);border-left:3px solid #b8963e;padding:1.2rem 1.4rem;font-family:'Instrument Sans',sans-serif;font-size:.66rem;letter-spacing:.06em;color:rgba(244,239,230,.5);line-height:1.85}
.annotation strong{color:#b8963e}
@media(max-width:640px){.demo-stage{padding-left:1.5rem;padding-right:1.5rem}}
</style>

<nav class="lcti-nav" role="navigation" aria-label="Main navigation">
  <a href="/index.html" class="lcti-logo" aria-label="Liberty CTI Home">
    <svg class="lcti-logo-emblem" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M20 2L4 10v12c0 9.4 6.8 18.2 16 20.4C29.2 40.2 36 31.4 36 22V10L20 2z" fill="#b8963e" opacity=".15" stroke="#b8963e" stroke-width="1.2"/>
      <path d="M20 8l-2 5h-3l2.5 2-1 5L20 17l3.5 3-1-5 2.5-2h-3z" fill="#b8963e" opacity=".9"/>
      <path d="M16 22h8M18 25v4M22 25v4" stroke="#b8963e" stroke-width="1.2" stroke-linecap="round"/>
    </svg>
    <div class="lcti-logo-wordmark">Liberty <span>CTI</span></div>
    <div class="lcti-logo-rule"></div>
    <div class="lcti-logo-slogan">Know the threat.<br>Stay ready.<br>They are.</div>
  </a>

  <ul class="lcti-links" role="list">
    <li><a href="/index.html">Home</a></li>
    <li class="lcti-drop-item">
      <button class="lcti-drop-toggle" aria-haspopup="true" aria-expanded="false">About</button>
      <div class="lcti-drop-panel" role="menu">
        <a href="/about/about.html" role="menuitem">Company Overview</a>
        <div class="drop-divider"></div>
        <span class="drop-label">Founders</span>
        <a href="/about/luis-maldonado.html" role="menuitem">Luis Maldonado</a>
        <a href="/about/angie-maldonado.html" role="menuitem">Angie Maldonado</a>
      </div>
    </li>
    <li class="lcti-drop-item">
      <button class="lcti-drop-toggle" aria-haspopup="true" aria-expanded="false">Intelligence</button>
      <div class="lcti-drop-panel" role="menu">
        <a href="/intelligence/intelligence.html" role="menuitem">Intelligence Overview</a>
        <div class="drop-divider"></div>
        <span class="drop-label">Products</span>
        <a href="/atb/index.html" role="menuitem">Alamo Threat Brief</a>
        <a href="/intelligence/texas-threat-outlook.html" role="menuitem">Texas Threat Outlook</a>
        <a href="/intelligence/sector-assessments.html" role="menuitem">Sector Assessments</a>
        <div class="drop-divider"></div>
        <a href="/atb/archive.html" role="menuitem">ATB Archive</a>
      </div>
    </li>
    <li class="lcti-drop-item">
      <button class="lcti-drop-toggle" aria-haspopup="true" aria-expanded="false">Texas Focus</button>
      <div class="lcti-drop-panel" role="menu">
        <a href="/texas-focus/texas-focus.html" role="menuitem">Texas Overview</a>
        <div class="drop-divider"></div>
        <span class="drop-label">Critical Sectors</span>
        <a href="/texas-focus/energy-ercot.html" role="menuitem">Energy &amp; ERCOT</a>
        <a href="/texas-focus/defense-dib.html" role="menuitem">Defense Industrial Base</a>
        <a href="/texas-focus/financial.html" role="menuitem">Financial Services</a>
        <a href="/texas-focus/healthcare.html" role="menuitem">Healthcare</a>
        <div class="drop-divider"></div>
        <a href="/texas-focus/ai-convergence.html" role="menuitem">AI Convergence</a>
      </div>
    </li>
    <li><a href="/briefing-request.html" class="lcti-cta">Request a Briefing</a></li>
  </ul>

  <button class="lcti-burger" id="lcti-burger" aria-label="Toggle mobile menu" aria-expanded="false">
    <span></span><span></span><span></span>
  </button>
</nav>

<div class="lcti-mobile-menu" id="lcti-mobile-menu" role="dialog" aria-label="Mobile navigation">
  <a href="/index.html">Home</a>
  <span class="m-group-label">About</span>
  <div class="m-sub">
    <a href="/about/about.html">Company Overview</a>
    <a href="/about/luis-maldonado.html">Luis Maldonado</a>
    <a href="/about/angie-maldonado.html">Angie Maldonado</a>
  </div>
  <span class="m-group-label">Intelligence</span>
  <div class="m-sub">
    <a href="/intelligence/intelligence.html">Intelligence Overview</a>
    <a href="/atb/index.html">Alamo Threat Brief</a>
    <a href="/intelligence/texas-threat-outlook.html">Texas Threat Outlook</a>
    <a href="/intelligence/sector-assessments.html">Sector Assessments</a>
    <a href="/atb/archive.html">ATB Archive</a>
  </div>
  <span class="m-group-label">Texas Focus</span>
  <div class="m-sub">
    <a href="/texas-focus/texas-focus.html">Texas Overview</a>
    <a href="/texas-focus/energy-ercot.html">Energy &amp; ERCOT</a>
    <a href="/texas-focus/defense-dib.html">Defense Industrial Base</a>
    <a href="/texas-focus/financial.html">Financial Services</a>
    <a href="/texas-focus/healthcare.html">Healthcare</a>
    <a href="/texas-focus/ai-convergence.html">AI Convergence</a>
  </div>
  <div class="m-cta-wrap">
    <a href="/briefing-request.html" class="m-cta">Request a Briefing</a>
  </div>
</div>

<script>
(function(){
  var burger=document.getElementById('lcti-burger');
  var menu=document.getElementById('lcti-mobile-menu');
  if(burger&&menu){burger.addEventListener('click',function(){var o=menu.classList.toggle('open');burger.classList.toggle('open',o);burger.setAttribute('aria-expanded',String(o))});}
  var drops=document.querySelectorAll('.lcti-drop-item');
  drops.forEach(function(item){
    var toggle=item.querySelector('.lcti-drop-toggle');
    if(!toggle)return;
    toggle.addEventListener('click',function(e){
      e.stopPropagation();
      var o=item.classList.toggle('open');
      toggle.setAttribute('aria-expanded',String(o));
      drops.forEach(function(other){if(other!==item){other.classList.remove('open');var t=other.querySelector('.lcti-drop-toggle');if(t)t.setAttribute('aria-expanded','false');}});
    });
  });
  document.addEventListener('click',function(){drops.forEach(function(item){item.classList.remove('open');var t=item.querySelector('.lcti-drop-toggle');if(t)t.setAttribute('aria-expanded','false');});});
  window.addEventListener('resize',function(){if(window.innerWidth>960){menu&&menu.classList.remove('open');burger&&burger.classList.remove('open');}});
})();
</script>
<!-- LCTI:NAV:END -->"""


# ═════════════════════════════════════════════════════════════
#  CANONICAL FOOTER
#  Edit this block to change the footer across every page.
# ═════════════════════════════════════════════════════════════
FOOTER_HTML = """\
<!-- LCTI:FOOTER:START -->
<style>
/* ── LCTI UNIVERSAL FOOTER ── */
.lcti-footer{background:#080c10;border-top:1px solid rgba(184,150,62,0.2);padding:4rem 2.5rem 2rem;font-family:'Instrument Sans',sans-serif}
.lcti-footer-inner{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;gap:3rem}
.lcti-footer-brand-row{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem}
.lcti-footer-emblem{width:36px;height:36px;object-fit:contain}
.lcti-footer-brand-name{font-family:'Playfair Display',serif;font-size:1rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#f4efe6}
.lcti-footer-brand-name span{color:#b8963e}
.lcti-footer-tagline{font-size:.82rem;font-weight:300;color:rgba(244,239,230,.45);line-height:1.75;max-width:280px;margin-bottom:1.25rem}
.lcti-footer-slogan{font-family:'Instrument Sans',sans-serif;font-size:.58rem;letter-spacing:.22em;text-transform:uppercase;color:#b8963e;opacity:.5}
.lcti-footer-col-title{font-family:'Instrument Sans',sans-serif;font-size:.58rem;letter-spacing:.28em;text-transform:uppercase;color:#b8963e;opacity:.6;margin-bottom:.9rem;display:block}
.lcti-footer-links{list-style:none}
.lcti-footer-links li{margin-bottom:.45rem}
.lcti-footer-links a{font-size:.8rem;font-weight:300;color:rgba(244,239,230,.45);text-decoration:none;transition:color .2s}
.lcti-footer-links a:hover{color:#b8963e}
.lcti-footer-bottom{max-width:1100px;margin:3rem auto 0;border-top:1px solid rgba(184,150,62,0.12);padding-top:1.25rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem}
.lcti-footer-copy{font-family:'Instrument Sans',sans-serif;font-size:.58rem;letter-spacing:.1em;color:rgba(244,239,230,.25)}
@media(max-width:860px){.lcti-footer-inner{grid-template-columns:1fr 1fr;gap:2rem}}
@media(max-width:520px){.lcti-footer-inner{grid-template-columns:1fr}.lcti-footer{padding:2.5rem 1.25rem 1.5rem}.lcti-footer-bottom{flex-direction:column;align-items:flex-start}}
</style>

<footer class="lcti-footer" role="contentinfo">
  <div class="lcti-footer-inner">

    <!-- Brand column -->
    <div>
      <div class="lcti-footer-brand-row">
        <img src="/liberty-cti-emblem.png" alt="Liberty CTI" class="lcti-footer-emblem">
        <div class="lcti-footer-brand-name">Liberty <span>CTI</span></div>
      </div>
      <p class="lcti-footer-tagline">Strategic cyber threat intelligence for organizations that understand the threat environment shapes every decision they make.</p>
      <div class="lcti-footer-slogan">Know the threat. Stay ready. They are.</div>
    </div>

    <!-- Intelligence column -->
    <div>
      <span class="lcti-footer-col-title">Intelligence</span>
      <ul class="lcti-footer-links">
        <li><a href="/atb/index.html">Alamo Threat Brief</a></li>
        <li><a href="/intelligence/texas-threat-outlook.html">Texas Threat Outlook</a></li>
        <li><a href="/intelligence/sector-assessments.html">Sector Assessments</a></li>
        <li><a href="/intelligence/intelligence.html">Intelligence Overview</a></li>
        <li><a href="/atb/archive.html">ATB Archive</a></li>
      </ul>
    </div>

    <!-- Texas Focus column -->
    <div>
      <span class="lcti-footer-col-title">Texas Focus</span>
      <ul class="lcti-footer-links">
        <li><a href="/texas-focus/texas-focus.html">Texas Overview</a></li>
        <li><a href="/texas-focus/energy-ercot.html">Energy &amp; ERCOT</a></li>
        <li><a href="/texas-focus/defense-dib.html">Defense Industrial Base</a></li>
        <li><a href="/texas-focus/financial.html">Financial Services</a></li>
        <li><a href="/texas-focus/healthcare.html">Healthcare</a></li>
        <li><a href="/texas-focus/ai-convergence.html">AI Convergence</a></li>
      </ul>
    </div>

    <!-- Connect column -->
    <div>
      <span class="lcti-footer-col-title">Connect</span>
      <ul class="lcti-footer-links">
        <li><a href="/briefing-request.html">Request a Briefing</a></li>
        <li><a href="mailto:intel@libertycti.com">intel@libertycti.com</a></li>
        <li><a href="https://libertycti.substack.com" target="_blank" rel="noopener">Substack</a></li>
        <li><a href="https://www.linkedin.com/company/libertycti" target="_blank" rel="noopener">LinkedIn</a></li>
        <li><a href="https://x.com/libertycti" target="_blank" rel="noopener">X / Twitter</a></li>
        <li><a href="https://www.facebook.com/LibertyCTI" target="_blank" rel="noopener">Facebook</a></li>
        <li><a href="https://www.instagram.com/libertycti" target="_blank" rel="noopener">Instagram</a></li>
      </ul>
    </div>

  </div>
  <div class="lcti-footer-bottom">
    <div class="lcti-footer-copy">© 2026 Liberty CTI LLC &nbsp;·&nbsp; San Antonio, Texas &nbsp;·&nbsp; libertycti.com</div>
    <div class="lcti-footer-copy">All analysis produced in accordance with national security-grade analytical practices</div>
  </div>
</footer>
<!-- LCTI:FOOTER:END -->"""


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def find_html_files(root: Path) -> list[Path]:
    """Recursively find all .html files under root, skipping SKIP_FILES."""
    results = []
    for p in sorted(root.rglob("*.html")):
        rel = str(p.relative_to(root))
        if any(rel == skip or p.name == skip for skip in SKIP_FILES):
            continue
        results.append(p)
    return results


def has_sentinel(content: str, start: str, end: str) -> bool:
    return start in content and end in content


def inject(content: str, pattern: re.Pattern, replacement: str) -> str:
    return pattern.sub(replacement, content)


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(f".{stamp}.bak")
    shutil.copy2(path, bak)
    return bak


# ─────────────────────────────────────────────────────────────
# MAIN PROCESSOR
# ─────────────────────────────────────────────────────────────

def process_file(path: Path, write: bool, backup_files: bool) -> dict:
    result = {
        "path": str(path),
        "nav": False,
        "footer": False,
        "skipped": False,
        "error": None,
        "backup": None,
    }

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        result["error"] = f"Read error: {e}"
        return result

    has_nav    = has_sentinel(content, NAV_START, NAV_END)
    has_footer = has_sentinel(content, FOOTER_START, FOOTER_END)

    if not has_nav and not has_footer:
        result["skipped"] = True
        return result

    new_content = content

    if has_nav:
        new_content = inject(new_content, NAV_PATTERN, NAV_HTML)
        result["nav"] = True

    if has_footer:
        new_content = inject(new_content, FOOTER_PATTERN, FOOTER_HTML)
        result["footer"] = True

    if new_content == content:
        # Content unchanged (already up to date)
        result["nav"] = False
        result["footer"] = False
        return result

    if write:
        if backup_files:
            result["backup"] = str(backup(path))
        path.write_text(new_content, encoding="utf-8")

    return result


# ─────────────────────────────────────────────────────────────
# ADD SENTINELS HELPER
# Adds missing sentinel comments to a page so it becomes
# managed. Use --add-sentinels to prep pages in bulk.
# ─────────────────────────────────────────────────────────────

SENTINEL_NAV_PLACEHOLDER = f"""\
{NAV_START}
<!-- TODO: paste canonical nav here, then run sync_components.py --write -->
{NAV_END}"""

SENTINEL_FOOTER_PLACEHOLDER = f"""\
{FOOTER_START}
<!-- TODO: paste canonical footer here, then run sync_components.py --write -->
{FOOTER_END}"""


def add_sentinels(path: Path, write: bool) -> dict:
    """
    Wraps existing <nav> ... </nav> and <footer> ... </footer> blocks
    with sentinel comments so they become managed by this script.
    Falls back to inserting placeholder sentinels if no tags found.
    """
    result = {"path": str(path), "nav_wrapped": False, "footer_wrapped": False, "error": None}
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        result["error"] = str(e)
        return result

    new = content

    # Only wrap if sentinels not already present
    if NAV_START not in new:
        # Try to wrap existing <nav ...> ... </nav>
        nav_tag = re.search(r'(<nav[\s>].*?</nav>)', new, re.DOTALL | re.IGNORECASE)
        if nav_tag:
            wrapped = f"{NAV_START}\n{nav_tag.group(1)}\n{NAV_END}"
            new = new[:nav_tag.start()] + wrapped + new[nav_tag.end():]
            result["nav_wrapped"] = True
        else:
            # Insert placeholder after <body>
            new = re.sub(r'(<body[^>]*>)', r'\1\n' + SENTINEL_NAV_PLACEHOLDER, new, count=1)
            result["nav_wrapped"] = True

    if FOOTER_START not in new:
        footer_tag = re.search(r'(<footer[\s>].*?</footer>)', new, re.DOTALL | re.IGNORECASE)
        if footer_tag:
            wrapped = f"{FOOTER_START}\n{footer_tag.group(1)}\n{FOOTER_END}"
            new = new[:footer_tag.start()] + wrapped + new[footer_tag.end():]
            result["footer_wrapped"] = True
        else:
            new = re.sub(r'(</body>)', SENTINEL_FOOTER_PLACEHOLDER + r'\n\1', new, count=1)
            result["footer_wrapped"] = True

    if write and new != content:
        path.write_text(new, encoding="utf-8")

    return result


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Liberty CTI — sync nav + footer across all HTML pages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
WORKFLOW FOR A NEW PAGE
-----------------------
1. Create the HTML file with any nav/footer placeholder.
2. Run:  python3 sync_components.py --add-sentinels --write --page yourpage.html
   This wraps existing <nav>/<footer> tags (or inserts placeholders) with sentinels.
3. Run:  python3 sync_components.py --write --page yourpage.html
   This injects the canonical nav and footer.
4. Done. Future runs of --write will keep it in sync automatically.

SENTINEL COMMENTS (add these manually to any page)
---------------------------------------------------
  <!-- LCTI:NAV:START -->    ...nav goes here...    <!-- LCTI:NAV:END -->
  <!-- LCTI:FOOTER:START --> ...footer goes here... <!-- LCTI:FOOTER:END -->
        """
    )
    parser.add_argument("--write", action="store_true",
                        help="Apply changes (default is dry-run preview)")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip .bak backup files when writing")
    parser.add_argument("--page", metavar="FILE",
                        help="Process a single file instead of the whole site")
    parser.add_argument("--add-sentinels", action="store_true",
                        help="Wrap existing nav/footer tags with sentinel comments")
    parser.add_argument("--root", metavar="DIR", default=str(SITE_ROOT),
                        help=f"Site root directory (default: {SITE_ROOT})")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    backup_files = not args.no_backup

    if not root.is_dir():
        print(f"ERROR: Site root not found: {root}")
        sys.exit(1)

    # Collect target files
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
    print(f"  Liberty CTI — sync_components.py  [{mode}]")
    print(f"  Site root : {root}")
    print(f"  Files     : {len(files)}")
    print(f"{'━'*60}\n")

    updated = 0
    skipped = 0
    errors  = 0

    for path in files:
        rel = path.relative_to(root)

        if args.add_sentinels:
            r = add_sentinels(path, write=args.write)
            if r["error"]:
                print(f"  ✗  {rel}  —  ERROR: {r['error']}")
                errors += 1
            elif r["nav_wrapped"] or r["footer_wrapped"]:
                tags = []
                if r["nav_wrapped"]:    tags.append("nav")
                if r["footer_wrapped"]: tags.append("footer")
                flag = "" if args.write else " [dry run]"
                print(f"  ✎  {rel}  —  sentinels added ({', '.join(tags)}){flag}")
                updated += 1
            else:
                print(f"  ·  {rel}  —  already has sentinels")
                skipped += 1
        else:
            r = process_file(path, write=args.write, backup_files=backup_files)
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
                if r["nav"]:    parts.append("nav")
                if r["footer"]: parts.append("footer")
                flag = "" if args.write else " [dry run — not written]"
                bak  = f"  →  backup: {Path(r['backup']).name}" if r.get("backup") else ""
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
