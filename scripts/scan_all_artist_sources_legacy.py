#!/usr/bin/env python3
"""Expanded all-artist discovery pass for Kingdom Circuit.

This complements update_events.py by checking every enabled artist against
additional public discovery surfaces, with Bandsintown as the primary universal
fallback. It also checks Songkick when robots.txt allows it, scans configured
official websites, and best-effort Spotify artist profiles already present in
config/artists.json.

New non-festival events are published only after the existing Kingdom Circuit
normalization/finalization rules accept them. Festival discoveries that still
need an official lineup source are written to full-scan-candidates.json instead
of being published automatically.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

from update_events import (
    HttpClient,
    PageContentParser,
    artist_image_map,
    artist_image_positions,
    collect_jsonld_source_from_html,
    events_are_duplicates,
    finalize_events,
    load_json,
    merge_events,
    normalize_name,
    preferred_artist_images,
    robots_allows,
    safe_url,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
ATTRACTION_CACHE_FILE = ROOT / "cache" / "ticketmaster-attractions.json"
STATUS_FILE = ROOT / "full-scan-status.json"
CANDIDATES_FILE = ROOT / "full-scan-candidates.json"

TICKET_HOSTS = (
    "ticketmaster.com",
    "eventbrite.com",
    "axs.com",
    "dice.fm",
    "tixr.com",
    "seetickets.us",
    "seetickets.com",
    "etix.com",
    "eventim.com",
    "ticketweb.com",
    "humanitix.com",
)

SOCIAL_OR_STREAMING_HOSTS = (
    "instagram.com",
    "facebook.com",
    "youtube.com",
    "youtu.be",
    "spotify.com",
    "music.apple.com",
    "linktr.ee",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_alias_lookup(artists: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for artist in artists:
        if not artist.get("enabled", True):
            continue
        canonical = str(artist.get("name") or "").strip()
        if not canonical:
            continue
        for raw in [canonical, *artist.get("aliases", [])]:
            key = normalize_name(str(raw))
            if key:
                lookup[key] = canonical
    return lookup


def artist_aliases(artist: dict[str, Any]) -> set[str]:
    values = {
        normalize_name(str(artist.get("name") or "")),
        *(normalize_name(str(value)) for value in artist.get("aliases", [])),
    }
    return {value for value in values if value}


def page_artist_matches(page: PageContentParser, artist: dict[str, Any]) -> bool:
    aliases = artist_aliases(artist)
    headings = [normalize_name(text) for tag, text in page.headings if tag == "h1" and text]
    if any(value in aliases for value in headings):
        return True
    title = normalize_name(page.meta.get("og:title", ""))
    if any(alias and (title == alias or title.startswith(alias + " ")) for alias in aliases):
        return True
    return False


def link_score(target: str, label: str, path_slug: str) -> float:
    label_norm = normalize_name(label)
    slug_norm = normalize_name(path_slug.replace("-", " "))
    scores = [
        SequenceMatcher(None, target, label_norm).ratio() if label_norm else 0.0,
        SequenceMatcher(None, target, slug_norm).ratio() if slug_norm else 0.0,
    ]
    if label_norm == target or slug_norm == target:
        scores.append(1.0)
    return max(scores)


def find_artist_page(
    search_url: str,
    html: str,
    artist: dict[str, Any],
    path_pattern: re.Pattern[str],
) -> str:
    page = PageContentParser()
    page.feed(html)
    target = normalize_name(str(artist.get("name") or ""))
    candidates: list[tuple[float, str]] = []

    for href, label in page.links:
        absolute = safe_url(urljoin(search_url, href))
        if not absolute:
            continue
        match = path_pattern.search(urlparse(absolute).path)
        if not match:
            continue
        slug = match.group(1) if match.lastindex else ""
        candidates.append((link_score(target, label, slug), absolute))

    # Some client-rendered search pages expose useful hrefs in HTML before the
    # anchor text is assembled. Keep a conservative regex fallback.
    if not candidates:
        for href in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I):
            absolute = safe_url(urljoin(search_url, href))
            if not absolute:
                continue
            match = path_pattern.search(urlparse(absolute).path)
            if not match:
                continue
            slug = match.group(1) if match.lastindex else ""
            candidates.append((link_score(target, "", slug), absolute))

    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    score, url = candidates[0]
    return url if score >= 0.72 else ""


def source_record(name: str, url: str, artist: str, authority: str = "artist_calendar", priority: int = 72) -> dict[str, Any]:
    return {
        "name": name,
        "url": url,
        "artist": artist,
        "authority": authority,
        "priority": priority,
        "musicConfirmed": True,
        "softFail": True,
        "imagePolicy": "ignore",
    }


def collect_ticket_corroboration(
    event_url: str,
    event_html: str,
    artist_name: str,
    alias_lookup: dict[str, str],
    checked_at: str,
    client: HttpClient,
) -> list[dict[str, Any]]:
    page = PageContentParser()
    page.feed(event_html)
    urls: list[str] = []
    seen: set[str] = set()
    for href, _ in page.links:
        absolute = safe_url(urljoin(event_url, href))
        if not absolute or absolute in seen:
            continue
        host = urlparse(absolute).netloc.lower()
        if not any(token in host for token in TICKET_HOSTS):
            continue
        seen.add(absolute)
        urls.append(absolute)

    events: list[dict[str, Any]] = []
    for ticket_url in urls[:2]:
        try:
            if not robots_allows(ticket_url):
                continue
            html = client.get_text(ticket_url)
            source = source_record(
                f"{artist_name} ticket corroboration",
                ticket_url,
                artist_name,
                authority="venue_ticket",
                priority=94,
            )
            events.extend(collect_jsonld_source_from_html(
                source, ticket_url, html, alias_lookup, checked_at
            ))
        except Exception:
            continue
    return events


def collect_bandsintown_for_artist(
    artist: dict[str, Any],
    client: HttpClient,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    name = str(artist.get("name") or "").strip()
    search_url = f"https://www.bandsintown.com/search?q={quote_plus(name)}"
    result: dict[str, Any] = {"artist": name, "source": "Bandsintown", "status": "unmatched", "eventsFound": 0}
    try:
        if not robots_allows(search_url):
            result["status"] = "blocked_by_robots"
            return [], result
        search_html = client.get_text(search_url)
        artist_url = find_artist_page(
            search_url,
            search_html,
            artist,
            re.compile(r"/a/\d+(?:-([^/?#]+))?", re.I),
        )
        if not artist_url:
            return [], result
        if not robots_allows(artist_url):
            result["status"] = "blocked_by_robots"
            return [], result
        artist_html = client.get_text(artist_url)
        artist_page = PageContentParser()
        artist_page.feed(artist_html)
        if not page_artist_matches(artist_page, artist):
            result["status"] = "identity_mismatch"
            result["artistUrl"] = artist_url
            return [], result

        event_urls: list[str] = []
        seen: set[str] = set()
        for href, _ in artist_page.links:
            absolute = safe_url(urljoin(artist_url, href))
            if not absolute or absolute in seen:
                continue
            if not re.search(r"/e/\d+", urlparse(absolute).path):
                continue
            seen.add(absolute)
            event_urls.append(absolute)

        source = source_record(f"{name} Bandsintown all-artist scan", artist_url, name, priority=74)
        events: list[dict[str, Any]] = []
        for event_url in event_urls[:25]:
            try:
                if not robots_allows(event_url):
                    continue
                detail_html = client.get_text(event_url)
                events.extend(collect_jsonld_source_from_html(
                    source, event_url, detail_html, alias_lookup, checked_at
                ))
                events.extend(collect_ticket_corroboration(
                    event_url, detail_html, name, alias_lookup, checked_at, client
                ))
            except Exception:
                continue

        events = merge_events(events)
        result.update({
            "status": "ok",
            "artistUrl": artist_url,
            "eventsFound": len(events),
            "eventPagesChecked": len(event_urls[:25]),
        })
        return events, result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)[:300]
        return [], result


def collect_songkick_for_artist(
    artist: dict[str, Any],
    client: HttpClient,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    name = str(artist.get("name") or "").strip()
    search_url = f"https://www.songkick.com/search?query={quote_plus(name)}&type=artists"
    result: dict[str, Any] = {"artist": name, "source": "Songkick", "status": "unmatched", "eventsFound": 0}
    try:
        if not robots_allows(search_url):
            result["status"] = "blocked_by_robots"
            return [], result
        search_html = client.get_text(search_url)
        artist_url = find_artist_page(
            search_url,
            search_html,
            artist,
            re.compile(r"/artists/\d+-([^/?#]+)", re.I),
        )
        if not artist_url or not robots_allows(artist_url):
            return [], result
        artist_html = client.get_text(artist_url)
        artist_page = PageContentParser()
        artist_page.feed(artist_html)
        if not page_artist_matches(artist_page, artist):
            result["status"] = "identity_mismatch"
            result["artistUrl"] = artist_url
            return [], result

        detail_urls: list[str] = []
        seen: set[str] = set()
        for href, _ in artist_page.links:
            absolute = safe_url(urljoin(artist_url, href))
            if not absolute or absolute in seen:
                continue
            path = urlparse(absolute).path
            if "/concerts/" not in path and "/festivals/" not in path:
                continue
            seen.add(absolute)
            detail_urls.append(absolute)

        source = source_record(f"{name} Songkick all-artist scan", artist_url, name, priority=70)
        events: list[dict[str, Any]] = []
        for detail_url in detail_urls[:20]:
            try:
                if not robots_allows(detail_url):
                    continue
                html = client.get_text(detail_url)
                events.extend(collect_jsonld_source_from_html(
                    source, detail_url, html, alias_lookup, checked_at
                ))
            except Exception:
                continue
        events = merge_events(events)
        result.update({"status": "ok", "artistUrl": artist_url, "eventsFound": len(events)})
        return events, result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)[:300]
        return [], result


def collect_configured_site(
    artist: dict[str, Any],
    url: str,
    source_label: str,
    client: HttpClient,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    name = str(artist.get("name") or "").strip()
    result: dict[str, Any] = {"artist": name, "source": source_label, "url": url, "status": "no_events", "eventsFound": 0}
    try:
        if not robots_allows(url):
            result["status"] = "blocked_by_robots"
            return [], result
        html = client.get_text(url)
        source = source_record(f"{name} {source_label} all-artist scan", url, name, priority=78)
        events = collect_jsonld_source_from_html(source, url, html, alias_lookup, checked_at)
        result["status"] = "ok" if events else "no_events"
        result["eventsFound"] = len(events)
        return events, result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)[:300]
        return [], result


def compact_candidate(event: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "reason": reason,
        "title": event.get("title", ""),
        "startDate": event.get("startDate", ""),
        "startTime": event.get("startTime", ""),
        "venue": event.get("venue", ""),
        "city": event.get("city", ""),
        "state": event.get("state", ""),
        "artists": event.get("artists", []),
        "eventType": event.get("eventType", ""),
        "ticketUrl": event.get("ticketUrl", ""),
        "officialUrl": event.get("officialUrl", ""),
        "sources": event.get("sources", []),
    }


def main() -> int:
    started = utc_now()
    checked_at = iso_z(started)
    today = started.date()

    artists = load_json(ARTISTS_FILE, [])
    existing = load_json(EVENTS_FILE, [])
    supplemental = load_json(SUPPLEMENTAL_FILE, [])
    attraction_cache = load_json(ATTRACTION_CACHE_FILE, {})
    if not isinstance(artists, list):
        raise SystemExit("config/artists.json must be an array")
    if not isinstance(existing, list):
        existing = []
    if not isinstance(supplemental, list):
        supplemental = []

    enabled_artists = [
        artist for artist in artists
        if isinstance(artist, dict) and artist.get("enabled", True) and str(artist.get("name") or "").strip()
    ]
    alias_lookup = build_alias_lookup(enabled_artists)
    client = HttpClient(min_interval_seconds=0.60)

    raw_events: list[dict[str, Any]] = []
    source_results: list[dict[str, Any]] = []

    for index, artist in enumerate(enabled_artists, start=1):
        name = str(artist.get("name") or "").strip()
        print(f"Expanded scan {index}/{len(enabled_artists)}: {name}")

        events, result = collect_bandsintown_for_artist(artist, client, alias_lookup, checked_at)
        raw_events.extend(events)
        source_results.append(result)

        events, result = collect_songkick_for_artist(artist, client, alias_lookup, checked_at)
        raw_events.extend(events)
        source_results.append(result)

        urls: list[tuple[str, str]] = []
        for field, label in (("website", "official website"), ("officialProfile", "official profile")):
            url = safe_url(artist.get(field))
            if not url:
                continue
            host = urlparse(url).netloc.lower()
            if any(token in host for token in SOCIAL_OR_STREAMING_HOSTS):
                continue
            if all(url != existing_url for existing_url, _ in urls):
                urls.append((url, label))
        for url, label in urls:
            events, result = collect_configured_site(
                artist, url, label, client, alias_lookup, checked_at
            )
            raw_events.extend(events)
            source_results.append(result)

        spotify_url = safe_url(artist.get("spotifyProfile"))
        if spotify_url:
            events, result = collect_configured_site(
                artist, spotify_url, "Spotify profile", client, alias_lookup, checked_at
            )
            raw_events.extend(events)
            source_results.append(result)

    raw_events = merge_events(raw_events)
    images = artist_image_map(enabled_artists, attraction_cache if isinstance(attraction_cache, dict) else {})
    positions = artist_image_positions(enabled_artists)
    preferred = preferred_artist_images(enabled_artists)
    finalized = finalize_events(raw_events, images, today, positions, preferred)

    current_all = [item for item in [*existing, *supplemental] if isinstance(item, dict)]
    new_events: list[dict[str, Any]] = []
    for event in finalized:
        if any(events_are_duplicates(event, current) for current in current_all):
            continue
        new_events.append(event)
        current_all.append(event)

    # Raw future festival events are intentionally retained as candidates when
    # the standard finalizer declines them because no official lineup authority
    # has corroborated the artist yet.
    finalized_ids = {str(item.get("id") or "") for item in finalized}
    candidates: list[dict[str, Any]] = []
    for event in raw_events:
        if str(event.get("eventType") or "") != "festival":
            continue
        if str(event.get("id") or "") in finalized_ids:
            continue
        start_date = str(event.get("startDate") or "")
        if not start_date or start_date < today.isoformat():
            continue
        if any(events_are_duplicates(event, current) for current in current_all):
            continue
        candidates.append(compact_candidate(event, "festival_needs_official_lineup_confirmation"))

    if new_events:
        supplemental = merge_events([*supplemental, *new_events])
        write_json(SUPPLEMENTAL_FILE, supplemental)

    write_json(CANDIDATES_FILE, candidates)

    status_counts: dict[str, int] = {}
    for item in source_results:
        key = str(item.get("status") or "unknown")
        status_counts[key] = status_counts.get(key, 0) + 1

    bandsintown_results = [item for item in source_results if item.get("source") == "Bandsintown"]
    songkick_results = [item for item in source_results if item.get("source") == "Songkick"]
    status = {
        "generatedAt": iso_z(utc_now()),
        "artistsChecked": len(enabled_artists),
        "rawEventsFound": len(raw_events),
        "newEventsPublished": len(new_events),
        "festivalCandidates": len(candidates),
        "bandsintown": {
            "artistsAttempted": len(bandsintown_results),
            "resolved": sum(1 for item in bandsintown_results if item.get("status") == "ok"),
            "eventsFound": sum(int(item.get("eventsFound") or 0) for item in bandsintown_results),
        },
        "songkick": {
            "artistsAttempted": len(songkick_results),
            "resolved": sum(1 for item in songkick_results if item.get("status") == "ok"),
            "blockedByRobots": sum(1 for item in songkick_results if item.get("status") == "blocked_by_robots"),
            "eventsFound": sum(int(item.get("eventsFound") or 0) for item in songkick_results),
        },
        "sourceStatusCounts": status_counts,
        "newEvents": [compact_candidate(item, "published") for item in new_events],
        "sourceResults": source_results,
    }
    write_json(STATUS_FILE, status)
    print(json.dumps({
        "artistsChecked": status["artistsChecked"],
        "rawEventsFound": status["rawEventsFound"],
        "newEventsPublished": status["newEventsPublished"],
        "festivalCandidates": status["festivalCandidates"],
        "bandsintownResolved": status["bandsintown"]["resolved"],
        "songkickResolved": status["songkick"]["resolved"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
