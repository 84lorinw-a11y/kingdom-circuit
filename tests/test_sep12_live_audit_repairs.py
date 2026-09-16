import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scripts import apply_sep12_live_audit_repairs as repairs


class September12LiveAuditRepairTests(unittest.TestCase):
    @staticmethod
    def _authoritative_rare() -> dict:
        rows = json.loads(Path("config/manual-events.json").read_text(encoding="utf-8"))
        return next(event for event in rows if repairs._is_rare(event))

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    def test_full_scan_restores_one_authoritative_cancelled_rare_record(self):
        authoritative = self._authoritative_rare()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.json"
            supplemental = root / "supplemental-events.json"
            manual = root / "config" / "manual-events.json"
            self._write(events, [{"id": "other", "startDate": "2026-10-17"}])
            self._write(supplemental, [authoritative])
            self._write(manual, [authoritative])

            with (
                patch.object(repairs, "EVENTS_FILE", events),
                patch.object(repairs, "SUPPLEMENTAL_EVENTS_FILE", supplemental),
                patch.object(repairs, "MANUAL_EVENTS_FILE", manual),
                patch.object(repairs, "EVENT_FILES", (events, supplemental, manual)),
            ):
                report = repairs.apply()
                repairs.check()
                second_report = repairs.apply()
                repairs.check()

            restored_rows = json.loads(events.read_text(encoding="utf-8"))
            matches = [event for event in restored_rows if repairs._is_rare(event)]
            self.assertEqual(1, report["rareRecordsRestored"])
            self.assertEqual(0, second_report["rareRecordsRestored"])
            self.assertEqual(1, len(matches))
            self.assertEqual(f"manual:{repairs.RARE_CANONICAL_ID}", matches[0]["id"])
            self.assertEqual("cancelled", matches[0]["status"])
            self.assertTrue(matches[0]["cancellationConfirmed"])
            self.assertEqual("cancelled", matches[0]["ticketAvailability"])
            self.assertEqual(repairs.RARE_CANCEL_URL, matches[0]["officialUrl"])
            self.assertEqual(authoritative["image"], matches[0]["image"])

    def test_rediscovered_rare_duplicates_collapse_without_restoring_another(self):
        authoritative = self._authoritative_rare()
        discovered = {
            **authoritative,
            "id": "eventbrite:rediscovered-rare-of-breed",
            "status": "scheduled",
            "cancellationConfirmed": False,
            "ticketAvailability": "available",
        }
        rows = [dict(authoritative), discovered]

        canonical, collapsed = repairs.consolidate_rare(rows)

        self.assertEqual(1, collapsed)
        self.assertEqual(1, len([event for event in rows if repairs._is_rare(event)]))
        self.assertIs(canonical, rows[0])

    def test_unverified_manual_record_cannot_be_used_for_restoration(self):
        unverified = {**self._authoritative_rare(), "cancellationConfirmed": False}
        with self.assertRaises(SystemExit):
            repairs.authoritative_rare([unverified])

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
