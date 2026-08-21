#!/usr/bin/env python3
"""Sync verified official artist websites into the monitored artist registry."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
WEBSITES_FILE = ROOT / "config" / "verified-artist-websites.json"


def norm(value: object) -> str:
    return str(value or "").strip().casefold()


def main() -> int:
    artists = json.loads(ARTISTS_FILE.read_text(encoding="utf-8"))
    websites = json.loads(WEBSITES_FILE.read_text(encoding="utf-8"))
    if not isinstance(artists, list) or not isinstance(websites, dict):
        raise SystemExit("Verified website sync expected artist list and website mapping")

    by_name = {
        norm(artist.get("name")): artist
        for artist in artists
        if isinstance(artist, dict) and artist.get("name")
    }
    missing = [name for name in websites if norm(name) not in by_name]
    if missing:
        raise SystemExit(f"Verified website artists missing from roster: {missing}")

    changed = 0
    for name, website in websites.items():
        if not isinstance(website, str) or not website.startswith(("http://", "https://")):
            raise SystemExit(f"Invalid verified website for {name}: {website!r}")
        artist = by_name[norm(name)]
        if artist.get("website") != website:
            artist["website"] = website
            changed += 1
        artist["websiteRegistryVerified"] = True

    ARTISTS_FILE.write_text(
        json.dumps(artists, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Verified artist websites synced: {len(websites)} configured, {changed} URL change(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
