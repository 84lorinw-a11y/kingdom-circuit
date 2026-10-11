import sys
import json
import tempfile
from datetime import date
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_verified_event_overrides as overrides
import verify_oct2_verified_intake as intake


class ArtworkArchiveRolloverTests(unittest.TestCase):
    def test_completed_show_can_leave_live_feed_without_blocking_publication(self):
        mayia = "mayia-boxyard-saturdaze-2026"
        self.assertIn(mayia, overrides.required_event_image_ids("2026-10-10"))
        self.assertNotIn(mayia, overrides.required_event_image_ids("2026-10-11"))
        rows = [{"id": event_id} for event_id in overrides.VERIFIED_EVENT_IMAGES
                if event_id != mayia]
        with patch("prune_past_events.today_cutoff", return_value="2026-10-11"):
            overrides.apply_verified_event_images(rows, [])
        self.assertNotIn(mayia, {row["id"] for row in rows})
        self.assertTrue(all(row.get("imageOverride") for row in rows))

    def test_missing_current_show_still_blocks_publication(self):
        with patch("prune_past_events.today_cutoff", return_value="2026-10-10"):
            with self.assertRaisesRegex(SystemExit, "mayia-boxyard"):
                overrides.apply_verified_event_images([], [])

    def test_archived_record_still_receives_artwork_when_present(self):
        rows = [{"id": event_id} for event_id in overrides.VERIFIED_EVENT_IMAGES]
        with patch("prune_past_events.today_cutoff", return_value="2027-01-01"):
            overrides.apply_verified_event_images(rows, [])
        self.assertTrue(all(row["image"] == overrides.VERIFIED_EVENT_IMAGES[row["id"]]
                            for row in rows))

    def test_final_intake_verifier_allows_archiving_but_requires_future_shows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            for filename in ["config/artists.json", "config/verified-artist-registry-updates.json",
                             "config/oct2-verified-shows.json", "events.json", "supplemental-events.json"]:
                (root / filename).write_text("[]")
            (root / "sitemap.xml").write_text("")
            ids = ["egr-2026-10-10-visalia-ca", "bandsintown:108975912",
                   "bandsintown:108976155", "alex-jean-plaza-live-orlando-2026-11-27",
                   "sevin-live-nashville-2026-10-24"]
            patches = {event_id: {"startDate": "2026-10-10"} for event_id in ids}
            path = root / "config/sep26-requested-lineups.json"
            path.write_text(json.dumps(patches))
            with patch.object(intake, "ROOT", root), patch.object(intake, "verify_site", return_value={}), \
                    patch("build_seo_site.VISIBILITY_CUTOFF", date(2026, 10, 11)):
                intake.verify(root)
                patches[ids[0]]["startDate"] = "2026-10-12"
                path.write_text(json.dumps(patches))
                with self.assertRaisesRegex(AssertionError, ids[0]):
                    intake.verify(root)


if __name__ == "__main__":
    unittest.main()
