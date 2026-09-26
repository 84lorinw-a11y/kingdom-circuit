import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from apply_sep26_approved_audit import patch_event, PATCHES, sold_out_badge


class ApprovedAuditTests(unittest.TestCase):
    def test_refresh_restores_selected_facts_preserving_identity_roster_and_age(self):
        for event_id, wanted in PATCHES.items():
            with self.subTest(event_id=event_id):
                row = {"id": "manual:" + event_id, "firstSeen": "2026-08-09T00:00:00Z",
                       "artists": ["Existing curated performer"], "image": "stale-portrait.jpg",
                       "startTime": "09:00", "legacyEventPaths": ["/event/older-link/"]}
                patch_event(row)
                self.assertEqual("manual:" + event_id, row["id"])
                self.assertEqual("2026-08-09T00:00:00Z", row["firstSeen"])
                self.assertEqual(wanted.get("artists", ["Existing curated performer"]), row["artists"])
                for key, value in wanted.items():
                    if key != "legacyEventPaths":
                        self.assertEqual(value, row[key], key)
                self.assertIn("/event/older-link/", row["legacyEventPaths"])
                before = copy.deepcopy(row)
                patch_event(row)
                self.assertEqual(before, row)

    def test_other_shows_and_eli_spelling_are_untouched(self):
        for row in [
            {"id": "another-issac-show", "artists": ["Issac Mansfield"], "city": "Winter Haven"},
            {"id": "manual:parris-chariz-dallas-2026-10-11", "advertisedBilling": ["Parris Chariz", "Eli Montanna"]},
        ]:
            before = copy.deepcopy(row)
            patch_event(row)
            self.assertEqual(before, row)

    def test_sold_out_remains_scheduled_and_ticketed(self):
        row = {"id": "manual:mike-malagies-florida-takeover-miami-2026", "ticketUrl": "https://example.com/tickets"}
        patch_event(row)
        self.assertTrue(row["soldOut"])
        self.assertEqual("sold_out", row["ticketAvailability"])
        self.assertEqual("scheduled", row["status"])
        self.assertEqual("https://example.com/tickets", row["ticketUrl"])

    def test_sold_out_card_retains_category_and_does_not_duplicate_badge(self):
        card = '<article><div class="event-badges"><span class="badge badge-gold">Concert</span></div></article>'
        result = sold_out_badge(card)
        self.assertIn('>Sold Out</span>', result)
        self.assertIn('>Concert</span>', result)
        self.assertEqual(result, sold_out_badge(result))
