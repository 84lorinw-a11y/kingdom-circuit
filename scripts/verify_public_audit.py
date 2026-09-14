#!/usr/bin/env python3
"""Verify the post-build Kingdom Circuit production safety and parity contract."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

import apply_public_audit_repairs as repair


class Audit:
    def __init__(self) -> None:
        self.failures: List[str] = []
        self.checks = 0

    def expect(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(message)


def meta_content(text: str, key: str) -> str:
    pattern = re.compile(
        rf'<meta\b(?=[^>]*\b(?:name|property|http-equiv)=["\']{re.escape(key)}["\'])[^>]*>',
        re.I,
    )
    match = pattern.search(text)
    return repair.get_attr(match.group(0), "content") or "" if match else ""


def title_text(text: str) -> str:
    match = re.search(r"<title\b[^>]*>(.*?)</title>", text, re.I | re.S)
    return repair.plain_text(match.group(1)) if match else ""


def iter_json_keys(value, prefix: str = "") -> Iterable[Tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            yield dotted, re.sub(r"[^a-z0-9]", "", str(key).casefold())
            yield from iter_json_keys(child, dotted)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_json_keys(child, f"{prefix}[{index}]")


def verify_operational_cleanup(site: Path, audit: Audit) -> None:
    for name in sorted(repair.INTERNAL_DIRS):
        audit.expect(not (site / name).exists(), f"internal directory remains: {name}")
    for path in site.iterdir():
        if not path.is_file():
            continue
        lower = path.name.lower()
        forbidden = (
            (path.name.startswith(".") and path.name != ".nojekyll")
            or path.suffix.lower() in {".md", ".py", ".yml", ".yaml"}
            or (path.suffix.lower() == ".txt" and path.name != "robots.txt")
            or (path.suffix.lower() == ".json" and path.name not in repair.KEEP_ROOT_JSON)
            or lower in {"package.json", "package-lock.json"}
        )
        audit.expect(not forbidden, f"operational root file remains: {path.name}")
    config = site / "config"
    if config.is_dir():
        for path in config.iterdir():
            audit.expect(path.name in repair.KEEP_CONFIG, f"internal config remains: config/{path.name}")
    for rel in sorted(repair.OBSOLETE_RUNTIME_ASSETS):
        audit.expect(not (site / rel).exists(), f"obsolete runtime image override remains: {rel}")

    cname = site / "CNAME"
    audit.expect(cname.is_file(), "production CNAME is missing")
    if cname.is_file():
        audit.expect(cname.read_text(encoding="utf-8").strip() == "kingdomcircuit.com", "production CNAME is wrong")
    robots = site / "robots.txt"
    audit.expect(robots.is_file(), "production robots.txt is missing")
    if robots.is_file():
        robots_text = robots.read_text(encoding="utf-8")
        audit.expect("Allow: /" in robots_text, "production robots.txt does not allow crawling")
        audit.expect("Disallow: /" not in robots_text, "production robots.txt blocks the entire site")

    for rel in (Path("events.json"), Path("supplemental-events.json"), Path("config/artists.json")):
        path = site / rel
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            audit.expect(False, f"invalid public JSON {rel}: {exc}")
            continue
        for dotted, normalized in iter_json_keys(payload):
            audit.expect(
                normalized not in repair.PRIVATE_JSON_KEYS and not normalized.startswith("internal"),
                f"private JSON field remains in {rel}: {dotted}",
            )
        audit.expect('"http://' not in json.dumps(payload), f"insecure URL remains in {rel}")


def verify_source_exposure(rel: Path, text: str, audit: Audit) -> None:
    forbidden = {
        "visible source-line": r'class=["\'][^"\']*\bsource-line\b',
        "Source detail row": r"<dt\b[^>]*>\s*Source\s*</dt>",
        "roster provenance note": r'class=["\'][^"\']*\bseo-roster-note\b',
        "legacy source link label": r">\s*Original event source\s*<",
        "generic source footer": r"confirm with the official source before traveling",
        "festival source note": r"confirmed by an official festival or event source",
        "official-source copy": r"\bofficial source(?:s)?\b|\bofficial event or ticket source\b",
        "roster status text": r"Roster data\s*:",
    }
    for label, pattern in forbidden.items():
        audit.expect(not re.search(pattern, text, re.I | re.S), f"{rel}: {label} remains")
    for obsolete in repair.OBSOLETE_RUNTIME_ASSETS:
        audit.expect(Path(obsolete).name not in text, f"{rel}: references obsolete image override {obsolete}")

    for card in repair.CARD_RE.findall(text):
        if re.search(r"\bdata-search\s*=", card, re.I):
            audit.expect(repair.clean_data_search(card) == card, f"{rel}: data-search includes non-display/source data")


def verify_security(rel: Path, text: str, audit: Audit) -> None:
    robots = {part.strip().casefold() for part in meta_content(text, "robots").split(",")}
    audit.expect(bool({"index", "noindex"} & robots), f"{rel}: production robots meta lacks an indexing directive")
    audit.expect(bool({"follow", "nofollow"} & robots), f"{rel}: production robots meta lacks a link directive")
    if rel == Path("index.html"):
        audit.expect({"index", "follow"}.issubset(robots), "homepage is not index,follow")
    audit.expect(
        meta_content(text, "referrer") == "strict-origin-when-cross-origin",
        f"{rel}: missing strict referrer meta policy",
    )
    csp = meta_content(text, "Content-Security-Policy")
    for directive in (
        "default-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self' https://formspree.io",
        "https://www.googletagmanager.com",
        "https://*.google-analytics.com",
        "https://*.analytics.google.com",
        "upgrade-insecure-requests",
    ):
        audit.expect(directive in csp, f"{rel}: CSP is missing {directive!r}")
    audit.expect("G-TEST-DISABLED" not in text, f"{rel}: test analytics marker remains")
    head = re.search(r"<head\b[^>]*>(.*?)</head>", text, re.I | re.S)
    if head:
        csp_position = head.group(1).find("Content-Security-Policy")
        first_resource = min(
            (position for position in (
                head.group(1).find("<script"),
                head.group(1).find("<link"),
            ) if position >= 0),
            default=len(head.group(1)),
        )
        audit.expect(0 <= csp_position < first_resource, f"{rel}: CSP meta appears after a loadable resource")


def verify_internal_attributes(site: Path, rel: Path, text: str, audit: Audit) -> None:
    pattern = re.compile(r'\b(href|src|action)\s*=\s*(["\'])(.*?)\2', re.I | re.S)
    for match in pattern.finditer(text):
        attr = match.group(1).lower()
        value = html.unescape(match.group(3)).strip()
        parsed = urlsplit(value)
        if value.startswith("//"):
            continue
        if not parsed.scheme and parsed.path.startswith("/"):
            audit.expect(
                parsed.path.startswith(repair.PUBLIC_BASE),
                f"{rel}: {attr} escapes production base: {value}",
            )
        if parsed.netloc.lower() in {"kingdomcircuit.com", "www.kingdomcircuit.com"}:
            audit.expect(
                not parsed.path.startswith("/kingdom-circuit-test/"),
                f"{rel}: site-owned {attr} points at the test path: {value}",
            )
        if parsed.scheme == "http":
            audit.expect(False, f"{rel}: insecure external {attr}: {value}")
        target = repair.internal_target_rel(value, rel)
        if target is not None:
            audit.expect((site / target).is_file(), f"{rel}: broken internal {attr}: {value} -> {target}")

    # srcset URLs are checked separately because one attribute can hold several.
    for _, value in re.findall(r'\bsrcset\s*=\s*(["\'])(.*?)\1', text, re.I | re.S):
        for candidate in value.split(","):
            url = html.unescape(candidate.strip().split(" ", 1)[0])
            if not url:
                continue
            parsed = urlsplit(url)
            if not parsed.scheme and parsed.path.startswith("/"):
                audit.expect(parsed.path.startswith(repair.PUBLIC_BASE), f"{rel}: srcset escapes production base: {url}")
            target = repair.internal_target_rel(url, rel)
            if target is not None:
                audit.expect((site / target).is_file(), f"{rel}: broken internal srcset: {url} -> {target}")


def parse_number(value: str) -> Optional[int]:
    match = re.search(r"\b(\d+)\b", repair.plain_text(value))
    return int(match.group(1)) if match else None


def verify_counts(rel: Path, text: str, audit: Audit) -> None:
    cards = repair.cards_in(text)
    event_count = len(cards)
    # Deferred directory cards live in a JSON text payload until the visitor
    # asks to show all artists. Only actual article elements are displayed.
    artist_count = len(
        re.findall(r'<article\b(?=[^>]*\bdata-artist-card\b)', text, re.I)
    )
    for match in re.finditer(
        r'<p\b(?=[^>]*class=["\'][^"\']*\bresults-count\b)[^>]*>.*?</p>', text, re.I | re.S
    ):
        expected = artist_count if re.search(r"\bdata-artist-count\b", match.group(0), re.I) else event_count
        audit.expect(parse_number(match.group(0)) == expected, f"{rel}: displayed result count does not equal {expected}")

    if "seo-artist-profile" in text:
        expected_stats = {
            "Upcoming shows": event_count,
            "States": len({card["state"] for card in cards if card.get("state")}),
            "Festivals": sum(1 for card in cards if card.get("type") == "festival"),
        }
        for label, expected in expected_stats.items():
            match = re.search(rf'<span>\s*{re.escape(label)}\s*</span>\s*<strong>(.*?)</strong>', text, re.I | re.S)
            audit.expect(bool(match), f"{rel}: missing artist stat {label}")
            if match:
                audit.expect(parse_number(match.group(1)) == expected, f"{rel}: {label} stat does not equal {expected}")
        summary = re.search(r'class=["\'][^"\']*\bseo-artist-summary\b[^"\']*["\'][^>]*>(.*?)</p>', text, re.I | re.S)
        audit.expect(bool(summary), f"{rel}: missing artist summary")
        if summary and event_count:
            audit.expect(parse_number(summary.group(1)) == event_count, f"{rel}: artist summary count does not equal {event_count}")
        select = re.search(r'<select\b[^>]*\bdata-artist-state-filter\b[^>]*>(.*?)</select>', text, re.I | re.S)
        if select:
            actual_states = {
                html.unescape(code).upper()
                for _, code in re.findall(r'<option\b[^>]*\bvalue\s*=\s*(["\'])(.*?)\1', select.group(1), re.I | re.S)
                if code
            }
            expected_states = {card["state"] for card in cards if card.get("state")}
            audit.expect(actual_states == expected_states, f"{rel}: artist state filter does not match surviving cards")

    hero = re.search(r'class=["\'][^"\']*\bhero-text\b[^"\']*["\'][^>]*>(.*?)</p>', text, re.I | re.S)
    if hero and "verified upcoming" in repair.plain_text(hero.group(1)).casefold():
        match = re.search(r"\b(?:Find|Browse)\s+(\d+)\s+verified upcoming\b", repair.plain_text(hero.group(1)), re.I)
        audit.expect(bool(match) and int(match.group(1)) == event_count, f"{rel}: hero count does not equal {event_count}")
        city_match = re.search(r"\bacross\s+(\d+)\s+.*?\bcit(?:y|ies)\b", repair.plain_text(hero.group(1)), re.I)
        if city_match:
            cities = {card["location"].split(",", 1)[0].strip().casefold() for card in cards if card.get("location")}
            audit.expect(int(city_match.group(1)) == len(cities), f"{rel}: hero city count does not equal {len(cities)}")

    rows = len(repair.PAST_ROW_RE.findall(text))
    past_count = re.search(r'class=["\'][^"\']*\bpast-count\b[^"\']*["\'][^>]*>(.*?)</span>', text, re.I | re.S)
    if past_count:
        audit.expect(parse_number(past_count.group(1)) == rows, f"{rel}: archived show count does not equal {rows}")

    keys = [repair.card_key(card) for card in repair.CARD_RE.findall(text)]
    populated = [key for key in keys if all(key)]
    audit.expect(len(populated) == len(set(populated)), f"{rel}: duplicate visible event cards remain")

    strip = re.search(
        r'<section\b[^>]*class=["\'][^"\']*\bseo-location-strip\b[^"\']*["\'][^>]*>(.*?)</section>',
        text,
        re.I | re.S,
    )
    if strip:
        eyebrow_match = re.search(r'class=["\'][^"\']*\beyebrow\b[^"\']*["\'][^>]*>(.*?)</p>', strip.group(1), re.I | re.S)
        eyebrow = repair.plain_text(eyebrow_match.group(1)).casefold() if eyebrow_match else ""
        expected: Counter = Counter()
        if "artist" in eyebrow:
            expected.update({label.casefold(): count for label, _, count in repair.artist_occurrences(cards)})
        elif "cities" in eyebrow:
            expected.update(
                card["location"].split(",", 1)[0].strip().casefold()
                for card in cards
                if card.get("location")
            )
        else:
            expected.update(repair.STATE_NAMES.get(card["state"], card["state"]).casefold() for card in cards if card.get("state"))

        actual: Counter = Counter()
        for match in re.finditer(
            r'<a\b[^>]*class=["\'][^"\']*\bseo-chip\b[^"\']*["\'][^>]*>(.*?)<span>(\d+)</span>\s*</a>',
            strip.group(1), re.I | re.S,
        ):
            actual[repair.plain_text(match.group(1)).casefold()] = int(match.group(2))
        for match in re.finditer(
            r'<span\b(?=[^>]*class=["\'][^"\']*\bseo-chip-static\b)(?=[^>]*\bdata-count=["\'](\d+)["\'])[^>]*>(.*?)<span>\d+</span>\s*</span>',
            strip.group(1), re.I | re.S,
        ):
            actual[repair.plain_text(match.group(2)).casefold()] = int(match.group(1))
        audit.expect(actual == expected, f"{rel}: location/artist summary chips do not match surviving cards")


def verify_runtime(site: Path, audit: Audit) -> None:
    for path in site.rglob("*.js"):
        rel = path.relative_to(site)
        text = path.read_text(encoding="utf-8")
        audit.expect('class="source-line"' not in text, f"{rel}: can still render source-line")
        audit.expect("<dt>Source</dt>" not in text, f"{rel}: can still render a Source detail row")
        audit.expect("Roster data:" not in text, f"{rel}: can still render roster provenance")
        audit.expect(
            not re.search(
                r"\bofficial source(?:s)?\b|\bofficial event or ticket source\b|\bsupporting source\b|\bEvery source is reviewed\b",
                text,
                re.I,
            ),
            f"{rel}: can still render source-attribution copy",
        )
        for field_match in re.finditer(r'["\']([A-Za-z_$][A-Za-z0-9_$]*)["\']\s*:', text):
            field = field_match.group(1)
            normalized = re.sub(r"[^a-z0-9]", "", field.casefold())
            audit.expect(
                normalized not in repair.PRIVATE_JSON_KEYS and not normalized.startswith("internal"),
                f"{rel}: embeds private field {field}",
            )
        audit.expect(
            not re.search(r'["\']http://[^"\']+["\']', text, re.I),
            f"{rel}: embeds an insecure external URL",
        )
    app = site / "app.js"
    if app.is_file():
        text = app.read_text(encoding="utf-8")
        audit.expect("function sourceText(" not in text, "app.js retains unused source helper")
        audit.expect("RUN_STATUS_URL" not in text and "run-status.json" not in text, "app.js requests removed operational status data")
        audit.expect(
            "const staticExperience = document.querySelector(" in text,
            "app.js still loads all JSON data on fully static pages",
        )


def verify_event_pages(site: Path, pages: Dict[Path, str], audit: Audit) -> None:
    used_titles: Dict[str, Path] = {}
    for rel, text in pages.items():
        if len(rel.parts) != 3 or rel.parts[0] != "event" or rel.name != "index.html":
            continue
        merged = repair.merged_target(text)
        canonical = repair.canonical_from_html(text)
        if merged:
            absolute = repair.PUBLIC_ORIGIN + merged if merged.startswith("/") else merged
            audit.expect(canonical == absolute, f"{rel}: merged page canonical does not point to redirect target")
            target = repair.internal_target_rel(merged, rel)
            audit.expect(target is not None and (site / target).is_file(), f"{rel}: merged redirect target is missing")
            continue

        fields = repair.event_page_fields(text)
        title = title_text(text)
        audit.expect(fields["location"] in title, f"{rel}: event title lacks location")
        audit.expect(fields["date"] in title, f"{rel}: event title lacks date")
        folded = title.casefold()
        audit.expect(folded not in used_titles, f"{rel}: duplicate event title also used by {used_titles.get(folded)}")
        used_titles[folded] = rel
        audit.expect(meta_content(text, "og:title") == title, f"{rel}: og:title does not match unique title")
        audit.expect(meta_content(text, "twitter:title") == title, f"{rel}: twitter:title does not match unique title")

        image = repair.absolute_image_url(fields.get("image", ""), rel)
        if image and not re.search(r"(?:logo-wordmark|event-fallback)", image, re.I):
            audit.expect(meta_content(text, "og:image") == image, f"{rel}: og:image is not the event image")
            audit.expect(meta_content(text, "twitter:image") == image, f"{rel}: twitter:image is not the event image")
        if "event-detail" in text:
            audit.expect(re.search(r">\s*Official details\s*</a>", text, re.I) is not None, f"{rel}: Official details link was lost")
            audit.expect("G-N2KK9XF4TJ" in text, f"{rel}: production analytics tag is missing")


def verify_canonicals_and_sitemap(site: Path, pages: Dict[Path, str], audit: Audit) -> None:
    merged_count = 0
    for rel, text in pages.items():
        canonical = repair.canonical_from_html(text)
        if not canonical:
            audit.expect(rel == Path("404.html"), f"{rel}: canonical is missing")
            continue
        if repair.merged_target(text):
            merged_count += 1
        else:
            audit.expect(canonical == repair.public_url_for_rel(rel), f"{rel}: canonical is not self/production based: {canonical}")

    sitemap = site / "sitemap.xml"
    audit.expect(sitemap.is_file(), "sitemap.xml is missing")
    if sitemap.is_file():
        try:
            root = ET.parse(sitemap).getroot()
            actual = [node.text.strip() for node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc") if node.text]
        except (ET.ParseError, OSError) as exc:
            audit.expect(False, f"sitemap.xml is invalid: {exc}")
            actual = []
        expected = repair.eligible_sitemap_entries(site)
        audit.expect(len(actual) == len(set(actual)), "sitemap.xml contains duplicate URLs")
        audit.expect(set(actual) == set(expected), f"sitemap coverage mismatch: expected {len(expected)}, got {len(actual)}")
        for url in actual:
            audit.expect(url.startswith(repair.PUBLIC_ROOT_URL), f"sitemap URL escapes production origin/base: {url}")

    manifest_path = site / "public-audit-manifest.json"
    audit.expect(manifest_path.is_file(), "public-audit-manifest.json is missing")
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            audit.expect(False, f"public audit manifest is invalid: {exc}")
        else:
            audit.expect(manifest.get("siteBase") == repair.PUBLIC_BASE, "manifest siteBase is wrong")
            audit.expect(manifest.get("mode") == "production-post-build-repair", "manifest mode is wrong")
            audit.expect(manifest.get("sitemapUrlCount") == len(repair.eligible_sitemap_entries(site)), "manifest sitemap count is stale")
            audit.expect(len(manifest.get("mergedRedirectPages", [])) == merged_count, "manifest merged redirect count is stale")


def verify_requested_live_repairs(pages: Dict[Path, str], audit: Audit) -> None:
    home = pages.get(Path("index.html"), "")
    kurtis_portraits = []
    for card in repair.CARD_RE.findall(home):
        if "Kurtis Hoppie" not in card:
            continue
        image = re.search(r'<img\b[^>]*class=["\'][^"\']*\bartist-photo\b[^"\']*["\'][^>]*>', card, re.I | re.S)
        if image:
            kurtis_portraits.append(image.group(0))
    audit.expect(bool(kurtis_portraits), "homepage has no Kurtis Hoppie portrait card")
    for image in kurtis_portraits:
        audit.expect("object-position:50% 4%" in image, "homepage Kurtis Hoppie portrait crop regressed")

    jimmy = pages.get(Path("artists/jimmy-rock/index.html"), "")
    jimmy_cards = repair.CARD_RE.findall(jimmy)
    audit.expect(len(jimmy_cards) >= 4, "Jimmy Rock profile is missing repaired show listings")
    for card in jimmy_cards:
        image = re.search(r"<img\b[^>]*>", card, re.I | re.S)
        tag = image.group(0) if image else ""
        audit.expect("event-artwork" in tag, "a Jimmy Rock show is not using event artwork")
        audit.expect("/assets/optimized/" in tag, "a Jimmy Rock show image is not optimized locally")

    expected_assets = {
        Path("event/one-day-fall-festival-2026-2026-10-10-aurora-587532/index.html"):
            "/assets/events/petrina-delacey-one-day-2026.jpg",
        Path("event/reign-volume-one-2026-10-10-brooklyn-fe93fe/index.html"):
            "/assets/events/reign-volume-one-single-2026.jpg",
    }
    for rel, asset in expected_assets.items():
        text = pages.get(rel, "")
        audit.expect(bool(text), f"requested repaired event page is missing: {rel}")
        audit.expect(asset in text, f"{rel}: requested replacement artwork is missing")
        media = re.search(
            r'<div\b[^>]*class=["\'][^"\']*\bevent-detail-media\b[^"\']*["\'][^>]*>(.*?)</div>',
            text,
            re.I | re.S,
        )
        image_count = len(re.findall(r"<img\b", media.group(1), re.I)) if media else 0
        audit.expect(image_count == 1, f"{rel}: expected exactly one primary event image")

    mayia_links = {
        Path("event/boxyard-saturdaze-2026-10-10-durham-7853b4/index.html"): "boxyard.rtp.org",
        Path("event/mayia-at-the-nc-state-fair-2026-10-17-raleigh-1c07ad/index.html"): "ncagr.gov",
    }
    for rel, expected_host in mayia_links.items():
        text = pages.get(rel, "")
        official = re.search(
            r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>\s*Official details\s*</a>',
            text,
            re.I | re.S,
        )
        href = html.unescape(official.group(1)) if official else ""
        audit.expect(expected_host in urlsplit(href).netloc.casefold(), f"{rel}: MAYIA Official details destination regressed")
        audit.expect("mayiawarren.org/go/bandsintown" not in href, f"{rel}: MAYIA redirect link returned")


def verify_site(site: Path) -> Audit:
    audit = Audit()
    audit.expect(site.is_dir(), f"site directory is missing: {site}")
    audit.expect((site / "index.html").is_file(), "site index.html is missing")
    if not site.is_dir():
        return audit

    verify_operational_cleanup(site, audit)
    pages: Dict[Path, str] = {}
    for path in sorted(site.rglob("*.html")):
        rel = path.relative_to(site)
        text = path.read_text(encoding="utf-8")
        pages[rel] = text
        audit.expect("kingdom-circuit-test" not in text, f"{rel}: test-site path remains")
        verify_source_exposure(rel, text, audit)
        verify_security(rel, text, audit)
        verify_internal_attributes(site, rel, text, audit)
        verify_counts(rel, text, audit)
    verify_runtime(site, audit)
    verify_event_pages(site, pages, audit)
    verify_canonicals_and_sitemap(site, pages, audit)
    verify_requested_live_repairs(pages, audit)
    return audit


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?", default="_site", type=Path, help="repaired site artifact (default: _site)")
    args = parser.parse_args(argv)
    audit = verify_site(args.site.resolve())
    if audit.failures:
        print(f"FAIL: {len(audit.failures)} issue(s) across {audit.checks} checks", file=sys.stderr)
        for failure in audit.failures[:200]:
            print(f"- {failure}", file=sys.stderr)
        if len(audit.failures) > 200:
            print(f"- ... {len(audit.failures) - 200} more", file=sys.stderr)
        return 1
    print(f"PASS: production artifact satisfies {audit.checks} audit checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
