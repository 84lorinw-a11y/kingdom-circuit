import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import apply_trnscnd_submission as trnscnd
import apply_rock_the_pines as rock
import build_seo_site as builder
import verify_public_audit as audit_module


class September24RegressionTests(unittest.TestCase):
    def test_submission_refresh_preserves_later_reviewed_artist_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            reviewed = dict(trnscnd.NEW_ARTISTS[0], youtubeProfile="https://www.youtube.com/@future-reviewed-channel")
            path.write_text(json.dumps([reviewed]))
            with patch.object(trnscnd, "UPDATES_FILE", path), patch.object(trnscnd.subprocess, "run"):
                trnscnd.patch_artist_registry()
            self.assertEqual(reviewed["youtubeProfile"], json.loads(path.read_text())[0]["youtubeProfile"])

    def test_new_festival_survives_repeat_refresh_without_guessing_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            for relative in ("config/manual-events.json", "events.json", "supplemental-events.json"):
                (root / relative).write_text("[]")
            rock.apply(root)
            once = (root / "events.json").read_text()
            rock.apply(root)
            self.assertEqual(once, (root / "events.json").read_text())
            event = json.loads(once)[0]
            self.assertEqual(["LJ THE MESSENGER", "DEON"], event["artists"])
            self.assertEqual("2027-04-24", event["startDate"])
            self.assertFalse(event.get("startTime"))
            self.assertFalse(event.get("price"))
            card = builder.event_card(event, [{"name": "DEON"}])
            self.assertIn("<span>LJ THE MESSENGER</span>", card)
            self.assertNotIn("/artists/lj-the-messenger/", card)
            self.assertIn('/artists/deon/', card)

    def jimmy_cards(self):
        cards = []
        for key in ("jimmy-rock-worship-wawa-miami-2026", "jimmy-rock-rave-worship-centennial-2026", "boise-invasion-2026", "jimmy-rock-rave-worship-dallas-2026"):
            event = dict(audit_module.requested_events.UPSERTS[key], id="manual:" + key)
            cards.append(builder.event_card(dict(event, image="assets/optimized/poster.webp"), []))
        return "".join(cards)

    def test_new_jimmy_show_can_use_a_real_artist_photo(self):
        html = self.jimmy_cards() + '<article class="event-card" data-event-card><img class="artist-photo" src="/assets/optimized/jimmy-portrait.webp"></article>'
        result = audit_module.Audit()
        audit_module.verify_jimmy_artwork(html, result)
        self.assertEqual([], result.failures)

    def test_reviewed_jimmy_posters_still_cannot_regress_to_portraits(self):
        result = audit_module.Audit()
        audit_module.verify_jimmy_artwork(self.jimmy_cards().replace('class="event-artwork"', 'class="artist-photo"', 1), result)
        self.assertTrue(any("verified poster missing" in failure for failure in result.failures))


if __name__ == "__main__":
    unittest.main()
