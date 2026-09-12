from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys
from urllib.parse import urlparse

from add_past_show_archives import apply_past_show_archives
from finalize_seo_indexing_core import main as finalize_main
from fix_seo_audit import apply_seo_audit_fixes
from pin_verified_event_artwork import pin_site

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE_URL = "https://kingdomcircuit.com"
LISTING_PAGES = (
    "index.html",
    "festivals/index.html",
    "shows/index.html",
    "shows/this-month/index.html",
    "new-shows/index.html",
)
SOCIAL_HOSTS = {
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com",
    "youtube.com", "www.youtube.com", "youtu.be",
}


def apply_p0_mobile_listing_safety(root: pathlib.Path) -> dict[str, int]:
    removed_scripts = 0
    inlined_pages = 0
    for relative in LISTING_PAGES:
        page = root / relative
        if not page.exists():
            continue
        html = page.read_text(encoding="utf-8")
        original = html
        html = re.sub(r'\s*<script[^>]+src="/assets/(?:image-fix|home-primary-image-guard|home-kaden-image-fix|event-image-repair-kc2100|verified-event-artwork-guard)[^"]*"[^>]*></script>', "", html)
        html = re.sub(r'\s*<script async src="https://www\.googletagmanager\.com/gtag/js\?id=G-N2KK9XF4TJ"></script>\s*<script>.*?</script>', "", html, flags=re.S)
        if html != original:
            page.write_text(html, encoding="utf-8")
            removed_scripts += 1

    app = root / "app.js"
    patched_runtime = 0
    if app.exists():
        js = app.read_text(encoding="utf-8")
        marker = "async function boot() {\n  try {"
        replacement = """async function boot() {
  const staticCards = [...document.querySelectorAll("[data-event-card]")];
  if (staticCards.length) {
    document.querySelectorAll(".loading-panel").forEach(element => element.remove());
    setupEventFilters(staticCards);
    setupSubmissionForm();
    return;
  }
  try {"""
        if marker in js and "const staticCards =" not in js:
            app.write_text(js.replace(marker, replacement, 1), encoding="utf-8")
            patched_runtime = 1
    return {"pages_cleaned": removed_scripts, "styles_inlined": inlined_pages, "runtime_patched": patched_runtime}


def load_source_events() -> list[dict]:
    rows: list[dict] = []
    for relative in ("events.json", "supplemental-events.json", "config/manual-events.json"):
        path = ROOT / relative
        if not path.exists():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    return rows


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def source_key(event: dict) -> tuple[str, str, str]:
    return (
        norm(event.get("title")),
        str(event.get("startDate") or "")[:10],
        norm(event.get("city")),
    )


def schema_key(schema: dict) -> tuple[str, str, str]:
    location = schema.get("location") if isinstance(schema.get("location"), dict) else {}
    address = location.get("address") if isinstance(location.get("address"), dict) else {}
    return (
        norm(schema.get("name")),
        str(schema.get("startDate") or "")[:10],
        norm(address.get("addressLocality")),
    )


def direct_ticket_url(value: object) -> str:
    url = str(value or "").strip()
    if not url.startswith(("https://", "http://")):
        return ""
    try:
        host = urlparse(url).netloc.casefold()
    except ValueError:
        return ""
    return "" if host in SOCIAL_HOSTS else url


def absolute_image(value: object) -> object:
    if isinstance(value, list):
        return [absolute_image(item) for item in value]
    raw = str(value or "").strip()
    if not raw:
        return value
    if raw.startswith("http://"):
        return "https://" + raw[len("http://"):]
    if raw.startswith("https://"):
        return raw
    return BASE_URL + "/" + raw.lstrip("/")


def repair_event_schema(schema: dict, source: dict | None) -> bool:
    changed = False
    if "image" in schema:
        resolved = absolute_image(schema["image"])
        if resolved != schema["image"]:
            schema["image"] = resolved
            changed = True

    if schema.get("eventStatus") == "https://schema.org/EventCompleted":
        schema.pop("eventStatus", None)
        changed = True

    if source is None:
        offers = schema.get("offers")
        if isinstance(offers, dict) and offers.get("availability") == "https://schema.org/InStock":
            offers.pop("availability", None)
            changed = True
        return changed

    ticket = direct_ticket_url(source.get("ticketUrl"))
    if ticket:
        offer = {"@type": "Offer", "url": ticket}
        if source.get("soldOut") is True or source.get("ticketAvailability") == "sold_out":
            offer["availability"] = "https://schema.org/SoldOut"
        if schema.get("offers") != offer:
            schema["offers"] = offer
            changed = True
    elif "offers" in schema:
        schema.pop("offers", None)
        changed = True

    age = str(source.get("ageRestriction") or "").strip()
    if age and schema.get("typicalAgeRange") != age:
        schema["typicalAgeRange"] = age
        changed = True
    return changed


def walk_schema(value: object, source_index: dict[tuple[str, str, str], dict]) -> bool:
    changed = False
    if isinstance(value, list):
        for item in value:
            changed = walk_schema(item, source_index) or changed
        return changed
    if not isinstance(value, dict):
        return False

    schema_type = value.get("@type")
    types = schema_type if isinstance(schema_type, list) else [schema_type]
    if any(item in {"MusicEvent", "Event"} for item in types):
        changed = repair_event_schema(value, source_index.get(schema_key(value))) or changed

    for child in value.values():
        if isinstance(child, (dict, list)):
            changed = walk_schema(child, source_index) or changed
    return changed


def finalize_structured_event_data(root: pathlib.Path, events: list[dict]) -> dict[str, int]:
    source_index = {source_key(event): event for event in events if event.get("title") and event.get("startDate")}
    scripts_changed = 0
    pages_changed = 0
    pattern = re.compile(r'(<script[^>]+type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)', re.S | re.I)

    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        page_changed = False

        def replace(match: re.Match[str]) -> str:
            nonlocal scripts_changed, page_changed
            try:
                payload = json.loads(match.group(2))
            except json.JSONDecodeError:
                return match.group(0)
            if not walk_schema(payload, source_index):
                return match.group(0)
            scripts_changed += 1
            page_changed = True
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
            return match.group(1) + encoded + match.group(3)

        updated = pattern.sub(replace, text)
        if page_changed:
            page.write_text(updated, encoding="utf-8")
            pages_changed += 1

    return {"pages": pages_changed, "schemas": scripts_changed}


def remove_disabled_artist_outputs(root: pathlib.Path) -> dict[str, int]:
    artists_path = ROOT / "config" / "artists.json"
    try:
        artists = json.loads(artists_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"profiles_removed": 0, "sitemap_entries_removed": 0}

    disabled = [str(item.get("name") or "").strip() for item in artists if isinstance(item, dict) and item.get("enabled") is False]
    removed = 0
    removed_urls: list[str] = []
    for name in disabled:
        slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "item"
        profile = root / "artists" / slug
        if profile.exists():
            shutil.rmtree(profile)
            removed += 1
        removed_urls.append(f"{BASE_URL}/artists/{slug}/")

    sitemap_path = root / "sitemap.xml"
    sitemap_removed = 0
    if sitemap_path.exists() and removed_urls:
        sitemap = sitemap_path.read_text(encoding="utf-8")
        for url in removed_urls:
            pattern = re.compile(rf"\s*<url><loc>{re.escape(url)}</loc>.*?</url>", re.S)
            sitemap, count = pattern.subn("", sitemap)
            sitemap_removed += count
        sitemap_path.write_text(sitemap, encoding="utf-8")
    return {"profiles_removed": removed, "sitemap_entries_removed": sitemap_removed}


def patch_verified_event_states(root: pathlib.Path, events: list[dict]) -> dict[str, int]:
    # Import the canonical path function used by the production builder so the
    # visible page and structured data stay tied to the same source record.
    from build_seo_site import event_path

    sold_out = 0
    age_restrictions = 0
    for event in events:
        if not (event.get("soldOut") is True or event.get("ageRestriction")):
            continue
        page = root / event_path(event).strip("/") / "index.html"
        if not page.exists():
            continue
        text = page.read_text(encoding="utf-8")
        original = text
        if event.get("soldOut") is True:
            text = text.replace('<div><dt>Status</dt><dd>Scheduled</dd></div>', '<div><dt>Status</dt><dd>Sold Out</dd></div>', 1)
            if text != original:
                sold_out += 1
        age = str(event.get("ageRestriction") or "").strip()
        if age and "<dt>Age restriction</dt>" not in text:
            marker = "<div><dt>Source</dt>"
            if marker in text:
                text = text.replace(marker, f'<div><dt>Age restriction</dt><dd>{age}</dd></div>{marker}', 1)
                age_restrictions += 1
        if text != original:
            page.write_text(text, encoding="utf-8")
    return {"sold_out_pages": sold_out, "age_restrictions": age_restrictions}


def main() -> None:
    try:
        index = sys.argv.index("--site")
        root = pathlib.Path(sys.argv[index + 1]).resolve()
    except (ValueError, IndexError):
        raise SystemExit("--site is required")

    report = apply_past_show_archives(root)
    print("Past show archive:", report)
    seo_report = apply_seo_audit_fixes(root)
    print("SEO audit fixes:", seo_report)
    finalize_main()
    artwork_report = pin_site(root)
    print("Verified event artwork:", artwork_report)
    safety_report = apply_p0_mobile_listing_safety(root)
    print("P0 mobile listing safety:", safety_report)

    events = load_source_events()
    disabled_report = remove_disabled_artist_outputs(root)
    print("Disabled artist output cleanup:", disabled_report)
    schema_report = finalize_structured_event_data(root, events)
    print("Structured event metadata repair:", schema_report)
    state_report = patch_verified_event_states(root, events)
    print("Verified event state display:", state_report)


if __name__ == "__main__":
    main()
