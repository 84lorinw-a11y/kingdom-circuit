import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from apply_sep26_requested_lineups import PATCHES, patch_event


class RequestedLineupTests(unittest.TestCase):
    def test_gate_checks_reviewed_record_before_provider_display_merge(self):
        import verify_sep26_requested_lineups as gate
        wanted = dict(startDate="2099-10-31", startTime="16:00", title="Reviewed concert",
                      venue="Concert Park", artists=["Reviewed artist"],
                      advertisedBilling=["Reviewed artist"])
        primary = dict(wanted, id="manual:reviewed-concert", city="Austin", state="TX")
        provider = dict(primary, id="provider:separate-listing", artists=["Additional artist"])
        href = gate.builder.event_path(primary)
        schema = {"@type": "MusicEvent", "performer": [{"name": "Reviewed artist"}]}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(gate.PATCHES, {"reviewed-concert": wanted}, clear=True):
            site = Path(tmp)
            (site / "config").mkdir()
            (site / "config/artists.json").write_text("[]")
            (site / "events.json").write_text(json.dumps([primary]))
            (site / "supplemental-events.json").write_text(json.dumps([provider]))
            (site / "shows").mkdir()
            (site / "shows/index.html").write_text(
                f'<article data-event-card><a href="{href}">Reviewed artist</a></article>')
            detail = site / href.strip("/") / "index.html"
            detail.parent.mkdir(parents=True)
            detail.write_text('<p class="artist-line">Reviewed artist</p>'
                              + '<script type="application/ld+json">' + json.dumps(schema) + '</script>')
            gate.verify(site)
            # A provider contribution must not hide damage to the reviewed record.
            primary["artists"] = []
            (site / "events.json").write_text(json.dumps([primary]))
            with self.assertRaises(AssertionError):
                gate.verify(site)
            primary["artists"] = ["Reviewed artist"]
            (site / "events.json").write_text(json.dumps([primary]))
            detail.write_text(detail.read_text().replace('<p class="artist-line">Reviewed artist</p>',
                                                         '<p class="artist-line">Wrong artist</p>'))
            with self.assertRaises(AssertionError):
                gate.verify(site)

    def test_refresh_is_scoped_idempotent_and_preserves_discovery(self):
        for event_id, wanted in PATCHES.items():
            with self.subTest(event=event_id):
                row = dict(id="manual:" + event_id, startDate=wanted["startDate"],
                           firstSeen="2026-08-01", sources=[{"url": "https://old.example/event"}],
                           legacyEventPaths=["/event/old/"])
                self.assertTrue(patch_event(row))
                self.assertEqual(row["id"], "manual:" + event_id)
                self.assertEqual(row["firstSeen"], "2026-08-01")
                self.assertIn({"url": "https://old.example/event"}, row["sources"])
                once = copy.deepcopy(row)
                patch_event(row)
                self.assertEqual(row, once)
                row["startDate"] = "2028-01-01"
                before = copy.deepcopy(row)
                self.assertFalse(patch_event(row))
                self.assertEqual(row, before)

    def test_flavor_days_follow_current_posters_without_duplicate_performers(self):
        friday = PATCHES["flavor-fest-2026-friday-concerts"]["advertisedBilling"]
        saturday = PATCHES["flavor-fest-2026-saturday-concerts"]["advertisedBilling"]
        self.assertEqual((len(friday), len(saturday)), (28, 20))
        self.assertEqual(len(friday), len(set(friday)))
        self.assertIn("Yung Kriss", friday)
        self.assertNotIn("Gifted Hands", friday)
        self.assertIn("Gifted Hands", saturday)
        self.assertNotIn("Yung Kriss", saturday)
        self.assertIn("Songbird SB", friday)
        self.assertNotIn("Breezy", friday)
        self.assertNotIn("Von Won", friday)

    def test_concert_starts_are_distinct_from_doors_and_vip(self):
        glo = PATCHES["bandsintown:1040378722"]
        self.assertEqual(glo["startTime"], "20:00")
        self.assertEqual(glo["doorsTime"], "19:00")
        self.assertIn("CJ Emulous", glo["artists"])
        self.assertEqual(PATCHES["mike-teezy-hrvstland-festival-2026"]["startTime"], "16:00")
        self.assertNotIn("cj-emulous-glo-concert-los-angeles-2026", PATCHES)
        awake = PATCHES["supplemental:brenno-awake-conference-2026"]
        self.assertEqual(len(awake["advertisedBilling"]), 6)
        self.assertIn("Eli Williams", awake["advertisedBilling"])
        self.assertNotIn("startTime", awake)


if __name__ == "__main__":
    unittest.main()
