import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_egr_bizzle_updates as repair
import build_seo_site as builder


class EgrBizzleRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.original = {"id": "manual:egr-2026-10-03-chandler-az", "title": "EGR Live — Chandler",
                         "startDate": "2026-10-03", "city": "Chandler", "artists": ["EGR"],
                         "firstSeen": "2026-08-01T10:00:00Z", "image": repair.OLD_PORTRAIT,
                         "sources": [{"name": "Original artist schedule", "url": "https://example.com/tour"}]}
        self.other_show = {"id": "bizzle-other-show", "startDate": "2026-10-03", "city": "Chandler",
                           "venue": "Another venue", "startTime": "12:00", "artists": ["Bizzle"],
                           "image": "assets/events/other-artwork.jpg"}
        self.duplicate = {"id": "bandsintown:108954639", "artists": ["Bizzle"],
                          "sources": [{"name": "Bandsintown", "url": "https://www.bandsintown.com/e/108954639"}]}
        self.egr = {"name": "EGR", "rosterOrder": 22, "spotifyProfile": repair.PORTRAIT_SOURCE,
                    "instagramProfile": "https://www.instagram.com/egrxofficial/", "imageUrl": repair.OLD_PORTRAIT}
        self.bizzle = {"name": "Bizzle", "rosterOrder": 30, "imageUrl": "bizzle-photo.jpg",
                       "instagramProfile": "https://www.instagram.com/bizzle/"}
        self.save("config/artists.json", [self.egr, self.bizzle])
        self.save("config/manual-events.json", [dict(self.original, id="egr-2026-10-03-chandler-az")])
        self.save("events.json", [self.original])
        self.save("supplemental-events.json", [self.duplicate, self.other_show])
        self.save("event-history.json", {"events": [{"id": "past-egr", "image": repair.OLD_PORTRAIT,
                                                     "startDate": "2026-03-01"}], "summary": {"total": 1}})

    def save(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def read(self, name):
        return json.loads((self.root / name).read_text())

    def apply(self, today="2026-09-25"):
        repair.apply(self.root, today=today)

    def test_collector_duplicate_is_reconciled_without_losing_history_or_unrelated_show(self):
        self.apply()
        self.assertEqual([self.other_show], self.read("supplemental-events.json"))
        canonical = next(e for e in self.read("events.json") if e["city"] == "Chandler")
        self.assertEqual("2026-08-01T10:00:00Z", canonical["firstSeen"])
        self.assertTrue(all(s in canonical["sources"] for s in self.original["sources"] + self.duplicate["sources"]))
        self.assertEqual(["EGR", "Bizzle"], canonical["artists"])
        self.assertEqual(5, len(canonical["advertisedBilling"]))
        self.assertIn("/event/bizzle-at-vybe-event-center-2026-10-03-chandler-998ccf/", canonical["legacyEventPaths"])
        # A subsequent collector can reintroduce its original record.
        self.save("supplemental-events.json", [self.other_show, self.duplicate])
        self.apply()
        self.assertEqual([self.other_show], self.read("supplemental-events.json"))
        self.assertEqual(canonical, next(e for e in self.read("events.json") if e["city"] == "Chandler"))

    def test_refresh_is_idempotent_and_does_not_restore_completed_shows(self):
        self.apply()
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*.json")}
        self.apply()
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*.json")})
        self.apply(today="2026-10-05")
        self.assertEqual([], self.read("events.json"))
        self.assertEqual([self.other_show], self.read("supplemental-events.json"))
        self.assertEqual(2, len(self.read("config/manual-events.json")))

    def test_overnight_show_remains_until_its_final_day(self):
        self.apply(today="2026-10-04")
        self.assertEqual(["Chandler"], [e["city"] for e in self.read("events.json")])

    def test_midnight_finish_is_one_evening_but_real_multi_day_events_keep_range(self):
        event = repair.EVENTS[1]
        self.assertEqual("Sat, Oct 3, 2026 - 7:00 PM", builder.format_date(event))
        self.assertIn("3–4", builder.format_date(dict(event, endTime="20:00")))
        self.assertIn("3–4", builder.format_date(dict(event, startTime="", endTime="")))
        schema = builder.event_schema(event)
        self.assertEqual("2026-10-03T19:00:00-07:00", schema["startDate"])
        self.assertEqual("2026-10-04T00:00:00-07:00", schema["endDate"])

    def test_portrait_replaces_only_old_fallback_and_preserves_socials(self):
        portrait = {"id": "egr-other", "image": repair.OLD_PORTRAIT, "artists": ["EGR"]}
        poster = {"id": "egr-poster", "image": "assets/events/real-poster.jpg", "imageType": "event_artwork", "artists": ["EGR"]}
        self.save("supplemental-events.json", [portrait, poster])
        self.apply()
        rows = {e["id"]: e for e in self.read("supplemental-events.json")}
        self.assertEqual(poster, rows["egr-poster"])
        self.assertEqual(repair.PORTRAIT, rows["egr-other"]["image"])
        updated, bizzle = self.read("config/artists.json")
        for key, value in self.egr.items():
            if key != "imageUrl":
                self.assertEqual(value, updated[key])
        for key, value in self.bizzle.items():
            if key != "imageUrl":
                self.assertEqual(value, bizzle[key])
        self.assertEqual(repair.BIZZLE_PORTRAIT, bizzle["imageUrl"])
        self.assertEqual("50% 0%", bizzle["imagePosition"])
        history = self.read("event-history.json")
        self.assertEqual({"total": 1}, history["summary"])
        self.assertEqual("2026-03-01", history["events"][0]["startDate"])
        self.assertEqual(repair.PORTRAIT, history["events"][0]["image"])


if __name__ == "__main__":
    unittest.main()
