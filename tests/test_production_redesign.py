from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_production_redesign as production
import catalog_removals as catalog


def approved_filter():
    path = ROOT / "tests/fixtures/approved_redesign_new_shows.py"
    spec = importlib.util.spec_from_file_location("approved_filter_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProductionNewShowsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        boundary = patch.object(catalog, 'REVIEW_FILE', pathlib.Path(temp.name) / 'missing-review.json', create=True)
        boundary.start()
        self.addCleanup(boundary.stop)
        self.redesign = approved_filter()
        production.configure_new_show_keys(self.redesign)
        # Captured production card: preserve its canonical URL and unconfirmed text.
        self.card = (ROOT / "tests/fixtures/1k-phew-unconfirmed-card.html.txt").read_text().strip()
        self.event = {
            "id": "official:023c040d4ea33e120949",
            "title": "1K Phew — Live performance",
            "startDate": "2026-11-21",
            "firstSeen": "2026-11-03T18:56:47Z",
            "city": "",
            "state": "",
            "locationUnconfirmed": True,
        }

    def render(self, card=None, event=None, today=dt.date(2026, 11, 7)):
        keys = self.redesign.recent_event_keys([event or self.event], today)
        document = '<p data-results-count>1 show</p>' + (card or self.card)
        return self.redesign.transform_new_shows(document, keys)

    def test_recent_unconfirmed_show_keeps_its_exact_card_and_canonical(self):
        self.assertEqual(self.render(), '<p data-results-count>1 show</p>' + self.card)

    def test_pinned_seo_location_placeholder_also_keeps_recent_show(self):
        card = self.card.replace("Location not confirmed", "Location to be announced")
        self.assertEqual(self.render(card), '<p data-results-count>1 show</p>' + card)

    def test_location_normalization_does_not_extend_discovery_window(self):
        # November 3 is seven days old on November 10 and must be excluded.
        self.assertEqual(self.render(today=dt.date(2026, 11, 10)), '<p data-results-count>0 shows</p>')

    def test_real_city_still_requires_matching_source_city(self):
        card = self.card.replace("Location not confirmed", "Dallas, TX").replace('data-state=""', 'data-state="TX"')
        self.assertEqual(self.render(card), '<p data-results-count>0 shows</p>')
        event = dict(self.event, city="Dallas", state="TX")
        self.assertEqual(self.render(card, event), '<p data-results-count>1 show</p>' + card)

    def test_placeholder_with_state_is_not_reinterpreted_as_unknown_location(self):
        card = self.card.replace('data-state=""', 'data-state="TX"')
        self.assertEqual(self.render(card), '<p data-results-count>0 shows</p>')

    def test_placeholder_without_explicit_state_is_not_reinterpreted(self):
        card = self.card.replace('data-state=""', '')
        self.assertEqual(self.render(card), '<p data-results-count>0 shows</p>')

    def test_other_location_text_is_not_blank_city(self):
        for location in ("TBA", "Unknown", "Location not confirmed, TX", "Location not confirmed nearby"):
            with self.subTest(location=location):
                self.assertEqual(self.render(self.card.replace("Location not confirmed", location)), '<p data-results-count>0 shows</p>')

    def test_unknown_location_does_not_override_title_or_show_date(self):
        for event in (dict(self.event, title="Other show"), dict(self.event, startDate="2026-11-22")):
            with self.subTest(event=event):
                self.assertEqual(self.render(event=event), '<p data-results-count>0 shows</p>')


class ProductionRedesignCommandTests(unittest.TestCase):
    def run_wrapper(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/apply_production_redesign.py"), *map(str, args)],
            capture_output=True, text=True, check=False,
        )

    def test_command_loads_pinned_module_and_preserves_its_arguments_and_asset_path(self):
        # Use the exact offline filter with a small file-I/O entry point. Production
        # supplies the whole approved module after the separate pinned checkout.
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            script = base / "approved.py"
            script.write_text((ROOT / "tests/fixtures/approved_redesign_new_shows.py").read_text() + '''
import argparse
import json
import pathlib

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=pathlib.Path)
    parser.add_argument("--production", action="store_true", required=True)
    parser.add_argument("--source-events", action="append", type=pathlib.Path, required=True)
    parser.add_argument("--source-history", type=pathlib.Path, required=True)
    args = parser.parse_args()
    events = [event for path in args.source_events for event in json.loads(path.read_text())]
    today = dt.date.fromisoformat(args.source_history.read_text())
    card = pathlib.Path(__file__).with_name("card.html").read_text()
    args.site.write_text(transform_new_shows(card, recent_event_keys(events, today)))
''')
            card = (ROOT / "tests/fixtures/1k-phew-unconfirmed-card.html.txt").read_text()
            (base / "card.html").write_text(card)
            primary = base / "events.json"
            primary.write_text('[]')
            supplemental = base / "supplemental.json"
            supplemental.write_text('[{"title":"1K Phew — Live performance","startDate":"2026-11-21","firstSeen":"2026-11-03T18:56:47Z","city":""}]')
            history = base / "history.txt"
            history.write_text("2026-11-07")
            output = base / "generated page.html"
            result = self.run_wrapper(script, output, "--production", "--source-events", primary, "--source-events", supplemental, "--source-history", history)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists(), "The approved module main must execute")
            self.assertEqual(output.read_text(), card)

    def test_incompatible_pinned_interface_fails_before_main(self):
        complete = (ROOT / "tests/fixtures/approved_redesign_new_shows.py").read_text()
        for missing in ("card_source_key", "clean_text", "normalized_key", "main"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                base = pathlib.Path(directory)
                marker = base / "should-not-run"
                script = base / "approved.py"
                script.write_text(complete + f'\nimport pathlib\ndef main():\n    pathlib.Path({str(marker)!r}).write_text("ran")\n' + f'\ndel {missing}\n')
                result = self.run_wrapper(script, base)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Approved redesign interface", result.stderr)
                self.assertIn(missing, result.stderr)
                self.assertFalse(marker.exists())

    def test_command_propagates_approved_main_failure(self):
        complete = (ROOT / "tests/fixtures/approved_redesign_new_shows.py").read_text()
        with tempfile.TemporaryDirectory() as directory:
            script = pathlib.Path(directory) / "approved.py"
            script.write_text(complete + '\ndef main():\n    return 7\n')
            result = self.run_wrapper(script, directory)
            self.assertEqual(result.returncode, 7)


if __name__ == "__main__":
    unittest.main()
