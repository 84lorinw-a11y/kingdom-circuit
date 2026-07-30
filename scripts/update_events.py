#!/usr/bin/env python3
"""Collect upcoming Christian hip-hop shows and update the static site data.

The collector uses two free inputs:
1. Official artist/label pages that expose Schema.org Event JSON-LD.
2. Ticketmaster Discovery API when TICKETMASTER_API_KEY is configured.

Only high-confidence, future, U.S. events are published. The script is designed
for a scheduled GitHub Actions workflow and uses only Python's standard library.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
OFFICIAL_SOURCES_FILE = ROOT / "config" / "official-sources.json"
MANUAL_EVENTS_FILE = ROOT / "config" / "manual-events.json"
ATTRACTION_CACHE_FILE = ROOT / "cache" / "ticketmaster-attractions.json"
EVENTS_FILE = ROOT / "events.json"
STATUS_FILE = ROOT / "run-status.json"

TICKETMASTER_BASE = "https://app.ticketmaster.com/discovery/v2"
USER_AGENT = (
    "KingdomCircuitBot/1.0 "
    "(+https://github.com/84lorinw-a11y/kingdom-circuit)"
)
REQUEST_TIMEOUT = 25
STALE_GRACE_DAYS = int(os.getenv("STALE_GRACE_DAYS", "3"))
LOOKAHEAD_DAYS = int(os.getenv("LOOKAHEAD_DAYS", "550"))

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
    "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VT", "VA", "WA", "WV", "WI", "WY", "DC"
}

NON_SHOW_PATTERN = re.compile(
    r"\b(parking|not a show ticket|add[- ]?on|fast lane|lawn chair|"
    r"club level seating|hospitality package|vip early entry package)\b",
    re.IGNORECASE,
)
FESTIVAL_PATTERN = re.compile(r"\b(festival|fest)\b", re.IGNORECASE)


class CollectorError(RuntimeError):
    """A recoverable collector error."""


class JsonLdScriptParser(HTMLParser):
    """Extract application/ld+json script contents from an HTML document."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capturing = False
        self._buffer: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attributes = {key.lower(): (value or "") for key, value in attrs}
        script_type = attributes.get("type", "").lower()
        if "ld+json" in script_type:
            self._capturing = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capturing:
            self.scripts.append("".join(self._buffer).strip())
            self._capturing = False
            self._buffer = []


@dataclass
class HttpClient:
    min_interval_seconds: float = 0.55
    last_request_at: float = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self.last_request_at
        remaining = self.min_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _request(self, url: str, accept: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            self._wait()
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": accept,
                    "Accept-Language": "en-US,en;q=0.8",
                },
            )
            try:
                with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                    self.last_request_at = time.monotonic()
                    return response.read()
            except HTTPError as exc:
                self.last_request_at = time.monotonic()
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except (URLError, TimeoutError, OSError) as exc:
                self.last_request_at = time.monotonic()
                last_error = exc
            time.sleep(2 ** (attempt - 1))
        raise CollectorError(f"Unable to retrieve {url}: {last_error}")

    def get_json(self, base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{base_url}?{urlencode(params)}"
        raw = self._request(url, "application/json")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectorError(f"Invalid JSON returned by {base_url}: {exc}") from exc
        if not isinstance(value, dict):
            raise CollectorError(f"Unexpected JSON structure returned by {base_url}")
        return value

    def get_text(self, url: str) -> str:
        raw = self._request(url, "text/html,application/xhtml+xml")
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")


def load_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    ascii_value = ascii_value.replace("&", " and ").lower()
    ascii_value = re.sub(r"[^a-z0-9]+", " ", ascii_value)
    return " ".join(ascii_value.split())


def safe_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parsed = urlparse(value.strip())
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value.strip()
    return ""


def parse_date_prefix(value: Any) -> tuple[str, str]:
    if not isinstance(value, str):
        return "", ""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?", value.strip())
    if not match:
        return "", ""
    return match.group(1), match.group(2) or ""


def event_is_future(event: dict[str, Any], today: date) -> bool:
    date_text = str(event.get("startDate", ""))
    try:
        return date.fromisoformat(date_text) >= today
    except ValueError:
        return False


def is_non_show(title: str) -> bool:
    return bool(NON_SHOW_PATTERN.search(title or ""))


def detect_event_type(title: str) -> str:
    return "festival" if FESTIVAL_PATTERN.search(title or "") else "concert"


def choose_image(images: Any) -> str:
    if not isinstance(images, list):
        return ""
    candidates = [image for image in images if isinstance(image, dict) and safe_url(image.get("url"))]
    if not candidates:
        return ""
    candidates.sort(
        key=lambda image: (
            image.get("ratio") == "16_9",
            int(image.get("width") or 0),
        ),
        reverse=True,
    )
    return safe_url(candidates[0].get("url"))


def build_alias_lookup(artists: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for artist in artists:
        canonical = str(artist.get("name", "")).strip()
        if not canonical:
            continue
        aliases = [canonical, *artist.get("aliases", [])]
        for alias in aliases:
            normalized = normalize_name(str(alias))
            if normalized:
                lookup[normalized] = canonical
    return lookup


def match_tracked_artists(
    names: Iterable[str], alias_lookup: dict[str, str]
) -> list[str]:
    matched: set[str] = set()
    for name in names:
        normalized = normalize_name(name)
        if normalized in alias_lookup:
            matched.add(alias_lookup[normalized])
    return sorted(matched, key=str.casefold)


def iter_event_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        event_type = value.get("@type")
        types = event_type if isinstance(event_type, list) else [event_type]
        if any(str(item).lower().endswith("event") for item in types if item):
            yield value
            return
        for nested in value.values():
            yield from iter_event_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_event_objects(nested)


def flatten_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, str):
        names.append(value)
    elif isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str):
            names.append(name)
    elif isinstance(value, list):
        for item in value:
            names.extend(flatten_names(item))
    return names


def extract_address(location: Any) -> tuple[str, str, str, str, str]:
    if isinstance(location, list):
        physical = next((item for item in location if isinstance(item, dict)), {})
        location = physical
    if not isinstance(location, dict):
        return "", "", "", "", ""

    venue = str(location.get("name") or "").strip()
    address = location.get("address")
    if isinstance(address, str):
        return venue, address.strip(), "", "", ""
    if not isinstance(address, dict):
        return venue, "", "", "", ""

    street = str(address.get("streetAddress") or "").strip()
    city = str(address.get("addressLocality") or "").strip()
    state = str(address.get("addressRegion") or "").strip()
    country_value = address.get("addressCountry")
    if isinstance(country_value, dict):
        country = str(country_value.get("name") or country_value.get("@id") or "").strip()
    else:
        country = str(country_value or "").strip()
    return venue, street, city, state, country


def is_us_location(state: str, country: str) -> bool:
    normalized_country = normalize_name(country)
    if normalized_country:
        return normalized_country in {
            "us", "usa", "united states", "united states of america"
        }
    return state.upper() in US_STATE_CODES


def extract_offer_url(offers: Any) -> str:
    if isinstance(offers, dict):
        return safe_url(offers.get("url"))
    if isinstance(offers, list):
        for offer in offers:
            url = extract_offer_url(offer)
            if url:
                return url
    return ""


def schema_status(value: Any) -> str:
    text = str(value or "").lower()
    if "cancel" in text:
        return "cancelled"
    if "postpon" in text:
        return "postponed"
    if "reschedul" in text:
        return "rescheduled"
    return "scheduled"


def event_hash(parts: Iterable[str]) -> str:
    value = "|".join(parts).encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:20]


def robots_allows(url: str) -> bool:
    """Check robots.txt once with a short timeout.

    Missing or temporarily unreachable robots files are treated as allowing a
    single low-frequency request. Explicit 401/403 responses are treated as a
    denial. This avoids RobotFileParser.read(), which has no configurable
    timeout and can stall a scheduled workflow.
    """

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    request = Request(
        robots_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/plain,*/*;q=0.1",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read()
    except HTTPError as exc:
        return exc.code not in {401, 403}
    except (URLError, TimeoutError, OSError):
        return True

    text = raw.decode("utf-8", errors="replace")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(text.splitlines())
    return parser.can_fetch("KingdomCircuitBot", url)


def collect_official_source(
    source: dict[str, Any],
    client: HttpClient,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    url = safe_url(source.get("url"))
    if not url:
        raise CollectorError("Source URL is missing or invalid")
    if not robots_allows(url):
        raise CollectorError("robots.txt does not allow automated retrieval")

    html = client.get_text(url)
    parser = JsonLdScriptParser()
    parser.feed(html)

    events: list[dict[str, Any]] = []
    source_artist = str(source.get("artist") or "").strip()
    for script in parser.scripts:
        if not script:
            continue
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        for raw_event in iter_event_objects(payload):
            title = str(raw_event.get("name") or "").strip()
            if not title or is_non_show(title):
                continue

            start_date, start_time = parse_date_prefix(raw_event.get("startDate"))
            if not start_date:
                continue

            venue, street, city, state, country = extract_address(raw_event.get("location"))
            if not city or not state or not is_us_location(state, country):
                continue

            performer_names = flatten_names(raw_event.get("performer"))
            performer_names.extend(flatten_names(raw_event.get("organizer")))
            artists = match_tracked_artists(performer_names, alias_lookup)
            if not artists and source_artist:
                artists = [source_artist]
            if not artists:
                normalized_title = normalize_name(title)
                for alias, canonical in alias_lookup.items():
                    if len(alias) >= 5 and alias in normalized_title:
                        artists.append(canonical)
                artists = sorted(set(artists), key=str.casefold)
            if not artists:
                continue

            ticket_url = extract_offer_url(raw_event.get("offers")) or safe_url(raw_event.get("url"))
            image_value = raw_event.get("image")
            if isinstance(image_value, list):
                image = next((safe_url(item) for item in image_value if safe_url(item)), "")
            elif isinstance(image_value, dict):
                image = safe_url(image_value.get("url"))
            else:
                image = safe_url(image_value)

            identifier = event_hash([url, title, start_date, venue, city, state])
            events.append(
                {
                    "id": f"official:{identifier}",
                    "title": title,
                    "startDate": start_date,
                    "startTime": start_time,
                    "timezone": "",
                    "venue": venue or "Venue not provided",
                    "address": street,
                    "city": city,
                    "state": state.upper(),
                    "country": "US",
                    "artists": artists,
                    "eventType": detect_event_type(title),
                    "status": schema_status(raw_event.get("eventStatus")),
                    "ticketUrl": ticket_url or url,
                    "officialUrl": safe_url(raw_event.get("url")) or url,
                    "image": image,
                    "price": "",
                    "sourceName": str(source.get("name") or "Official source"),
                    "sources": [
                        {
                            "name": str(source.get("name") or "Official source"),
                            "url": url,
                            "type": "official",
                        }
                    ],
                    "lastVerified": checked_at,
                    "confidence": "high",
                }
            )
    return events


def attraction_cache_is_fresh(entry: dict[str, Any]) -> bool:
    checked = entry.get("checkedAt")
    if not isinstance(checked, str):
        return False
    try:
        checked_date = datetime.fromisoformat(checked.replace("Z", "+00:00"))
    except ValueError:
        return False
    max_age = timedelta(days=180 if entry.get("id") else 30)
    return now_utc() - checked_date <= max_age


def find_ticketmaster_attraction(
    artist: dict[str, Any],
    api_key: str,
    client: HttpClient,
    cache: dict[str, Any],
    checked_at: str,
) -> str | None:
    canonical = str(artist.get("name") or "").strip()
    explicit_id = str(artist.get("ticketmasterAttractionId") or "").strip()
    if explicit_id:
        return explicit_id

    cached = cache.get(canonical)
    if isinstance(cached, dict) and attraction_cache_is_fresh(cached):
        cached_id = cached.get("id")
        return str(cached_id) if cached_id else None

    aliases = {
        normalize_name(canonical),
        *(normalize_name(str(alias)) for alias in artist.get("aliases", [])),
    }
    aliases.discard("")
    payload = client.get_json(
        f"{TICKETMASTER_BASE}/attractions.json",
        {
            "apikey": api_key,
            "keyword": str(artist.get("ticketmasterQuery") or canonical),
            "classificationName": "music",
            "size": 50,
            "locale": "*",
        },
    )
    attractions = payload.get("_embedded", {}).get("attractions", [])
    exact: list[dict[str, Any]] = []
    for attraction in attractions if isinstance(attractions, list) else []:
        if not isinstance(attraction, dict):
            continue
        if normalize_name(str(attraction.get("name") or "")) in aliases:
            exact.append(attraction)

    exact.sort(
        key=lambda item: int(item.get("upcomingEvents", {}).get("_total") or 0),
        reverse=True,
    )
    selected = exact[0] if exact else None
    cache[canonical] = {
        "id": selected.get("id") if selected else None,
        "matchedName": selected.get("name") if selected else None,
        "checkedAt": checked_at,
    }
    return str(selected.get("id")) if selected and selected.get("id") else None


def ticketmaster_status(raw_event: dict[str, Any]) -> str:
    code = raw_event.get("dates", {}).get("status", {}).get("code")
    return str(code or "scheduled").lower()


def ticketmaster_price(raw_event: dict[str, Any]) -> str:
    ranges = raw_event.get("priceRanges")
    if not isinstance(ranges, list) or not ranges:
        return ""
    minimums = [item.get("min") for item in ranges if isinstance(item, dict) and item.get("min") is not None]
    maximums = [item.get("max") for item in ranges if isinstance(item, dict) and item.get("max") is not None]
    currency = str(ranges[0].get("currency") or "USD") if isinstance(ranges[0], dict) else "USD"
    if not minimums:
        return ""
    minimum = min(float(value) for value in minimums)
    maximum = max(float(value) for value in maximums) if maximums else minimum
    symbol = "$" if currency == "USD" else f"{currency} "
    if minimum == maximum:
        return f"{symbol}{minimum:,.0f}"
    return f"{symbol}{minimum:,.0f}-${maximum:,.0f}"


def extract_ticketmaster_event(
    raw_event: dict[str, Any],
    fallback_artist: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> dict[str, Any] | None:
    title = str(raw_event.get("name") or "").strip()
    if not title or is_non_show(title):
        return None

    event_id = str(raw_event.get("id") or "").strip()
    local_date = str(raw_event.get("dates", {}).get("start", {}).get("localDate") or "").strip()
    local_time = str(raw_event.get("dates", {}).get("start", {}).get("localTime") or "").strip()
    if not event_id or not local_date:
        return None

    venues = raw_event.get("_embedded", {}).get("venues", [])
    venue_data = venues[0] if isinstance(venues, list) and venues and isinstance(venues[0], dict) else {}
    country_code = str(venue_data.get("country", {}).get("countryCode") or "").upper()
    if country_code and country_code != "US":
        return None

    city = str(venue_data.get("city", {}).get("name") or "").strip()
    state = str(venue_data.get("state", {}).get("stateCode") or "").strip().upper()
    venue = str(venue_data.get("name") or "Venue not provided").strip()
    address = str(venue_data.get("address", {}).get("line1") or "").strip()
    if not city or not state:
        return None

    attractions = raw_event.get("_embedded", {}).get("attractions", [])
    attraction_names = [
        str(item.get("name") or "")
        for item in attractions
        if isinstance(item, dict)
    ] if isinstance(attractions, list) else []
    artists = match_tracked_artists(attraction_names, alias_lookup)
    if fallback_artist not in artists:
        artists.append(fallback_artist)
    artists = sorted(set(artists), key=str.casefold)

    event_url = safe_url(raw_event.get("url"))
    return {
        "id": f"ticketmaster:{event_id}",
        "title": title,
        "startDate": local_date,
        "startTime": local_time[:5] if local_time else "",
        "timezone": str(raw_event.get("dates", {}).get("timezone") or ""),
        "venue": venue,
        "address": address,
        "city": city,
        "state": state,
        "country": "US",
        "artists": artists,
        "eventType": detect_event_type(title),
        "status": ticketmaster_status(raw_event),
        "ticketUrl": event_url,
        "officialUrl": event_url,
        "image": choose_image(raw_event.get("images")),
        "price": ticketmaster_price(raw_event),
        "sourceName": "Ticketmaster",
        "sources": [
            {
                "name": "Ticketmaster",
                "url": event_url,
                "type": "ticketing",
            }
        ],
        "lastVerified": checked_at,
        "confidence": "high",
    }


def collect_ticketmaster_artist(
    artist: dict[str, Any],
    attraction_id: str,
    api_key: str,
    client: HttpClient,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    start = now_utc()
    end = start + timedelta(days=LOOKAHEAD_DAYS)
    events: list[dict[str, Any]] = []
    page = 0
    while page < 5:
        payload = client.get_json(
            f"{TICKETMASTER_BASE}/events.json",
            {
                "apikey": api_key,
                "attractionId": attraction_id,
                "countryCode": "US",
                "startDateTime": iso_z(start),
                "endDateTime": iso_z(end),
                "includeTBA": "no",
                "includeTBD": "no",
                "size": 200,
                "page": page,
                "locale": "*",
            },
        )
        raw_events = payload.get("_embedded", {}).get("events", [])
        if isinstance(raw_events, list):
            for raw_event in raw_events:
                if not isinstance(raw_event, dict):
                    continue
                event = extract_ticketmaster_event(
                    raw_event,
                    str(artist.get("name")),
                    alias_lookup,
                    checked_at,
                )
                if event:
                    events.append(event)
        page_info = payload.get("page", {})
        total_pages = int(page_info.get("totalPages") or 0)
        page += 1
        if page >= total_pages:
            break
    return events


def canonical_event_key(event: dict[str, Any]) -> str:
    event_date = str(event.get("startDate") or "")
    venue = normalize_name(str(event.get("venue") or ""))
    city = normalize_name(str(event.get("city") or ""))
    state = normalize_name(str(event.get("state") or ""))
    if event_date and venue and city:
        return f"{event_date}|{venue}|{city}|{state}"
    return normalize_name(str(event.get("id") or event.get("title") or ""))


def merge_two_events(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key in (
        "title", "startDate", "startTime", "timezone", "venue", "address",
        "city", "state", "country", "eventType", "status", "ticketUrl",
        "officialUrl", "image", "price", "lastVerified", "confidence",
    ):
        incoming_value = incoming.get(key)
        if incoming_value:
            if key in {"ticketUrl", "image", "price"} and merged.get(key):
                continue
            merged[key] = incoming_value

    merged["artists"] = sorted(
        set(existing.get("artists", [])) | set(incoming.get("artists", [])),
        key=str.casefold,
    )

    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for source in [*existing.get("sources", []), *incoming.get("sources", [])]:
        if not isinstance(source, dict):
            continue
        url = safe_url(source.get("url"))
        identity = url or str(source.get("name") or "")
        if identity and identity not in seen_urls:
            seen_urls.add(identity)
            sources.append(source)
    merged["sources"] = sources
    if sources:
        merged["sourceName"] = str(sources[0].get("name") or merged.get("sourceName") or "")
    return merged


def merge_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    key_to_id: dict[str, str] = {}
    for event in events:
        event_id = str(event.get("id") or "").strip()
        if not event_id:
            continue
        key = canonical_event_key(event)
        existing_id = event_id if event_id in by_id else key_to_id.get(key)
        if existing_id and existing_id in by_id:
            by_id[existing_id] = merge_two_events(by_id[existing_id], event)
            continue
        by_id[event_id] = event
        if key:
            key_to_id[key] = event_id

    values = list(by_id.values())
    values.sort(
        key=lambda item: (
            str(item.get("startDate") or "9999-12-31"),
            str(item.get("startTime") or "23:59"),
            str(item.get("title") or "").casefold(),
        )
    )
    return values


def normalize_manual_event(event: Any, checked_at: str) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    title = str(event.get("title") or "").strip()
    start_date = str(event.get("startDate") or "").strip()
    city = str(event.get("city") or "").strip()
    state = str(event.get("state") or "").strip().upper()
    artists = [str(value).strip() for value in event.get("artists", []) if str(value).strip()]
    if not title or not start_date or not city or state not in US_STATE_CODES or not artists:
        return None
    identifier = str(event.get("id") or event_hash([title, start_date, city, state]))
    source_url = safe_url(event.get("officialUrl")) or safe_url(event.get("ticketUrl"))
    return {
        "id": f"manual:{identifier}",
        "title": title,
        "startDate": start_date,
        "startTime": str(event.get("startTime") or ""),
        "timezone": str(event.get("timezone") or ""),
        "venue": str(event.get("venue") or "Venue not provided"),
        "address": str(event.get("address") or ""),
        "city": city,
        "state": state,
        "country": "US",
        "artists": sorted(set(artists), key=str.casefold),
        "eventType": str(event.get("eventType") or detect_event_type(title)),
        "status": str(event.get("status") or "scheduled"),
        "ticketUrl": safe_url(event.get("ticketUrl")) or source_url,
        "officialUrl": source_url,
        "image": safe_url(event.get("image")),
        "price": str(event.get("price") or ""),
        "sourceName": "Manual verified listing",
        "sources": [
            {
                "name": "Manual verified listing",
                "url": source_url,
                "type": "manual",
            }
        ] if source_url else [],
        "lastVerified": checked_at,
        "confidence": "high",
    }


def preserve_recent_existing(
    fresh_events: list[dict[str, Any]],
    existing_events: list[dict[str, Any]],
    today: date,
    checked_at: str,
) -> list[dict[str, Any]]:
    fresh_ids = {str(event.get("id") or "") for event in fresh_events}
    fresh_keys = {canonical_event_key(event) for event in fresh_events}
    preserved: list[dict[str, Any]] = []
    current_time = now_utc()
    for event in existing_events:
        if not isinstance(event, dict) or not event_is_future(event, today):
            continue
        event_id = str(event.get("id") or "")
        if event_id in fresh_ids or canonical_event_key(event) in fresh_keys:
            continue
        verified = str(event.get("lastVerified") or "")
        try:
            verified_at = datetime.fromisoformat(verified.replace("Z", "+00:00"))
        except ValueError:
            continue
        if current_time - verified_at <= timedelta(days=STALE_GRACE_DAYS):
            copy = dict(event)
            copy["stale"] = True
            copy["staleSince"] = checked_at
            preserved.append(copy)
    return [*fresh_events, *preserved]


def main() -> int:
    started = now_utc()
    checked_at = iso_z(started)
    today = started.date()

    artists = [
        item for item in load_json(ARTISTS_FILE, [])
        if isinstance(item, dict) and item.get("enabled", True)
    ]
    official_sources = [
        item for item in load_json(OFFICIAL_SOURCES_FILE, [])
        if isinstance(item, dict) and item.get("enabled", True)
    ]
    manual_events = load_json(MANUAL_EVENTS_FILE, [])
    existing_events = load_json(EVENTS_FILE, [])
    previous_status = load_json(STATUS_FILE, {})
    attraction_cache = load_json(ATTRACTION_CACHE_FILE, {})
    if not isinstance(attraction_cache, dict):
        attraction_cache = {}

    alias_lookup = build_alias_lookup(artists)
    client = HttpClient()
    collected: list[dict[str, Any]] = []
    errors: list[str] = []
    sources_checked = 0
    official_events_count = 0
    ticketmaster_events_count = 0
    artists_matched = 0
    unmatched_artists: list[str] = []

    for source in official_sources:
        source_name = str(source.get("name") or source.get("url") or "Official source")
        try:
            source_events = collect_official_source(
                source, client, alias_lookup, checked_at
            )
            collected.extend(source_events)
            official_events_count += len(source_events)
            sources_checked += 1
            print(f"Official source: {source_name}: {len(source_events)} event(s)")
        except CollectorError as exc:
            errors.append(f"{source_name}: {exc}")
            print(f"WARNING: {source_name}: {exc}", file=sys.stderr)

    api_key = os.getenv("TICKETMASTER_API_KEY", "").strip()
    if api_key:
        for artist in artists:
            name = str(artist.get("name") or "")
            try:
                attraction_id = find_ticketmaster_attraction(
                    artist, api_key, client, attraction_cache, checked_at
                )
                if not attraction_id:
                    unmatched_artists.append(name)
                    print(f"Ticketmaster: no exact attraction match for {name}")
                    continue
                artists_matched += 1
                artist_events = collect_ticketmaster_artist(
                    artist,
                    attraction_id,
                    api_key,
                    client,
                    alias_lookup,
                    checked_at,
                )
                collected.extend(artist_events)
                ticketmaster_events_count += len(artist_events)
                sources_checked += 1
                print(f"Ticketmaster: {name}: {len(artist_events)} event(s)")
            except CollectorError as exc:
                errors.append(f"Ticketmaster - {name}: {exc}")
                print(f"WARNING: Ticketmaster - {name}: {exc}", file=sys.stderr)
    else:
        errors.append(
            "Ticketmaster is not configured. Add the TICKETMASTER_API_KEY repository secret for broader coverage."
        )

    if isinstance(manual_events, list):
        for raw_event in manual_events:
            event = normalize_manual_event(raw_event, checked_at)
            if event:
                collected.append(event)

    fresh_events = [event for event in collected if event_is_future(event, today)]
    fresh_events = merge_events(fresh_events)
    events = preserve_recent_existing(
        fresh_events,
        existing_events if isinstance(existing_events, list) else [],
        today,
        checked_at,
    )
    events = merge_events(events)

    write_json(EVENTS_FILE, events)
    write_json(ATTRACTION_CACHE_FILE, attraction_cache)

    any_source_succeeded = sources_checked > 0
    if errors and any_source_succeeded:
        status_name = "partial"
    elif errors:
        status_name = "needs_configuration" if not api_key else "error"
    else:
        status_name = "ok"

    last_success = checked_at if any_source_succeeded else previous_status.get("lastSuccessfulUpdate")
    status = {
        "status": status_name,
        "lastAttempt": checked_at,
        "lastSuccessfulUpdate": last_success,
        "eventsPublished": len(events),
        "artistsConfigured": len(artists),
        "artistsMatchedOnTicketmaster": artists_matched,
        "officialEventsFound": official_events_count,
        "ticketmasterEventsFound": ticketmaster_events_count,
        "sourcesChecked": sources_checked,
        "unmatchedArtists": unmatched_artists,
        "errors": errors[:25],
        "message": (
            "Show listings updated successfully."
            if status_name == "ok"
            else "The site updated, but one or more sources need attention."
        ),
    }
    write_json(STATUS_FILE, status)

    print(
        f"Published {len(events)} event(s); "
        f"official={official_events_count}; ticketmaster={ticketmaster_events_count}; "
        f"errors={len(errors)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
