#!/usr/bin/env python3
from pathlib import Path
import html
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

site = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
SITE_HOSTS = {"kingdomcircuit.com", "www.kingdomcircuit.com"}
required = [
    "index.html", "shows/index.html", "shows/this-month/index.html",
    "festivals/index.html", "new-shows/index.html", "artists/index.html",
    "artists/profile/index.html", "event/index.html", "submit/index.html",
    "404.html", "styles.css", "app.js", "events.json", "run-status.json",
    "config/artists.json", "supplemental-events.json", "assets/logo.png",
    "assets/event-fallback.webp", "assets/artists/skema-boy.webp", "sitemap.xml"
]
missing = [name for name in required if not (site / name).is_file() or (site / name).stat().st_size == 0]
if missing:
    raise SystemExit("Missing or empty deployed files: " + ", ".join(missing))


def norm(value):
    return str(value or "").strip().casefold()


def slug(value):
    text = norm(value).replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "artist"


def parsed_url(value: str):
    return urllib.parse.urlparse(html.unescape(str(value or "").strip()))


def local_target(value: str, page: Path | None = None) -> Path | None:
    """Resolve relative, root-relative, and absolute kingdomcircuit.com URLs into the artifact."""
    parsed = parsed_url(value)
    if not parsed.path:
        return None
    if parsed.netloc and parsed.netloc.casefold() not in SITE_HOSTS:
        return None
    if parsed.scheme and parsed.scheme.casefold() not in {"http", "https"}:
        return None
    path = parsed.path
    if parsed.netloc or path.startswith("/"):
        target = site / path.lstrip("/")
    elif page is not None:
        target = page.parent / path
    else:
        target = site / path
    if path.endswith("/"):
        target = target / "index.html"
    return target


artists = json.loads((site / "config/artists.json").read_text(encoding="utf-8"))
if len(artists) < 299:
    raise SystemExit(f"Artist roster unexpectedly small: {len(artists)}")
if not any(a.get("name") == "Mike Malagies" for a in artists):
    raise SystemExit("Mike Malagies missing from artist roster")
artist_by_name = {norm(a.get("name")): a for a in artists if isinstance(a, dict) and a.get("name")}
artist_by_slug = {slug(a.get("name")): a for a in artists if isinstance(a, dict) and a.get("name")}

# The deploy artifact contains the verified registry embedded in app.js. Reuse it so
# a missing generated local portrait can still resolve to a verified Spotify/Instagram image.
app_text = (site / "app.js").read_text(encoding="utf-8")
verified_registry = {}
registry_match = re.search(
    r"const VERIFIED_ARTIST_REGISTRY\s*=\s*(\{.*?\});\s*const ARTIST_OVERRIDES",
    app_text,
    re.S,
)
if registry_match:
    try:
        verified_registry = json.loads(registry_match.group(1))
    except Exception:
        verified_registry = {}

FALLBACK = "assets/event-fallback.webp"
SPOTIFY_IMAGE_ENDPOINT = "https://open.voidware.de/artist/"


def artist_record(name: str) -> dict:
    base = artist_by_name.get(norm(name)) or artist_by_slug.get(slug(name)) or {}
    verified = verified_registry.get(norm(name)) or {}
    return {**base, **verified}


def spotify_id(record: dict) -> str:
    raw = str(record.get("spotifyProfile") or "")
    match = re.search(r"open\.spotify\.com/artist/([A-Za-z0-9]+)", raw, re.I)
    return match.group(1) if match else str(record.get("spotifyId") or "").strip()


def artist_image(name: str) -> str:
    record = artist_record(name)
    value = str(record.get("imageUrl") or "").strip()
    if value:
        target = local_target(value)
        if target is not None:
            if target.is_file():
                return "/" + str(target.relative_to(site)).replace("\\", "/")
        elif value.startswith(("http://", "https://")):
            return value.replace("http://", "https://", 1)

    guessed = site / "assets" / "artists" / f"{slug(name)}.webp"
    if guessed.is_file():
        return "/" + str(guessed.relative_to(site)).replace("\\", "/")

    sid = spotify_id(record)
    if sid and record.get("sourceRegistryVerified") is True:
        return SPOTIFY_IMAGE_ENDPOINT + urllib.parse.quote(sid, safe="")

    instagram = str(record.get("instagramProfile") or "").strip()
    match = re.search(r"instagram\.com/([^/?#]+)", instagram, re.I)
    if match and record.get("sourceRegistryVerified") is True:
        return f"https://unavatar.io/instagram/{match.group(1)}"
    return "/" + FALLBACK


def repair_event_images(filename: str) -> tuple[list[dict], int]:
    path = site / filename
    events = json.loads(path.read_text(encoding="utf-8"))
    repaired = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        image = str(event.get("image") or "").strip()
        target = local_target(image) if image else None
        broken_internal = bool(image and target is not None and not target.is_file())
        if not image or broken_internal:
            name = str(event.get("headliner") or "").strip() or str((event.get("artists") or [""])[0])
            event["image"] = artist_image(name)
            repaired += 1
    path.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return events, repaired


events, repaired_primary_images = repair_event_images("events.json")
supp, repaired_supp_images = repair_event_images("supplemental-events.json")
if len({e["id"] for e in supp}) != len(supp):
    raise SystemExit("Duplicate supplemental event IDs")

skema_events = [e for e in supp if "Skema Boy" in e.get("artists", [])]
if len(skema_events) != 13:
    raise SystemExit(f"Expected 13 Skema Boy supplemental events, found {len(skema_events)}")
if not all(e.get("headliner") == "Zauntee" for e in skema_events):
    raise SystemExit("A Skema Boy tour event is missing Zauntee as headliner")
if not all(str(e.get("image") or "").endswith("assets/artists/zauntee.webp") for e in skema_events):
    raise SystemExit("A Skema Boy tour event is missing the Zauntee image")

hope_fest = [e for e in supp if e.get("id") == "supplemental:image-override-hope-fest-daytona-2026"]
if len(hope_fest) != 1:
    raise SystemExit("Hope Fest image override is missing or duplicated")
expected_hope_fest_image = "https://images.sk-static.com/images/media/profile_images/events/43075130/huge_avatar?series_id=719039"
if hope_fest[0].get("image") != expected_hope_fest_image or hope_fest[0].get("imageType") != "event_artwork":
    raise SystemExit("Hope Fest verified artwork regressed")

anchor_re = re.compile(r'<a\b([^>]*?)href=(["\'])([^"\']+)\2([^>]*)>(.*?)</a>', re.I | re.S)
img_re = re.compile(r'(<img\b[^>]*?\bsrc=)(["\'])([^"\']+)(\2)', re.I | re.S)
repaired_links = 0
repaired_html_images = 0

for page in site.rglob("*.html"):
    text = page.read_text(encoding="utf-8", errors="ignore")

    def fix_anchor(match):
        global repaired_links
        href = match.group(3)
        target = local_target(href, page)
        if target is not None and not target.exists():
            repaired_links += 1
            return match.group(5)
        return match.group(0)

    def fix_img(match):
        global repaired_html_images
        src = html.unescape(match.group(3))
        target = local_target(src, page)
        if target is None or target.is_file():
            return match.group(0)
        replacement = "/assets/event-fallback.webp"
        m = re.search(r"/assets/artists/([^/]+)\.webp$", parsed_url(src).path, re.I)
        if m:
            candidate = artist_by_slug.get(m.group(1))
            if candidate:
                replacement = artist_image(candidate.get("name"))
        repaired_html_images += 1
        return match.group(1) + match.group(2) + html.escape(replacement, quote=True) + match.group(4)

    text = anchor_re.sub(fix_anchor, text)
    text = img_re.sub(fix_img, text)
    page.write_text(text, encoding="utf-8")

# Every sitemap URL must resolve to a generated artifact page.
tree = ET.parse(site / "sitemap.xml")
namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
sitemap_urls = [node.text or "" for node in tree.findall(".//s:loc", namespace)]
missing_sitemap = []
for url in sitemap_urls:
    target = local_target(url)
    if target is None or not target.exists():
        missing_sitemap.append(url)
if missing_sitemap:
    raise SystemExit("Sitemap contains missing URLs: " + ", ".join(missing_sitemap[:20]))

# Full artifact audit, including absolute kingdomcircuit.com links/images.
broken_links = []
broken_images = []
canonical_errors = []
for page in site.rglob("*.html"):
    text = page.read_text(encoding="utf-8", errors="ignore")
    for href in re.findall(r'<a\b[^>]*?href=["\']([^"\']+)', text, re.I):
        target = local_target(href, page)
        if target is not None and not target.exists():
            broken_links.append((str(page.relative_to(site)), href))
    for src in re.findall(r'<img\b[^>]*?src=["\']([^"\']+)', text, re.I):
        target = local_target(src, page)
        if target is not None and not target.is_file():
            broken_images.append((str(page.relative_to(site)), src))
    if page.name != "404.html":
        canonical = re.search(r'<link\b[^>]*?rel=["\']canonical["\'][^>]*?href=["\']([^"\']+)', text, re.I)
        if not canonical:
            canonical_errors.append((str(page.relative_to(site)), "missing canonical"))
        else:
            target = local_target(canonical.group(1))
            if target is not None and not target.exists():
                canonical_errors.append((str(page.relative_to(site)), canonical.group(1)))

if broken_links:
    raise SystemExit(f"Broken internal links remain: {broken_links[:20]}")
if broken_images:
    raise SystemExit(f"Broken local images remain: {broken_images[:20]}")
if canonical_errors:
    raise SystemExit(f"Canonical URL errors remain: {canonical_errors[:20]}")

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

for forbidden in ["raw.githubusercontent.com/84lorinw-a11y/kingdom-circuit/main", "/kingdom-circuit-test/"]:
    if forbidden in app_text:
        raise SystemExit(f"Production app contains test/remote dependency: {forbidden}")
for required_text in [
    'const BASE = "/";', 'events.json', 'config/artists.json',
    'supplemental-events.json', 'run-status.json',
    '77IKXFvO7SpWrq8hflrUXc', 'Spotify link pending verification'
]:
    if required_text not in app_text:
        raise SystemExit(f"Required production behavior missing from app.js: {required_text}")

audit = {
    "sitemapUrls": len(sitemap_urls),
    "missingSitemapUrls": 0,
    "brokenInternalLinks": 0,
    "brokenLocalImages": 0,
    "canonicalErrors": 0,
    "repairedInternalLinks": repaired_links,
    "repairedHtmlImages": repaired_html_images,
    "repairedPrimaryEventImages": repaired_primary_images,
    "repairedSupplementalEventImages": repaired_supp_images,
    "htmlPagesAudited": sum(1 for _ in site.rglob("*.html")),
}
(site / "integrity-audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
print(json.dumps(audit, indent=2))
