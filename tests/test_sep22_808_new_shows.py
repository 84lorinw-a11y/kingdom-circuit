import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_verified_event_overrides as overrides
import build_site


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class BeezyNewShowsHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = load("events.json")
        cls.supplemental = load("supplemental-events.json")

    def test_known_tour_dates_keep_their_original_discovery_date(self):
        events = json.loads(json.dumps(self.events))
        supplemental = json.loads(json.dumps(self.supplemental))
        overrides.apply_historical_discovery_dates(events, supplemental)
        combined = [*events, *supplemental]
        known = {
            str(event.get("id") or ""): event
            for event in combined
            if str(event.get("id") or "") in overrides.KNOWN_808_BEEZY_EVENT_IDS
        }
        self.assertEqual(overrides.KNOWN_808_BEEZY_EVENT_IDS, set(known))

        for event in known.values():
            self.assertEqual(
                overrides.KNOWN_808_BEEZY_FIRST_SEEN,
                event.get("firstSeen"),
            )
            self.assertFalse(build_site.is_recent(event, date(2026, 9, 22)))

    def test_late_override_is_scoped_and_idempotent(self):
        target_id = next(iter(overrides.KNOWN_808_BEEZY_EVENT_IDS))
        events = json.loads(json.dumps(self.events))
        target = next(event for event in events if event.get("id") == target_id)
        target["firstSeen"] = "2026-09-21T21:43:48Z"
        future_new_show = {
            "id": "manual:808-beezy-future-genuinely-new-show",
            "title": "808 BEEZY — A Future New Show",
            "startDate": "2027-03-01",
            "startTime": "19:00",
            "venue": "Test Venue",
            "city": "Nashville",
            "state": "TN",
            "artists": ["808 BEEZY"],
            "headliner": "808 BEEZY",
            "firstSeen": "2026-09-22T12:00:00Z",
        }
        events.append(future_new_show)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "events.json").write_text(json.dumps(events), encoding="utf-8")
            (root / "supplemental-events.json").write_text(
                json.dumps(self.supplemental), encoding="utf-8"
            )

            overrides.apply(root)
            first_events = (root / "events.json").read_text(encoding="utf-8")
            first_supplemental = (
                root / "supplemental-events.json"
            ).read_text(encoding="utf-8")
            overrides.apply(root)

            self.assertEqual(
                first_events, (root / "events.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                first_supplemental,
                (root / "supplemental-events.json").read_text(encoding="utf-8"),
            )
            published = json.loads(first_events)
            corrected = next(event for event in published if event.get("id") == target_id)
            future = next(
                event for event in published
                if event.get("id") == future_new_show["id"]
            )
            self.assertEqual(
                overrides.KNOWN_808_BEEZY_FIRST_SEEN,
                corrected["firstSeen"],
            )
            self.assertEqual(future_new_show["firstSeen"], future["firstSeen"])

    def test_generated_site_hides_808_only_from_new_shows(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory) / "source"
            output = Path(directory) / "site"
            (temp_root / "config").mkdir(parents=True)
            (temp_root / "assets").mkdir()
            shutil.copy2(ROOT / "config" / "artists.json", temp_root / "config")
            shutil.copy2(ROOT / "styles.css", temp_root)
            shutil.copy2(ROOT / "app.js", temp_root)
            shutil.copy2(ROOT / "run-status.json", temp_root)
            (temp_root / "assets" / "logo.png").write_bytes(b"logo")
            (temp_root / "assets" / "favicon.svg").write_text(
                "<svg></svg>", encoding="utf-8"
            )
            (temp_root / "assets" / "event-fallback.webp").write_bytes(b"fallback")

            events = json.loads(json.dumps(self.events))
            supplemental = json.loads(json.dumps(self.supplemental))
            overrides.apply_historical_discovery_dates(events, supplemental)
            (temp_root / "events.json").write_text(
                json.dumps(events), encoding="utf-8"
            )

            original_root = build_site.ROOT
            build_site.ROOT = temp_root
            try:
                build_site.generate_site(output, today=date(2026, 9, 22))
            finally:
                build_site.ROOT = original_root
            new_shows = (output / "new-shows" / "index.html").read_text(
                encoding="utf-8"
            )
            all_shows = (output / "shows" / "index.html").read_text(
                encoding="utf-8"
            )
            artist = (output / "artists" / "808-beezy" / "index.html").read_text(
                encoding="utf-8"
            )

            self.assertNotIn("808 BEEZY", new_shows)
            self.assertIn("808 BEEZY", all_shows)
            self.assertIn("808 BEEZY", artist)


if __name__ == "__main__":
    unittest.main()
