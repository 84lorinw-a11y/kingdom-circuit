#!/usr/bin/env python3
"""Collect future U.S. shows from tracked artists' official websites.

This is intentionally conservative. It checks the verified artist website, follows
likely tour/show/event links on that same domain, and follows explicit Bandsintown
artist pages when they are configured or exposed by the official website.
Structured event data is preferred; failures are recorded without blocking the run.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from update_events import (
    ARTISTS_FILE,
    CollectorError,
    HttpClient,
    PageContentParser,
    build_alias_lookup,
    collect_bandsintown_public_source,
    collect_jsonld_source_from_html,
    event_is_future,
    iso_z,
    load_json,
    merge_events,
    normalize_name,
    now_utc,
    robots_allows,
    safe_url,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "artist-website-events.json"
STATUS_FILE = ROOT / "artist-website-status.json"

SKIP_HOSTS = {
    "google.com", "www.google.com", "instagram.com", "www.instagram.com",
    "spotify.com", "open.spotify.com", "youtube.com", "www.youtube.com",
    "music.youtube.com", "facebook.com", "www.facebook.com", "x.com", "twitter.com",
    "wikipedia.org", "en.wikipedia.org", "music.apple.com", "apple.com", "www.apple.com",
}
TOUR_TERMS = ("tour", "show", "shows", "event", "events", "concert", "concerts", "live", "tickets")
BANDSINTOWN_RE = re.compile(
    r"https?://(?:www\.)?bandsintown\.com/a/[A-Za-z0-9%._~!$&'()*+,;=:@/?-]+",
    re.I,
)


def eligible_website(artist: dict) -> str:
    url = safe_url(artist.get("website"))
    if not url:
        return ""
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":", 1)[0]
    if host in SKIP_HOSTS or host.endswith(".wikipedia.org"):
        return ""
    if "google." in host or not parsed.scheme.startswith("http"):
        return ""
    return url


def website_source(artist: dict, url: str, name_suffix: str = "official website") -> dict:
    return {
        "name": f"{artist.get('name', 'Artist')} {name_suffix}",
        "url": url,
        "parser": "artist_website",
        "artist": str(artist.get("name") or "").strip(),
        "authority": "artist_calendar",
        "priority": 74,
        "imagePolicy": "ignore",
        "musicConfirmed": True,
        "softFail": True,
    }


def candidate_internal_pages(base_url: str, html: str) -> list[str]:
    page = PageContentParser()
    page.feed(html)
    base = urlparse(base_url)
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for href, text in page.links:
        absolute = safe_url(urljoin(base_url, href))
        if not absolute or absolute in seen:
            continue
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != base.netloc.lower():
            continue
        haystack = normalize_name(f"{parsed.path} {text}")
        score = sum(1 for term in TOUR_TERMS if term in haystack)
        if score <= 0:
            continue
        seen.add(absolute)
        scored.append((score, absolute))
    scored.sort(key=lambda item: (-item[0], len(urlparse(item[1]).path)))
    return [url for _, url in scored[:2]]


def bandsintown_profiles(artist: dict, html: str, base_url: str) -> list[str]:
    urls: list[str] = []
    configured = safe_url(artist.get("bandsintownProfile"))
    if configured:
        urls.append(configured)

    normalized_html = html.replace("\\u002F", "/").replace("\\/", "/")
    urls.extend(BANDSINTOWN_RE.findall(normalized_html))

    page = PageContentParser()
    page.feed(html)
    for href, _ in page.links:
        absolute = safe_url(urljoin(base_url, href))
        if absolute and "bandsintown.com" in urlparse(absolute).netloc.lower() and "/a/" in urlparse(absolute).path:
            urls.append(absolute)

    result: list[str] = []
    seen: set[str] = set()
    for url in urls:
        clean = url.split("#", 1)[0]
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result[:3]


def hidden_bandsintown_event_urls(html: str, profile_url: str) -> list[str]:
    normalized = html.replace("\\u002F", "/").replace("\\/", "/")
    found: list[str] = []
    seen: set[str] = set()
    patterns = [
        r"https?://(?:www\.)?bandsintown\.com/e/[A-Za-z0-9%._~!$&'()*+,;=:@/?-]+",
        r"[\"'](/e/\d+[A-Za-z0-9%._~!$&'()*+,;=:@/?-]*)",
    ]
    for pattern in patterns:
        for raw in re.findall(pattern, normalized, flags=re.I):
            absolute = safe_url(urljoin(profile_url, raw))
            if absolute and absolute not in seen:
                seen.add(absolute)
                found.append(absolute)
    return found[:60]


def collect_bandsintown_profile(source: dict, profile_url: str, html: str, client: HttpClient, alias_lookup: dict[str, str], checked_at: str) -> list[dict]:
    events = collect_bandsintown_public_source(source, profile_url, html, client, alias_lookup, checked_at)
    for event_url in hidden_bandsintown_event_urls(html, profile_url):
        try:
            if not robots_allows(event_url):
                continue
            detail_html = client.get_text(event_url)
            events.extend(collect_jsonld_source_from_html(source, event_url, detail_html, alias_lookup, checked_at))
        except CollectorError:
            continue
    return merge_events(events)


def collect_artist(artist: dict, client: HttpClient, alias_lookup: dict[str, str], checked_at: str) -> tuple[list[dict], list[str]]:
    website = eligible_website(artist)
    if not website:
        return [], []

    warnings: list[str] = []
    events: list[dict] = []
    try:
        if not robots_allows(website):
            return [], [f"{artist.get('name')}: robots.txt blocked {website}"]
        html = client.get_text(website)
    except CollectorError as exc:
        return [], [f"{artist.get('name')}: {exc}"]

    source = website_source(artist, website)
    events.extend(collect_jsonld_source_from_html(source, website, html, alias_lookup, checked_at))

    for page_url in candidate_internal_pages(website, html):
        try:
            if not robots_allows(page_url):
                continue
            page_html = client.get_text(page_url)
            page_source = website_source(artist, page_url, "official tour page")
            events.extend(collect_jsonld_source_from_html(page_source, page_url, page_html, alias_lookup, checked_at))
            for profile in bandsintown_profiles(artist, page_html, page_url):
                try:
                    if robots_allows(profile):
                        profile_html = client.get_text(profile)
                        bit_source = website_source(artist, profile, "official Bandsintown calendar")
                        events.extend(collect_bandsintown_profile(bit_source, profile, profile_html, client, alias_lookup, checked_at))
                except CollectorError as exc:
                    warnings.append(f"{artist.get('name')} Bandsintown: {exc}")
        except CollectorError as exc:
            warnings.append(f"{artist.get('name')} tour page: {exc}")

    for profile in bandsintown_profiles(artist, html, website):
        try:
            if not robots_allows(profile):
                continue
            profile_html = client.get_text(profile)
            bit_source = website_source(artist, profile, "official Bandsintown calendar")
            events.extend(collect_bandsintown_profile(bit_source, profile, profile_html, client, alias_lookup, checked_at))
        except CollectorError as exc:
            warnings.append(f"{artist.get('name')} Bandsintown: {exc}")

    today = now_utc().date()
    return merge_events(event for event in events if event_is_future(event, today)), warnings


def main() -> int:
    checked_at = iso_z(now_utc())
    artists = [
        item for item in load_json(ARTISTS_FILE, [])
        if isinstance(item, dict) and item.get("enabled", True)
    ]
    alias_lookup = build_alias_lookup(artists)
    client = HttpClient(min_interval_seconds=float(os.getenv("ARTIST_WEBSITE_MIN_INTERVAL", "0.20")))
    limit = int(os.getenv("ARTIST_WEBSITE_LIMIT", "0") or 0)
    if limit > 0:
        artists = artists[:limit]

    collected: list[dict] = []
    warnings: list[str] = []
    sites_checked = 0
    artists_with_events = 0

    for artist in artists:
        if not eligible_website(artist):
            continue
        sites_checked += 1
        artist_events, artist_warnings = collect_artist(artist, client, alias_lookup, checked_at)
        warnings.extend(artist_warnings)
        if artist_events:
            artists_with_events += 1
            collected.extend(artist_events)
        print(f"Artist website: {artist.get('name')}: {len(artist_events)} event(s)")

    events = merge_events(collected)
    write_json(OUTPUT_FILE, events)
    write_json(STATUS_FILE, {
        "generatedAt": checked_at,
        "artistsConfigured": len(artists),
        "officialWebsitesChecked": sites_checked,
        "artistsWithEvents": artists_with_events,
        "eventsFound": len(events),
        "warningCount": len(warnings),
        "warnings": warnings[:100],
        "mode": "all-tracked-artists-official-website-scan",
    })
    print(f"Artist website scan complete: websites={sites_checked}, events={len(events)}, warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
