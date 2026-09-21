#!/usr/bin/env python3
"""Verify the approved test redesign without allowing test identity into production."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo


INACTIVE = {"cancelled", "canceled", "postponed", "merged"}
TEST_MARKERS = (
    "/kingdom-circuit-test/",
    "84lorinw-a11y.github.io/kingdom-circuit-test",
    "Kingdom Circuit Test",
    "G-TEST-DISABLED",
    'name="environment" value="test"',
)


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def event_last_date(event: dict) -> dt.date | None:
    raw = str(event.get("endDate") or event.get("startDate") or "")[:10]
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def current_808_count(site: pathlib.Path) -> int:
    cutoff = dt.datetime.now(ZoneInfo("America/Los_Angeles")).date() - dt.timedelta(days=1)
    rows: list[dict] = []
    for relative in ("events.json", "supplemental-events.json"):
        payload = json.loads(read(site / relative))
        if isinstance(payload, list):
            rows.extend(item for item in payload if isinstance(item, dict))
    expected: set[str] = set()
    for event in rows:
        artists = {str(name).strip().casefold() for name in event.get("artists", [])}
        if "808 beezy" not in artists:
            continue
        if str(event.get("status") or "scheduled").strip().casefold() in INACTIVE:
            continue
        last = event_last_date(event)
        if last is not None and last < cutoff:
            continue
        expected.add(str(event.get("id") or json.dumps(event, sort_keys=True)))
    return len(expected)


def local_target(site: pathlib.Path, href: str) -> pathlib.Path | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return None
    path = unquote(parsed.path)
    if path.endswith("/"):
        return site / path.lstrip("/") / "index.html"
    target = site / path.lstrip("/")
    return target if target.suffix else target / "index.html"


def verify(site: pathlib.Path) -> dict[str, int]:
    failures: list[str] = []
    required = (
        "index.html",
        "artists/index.html",
        "artists/808-beezy/index.html",
        "new-shows/index.html",
        "shows/this-month/index.html",
        "submit/artist/index.html",
        "assets/kc-redesign-v1.css",
        "assets/kc-redesign-v1.js",
        "assets/live-redesign-manifest.json",
        "events.json",
        "supplemental-events.json",
        "CNAME",
        "robots.txt",
        "sitemap.xml",
    )
    for relative in required:
        path = site / relative
        if not path.is_file() or path.stat().st_size == 0:
            failures.append(f"missing:{relative}")

    if failures:
        raise SystemExit("Live redesign verification failed:\n" + "\n".join(failures))

    if read(site / "CNAME").strip() != "kingdomcircuit.com":
        failures.append("identity:CNAME")
    robots = read(site / "robots.txt")
    if "Allow: /" not in robots or "Disallow: /" in robots:
        failures.append("identity:robots")

    manifest = json.loads(read(site / "assets/live-redesign-manifest.json"))
    for key, expected in {
        "mode": "mobile-first-live-redesign-v1",
        "siteBase": "/",
        "deploymentEnvironment": "production",
        "productionChanged": True,
        "newWindowDays": 7,
        "pastGraceDays": 1,
    }.items():
        if manifest.get(key) != expected:
            failures.append(f"manifest:{key}:{manifest.get(key)!r}")

    pages = sorted(site.rglob("*.html"))
    profile_pages = [
        page for page in pages
        if len(page.relative_to(site).parts) == 3
        and page.relative_to(site).parts[0] == "artists"
        and page.relative_to(site).parts[1] != "profile"
        and "kc-rd-artist-profile" in read(page)
    ]
    for page in pages:
        relative = page.relative_to(site).as_posix()
        text = read(page)
        for marker in TEST_MARKERS:
            if marker in text:
                failures.append(f"test-leak:{relative}:{marker}")
        if "<dt>Source</dt>" in text or "Original event source" in text:
            failures.append(f"public-source-label:{relative}")
        if not re.search(r'class="[^"]*\bkc-rd-header\b[^"]*"', text):
            failures.append(f"header:{relative}")
        if "/assets/kc-redesign-v1.css" not in text:
            failures.append(f"css:{relative}")
        if "/assets/kc-redesign-v1.js" not in text:
            failures.append(f"js:{relative}")

    home = read(site / "index.html")
    for phrase in ("Find Christian", "Hip Hop Shows", "Near You!", "Shows Listed", "Artists Tracked"):
        if phrase not in home:
            failures.append(f"home:missing:{phrase}")
    for phrase in (
        "Discover Christian hip-hop concerts, festivals, tours, and independent events",
        "Updated daily · U.S. music performances only",
        "Verified listings",
    ):
        if phrase in home:
            failures.append(f"home:legacy:{phrase}")

    directory = read(site / "artists/index.html")
    for phrase in ("Submit a Show", "Submit a CHH Artist to Be Listed", "CHH Artists", "Artist Directory"):
        if phrase not in directory:
            failures.append(f"directory:missing:{phrase}")
    if re.search(r'class="seo-card-next"[^>]*>.*?\b\d{1,2}:\d{2}\s*(?:AM|PM)\b', directory, re.I | re.S):
        failures.append("directory:show-time")

    submit = read(site / "submit/artist/index.html")
    if 'name="environment" value="production"' not in submit:
        failures.append("submit:environment")
    if "https://kingdomcircuit.com/submit/artist/" not in submit:
        failures.append("submit:canonical")
    if "G-N2KK9XF4TJ" not in submit:
        failures.append("submit:analytics")

    new_shows = read(site / "new-shows/index.html")
    if "7 days" not in new_shows or "14 days" in new_shows:
        failures.append("new-shows:window")

    month = read(site / "shows/this-month/index.html")
    for label in ("Shows", "States", "Artists"):
        if not re.search(rf">\s*{label}\s*<", month, re.I):
            failures.append(f"month:counter:{label}")
    if "data-month-festival-count" in month:
        failures.append("month:legacy-festivals-counter")

    expected_808 = current_808_count(site)
    beezy = read(site / "artists/808-beezy/index.html")
    row_hrefs = re.findall(
        r'<a\b[^>]*class="[^"]*\bkc-rd-show-row\b[^"]*"[^>]*href="([^"]+)"',
        beezy,
        re.I,
    )
    if len(row_hrefs) != expected_808 or len(set(row_hrefs)) != expected_808:
        failures.append(f"808:rows:{len(row_hrefs)}:{len(set(row_hrefs))}:expected:{expected_808}")
    for href in set(row_hrefs):
        target = local_target(site, href)
        if target is not None and not target.is_file():
            failures.append(f"808:broken:{href}")

    css = read(site / "assets/kc-redesign-v1.css")
    for token in (
        ".kc-rd-followbar",
        ".kc-rd-nav",
        ".kc-rd-home-title",
        "[data-artist-directory] .artist-visual",
        ".kc-rd-profile-page",
        ".kc-rd-upcoming-total",
    ):
        if token not in css:
            failures.append(f"css-token:{token}")

    if len(profile_pages) < 300:
        failures.append(f"profiles:{len(profile_pages)}")
    if len(pages) < 800:
        failures.append(f"html-pages:{len(pages)}")
    if failures:
        raise SystemExit(
            "Live redesign verification failed:\n" + "\n".join(failures[:100])
        )
    report = {
        "htmlPages": len(pages),
        "artistProfiles": len(profile_pages),
        "expected808Shows": expected_808,
        "profileRows": sum(read(page).count("kc-rd-show-row") for page in profile_pages),
    }
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=pathlib.Path)
    args = parser.parse_args()
    verify(args.site.resolve())


if __name__ == "__main__":
    main()
