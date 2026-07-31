#!/usr/bin/env python3
"""Collect upcoming Christian hip-hop shows and update the static site data.

The collector uses free structured and public first-party inputs:
1. Ticketmaster Discovery API when TICKETMASTER_API_KEY is configured.
2. Official artist, label, promoter, and festival pages.
3. Selected CHH calendars that are filtered to the tracked artist roster.
4. A free, best-effort public-index scan of Instagram announcements for every tracked artist.

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
from difflib import SequenceMatcher
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from instagram_monitor import scan_instagram_index

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
OFFICIAL_SOURCES_FILE = ROOT / "config" / "official-sources.json"
MANUAL_EVENTS_FILE = ROOT / "config" / "manual-events.json"
KNOWN_INSTAGRAM_POSTS_FILE = ROOT / "config" / "known-instagram-posts.json"
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

US_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}
MONTH_NUMBERS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
    "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
MONTH_PATTERN = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?"
)
GENERIC_VENUES = {"", "venue not provided", "tba", "to be announced"}

NON_SHOW_PATTERN = re.compile(
    r"\b(parking|not a show ticket|add[- ]?on|fast lane|lawn chair|"
    r"club level seating|hospitality package|vip early entry package)\b",
    re.IGNORECASE,
)
FESTIVAL_PATTERN = re.compile(r"\b(festival|fest)\b", re.IGNORECASE)

NON_MUSIC_PATTERN = re.compile(
    r"\b(conference|summit|workshop|seminar|podcast|book tour|book signing|"
    r"speaking|speaker|sermon|lecture|panel discussion|meet[ -]?and[ -]?greet only|"
    r"chapel service|church service|prayer breakfast|leadership event|women['’]s event)\b",
    re.IGNORECASE,
)

AUTHORITY_RANKS = {
    "aggregator": 45,
    "artist_calendar": 72,
    "artist_label": 82,
    "promoter": 88,
    "venue_ticket": 94,
    "official_event": 100,
    "official_festival": 106,
    "manual_verified": 112,
}

IMAGE_REJECT_PATTERN = re.compile(
    r"(?:favicon|(?:^|[/_.-])logo(?:[/_.-]|$)|placeholder|default[-_ ]?image|"
    r"sprite|icon[-_.]|reachrecords(?:\.com)?/(?:wp-content/)?"
    r"(?:themes|images)?/?(?:logo)?)",
    re.IGNORECASE,
)

VENUE_STOPWORDS = {
    "the", "at", "venue", "theater", "theatre", "center", "centre", "hall",
    "auditorium", "arena", "club", "live", "event", "events", "music",
    "performance", "performing", "arts", "stage", "room", "complex",
}
TITLE_STOPWORDS = {
    "the", "a", "an", "live", "concert", "tickets", "ticket", "official",
    "presents", "present", "tour", "show", "featuring", "feat", "with",
}


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


class PageContentParser(HTMLParser):
    """Collect visible text, headings, links, dates, and social metadata."""

    IGNORE_TAGS = {"script", "style", "noscript", "svg"}
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_chunks: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.headings: list[tuple[str, str]] = []
        self.datetimes: list[str] = []
        self.meta: dict[str, str] = {}
        self._ignore_depth = 0
        self._link_depth = 0
        self._link_href = ""
        self._link_buffer: list[str] = []
        self._heading_depth = 0
        self._heading_tag = ""
        self._heading_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if tag in self.IGNORE_TAGS:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return
        if tag == "a":
            if self._link_depth == 0:
                self._link_href = attributes.get("href", "")
                self._link_buffer = []
            self._link_depth += 1
        if tag in self.HEADING_TAGS:
            if self._heading_depth == 0:
                self._heading_tag = tag
                self._heading_buffer = []
            self._heading_depth += 1
        if tag == "time" and attributes.get("datetime"):
            self.datetimes.append(attributes["datetime"].strip())
        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            value = attributes.get("content", "").strip()
            if key and value:
                self.meta[key] = value

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        self.text_chunks.append(text)
        if self._link_depth:
            self._link_buffer.append(text)
        if self._heading_depth:
            self._heading_buffer.append(text)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.IGNORE_TAGS:
            self._ignore_depth = max(0, self._ignore_depth - 1)
            return
        if self._ignore_depth:
            return
        if tag == "a" and self._link_depth:
            self._link_depth -= 1
            if self._link_depth == 0:
                text = " ".join(self._link_buffer).strip()
                self.links.append((self._link_href, text))
                self._link_href = ""
                self._link_buffer = []
        if tag in self.HEADING_TAGS and self._heading_depth:
            self._heading_depth -= 1
            if self._heading_depth == 0:
                text = " ".join(self._heading_buffer).strip()
                self.headings.append((self._heading_tag, text))
                self._heading_tag = ""
                self._heading_buffer = []

    @property
    def text(self) -> str:
        return " ".join(self.text_chunks)


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
    # Multi-day festivals should remain visible through their final day.
    date_text = str(event.get("endDate") or event.get("startDate") or "")
    try:
        return date.fromisoformat(date_text) >= today
    except ValueError:
        return False


def is_non_show(title: str) -> bool:
    return bool(NON_SHOW_PATTERN.search(title) or NON_MUSIC_PATTERN.search(title))

def detect_event_type(title: str) -> str:
    return "festival" if FESTIVAL_PATTERN.search(title) else "concert"

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
    # Preserve the source's performer order so the first-billed confirmed artist
    # remains the headliner. A set/sort here would incorrectly choose the
    # alphabetically first artist for images and display order.
    matched: list[str] = []
    seen: set[str] = set()
    for name in names:
        normalized = normalize_name(name)
        canonical = alias_lookup.get(normalized)
        key = normalize_name(canonical) if canonical else ""
        if canonical and key not in seen:
            seen.add(key)
            matched.append(canonical)
    return matched


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


def normalize_whitespace(value: str) -> str:
    return " ".join((value or "").split())


def normalize_state(value: str) -> str:
    cleaned = normalize_name(value)
    if not cleaned:
        return ""
    if cleaned.upper() in US_STATE_CODES and len(cleaned) == 2:
        return cleaned.upper()
    return US_STATE_NAMES.get(cleaned, "")


def month_number(value: str) -> int:
    return MONTH_NUMBERS.get(normalize_name(value), 0)


def infer_date(month_value: str, day_value: int, year_value: int | None, today: date) -> str:
    month = month_number(month_value)
    if not month or not 1 <= day_value <= 31:
        return ""
    year = year_value or today.year
    try:
        candidate = date(year, month, day_value)
    except ValueError:
        return ""
    if year_value is None and candidate < today - timedelta(days=7):
        try:
            candidate = date(year + 1, month, day_value)
        except ValueError:
            return ""
    return candidate.isoformat()


def parse_clock(value: str) -> str:
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b", value or "", re.I)
    if not match:
        match_24 = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", value or "")
        return f"{int(match_24.group(1)):02d}:{match_24.group(2)}" if match_24 else ""
    hour = int(match.group(1))
    minute = int(match.group(2) or "00")
    meridiem = match.group(3).lower()
    if hour == 12:
        hour = 0
    if meridiem == "p":
        hour += 12
    return f"{hour:02d}:{minute:02d}"


def match_artists_in_text(text: str, alias_lookup: dict[str, str]) -> list[str]:
    normalized = f" {normalize_name(text)} "
    matched: set[str] = set()
    for alias, canonical in alias_lookup.items():
        # Numeric-only names (for example, "350") are safe when a source
        # supplies an exact performer name, but unsafe in general page text.
        if alias and not alias.isdigit() and f" {alias} " in normalized:
            matched.add(canonical)
    return sorted(matched, key=str.casefold)


def parse_city_state(value: str) -> tuple[str, str]:
    cleaned = normalize_whitespace(value)
    cleaned = re.sub(r"\s+(?:United States|USA)\s*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+\d{5}(?:-\d{4})?\s*$", "", cleaned)
    if "," not in cleaned:
        return "", ""
    before, state_text = cleaned.rsplit(",", 1)
    state = normalize_state(state_text)
    if not state:
        return "", ""
    city = before.strip(" -–—,")
    if not city:
        return "", ""
    return city, state


def extract_city_state_from_block(value: str) -> tuple[str, str]:
    cleaned = normalize_whitespace(value)
    state_terms = sorted([*US_STATE_NAMES.keys(), *US_STATE_CODES], key=len, reverse=True)
    state_pattern = "|".join(re.escape(term) for term in state_terms)
    matches = list(re.finditer(
        rf"([A-Za-z][A-Za-z .()'&-]{{1,60}}),\s*({state_pattern})(?:\s+\d{{5}}(?:-\d{{4}})?)?",
        cleaned,
        re.I,
    ))
    if not matches:
        return parse_city_state(cleaned)
    match = matches[-1]
    city_candidate = match.group(1).strip()
    # When an address precedes the city, keep only the final probable city phrase.
    city_candidate = re.sub(r"^.*?\b(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln)\b\s+", "", city_candidate, flags=re.I)
    city_words = city_candidate.split()
    if len(city_words) > 5:
        city_candidate = " ".join(city_words[-4:])
    return city_candidate.strip(), normalize_state(match.group(2))


def date_candidates_from_text(text: str, datetimes: Iterable[str] = ()) -> list[date]:
    candidates: set[date] = set()
    for raw in datetimes:
        date_text, _ = parse_date_prefix(raw)
        if date_text:
            try:
                candidates.add(date.fromisoformat(date_text))
            except ValueError:
                pass
    for match in re.finditer(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,|\s)+\s*(20\d{{2}})\b",
        text or "",
        re.I,
    ):
        month = month_number(match.group(1))
        try:
            candidates.add(date(int(match.group(3)), month, int(match.group(2))))
        except ValueError:
            pass
    for match in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text or ""):
        try:
            candidates.add(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
        except ValueError:
            pass
    return sorted(candidates)


def choose_future_date(candidates: Iterable[date], today: date) -> date | None:
    upper = today + timedelta(days=LOOKAHEAD_DAYS)
    future = [item for item in candidates if today <= item <= upper]
    return min(future) if future else None


def find_best_link(
    links: Iterable[tuple[str, str]],
    base_url: str,
    title: str,
    city: str = "",
    preferred_text: str = "",
) -> str:
    title_normalized = normalize_name(title)
    city_normalized = normalize_name(city)
    preferred_normalized = normalize_name(preferred_text)
    best_url = ""
    best_score = -1
    for href, text in links:
        absolute = safe_url(urljoin(base_url, href))
        if not absolute:
            continue
        normalized = normalize_name(text)
        score = 0
        if title_normalized and title_normalized in normalized:
            score += 6
        if city_normalized and city_normalized in normalized:
            score += 3
        if preferred_normalized and preferred_normalized in normalized:
            score += 2
        if "ticket" in normalized or "rsvp" in normalized or "register" in normalized:
            score += 1
        if score > best_score:
            best_score = score
            best_url = absolute
    return best_url


def authority_name(source: dict[str, Any]) -> str:
    explicit = str(source.get("authority") or "").strip().lower()
    if explicit in AUTHORITY_RANKS:
        return explicit
    parser = str(source.get("parser") or "jsonld").strip().lower()
    if parser in {"holy_smoke", "space_city", "rural_festival", "official_festival"}:
        return "official_festival"
    if parser in {"tpr"}:
        return "promoter"
    if parser in {"reach_records"}:
        return "artist_label"
    if parser in {"bandsintown_public", "bandsintown_widget"}:
        return "artist_calendar"
    if parser in {"holy_culture", "christian_hits", "christian_festivals"}:
        return "aggregator"
    return "artist_label"


def authority_rank(source: dict[str, Any], default: int = 80) -> int:
    try:
        configured = int(source.get("priority", 0))
    except (TypeError, ValueError):
        configured = 0
    return configured or AUTHORITY_RANKS.get(authority_name(source), default)


def source_priority(source: dict[str, Any], default: int) -> int:
    return authority_rank(source, default)


def is_valid_image_url(value: Any, allow_event_artwork: bool = False) -> bool:
    url = safe_url(value)
    if not url:
        return False
    if not IMAGE_REJECT_PATTERN.search(url):
        return True
    # A file explicitly named like a poster, flyer, tour, or festival graphic can
    # still be legitimate event art. Generic source/label logos are rejected.
    return bool(
        allow_event_artwork
        and re.search(r"(?:poster|flyer|artwork|tour[-_ ]?art|festival|fest[-_ ])", url, re.IGNORECASE)
    )


def ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip()
        key = normalize_name(clean)
        if clean and key and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def schema_is_music_event(raw_event: dict[str, Any]) -> bool:
    raw_type = raw_event.get("@type")
    values = raw_type if isinstance(raw_type, list) else [raw_type]
    return any("musicevent" in normalize_name(str(value)) for value in values if value)

def make_source_event(
    *,
    source: dict[str, Any],
    source_url: str,
    title: str,
    start_date: str,
    start_time: str,
    venue: str,
    address: str,
    city: str,
    state: str,
    artists: list[str],
    checked_at: str,
    ticket_url: str = "",
    official_url: str = "",
    image: str = "",
    price: str = "",
    status: str = "scheduled",
    confidence: str = "high",
    event_type: str = "",
    end_date: str = "",
    priority: int = 80,
    headliner: str = "",
    lineup_explicit: bool | None = None,
    music_confirmed: bool = True,
    external_ids: dict[str, str] | None = None,
) -> dict[str, Any]:
    identifier = event_hash([source_url, title, start_date, venue, city, state])
    event_type = event_type or detect_event_type(title)
    clean_artists = ordered_unique(artists)
    authority = authority_name(source)
    rank = max(priority, authority_rank(source, priority))
    explicit_lineup = bool(source.get("lineupExplicit", False)) if lineup_explicit is None else bool(lineup_explicit)
    configured_headliner = str(headliner or source.get("headliner") or "").strip()
    chosen_headliner = configured_headliner if configured_headliner in clean_artists else (clean_artists[0] if clean_artists else "")
    image_policy = str(source.get("imagePolicy") or "event_artwork").strip().lower()
    configured_artwork = safe_url(source.get("eventArtworkUrl"))
    event_artwork = configured_artwork or (safe_url(image) if image_policy == "event_artwork" and is_valid_image_url(image, True) else "")
    source_link = official_url or source_url
    source_record = {
        "name": str(source.get("name") or "Official source"),
        "url": source_link,
        "type": str(source.get("parser") or "official"),
        "authority": authority,
        "priority": rank,
    }
    event = {
        "id": f"official:{identifier}",
        "title": title,
        "startDate": start_date,
        "startTime": start_time,
        "timezone": "",
        "venue": venue or "Venue not provided",
        "address": address,
        "city": city,
        "state": state.upper(),
        "country": "US",
        "artists": clean_artists,
        "headliner": chosen_headliner,
        "eventType": event_type,
        "status": status,
        "ticketUrl": ticket_url or source_link,
        "officialUrl": source_link,
        "image": "",
        "eventArtwork": event_artwork,
        "price": price,
        "sourceName": source_record["name"],
        "sources": [source_record],
        "lastVerified": checked_at,
        "confidence": confidence,
        "sourcePriority": rank,
        "sourceAuthority": authority,
        "lineupExplicit": explicit_lineup,
        "festivalLineupAuthoritative": bool(
            event_type == "festival"
            and explicit_lineup
            and authority in {"official_festival", "official_event", "manual_verified"}
        ),
        "musicConfirmed": bool(music_confirmed),
        "requiresCorroboration": bool(source.get("discoveryOnly", False)),
        "artistEvidence": [{
            "artists": clean_artists,
            "headliner": chosen_headliner,
            "authority": authority,
            "priority": rank,
            "lineupExplicit": explicit_lineup,
            "sourceUrl": source_link,
        }],
        "artworkEvidence": ([{
            "url": event_artwork,
            "authority": authority,
            "priority": rank,
            "kind": "event",
            "sourceUrl": source_link,
        }] if event_artwork else []),
        "externalIds": external_ids or {},
    }
    if end_date:
        event["endDate"] = end_date
    return event

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


def collect_jsonld_source_from_html(
    source: dict[str, Any],
    url: str,
    html: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    parser = JsonLdScriptParser()
    parser.feed(html)
    events: list[dict[str, Any]] = []
    configured_artists = ordered_unique([
        *[str(item).strip() for item in source.get("artists", []) if str(item).strip()],
        str(source.get("artist") or "").strip(),
    ])

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
            music_confirmed = schema_is_music_event(raw_event) or bool(source.get("musicConfirmed", False))
            if not music_confirmed:
                continue
            start_date, start_time = parse_date_prefix(raw_event.get("startDate"))
            end_date, _ = parse_date_prefix(raw_event.get("endDate"))
            if not start_date:
                continue
            venue, street, city, state, country = extract_address(raw_event.get("location"))
            state = normalize_state(state) or state.upper()
            if not city or state not in US_STATE_CODES or not is_us_location(state, country):
                continue
            performer_names = flatten_names(raw_event.get("performer"))
            artists = match_tracked_artists(performer_names, alias_lookup)
            event_type = detect_event_type(title)
            # A configured artist is a safe fallback for a dedicated artist page,
            # but never authoritative evidence for a festival lineup.
            if not artists and event_type != "festival":
                artists = configured_artists
            if not artists:
                artists = match_artists_in_text(" ".join([title, *performer_names]), alias_lookup)
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
            events.append(make_source_event(
                source=source,
                source_url=url,
                title=title,
                start_date=start_date,
                end_date=end_date,
                start_time=start_time,
                venue=venue or "Venue not provided",
                address=street,
                city=city,
                state=state,
                artists=artists,
                headliner=artists[0] if artists else "",
                checked_at=checked_at,
                ticket_url=ticket_url or url,
                official_url=safe_url(raw_event.get("url")) or url,
                image=image,
                status=schema_status(raw_event.get("eventStatus")),
                event_type=event_type,
                lineup_explicit=bool(performer_names),
                music_confirmed=True,
                priority=source_priority(source, 90),
            ))
    return events

def collect_reach_records_source(
    source: dict[str, Any],
    url: str,
    html: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    """Parse Reach Records' consolidated and artist calendar cards.

    Reach renders each card as a sequence of headings: day, month, year,
    artist, event/venue, and city/state. Some artist-page cards omit the
    artist heading, so an artist configured on that source is used as a safe
    fallback. The consolidated page intentionally has no fallback.
    """

    page = PageContentParser()
    page.feed(html)
    headings = [text for _, text in page.headings if text is not None]
    configured_artists = [
        str(item).strip() for item in source.get("artists", []) if str(item).strip()
    ]
    source_artist = str(source.get("artist") or "").strip()
    if source_artist:
        configured_artists.append(source_artist)
    configured_artists = sorted(set(configured_artists), key=str.casefold)

    events: list[dict[str, Any]] = []
    for index in range(max(0, len(headings) - 5)):
        if not re.fullmatch(r"\d{1,2}", headings[index]):
            continue
        day = int(headings[index])
        month_text = headings[index + 1]
        year_text = headings[index + 2]
        if not month_number(month_text) or not re.fullmatch(r"20\d{2}", year_text):
            continue

        artist_text = headings[index + 3]
        title = normalize_whitespace(headings[index + 4]).strip(" -–—")
        location = headings[index + 5]
        if not title or is_non_show(title):
            continue

        artists = match_artists_in_text(f"{artist_text} {title}", alias_lookup)
        if not artists and configured_artists:
            artists = configured_artists
        if not artists:
            continue

        city, state = parse_city_state(location)
        if not city or state not in US_STATE_CODES:
            continue
        start_date = infer_date(month_text, day, int(year_text), now_utc().date())
        if not start_date:
            continue

        ticket_url = find_best_link(page.links, url, title, city, "tickets") or url
        venue = "Venue not provided" if detect_event_type(title) == "festival" else title
        events.append(make_source_event(
            source=source,
            source_url=url,
            title=title,
            start_date=start_date,
            start_time="",
            venue=venue,
            address="",
            city=city,
            state=state,
            artists=artists,
            checked_at=checked_at,
            ticket_url=ticket_url,
            official_url=url,
            image="",
            lineup_explicit=False,
            music_confirmed=True,
            priority=source_priority(source, 88),
        ))
    return merge_events(events)

def collect_bandsintown_widget_source(
    source: dict[str, Any],
    url: str,
    html: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    page = PageContentParser()
    page.feed(html)
    text = normalize_whitespace(page.text)
    pattern = re.compile(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})\s+"
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(.+?)\s+@\s+"
        r"(\d{1,2}(?::\d{2})?\s*[AP]M)\s+"
        r"([A-Za-z0-9 .()'&-]+),\s*([A-Z]{2}),\s*United States",
        re.I,
    )
    ticket_links = [
        safe_url(urljoin(url, href))
        for href, link_text in page.links
        if "ticket" in normalize_name(link_text) and safe_url(urljoin(url, href))
    ]
    configured_artists = [
        str(item).strip() for item in source.get("artists", []) if str(item).strip()
    ]
    artist = str(source.get("artist") or "").strip()
    if artist:
        configured_artists.append(artist)
    events: list[dict[str, Any]] = []
    today = now_utc().date()
    explicit_year = source.get("year")
    try:
        explicit_year = int(explicit_year) if explicit_year else None
    except (TypeError, ValueError):
        explicit_year = None
    for number, match in enumerate(pattern.finditer(text)):
        title = normalize_whitespace(match.group(3)).strip(" -–—")
        city = normalize_whitespace(match.group(5))
        state = normalize_state(match.group(6))
        start_date = infer_date(match.group(1), int(match.group(2)), explicit_year, today)
        if not title or not start_date or not state or is_non_show(title):
            continue
        artists = sorted(set(configured_artists), key=str.casefold)
        if not artists:
            artists = match_artists_in_text(f"{title} {text[:500]}", alias_lookup)
        if not artists:
            continue
        ticket_url = ticket_links[number] if number < len(ticket_links) else url
        events.append(make_source_event(
            source=source,
            source_url=url,
            title=title,
            start_date=start_date,
            start_time=parse_clock(match.group(4)),
            venue=title,
            address="",
            city=city,
            state=state,
            artists=artists,
            checked_at=checked_at,
            ticket_url=ticket_url,
            official_url=url,
            image=safe_url(page.meta.get("og:image")),
            priority=source_priority(source, 85),
        ))
    return events


def collect_tpr_source(
    source: dict[str, Any],
    url: str,
    html: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    page = PageContentParser()
    page.feed(html)
    text = normalize_whitespace(page.text)
    pattern = re.compile(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}}),\s+(20\d{{2}})\s+"
        r"(\d{1,2}:\d{2}\s*[AP]M)\s+(.+?),\s*([A-Z]{2})\s+"
        r"Event Info\s+Buy Tickets",
        re.I,
    )
    title = str(source.get("eventTitle") or "").strip()
    if not title:
        title = next((text for tag, text in page.headings if tag == "h1" and text), "TPR Live Event")
    configured_artists = [
        str(item).strip() for item in source.get("artists", []) if str(item).strip()
    ]
    artist = str(source.get("artist") or "").strip()
    if artist:
        configured_artists.append(artist)
    artists = sorted(set(configured_artists), key=str.casefold)
    if not artists:
        artists = match_artists_in_text(text, alias_lookup)
    if not artists:
        return []
    ticket_links = [
        safe_url(urljoin(url, href))
        for href, link_text in page.links
        if "buy tickets" in normalize_name(link_text) and safe_url(urljoin(url, href))
    ]
    events: list[dict[str, Any]] = []
    for number, match in enumerate(pattern.finditer(text)):
        city = normalize_whitespace(match.group(5))
        state = normalize_state(match.group(6))
        start_date = infer_date(match.group(1), int(match.group(2)), int(match.group(3)), now_utc().date())
        if not start_date or not state:
            continue
        ticket_url = ticket_links[number] if number < len(ticket_links) else url
        events.append(make_source_event(
            source=source,
            source_url=url,
            title=title,
            start_date=start_date,
            start_time=parse_clock(match.group(4)),
            venue=str(source.get("venue") or "Venue not provided"),
            address="",
            city=city,
            state=state,
            artists=artists,
            checked_at=checked_at,
            ticket_url=ticket_url,
            official_url=url,
            image=safe_url(page.meta.get("og:image")),
            priority=source_priority(source, 80),
        ))
    return events


def collect_holy_smoke_source(
    source: dict[str, Any],
    url: str,
    html: str,
    client: HttpClient,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    landing = PageContentParser()
    landing.feed(html)
    product_url = url if "/products/" in url else ""
    if not product_url:
        for href, link_text in landing.links:
            absolute = safe_url(urljoin(url, href))
            if absolute and "/products/holy-smoke" in absolute and "holy smoke" in normalize_name(link_text):
                product_url = absolute
                break
    if not product_url:
        return []
    product_html = html if product_url == url else client.get_text(product_url)
    page = PageContentParser()
    page.feed(product_html)
    text = normalize_whitespace(page.text)
    title = next(
        (heading for _, heading in page.headings if "holy smoke" in normalize_name(heading)),
        str(source.get("eventTitle") or "HOLY SMOKE!"),
    )
    date_match = re.search(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?:,\s*(\d{{1,2}}))?(?:,\s*\+?\s*(\d{{1,2}}))?,\s*(20\d{{2}})\b",
        text,
        re.I,
    )
    if not date_match:
        return []
    month_text = date_match.group(1)
    year = int(date_match.group(5))
    start_date = infer_date(month_text, int(date_match.group(2)), year, now_utc().date())
    end_day = date_match.group(4) or date_match.group(3) or date_match.group(2)
    end_date = infer_date(month_text, int(end_day), year, now_utc().date())
    if not start_date:
        return []
    venue = str(source.get("venue") or "Rocketown")
    city = str(source.get("city") or "Nashville")
    state = normalize_state(str(source.get("state") or "TN")) or "TN"
    for chunk in page.text_chunks:
        location_match = re.search(
            r"^([A-Za-z0-9 .&'!()-]{2,80})\s*[-–—]\s*([A-Za-z .'-]+),\s*([A-Za-z ]{2,20})$",
            chunk,
            re.I,
        )
        if location_match:
            parsed_state = normalize_state(location_match.group(3))
            if parsed_state:
                venue = normalize_whitespace(location_match.group(1))
                city = normalize_whitespace(location_match.group(2))
                state = parsed_state
                break
    configured_artists = [
        str(item).strip() for item in source.get("artists", []) if str(item).strip()
    ]
    artists = list(configured_artists)
    if not configured_artists:
        artists.extend(match_artists_in_text(text, alias_lookup))
    lineup_url = safe_url(source.get("lineupUrl"))
    if not lineup_url:
        lineup_url = next(
            (
                safe_url(urljoin(product_url, href))
                for href, link_text in page.links
                if "schedule" in normalize_name(link_text) and safe_url(urljoin(product_url, href))
            ),
            "",
        )
    if lineup_url and not configured_artists:
        try:
            lineup_html = client.get_text(lineup_url)
            lineup_page = PageContentParser()
            lineup_page.feed(lineup_html)
            artists.extend(match_artists_in_text(lineup_page.text, alias_lookup))
        except CollectorError:
            pass
    artists = sorted(set(artists), key=str.casefold)
    if not artists:
        return []
    prices = [float(value) for value in re.findall(r"\$(\d+(?:\.\d{2})?)", text)]
    price = f"${min(prices):,.0f}+" if prices else ""
    return [make_source_event(
        source=source,
        source_url=url,
        title=title,
        start_date=start_date,
        end_date=end_date,
        start_time="",
        venue=venue,
        address=str(source.get("address") or "601 4th Ave S"),
        city=city,
        state=state,
        artists=artists,
        checked_at=checked_at,
        ticket_url=product_url,
        official_url=product_url,
        image=safe_url(page.meta.get("og:image")),
        price=price,
        event_type="festival",
        priority=source_priority(source, 100),
    )]


def collect_space_city_source(
    source: dict[str, Any],
    url: str,
    html: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    """Monitor the organizer and venue pages for Space City Fest.

    Discovery Green event URLs encode the date, while the organizer page may
    publish a date in visible text. Only the event-specific introduction is
    scanned so unrelated dates from venue navigation do not become false
    listings.
    """

    page = PageContentParser()
    page.feed(html)
    text = normalize_whitespace(page.text)

    event_date: date | None = None
    path = urlparse(url).path
    url_date = re.search(
        rf"/({MONTH_PATTERN})-(\d{{1,2}})-(20\d{{2}})(?:-|/|$)",
        path,
        re.I,
    )
    if url_date:
        inferred = infer_date(
            url_date.group(1), int(url_date.group(2)), int(url_date.group(3)), now_utc().date()
        )
        if inferred:
            event_date = date.fromisoformat(inferred)

    configured_date = str(source.get("startDate") or "").strip()
    if not event_date and configured_date:
        try:
            event_date = date.fromisoformat(configured_date)
        except ValueError:
            event_date = None

    if not event_date:
        intro = re.split(
            r"\b(?:VIEW SIMILAR EVENTS|Want to learn more about Space City Church)\b",
            text,
            maxsplit=1,
            flags=re.I,
        )[0]
        candidates = date_candidates_from_text(intro, page.datetimes[:4])
        event_date = choose_future_date(candidates, now_utc().date())

    if not event_date or event_date < now_utc().date():
        return []

    configured_artists = [
        str(item).strip() for item in source.get("artists", []) if str(item).strip()
    ]
    artists = configured_artists or match_artists_in_text(text, alias_lookup)
    artists = ordered_unique(artists)
    if not artists:
        return []

    city = str(source.get("city") or "Houston")
    state = normalize_state(str(source.get("state") or "TX")) or "TX"
    configured_time = str(source.get("startTime") or "").strip()
    start_time = configured_time or parse_clock(text)
    return [make_source_event(
        source=source,
        source_url=url,
        title=str(source.get("eventTitle") or "Space City Fest"),
        start_date=event_date.isoformat(),
        start_time=start_time,
        venue=str(source.get("venue") or "Discovery Green"),
        address=str(source.get("address") or "1600 McKinney St"),
        city=city,
        state=state,
        artists=artists,
        checked_at=checked_at,
        ticket_url=find_best_link(page.links, url, "Space City Fest", city, "register") or url,
        official_url=url,
        image=safe_url(page.meta.get("og:image")),
        price=str(source.get("price") or "Free"),
        event_type="festival",
        priority=source_priority(source, 100),
    )]

def collect_holy_culture_detail(
    source: dict[str, Any],
    detail_url: str,
    html: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    detail_source = dict(source)
    detail_source["name"] = f"Holy Culture: {source.get('name', 'Events')}"
    jsonld_events = collect_jsonld_source_from_html(
        detail_source, detail_url, html, alias_lookup, checked_at
    )
    if jsonld_events:
        for event in jsonld_events:
            event["confidence"] = "medium"
            event["sourcePriority"] = source_priority(source, 55)
        return jsonld_events
    page = PageContentParser()
    page.feed(html)
    text = normalize_whitespace(page.text)
    title = next(
        (heading for tag, heading in page.headings if tag == "h1" and heading),
        next((heading for _, heading in page.headings if heading), ""),
    )
    artists = match_artists_in_text(text, alias_lookup)
    if not title or not artists or is_non_show(title):
        return []
    date_block = ""
    time_block = ""
    location_block = ""
    chunks = page.text_chunks
    for index, chunk in enumerate(chunks):
        normalized = normalize_name(chunk)
        if normalized == "date" and not date_block:
            date_block = " ".join(chunks[index + 1:index + 4])
        elif normalized == "time" and not time_block:
            time_block = " ".join(chunks[index + 1:index + 4])
        elif normalized == "location" and not location_block:
            collected: list[str] = []
            for next_chunk in chunks[index + 1:index + 9]:
                if normalize_name(next_chunk) in {"organizer", "share this event"}:
                    break
                collected.append(next_chunk)
            location_block = " ".join(collected)
    date_candidates = date_candidates_from_text(date_block or text, page.datetimes)
    event_date = choose_future_date(date_candidates, now_utc().date())
    if not event_date:
        return []
    city, state = extract_city_state_from_block(location_block)
    if not city or not state:
        return []
    venue = "Venue not provided"
    if location_block:
        first_piece = normalize_whitespace(location_block.split(city, 1)[0]).strip(" ,-–—")
        if first_piece and len(first_piece) <= 100:
            venue = first_piece
    ticket_url = find_best_link(page.links, detail_url, title, city, "ticket") or detail_url
    return [make_source_event(
        source=detail_source,
        source_url=detail_url,
        title=title,
        start_date=event_date.isoformat(),
        start_time=parse_clock(time_block),
        venue=venue,
        address="",
        city=city,
        state=state,
        artists=artists,
        checked_at=checked_at,
        ticket_url=ticket_url,
        official_url=detail_url,
        image=safe_url(page.meta.get("og:image")),
        confidence="medium",
        priority=source_priority(source, 55),
    )]


def collect_holy_culture_source(
    source: dict[str, Any],
    url: str,
    html: str,
    client: HttpClient,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    """Follow likely CHH event detail links from Holy Culture's calendar.

    Holy Culture mixes internal event pages with links to official artist and
    festival pages. Internal event pages are reviewed broadly, while external
    links are followed only when their anchor text names a tracked artist or a
    clearly relevant CHH event.
    """

    page = PageContentParser()
    page.feed(html)
    base_host = urlparse(url).netloc
    urls: list[str] = []
    seen: set[str] = set()
    relevant_terms = ("festival", "concert", "tour", "hip hop", "rap", "chh", "holy smoke")

    for href, link_text in page.links:
        absolute = safe_url(urljoin(url, href))
        if not absolute or absolute in seen:
            continue
        parsed = urlparse(absolute)
        path = parsed.path.rstrip("/")
        normalized_link = normalize_name(link_text)
        is_internal_detail = (
            parsed.netloc == base_host
            and path.startswith("/events/")
            and path != "/events"
        )
        is_relevant_external = (
            parsed.netloc != base_host
            and bool(
                match_artists_in_text(link_text, alias_lookup)
                or any(term in normalized_link for term in relevant_terms)
            )
        )
        if not is_internal_detail and not is_relevant_external:
            continue
        seen.add(absolute)
        urls.append(absolute)

    max_pages = int(source.get("maxPages") or 35)
    events: list[dict[str, Any]] = []
    for detail_url in urls[:max_pages]:
        try:
            detail_html = client.get_text(detail_url)
            if "indietribe.us/products/holy-smoke" in detail_url:
                # Holy Smoke has its own higher-confidence first-party parser.
                continue
            events.extend(collect_holy_culture_detail(
                source, detail_url, detail_html, alias_lookup, checked_at
            ))
        except CollectorError:
            continue
    return merge_events(events)


def parse_us_numeric_date(value: str) -> str:
    """Parse M/D/YY or M/D/YYYY into ISO format."""

    match = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\s*", value or "")
    if not match:
        return ""
    month, day, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def parse_human_date_range(value: str) -> tuple[str, str]:
    """Parse festival date text such as 'Aug 28 - Aug 30, 2026'."""

    cleaned = normalize_whitespace(value).replace("–", "-").replace("—", "-")
    range_match = re.fullmatch(
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})\s*-\s*"
        rf"(?:({MONTH_PATTERN})\s+)?(\d{{1,2}}),\s*(20\d{{2}})",
        cleaned,
        re.I,
    )
    if range_match:
        start_month, start_day, end_month, end_day, year = range_match.groups()
        start_date = infer_date(start_month, int(start_day), int(year), now_utc().date())
        end_date = infer_date(end_month or start_month, int(end_day), int(year), now_utc().date())
        return start_date, end_date

    single_match = re.fullmatch(
        rf"({MONTH_PATTERN})\s+(\d{{1,2}}),\s*(20\d{{2}})",
        cleaned,
        re.I,
    )
    if single_match:
        month, day, year = single_match.groups()
        return infer_date(month, int(day), int(year), now_utc().date()), ""
    return "", ""


def parse_single_city_state(value: str) -> tuple[str, str]:
    """Parse one city/state pair while rejecting multi-state tour summaries."""

    cleaned = normalize_whitespace(value)
    if cleaned.count(",") != 1:
        return "", ""
    city, state = parse_city_state(cleaned)
    if not city or not state:
        return "", ""
    if normalize_name(city) in US_STATE_NAMES or city.upper() in US_STATE_CODES:
        return "", ""
    return city, state


def collect_christian_hits_source(
    source: dict[str, Any],
    url: str,
    html: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    """Parse ChristianHits.Net's consolidated upcoming-show feed."""

    page = PageContentParser()
    page.feed(html)
    chunks = [normalize_whitespace(chunk) for chunk in page.text_chunks if normalize_whitespace(chunk)]
    event_pattern = re.compile(
        r"^(?P<title>.+?):\s*(?P<start>\d{1,2}/\d{1,2}/(?:\d{2}|\d{4}))"
        r"(?:\s*-\s*(?P<end>\d{1,2}/\d{1,2}/(?:\d{2}|\d{4})))?$"
    )
    matches = [(index, event_pattern.match(chunk)) for index, chunk in enumerate(chunks)]
    matches = [(index, match) for index, match in matches if match]
    events: list[dict[str, Any]] = []

    for position, (index, match) in enumerate(matches):
        assert match is not None
        title = normalize_whitespace(match.group("title")).strip(" -–—")
        start_date = parse_us_numeric_date(match.group("start"))
        end_date = parse_us_numeric_date(match.group("end") or "")
        if not title or not start_date or is_non_show(title):
            continue

        next_event_index = matches[position + 1][0] if position + 1 < len(matches) else len(chunks)
        location_index = -1
        city = ""
        state = ""
        for candidate_index in range(index + 1, min(index + 5, next_event_index)):
            city, state = parse_single_city_state(chunks[candidate_index])
            if city and state:
                location_index = candidate_index
                break
        if location_index < 0:
            # Multi-state tour summaries are intentionally not published as one event.
            continue

        lineup_text = " ".join(chunks[location_index + 1:next_event_index])
        artists = match_artists_in_text(f"{title} {lineup_text}", alias_lookup)
        configured = [str(item).strip() for item in source.get("artists", []) if str(item).strip()]
        artist = str(source.get("artist") or "").strip()
        if artist:
            configured.append(artist)
        artists = sorted(set(artists) | set(configured), key=str.casefold)
        if not artists:
            continue

        ticket_url = find_best_link(page.links, url, title, city, "ticket") or url
        event_type = detect_event_type(title)
        events.append(make_source_event(
            source=source,
            source_url=url,
            title=title,
            start_date=start_date,
            end_date=end_date,
            start_time="",
            venue=title if event_type == "festival" else "Venue not provided",
            address="",
            city=city,
            state=state,
            artists=artists,
            checked_at=checked_at,
            ticket_url=ticket_url,
            official_url=ticket_url,
            image=safe_url(page.meta.get("og:image")),
            confidence="medium",
            event_type=event_type,
            priority=source_priority(source, 58),
        ))
    return merge_events(events)


def collect_christian_festivals_source(
    source: dict[str, Any],
    url: str,
    html: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    """Parse the ChristianHits/ChristianRock U.S. festival directory."""

    page = PageContentParser()
    page.feed(html)
    chunks = [normalize_whitespace(chunk) for chunk in page.text_chunks if normalize_whitespace(chunk)]
    events: list[dict[str, Any]] = []

    for index, chunk in enumerate(chunks):
        if "|" not in chunk:
            continue
        date_text, location_text = [part.strip() for part in chunk.split("|", 1)]
        start_date, end_date = parse_human_date_range(date_text)
        city, state = parse_single_city_state(location_text)
        if not start_date or not city or not state:
            continue

        title = ""
        for previous in range(index - 1, max(-1, index - 5), -1):
            candidate = chunks[previous].strip(" -*")
            if not candidate:
                continue
            if re.fullmatch(rf"({MONTH_PATTERN})\s+20\d{{2}}", candidate, re.I):
                continue
            if normalize_name(candidate) in {
                "upcoming christian music festivals",
                "discover festivals across the united states and world wide",
                "image",
            }:
                continue
            title = candidate
            break
        if not title or is_non_show(title):
            continue

        stop = len(chunks)
        for following in range(index + 1, len(chunks)):
            if "get tickets or more information" in normalize_name(chunks[following]):
                stop = following
                break
            if "|" in chunks[following] and parse_human_date_range(chunks[following].split("|", 1)[0])[0]:
                stop = following
                break
        lineup_text = " ".join(chunks[index + 1:stop])
        artists = match_artists_in_text(lineup_text, alias_lookup)
        if not artists:
            continue

        ticket_url = find_best_link(page.links, url, title, city, "get tickets") or url
        events.append(make_source_event(
            source=source,
            source_url=url,
            title=title,
            start_date=start_date,
            end_date=end_date,
            start_time="",
            venue=title,
            address="",
            city=city,
            state=state,
            artists=artists,
            checked_at=checked_at,
            ticket_url=ticket_url,
            official_url=ticket_url,
            image=safe_url(page.meta.get("og:image")),
            confidence="medium",
            event_type="festival",
            priority=source_priority(source, 60),
        ))
    return merge_events(events)


def collect_bandsintown_public_source(
    source: dict[str, Any],
    url: str,
    html: str,
    client: HttpClient,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    """Follow upcoming event cards on a public Bandsintown artist page.

    Event detail pages are preferred because they usually expose structured
    event metadata. Past-show links are excluded by their position on the
    artist page.
    """

    page = PageContentParser()
    page.feed(html)
    chunks = [normalize_whitespace(chunk) for chunk in page.text_chunks]
    normalized_chunks = [normalize_name(chunk) for chunk in chunks]
    try:
        section_start = normalized_chunks.index("all concerts and live streams")
    except ValueError:
        return []
    section_end = next(
        (index for index in range(section_start + 1, len(chunks)) if normalized_chunks[index] == "past shows"),
        len(chunks),
    )

    upcoming_urls: list[str] = []
    seen: set[str] = set()
    for href, link_text in page.links:
        absolute = safe_url(urljoin(url, href))
        if not absolute or "/e/" not in urlparse(absolute).path:
            continue
        positions = [
            index for index in range(section_start + 1, section_end)
            if normalize_name(chunks[index]) == normalize_name(link_text)
        ]
        if not positions or absolute in seen:
            continue
        seen.add(absolute)
        upcoming_urls.append(absolute)

    max_pages = int(source.get("maxPages") or 15)
    events: list[dict[str, Any]] = []
    for event_url in upcoming_urls[:max_pages]:
        try:
            if not robots_allows(event_url):
                continue
            detail_html = client.get_text(event_url)
            detail_events = collect_jsonld_source_from_html(
                source, event_url, detail_html, alias_lookup, checked_at
            )
            events.extend(detail_events)
        except CollectorError:
            continue
    return merge_events(events)



def collect_wix_event_list_source(
    source: dict[str, Any],
    url: str,
    html: str,
    client: HttpClient,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    """Follow event-detail links from a Wix event-list page."""

    page = PageContentParser()
    page.feed(html)
    detail_urls: list[str] = []
    seen: set[str] = set()
    for href, _ in page.links:
        absolute = safe_url(urljoin(url, href))
        if not absolute or "/event-details/" not in urlparse(absolute).path:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        detail_urls.append(absolute)

    events: list[dict[str, Any]] = []
    max_pages = int(source.get("maxPages") or 20)
    for detail_url in detail_urls[:max_pages]:
        try:
            if not robots_allows(detail_url):
                continue
            detail_html = client.get_text(detail_url)
            events.extend(collect_jsonld_source_from_html(
                source, detail_url, detail_html, alias_lookup, checked_at
            ))
        except CollectorError:
            continue
    return merge_events(events)


def collect_rural_festival_source(
    source: dict[str, Any],
    url: str,
    html: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> list[dict[str, Any]]:
    """Parse the official Rural Music Festival Wix event page."""

    page = PageContentParser()
    page.feed(html)
    text = normalize_whitespace(page.text).replace("–", "-").replace("—", "-")
    range_pattern = re.compile(
        rf"({MONTH_PATTERN})\s+(\d{{1,2}}),\s*(20\d{{2}}),\s*"
        r"(\d{1,2}(?::\d{2})?\s*[AP]M)\s*-\s*"
        rf"({MONTH_PATTERN})\s+(\d{{1,2}}),\s*(20\d{{2}}),\s*"
        r"(\d{1,2}(?::\d{2})?\s*[AP]M)",
        re.I,
    )
    match = range_pattern.search(text)
    if not match:
        return []
    start_date = infer_date(match.group(1), int(match.group(2)), int(match.group(3)), now_utc().date())
    end_date = infer_date(match.group(5), int(match.group(6)), int(match.group(7)), now_utc().date())
    city = str(source.get("city") or "Isle").strip()
    state = normalize_state(str(source.get("state") or "MN"))
    artists = [str(item).strip() for item in source.get("artists", []) if str(item).strip()]
    if not start_date or not end_date or not city or not state or not artists:
        return []
    title = str(source.get("eventTitle") or "Rural Music Festival 2026").strip()
    return [make_source_event(
        source=source,
        source_url=url,
        title=title,
        start_date=start_date,
        end_date=end_date,
        start_time=parse_clock(match.group(4)),
        venue=str(source.get("venue") or "Redemption Hill"),
        address=str(source.get("address") or "43694 State Hwy 47"),
        city=city,
        state=state,
        artists=artists,
        checked_at=checked_at,
        ticket_url=url,
        official_url=url,
        image=safe_url(page.meta.get("og:image")),
        price=str(source.get("price") or "Free"),
        confidence="high",
        event_type="festival",
        priority=source_priority(source, 102),
    )]


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
    parser_type = str(source.get("parser") or "jsonld").strip().lower()
    if parser_type == "reach_records":
        return collect_reach_records_source(source, url, html, alias_lookup, checked_at)
    if parser_type == "bandsintown_widget":
        return collect_bandsintown_widget_source(source, url, html, alias_lookup, checked_at)
    if parser_type == "tpr":
        return collect_tpr_source(source, url, html, alias_lookup, checked_at)
    if parser_type == "holy_smoke":
        return collect_holy_smoke_source(source, url, html, client, alias_lookup, checked_at)
    if parser_type == "space_city":
        return collect_space_city_source(source, url, html, alias_lookup, checked_at)
    if parser_type == "holy_culture":
        return collect_holy_culture_source(source, url, html, client, alias_lookup, checked_at)
    if parser_type == "christian_hits":
        return collect_christian_hits_source(source, url, html, alias_lookup, checked_at)
    if parser_type == "christian_festivals":
        return collect_christian_festivals_source(source, url, html, alias_lookup, checked_at)
    if parser_type == "bandsintown_public":
        return collect_bandsintown_public_source(source, url, html, client, alias_lookup, checked_at)
    if parser_type == "rural_festival":
        return collect_rural_festival_source(source, url, html, alias_lookup, checked_at)
    if parser_type == "wix_event_list":
        return collect_wix_event_list_source(source, url, html, client, alias_lookup, checked_at)
    return collect_jsonld_source_from_html(source, url, html, alias_lookup, checked_at)


def attraction_cache_is_fresh(entry: dict[str, Any]) -> bool:
    checked = entry.get("checkedAt")
    if not isinstance(checked, str):
        return False
    try:
        checked_date = datetime.fromisoformat(checked.replace("Z", "+00:00"))
    except ValueError:
        return False
    # Version-1 cache records did not include image resolution. Refresh them once.
    if entry.get("id") and not entry.get("imageChecked"):
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
    cached = cache.get(canonical)
    if explicit_id:
        if not isinstance(cached, dict):
            cache[canonical] = {"id": explicit_id, "matchedName": canonical, "checkedAt": checked_at}
        return explicit_id
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
    exact.sort(key=lambda item: int(item.get("upcomingEvents", {}).get("_total") or 0), reverse=True)
    selected = exact[0] if exact else None
    image = choose_image(selected.get("images")) if selected else ""
    cache[canonical] = {
        "id": selected.get("id") if selected else None,
        "matchedName": selected.get("name") if selected else None,
        "image": image if is_valid_image_url(image) else "",
        "imageChecked": True,
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


def ticketmaster_is_music(raw_event: dict[str, Any]) -> bool:
    classifications = raw_event.get("classifications", [])
    if not isinstance(classifications, list):
        return False
    for item in classifications:
        if not isinstance(item, dict):
            continue
        segment = item.get("segment", {})
        if normalize_name(str(segment.get("name") or "")) == "music":
            return True
    return False


def extract_ticketmaster_event(
    raw_event: dict[str, Any],
    fallback_artist: str,
    alias_lookup: dict[str, str],
    checked_at: str,
) -> dict[str, Any] | None:
    title = str(raw_event.get("name") or "").strip()
    if not title or is_non_show(title) or not ticketmaster_is_music(raw_event):
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
    if not city or state not in US_STATE_CODES:
        return None

    attraction_items = raw_event.get("_embedded", {}).get("attractions", [])
    attraction_names = [
        str(item.get("name") or "") for item in attraction_items
        if isinstance(item, dict)
    ] if isinstance(attraction_items, list) else []
    artists: list[str] = []
    for name in attraction_names:
        matched = match_tracked_artists([name], alias_lookup)
        artists.extend(matched)
    artists = ordered_unique(artists)
    if fallback_artist and fallback_artist not in artists:
        artists.insert(0, fallback_artist)
    if not artists:
        return None
    event_url = safe_url(raw_event.get("url"))
    source = {
        "name": "Ticketmaster",
        "parser": "ticketmaster",
        "authority": "venue_ticket",
        "priority": AUTHORITY_RANKS["venue_ticket"],
        "imagePolicy": "event_artwork",
    }
    return make_source_event(
        source=source,
        source_url=event_url,
        title=title,
        start_date=local_date,
        start_time=local_time[:5] if local_time else "",
        venue=venue,
        address=address,
        city=city,
        state=state,
        artists=artists,
        headliner=artists[0],
        checked_at=checked_at,
        ticket_url=event_url,
        official_url=event_url,
        image=choose_image(raw_event.get("images")),
        price=ticketmaster_price(raw_event),
        status=ticketmaster_status(raw_event),
        event_type=detect_event_type(title),
        lineup_explicit=True,
        music_confirmed=True,
        priority=AUTHORITY_RANKS["venue_ticket"],
        external_ids={"ticketmaster": event_id},
    ) | {"id": f"ticketmaster:{event_id}", "timezone": str(raw_event.get("dates", {}).get("timezone") or "")}

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


def normalize_event_title(value: str) -> str:
    tokens = normalize_name(value).split()
    tokens = [token for token in tokens if token not in TITLE_STOPWORDS and not re.fullmatch(r"20\d{2}", token)]
    return " ".join(tokens)


def normalize_venue(value: str) -> str:
    normalized = normalize_name(value)
    normalized = normalized.replace("first ave", "first avenue")
    normalized = normalized.replace("work play", "workplay")
    tokens = [token for token in normalized.split() if token not in VENUE_STOPWORDS]
    return " ".join(tokens)


def token_similarity(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return max(SequenceMatcher(None, left, right).ratio(), token_similarity(left, right))


def artist_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a = {normalize_name(value) for value in left.get("artists", []) if value}
    b = {normalize_name(value) for value in right.get("artists", []) if value}
    return bool(a & b)


def external_id_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_ids = left.get("externalIds", {}) if isinstance(left.get("externalIds"), dict) else {}
    right_ids = right.get("externalIds", {}) if isinstance(right.get("externalIds"), dict) else {}
    return any(key in right_ids and value and right_ids.get(key) == value for key, value in left_ids.items())


def source_url_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_urls = {safe_url(item.get("url")) for item in left.get("sources", []) if isinstance(item, dict)}
    right_urls = {safe_url(item.get("url")) for item in right.get("sources", []) if isinstance(item, dict)}
    left_urls.discard("")
    right_urls.discard("")
    return bool(left_urls & right_urls)


def events_are_duplicates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    # A provider event ID is globally authoritative. A shared source URL is not:
    # consolidated calendar pages can contain dozens of unrelated events.
    if external_id_overlap(left, right):
        return True
    if str(left.get("startDate") or "") != str(right.get("startDate") or ""):
        return False
    if normalize_name(str(left.get("city") or "")) != normalize_name(str(right.get("city") or "")):
        return False
    if normalize_state(str(left.get("state") or "")) != normalize_state(str(right.get("state") or "")):
        return False

    left_title = normalize_event_title(str(left.get("title") or ""))
    right_title = normalize_event_title(str(right.get("title") or ""))
    left_venue = normalize_venue(str(left.get("venue") or ""))
    right_venue = normalize_venue(str(right.get("venue") or ""))
    title_score = text_similarity(left_title, right_title)
    venue_score = text_similarity(left_venue, right_venue)
    overlap = artist_overlap(left, right)
    festival_pair = left.get("eventType") == "festival" or right.get("eventType") == "festival"

    if left_venue and right_venue and left_venue == right_venue and (overlap or title_score >= 0.45):
        return True
    if festival_pair and title_score >= 0.66:
        return True
    if overlap and (venue_score >= 0.66 or title_score >= 0.66):
        return True
    if overlap and venue_score >= 0.52 and title_score >= 0.52:
        return True
    return False


def canonical_event_keys(event: dict[str, Any]) -> list[str]:
    event_date = str(event.get("startDate") or "")
    city = normalize_name(str(event.get("city") or ""))
    state = normalize_state(str(event.get("state") or ""))
    venue = normalize_venue(str(event.get("venue") or ""))
    title = normalize_event_title(str(event.get("title") or ""))
    keys: list[str] = []
    for provider, value in (event.get("externalIds") or {}).items() if isinstance(event.get("externalIds"), dict) else []:
        if value:
            keys.append(f"external|{provider}|{value}")
    if event_date and city:
        if venue:
            keys.append(f"venue|{event_date}|{venue}|{city}|{state}")
        if title:
            keys.append(f"title|{event_date}|{title}|{city}|{state}")
    return keys or [normalize_name(str(event.get("id") or event.get("title") or ""))]


def canonical_event_key(event: dict[str, Any]) -> str:
    return canonical_event_keys(event)[0]


def merge_two_events(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    existing_priority = int(existing.get("sourcePriority") or 0)
    incoming_priority = int(incoming.get("sourcePriority") or 0)
    prefer_incoming = incoming_priority > existing_priority
    for key in (
        "title", "startDate", "endDate", "startTime", "timezone", "venue", "address",
        "city", "state", "country", "eventType", "status", "ticketUrl", "officialUrl",
        "price", "lastVerified", "confidence", "headliner",
    ):
        value = incoming.get(key)
        if value and (prefer_incoming or not merged.get(key)):
            merged[key] = value
    merged["sourcePriority"] = max(existing_priority, incoming_priority)
    merged["musicConfirmed"] = bool(existing.get("musicConfirmed") or incoming.get("musicConfirmed"))
    merged["requiresCorroboration"] = bool(existing.get("requiresCorroboration") and incoming.get("requiresCorroboration"))
    merged["artists"] = ordered_unique([*existing.get("artists", []), *incoming.get("artists", [])])
    merged["artistEvidence"] = [*existing.get("artistEvidence", []), *incoming.get("artistEvidence", [])]
    merged["artworkEvidence"] = [*existing.get("artworkEvidence", []), *incoming.get("artworkEvidence", [])]
    merged["festivalLineupAuthoritative"] = bool(existing.get("festivalLineupAuthoritative") or incoming.get("festivalLineupAuthoritative"))
    merged["lineupExplicit"] = bool(existing.get("lineupExplicit") or incoming.get("lineupExplicit"))
    external = dict(existing.get("externalIds", {}) if isinstance(existing.get("externalIds"), dict) else {})
    external.update(incoming.get("externalIds", {}) if isinstance(incoming.get("externalIds"), dict) else {})
    merged["externalIds"] = external
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in [*existing.get("sources", []), *incoming.get("sources", [])]:
        if not isinstance(source, dict):
            continue
        identity = safe_url(source.get("url")) or str(source.get("name") or "")
        if identity and identity not in seen:
            seen.add(identity)
            sources.append(source)
    sources.sort(key=lambda item: int(item.get("priority") or 0), reverse=True)
    merged["sources"] = sources
    if sources:
        merged["sourceName"] = str(sources[0].get("name") or "")
        merged["sourceAuthority"] = str(sources[0].get("authority") or "")
    return merged


def merge_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for raw in events:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        match_index = next((index for index, item in enumerate(clusters) if events_are_duplicates(item, raw)), None)
        if match_index is None:
            clusters.append(dict(raw))
        else:
            clusters[match_index] = merge_two_events(clusters[match_index], raw)
    clusters.sort(key=lambda item: (
        str(item.get("startDate") or "9999-12-31"),
        str(item.get("startTime") or "23:59"),
        str(item.get("title") or "").casefold(),
    ))
    return clusters


def artist_image_map(artists: list[dict[str, Any]], attraction_cache: dict[str, Any]) -> dict[str, str]:
    images: dict[str, str] = {}
    for artist in artists:
        name = str(artist.get("name") or "").strip()
        configured = safe_url(artist.get("imageUrl"))
        cached = attraction_cache.get(name) if isinstance(attraction_cache, dict) else None
        cached_image = safe_url(cached.get("image")) if isinstance(cached, dict) else ""
        chosen = configured if is_valid_image_url(configured) else (cached_image if is_valid_image_url(cached_image) else "")
        if name and chosen:
            images[name] = chosen
    return images


def finalize_event(event: dict[str, Any], images: dict[str, str]) -> dict[str, Any] | None:
    if not event.get("musicConfirmed") or is_non_show(str(event.get("title") or "")):
        return None
    status = str(event.get("status") or "scheduled").lower()
    if status in {"cancelled", "canceled", "postponed"}:
        return None
    if str(event.get("country") or "US").upper() != "US":
        return None
    if not event.get("startDate") or not event.get("city") or normalize_state(str(event.get("state") or "")) not in US_STATE_CODES:
        return None
    sources = [item for item in event.get("sources", []) if isinstance(item, dict)]
    if not sources:
        return None
    non_discovery = [item for item in sources if str(item.get("authority") or "aggregator") != "aggregator"]
    if event.get("requiresCorroboration") and not non_discovery:
        return None

    evidence = [item for item in event.get("artistEvidence", []) if isinstance(item, dict)]
    if event.get("eventType") == "festival":
        authoritative = [
            item for item in evidence
            if item.get("lineupExplicit")
            and str(item.get("authority") or "") in {"official_festival", "official_event", "manual_verified"}
        ]
        if not authoritative:
            return None
        authoritative.sort(key=lambda item: int(item.get("priority") or 0), reverse=True)
        artists = ordered_unique(value for item in authoritative for value in item.get("artists", []))
        headliner = next((str(item.get("headliner") or "") for item in authoritative if item.get("headliner")), "")
    else:
        strong = [item for item in evidence if int(item.get("priority") or 0) >= AUTHORITY_RANKS["artist_calendar"]]
        artists = ordered_unique(value for item in (strong or evidence) for value in item.get("artists", []))
        ranked = sorted(strong or evidence, key=lambda item: int(item.get("priority") or 0), reverse=True)
        headliner = next((str(item.get("headliner") or "") for item in ranked if item.get("headliner")), "")
    if not artists:
        return None
    if headliner not in artists:
        headliner = artists[0]

    artwork = ""
    artwork_items = [item for item in event.get("artworkEvidence", []) if isinstance(item, dict) and is_valid_image_url(item.get("url"), True)]
    if event.get("eventType") == "festival":
        artwork_items = [
            item for item in artwork_items
            if str(item.get("authority") or "") in {"official_festival", "official_event", "manual_verified"}
        ]
    artwork_items.sort(key=lambda item: int(item.get("priority") or 0), reverse=True)
    if artwork_items:
        artwork = safe_url(artwork_items[0].get("url"))
    image = artwork or images.get(headliner, "") or "assets/logo.png"

    result = {key: value for key, value in event.items() if key not in {
        "artistEvidence", "artworkEvidence", "eventArtwork", "requiresCorroboration",
        "festivalLineupAuthoritative", "lineupExplicit", "musicConfirmed", "sourcePriority",
        "sourceAuthority", "externalIds",
    }}
    result["artists"] = artists
    result["headliner"] = headliner
    result["image"] = image
    result["imageType"] = "event_artwork" if artwork else ("artist" if images.get(headliner) else "fallback")
    result["sources"] = sorted(sources, key=lambda item: int(item.get("priority") or 0), reverse=True)
    result["sourceName"] = str(result["sources"][0].get("name") or "Verified source")
    result["confidence"] = "high"
    result["verifiedVersion"] = 2
    return result


def finalize_events(events: Iterable[dict[str, Any]], images: dict[str, str], today: date) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for event in events:
        if not event_is_future(event, today):
            continue
        normalized = finalize_event(event, images)
        if normalized:
            output.append(normalized)
    output.sort(key=lambda item: (
        str(item.get("startDate") or "9999-12-31"),
        str(item.get("startTime") or "23:59"),
        str(item.get("title") or "").casefold(),
    ))
    return output

def normalize_manual_event(event: Any, checked_at: str) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    title = str(event.get("title") or "").strip()
    start_date = str(event.get("startDate") or "").strip()
    city = str(event.get("city") or "").strip()
    state = normalize_state(str(event.get("state") or ""))
    artists = ordered_unique(event.get("artists", []))
    if not title or not start_date or not city or state not in US_STATE_CODES or not artists or is_non_show(title):
        return None
    identifier = str(event.get("id") or event_hash([title, start_date, city, state]))
    source_url = safe_url(event.get("officialUrl")) or safe_url(event.get("ticketUrl"))
    source = {
        "name": str(event.get("sourceName") or "Official event listing"),
        "parser": "manual_verified",
        "authority": str(event.get("authority") or ("official_festival" if str(event.get("eventType")) == "festival" else "official_event")),
        "priority": AUTHORITY_RANKS["manual_verified"],
        "lineupExplicit": bool(event.get("lineupExplicit", True)),
        "imagePolicy": "event_artwork",
    }
    result = make_source_event(
        source=source,
        source_url=source_url,
        title=title,
        start_date=start_date,
        end_date=str(event.get("endDate") or ""),
        start_time=str(event.get("startTime") or ""),
        venue=str(event.get("venue") or "Venue not provided"),
        address=str(event.get("address") or ""),
        city=city,
        state=state,
        artists=artists,
        headliner=str(event.get("headliner") or artists[0]),
        checked_at=checked_at,
        ticket_url=safe_url(event.get("ticketUrl")) or source_url,
        official_url=source_url,
        image=safe_url(event.get("image")),
        price=str(event.get("price") or ""),
        status=str(event.get("status") or "scheduled"),
        confidence="high",
        event_type=str(event.get("eventType") or detect_event_type(title)),
        lineup_explicit=bool(event.get("lineupExplicit", True)),
        music_confirmed=True,
        priority=AUTHORITY_RANKS["manual_verified"],
        external_ids={"manual": identifier},
    )
    result["id"] = f"manual:{identifier}"
    return result

def normalize_social_event(event: Any, checked_at: str) -> dict[str, Any] | None:
    """Normalize a high-confidence official Instagram announcement."""
    if not isinstance(event, dict):
        return None
    title = str(event.get("title") or "").strip()
    start_date = str(event.get("startDate") or "").strip()
    city = str(event.get("city") or "").strip()
    state = normalize_state(str(event.get("state") or ""))
    artists = ordered_unique(event.get("artists", []))
    source_url = safe_url(event.get("sourceUrl")) or safe_url(event.get("officialUrl"))
    if (
        not title or not start_date or not city or state not in US_STATE_CODES
        or not artists or not source_url or is_non_show(title)
    ):
        return None
    source = {
        "name": str(event.get("sourceName") or "Official Instagram announcement"),
        "parser": "instagram_index",
        "authority": "artist_calendar",
        "priority": 78,
        "lineupExplicit": True,
        "imagePolicy": "ignore",
    }
    identifier = str(event.get("id") or event_hash([source_url, title, start_date, city, state]))
    result = make_source_event(
        source=source,
        source_url=source_url,
        title=title,
        start_date=start_date,
        start_time=str(event.get("startTime") or ""),
        venue=str(event.get("venue") or "Venue not provided"),
        address=str(event.get("address") or ""),
        city=city,
        state=state,
        artists=artists,
        headliner=str(event.get("headliner") or artists[0]),
        checked_at=checked_at,
        ticket_url=safe_url(event.get("ticketUrl")) or source_url,
        official_url=source_url,
        image="",
        status=str(event.get("status") or "scheduled"),
        confidence="high",
        event_type=str(event.get("eventType") or "concert"),
        lineup_explicit=True,
        music_confirmed=True,
        priority=78,
        external_ids={"instagram": identifier},
    )
    result["id"] = identifier if identifier.startswith("instagram:") else f"instagram:{identifier}"
    return result


def preserve_recent_existing(
    fresh_events: list[dict[str, Any]],
    existing_events: list[dict[str, Any]],
    today: date,
    checked_at: str,
) -> list[dict[str, Any]]:
    # Version 3 intentionally does not retain stale version-1/2 records. This prevents
    # previously incorrect festival lineups and duplicates from lingering after deploy.
    return fresh_events

def main() -> int:
    started = now_utc()
    checked_at = iso_z(started)
    today = started.date()
    artists = [item for item in load_json(ARTISTS_FILE, []) if isinstance(item, dict) and item.get("enabled", True)]
    official_sources = [item for item in load_json(OFFICIAL_SOURCES_FILE, []) if isinstance(item, dict) and item.get("enabled", True)]
    manual_events = load_json(MANUAL_EVENTS_FILE, [])
    known_instagram_posts = load_json(KNOWN_INSTAGRAM_POSTS_FILE, [])
    previous_status = load_json(STATUS_FILE, {})
    attraction_cache = load_json(ATTRACTION_CACHE_FILE, {})
    if not isinstance(attraction_cache, dict):
        attraction_cache = {}

    alias_lookup = build_alias_lookup(artists)
    client = HttpClient()
    collected: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    source_results: list[dict[str, Any]] = []
    sources_checked = 0
    official_events_count = 0
    ticketmaster_events_count = 0
    instagram_events_count = 0
    instagram_report: dict[str, Any] = {
        "artistsConfigured": len(artists),
        "queriesRun": 0,
        "queriesAttempted": 0,
        "resultsFound": 0,
        "eventsFound": 0,
        "candidates": [],
        "warnings": [],
    }
    artists_matched = 0
    unmatched_artists: list[str] = []

    for source in official_sources:
        source_name = str(source.get("name") or source.get("url") or "Official source")
        try:
            source_events = collect_official_source(source, client, alias_lookup, checked_at)
            collected.extend(source_events)
            official_events_count += len(source_events)
            sources_checked += 1
            source_results.append({"name": source_name, "status": "ok", "eventsFound": len(source_events)})
            print(f"Official source: {source_name}: {len(source_events)} event(s)")
        except CollectorError as exc:
            message = f"{source_name}: {exc}"
            warnings.append(message)
            source_results.append({"name": source_name, "status": "warning", "eventsFound": 0})
            print(f"WARNING: {message}", file=sys.stderr)

    try:
        raw_instagram_events, instagram_report = scan_instagram_index(
            client=client,
            artists=artists,
            known_posts=known_instagram_posts if isinstance(known_instagram_posts, list) else [],
            today=today,
            checked_at=checked_at,
            lookahead_days=LOOKAHEAD_DAYS,
        )
        for raw_event in raw_instagram_events:
            event = normalize_social_event(raw_event, checked_at)
            if event:
                collected.append(event)
                instagram_events_count += 1
        queries_run = int(instagram_report.get("queriesRun") or 0)
        sources_checked += queries_run
        warnings.extend(str(item) for item in instagram_report.get("warnings", []) if str(item))
        source_results.append({
            "name": "Instagram public announcement scan",
            "status": "ok" if not instagram_report.get("warnings") else "warning",
            "eventsFound": instagram_events_count,
            "artistsChecked": int(instagram_report.get("artistsConfigured") or len(artists)),
            "queriesRun": queries_run,
        })
        print(
            "Instagram public-index scan: "
            f"{instagram_events_count} publishable event(s); "
            f"{len(instagram_report.get('candidates', []))} candidate(s)"
        )
    except Exception as exc:
        warning = f"Instagram public-index scan: {exc}"
        warnings.append(warning)
        source_results.append({"name": "Instagram public announcement scan", "status": "warning", "eventsFound": 0})
        print(f"WARNING: {warning}", file=sys.stderr)

    api_key = os.getenv("TICKETMASTER_API_KEY", "").strip()
    if api_key:
        for artist in artists:
            name = str(artist.get("name") or "")
            if not artist.get("ticketmasterEnabled", True):
                continue
            try:
                attraction_id = find_ticketmaster_attraction(artist, api_key, client, attraction_cache, checked_at)
                if not attraction_id:
                    unmatched_artists.append(name)
                    continue
                artists_matched += 1
                artist_events = collect_ticketmaster_artist(artist, attraction_id, api_key, client, alias_lookup, checked_at)
                collected.extend(artist_events)
                ticketmaster_events_count += len(artist_events)
                sources_checked += 1
                print(f"Ticketmaster: {name}: {len(artist_events)} event(s)")
            except CollectorError as exc:
                warnings.append(f"Ticketmaster - {name}: {exc}")
                print(f"WARNING: Ticketmaster - {name}: {exc}", file=sys.stderr)
    else:
        errors.append("Ticketmaster is not configured. Add the TICKETMASTER_API_KEY repository secret.")

    if isinstance(manual_events, list):
        for raw_event in manual_events:
            event = normalize_manual_event(raw_event, checked_at)
            if event:
                collected.append(event)

    candidates = merge_events(event for event in collected if event_is_future(event, today))
    images = artist_image_map(artists, attraction_cache)
    events = finalize_events(candidates, images, today)
    write_json(EVENTS_FILE, events)
    write_json(ATTRACTION_CACHE_FILE, attraction_cache)

    any_source_succeeded = sources_checked > 0 or bool(manual_events)
    status_name = "ok" if not errors else ("partial" if any_source_succeeded else "needs_configuration")
    last_success = checked_at if any_source_succeeded else previous_status.get("lastSuccessfulUpdate")
    status = {
        "status": status_name,
        "collectorVersion": 3,
        "lastAttempt": checked_at,
        "lastSuccessfulUpdate": last_success,
        "eventsPublished": len(events),
        "candidatesCollected": len(collected),
        "artistsConfigured": len(artists),
        "artistsMatchedOnTicketmaster": artists_matched,
        "officialEventsFound": official_events_count,
        "ticketmasterEventsFound": ticketmaster_events_count,
        "instagramArtistsConfigured": int(instagram_report.get("artistsConfigured") or len(artists)),
        "instagramQueriesRun": int(instagram_report.get("queriesRun") or 0),
        "instagramQueriesAttempted": int(instagram_report.get("queriesAttempted") or 0),
        "instagramResultsFound": int(instagram_report.get("resultsFound") or 0),
        "instagramEventsFound": instagram_events_count,
        "instagramCandidates": instagram_report.get("candidates", [])[:30],
        "instagramMode": instagram_report.get("mode", "free public-index scan"),
        "sourcesChecked": sources_checked,
        "unmatchedArtists": unmatched_artists,
        "sourceResults": source_results,
        "warnings": warnings[:30],
        "errors": errors[:10],
        "message": "Verified U.S. music listings updated with strict festival, image, duplicate, and public Instagram-announcement rules.",
    }
    write_json(STATUS_FILE, status)
    print(f"Published {len(events)} event(s); candidates={len(collected)}; errors={len(errors)}; warnings={len(warnings)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
