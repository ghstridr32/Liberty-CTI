#!/usr/bin/env python3
"""Apply site optimizations.

SEO, accessibility, and image-loading updates target the root-level public HTML
pages. The shared micro-label typography override is applied across every HTML
page under the site root so archived/secondary pages stay visually consistent.
"""

from __future__ import annotations

import html
import re
import struct
from pathlib import Path


SITE_ROOT = Path(__file__).parent
BASE_URL = "https://libertycti.com"

PUBLIC_PAGES = [
    "index.html",
    "about.html",
    "decision-support.html",
    "alamo-threat-brief.html",
    "texas-threat-outlook.html",
    "sector-assessments.html",
    "texas-focus.html",
    "energy-ercot.html",
    "defense-dib.html",
    "financial.html",
    "healthcare.html",
    "Energy_data_AI.html",
    "briefing-request.html",
    "contact.html",
    "luis-maldonado.html",
    "angie-maldonado.html",
    "thank-you.html",
]

DESCRIPTIONS = {
    "index.html": "Executive decision intelligence for Texas critical infrastructure leaders who need to know what changed, why it matters, and what to do this week.",
    "about.html": "Learn how Liberty CTI supports Texas executives with warning intelligence, operational context, and decision-ready analysis.",
    "decision-support.html": "Explore Liberty CTI products and services, from the Alamo Threat Brief to executive briefings and intelligence retainers.",
    "alamo-threat-brief.html": "The Alamo Threat Brief delivers weekly executive warning intelligence for Texas critical infrastructure leaders.",
    "texas-threat-outlook.html": "Liberty CTI's Texas Threat Outlook tracks cyber risks, sector exposure, and decision points for Texas organizations.",
    "sector-assessments.html": "Explore Liberty CTI sector assessments for energy, defense, financial services, healthcare, and AI-enabled operations.",
    "texas-focus.html": "Liberty CTI focuses on the cyber threat environment affecting Texas infrastructure, industry, and public-sector decision makers.",
    "energy-ercot.html": "Cyber threat intelligence and decision advantage for Texas energy, ERCOT-adjacent operations, and critical infrastructure leaders.",
    "defense-dib.html": "Decision-ready warning intelligence for defense industrial base organizations and national security suppliers.",
    "financial.html": "Cyber threat intelligence for financial services leaders managing fraud, disruption, ransomware, and operational risk.",
    "healthcare.html": "Cyber threat intelligence for healthcare leaders protecting patient care, clinical operations, and sensitive data.",
    "Energy_data_AI.html": "Liberty CTI analyzes the convergence of energy, data, AI, and cyber risk for executive decision makers.",
    "briefing-request.html": "Request an executive briefing, rapid threat assessment, or intelligence retainer from Liberty CTI.",
    "contact.html": "Contact Liberty CTI for executive decision intelligence, briefings, and retainers.",
    "luis-maldonado.html": "Learn about Lou Maldonado, Liberty CTI co-founder and executive intelligence leader.",
    "angie-maldonado.html": "Learn about Angie Maldonado, Liberty CTI co-founder and national security intelligence leader.",
    "thank-you.html": "Liberty CTI has received your request and will follow up through the appropriate channel.",
}

OG_IMAGES = {
    "index.html": "liberty-cti-emblem.png",
    "about.html": "liberty-cti-emblem.png",
    "luis-maldonado.html": "WHSR.jpg",
    "angie-maldonado.html": "Angie-aide-promo.jpg",
    "texas-focus.html": "Texas-Cyber-Threat.jpg",
}

IMAGE_REPLACEMENTS = {
    "WHSR.png": "WHSR.jpg",
    "Texas-Cyber-Threat.png": "Texas-Cyber-Threat.jpg",
}

LINK_REPLACEMENTS = {
    "request-briefing.html": "briefing-request.html",
    "threat-brief.html": "alamo-threat-brief.html",
    "intelligence.html": "decision-support.html",
}


def page_url(filename: str) -> str:
    if filename == "index.html":
        return BASE_URL + "/"
    return f"{BASE_URL}/{filename}"


def read_title(content: str, filename: str) -> str:
    match = re.search(r"<title>(.*?)</title>", content, re.I | re.S)
    if not match:
        return "Liberty CTI"
    return html.unescape(re.sub(r"\s+", " ", match.group(1)).strip())


def local_image_size(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    data = path.read_bytes()
    if len(data) < 24:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            i += 2
            if marker in (0xD8, 0xD9):
                continue
            if i + 2 > len(data):
                return None
            length = struct.unpack(">H", data[i : i + 2])[0]
            if marker in range(0xC0, 0xC4):
                if i + 7 > len(data):
                    return None
                height = struct.unpack(">H", data[i + 3 : i + 5])[0]
                width = struct.unpack(">H", data[i + 5 : i + 7])[0]
                return width, height
            i += length
    return None


def build_meta(filename: str, title: str) -> str:
    description = DESCRIPTIONS[filename]
    url = page_url(filename)
    image_name = OG_IMAGES.get(filename, "liberty-cti-emblem.png")
    image_url = f"{BASE_URL}/{image_name}"
    escaped_title = html.escape(title, quote=True)
    escaped_desc = html.escape(description, quote=True)
    return "\n".join(
        [
            f'<meta name="description" content="{escaped_desc}">',
            f'<link rel="canonical" href="{url}">',
            f'<meta property="og:type" content="website">',
            f'<meta property="og:site_name" content="Liberty CTI">',
            f'<meta property="og:title" content="{escaped_title}">',
            f'<meta property="og:description" content="{escaped_desc}">',
            f'<meta property="og:url" content="{url}">',
            f'<meta property="og:image" content="{image_url}">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{escaped_title}">',
            f'<meta name="twitter:description" content="{escaped_desc}">',
            f'<meta name="twitter:image" content="{image_url}">',
        ]
    )


def replace_meta(content: str, filename: str) -> str:
    title = read_title(content, filename)
    meta = build_meta(filename, title)
    block_re = re.compile(
        r"(?:\n<meta name=\"description\"[^>]*>)?"
        r"(?:\n<link rel=\"canonical\"[^>]*>)?"
        r"(?:\n<meta property=\"og:[^\"]+\"[^>]*>)*"
        r"(?:\n<meta name=\"twitter:[^\"]+\"[^>]*>)*",
        re.I,
    )
    title_match = re.search(r"</title>", content, re.I)
    if not title_match:
        return content
    after_title = title_match.end()
    rest = block_re.sub("", content[after_title:], count=1)
    return content[:after_title] + "\n" + meta + rest


SKIP_STYLE = """<style id="lcti-accessibility">
.skip-link{position:fixed;left:1rem;top:-4rem;z-index:3000;background:#f4efe6;color:#080c10;padding:.65rem .85rem;border:2px solid #b8963e;text-decoration:none;font-weight:700}
.skip-link:focus{top:1rem}
</style>"""

LEGIBILITY_STYLE = """<style id="lcti-stat-legibility">
html{
  -webkit-text-size-adjust:100%;
  text-size-adjust:100%;
}
body{
  overflow-x:hidden;
  font-size:17px;
  line-height:1.65;
}
img,
video,
canvas,
svg{
  max-width:100%;
}
:where(p,li,dd,td,th,blockquote){
  font-size:max(1rem,16px) !important;
  line-height:1.75 !important;
}
:where(.lead,.hero-sub,.page-hero-body,.sec-lead,.section-lead,.mission-body,.story-text p,.copy p,.card p,.product p,.sector-card p,.capability-card p,.approach-card p,.value-card p,.archive-card p,.brief-card p,.contact-card p,.audience-body,.cycle-body,.framework-body,.deliverable-body,.content-card-body,.use-desc,.use-note-body,.form-help,.help-text,.field-note,.hint,.note){
  font-size:max(1.06rem,17px) !important;
  font-weight:500 !important;
  line-height:1.75 !important;
  color:rgba(244,239,230,.78) !important;
}
:where(.hero-sub,.hero-lede,.page-hero-body,.lead){
  font-size:max(1.12rem,18px) !important;
  font-weight:500 !important;
  line-height:1.75 !important;
  color:rgba(244,239,230,.82) !important;
}
:where(.eyebrow,.sec-eyebrow,.hero-eyebrow,.hero-classification,.hero-breadcrumb,.back-link,.label,.kicker,.overline,.meta,.date,.tag,.pill,.badge,.risk-badge,.source,.caption,.photo-caption,.vignette-attr,.j-conf,.confidence,.risk-label,.brief-meta,.archive-meta,.card-meta,.timeline-meta,.tl-unit,.tl-role,.m-sub,.drop-label,.actor-origin,.jewel-label,.j-label,.hero-meta-label,.field-label,.field-error,.rail-section-id,.rail-section-name,.leader-tag,.leader-link,.section-label,.cs-label,.sec-tag,.sector-card a,.sector-card [style*="Instrument Sans"],.audience-tag,.cycle-label,.cycle-word,.framework-label,.framework-word,.deliverable-tag,.content-card-label,.use-tag,.btn-gold,.btn-outline-light,.btn-dark,.btn-outline,.chip-label,.chip-sublabel,.section-kicker,.section-desc,.submit-note,.conf-meta){
  font-size:max(.88rem,14px) !important;
  font-weight:500 !important;
  line-height:1.55 !important;
  letter-spacing:.07em !important;
  opacity:1 !important;
  color:rgba(212,175,98,.9) !important;
  text-shadow:0 0 1px rgba(212,175,98,.18) !important;
}
:where(.eyebrow,.sec-eyebrow,.hero-eyebrow,.hero-classification,.section-kicker,.hero-breadcrumb){
  font-size:max(1rem,16px) !important;
  font-weight:500 !important;
  letter-spacing:.045em !important;
  color:#d4af62 !important;
  opacity:1 !important;
  text-shadow:0 0 1px rgba(212,175,98,.25) !important;
}
:where(.section-desc,.submit-note,.chip-sublabel,.caption,.photo-caption,.card-meta,.archive-meta,.brief-meta,.vignette-attr,.j-conf,.confidence,.risk-label,.rail-section-name,.meta,.audience-body,.cycle-body,.framework-body,.deliverable-body,.content-card-body,.use-desc,.use-note-body){
  color:rgba(244,239,230,.72) !important;
}
.audience-tag,
.cycle-label,
.cycle-word,
.framework-label,
.framework-word,
.deliverable-tag,
.content-card-label,
.use-tag,
.leader-tag,
.leader-link,
.section-label,
.cs-label,
.sec-tag,
.sector-card a,
.sector-card [style*="Instrument Sans"]{
  font-family:'Instrument Sans',sans-serif !important;
  font-size:max(.94rem,15px) !important;
  font-weight:500 !important;
  line-height:1.45 !important;
  letter-spacing:.07em !important;
  text-transform:uppercase !important;
  color:#d4af62 !important;
  opacity:1 !important;
  text-shadow:0 0 1px rgba(212,175,98,.18) !important;
}
.sec-tag{
  display:flex !important;
  align-items:center !important;
  gap:.45rem !important;
  color:#d4af62 !important;
}
.sec-tag .sec-icon{
  font-size:1rem !important;
  line-height:1 !important;
}
.sector-card a{
  display:inline-flex !important;
  align-items:center !important;
  min-height:34px !important;
  margin-top:1rem !important;
  color:#d4af62 !important;
  text-decoration:none !important;
}
.sector-card a:hover{
  color:#f0d27a !important;
}
:where(.hero-badge,.pillar-tag,.pillar-stat-label,.dep-hdr-label,.dep-risk,.shift-from,.product-tag,.product-features,.bulldog-label,.distinction-label,.fc-label,.fc-edu-label,.founders-statement-label,.leader-callsign,.section-id,.cascade-label,.conf-badge,.conf-ref,.connector-text,.industries-label,.topline-step,.decision-prompt,.btn-request-hint,.form-note,.cf-label,.cf-error,.meta-label,.meta-table,.vignette-timing,.loc,.exec-label,.kiq-list,.use-features),
body [style*="font-size:0.5"],
body [style*="font-size: 0.5"],
body [style*="font-size:0.6"],
body [style*="font-size: 0.6"],
body [style*="font-size:0.7"],
body [style*="font-size: 0.7"]{
  font-size:max(.94rem,15px) !important;
  font-weight:500 !important;
  line-height:1.5 !important;
  letter-spacing:.06em !important;
  opacity:1 !important;
}
:where(.hero-badge,.pillar-tag,.pillar-stat-label,.dep-hdr-label,.dep-risk,.shift-from,.product-tag,.product-features,.bulldog-label,.distinction-label,.fc-label,.fc-edu-label,.founders-statement-label,.leader-callsign,.section-id,.cascade-label,.conf-badge,.conf-ref,.connector-text,.industries-label,.topline-step,.decision-prompt,.btn-request-hint,.form-note,.cf-label,.cf-error,.meta-label,.vignette-timing,.loc,.exec-label),
body [style*="font-family:'Instrument Sans'"][style*="font-size:0."],
body [style*='font-family:"Instrument Sans"'][style*="font-size:0."],
body [style*="font-family: 'Instrument Sans'"][style*="font-size: 0."]{
  font-family:'Instrument Sans',sans-serif !important;
  color:#d4af62 !important;
  text-transform:uppercase !important;
  text-shadow:0 0 1px rgba(212,175,98,.18) !important;
}
.leader-tag{
  display:inline-flex !important;
  align-items:center !important;
  min-height:32px !important;
  padding:.34rem .72rem !important;
  border-color:rgba(212,175,98,.38) !important;
  color:rgba(212,175,98,.88) !important;
}
.leader-link{
  display:inline-flex !important;
  align-items:center !important;
  min-height:34px !important;
  padding-top:.25rem !important;
  color:#d4af62 !important;
  text-decoration:none !important;
}
.leader-link:hover{
  color:#f0d27a !important;
}
.audience-title,
.deliverable-title,
.content-card-title{
  font-size:max(1.2rem,19px) !important;
  line-height:1.35 !important;
  color:#f4efe6 !important;
}
.audience-body,
.cycle-body,
.framework-body,
.deliverable-body,
.content-card-body,
.use-desc,
.use-note-body{
  font-size:max(1.04rem,16.75px) !important;
  font-weight:500 !important;
  line-height:1.75 !important;
  color:rgba(244,239,230,.78) !important;
}
.hero-classification{
  font-size:max(1rem,16px) !important;
  font-weight:500 !important;
  letter-spacing:.05em !important;
  line-height:1.55 !important;
  color:#d4af62 !important;
  opacity:1 !important;
}
.hero-inner > div[style*="margin-top:1.75rem"] p{
  font-size:max(1.04rem,16.75px) !important;
  font-weight:500 !important;
  line-height:1.78 !important;
  color:rgba(244,239,230,.78) !important;
}
.hero-inner > div[style*="margin-top:1.75rem"] strong{
  font-weight:800 !important;
  color:#f4efe6 !important;
}
.hero-inner > div[style*="margin-top:1.5rem"] > p{
  font-size:max(1rem,16px) !important;
  font-weight:500 !important;
  letter-spacing:.045em !important;
  line-height:1.55 !important;
  color:#d4af62 !important;
  opacity:1 !important;
}
.hero-inner > div[style*="margin-top:1.5rem"] li{
  font-size:max(1.02rem,16.25px) !important;
  font-weight:600 !important;
  line-height:1.58 !important;
  color:rgba(244,239,230,.84) !important;
}
.hero-inner [style*="font-size:0.56rem"],
.hero-inner [style*="letter-spacing:0.24em"],
.form-shell [style*="font-size:0.56rem"],
.form-shell [style*="letter-spacing:0.24em"]{
  font-size:max(.95rem,15.25px) !important;
  font-weight:500 !important;
  letter-spacing:.055em !important;
  line-height:1.45 !important;
  color:#d4af62 !important;
  opacity:1 !important;
}
.hero-inner [style*="font-size:0.82rem"],
.form-shell [style*="font-size:0.82rem"]{
  font-size:max(1rem,16px) !important;
  font-weight:500 !important;
  line-height:1.7 !important;
  color:rgba(244,239,230,.78) !important;
}
:where(.field-error){
  color:#d6554a !important;
}
:where(.chip.chip-lg .chip-label){
  font-size:max(1rem,16px) !important;
  font-weight:700 !important;
  line-height:1.45 !important;
  letter-spacing:0 !important;
  color:rgba(244,239,230,.86) !important;
}
:where(.chip-sublabel){
  font-size:max(.92rem,14.75px) !important;
  font-weight:400 !important;
  line-height:1.6 !important;
  letter-spacing:.04em !important;
  color:rgba(244,239,230,.68) !important;
  text-shadow:none !important;
}
.chip.chip-lg .chip-sublabel{
  font-family:'Instrument Sans',sans-serif !important;
  font-size:max(.95rem,15px) !important;
  font-weight:500 !important;
  line-height:1.7 !important;
  letter-spacing:0 !important;
  color:rgba(244,239,230,.68) !important;
  max-width:28ch;
}
.chip.chip-lg.selected .chip-sublabel{
  color:rgba(244,239,230,.76) !important;
}
:where(.actor-name,.vignette-body h3,.jewel-card h3){
  font-size:max(1.08rem,17px) !important;
  line-height:1.35 !important;
}
:where(.actor-card p,.jewel-card p,.vignette-body p,.vignette-impact,.judgment-block p,.timeline p,.cred-text,.cred-intro,.cred-closing,.pull-attr,.story-summary,.sector-copy,.assessment-copy,.request-copy,.next-panel li){
  font-size:max(1rem,16px) !important;
  line-height:1.78 !important;
}
.actor-origin,
.jewel-label{
  font-size:max(.94rem,15px) !important;
  font-weight:600 !important;
  line-height:1.45 !important;
  letter-spacing:.06em !important;
  color:#d6554a !important;
  opacity:1 !important;
  text-shadow:0 0 1px rgba(214,85,74,.22) !important;
}
.actor-name,
.jewel-card h3{
  font-size:max(1.12rem,18px) !important;
  font-weight:800 !important;
  line-height:1.35 !important;
  color:#f4efe6 !important;
}
.actor-card p,
.jewel-card p{
  font-size:max(1.02rem,16.25px) !important;
  font-weight:500 !important;
  line-height:1.72 !important;
  color:rgba(244,239,230,.74) !important;
}
.jewel-section .lead,
.jewel-section :where(p,li,dd,td,th,blockquote),
.crown-jewels .lead,
.crown-jewels :where(p,li,dd,td,th,blockquote){
  color:rgba(8,12,16,.72) !important;
}
.jewel-section .jewel-label,
.crown-jewels .jewel-label{
  color:#b63a32 !important;
  text-shadow:none !important;
}
.jewel-section .jewel-card h3,
.crown-jewels .jewel-card h3{
  color:#080c10 !important;
}
.jewel-section .jewel-card p,
.crown-jewels .jewel-card p{
  color:rgba(8,12,16,.68) !important;
}
.posture,
.shift-card,
.content-frame,
.content-card,
.use-cases,
.use-item,
.products,
.product-item,
.fc,
.crown-jewels,
.jewel-card{
  color:#080c10 !important;
}
.posture :where(p,.lead,.section-lead,.sec-lead),
.shift-card p,
.content-frame :where(.content-intro,p,li,dd,td,th,blockquote),
.content-card :where(p,li,dd,td,th,blockquote),
.use-cases :where(.use-cases-intro,.use-desc,.use-features li,p,li,dd,td,th,blockquote),
.use-item :where(p,li,dd,td,th,blockquote),
.products :where(p,li,.lead),
.product-item :where(p,li),
.fc :where(p,li,.fc-rank),
.crown-jewels :where(p,li,dd,td,th,blockquote),
.jewel-card :where(p,li,dd,td,th,blockquote){
  color:rgba(8,12,16,.74) !important;
  text-shadow:none !important;
}
.posture :where(h1,h2,h3,h4,.shift-to),
.shift-card :where(h1,h2,h3,h4,.shift-to),
.content-frame :where(h1,h2,h3,h4,.content-card-title),
.content-card :where(h1,h2,h3,h4,.content-card-title),
.use-cases :where(h1,h2,h3,h4,.use-name),
.use-item :where(h1,h2,h3,h4,.use-name),
.products :where(h1,h2,h3,h4),
.product-item :where(h1,h2,h3,h4),
.fc :where(h1,h2,h3,h4),
.crown-jewels :where(h1,h2,h3,h4),
.jewel-card :where(h1,h2,h3,h4){
  color:#080c10 !important;
  text-shadow:none !important;
}
.posture :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.shift-from,.jewel-label,.product-tag,.fc-label,.fc-edu-label),
.shift-card :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.shift-from,.jewel-label,.product-tag),
.content-frame :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.content-card-label),
.content-card :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.content-card-label),
.use-cases :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.use-tag),
.use-item :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.use-tag),
.products :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.product-tag),
.product-item :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.product-tag),
.fc :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.fc-label,.fc-edu-label),
.crown-jewels :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.jewel-label),
.jewel-card :where(.eyebrow,.sec-eyebrow,.label,.kicker,.overline,.jewel-label){
  color:#9b7626 !important;
  text-shadow:none !important;
}
.posture em,
.shift-card em,
.content-frame em,
.content-card em,
.use-cases em,
.use-item em,
.products em,
.product-item em,
.fc em,
.crown-jewels em,
.jewel-card em{
  color:#8f1f1b !important;
}
.content-frame .content-card-body,
.content-card .content-card-body{
  font-family:'Instrument Sans',sans-serif !important;
  font-size:max(1.05rem,17px) !important;
  font-weight:500 !important;
  line-height:1.75 !important;
  letter-spacing:0 !important;
  color:rgba(8,12,16,.76) !important;
}
.content-frame .content-card-title,
.content-card .content-card-title{
  font-size:max(1.35rem,21px) !important;
  line-height:1.35 !important;
}
.content-frame .content-card:nth-child(2) .content-card-label,
.content-card:nth-child(2) .content-card-label{
  color:#8b1a1a !important;
}
.content-frame .content-note{
  background:#080c10 !important;
  border:1px solid rgba(184,150,62,.28) !important;
}
.content-frame .content-note p{
  font-size:max(1.44rem,23px) !important;
  line-height:1.65 !important;
  color:rgba(244,239,230,.9) !important;
  font-weight:500 !important;
  text-shadow:none !important;
}
.content-frame .content-note p::before,
.content-frame .content-note p::after{
  font-size:1.9rem !important;
}
:where(.eyebrow,.sec-eyebrow,.hero-eyebrow,.hero-classification,.hero-breadcrumb,.back-link,.label,.kicker,.overline,.meta,.date,.tag,.pill,.badge,.risk-badge,.source,.caption,.photo-caption,.vignette-attr,.j-conf,.confidence,.risk-label,.brief-meta,.archive-meta,.card-meta,.timeline-meta,.tl-unit,.tl-role,.m-sub,.drop-label,.actor-origin,.jewel-label,.j-label,.hero-meta-label,.field-label,.field-error,.rail-section-id,.rail-section-name,.leader-tag,.leader-link,.section-label,.cs-label,.sec-tag,.sector-icon,.audience-tag,.cycle-label,.cycle-word,.framework-label,.framework-word,.deliverable-tag,.content-card-label,.use-tag,.product-tag,.product-features,.use-features,.kiq-list,.meta-table,.conf-ref,.connector-text,.industries-label,.topline-step,.decision-prompt,.btn-request-hint,.form-note,.cf-label,.cf-error,.meta-label,.vignette-timing,.loc,.exec-label,.lcti-logo-slogan,.lcti-footer-slogan,.lcti-footer-col-title,.lcti-footer-copy),
body [style*="Instrument Sans"]{
  font-family:'Instrument Sans',sans-serif !important;
}
:where(.use-features li,.product-features li,.kiq-list li,.meta-table td,.meta-table th){
  font-family:'Instrument Sans',sans-serif !important;
  font-size:max(.96rem,15.5px) !important;
  font-weight:500 !important;
  line-height:1.65 !important;
  letter-spacing:0 !important;
  text-transform:none !important;
  color:inherit !important;
}
:where(.vignette-timing,.stat-label,.hero-stat-label,.pillar-stat-label,.intel-desc,.footer-tagline,.foot-tagline,.lcti-footer-slogan,.lcti-footer-col-title,.lcti-footer-copy,.footer-copy){
  font-size:max(.88rem,14px) !important;
  line-height:1.58 !important;
  letter-spacing:.1em !important;
}
.timeline .tl-role,
.timeline .tl-unit{
  color:#f4efe6 !important;
  text-shadow:none !important;
}
.timeline .tl-unit{
  opacity:.86 !important;
}
.lcti-footer-tagline,
.footer-tagline,
.foot-tagline{
  font-size:max(1rem,16px) !important;
  font-weight:500 !important;
  line-height:1.72 !important;
  letter-spacing:0 !important;
  color:rgba(244,239,230,.78) !important;
  opacity:1 !important;
}
.lcti-footer-slogan,
.lcti-footer-col-title{
  font-size:max(.94rem,15px) !important;
  font-weight:500 !important;
  line-height:1.45 !important;
  letter-spacing:.09em !important;
  color:#d4af62 !important;
  opacity:1 !important;
}
.lcti-footer-links a{
  font-size:max(.98rem,15.75px) !important;
  font-weight:500 !important;
  line-height:1.55 !important;
  color:rgba(244,239,230,.74) !important;
  opacity:1 !important;
}
.lcti-footer-links a.lcti-atb-link{
  color:#d6554a !important;
  font-weight:600 !important;
}
.lcti-footer-copy,
.footer-copy{
  font-size:max(.86rem,13.75px) !important;
  font-weight:600 !important;
  letter-spacing:.04em !important;
  color:rgba(244,239,230,.56) !important;
}
:where(.subtle,.muted,.fine-print,.small,.micro,.form-disclaimer,.disclaimer,.legal,.attribution){
  font-size:max(.9rem,14.5px) !important;
  line-height:1.65 !important;
}
:where(input,select,textarea,button){
  font-size:max(1rem,16px);
}
:where(.btn,.button,.btn-gold,.btn-dark,.btn-outline,.btn-gold-outline,.btn-outline-light,.btn-request,.btn-send,.actions a,.hero-actions a,.cta-actions a,.form-actions button){
  display:inline-flex !important;
  align-items:center !important;
  justify-content:center !important;
  min-height:48px !important;
  padding:.85rem 1.35rem !important;
  font-family:'Instrument Sans',sans-serif !important;
  font-size:max(.95rem,15.25px) !important;
  font-weight:800 !important;
  line-height:1.2 !important;
  letter-spacing:.07em !important;
  text-transform:uppercase !important;
  text-decoration:none !important;
  opacity:1 !important;
  border-radius:2px !important;
}
:where(.btn-gold,.btn-request,.btn-send,.button-gold){
  background:#c9a84f !important;
  border:1px solid #c9a84f !important;
  color:#080c10 !important;
  text-shadow:none !important;
}
:where(.btn-gold:hover,.btn-request:hover,.btn-send:hover,.button-gold:hover){
  background:#d4b762 !important;
  border-color:#d4b762 !important;
  color:#080c10 !important;
}
:where(.btn-dark){
  background:#101923 !important;
  border:1px solid rgba(212,175,98,.55) !important;
  color:#f4efe6 !important;
}
:where(.btn-outline,.btn-gold-outline,.btn-outline-light){
  background:rgba(8,12,16,.28) !important;
  border:1px solid rgba(212,175,98,.65) !important;
  color:#d4af62 !important;
  text-shadow:none !important;
}
:where(.btn-outline:hover,.btn-gold-outline:hover,.btn-outline-light:hover){
  background:#c9a84f !important;
  border-color:#c9a84f !important;
  color:#080c10 !important;
}
:where(.cta,.cta-section,.section-light,.paper-section) :where(.btn-outline,.btn-gold-outline,.btn-outline-light,.cta-actions a:not(.btn-dark):not(.btn-gold):not(.btn-request):not(.btn-send)){
  background:#080c10 !important;
  border:1px solid #080c10 !important;
  color:#f4efe6 !important;
  text-shadow:none !important;
}
:where(.cta,.cta-section,.section-light,.paper-section) :where(.btn-outline:hover,.btn-gold-outline:hover,.btn-outline-light:hover,.cta-actions a:not(.btn-dark):not(.btn-gold):not(.btn-request):not(.btn-send):hover){
  background:#1a2430 !important;
  border-color:#1a2430 !important;
  color:#f4efe6 !important;
}
.actions a{
  background:#080c10 !important;
  border:1px solid #080c10 !important;
  color:#f4efe6 !important;
  text-shadow:none !important;
}
.actions a + a{
  background:#c9a84f !important;
  border-color:#c9a84f !important;
  color:#080c10 !important;
}
.intel-desc,
.stat-l,
.stat-label,
.hero-stat-label,
.pillar-stat-label,
.photo-caption{
  font-family:'Instrument Sans',sans-serif !important;
  font-size:max(.88rem,14px) !important;
  font-weight:400 !important;
  line-height:1.55 !important;
  letter-spacing:.1em !important;
  text-transform:uppercase !important;
}
.stat-l,
.stat-label,
.pillar-stat-label,
.photo-caption{
  margin-top:.22rem !important;
}
.cta-inner img,
.cta-emblem{
  height:auto !important;
  object-fit:contain !important;
}
.cta-section .cta-inner > img[src$="liberty-cti-emblem.png"]{
  width:140px !important;
}
.cta .cta-emblem{
  width:160px !important;
}
@media(max-width:700px){
  .intel-desc,
  .stat-l,
  .stat-label,
  .hero-stat-label,
  .pillar-stat-label,
  .photo-caption{
    font-size:.9rem !important;
    letter-spacing:.08em !important;
  }
}
@media(max-width:900px){
  .page-hero-inner,
  .hero-inner,
  .hero-layout,
  .mission-inner,
  .founders-grid,
  .fc-grid,
  .story,
  .story-inner,
  .story-angie,
  .why-inner,
  .vision-inner,
  .bulldog-box,
  .contact-body-inner,
  .contact-grid,
  .form-body,
  .product-grid,
  .products-grid,
  .products-list,
  .approach-grid,
  .sector-grid,
  .sectors-grid,
  .domain-grid,
  .actor-grid,
  .shift-grid,
  .doctrine-grid,
  .highlight-grid,
  .feature-grid,
  .value-grid,
  .capability-grid,
  .atb-grid,
  .two-col,
  .grid-2,
  .footer-inner,
  .site-footer-inner{
    grid-template-columns:1fr !important;
  }
  .stat-bar,
  .intel-strip,
  .cred-strip-inner{
    display:grid !important;
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    gap:0 !important;
  }
  .intel-sep,
  .stat-sep,
  .cred-sep{
    display:none !important;
  }
  .intel-item,
  .stat,
  .cred-item{
    min-width:0 !important;
  }
  .intel-item{
    justify-content:flex-start !important;
    padding:1rem 1.1rem !important;
    border-right:1px solid rgba(184,150,62,0.16);
    border-bottom:1px solid rgba(184,150,62,0.16);
  }
}
@media(max-width:768px){
  body{
    min-width:0 !important;
  }
  :where(.page-hero,.hero,.mission,.founders,.approach,.products,.vision,.section,.section-navy,.section-accent,.contact-body,.form-body,.cta,.cta-section,footer,.site-footer){
    padding-left:1.25rem !important;
    padding-right:1.25rem !important;
  }
  :where(.page-hero,.hero){
    margin-top:var(--nav-h,68px) !important;
  }
  :where(.page-hero h1,.hero h1,h1){
    font-size:clamp(2.15rem,10vw,3.1rem) !important;
    line-height:1.05 !important;
    overflow-wrap:break-word;
  }
  :where(h2,.section-title){
    font-size:clamp(1.65rem,8vw,2.35rem) !important;
    line-height:1.12 !important;
    overflow-wrap:break-word;
  }
  :where(.page-hero-body,.hero-sub,.sec-lead,.section-lead,.mission-body,.story-text p,.copy p,p,li){
    overflow-wrap:break-word;
  }
  :where(.hero-content,.page-hero-inner){
    max-width:100% !important;
  }
  :where(.hero-emblem,.header-emblem-large,.cta-emblem){
    max-width:min(220px,62vw) !important;
    height:auto !important;
  }
  :where(.photo-grid,.story-photo-pair){
    grid-template-columns:1fr !important;
  }
  :where(.photo-grid img,.photo-frame){
    max-height:320px !important;
  }
  :where(input,select,textarea,button,.button,.btn,.nav-cta,.site-nav-cta){
    max-width:100%;
  }
  :where(input,select,textarea){
    font-size:16px !important;
  }
  :where(.cta-actions,.form-actions,.hero-meta,.hero-stat-row){
    flex-wrap:wrap !important;
  }
  .intel-strip{
    display:grid !important;
    grid-template-columns:1fr !important;
    padding:0 1.25rem !important;
  }
  .intel-item{
    display:grid !important;
    grid-template-columns:minmax(5.8rem,auto) minmax(0,1fr) !important;
    align-items:center !important;
    justify-content:initial !important;
    gap:1rem !important;
    padding:1.15rem 0 !important;
    border-right:0 !important;
    border-bottom:1px solid rgba(184,150,62,0.16);
  }
  .intel-item:last-child{
    border-bottom:0 !important;
  }
  .intel-num{
    font-size:clamp(2.15rem,10vw,3rem) !important;
    line-height:1 !important;
  }
  .intel-desc{
    font-size:.9rem !important;
    line-height:1.6 !important;
    letter-spacing:.08em !important;
  }
  :where(p,li,dd,td,th,blockquote){
    font-size:1rem !important;
    line-height:1.72 !important;
  }
  :where(.hero-sub,.hero-lede,.page-hero-body,.lead){
    font-size:1.04rem !important;
    line-height:1.7 !important;
    color:rgba(244,239,230,.82) !important;
  }
  :where(.eyebrow,.sec-eyebrow,.hero-eyebrow,.hero-classification,.hero-breadcrumb,.back-link,.label,.kicker,.overline,.meta,.date,.tag,.pill,.badge,.risk-badge,.source,.caption,.photo-caption,.vignette-attr,.j-conf,.confidence,.risk-label,.brief-meta,.archive-meta,.card-meta,.timeline-meta,.tl-unit,.tl-role,.m-sub,.actor-origin,.jewel-label,.j-label,.hero-meta-label,.field-label,.field-error,.rail-section-id,.rail-section-name,.leader-tag,.leader-link,.section-label,.cs-label,.sec-tag,.sector-card a,.sector-card [style*="Instrument Sans"],.audience-tag,.cycle-label,.cycle-word,.framework-label,.framework-word,.deliverable-tag,.content-card-label,.use-tag,.chip-label,.chip-sublabel,.section-kicker,.section-desc,.submit-note,.conf-meta){
    font-size:.9rem !important;
    font-weight:500 !important;
    line-height:1.55 !important;
    letter-spacing:.06em !important;
    opacity:1 !important;
  }
  .chip.chip-lg .chip-sublabel{
    font-family:'Instrument Sans',sans-serif !important;
    font-size:1rem !important;
    font-weight:500 !important;
    line-height:1.65 !important;
    letter-spacing:0 !important;
  }
  :where(.eyebrow,.sec-eyebrow,.hero-eyebrow,.hero-classification,.section-kicker,.hero-breadcrumb){
    font-size:.96rem !important;
    font-weight:500 !important;
    letter-spacing:.04em !important;
  }
  :where(.actor-card p,.jewel-card p,.vignette-body p,.vignette-impact,.judgment-block p){
    font-size:1rem !important;
    line-height:1.72 !important;
  }
}
@media(max-width:520px){
  :where(.stat-bar,.intel-strip,.cred-strip-inner){
    display:grid !important;
    grid-template-columns:1fr !important;
  }
  :where(.stat,.intel-card,.cred-item,.intel-item){
    border-right:0 !important;
  }
  :where(.intel-item){
    padding:1rem 0 !important;
  }
  :where(.page-hero,.hero){
    min-height:auto !important;
  }
  :where(.hero-content){
    padding-left:0 !important;
    padding-right:0 !important;
  }
  :where(.photo-grid img,.photo-frame){
    max-height:280px !important;
  }
  :where(.cta-actions a,.form-actions button,.button,.btn){
    width:100%;
    text-align:center;
  }
}
.luis-hero{
  height:100svh !important;
  min-height:640px !important;
  align-items:flex-end !important;
}
.luis-hero .hero-content{
  padding-bottom:4rem !important;
}
@media(max-width:900px){
  .luis-hero{
    height:auto !important;
    min-height:calc(100svh - var(--nav-h,68px)) !important;
    padding-top:clamp(2rem,7vw,4rem) !important;
    padding-bottom:clamp(2.5rem,8vw,5rem) !important;
  }
  .luis-hero .hero-content{
    padding:0 2rem 4rem !important;
    transform:none !important;
    width:100% !important;
    max-width:100% !important;
    overflow:hidden !important;
  }
  .luis-hero h1,
  .luis-hero .hero-eyebrow,
  .luis-hero .hero-sub{
    max-width:100% !important;
    overflow-wrap:break-word !important;
  }
  .luis-photo-grid{
    grid-template-columns:1fr 1fr !important;
  }
  .luis-photo-grid .photo-tile:last-child{
    display:flex !important;
  }
  .luis-photo-grid .photo-frame{
    aspect-ratio:4 / 5 !important;
    height:auto !important;
    max-height:none !important;
  }
  .luis-stat-bar{
    grid-template-columns:1fr 1fr !important;
    overflow:hidden !important;
  }
  .luis-stat-bar .stat{
    min-width:0 !important;
    overflow:hidden !important;
  }
  .luis-stat-bar .stat-n{
    display:block !important;
    max-width:100% !important;
    font-size:clamp(2.1rem,8vw,3.4rem) !important;
    line-height:1.05 !important;
    overflow-wrap:anywhere !important;
    word-break:normal !important;
    hyphens:auto !important;
  }
  .luis-stat-bar .stat-l{
    max-width:100% !important;
    overflow-wrap:anywhere !important;
    word-break:normal !important;
    letter-spacing:.08em !important;
  }
}
@media(max-width:520px){
  .luis-hero{
    min-height:calc(100svh - var(--nav-h,68px)) !important;
    padding-bottom:3rem !important;
  }
  .luis-hero .hero-content{
    padding:0 0 3.5rem !important;
  }
  .luis-hero h1{
    font-size:clamp(2.05rem,10.5vw,2.4rem) !important;
    line-height:1.05 !important;
  }
  .luis-photo-grid{
    grid-template-columns:1fr !important;
    width:100% !important;
    max-width:100% !important;
    overflow:hidden !important;
  }
  .luis-photo-grid .photo-tile:not(:first-child){
    display:flex !important;
  }
  .luis-photo-grid .photo-frame{
    aspect-ratio:auto !important;
    height:auto !important;
    max-height:none !important;
    width:100% !important;
    overflow:visible !important;
  }
  .luis-photo-grid .photo-frame img{
    width:100% !important;
    height:auto !important;
    object-fit:contain !important;
    object-position:center center !important;
  }
  .luis-photo-grid .photo-caption{
    display:block !important;
    max-width:100% !important;
    padding-left:1rem !important;
    padding-right:1rem !important;
    overflow-wrap:break-word !important;
    white-space:normal !important;
  }
  .luis-stat-bar{
    grid-template-columns:1fr !important;
  }
  .luis-stat-bar .stat{
    border-right:0 !important;
    border-top:1px solid var(--rule) !important;
    padding:1.75rem 1.25rem !important;
  }
  .luis-stat-bar .stat:first-child{
    border-top:0 !important;
  }
  .luis-stat-bar .stat-n{
    font-size:clamp(2.4rem,13vw,3.25rem) !important;
    max-width:100% !important;
  }
  .luis-stat-bar .stat-l{
    font-size:clamp(.9rem,4vw,1rem) !important;
    line-height:1.55 !important;
    letter-spacing:.07em !important;
  }
}
</style>"""


def add_skip_link(content: str) -> str:
    if "id=\"lcti-accessibility\"" not in content:
        content = re.sub(r"</head>", SKIP_STYLE + "\n</head>", content, count=1, flags=re.I)
    content = apply_legibility_style(content)
    if "class=\"skip-link\"" not in content:
        content = re.sub(
            r"(<body[^>]*>)",
            r'\1\n<a class="skip-link" href="#main-content">Skip to content</a>',
            content,
            count=1,
            flags=re.I,
        )
    if 'id="main-content"' not in content:
        content = re.sub(
            r"<section\b([^>]*)>",
            lambda m: "<section" + m.group(1) + ' id="main-content" tabindex="-1">',
            content,
            count=1,
            flags=re.I,
        )
    return content


def apply_legibility_style(content: str) -> str:
    if not re.search(r"</head>", content, re.I):
        return content
    if "id=\"lcti-stat-legibility\"" in content:
        return re.sub(
            r"<style id=\"lcti-stat-legibility\">.*?</style>",
            LEGIBILITY_STYLE,
            content,
            count=1,
            flags=re.I | re.S,
        )
    return re.sub(r"</head>", LEGIBILITY_STYLE + "\n</head>", content, count=1, flags=re.I)


def all_source_html_files() -> list[Path]:
    results = []
    for path in sorted(SITE_ROOT.rglob("*.html")):
        rel_parts = path.relative_to(SITE_ROOT).parts
        if rel_parts and rel_parts[0].lower() == "dist":
            continue
        if path.name.lower().endswith(".bak"):
            continue
        results.append(path)
    return results


def is_redirect_stub(content: str) -> bool:
    return bool(re.search(r'<meta\s+http-equiv=["\']refresh["\']', content, re.I))


def optimize_img_tag(tag: str) -> str:
    src_match = re.search(r'\bsrc="([^"]+)"', tag, re.I)
    if not src_match:
        return tag
    src = src_match.group(1)
    if src.startswith(("http://", "https://", "data:", "mailto:")):
        return tag

    if src in IMAGE_REPLACEMENTS and (SITE_ROOT / IMAGE_REPLACEMENTS[src]).exists():
        src = IMAGE_REPLACEMENTS[src]
        tag = re.sub(r'\bsrc="[^"]+"', f'src="{src}"', tag, count=1, flags=re.I)

    critical_classes = ("lcti-logo-emblem", "nav-emblem", "hero-img", "hero-map-image", "hero-emblem")
    is_critical = any(cls in tag for cls in critical_classes)

    new_tag = tag
    if 'decoding=' not in new_tag:
        new_tag = new_tag[:-1] + ' decoding="async">'
    if not is_critical and 'loading=' not in new_tag:
        new_tag = new_tag[:-1] + ' loading="lazy">'
    if is_critical and 'fetchpriority=' not in new_tag and any(cls in tag for cls in ("hero-img", "hero-map-image", "hero-emblem")):
        new_tag = new_tag[:-1] + ' fetchpriority="high">'

    image_path = SITE_ROOT / src
    size = local_image_size(image_path)
    if size:
        width, height = size
        if re.search(r'\swidth="[^"]*"', new_tag, re.I):
            new_tag = re.sub(r'\swidth="[^"]*"', f' width="{width}"', new_tag, count=1, flags=re.I)
        else:
            new_tag = new_tag[:-1] + f' width="{width}">'
        if re.search(r'\sheight="[^"]*"', new_tag, re.I):
            new_tag = re.sub(r'\sheight="[^"]*"', f' height="{height}"', new_tag, count=1, flags=re.I)
        else:
            new_tag = new_tag[:-1] + f' height="{height}">'
    return new_tag


def optimize_images_in_html(content: str) -> str:
    return re.sub(r"<img\b[^>]*>", lambda m: optimize_img_tag(m.group(0)), content, flags=re.I)


def replace_legacy_links(content: str) -> str:
    for old, new in LINK_REPLACEMENTS.items():
        content = content.replace(f'href="{old}"', f'href="{new}"')
    return content


MOJIBAKE_REPLACEMENTS = {
    "\u00e2\u20ac\u201d": "&mdash;",
    "\u00e2\u20ac\u201c": "&ndash;",
    "\u00e2\u20ac\u2122": "&rsquo;",
    "\u00e2\u20ac\u0153": "&ldquo;",
    "\u00e2\u20ac\u009d": "&rdquo;",
    "\u00e2\u20ac\u00a6": "&hellip;",
    "\u00e2\u2014\u008f": "&bull;",
    "\u00e2\u2013\u00be": "\u25be",
    "\u00c2\u00b7": "&middot;",
    "\u00c2\u00a0": "&nbsp;",
}


def repair_mojibake(content: str) -> str:
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        content = content.replace(bad, good)
    return content


def write_sitemap() -> None:
    urls = []
    for filename in PUBLIC_PAGES:
        path = SITE_ROOT / filename
        if not path.exists():
            continue
        priority = "1.0" if filename == "index.html" else "0.8"
        changefreq = "weekly" if filename in {"index.html", "alamo-threat-brief.html", "atb-archive.html"} else "monthly"
        urls.append(
            "  <url>\n"
            f"    <loc>{page_url(filename)}</loc>\n"
            f"    <lastmod>{path.stat().st_mtime_ns}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )
    # Use file modification dates in ISO format after building the block, keeping
    # the ordering above stable.
    sitemap_urls = []
    for filename in PUBLIC_PAGES:
        path = SITE_ROOT / filename
        if not path.exists():
            continue
        mtime = __import__("datetime").datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        priority = "1.0" if filename == "index.html" else "0.8"
        changefreq = "weekly" if filename in {"index.html", "alamo-threat-brief.html", "atb-archive.html"} else "monthly"
        sitemap_urls.append(
            "  <url>\n"
            f"    <loc>{page_url(filename)}</loc>\n"
            f"    <lastmod>{mtime}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "\n".join(sitemap_urls)
    sitemap += "\n</urlset>\n"
    (SITE_ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def write_robots() -> None:
    robots = """User-agent: *
Allow: /
Disallow: /Extra/
Disallow: /April%202026/
Disallow: /Intel%20Production/
Disallow: /Operational%20Dashboard/
Disallow: /*.bak$

Sitemap: https://libertycti.com/sitemap.xml
"""
    (SITE_ROOT / "robots.txt").write_text(robots, encoding="utf-8")


def main() -> None:
    changed = []
    public_paths = {(SITE_ROOT / filename).resolve() for filename in PUBLIC_PAGES}
    for filename in PUBLIC_PAGES:
        path = SITE_ROOT / filename
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8")
        if is_redirect_stub(old):
            continue
        new = repair_mojibake(old)
        new = replace_meta(new, filename)
        new = replace_legacy_links(new)
        new = add_skip_link(new)
        new = optimize_images_in_html(new)
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed.append(filename)

    typography_changed = []
    for path in all_source_html_files():
        if path.resolve() in public_paths:
            continue
        old = path.read_text(encoding="utf-8")
        if is_redirect_stub(old):
            continue
        new = repair_mojibake(old)
        new = apply_legibility_style(new)
        if new != old:
            path.write_text(new, encoding="utf-8")
            typography_changed.append(str(path.relative_to(SITE_ROOT)))

    write_sitemap()
    write_robots()
    print(f"Updated {len(changed)} HTML files")
    for filename in changed:
        print(f"  {filename}")
    print(f"Updated typography on {len(typography_changed)} additional HTML files")
    for filename in typography_changed:
        print(f"  {filename}")
    print("Wrote sitemap.xml and robots.txt")


if __name__ == "__main__":
    main()
