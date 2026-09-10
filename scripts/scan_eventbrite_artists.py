#!/usr/bin/env python3
"""Audit Eventbrite for upcoming U.S. events mentioning Kingdom Circuit artists.

This is a discovery/audit pass only. It does not publish events automatically.
Candidates are compared with the current event catalog and written to JSON for
manual verification before publication.
"""

from __future__ import annotations

import html as html_lib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
MANUAL_FILE = ROOT / "config" / "manual-events.json"
STATUS_FILE = ROOT / "eventbrite-scan-status.json"
CANDIDATES_FILE = ROOT / "eventbrite-scan-candidates.json"

USER_AGENT = "KingdomCircuitBot/1.0 (+https://kingdomcircuit.com/)"
TIMEOUT = 22
MIN_INTERVAL = 0.18
EVENT_URL_RE = re.compile(
    r"https?://(?:www\.)?eventbrite\.com/e/[A-Za-z0-9_%?=&+.,'()!~*:/-]*?(?:tickets-)?\d{8,}(?:[?&][^\"'<> ]*)?",
    re.I,
)
REL_EVENT_RE = re.compile(
    r"(?:href=|\\\"url\\\":)\s*[\"'](?:\\u002F|/)?(e/[A-Za-z0-9_%?=&+.,'()!~*:/-]*?(?:tickets-)?\d{8,}(?:[?&][^\"'<> ]*)?)[\"']",
    re.I,
)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9']+", " ", value)
    return " ".join(value.split())


def slugify(value: str) -> str:
    text = normalize(value).replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def canonical_eventbrite_url(url: str) -> str:
    url = html_lib.unescape(url).replace("\\u002F", "/").replace("\\/", "/")
    parsed = urlparse(url)
    if "eventbrite.com" not in parsed.netloc.lower() or not parsed.path.startswith("/e/"):
        return ""
    return f"https://www.eventbrite.com{parsed.path.rstrip('/')}"


class Client:
    def __init__(self) -> None:
        self.last = 0.0

    def get(self, url: str) -> str:
        remaining = MIN_INTERVAL - (time.monotonic() - self.last)
        if remaining > 0:
            time.sleep(remaining)
        request = Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.8",
        })
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urlopen(request, timeout=TIMEOUT) as response:
                    self.last = time.monotonic()
                    return response.read().decode("utf-8", errors="replace")
            except HTTPError as exc:
                self.last = time.monotonic()
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except (URLError, TimeoutError, OSError) as exc:
                self.last = time.monotonic()
                last_error = exc
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"{type(last_error).__name__}: {last_error}")


def extract_event_urls(text: str) -> list[str]:
    unescaped = html_lib.unescape(text).replace("\\u002F", "/").replace("\\/", "/")
    found: list[str] = []
    seen: set[str] = set()
    for match in EVENT_URL_RE.findall(unescaped):
        url = canonical_eventbrite_url(match)
        if url and url not in seen:
            seen.add(url)
            found.append(url)
    for match in REL_EVENT_RE.findall(unescaped):
        url = canonical_eventbrite_url("https://www.eventbrite.com/" + match.lstrip("/"))
        if url and url not in seen:
            seen.add(url)
            found.append(url)
    return found


def iter_jsonld_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from iter_jsonld_objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_jsonld_objects(item)


def jsonld_events(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    scripts = re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        text,
        flags=re.I | re.S,
    )
    for raw in scripts:
        try:
            value = json.loads(html_lib.unescape(raw).strip())
        except Exception:
            continue
        for obj in iter_jsonld_objects(value):
            typ = obj.get("@type")
            types = typ if isinstance(typ, list) else [typ]
            if any(str(t).casefold() in {"event", "musicevent"} for t in types if t):
                results.append(obj)
    return results


def text_from_html(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html_lib.unescape(text).split())


def artist_terms(artist: dict[str, Any]) -> list[str]:
    values = [str(artist.get("name") or ""), *[str(v) for v in artist.get("aliases", [])]]
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        norm = normalize(value)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def exact_term_present(haystack_norm: str, term_norm: str) -> bool:
    if not term_norm:
        return False
    return bool(re.search(r"(?:^|\s)" + re.escape(term_norm) + r"(?:$|\s)", haystack_norm))


def location_parts(event: dict[str, Any]) -> tuple[str, str, str, str]:
    location = event.get("location") or {}
    if isinstance(location, list):
        location = next((v for v in location if isinstance(v, dict)), {})
    if not isinstance(location, dict):
        return "", "", "", ""
    venue = str(location.get("name") or "")
    address = location.get("address") or {}
    if isinstance(address, str):
        return venue, "", "", ""
    if not isinstance(address, dict):
        address = {}
    city = str(address.get("addressLocality") or "")
    state = str(address.get("addressRegion") or "")
    country = address.get("addressCountry") or ""
    if isinstance(country, dict):
        country = country.get("name") or country.get("@id") or ""
    return venue, city, state, str(country)


def event_candidate(url: str, page: str, artist: dict[str, Any], today: str) -> dict[str, Any] | None:
    terms = artist_terms(artist)
    visible_norm = normalize(text_from_html(page))
    matched = [term for term in terms if exact_term_present(visible_norm, term)]
    if not matched:
        return None

    objs = jsonld_events(page)
    event = objs[0] if objs else {}
    title = str(event.get("name") or "")
    description = str(event.get("description") or "")
    start = str(event.get("startDate") or "")
    start_date = start[:10] if re.match(r"\d{4}-\d{2}-\d{2}", start) else ""
    if start_date and start_date < today:
        return None

    # Strengthen identity matching by requiring the artist in the event's
    # structured title/description when those fields exist. This prevents
    # generic site chrome from creating candidates.
    structured_norm = normalize(" ".join([title, description]))
    if structured_norm and not any(exact_term_present(structured_norm, term) for term in terms):
        return None

    venue, city, state, country = location_parts(event)
    country_norm = normalize(country)
    if country_norm and country_norm not in {"us", "usa", "united states", "united states of america"}:
        return None

    return {
        "artist": str(artist.get("name") or ""),
        "title": title or "Eventbrite event",
        "startDate": start_date,
        "startTime": start[11:16] if len(start) >= 16 and "T" in start else "",
        "venue": venue,
        "city": city,
        "state": state,
        "eventbriteUrl": url,
        "matchedAlias": matched[0],
        "confidence": "candidate",
    }


def existing_keys() -> tuple[set[str], set[tuple[str, str, str]]]:
    urls: set[str] = set()
    fuzzy: set[tuple[str, str, str]] = set()
    for path in (EVENTS_FILE, SUPPLEMENTAL_FILE, MANUAL_FILE):
        rows = load_json(path, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in ("ticketUrl", "officialUrl", "announcementUrl"):
                value = str(row.get(key) or "")
                canon = canonical_eventbrite_url(value)
                if canon:
                    urls.add(canon)
            title = normalize(str(row.get("title") or ""))
            date = str(row.get("startDate") or "")[:10]
            city = normalize(str(row.get("city") or ""))
            if title and date:
                fuzzy.add((title, date, city))
    return urls, fuzzy


def main() -> int:
    started = datetime.now(timezone.utc)
    today = started.date().isoformat()
    artists = load_json(ARTISTS_FILE, [])
    if not isinstance(artists, list):
        raise SystemExit("config/artists.json must be an array")
    enabled = [a for a in artists if isinstance(a, dict) and a.get("enabled", True) and a.get("name")]
    known_urls, known_fuzzy = existing_keys()
    client = Client()

    candidates: list[dict[str, Any]] = []
    artist_results: list[dict[str, Any]] = []
    seen_candidate_urls: set[str] = set()
    pages_checked = 0
    search_failures = 0
    detail_failures = 0
    event_links_found = 0

    for index, artist in enumerate(enabled, start=1):
        name = str(artist.get("name") or "").strip()
        slug = slugify(name)
        search_urls = [
            f"https://www.eventbrite.com/d/united-states/{quote(slug)}/",
            f"https://www.eventbrite.com/d/united-states/all-events/?q={quote(name)}",
        ]
        links: list[str] = []
        error = ""
        for attempt_url in search_urls:
            try:
                search_html = client.get(attempt_url)
                links = extract_event_urls(search_html)
                if links:
                    break
            except Exception as exc:
                error = str(exc)[:240]
                continue
        if error and not links:
            search_failures += 1
        event_links_found += len(links)
        new_for_artist = 0
        matched_for_artist = 0
        for event_url in links[:18]:
            if event_url in seen_candidate_urls:
                continue
            pages_checked += 1
            try:
                page = client.get(event_url)
            except Exception:
                detail_failures += 1
                continue
            candidate = event_candidate(event_url, page, artist, today)
            if not candidate:
                continue
            matched_for_artist += 1
            key = (normalize(candidate["title"]), candidate["startDate"], normalize(candidate["city"]))
            candidate["alreadyInCatalog"] = event_url in known_urls or (candidate["startDate"] and key in known_fuzzy)
            if not candidate["alreadyInCatalog"]:
                new_for_artist += 1
            seen_candidate_urls.add(event_url)
            candidates.append(candidate)
        artist_results.append({
            "artist": name,
            "searchLinksFound": len(links),
            "matchedEvents": matched_for_artist,
            "newCandidates": new_for_artist,
            "status": "ok" if links or not error else "failed",
            "error": error if error and not links else "",
        })
        print(f"Eventbrite {index}/{len(enabled)}: {name} links={len(links)} matched={matched_for_artist} new={new_for_artist}")

    # One Eventbrite event can mention multiple roster artists. Consolidate by URL
    # while preserving all matched artists.
    consolidated: dict[str, dict[str, Any]] = {}
    for item in candidates:
        url = item["eventbriteUrl"]
        if url not in consolidated:
            copy = dict(item)
            copy["artists"] = [item["artist"]]
            consolidated[url] = copy
        elif item["artist"] not in consolidated[url]["artists"]:
            consolidated[url]["artists"].append(item["artist"])
    final = sorted(consolidated.values(), key=lambda x: (x.get("startDate") or "9999", x.get("title") or ""))
    new_final = [item for item in final if not item.get("alreadyInCatalog")]

    status = {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "artistsChecked": len(enabled),
        "eventLinksFoundAcrossSearches": event_links_found,
        "eventPagesChecked": pages_checked,
        "matchedUpcomingEvents": len(final),
        "alreadyInCatalog": len(final) - len(new_final),
        "newCandidateEvents": len(new_final),
        "searchFailures": search_failures,
        "detailFailures": detail_failures,
        "artistResults": artist_results,
    }
    write_json(CANDIDATES_FILE, final)
    write_json(STATUS_FILE, status)
    print(json.dumps({k: v for k, v in status.items() if k != "artistResults"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
