import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_sep12_phase2_repairs as phase2
import apply_sevin_official_schedule as sevin
import finalize_seo_indexing as finalizer


class September12Phase2PublishTests(unittest.TestCase):
    def test_future_sevin_records_do_not_publish_broken_ticket_offers(self):
        future = [event for event in sevin.SEVIN_EVENTS if event["startDate"] > "2026-09-12"]
        self.assertEqual(4, len(future))
        for event in future:
            self.assertEqual("", event.get("ticketUrl"))
            self.assertEqual("needs_confirmation", event.get("ticketAvailability"))
            self.assertEqual(sevin.HOGMOB_URL, event.get("officialUrl"))

    def test_phase2_repairs_truthx_sevin_and_mercury_without_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            rows = [
                {
                    "id": "eventbrite:truthx-yung-kriss-brandon-2026",
                    "title": "TruthX Concert 2026",
                    "status": "scheduled",
                    "ticketUrl": f"https://www.eventbrite.com/e/{phase2.TRUTHX_EVENTBRITE_ID}",
                },
                {
                    "id": "sevin-live-kansas-city-2026-09-26",
                    "artists": ["Sevin"],
                    "ticketUrl": "https://www.eventbrite.com/e/1976535062579?aff=oddtdtcreator",
                    "officialUrl": phase2.SEVIN_HOGMOB_URL,
                    "sources": [{"url": "https://www.eventbrite.com/e/1976535062579?aff=oddtdtcreator"}],
                },
                {"id": phase2.ZAUNTEE_MERCURY_ID, "title": "Zauntee — God Remembers Tour"},
            ]
            paths = []
            for name in ("events.json", "supplemental-events.json", "manual-events.json"):
                path = root / name
                path.write_text(json.dumps(rows), encoding="utf-8")
                paths.append(path)

            original = phase2.EVENT_FILES
            try:
                phase2.EVENT_FILES = tuple(paths)
                phase2.apply()
                phase2.check()
                fixed = json.loads(paths[0].read_text(encoding="utf-8"))
            finally:
                phase2.EVENT_FILES = original

            truthx = fixed[0]
            self.assertTrue(truthx["soldOut"])
            self.assertEqual("sold_out", truthx["ticketAvailability"])
            self.assertEqual("scheduled", truthx["status"])
            self.assertEqual("", fixed[1]["ticketUrl"])
            self.assertEqual("needs_confirmation", fixed[1]["ticketAvailability"])
            self.assertEqual("18+", fixed[2]["ageRestriction"])

    def test_schema_offers_use_direct_ticket_and_only_supported_availability(self):
        schema = {
            "@type": "MusicEvent",
            "offers": {"@type": "Offer", "url": "https://example.com/event", "availability": "https://schema.org/InStock"},
            "image": ["assets/events/test.jpg"],
        }
        source = {"ticketUrl": "https://tickets.example.com/123", "soldOut": True}
        self.assertTrue(finalizer.repair_event_schema(schema, source))
        self.assertEqual("https://tickets.example.com/123", schema["offers"]["url"])
        self.assertEqual("https://schema.org/SoldOut", schema["offers"]["availability"])
        self.assertEqual("https://kingdomcircuit.com/assets/events/test.jpg", schema["image"][0])

        unsupported = {"@type": "MusicEvent", "offers": {"@type": "Offer", "url": "https://instagram.com/p/test", "availability": "https://schema.org/InStock"}}
        self.assertTrue(finalizer.repair_event_schema(unsupported, {"ticketUrl": "https://instagram.com/p/test"}))
        self.assertNotIn("offers", unsupported)

    def test_disabled_madison_profile_is_removed_from_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = pathlib.Path(tmp)
            profile = site / "artists" / "madison-ryann-ward"
            profile.mkdir(parents=True)
            (profile / "index.html").write_text("stale", encoding="utf-8")
            sitemap = site / "sitemap.xml"
            sitemap.write_text(
                '<urlset><url><loc>https://kingdomcircuit.com/artists/madison-ryann-ward/</loc><lastmod>2026-09-12</lastmod></url></urlset>',
                encoding="utf-8",
            )
            result = finalizer.remove_disabled_artist_outputs(site)
            self.assertFalse(profile.exists())
            self.assertNotIn("madison-ryann-ward", sitemap.read_text(encoding="utf-8"))
            self.assertGreaterEqual(result["profiles_removed"], 1)

    def test_deonte_guard_recomputes_complete_repair_set_after_raced_push(self):
        workflow = (ROOT / ".github" / "workflows" / "guard-deonte-hall-submission.yml").read_text(encoding="utf-8")
        self.assertIn("git add -A", workflow)
        self.assertIn("for attempt in 1 2 3", workflow)
        self.assertIn("git fetch origin main", workflow)
        self.assertIn("git reset --hard origin/main", workflow)
        self.assertNotIn("git pull --rebase origin main", workflow)
        self.assertLess(workflow.index("git fetch origin main"), workflow.index("git reset --hard origin/main"))
        self.assertLess(workflow.index("git reset --hard origin/main"), workflow.rindex("python scripts/apply_deonte_hall_submission.py"))
        self.assertLess(workflow.rindex("python scripts/apply_deonte_hall_submission.py"), workflow.index("git add -A"))


if __name__ == "__main__":
    unittest.main()
