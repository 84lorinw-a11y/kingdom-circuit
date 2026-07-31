import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_events", ROOT / "scripts" / "update_events.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CHECKED = "2098-01-01T00:00:00Z"


def candidate(
    *,
    title="Test Tour",
    event_date="2099-08-10",
    venue="Test Theatre",
    city="Nashville",
    state="TN",
    artists=None,
    authority="venue_ticket",
    priority=94,
    event_type="concert",
    lineup_explicit=True,
    image="",
    image_policy="event_artwork",
    source_name="Test source",
    url="https://example.com/event",
    headliner="",
    discovery_only=False,
):
    artists = artists or ["KB"]
    source = {
        "name": source_name,
        "parser": "test",
        "authority": authority,
        "priority": priority,
        "lineupExplicit": lineup_explicit,
        "imagePolicy": image_policy,
        "discoveryOnly": discovery_only,
    }
    return MODULE.make_source_event(
        source=source,
        source_url=url,
        title=title,
        start_date=event_date,
        start_time="19:00",
        venue=venue,
        address="123 Main St",
        city=city,
        state=state,
        artists=artists,
        headliner=headliner or artists[0],
        checked_at=CHECKED,
        ticket_url=url,
        official_url=url,
        image=image,
        event_type=event_type,
        lineup_explicit=lineup_explicit,
        music_confirmed=True,
        priority=priority,
    )


class KingdomCircuitV2Tests(unittest.TestCase):
    def test_workplay_variants_merge(self):
        first = candidate(venue="Workplay Theatre", artists=["Hulvey"], url="https://a.example")
        second = candidate(venue="Workplay", artists=["Hulvey"], url="https://b.example")
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]["sources"]), 2)


    def test_consolidated_calendar_url_does_not_merge_different_dates(self):
        first = candidate(
            title="Reach Tour Date One",
            event_date="2099-08-10",
            city="Nashville",
            artists=["Lecrae"],
            url="https://label.example/events",
        )
        second = candidate(
            title="Reach Tour Date Two",
            event_date="2099-08-11",
            city="Atlanta",
            state="GA",
            artists=["Hulvey"],
            url="https://label.example/events",
        )
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 2)


    def test_same_consolidated_url_same_city_still_keeps_distinct_events(self):
        first = candidate(
            title="Lecrae Arena Concert",
            event_date="2099-08-10",
            venue="Bridgestone Arena",
            city="Nashville",
            artists=["Lecrae"],
            url="https://label.example/events",
        )
        second = candidate(
            title="Hulvey Club Show",
            event_date="2099-08-10",
            venue="The Basement East",
            city="Nashville",
            artists=["Hulvey"],
            url="https://label.example/events",
        )
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 2)

    def test_same_day_distinct_venues_do_not_merge(self):
        first = candidate(title="KB Signal Tour", venue="Ryman Auditorium", artists=["KB"], url="https://a.example")
        second = candidate(title="KB Pop-Up Show", venue="Rocketown", artists=["KB"], url="https://b.example")
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 2)

    def test_festival_lineup_comes_only_from_official_festival(self):
        official = candidate(
            title="Holy Smoke 2099",
            venue="Rocketown",
            artists=["indie tribe.", "Hulvey", "Social Club Misfits"],
            headliner="indie tribe.",
            authority="official_festival",
            priority=106,
            event_type="festival",
            lineup_explicit=True,
            image="https://example.com/holy-smoke-poster.jpg",
            url="https://festival.example",
        )
        label = candidate(
            title="Holy Smoke 2099",
            venue="Holy Smoke Festival",
            artists=["Lecrae", "Forrest Frank"],
            authority="artist_label",
            priority=84,
            event_type="festival",
            lineup_explicit=False,
            image="https://reachrecords.com/logo.png",
            url="https://label.example",
        )
        tm = candidate(
            title="Holy Smoke 2099",
            venue="Rocketown",
            artists=["KB"],
            authority="venue_ticket",
            priority=94,
            event_type="festival",
            lineup_explicit=True,
            url="https://ticket.example",
        )
        merged = MODULE.merge_events([label, tm, official])
        final = MODULE.finalize_events(merged, {}, date(2098, 1, 1))
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]["artists"], ["indie tribe.", "Hulvey", "Social Club Misfits"])
        self.assertNotIn("Lecrae", final[0]["artists"])
        self.assertNotIn("Forrest Frank", final[0]["artists"])
        self.assertNotIn("KB", final[0]["artists"])


    def test_festival_ticket_seller_image_does_not_replace_artist_photo(self):
        official_lineup = candidate(
            title="Verified Festival 2099",
            artists=["KB"],
            headliner="KB",
            authority="official_festival",
            priority=106,
            event_type="festival",
            lineup_explicit=True,
            image="",
            url="https://festival.example/lineup",
        )
        ticket = candidate(
            title="Verified Festival 2099",
            artists=["KB"],
            headliner="KB",
            authority="venue_ticket",
            priority=94,
            event_type="festival",
            lineup_explicit=True,
            image="https://ticket.example/generic-event.jpg",
            url="https://ticket.example/festival",
        )
        final = MODULE.finalize_events(
            MODULE.merge_events([ticket, official_lineup]),
            {"KB": "https://example.com/kb-approved.jpg"},
            date(2098, 1, 1),
        )
        self.assertEqual(final[0]["image"], "https://example.com/kb-approved.jpg")
        self.assertEqual(final[0]["imageType"], "artist")

    def test_festival_without_official_explicit_lineup_is_excluded(self):
        tm = candidate(
            title="Mystery Festival 2099",
            artists=["KB"],
            authority="venue_ticket",
            event_type="festival",
            lineup_explicit=True,
        )
        final = MODULE.finalize_events(MODULE.merge_events([tm]), {}, date(2098, 1, 1))
        self.assertEqual(final, [])

    def test_official_event_artwork_beats_label_logo(self):
        official = candidate(
            artists=["Lecrae"],
            authority="official_event",
            priority=100,
            image="https://example.com/tour-art.jpg",
            url="https://official.example",
        )
        label = candidate(
            artists=["Lecrae"],
            authority="artist_label",
            priority=84,
            image="https://reachrecords.com/logo.png",
            url="https://label.example",
        )
        final = MODULE.finalize_events(MODULE.merge_events([label, official]), {}, date(2098, 1, 1))
        self.assertEqual(final[0]["image"], "https://example.com/tour-art.jpg")
        self.assertEqual(final[0]["imageType"], "event_artwork")


    def test_label_logo_without_event_art_falls_back_to_artist(self):
        label_only = candidate(
            artists=["Lecrae"],
            authority="artist_label",
            priority=84,
            image="https://example.com/assets/reach-label-logo_white.png",
            url="https://label.example",
        )
        final = MODULE.finalize_events(
            MODULE.merge_events([label_only]),
            {"Lecrae": "https://example.com/lecrae-approved.jpg"},
            date(2098, 1, 1),
        )
        self.assertEqual(final[0]["image"], "https://example.com/lecrae-approved.jpg")
        self.assertEqual(final[0]["imageType"], "artist")

    def test_no_artwork_uses_headliner_base_image(self):
        event = candidate(artists=["KB", "Hulvey"], headliner="KB", image="", image_policy="ignore")
        final = MODULE.finalize_events(
            MODULE.merge_events([event]),
            {"KB": "https://example.com/kb.jpg", "Hulvey": "https://example.com/hulvey.jpg"},
            date(2098, 1, 1),
        )
        self.assertEqual(final[0]["image"], "https://example.com/kb.jpg")
        self.assertEqual(final[0]["imageType"], "artist")

    def test_fallback_image_is_local_logo(self):
        event = candidate(artists=["Unknown Tracked Artist"], image="", image_policy="ignore")
        final = MODULE.finalize_events(MODULE.merge_events([event]), {}, date(2098, 1, 1))
        self.assertEqual(final[0]["image"], "assets/logo.png")

    def test_discovery_only_event_needs_corroboration(self):
        discovery = candidate(authority="aggregator", priority=45, discovery_only=True)
        final = MODULE.finalize_events(MODULE.merge_events([discovery]), {}, date(2098, 1, 1))
        self.assertEqual(final, [])

    def test_non_music_title_is_excluded(self):
        event = candidate(title="Leadership Conference with KB")
        final = MODULE.finalize_events(MODULE.merge_events([event]), {}, date(2098, 1, 1))
        self.assertEqual(final, [])

    def test_non_us_event_is_excluded(self):
        event = candidate(state="ON", city="Toronto")
        final = MODULE.finalize_events(MODULE.merge_events([event]), {}, date(2098, 1, 1))
        self.assertEqual(final, [])


    def test_explicit_performer_order_selects_first_billed_headliner(self):
        lookup = {"kb": "KB", "hulvey": "Hulvey"}
        matched = MODULE.match_tracked_artists(["Hulvey", "KB"], lookup)
        self.assertEqual(matched, ["Hulvey", "KB"])

    def test_ticketmaster_rejects_non_music_segment(self):
        raw = {
            "id": "abc",
            "name": "KB Speaking Night",
            "dates": {"start": {"localDate": "2099-08-10", "localTime": "19:00:00"}},
            "classifications": [{"segment": {"name": "Miscellaneous"}}],
            "_embedded": {
                "venues": [{"name": "Test", "city": {"name": "Nashville"}, "state": {"stateCode": "TN"}, "country": {"countryCode": "US"}}],
                "attractions": [{"name": "KB"}],
            },
            "url": "https://ticket.example",
        }
        self.assertIsNone(MODULE.extract_ticketmaster_event(raw, "KB", {"kb": "KB"}, CHECKED))

    def test_ticketmaster_music_event_is_accepted(self):
        raw = {
            "id": "abc",
            "name": "KB Signal Tour",
            "dates": {"start": {"localDate": "2099-08-10", "localTime": "19:00:00"}, "status": {"code": "onsale"}},
            "classifications": [{"segment": {"name": "Music"}}],
            "_embedded": {
                "venues": [{"name": "Test Theatre", "city": {"name": "Nashville"}, "state": {"stateCode": "TN"}, "country": {"countryCode": "US"}}],
                "attractions": [{"name": "KB"}],
            },
            "url": "https://ticket.example",
            "images": [{"url": "https://example.com/event.jpg", "width": 1200, "height": 675}],
        }
        event = MODULE.extract_ticketmaster_event(raw, "KB", {"kb": "KB"}, CHECKED)
        self.assertIsNotNone(event)
        self.assertEqual(event["headliner"], "KB")
        self.assertEqual(event["externalIds"]["ticketmaster"], "abc")

    def test_manual_holy_smoke_lineup_and_artwork(self):
        manual = json.loads((ROOT / "config" / "manual-events.json").read_text())
        raw = next(item for item in manual if item["id"] == "holy-smoke-2026")
        event = MODULE.normalize_manual_event(raw, CHECKED)
        final = MODULE.finalize_events(MODULE.merge_events([event]), {}, date(2026, 7, 30))
        self.assertEqual(len(final), 1)
        self.assertNotIn("Lecrae", final[0]["artists"])
        self.assertNotIn("Forrest Frank", final[0]["artists"])
        self.assertEqual(final[0]["headliner"], "indie tribe.")
        self.assertIn("HolySmoke26.jpg", final[0]["image"])

    def test_roster_contains_all_current_reach_names(self):
        artists = json.loads((ROOT / "config" / "artists.json").read_text())
        names = {item["name"] for item in artists}
        expected = {"1K Phew", "2819 Worship", "Alexxander", "Anike", "Hulvey", "Jackie Hill Perry", "Lecrae", "Limoblaze", "Tedashii", "Trip Lee", "WHATUPRG"}
        self.assertTrue(expected.issubset(names))


if __name__ == "__main__":
    unittest.main()
