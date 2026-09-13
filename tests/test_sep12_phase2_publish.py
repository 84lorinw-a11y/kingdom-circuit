import json
import pathlib
import tempfile
import unittest

from scripts import finalize_seo_indexing as finalizer
from scripts import apply_sep12_phase2_repairs as phase2

ROOT = pathlib.Path(__file__).resolve().parents[1]


class September12Phase2PublishTests(unittest.TestCase):
    def test_phase2_repairs_truthx_sevin_and_mercury_without_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "events.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": phase2.TRUTHX_ID,
                            "status": "scheduled",
                            "ticketUrl": "https://www.eventbrite.com/e/truthx-concert-2026-tickets-1989610293948",
                        },
                        {
                            "id": "1976535062579",
                            "status": "scheduled",
                            "ticketUrl": "https://www.eventbrite.com/e/sevin-live-concert-tickets-1976535062579",
                            "officialUrl": "https://hogmob.com/sevin-live-concert/",
                            "sources": [
                                {"url": "https://www.eventbrite.com/e/sevin-live-concert-tickets-1976535062579"},
                                {"url": "https://hogmob.com/sevin-live-concert/"},
                            ],
                        },
                        {
                            "id": phase2.MERCURY_ID,
                            "status": "scheduled",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            phase2.apply(path)
            rows = {row["id"]: row for row in json.loads(path.read_text(encoding="utf-8"))}
            truthx = rows[phase2.TRUTHX_ID]
            self.assertTrue(truthx["soldOut"])
            self.assertEqual(truthx["ticketAvailability"], "sold_out")
            self.assertNotEqual(truthx["status"], "cancelled")
            sevin = rows["1976535062579"]
            self.assertEqual(sevin["ticketUrl"], "")
            self.assertEqual(sevin["ticketAvailability"], "needs_confirmation")
            self.assertNotEqual(sevin["status"], "cancelled")
            self.assertEqual([source["url"] for source in sevin["sources"]], ["https://hogmob.com/sevin-live-concert/"])
            self.assertEqual(rows[phase2.MERCURY_ID]["ageRestriction"], "18+")

    def test_future_sevin_records_do_not_publish_broken_ticket_offers(self):
        events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        for event in events:
            if str(event.get("id") or "").removeprefix("manual:") not in phase2.SEVIN_IDS:
                continue
            self.assertFalse(event.get("ticketUrl"))
            self.assertEqual(event.get("ticketAvailability"), "needs_confirmation")
            self.assertNotEqual(event.get("status"), "cancelled")
            self.assertTrue(any("hogmob.com" in str(source.get("url") or "") for source in event.get("sources") or []))

    def test_schema_offers_use_direct_ticket_and_only_supported_availability(self):
        direct = {"ticketUrl": "https://tickets.example/show", "price": "$20", "ticketAvailability": "sold_out"}
        offer = finalizer.event_offer(direct)
        self.assertEqual(offer["url"], direct["ticketUrl"])
        self.assertEqual(offer["availability"], "https://schema.org/SoldOut")

        no_direct_ticket = {
            "officialUrl": "https://www.instagram.com/p/example/",
            "price": "$20",
            "ticketAvailability": "available",
        }
        self.assertIsNone(finalizer.event_offer(no_direct_ticket))

        unknown = {"ticketUrl": "https://tickets.example/show", "price": "$20"}
        offer = finalizer.event_offer(unknown)
        self.assertNotIn("availability", offer)

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
        self.assertIn("python scripts/apply_deonte_hall_submission.py", workflow)
        self.assertNotIn("git pull --rebase origin main", workflow)
        self.assertLess(workflow.index("git fetch origin main"), workflow.index("git reset --hard origin/main"))
        self.assertLess(workflow.index("git reset --hard origin/main"), workflow.rindex("python scripts/apply_deonte_hall_submission.py"))
        self.assertLess(workflow.rindex("python scripts/apply_deonte_hall_submission.py"), workflow.index("git add -A"))


if __name__ == "__main__":
    unittest.main()
