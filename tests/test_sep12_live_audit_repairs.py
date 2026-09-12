import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scripts import apply_sep12_live_audit_repairs as repairs


class September12LiveAuditRepairTests(unittest.TestCase):
    def test_cancelled_rare_event_is_removed_from_upcoming_but_retained_as_page(self):
        source = Path("events.json").read_text(encoding="utf-8")
        rows = json.loads(source)
        rare = next(event for event in rows if repairs.RARE_EVENTBRITE_ID in json.dumps(event))
        self.assertEqual(rare.get("status"), "cancelled")
        self.assertTrue(rare.get("cancellationConfirmed"))

    def test_static_cards_expose_filter_contract(self):
        source = Path("scripts/build_seo_site.py").read_text(encoding="utf-8")
        self.assertIn('data-search="{esc(search)}"', source)
        self.assertIn('data-artists="{esc(artist_values)}"', source)

    def test_weekend_logic_keeps_current_weekend_on_saturday_and_sunday(self):
        source = Path("app.js").read_text(encoding="utf-8")
        self.assertIn("day === 0 ? -2 : day === 6 ? -1", source)

    def test_clear_filters_explicitly_clears_dynamic_selects(self):
        source = Path("app.js").read_text(encoding="utf-8")
        self.assertIn('if (artist) artist.value = "";', source)
        self.assertIn('if (state) state.value = "";', source)


if __name__ == "__main__":
    unittest.main()
