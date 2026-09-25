import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_man_of_faith_joz_shows as shows
import build_seo_site as builder


class SubmittedShowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        for name in ("config/manual-events.json", "events.json", "supplemental-events.json"):
            self.save(name, [])

    def save(self, name, rows):
        (self.root / name).write_text(json.dumps(rows))

    def read(self, name):
        return json.loads((self.root / name).read_text())

    def test_refresh_deduplicates_both_ticket_sources_without_changing_other_shows(self):
        ghost = shows.EVENTS[1]
        original = {"id": "collector:ghost", "officialUrl": ghost["officialUrl"] + "?fbclid=tracking",
                    "firstSeen": "2026-09-24T14:00:00Z", "sources": [{"url": ghost["officialUrl"], "name": "First discovery"}]}
        duplicate = {"id": "eventbrite:2000667257624", "ticketUrl": "https://eventbrite.com/e/another-slug-tickets-2000667257624?aff=tracking"}
        other = {"id": "nu-wave-next-show", "officialUrl": shows.EVENTS[0]["officialUrl"], "startDate": "2026-11-10", "city": "Sacramento"}
        self.save("events.json", [original])
        self.save("supplemental-events.json", [duplicate, other])
        shows.apply(self.root, "2026-09-25")
        self.assertEqual([other], self.read("supplemental-events.json"))
        event = next(r for r in self.read("events.json") if r["city"] == "Berkeley")
        self.assertEqual("2026-09-24T14:00:00Z", event["firstSeen"])
        self.assertIn(original["sources"][0], event["sources"])
        before = {p: p.read_bytes() for p in self.root.rglob("*.json")}
        shows.apply(self.root, "2026-09-25")
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*.json")})
        self.save("supplemental-events.json", [duplicate, other])
        shows.apply(self.root, "2026-09-25")
        self.assertEqual(len(shows.EVENTS), len(self.read("events.json")))

    def test_completed_shows_are_not_restored_and_event_day_stays_visible(self):
        shows.apply(self.root, "2026-10-30")
        self.assertEqual(["Miami Gardens"], [r["city"] for r in self.read("events.json")])
        shows.apply(self.root, "2026-10-31")
        self.assertEqual([], self.read("events.json"))
        self.assertEqual(len(shows.EVENTS), len(self.read("config/manual-events.json")))

    def test_source_utc_time_is_previous_local_day_and_confirmed_start_keeps_unknown_end(self):
        ghost = shows.EVENTS[1]
        utc = dt.datetime.fromisoformat("2026-10-18T00:00:00+00:00")
        self.assertEqual(utc.astimezone(ZoneInfo("America/Los_Angeles")).isoformat(), ghost["startDateTime"])
        self.assertEqual("2026-10-17T17:00:00-07:00", builder.event_schema(ghost)["startDate"])
        sacramento = shows.EVENTS[0]
        self.assertEqual("2026-10-10T17:00:00-07:00", builder.event_schema(sacramento)["startDate"])
        self.assertEqual("Nu Wave Church", sacramento["venue"])
        self.assertEqual("9529 Folsom Blvd, Suite D", sacramento["address"])
        self.assertFalse(sacramento["endTime"])

    def test_advertised_alias_links_to_existing_profile_without_linking_unknown_guests(self):
        artists = [{"name": "Joz", "aliases": ["Southside Joz", "Shared alias"]},
                   {"name": "Other", "aliases": ["Shared alias"]},
                   {"name": "Disabled", "aliases": ["DJ Mr. E"], "enabled": False}]
        card = builder.event_card(shows.EVENTS[2], artists)
        self.assertIn('<a href="/artists/joz/">Southside Joz</a>', card)
        self.assertIn('<span>DJ Mr. E</span>', card)
        self.assertNotIn('/artists/southside-joz/', card)
        self.assertEqual('<span>Shared alias</span>', builder.billing_links({"artists": ["Shared alias"]}, artists))
        self.assertIn('&lt;Guest&gt;', builder.billing_links({"artists": ["<Guest>"]}, artists))

    def test_weekend_itinerary_does_not_merge_different_sessions_or_blank_urls(self):
        spin = shows.EVENTS[3]
        saturday = dict(spin, id="saturday-ceremony", startDate="2026-10-24")
        self.assertFalse(shows.matches(saturday, spin))
        self.assertFalse(shows.matches({"id": "unrelated", "startDate": spin["startDate"], "city": spin["city"]}, spin))
        self.save("supplemental-events.json", [saturday])
        shows.apply(self.root, "2026-09-25")
        self.assertEqual([saturday], self.read("supplemental-events.json"))

    def test_assumed_artist_session_stays_explicit_and_is_not_schema_confirmed(self):
        from finalize_seo_indexing import repair_event_schema
        spin = shows.EVENTS[3]
        artists = [{"name": "Bobby Real Montgomery"}]
        line = builder.billing_links(spin, artists)
        self.assertIn('<a href="/artists/bobby-real-montgomery/">Bobby Real Montgomery</a> <span>(session unconfirmed)</span>', line)
        schema = builder.event_schema(spin)
        self.assertNotIn("performer", schema)
        self.assertIn("unconfirmed", schema["description"])
        self.assertEqual("2026-10-23T19:30:00-04:00", schema["startDate"])
        self.assertEqual("The Lawrence Hotel", schema["location"]["name"])
        stale = {"performer": [{"name": "Bobby Real Montgomery"}, {"name": "Confirmed guest"}]}
        self.assertTrue(repair_event_schema(stale, spin))
        self.assertEqual([{"name": "Confirmed guest"}], stale["performer"])
        self.assertFalse(repair_event_schema(stale, spin))
        self.assertNotIn('(session unconfirmed)', builder.billing_links(shows.EVENTS[0], artists))


if __name__ == "__main__":
    unittest.main()
