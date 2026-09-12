from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pin_verified_event_artwork import VERIFIED_ARTWORK  # noqa: E402


class VerifiedEventArtworkTests(unittest.TestCase):
    def test_genesis_and_sep11_events_have_pinned_show_artwork(self):
        self.assertEqual(len(VERIFIED_ARTWORK), 14)
        self.assertEqual(
            VERIFIED_ARTWORK["The Genesis Show – All Women's CHH Event"][1],
            "assets/events/genesis-show-2026-all-women-v3.jpg",
        )
        self.assertEqual(
            VERIFIED_ARTWORK["Fountain Fest WV 2026"][1],
            "assets/events/fountain-fest-wv-2026.svg",
        )

    def test_all_local_pinned_artwork_exists(self):
        missing = []
        for _title, (_date, image) in VERIFIED_ARTWORK.items():
            if image.startswith(("http://", "https://")):
                continue
            if not (ROOT / image).is_file():
                missing.append(image)
        self.assertEqual(missing, [])

    def test_runtime_preserves_real_event_artwork(self):
        for relative in ("assets/event-image-repair.js", "assets/event-image-repair-kc2100.js"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("if (lockedPrimary || explicitEventArtwork)", text)
            self.assertNotIn("explicitEventArtwork && !forcePrimary", text)

    def test_client_guard_covers_every_pinned_event(self):
        text = (ROOT / "assets/verified-event-artwork-guard.js").read_text(encoding="utf-8")
        expected_slugs = [
            "the-genesis-show-all-women-s-chh-event-2026-09-19-roswell-9d321d",
            "flavor-fest-2026-saturday-concerts-2026-11-07-tampa-cf7fac",
            "future-legacy-hip-hop-showcase-2026-10-04-nashville-4bd33c",
            "miles-minnick-and-cj-emulous-at-zion-ultra-lounge-2026-12-05-chandler-bfff69",
            "fountain-fest-wv-2026-2026-09-18-martinsburg-1cd64d",
            "mission-and-special-guests-2026-10-17-sacramento-15909d",
            "boxyard-saturdaze-2026-10-10-durham-7853b4",
            "mayia-at-the-nc-state-fair-2026-10-17-raleigh-1c07ad",
            "syatp-concert-2026-09-23-sierra-vista-121b78",
            "live-loud-2026-10-07-chico-1b6570",
            "teen-club-kickoff-back-to-school-concert-2026-10-12-turlock-c869fd",
            "the-kickback-2026-11-14-grand-prairie-ce6c40",
            "alex-zurdo-zona-zero-2026-10-18-san-juan-6d6263",
            "jay-kalyl-desde-antes-tour-2026-10-03-rockville-centre-8ea3e4",
        ]
        for slug in expected_slugs:
            self.assertIn(slug, text)

    def test_final_seo_stage_reapplies_verified_artwork(self):
        text = (ROOT / "scripts/finalize_seo_indexing.py").read_text(encoding="utf-8")
        self.assertIn("from pin_verified_event_artwork import pin_site", text)
        self.assertIn("pin_site(root)", text)


if __name__ == "__main__":
    unittest.main()
