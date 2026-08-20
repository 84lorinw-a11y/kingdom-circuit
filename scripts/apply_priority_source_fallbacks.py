#!/usr/bin/env python3
"""Inject resilient artist-calendar fallbacks before each scheduled collection.

Bandsintown's public pages frequently reject the GitHub runner, while Apple Music
publishes concert calendars powered by the same event ecosystem and can be
parsed by the collector's existing JSON-LD path. Keep these as lower-priority
fallbacks behind first-party artist calendars and venue/ticket sources.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "config" / "official-sources.json"

FALLBACKS = [
    {
        "name": "Mike Teezy Apple Music concerts",
        "url": "https://music.apple.com/us/concerts/artist/517774271",
        "parser": "jsonld",
        "enabled": True,
        "artist": "Mike Teezy",
        "authority": "artist_calendar",
        "priority": 74,
        "imagePolicy": "ignore",
        "musicConfirmed": True,
        "softFail": True,
    },
    {
        "name": "Parris Chariz Apple Music concerts",
        "url": "https://music.apple.com/us/concerts/artist/772171124",
        "parser": "jsonld",
        "enabled": True,
        "artist": "Parris Chariz",
        "authority": "artist_calendar",
        "priority": 74,
        "imagePolicy": "ignore",
        "musicConfirmed": True,
        "softFail": True,
    },
    {
        "name": "Mike Malagies Apple Music concerts",
        "url": "https://music.apple.com/us/concerts/artist/1573408784",
        "parser": "jsonld",
        "enabled": True,
        "artist": "Mike Malagies",
        "authority": "artist_calendar",
        "priority": 74,
        "imagePolicy": "ignore",
        "musicConfirmed": True,
        "softFail": True,
    },
]


def norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def main() -> int:
    with SOURCES_FILE.open("r", encoding="utf-8") as handle:
        sources = json.load(handle)
    if not isinstance(sources, list):
        raise SystemExit("config/official-sources.json must be a JSON array")

    fallback_names = {norm(item["name"]) for item in FALLBACKS}
    fallback_urls = {norm(item["url"]) for item in FALLBACKS}
    cleaned = [
        source for source in sources
        if isinstance(source, dict)
        and norm(source.get("name")) not in fallback_names
        and norm(source.get("url")) not in fallback_urls
    ]
    cleaned.extend(FALLBACKS)

    with SOURCES_FILE.open("w", encoding="utf-8") as handle:
        json.dump(cleaned, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(
        "Priority source fallbacks ensured: "
        + ", ".join(item["artist"] for item in FALLBACKS)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
