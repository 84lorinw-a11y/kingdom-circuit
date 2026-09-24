"""Keep artist search titles and compact dates aligned with the final schedule.

Runs after the pinned redesign on every production build. Read the event pages
linked by upcoming rows, so archive entries and unlisted source records cannot
add stale years to a profile's title.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


YEAR_STYLE = '''<style data-kc-artist-schedule-years>
body .kc-rd-show-date { display: grid; grid-template-columns: max-content max-content; row-gap: 4px; }
body .kc-rd-show-year { grid-column: 1 / -1; font-size: .72em; font-weight: 600; letter-spacing: .06em; }
</style>'''
YEAR_STYLE_RE = re.compile(r'<style data-kc-artist-schedule-years>.*?</style>\s*', re.S)
ROW_RE = re.compile(r'<a class="kc-rd-show-row"[^>]*>.*?</a>', re.S)
DATE_RE = re.compile(
    r'(<span class="kc-rd-show-date"><span>.*?</span><strong>.*?</strong>)'
    r'(?:<span class="kc-rd-show-year">.*?</span>)?(</span>)', re.S
)
NEXT_RE = re.compile(r'<a class="kc-rd-next kc-rd-next-show"[^>]*>.*?</a>', re.S)


def title_for(name: str, years: set[int]) -> str:
    ordered = sorted(years)
    if len(ordered) > 1 and ordered == list(range(ordered[0], ordered[-1] + 1)):
        label = f"{ordered[0]}–{ordered[-1]}"
    else:
        label = ", ".join(map(str, ordered))
    return f"{name} Concerts & Tour Dates{(' ' + label) if label else ''} | Kingdom Circuit"


def schema_nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from schema_nodes(item)
    elif isinstance(value, dict):
        yield value
        yield from schema_nodes(value.get("@graph", []))


def event_dates(root: pathlib.Path, anchor: str) -> tuple[dt.date, dt.date]:
    href = re.search(r'\bhref="([^"]+)"', anchor).group(1)
    url = urlsplit(html.unescape(href))
    parts = pathlib.PurePosixPath(url.path).parts
    if url.netloc not in ("", "kingdomcircuit.com") or len(parts) != 3 or parts[1] != "event" or ".." in parts:
        raise ValueError(f"Unexpected upcoming event URL: {href}")
    page = root / "event" / parts[2] / "index.html"
    document = page.read_text(encoding="utf-8")
    for raw in re.findall(r'<script\b[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', document, re.S):
        for node in schema_nodes(json.loads(raw)):
            types = node.get("@type", [])
            if not {"MusicEvent", "Event", "Festival"}.intersection(types if isinstance(types, list) else [types]):
                continue
            start = dt.date.fromisoformat(str(node["startDate"])[:10])
            end = dt.date.fromisoformat(str(node.get("endDate") or node["startDate"])[:10])
            if end < start:
                raise ValueError(f"Event ends before its start: {href}")
            return start, end
    raise ValueError(f"Upcoming event has no dated event schema: {href}")


def patch_profile(document: str, root: pathlib.Path, today: dt.date) -> str:
    name_match = re.search(r'<h1\b[^>]*id="kc-rd-artist-name"[^>]*>(.*?)</h1>', document, re.S)
    if not name_match:
        raise ValueError("Artist profile name missing")
    name = html.unescape(name_match.group(1))
    years: set[int] = set()
    next_year_dates = 0

    def patch_row(match: re.Match) -> str:
        nonlocal next_year_dates
        row = match.group(0)
        start, end = event_dates(root, row)
        if end < today:
            raise ValueError(f"Expired show remains in {name}'s upcoming schedule")
        years.update(range(start.year, end.year + 1))
        year = f'<span class="kc-rd-show-year">{start.year}</span>' if start.year != today.year else ""
        next_year_dates += bool(year)
        patched, count = DATE_RE.subn(lambda m: m[1] + year + m[2], row)
        if count != 1:
            raise ValueError(f"Unexpected compact show date for {name}")
        return patched

    document = ROW_RE.sub(patch_row, document)

    def patch_next(match: re.Match) -> str:
        anchor = match.group(0)
        start, _ = event_dates(root, anchor)
        # Reconstruct only the date label; venue, time, and destination stay intact.
        label = f"Next show · {start.strftime('%b').upper()} {start.day}"
        if start.year != today.year:
            label += f", {start.year}"
        return re.sub(r'(<span class="kc-rd-next-kicker">).*?(</span>)',
                      lambda m: m[1] + label + m[2], anchor, count=1, flags=re.S)

    document = NEXT_RE.sub(patch_next, document)
    title = html.escape(title_for(name, years), quote=True)
    document = re.sub(r'<title>.*?</title>', lambda _: f"<title>{title}</title>", document, count=1, flags=re.S)
    for attribute, key in (("property", "og:title"), ("name", "twitter:title")):
        pattern = rf'(<meta\s+{attribute}="{key}"\s+content=")[^"]*(")'
        document = re.sub(pattern, lambda m: m[1] + title + m[2], document)
    document = YEAR_STYLE_RE.sub("", document)
    if next_year_dates:
        document = document.replace("</head>", YEAR_STYLE + "\n</head>", 1)
    return document


def apply(root: pathlib.Path, *, today: dt.date | None = None, check_only: bool = False) -> int:
    today = today or dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    count = 0
    for page in sorted((root / "artists").glob("*/index.html")):
        document = page.read_text(encoding="utf-8")
        if "data-kc-rd-artist-profile" not in document:
            continue
        patched = patch_profile(document, root, today)
        if patched != document:
            if check_only:
                raise ValueError(f"Artist title or visible date years are stale: {page.relative_to(root)}")
            page.write_text(patched, encoding="utf-8")
        count += 1
    return count
