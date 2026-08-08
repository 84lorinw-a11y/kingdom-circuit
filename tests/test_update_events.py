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


class KingdomCircuitV7Tests(unittest.TestCase):
    def test_workplay_variants_merge(self):
        first = candidate(venue="Workplay Theatre", artists=["Hulvey"], url="https://a.example")
        second = candidate(venue="Workplay", artists=["Hulvey"], url="https://b.example")
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]["sources"]), 2)

    def test_tower_theatre_city_suffix_merges(self):
        first = candidate(
            title="Hulvey w/ Indie Tribe",
            venue="Tower Theatre - Oklahoma City",
            city="Oklahoma City",
            state="OK",
            artists=["Hulvey", "indie tribe."],
            url="https://ticket.example/tower",
        )
        second = candidate(
            title="Tower Theatre",
            venue="Tower Theatre",
            city="Oklahoma City",
            state="OK",
            artists=["Hulvey"],
            url="https://artist.example/tower",
        )
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]["sources"]), 2)

    def test_novo_sponsor_suffix_merges(self):
        first = candidate(
            title="Hulvey",
            venue="The Novo by Microsoft",
            city="Los Angeles",
            state="CA",
            artists=["Hulvey"],
            url="https://ticket.example/novo",
        )
        second = candidate(
            title="The Novo",
            venue="The Novo",
            city="Los Angeles",
            state="CA",
            artists=["Hulvey"],
            url="https://artist.example/novo",
        )
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 1)

    def test_same_artist_same_city_different_show_times_do_not_merge(self):
        first = candidate(title="KB Matinee", venue="Ryman Auditorium", artists=["KB"], url="https://a.example")
        second = candidate(title="KB Late Show", venue="Ryman Auditorium", artists=["KB"], url="https://b.example")
        first["startTime"] = "13:00"
        second["startTime"] = "20:00"
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 2)


    def test_steven_malcolm_timezone_shift_duplicate_merges(self):
        official = candidate(
            title="Steven Malcolm at The Centre",
            venue="The Centre Cafe",
            city="Adrian",
            state="MI",
            artists=["Steven Malcolm"],
            url="https://stevenmalcolm.com/",
        )
        apple = candidate(
            title="Steven Malcolm",
            venue="The Centre Café",
            city="Adrian",
            state="MI",
            artists=["Steven Malcolm"],
            url="https://music.apple.com/us/concerts/ce.8211b80e-7b98-426e-8b33-0c157be143e2",
        )
        official["address"] = "1800 W Maumee St"
        apple["address"] = "1800 West Maumee Street"
        official["startTime"] = "19:30"
        apple["startTime"] = "23:30"
        merged = MODULE.merge_events([official, apple])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]["sources"]), 2)

    def test_1k_phew_space_city_bandsintown_identity_merges(self):
        first = candidate(
            title="Konnect Concert Series",
            venue="Space City Church",
            city="Houston",
            state="TX",
            artists=["1K Phew", "Parris Chariz"],
            url="https://www.bandsintown.com/e/1038610442-1k-phew-at-space-city-church",
        )
        second = candidate(
            title="1K Phew at Space City Church",
            venue="Space City Church",
            city="South Houston",
            state="TX",
            artists=["1K Phew"],
            url="https://www.bandsintown.com/e/1038610442-1k-phew-at-space-city-church?came_from=253",
        )
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 1)
        self.assertIn("Parris Chariz", merged[0]["artists"])

    def test_1k_phew_fastivalle_ticket_identity_merges(self):
        first = candidate(
            title="Fastivalle 2026",
            venue="Everwise Amphitheater",
            city="Indianapolis",
            state="IN",
            artists=["1K Phew"],
            url="https://www.bandsintown.com/e/1040026694-1k-phew-at-everwise-amphitheater",
        )
        second = candidate(
            title="1K Phew - Fastivalle",
            venue="Everwise Amphitheater at White River State Park",
            city="North Indianapolis",
            state="IN",
            artists=["1K Phew"],
            url="https://www.bandsintown.com/e/1040026694-1k-phew-at-everwise-amphitheater?came_from=257",
        )
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 1)

    def test_1k_phew_uses_approved_local_artist_image(self):
        artists = json.loads((ROOT / "config" / "artists.json").read_text())
        images = MODULE.artist_image_map(artists, {})
        positions = MODULE.artist_image_positions(artists)
        preferred = MODULE.preferred_artist_images(artists)
        event = candidate(
            title="1K Phew Live",
            artists=["1K Phew"],
            headliner="1K Phew",
            authority="venue_ticket",
            image="https://example.com/generic-ticket-image.jpg",
        )
        final = MODULE.finalize_events(
            MODULE.merge_events([event]),
            images,
            date(2098, 1, 1),
            positions,
            preferred,
        )
        self.assertEqual(final[0]["image"], "assets/artists/1k-phew.webp")
        self.assertEqual(final[0]["imageType"], "artist")
        self.assertEqual(final[0]["imagePosition"], "50% 24%")

    def test_first_seen_marks_only_genuinely_new_events(self):
        existing = candidate(title="Existing Show", artists=["KB"], url="https://example.com/existing")
        existing["firstSeen"] = "2097-12-01T00:00:00Z"
        fresh_existing = candidate(title="Existing Show", artists=["KB"], url="https://example.com/existing")
        new_event = candidate(title="Brand New Show", event_date="2099-09-10", artists=["Hulvey"], url="https://example.com/new")
        result = MODULE.apply_first_seen([fresh_existing, new_event], [existing], CHECKED)
        self.assertEqual(result[0]["firstSeen"], "2097-12-01T00:00:00Z")
        self.assertEqual(result[1]["firstSeen"], CHECKED)

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

    def test_venue_only_title_becomes_artist_live_title(self):
        event = candidate(
            title="The Novo",
            venue="The Novo",
            city="Los Angeles",
            state="CA",
            artists=["Hulvey"],
        )
        final = MODULE.finalize_events(MODULE.merge_events([event]), {}, date(2098, 1, 1))
        self.assertEqual(final[0]["title"], "Hulvey — Live at The Novo")

    def test_unknown_venue_uses_public_tba_language(self):
        event = candidate(
            title="Caleb Gordon - The Eden Experience",
            venue="Venue not provided",
            city="Phoenix",
            state="AZ",
            artists=["Caleb Gordon"],
        )
        final = MODULE.finalize_events(MODULE.merge_events([event]), {}, date(2098, 1, 1))
        self.assertEqual(final[0]["venue"], "Venue to be announced")

    def test_at_venue_is_extracted_when_source_repeats_title_as_venue(self):
        event = candidate(
            title="Hip Hop Nights @The Rock Box w/ 1K Phew",
            venue="Hip Hop Nights @The Rock Box w/ 1K Phew",
            city="San Antonio",
            state="TX",
            artists=["1K Phew"],
        )
        final = MODULE.finalize_events(MODULE.merge_events([event]), {}, date(2098, 1, 1))
        self.assertEqual(final[0]["venue"], "The Rock Box")
        self.assertEqual(final[0]["title"], "Hip Hop Nights @The Rock Box w/ 1K Phew")

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


    def test_requested_v7_artist_roster_is_present(self):
        artists = json.loads((ROOT / "config" / "artists.json").read_text())
        names = {item["name"] for item in artists}
        expected = {
            "EGR", "Sevin", "ASAP Preach", "Nicky Gracious", "Brother Bo",
            "Tommy Chapa", "B. Cody Shields", "Santana Rose", "DJ Winn",
            "J.List", "BIG HOLY", "KJ-52", "Bryann T", "Young Bro",
            "D-Maub", "K-Drama", "GAWVI", "Monster Tarver", "Taelor Gray",
            "ZEE", "IMRSQD", "TJ Carroll", "Coop", "CJ Emulous",
            "Lul DreDay", "REDEEMED", "Pishko",
        }
        self.assertTrue(expected.issubset(names))

    def test_just_announced_catalog_is_baselined_before_activation(self):
        new_event = candidate(title="New Before Launch", url="https://example.com/prelaunch")
        result = MODULE.apply_first_seen([new_event], [], "2026-08-06T12:00:00Z")
        self.assertEqual(result[0]["firstSeen"], MODULE.BASELINE_FIRST_SEEN)

    def test_just_announced_marks_new_event_after_activation(self):
        new_event = candidate(title="New After Launch", url="https://example.com/postlaunch")
        checked = "2026-08-11T12:00:00Z"
        result = MODULE.apply_first_seen([new_event], [], checked)
        self.assertEqual(result[0]["firstSeen"], checked)

    def test_sevin_tour_parser_finds_future_us_dates(self):
        source = {
            "name": "Sevin official tour",
            "parser": "sevin_tour",
            "authority": "artist_calendar",
            "priority": 80,
            "lineupExplicit": True,
            "imagePolicy": "ignore",
        }
        html = """
          <h4>SAN DIEGO, CA</h4><p>Location: TBD</p>
          <p>August 29th 2099 (8pm – 11pm)</p>
          <a href="https://www.eventbrite.com/e/test-one">BUY TICKET</a>
          <h4>KANSAS CITY, MO</h4><p>Location: TBD</p>
          <p>September 26th 2099 (8pm – 11pm)</p>
          <a href="https://www.eventbrite.com/e/test-two">BUY TICKET</a>
        """
        events = MODULE.collect_sevin_tour_source(
            source,
            "https://hogmob.com/sevin-live-concert/",
            html,
            {"sevin": "Sevin"},
            CHECKED,
        )
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["artists"], ["Sevin"])
        self.assertEqual(events[0]["city"], "San Diego")
        self.assertEqual(events[0]["state"], "CA")

    def test_egr_official_youtube_source_is_configured(self):
        sources = json.loads((ROOT / "config" / "official-sources.json").read_text())
        egr_sources = [item for item in sources if item.get("artist") == "EGR"]
        self.assertTrue(egr_sources)
        self.assertTrue(any("youtube.com" in item.get("url", "") for item in egr_sources))

    def test_new_verified_independent_events_are_present(self):
        manual = json.loads((ROOT / "config" / "manual-events.json").read_text())
        identifiers = {item["id"] for item in manual}
        expected = {
            "hope-fest-daytona-2026",
            "turned-up-for-christ-corbin-2026",
            "faith-jam-sparta-2026",
        }
        self.assertTrue(expected.issubset(identifiers))

    def test_master_v8_roster_has_300_unique_artists(self):
        artists = json.loads((ROOT / "config" / "artists.json").read_text())
        names = [item["name"] for item in artists]
        self.assertEqual(len(names), 300)
        self.assertEqual(len({name.casefold() for name in names}), 300)
        self.assertEqual(sum(1 for item in artists if item.get("monitoringPriority") == 1), 100)
        self.assertEqual(sum(1 for item in artists if item.get("monitoringPriority") == 2), 100)
        self.assertEqual(sum(1 for item in artists if item.get("monitoringPriority") == 3), 100)

    def test_top_streaming_priority_artists_are_present(self):
        artists = json.loads((ROOT / "config" / "artists.json").read_text())
        names = {item["name"] for item in artists}
        required = {
            "Lecrae", "Hulvey", "KB", "Caleb Gordon", "Andy Mineo",
            "nobigdyl.", "Alex Jean", "gio.", "Torey D'Shaun", "Redimi2",
            "GRITS", "Funky", "Forrest Frank", "NF", "Nic D", "1K Phew",
            "Jon Keith", "Miles Minnick", "Tedashii", "Trip Lee", "Manafest",
            "Pastor Mike Jr.", "Pregador Luo", "Nesk Only", "Futuristic",
            "Beacon Light", "Sondae", "FLAME", "Scootie Wop", "Aaron Cole",
        }
        self.assertTrue(required.issubset(names))
        top = {item["name"] for item in artists if item.get("topStreamingPriority")}
        self.assertEqual(top, required)

    def test_mike_malagies_manual_show_is_preserved(self):
        manual = json.loads((ROOT / "config" / "manual-events.json").read_text())
        event = next(item for item in manual if item.get("id") == "let-the-church-sing-tour-dunedin-2026")
        self.assertEqual(event["startDate"], "2026-10-02")
        self.assertIn("Mike Malagies", event["artists"])

    def test_ambiguous_artist_names_are_blocked_only_in_free_text(self):
        artists = json.loads((ROOT / "config" / "artists.json").read_text())
        lookup = MODULE.build_alias_lookup(artists)
        original = MODULE.TEXT_MATCH_BLOCKLIST.copy()
        try:
            MODULE.TEXT_MATCH_BLOCKLIST = MODULE.configure_text_match_blocklist(artists)
            self.assertNotIn("Mission", MODULE.match_artists_in_text("Our mission is to serve the city", lookup))
            self.assertNotIn("Canon", MODULE.match_artists_in_text("Canon cameras are not allowed", lookup))
            self.assertEqual(MODULE.match_tracked_artists(["Mission"], lookup), ["Mission"])
        finally:
            MODULE.TEXT_MATCH_BLOCKLIST = original

    def test_expanded_high_value_sources_are_configured(self):
        sources = json.loads((ROOT / "config" / "official-sources.json").read_text())
        names = {item.get("name") for item in sources}
        expected = {
            "Manafest official tour",
            "GRITS Bandsintown public calendar",
            "Nic D Bandsintown public calendar",
            "Pastor Mike Jr. Bandsintown public calendar",
            "TobyMac official tour",
            "Yung Kriss Bandsintown public calendar",
        }
        self.assertTrue(expected.issubset(names))


class InstagramMonitoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        social_path = ROOT / "scripts" / "instagram_monitor.py"
        social_spec = importlib.util.spec_from_file_location("instagram_monitor_test", social_path)
        cls.social = importlib.util.module_from_spec(social_spec)
        assert social_spec.loader
        social_spec.loader.exec_module(cls.social)

    def test_instagram_queries_cover_the_social_priority_tier(self):
        artists = json.loads((ROOT / "config" / "artists.json").read_text())
        queries = self.social.build_search_queries(artists, 2099, batch_size=5)
        combined = " ".join(queries)
        enabled = [artist for artist in artists if self.social.social_search_enabled(artist)]
        disabled = [artist for artist in artists if artist.get("enabled", True) and not self.social.social_search_enabled(artist)]
        for artist in enabled:
            self.assertIn(f'"{artist["name"]}"', combined)
        for artist in disabled[:25]:
            self.assertNotIn(f'"{artist["name"]}"', combined)
        # The live scanner uses one search query per selected artist so the
        # highest-priority accounts are checked independently.
        self.assertEqual(len(self.social.build_search_queries(artists, 2099)), len(enabled))
        self.assertLess(len(enabled), len([artist for artist in artists if artist.get("enabled", True)]))

    def test_high_confidence_official_instagram_post_becomes_event(self):
        records = self.social._artist_records([
            {
                "name": "Scootie Wop",
                "aliases": ["Scootie Wop"],
                "enabled": True,
                "instagramProfile": "https://www.instagram.com/scootiewop/",
            }
        ])
        item = {
            "title": 'Scootie Wop (@scootiewop) on Instagram: "Houston concert June 10, 2099 at MATCH in Houston, TX"',
            "description": "Tickets available now. Doors open at 6:00 PM.",
            "link": "https://www.instagram.com/reel/TESTSOCIAL123/",
            "pubDate": "",
        }
        event, candidate_item = self.social.parse_result(item, records, date(2098, 1, 1), 550)
        self.assertIsNotNone(event)
        self.assertIsNone(candidate_item)
        self.assertEqual(event["artists"], ["Scootie Wop"])
        self.assertEqual(event["startDate"], "2099-06-10")
        self.assertEqual(event["city"], "Houston")
        self.assertEqual(event["state"], "TX")

    def test_uncertain_instagram_post_is_candidate_not_published(self):
        records = self.social._artist_records([
            {"name": "Mike Malagies", "aliases": ["Mike Malagies"], "enabled": True}
        ])
        item = {
            "title": "Mike Malagies on Instagram: Big announcement soon",
            "description": "See you there!",
            "link": "https://www.instagram.com/reel/UNRESOLVED123/",
            "pubDate": "",
        }
        event, candidate_item = self.social.parse_result(item, records, date(2098, 1, 1), 550)
        self.assertIsNone(event)
        self.assertIsNotNone(candidate_item)
        self.assertIn("future date", candidate_item["reason"])

    def test_instagram_festival_post_waits_for_official_festival_lineup(self):
        records = self.social._artist_records([
            {
                "name": "Social Club Misfits",
                "aliases": ["Social Club Misfits"],
                "enabled": True,
                "instagramProfile": "https://www.instagram.com/socialclubmisfits/",
            }
        ])
        item = {
            "title": 'Social Club Misfits on Instagram: "Festival August 28, 2099 in Isle, MN"',
            "description": "We are performing live at Rural Music Festival.",
            "link": "https://www.instagram.com/p/FESTIVALPOST123/",
            "pubDate": "",
        }
        event, candidate_item = self.social.parse_result(item, records, date(2098, 1, 1), 550)
        self.assertIsNone(event)
        self.assertIsNotNone(candidate_item)
        self.assertIn("official festival lineup", candidate_item["reason"])

    def test_social_event_normalizes_as_artist_calendar(self):
        raw = {
            "id": "instagram:reel:ABC",
            "title": "Steven Malcolm Live in Adrian",
            "startDate": "2099-08-20",
            "startTime": "19:30",
            "venue": "The Centre",
            "city": "Adrian",
            "state": "MI",
            "artists": ["Steven Malcolm"],
            "headliner": "Steven Malcolm",
            "officialUrl": "https://www.instagram.com/reel/ABC/",
            "sourceUrl": "https://www.instagram.com/reel/ABC/",
        }
        event = MODULE.normalize_social_event(raw, CHECKED)
        self.assertIsNotNone(event)
        self.assertEqual(event["sourceAuthority"], "artist_calendar")
        self.assertTrue(event["musicConfirmed"])

    def test_new_verified_manual_events_are_present(self):
        manual = json.loads((ROOT / "config" / "manual-events.json").read_text())
        identifiers = {item["id"] for item in manual}
        expected = {
            "steven-malcolm-the-centre-adrian-2026",
            "scootie-wop-southwest-trail-riders-houston-2026",
            "scootie-wop-match-houston-2026",
            "mike-teezy-stellar-popup-charlotte-2026",
        }
        self.assertTrue(expected.issubset(identifiers))

    def test_known_mike_malagies_instagram_post_is_monitored(self):
        posts = json.loads((ROOT / "config" / "known-instagram-posts.json").read_text())
        urls = {item["url"] for item in posts}
        self.assertIn("https://www.instagram.com/reel/DadaZKqPnGY/", urls)


if __name__ == "__main__":
    unittest.main()
