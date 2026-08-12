#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

site = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
required = [
    "index.html", "shows/index.html", "shows/this-month/index.html",
    "festivals/index.html", "new-shows/index.html", "artists/index.html",
    "artists/profile/index.html", "event/index.html", "submit/index.html",
    "404.html", "styles.css", "app.js", "events.json", "run-status.json",
    "config/artists.json", "supplemental-events.json", "assets/logo.png",
    "assets/event-fallback.webp", "assets/artists/skema-boy.webp"
]
missing = [name for name in required if not (site / name).is_file() or (site / name).stat().st_size == 0]
if missing:
    raise SystemExit("Missing or empty deployed files: " + ", ".join(missing))

pages = [site / name for name in required if name.endswith(".html")]
for page in pages:
    text = page.read_text(encoding="utf-8")
    if "/kingdom-circuit-test/" in text or "TEST SITE" in text:
        raise SystemExit(f"Test-site reference remains in {page}")
    if page.name != "404.html" and 'noindex,nofollow' in text:
        raise SystemExit(f"Production page is noindex: {page}")
    if "G-N2KK9XF4TJ" not in text:
        raise SystemExit(f"Google Analytics tag missing from {page}")
    if 'data-calendar-status' not in text:
        raise SystemExit(f"Calendar footer status missing from {page}")

app = (site / "app.js").read_text(encoding="utf-8")
for forbidden in ["raw.githubusercontent.com/84lorinw-a11y/kingdom-circuit/main", "/kingdom-circuit-test/"]:
    if forbidden in app:
        raise SystemExit(f"Production app contains test/remote dependency: {forbidden}")
for required_text in [
    'const BASE = "/";', 'events.json', 'config/artists.json',
    'supplemental-events.json', 'run-status.json',
    '77IKXFvO7SpWrq8hflrUXc', 'Spotify link pending verification'
]:
    if required_text not in app:
        raise SystemExit(f"Required production behavior missing from app.js: {required_text}")

supp = json.loads((site / "supplemental-events.json").read_text(encoding="utf-8"))
if len(supp) != 13:
    raise SystemExit(f"Expected 13 Skema Boy supplemental events, found {len(supp)}")
if len({e["id"] for e in supp}) != len(supp):
    raise SystemExit("Duplicate supplemental event IDs")
if not all("Skema Boy" in e.get("artists", []) for e in supp):
    raise SystemExit("A supplemental event is missing Skema Boy")

artists = json.loads((site / "config/artists.json").read_text(encoding="utf-8"))
if len(artists) < 299:
    raise SystemExit(f"Artist roster unexpectedly small: {len(artists)}")
if not any(a.get("name") == "Mike Malagies" for a in artists):
    raise SystemExit("Mike Malagies missing from artist roster")

print(f"Verified {len(required)} deployment files, {len(pages)} pages, {len(artists)} artists, and {len(supp)} supplemental events.")
