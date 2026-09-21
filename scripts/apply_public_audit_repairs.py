#!/usr/bin/env python3
"""Apply production safety, consistency, privacy, and SEO repairs to a built site artifact.

This script intentionally operates on a generated directory such as ``_site``.
It refuses to run against a Git worktree so source files cannot be deleted by
accident. The repository remains the source of truth; these changes are an
idempotent post-build overlay for the public production site.
"""

from __future__ import annotations

import argparse
import html
import json
import posixpath
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlsplit


PUBLIC_ORIGIN = "https://kingdomcircuit.com"
PUBLIC_BASE = "/"
PUBLIC_ROOT_URL = PUBLIC_ORIGIN + PUBLIC_BASE
INTERNAL_HOSTS = {
    "84lorinw-a11y.github.io",
    "kingdomcircuit.com",
    "www.kingdomcircuit.com",
}
LEGACY_BASES = ("/kingdom-circuit/", "/kingdom-circuit-test/")

# A CSP meta tag is the strongest practical policy GitHub Pages can apply from
# repository content.  Response-only directives (for example frame-ancestors)
# deliberately are not claimed here.
CSP = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; "
    "form-action 'self' https://formspree.io; frame-src 'none'; "
    "img-src 'self' data: https:; media-src 'self' https:; "
    "font-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com; "
    "connect-src 'self' https://formspree.io https://www.googletagmanager.com "
    "https://www.google-analytics.com https://*.google-analytics.com "
    "https://*.analytics.google.com; upgrade-insecure-requests"
)

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

INTERNAL_DIRS = {
    ".github", "_live", "_seo_source", "audit", "cache", "scripts",
    "tests", "workflows", "__pycache__",
}
KEEP_ROOT_JSON = {"events.json", "supplemental-events.json", "public-audit-manifest.json"}
KEEP_CONFIG = {"artists.json"}
OBSOLETE_RUNTIME_ASSETS = {
    "assets/event-image-repair-kc2050.js",
    "assets/event-image-repair-kc2100.js",
    "assets/event-image-repair.js",
    "assets/home-kaden-image-fix.js",
    "assets/home-primary-image-guard.js",
    "assets/image-fix.js",
    "assets/verified-event-artwork-guard.js",
}

# Normalized (lowercase alphanumeric) JSON keys that contain collection,
# provenance, rollout, or verification internals rather than public content.
PRIVATE_JSON_KEYS = {
    "audit", "auditverified", "authority", "bandsintownartistid",
    "bandsintowneventid", "bandsintownidentity", "bandsintownprofile",
    "bandsintownrejectedartistids", "bandsintownresolvedname",
    "collector", "confidence", "discoveredat", "discovery", "editorialnote",
    "exclusionreason", "firstseen", "imagesource", "imagesourcename",
    "imagesourceurl", "internal", "lastseen", "lastverified", "mergedids",
    "mergedintoid", "monitoringexcluded", "monitoringnote", "monitoringpriority",
    "notes", "officialimagesource", "priority", "raw", "rosterorder",
    "socialsearchenabled", "sourcename",
    "sourcepriority", "sourceregistryrosterorder", "sourceregistryverified",
    "sources", "sourceurl", "textmatchenabled", "ticketmasterattractionid",
    "ticketmasterenabled", "ticketmasternote", "topstreamingpriority",
    "trackedartist", "verificationmethod", "verifiedversion",
    "websiteregistryverified",
}

CARD_RE = re.compile(
    r'<article\b(?=[^>]*\bdata-event-card\b)[^>]*>.*?</article>', re.I | re.S
)
PAST_ROW_RE = re.compile(
    r'<article\b[^>]*class=["\'][^"\']*\bpast-show-row\b[^"\']*["\'][^>]*>.*?</article>',
    re.I | re.S,
)
ATTR_RE_TEMPLATE = r'\b{0}\s*=\s*(["\'])(.*?)\1'


def slugify(value: str) -> str:
    value = html.unescape(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def state_route_slug(code: str) -> str:
    return "pr" if code.upper() == "PR" else slugify(STATE_NAMES.get(code.upper(), code))


def plain_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def get_attr(tag_or_html: str, name: str) -> Optional[str]:
    match = re.search(ATTR_RE_TEMPLATE.format(re.escape(name)), tag_or_html, re.I | re.S)
    return html.unescape(match.group(2)) if match else None


def set_attr(tag: str, name: str, value: str) -> str:
    encoded = html.escape(value, quote=True)
    pattern = re.compile(ATTR_RE_TEMPLATE.format(re.escape(name)), re.I | re.S)
    if pattern.search(tag):
        return pattern.sub(lambda m: f'{name}="{encoded}"', tag, count=1)
    return tag[:-1] + f' {name}="{encoded}">' if tag.endswith(">") else tag


def page_web_path(rel: Path) -> str:
    posix = rel.as_posix()
    if posix == "index.html":
        return "/"
    if posix.endswith("/index.html"):
        return "/" + posix[:-10]
    return "/" + posix


def public_url_for_rel(rel: Path) -> str:
    return PUBLIC_ROOT_URL.rstrip("/") + page_web_path(rel)


def normalize_internal_url(value: str, current_rel: Optional[Path] = None) -> str:
    """Move site-owned URLs onto the production base without touching third parties."""
    raw = html.unescape(value).strip()
    if not raw or raw.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return raw
    parsed = urlsplit(raw)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return raw
    if parsed.netloc and parsed.netloc.lower() not in INTERNAL_HOSTS:
        return "https://" + raw[len("http://"):] if raw.lower().startswith("http://") else raw

    path = parsed.path
    if parsed.netloc:
        host = parsed.netloc.lower()
        if host == "84lorinw-a11y.github.io":
            for prefix in LEGACY_BASES:
                if path.startswith(prefix):
                    path = "/" + path[len(prefix):]
                    break
        path = PUBLIC_BASE + path.lstrip("/")
    elif path.startswith("/"):
        for prefix in LEGACY_BASES:
            if path.startswith(prefix):
                path = PUBLIC_BASE + path[len(prefix):]
                break
        else:
            path = PUBLIC_BASE + path.lstrip("/")
    else:
        return raw

    path = re.sub(r"/{2,}", "/", path)
    suffix = ("?" + parsed.query) if parsed.query else ""
    suffix += ("#" + parsed.fragment) if parsed.fragment else ""
    return path + suffix


def internal_target_rel(value: str, current_rel: Path) -> Optional[Path]:
    """Resolve a site-owned link/resource to its artifact path."""
    raw = html.unescape(value).strip()
    if not raw or raw.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return None
    parsed = urlsplit(raw)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc and parsed.netloc.lower() not in INTERNAL_HOSTS:
        return None

    path = unquote(parsed.path)
    if parsed.netloc:
        if parsed.netloc.lower() == "84lorinw-a11y.github.io" and path.startswith(PUBLIC_BASE):
            path = path[len(PUBLIC_BASE):]
        else:
            for prefix in LEGACY_BASES:
                if path.startswith(prefix):
                    path = path[len(prefix):]
                    break
            else:
                path = path.lstrip("/")
    elif path.startswith(PUBLIC_BASE):
        path = path[len(PUBLIC_BASE):]
    elif path.startswith("/"):
        path = path.lstrip("/")
    else:
        parent_web = page_web_path(current_rel)
        if not parent_web.endswith("/"):
            parent_web = posixpath.dirname(parent_web) + "/"
        path = posixpath.normpath(posixpath.join(parent_web.lstrip("/"), path))

    path = posixpath.normpath(path).lstrip("./")
    if path in {"", "."} or parsed.path.endswith("/"):
        return Path(path) / "index.html" if path else Path("index.html")
    candidate = Path(path)
    if candidate.suffix:
        return candidate
    return candidate / "index.html"


def target_exists(site: Path, value: str, current_rel: Path) -> bool:
    target = internal_target_rel(value, current_rel)
    return target is None or (site / target).is_file()


def set_meta(text: str, key: str, value: str, *, http_equiv: bool = False) -> str:
    attr_name = "http-equiv" if http_equiv else "name"
    if key.startswith("og:"):
        attr_name = "property"
    pattern = re.compile(
        rf'<meta\b(?=[^>]*\b(?:name|property|http-equiv)=["\']{re.escape(key)}["\'])[^>]*>',
        re.I,
    )
    match = pattern.search(text)
    if match:
        replacement = set_attr(match.group(0), "content", value)
        replacement = re.sub(
            r'\b(?:name|property|http-equiv)\s*=\s*(["\']).*?\1',
            f'{attr_name}="{html.escape(key, quote=True)}"',
            replacement,
            count=1,
            flags=re.I | re.S,
        )
        return text[:match.start()] + replacement + text[match.end():]
    tag = f'<meta {attr_name}="{html.escape(key, quote=True)}" content="{html.escape(value, quote=True)}">'
    return text.replace("</head>", tag + "</head>", 1)


def set_link(text: str, rel_value: str, href: str) -> str:
    pattern = re.compile(
        rf'<link\b(?=[^>]*\brel=["\']{re.escape(rel_value)}["\'])[^>]*>', re.I
    )
    match = pattern.search(text)
    if match:
        replacement = set_attr(match.group(0), "href", href)
        return text[:match.start()] + replacement + text[match.end():]
    return text.replace(
        "</head>",
        f'<link rel="{rel_value}" href="{html.escape(href, quote=True)}"></head>',
        1,
    )


def set_title(text: str, title: str) -> str:
    encoded = html.escape(title, quote=False)
    if re.search(r"<title\b[^>]*>.*?</title>", text, re.I | re.S):
        return re.sub(r"<title\b[^>]*>.*?</title>", f"<title>{encoded}</title>", text, count=1, flags=re.I | re.S)
    return text.replace("</head>", f"<title>{encoded}</title></head>", 1)


def set_security_meta(text: str) -> str:
    # Put the CSP first in <head>; a meta-delivered policy only governs content
    # parsed after the tag. Preserve the production indexing decision already
    # made by finalize_seo_indexing_core.
    for key in ("referrer", "Content-Security-Policy"):
        text = re.sub(
            rf'<meta\b(?=[^>]*\b(?:name|property|http-equiv)=["\']{re.escape(key)}["\'])[^>]*>\s*',
            "",
            text,
            flags=re.I,
        )
    tags = (
        f'<meta http-equiv="Content-Security-Policy" content="{html.escape(CSP, quote=True)}">'
        '<meta name="referrer" content="strict-origin-when-cross-origin">'
    )
    text = re.sub(r'(<head\b[^>]*>)', lambda match: match.group(1) + tags, text, count=1, flags=re.I)
    if not re.search(r'<meta\b(?=[^>]*\bname=["\']robots["\'])[^>]*>', text, re.I):
        text = set_meta(text, "robots", "index,follow")
    return text


def normalize_html_urls(text: str) -> str:
    attr_pattern = re.compile(r'\b(href|src|action)\s*=\s*(["\'])(.*?)\2', re.I | re.S)

    def replace_attr(match: re.Match) -> str:
        name, quote, value = match.group(1), match.group(2), match.group(3)
        normalized = normalize_internal_url(value)
        return f"{name}={quote}{html.escape(normalized, quote=True)}{quote}"

    return attr_pattern.sub(replace_attr, text)


def card_details(card: str) -> Dict[str, str]:
    opening = re.match(r"<article\b[^>]*>", card, re.I | re.S)
    heading = re.search(r"<h3\b[^>]*>(.*?)</h3>", card, re.I | re.S)
    artist_line = re.search(r'<p\b[^>]*class=["\'][^"\']*\bartist-line\b[^"\']*["\'][^>]*>(.*?)</p>', card, re.I | re.S)
    meta = {
        plain_text(label): plain_text(value)
        for label, value in re.findall(r"<dt\b[^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>", card, re.I | re.S)
    }
    event_href = ""
    for href in re.findall(r'<a\b[^>]*\bhref\s*=\s*(["\'])(.*?)\1', card, re.I | re.S):
        if "/event/" in html.unescape(href[1]):
            event_href = html.unescape(href[1])
            break
    attrs = opening.group(0) if opening else ""
    return {
        "title": plain_text(heading.group(1)) if heading else "",
        "artists_html": artist_line.group(1) if artist_line else "",
        "artists": plain_text(artist_line.group(1)) if artist_line else "",
        "date": meta.get("Date", get_attr(attrs, "data-date") or ""),
        "time": get_attr(attrs, "data-start-time") or "",
        "venue": meta.get("Venue", ""),
        "location": meta.get("Location", ""),
        "state": (get_attr(attrs, "data-state") or "").upper(),
        "type": (get_attr(attrs, "data-type") or "").lower(),
        "href": event_href,
    }


def clean_data_search(card: str) -> str:
    if not re.search(r"\bdata-search\s*=", card, re.I):
        return card
    details = card_details(card)
    value = " ".join(
        part for part in (
            details["title"], details["artists"], details["venue"], details["location"], details["date"]
        ) if part
    ).lower()
    opening = re.match(r"<article\b[^>]*>", card, re.I | re.S)
    if not opening:
        return card
    new_opening = set_attr(opening.group(0), "data-search", value)
    return new_opening + card[opening.end():]


def card_key(card: str) -> Tuple[str, str, str, str]:
    details = card_details(card)
    return (
        re.sub(r"\W+", "", details["title"].casefold()),
        details["date"].split(" - ", 1)[0].casefold(),
        re.sub(r"\s+", " ", details["location"].casefold()).strip(),
        details["time"].casefold(),
    )


def repair_cards(text: str, site: Path, rel: Path, report: Dict[str, int]) -> str:
    seen = set()

    def replace_card(match: re.Match) -> str:
        card = match.group(0)
        details = card_details(card)
        href = details["href"]
        if href and not target_exists(site, href, rel):
            report["brokenEventCardsRemoved"] += 1
            return ""
        key = card_key(card)
        if all(key[:3]) and key in seen:
            report["duplicateEventCardsRemoved"] += 1
            return ""
        if all(key[:3]):
            seen.add(key)
        return clean_data_search(card)

    return CARD_RE.sub(replace_card, text)


def repair_past_rows(text: str, site: Path, rel: Path, report: Dict[str, int]) -> str:
    def replace_row(match: re.Match) -> str:
        row = match.group(0)
        event_links = [
            html.unescape(value)
            for _, value in re.findall(r'<a\b[^>]*\bhref\s*=\s*(["\'])(.*?)\1', row, re.I | re.S)
            if "/event/" in html.unescape(value)
        ]
        if event_links and not target_exists(site, event_links[0], rel):
            report["brokenPastRowsRemoved"] += 1
            return ""
        return row

    text = PAST_ROW_RE.sub(replace_row, text)
    count = len(PAST_ROW_RE.findall(text))
    label = f"{count} archived {'show' if count == 1 else 'shows'}"
    return re.sub(
        r'(<span\b[^>]*class=["\'][^"\']*\bpast-count\b[^"\']*["\'][^>]*>).*?(</span>)',
        lambda m: m.group(1) + label + m.group(2),
        text,
        flags=re.I | re.S,
    )


def strip_source_exposure(text: str, report: Dict[str, int]) -> str:
    patterns = [
        r'<p\b[^>]*class=["\'][^"\']*\bsource-line\b[^"\']*["\'][^>]*>.*?</p>',
        r'<div\b[^>]*>\s*<dt\b[^>]*>\s*Source\s*</dt>\s*<dd\b[^>]*>.*?</dd>\s*</div>',
        r'<p\b[^>]*class=["\'][^"\']*\bseo-roster-note\b[^"\']*["\'][^>]*>.*?</p>',
    ]
    for pattern in patterns:
        text, count = re.subn(pattern, "", text, flags=re.I | re.S)
        report["sourceNodesRemoved"] += count
    text, count = re.subn(
        r'(<a\b[^>]*>)\s*Original event source\s*(</a>)',
        r'\1Official details\2',
        text,
        flags=re.I,
    )
    report["sourceLabelsReplaced"] += count
    text, count = re.subn(
        r"confirm with the official source before traveling\.?",
        "confirm with the official organizer or ticket provider before traveling.",
        text,
        flags=re.I,
    )
    report["sourceLabelsReplaced"] += count
    text, count = re.subn(
        r"confirmed by an official festival or event source\.?",
        "confirmed by the official festival organizer or venue.",
        text,
        flags=re.I,
    )
    report["sourceLabelsReplaced"] += count
    public_copy_replacements = (
        (r"\bofficial event or ticket source\b", "official organizer or ticket provider"),
        (r"\bofficial festival or event source\b", "official festival organizer or venue"),
        (r"\bofficial sources\b", "official accounts and listings"),
        (r"\bofficial source\b", "official listing"),
    )
    for pattern, replacement in public_copy_replacements:
        text, count = re.subn(pattern, replacement, text, flags=re.I)
        report["sourceLabelsReplaced"] += count
    return text


def strip_obsolete_asset_references(text: str, report: Dict[str, int]) -> str:
    names = "|".join(re.escape(Path(path).name) for path in sorted(OBSOLETE_RUNTIME_ASSETS))
    text, count = re.subn(
        rf'<script\b(?=[^>]*\bsrc\s*=\s*["\'][^"\']*(?:{names})(?:\?[^"\']*)?["\'])[^>]*>\s*</script>',
        "",
        text,
        flags=re.I | re.S,
    )
    report["obsoleteRuntimeTagsRemoved"] += count
    text, comment_count = re.subn(
        rf'<!--(?:(?!-->).)*(?:{names})(?:(?!-->).)*-->',
        "",
        text,
        flags=re.I | re.S,
    )
    report["obsoleteRuntimeCommentsRemoved"] += comment_count
    return text


def repair_remaining_anchors(text: str, site: Path, rel: Path, report: Dict[str, int]) -> str:
    pattern = re.compile(r'<a\b[^>]*\bhref\s*=\s*(["\'])(.*?)\1[^>]*>', re.I | re.S)

    def replace_anchor(match: re.Match) -> str:
        tag = match.group(0)
        href = html.unescape(match.group(2))
        if target_exists(site, href, rel):
            return tag
        target = internal_target_rel(href, rel)
        if target is None:
            return tag
        posix = target.as_posix()
        if posix.startswith("artists/"):
            fallback = PUBLIC_BASE + "artists/"
        elif posix.startswith("event/") or posix.startswith("shows/"):
            fallback = PUBLIC_BASE + "shows/"
        else:
            fallback = PUBLIC_BASE
        report["brokenLinksReplaced"] += 1
        return set_attr(tag, "href", fallback)

    return pattern.sub(replace_anchor, text)


def repair_broken_images(text: str, site: Path, rel: Path, report: Dict[str, int]) -> str:
    pattern = re.compile(r'<img\b[^>]*\bsrc\s*=\s*(["\'])(.*?)\1[^>]*>', re.I | re.S)

    def replace_image(match: re.Match) -> str:
        tag = match.group(0)
        src = html.unescape(match.group(2))
        if target_exists(site, src, rel):
            return tag
        if internal_target_rel(src, rel) is None:
            return tag
        report["brokenImagesReplaced"] += 1
        tag = set_attr(tag, "src", PUBLIC_BASE + "assets/event-fallback.webp")
        return re.sub(r'\s+srcset\s*=\s*(["\']).*?\1', "", tag, flags=re.I | re.S)

    return pattern.sub(replace_image, text)


def repair_broken_srcsets(text: str, site: Path, rel: Path, report: Dict[str, int]) -> str:
    pattern = re.compile(r'\s+srcset\s*=\s*(["\'])(.*?)\1', re.I | re.S)

    def replace_srcset(match: re.Match) -> str:
        kept = []
        removed = 0
        for candidate in match.group(2).split(","):
            candidate = html.unescape(candidate.strip())
            if not candidate:
                continue
            pieces = candidate.split()
            url = pieces[0]
            if repair_target := internal_target_rel(url, rel):
                if not (site / repair_target).is_file():
                    removed += 1
                    continue
            kept.append(" ".join([url] + pieces[1:]))
        report["brokenSrcsetCandidatesRemoved"] += removed
        if not kept:
            return ""
        encoded = html.escape(", ".join(kept), quote=True)
        return f' srcset="{encoded}"'

    return pattern.sub(replace_srcset, text)


def cards_in(text: str) -> List[Dict[str, str]]:
    return [card_details(card) for card in CARD_RE.findall(text)]


def plural_show(count: int) -> str:
    return f"{count} {'show' if count == 1 else 'shows'}"


def replace_result_counts(text: str, cards: Sequence[Dict[str, str]], report: Dict[str, int]) -> str:
    count = len(cards)
    pattern = re.compile(
        r'(<p\b(?=[^>]*class=["\'][^"\']*\bresults-count\b)[^>]*>).*?(</p>)',
        re.I | re.S,
    )

    def replacement(match: re.Match) -> str:
        if re.search(r"\bdata-artist-count\b", match.group(1), re.I):
            return match.group(0)
        current = plain_text(match.group(0))
        desired = plural_show(count)
        if current != desired:
            report["countsUpdated"] += 1
        return match.group(1) + desired + match.group(2)

    return pattern.sub(replacement, text)


def artist_occurrences(cards: Sequence[Dict[str, str]]) -> List[Tuple[str, Optional[str], int]]:
    counts: Counter = Counter()
    hrefs: Dict[str, Optional[str]] = {}
    labels: Dict[str, str] = {}
    order: List[str] = []
    for card in cards:
        raw = card.get("artists_html", "")
        linked: Dict[str, str] = {}
        for _, href, inner in re.findall(r'<a\b[^>]*\bhref\s*=\s*(["\'])(.*?)\1[^>]*>(.*?)</a>', raw, re.I | re.S):
            label = plain_text(inner)
            if label:
                linked[label.casefold()] = html.unescape(href)
        rendered = re.sub(r"<a\b[^>]*>(.*?)</a>", lambda m: plain_text(m.group(1)), raw, flags=re.I | re.S)
        names = [
            plain_text(piece)
            for piece in re.split(r"\s*(?:,|·|\|)\s*|\s+-\s+", plain_text(rendered))
        ]
        for name in names:
            if not name:
                continue
            key = name.casefold()
            if key not in counts:
                order.append(key)
                labels[key] = name
                hrefs[key] = linked.get(key)
            counts[key] += 1
    return [(labels[key], hrefs.get(key), counts[key]) for key in order]


def rebuild_location_strip(text: str, cards: Sequence[Dict[str, str]], site: Path, rel: Path) -> str:
    if len(rel.parts) == 3 and rel.parts[0] == "artists" and "seo-artist-profile" in text:
        # repair_artist_profile already produced artist-specific state links.
        return text
    section_re = re.compile(
        r'<section\b[^>]*class=["\'][^"\']*\bseo-location-strip\b[^"\']*["\'][^>]*>.*?</section>',
        re.I | re.S,
    )
    match = section_re.search(text)
    if not match:
        return text
    section = match.group(0)
    eyebrow_match = re.search(r'<p\b[^>]*class=["\'][^"\']*\beyebrow\b[^"\']*["\'][^>]*>(.*?)</p>', section, re.I | re.S)
    eyebrow = plain_text(eyebrow_match.group(1)).casefold() if eyebrow_match else ""
    chip_row_match = re.search(r'(<div\b[^>]*class=["\'][^"\']*\bseo-chip-row\b[^"\']*["\'][^>]*>).*?(</div>)', section, re.I | re.S)
    if not chip_row_match:
        return text

    chips: List[str] = []
    if "artist" in eyebrow:
        for label, href, count in artist_occurrences(cards):
            body = f"{html.escape(label)} <span>{count}</span>"
            if href and target_exists(site, href, rel):
                chips.append(f'<a class="seo-chip" href="{html.escape(href, quote=True)}">{body}</a>')
            else:
                chips.append(f'<span class="seo-chip seo-chip-static" data-count="{count}">{body}</span>')
    elif "cities" in eyebrow:
        city_counts: Counter = Counter()
        city_labels: Dict[str, str] = {}
        state_code = next((card["state"] for card in cards if card.get("state")), "")
        state_name = STATE_NAMES.get(state_code, state_code)
        for card in cards:
            city = card.get("location", "").split(",", 1)[0].strip()
            if city:
                key = city.casefold()
                city_counts[key] += 1
                city_labels.setdefault(key, city)
        for key, count in city_counts.items():
            label = city_labels[key]
            suffix = "pr" if state_code == "PR" else slugify(state_name)
            route = PUBLIC_BASE + "shows/" + slugify(label) + "-" + suffix + "/"
            if target_exists(site, route, rel):
                chips.append(f'<a class="seo-chip" href="{route}">{html.escape(label)} <span>{count}</span></a>')
            else:
                chips.append(f'<span class="seo-chip seo-chip-static" data-count="{count}">{html.escape(label)} <span>{count}</span></span>')
    else:
        state_counts = Counter(card["state"] for card in cards if card.get("state"))
        for code, count in sorted(state_counts.items(), key=lambda item: STATE_NAMES.get(item[0], item[0])):
            name = STATE_NAMES.get(code, code)
            route = PUBLIC_BASE + "shows/" + state_route_slug(code) + "/"
            if target_exists(site, route, rel):
                chips.append(f'<a class="seo-chip" href="{route}">{html.escape(name)} <span>{count}</span></a>')
            else:
                chips.append(f'<span class="seo-chip seo-chip-static" data-count="{count}">{html.escape(name)} <span>{count}</span></span>')

    if not chips:
        return text[:match.start()] + "" + text[match.end():]
    new_section = (
        section[:chip_row_match.start()]
        + chip_row_match.group(1)
        + "".join(chips)
        + chip_row_match.group(2)
        + section[chip_row_match.end():]
    )
    return text[:match.start()] + new_section + text[match.end():]


def repair_artist_profile(text: str, cards: Sequence[Dict[str, str]], site: Path, rel: Path, report: Dict[str, int]) -> str:
    if "seo-artist-profile" not in text:
        return text
    heading = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, re.I | re.S)
    artist = plain_text(heading.group(1)) if heading else "This artist"
    artist = re.sub(r"\s+Concerts\s*&\s*Tour Dates.*$", "", artist, flags=re.I)
    count = len(cards)
    states = Counter(card["state"] for card in cards if card.get("state"))
    festivals = sum(1 for card in cards if card.get("type") == "festival")

    for label, value in (("Upcoming shows", count), ("States", len(states)), ("Festivals", festivals)):
        pattern = re.compile(rf'(<span>\s*{re.escape(label)}\s*</span>\s*<strong>).*?(</strong>)', re.I | re.S)
        text, changed = pattern.subn(lambda m, v=value: m.group(1) + str(v) + m.group(2), text, count=1)
        report["countsUpdated"] += changed

    first = cards[0] if cards else None
    if first:
        summary = (
            f"Kingdom Circuit currently lists {plural_show(count)} for {artist} across "
            f"{len(states)} {'state' if len(states) == 1 else 'states'}."
        )
        if first.get("date") and first.get("location"):
            summary += f" The next confirmed appearance is {first['date']} in {first['location']}."
        href = first.get("href") or (PUBLIC_BASE + "shows/")
        next_show = (
            '<div class="seo-next-show"><span>Next show</span><strong>'
            f'<a class="seo-next-show-link text-link" href="{html.escape(href, quote=True)}" '
            f'aria-label="Open next show">{html.escape(first.get("date") or "See details")}<br>'
            f'<span>{html.escape(first.get("location") or "Location to be announced")}</span></a>'
            "</strong></div>"
        )
    else:
        summary = f"No upcoming U.S. shows are currently confirmed for {artist}."
        next_show = '<div class="seo-next-show"><span>Next show</span><strong>No confirmed date</strong></div>'

    text = re.sub(
        r'(<p\b[^>]*class=["\'][^"\']*\bseo-artist-summary\b[^"\']*["\'][^>]*>).*?(</p>)',
        lambda m: m.group(1) + html.escape(summary) + m.group(2), text, count=1, flags=re.I | re.S,
    )
    text = re.sub(
        r'<div\b[^>]*class=["\'][^"\']*\bseo-next-show\b[^"\']*["\'][^>]*>.*?</strong></div>',
        next_show, text, count=1, flags=re.I | re.S,
    )

    select_re = re.compile(r'(<select\b[^>]*\bdata-artist-state-filter\b[^>]*>).*?(</select>)', re.I | re.S)
    options = ['<option value="">All states</option>']
    for code in sorted(states, key=lambda item: STATE_NAMES.get(item, item)):
        options.append(f'<option value="{html.escape(code, quote=True)}">{html.escape(STATE_NAMES.get(code, code))}</option>')
    text = select_re.sub(lambda m: m.group(1) + "".join(options) + m.group(2), text, count=1)

    # Base artist profiles browse states. Artist/state pages browse cities and
    # are handled by the generic strip rebuilder.
    if len(rel.parts) == 3 and rel.parts[0] == "artists":
        section_re = re.compile(
            r'<section\b[^>]*class=["\'][^"\']*\bseo-location-strip\b[^"\']*["\'][^>]*>.*?</section>',
            re.I | re.S,
        )
        section_match = section_re.search(text)
        if section_match:
            section = section_match.group(0)
            row = re.search(r'(<div\b[^>]*class=["\'][^"\']*\bseo-chip-row\b[^"\']*["\'][^>]*>).*?(</div>)', section, re.I | re.S)
            chips = []
            artist_slug = rel.parts[1]
            for code in sorted(states, key=lambda item: STATE_NAMES.get(item, item)):
                name = STATE_NAMES.get(code, code)
                route = PUBLIC_BASE + f"artists/{artist_slug}/{state_route_slug(code)}/"
                if target_exists(site, route, rel):
                    chips.append(f'<a class="seo-chip" href="{route}">{html.escape(name)} <span>{states[code]}</span></a>')
                else:
                    chips.append(f'<span class="seo-chip seo-chip-static" data-count="{states[code]}">{html.escape(name)} <span>{states[code]}</span></span>')
            if row and chips:
                replacement = section[:row.start()] + row.group(1) + "".join(chips) + row.group(2) + section[row.end():]
                text = text[:section_match.start()] + replacement + text[section_match.end():]
            elif section_match and not chips:
                text = text[:section_match.start()] + text[section_match.end():]
    return text


def repair_location_summary(text: str, cards: Sequence[Dict[str, str]]) -> str:
    count = len(cards)
    cities = {card["location"].split(",", 1)[0].strip().casefold() for card in cards if card.get("location")}

    def update_hero(match: re.Match) -> str:
        body = match.group(2)
        if "verified upcoming" not in plain_text(body).casefold():
            return match.group(0)
        body = re.sub(r"\b(Browse|Find)\s+\d+\s+verified upcoming\b", lambda m: f"{m.group(1)} {count} verified upcoming", body, count=1, flags=re.I)
        body = re.sub(r"\bacross\s+\d+\s+([^.<]*?)\bcities\b", lambda m: f"across {len(cities)} {m.group(1)}{'city' if len(cities) == 1 else 'cities'}", body, count=1, flags=re.I)
        if count == 1:
            body = re.sub(r"\bshows\b", "show", body, count=1, flags=re.I)
        elif count != 1:
            body = re.sub(r"\bshow\b", "shows", body, count=1, flags=re.I)
        return match.group(1) + body + match.group(3)

    return re.sub(
        r'(<p\b[^>]*class=["\'][^"\']*\bhero-text\b[^"\']*["\'][^>]*>)(.*?)(</p>)',
        update_hero, text, count=1, flags=re.I | re.S,
    )


def repair_artist_directory_count(text: str, report: Dict[str, int]) -> str:
    artist_count = len(re.findall(r"\bdata-artist-card\b", text, re.I))
    if not re.search(r"\bdata-artist-count\b", text, re.I):
        return text
    label = f"{artist_count} {'artist' if artist_count == 1 else 'artists'}"
    text, changed = re.subn(
        r'(<p\b(?=[^>]*\bdata-artist-count\b)[^>]*>).*?(</p>)',
        lambda m: m.group(1) + label + m.group(2), text, flags=re.I | re.S,
    )
    report["countsUpdated"] += changed
    return text


def event_page_fields(text: str) -> Dict[str, str]:
    h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, re.I | re.S)
    details = {
        plain_text(label): plain_text(value)
        for label, value in re.findall(r"<dt\b[^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>", text, re.I | re.S)
    }
    media = re.search(
        r'<div\b[^>]*class=["\'][^"\']*\bevent-detail-media\b[^"\']*["\'][^>]*>.*?</div>',
        text, re.I | re.S,
    )
    image_tag = re.search(r"<img\b[^>]*>", media.group(0), re.I | re.S) if media else None
    image = get_attr(image_tag.group(0), "src") if image_tag else ""
    if not image:
        schema_image = re.search(r'"image"\s*:\s*(?:\[\s*)?"([^"]+)"', html.unescape(text), re.I)
        image = schema_image.group(1) if schema_image else ""
    return {
        "title": plain_text(h1.group(1)) if h1 else "Event",
        "date": details.get("Date", "Date to be announced"),
        "venue": details.get("Venue", ""),
        "location": details.get("Location", "Location to be announced"),
        "image": image,
    }


def absolute_image_url(image_url: str, rel: Path) -> str:
    if not image_url:
        return ""
    normalized = normalize_internal_url(image_url, rel)
    parsed = urlsplit(normalized)
    if parsed.scheme in {"http", "https"}:
        return normalized
    if normalized.startswith(PUBLIC_BASE):
        return PUBLIC_ORIGIN + normalized
    if normalized.startswith("/"):
        return PUBLIC_ORIGIN + PUBLIC_BASE + normalized.lstrip("/")
    base = page_web_path(rel)
    joined = posixpath.normpath(posixpath.join(base, normalized))
    return PUBLIC_ORIGIN + PUBLIC_BASE.rstrip("/") + "/" + joined.lstrip("/")


def merged_target(text: str) -> str:
    match = re.search(r"""location\.replace\(\s*(["'])(.*?)\1\s*\)""", text, re.I | re.S)
    if match:
        return normalize_internal_url(html.unescape(match.group(2)))
    if "Merged listing" in text:
        match = re.search(r'<a\b[^>]*\bhref\s*=\s*(["\'])(.*?)\1[^>]*>\s*View (?:the )?canonical event', text, re.I | re.S)
        if match:
            return normalize_internal_url(html.unescape(match.group(2)))
    return ""


def repair_merged_page(text: str, rel: Path, report: Dict[str, int]) -> Tuple[str, str]:
    target = merged_target(text)
    if not target:
        return text, ""
    absolute = PUBLIC_ORIGIN + target if target.startswith("/") else target
    text = set_link(text, "canonical", absolute)
    text = set_meta(text, "og:url", absolute)
    text = set_meta(text, "robots", "noindex,nofollow")
    text = re.sub(
        r"""location\.replace\(\s*(["']).*?\1\s*\)""",
        lambda _: f'location.replace("{target}")', text, count=1, flags=re.I | re.S,
    )
    report["mergedRedirectPagesRepaired"] += 1
    return text, target


def repair_event_page(text: str, rel: Path, used_titles: Dict[str, Path], report: Dict[str, int]) -> str:
    fields = event_page_fields(text)
    title = f"{fields['title']} — {fields['location']} — {fields['date']} | Kingdom Circuit"
    folded = plain_text(title).casefold()
    if folded in used_titles:
        qualifier = fields.get("venue") or rel.parent.name[-6:]
        title = f"{fields['title']} — {fields['location']} — {fields['date']} — {qualifier} | Kingdom Circuit"
        folded = plain_text(title).casefold()
    if folded in used_titles:
        title = title.replace(" | Kingdom Circuit", f" — {rel.parent.name[-6:]} | Kingdom Circuit")
        folded = plain_text(title).casefold()
    used_titles[folded] = rel
    text = set_title(text, title)
    text = set_meta(text, "og:title", title)
    text = set_meta(text, "twitter:title", title)
    image_url = absolute_image_url(fields.get("image", ""), rel)
    if image_url and not re.search(r"(?:logo-wordmark|event-fallback)", image_url, re.I):
        text = set_meta(text, "og:image", image_url)
        text = set_meta(text, "twitter:image", image_url)
        report["eventSocialImagesUpdated"] += 1
    report["eventTitlesUpdated"] += 1
    return text


def sanitize_json_value(value):
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if normalized in PRIVATE_JSON_KEYS or normalized.startswith("internal"):
                continue
            cleaned[key] = sanitize_json_value(item)
        return cleaned
    if isinstance(value, str) and value.lower().startswith("http://"):
        return "https://" + value[len("http://"):]
    return value


def sanitize_public_json(site: Path, report: Dict[str, int]) -> None:
    for rel in (Path("events.json"), Path("supplemental-events.json"), Path("config/artists.json")):
        path = site / rel
        if not path.is_file():
            continue
        before = path.read_text(encoding="utf-8")
        payload = json.loads(before)
        cleaned = sanitize_json_value(payload)
        after = json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n"
        if after != before:
            path.write_text(after, encoding="utf-8")
            report["publicJsonFilesSanitized"] += 1


def clean_artifact(site: Path, report: Dict[str, int]) -> None:
    for name in sorted(INTERNAL_DIRS):
        path = site / name
        if path.is_symlink() or path.is_file():
            path.unlink()
            report["operationalFilesRemoved"] += 1
        elif path.is_dir():
            report["operationalFilesRemoved"] += sum(1 for child in path.rglob("*") if child.is_file())
            shutil.rmtree(path)

    for path in list(site.iterdir()):
        if not path.is_file():
            continue
        lower = path.name.lower()
        remove = False
        if path.name.startswith(".") and path.name != ".nojekyll":
            remove = True
        elif path.suffix.lower() in {".md", ".py", ".yml", ".yaml"}:
            remove = True
        elif path.suffix.lower() == ".txt" and path.name != "robots.txt":
            remove = True
        elif path.suffix.lower() == ".json" and path.name not in KEEP_ROOT_JSON:
            remove = True
        elif lower in {"package.json", "package-lock.json"}:
            remove = True
        if remove:
            path.unlink()
            report["operationalFilesRemoved"] += 1

    config = site / "config"
    if config.is_dir():
        for path in list(config.iterdir()):
            if path.name not in KEEP_CONFIG:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                report["operationalFilesRemoved"] += 1

    for rel in sorted(OBSOLETE_RUNTIME_ASSETS):
        path = site / rel
        if path.is_file() or path.is_symlink():
            path.unlink()
            report["obsoleteRuntimeAssetsRemoved"] += 1


def patch_runtime_javascript(site: Path, report: Dict[str, int]) -> None:
    path = site / "app.js"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    replacements = (
        '<p class="source-line">Source: ${esc(sourceText(event))}</p>',
        '<div><dt>Source</dt><dd>${esc(sourceText(event))}</dd></div>',
    )
    for fragment in replacements:
        count = text.count(fragment)
        if count:
            text = text.replace(fragment, "")
            report["runtimeSourceFragmentsRemoved"] += count
    text, count = re.subn(
        r'^\s*"(?:officialImageSource|sourceRegistryRosterOrder|sourceRegistryVerified)"\s*:\s*.*?\s*,?\s*$',
        "",
        text,
        flags=re.I | re.M,
    )
    report["runtimePrivateRegistryFieldsRemoved"] += count
    text = text.replace(
        "// Artist source registry imported from Book4.xlsx. Only rows marked Verified are enriched.",
        "// Public artist directory metadata.",
    )
    text = re.sub(r'^const RUN_STATUS_URL\s*=.*?;\s*\n', "", text, count=1, flags=re.M)
    text = text.replace('  if (artist?.sourceRegistryVerified !== true) return "";\n', "")
    text = text.replace(
        '  if (artist.sourceRegistryVerified !== true) return { url: "", fallbackUrl: "", position: "center" };',
        '  if (!artist) return { url: "", fallbackUrl: "", position: "center" };',
    )
    text = text.replace(
        '? { ...merged, imageUrl, imageSource: "Verified Spotify artist profile" }',
        "? { ...merged, imageUrl }",
    )
    text = text.replace(
        "const search = [event.title, event.venue, event.city, event.state, event.sourceName, ...(event.artists || [])]",
        "const search = [event.title, event.venue, event.city, event.state, ...(event.artists || [])]",
    )
    runtime_copy_replacements = (
        (r"\bofficial event or ticket source\b", "official organizer or ticket provider"),
        (r"\bofficial festival or event source\b", "official festival organizer or venue"),
        (r"\bofficial sources\b", "official accounts and listings"),
        (r"\bofficial source\b", "official listing"),
        (r"\bEvery source is reviewed before it goes live\b", "Every submission is reviewed before it goes live"),
    )
    for pattern, replacement in runtime_copy_replacements:
        text, count = re.subn(pattern, replacement, text, flags=re.I)
        report["sourceLabelsReplaced"] += count
    text = re.sub(
        r'(?P<quote>["\'])http://(?P<url>[^"\']+)(?P=quote)',
        lambda match: match.group("quote") + "https://" + match.group("url") + match.group("quote"),
        text,
    )
    static_guard = '''  const staticExperience = document.querySelector(
    '[data-seo-enhanced-directory], .seo-artist-profile, .event-detail-section:not([data-event-detail]), [data-submission-form]'
  ) || document.body?.dataset.page === "404";
  if (staticExperience) {
    setupSubmissionForm();
    return;
  }
'''
    static_marker = "  try {\n    const [liveEvents, liveArtists, supplemental] = await Promise.all(["
    if "const staticExperience = document.querySelector(" not in text and static_marker in text:
        text = text.replace(static_marker, static_guard + static_marker, 1)
        report["staticPageDataLoadsRemoved"] += 1
    text, count = re.subn(
        r"function sourceText\(event\)\s*\{.*?\}\s*",
        "",
        text,
        count=1,
        flags=re.S,
    )
    report["runtimeSourceHelpersRemoved"] += count
    # The status endpoint is an operational report and is intentionally absent
    # from the public artifact. Keep the optional footer region hidden instead
    # of requesting a file that no longer exists.
    text, count = re.subn(
        r'async function renderCalendarStatus\(\)\s*\{.*?\n\}(?=\nfunction setMenuOpen)',
        'async function renderCalendarStatus() {\n  const root = document.querySelector("[data-calendar-status]");\n  if (root) root.hidden = true;\n}',
        text,
        count=1,
        flags=re.S,
    )
    report["runtimeOperationalStatusFetchesRemoved"] += count
    path.write_text(text, encoding="utf-8")

    # Other retained runtime helpers can also contain visitor-facing copy.
    # Normalize that copy across every public script without changing the
    # internal data-processing identifiers those helpers rely on.
    public_script_replacements = (
        (r"\bofficial event or ticket source\b", "official organizer or ticket provider"),
        (r"\bofficial festival or event source\b", "official festival organizer or venue"),
        (r"\bofficial sources\b", "official accounts and listings"),
        (r"\bofficial source\b", "official listing"),
        (r"\bsupporting source\b", "supporting link"),
        (r"\bEvery source is reviewed before it goes live\b", "Every submission is reviewed before it goes live"),
    )
    for script in sorted(site.rglob("*.js")):
        script_text = script.read_text(encoding="utf-8")
        original = script_text
        for pattern, replacement in public_script_replacements:
            script_text, count = re.subn(pattern, replacement, script_text, flags=re.I)
            report["sourceLabelsReplaced"] += count
        if script_text != original:
            script.write_text(script_text, encoding="utf-8")


def canonical_from_html(text: str) -> str:
    match = re.search(r'<link\b(?=[^>]*\brel=["\']canonical["\'])[^>]*>', text, re.I)
    return get_attr(match.group(0), "href") if match else ""


def eligible_sitemap_entries(site: Path) -> List[str]:
    urls = []
    excluded = {Path("404.html"), Path("event/index.html"), Path("artists/profile/index.html")}
    for path in sorted(site.rglob("*.html")):
        rel = path.relative_to(site)
        if rel in excluded:
            continue
        text = path.read_text(encoding="utf-8")
        robots_tag = re.search(
            r'<meta\b(?=[^>]*\bname=["\']robots["\'])[^>]*>', text, re.I
        )
        robots = get_attr(robots_tag.group(0), "content") if robots_tag else ""
        if "noindex" in {part.strip().casefold() for part in robots.split(",")}:
            continue
        canonical = canonical_from_html(text)
        expected = public_url_for_rel(rel)
        if canonical == expected:
            urls.append(canonical)
    return sorted(set(urls))


def write_sitemap(site: Path) -> int:
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    root = ET.Element(f"{{{namespace}}}urlset")
    urls = eligible_sitemap_entries(site)
    for url in urls:
        node = ET.SubElement(root, f"{{{namespace}}}url")
        ET.SubElement(node, f"{{{namespace}}}loc").text = url
    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:  # Python 3.8 compatibility
        pass
    tree.write(site / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    return len(urls)


def validate_target(site: Path) -> None:
    if not site.is_dir() or not (site / "index.html").is_file():
        raise SystemExit(f"Not a built site artifact: {site}")
    if (site / ".git").exists():
        raise SystemExit("Refusing to modify a Git worktree. Pass a generated artifact such as _site.")
    try:
        Path(__file__).resolve().relative_to(site.resolve())
    except ValueError:
        return
    raise SystemExit("Refusing to remove files from the directory containing this repair script.")


def apply_repairs(site: Path) -> Dict[str, object]:
    validate_target(site)
    counters: Dict[str, int] = Counter()
    clean_artifact(site, counters)
    sanitize_public_json(site, counters)
    patch_runtime_javascript(site, counters)

    used_event_titles: Dict[str, Path] = {}
    merged_pages: List[str] = []
    for path in sorted(site.rglob("*.html")):
        rel = path.relative_to(site)
        text = path.read_text(encoding="utf-8")
        text = normalize_html_urls(text)
        if canonical_from_html(text) and rel != Path("404.html"):
            text = set_link(text, "canonical", public_url_for_rel(rel))
        text = set_security_meta(text)
        text = strip_obsolete_asset_references(text, counters)
        text = strip_source_exposure(text, counters)
        text = repair_cards(text, site, rel, counters)
        text = repair_past_rows(text, site, rel, counters)
        text = repair_remaining_anchors(text, site, rel, counters)
        text = repair_broken_images(text, site, rel, counters)
        text = repair_broken_srcsets(text, site, rel, counters)
        cards = cards_in(text)
        text = replace_result_counts(text, cards, counters)
        text = repair_artist_directory_count(text, counters)
        text = repair_artist_profile(text, cards, site, rel, counters)
        text = rebuild_location_strip(text, cards, site, rel)
        text = repair_location_summary(text, cards)
        text, merged = repair_merged_page(text, rel, counters)
        if merged:
            merged_pages.append(rel.as_posix())
        elif len(rel.parts) == 3 and rel.parts[0] == "event" and rel.name == "index.html":
            text = repair_event_page(text, rel, used_event_titles, counters)
        path.write_text(text, encoding="utf-8")

    sitemap_count = write_sitemap(site)
    manifest: Dict[str, object] = {
        "schemaVersion": 1,
        "mode": "production-post-build-repair",
        "siteBase": PUBLIC_BASE,
        "sitemapPolicy": "complete self-canonical production site",
        "htmlPageCount": sum(1 for _ in site.rglob("*.html")),
        "sitemapUrlCount": sitemap_count,
        "mergedRedirectPages": sorted(merged_pages),
        "repairs": dict(sorted(counters.items())),
        "httpHeaderLimitation": (
            "GitHub Pages cannot set repository-defined response headers; CSP and referrer policy are HTML meta protections."
        ),
    }
    (site / "public-audit-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?", default="_site", type=Path, help="built site artifact (default: _site)")
    args = parser.parse_args(argv)
    manifest = apply_repairs(args.site.resolve())
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
