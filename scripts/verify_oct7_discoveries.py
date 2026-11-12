"""Check reviewed discoveries and the October 6 archive in the final artifact."""
import html
import json
from pathlib import Path
import re
import sys

import build_seo_site as builder
from apply_verified_show_information import enrich
from verify_egr_bizzle_updates import uses_image
from verify_show_artwork import published_event_path

ROOT = Path(__file__).resolve().parents[1]
BATCH = "2026-10-07-reviewed-discoveries"
REVIEWED_CANCELLATION = ("babytooth-experience-huntington-beach-2026-11-21", "2026-11-21")


def verify_reviewed_cancellation(site, wanted, raw):
    """Keep the reviewed cancellation/postponement accountable after feed removal."""
    identity = wanted["id"]
    assert (identity, wanted["startDate"]) == REVIEWED_CANCELLATION
    assert wanted.get("status") in {"cancelled", "canceled", "postponed"}, (identity, "inactive status")
    postponed = wanted.get("status") == "postponed"
    status = "postponed" if postponed else "cancelled"
    status_kind = "postponement" if postponed else "cancellation"
    assert wanted.get("ticketAvailability") == status and not wanted.get("ticketUrl"), (identity, f"actionable {status} ticket")
    assert not any(str(e["id"]).removeprefix("manual:") == identity for e in raw), (identity, f"{status} event in public feed")
    event = dict(wanted, id="manual:" + identity)
    href = published_event_path(event, ROOT)
    detail = (site / href.strip("/") / "index.html").read_text()
    assert uses_image(detail, site, wanted["image"]), (identity, "source artwork")
    for name in wanted["advertisedBilling"]:
        assert name in html.unescape(detail), (identity, name)
    schemas = [json.loads(value) for value in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', detail, re.S)]
    events = [value for value in schemas if value.get("@type") == "MusicEvent"]
    assert len(events) == 1, (identity, "missing or duplicated event schema")
    schema = events[0]
    schema_status = "EventPostponed" if postponed else "EventCancelled"
    assert schema.get("eventStatus") == "https://schema.org/" + schema_status, (identity, f"{status_kind} schema")
    assert schema.get("name") == wanted["title"] and schema.get("startDate") == wanted["startDate"], (identity, "retained event identity/date")
    assert schema.get("url") == "https://kingdomcircuit.com" + href, (identity, "retained schema URL")
    assert schema.get("location", {}).get("name") == wanted["venue"], (identity, "retained venue")
    address = schema.get("location", {}).get("address", {})
    assert address.get("addressLocality") == wanted["city"] and address.get("addressRegion") == wanted["state"], (identity, "retained location")
    assert [p.get("name") for p in schema.get("performer", [])] == wanted["advertisedBilling"], (identity, "retained full billing")
    assert "offers" not in schema, (identity, f"{status} purchase offer")
    assert re.search(r'<link[^>]*rel="canonical"[^>]*href="' + re.escape("https://kingdomcircuit.com" + href) + '"', detail), (identity, "retained canonical URL")
    assert html.escape(wanted["officialUrl"], quote=True) in detail, (identity, "official source")
    visible = re.sub(r"<(?:head|script|style)\b[^>]*>.*?</(?:head|script|style)>", " ", detail, flags=re.S | re.I)
    visible = html.unescape(re.sub(r"<[^>]+>", " ", visible))
    status_pattern = r"postponed" if postponed else r"cancelled|canceled"
    assert re.search(status_pattern, visible, re.I), (identity, f"visible {status_kind}")
    if postponed:
        assert re.search(r"new date\s+(?:to be announced|TBA)", visible, re.I), (identity, "postponed new date notice")
    anchors = re.findall(r'<a\b[^>]*>(.*?)</a>', detail, re.S | re.I)
    labels = [html.unescape(re.sub(r"<[^>]+>", " ", value)).strip() for value in anchors]
    assert not any(re.search(r"\b(?:(?:buy|get|purchase)\s+tickets?|rsvp|register(?:\s+now)?)\b", label, re.I) for label in labels), (identity, f"{status} ticket action")
    assert href not in (site / "shows/index.html").read_text(), (identity, f"{status} show listed")
    for name in wanted["artists"]:
        profile = site / builder.artist_path(name).strip("/") / "index.html"
        profile_text = profile.read_text()
        archive_pattern = r'<section\b(?=[^>]*\bdata-past-shows-archive(?=[\s=>]))[^>]*>.*?</section>'
        for archive in re.findall(archive_pattern, profile_text, re.S | re.I):
            if href in archive:
                links = re.findall(r'<a\b[^>]*href="' + re.escape(href) + r'"[^>]*>(.*?)</a>', archive, re.S | re.I)
                assert links and all(re.search(status_pattern, value, re.I) for value in links), (identity, f"unmarked {status} archive")
        upcoming = re.sub(archive_pattern, "", profile_text, flags=re.S | re.I)
        assert href not in upcoming, (identity, f"{status} artist schedule")


def verify(site):
    primary = json.loads((site / "events.json").read_text())
    supplemental = json.loads((site / "supplemental-events.json").read_text())
    rows = builder.merge_events(primary, supplemental)
    registry = ROOT / 'config/verified-show-information.json'
    reviewed = json.loads(registry.read_text()).get('events', []) if registry.exists() else []
    # Later guarded source corrections supersede the original discovery seed.
    approved = [enrich(e, reviewed) for e in json.loads((ROOT / "config/manual-events.json").read_text())
                if e.get("editorialBatch") == BATCH]
    checked = 0
    for wanted in approved:
        if not builder.current(wanted):
            continue
        if ((wanted["id"], wanted["startDate"]) == REVIEWED_CANCELLATION
                and wanted.get("status") in {"cancelled", "canceled", "postponed"}):
            verify_reviewed_cancellation(site, wanted, primary + supplemental)
            continue
        matches = [e for e in rows if str(e["id"]).removeprefix("manual:") == wanted["id"]]
        assert len(matches) == 1, (wanted["id"], "missing or duplicate")
        event = matches[0]
        for field in ("startDate", "startTime", "venue", "city", "state", "artists", "advertisedBilling", "officialUrl"):
            assert event.get(field) == wanted.get(field), (wanted["id"], field)
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        assert uses_image(detail, site, wanted["image"]), (wanted["id"], "source artwork")
        for name in wanted["advertisedBilling"]:
            assert name in html.unescape(detail), (wanted["id"], name)
        assert href in (site / "shows/index.html").read_text(), (wanted["id"], "shows list")
        checked += 1

    history = json.loads((ROOT / "event-history.json").read_text())["events"]
    for identity in ("bandsintown:1040305060", "manual:after-doves-at-the-cg-nashville-2026-10-06"):
        event = next(row["event"] for row in history if row["event"].get("id") == identity)
        assert not any(e["id"] == identity for e in rows), (identity, "still upcoming")
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        assert re.search(r"past (?:show|event)", detail, re.I), (identity, "missing archive notice")
        for name in event["artists"]:
            profile = site / builder.artist_path(name).strip("/") / "index.html"
            assert href in profile.read_text(), (identity, name, "missing artist archive")
        if "after-doves" in identity:
            # Existing archive pages intentionally display calendar dates only;
            # the durable record must still retain the exact overnight timing.
            assert event["endDate"] == "2026-10-06"
            assert event["endDateTime"] == "2026-10-07T00:00:00-05:00", "Actual midnight end was lost"
    print(f"October 7 discoveries verified: {checked} upcoming additions; both October 6 events archived")


if __name__ == "__main__":
    verify(Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve())
