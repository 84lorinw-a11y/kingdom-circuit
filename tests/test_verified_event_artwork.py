from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pin_verified_event_artwork import VERIFIED_ARTWORK  # noqa: E402


class VerifiedEventArtworkTests(unittest.TestCase):
    def test_pinned_artwork_uses_source_authorized_media(self):
        self.assertEqual(len(VERIFIED_ARTWORK), 13)
        self.assertEqual(
            VERIFIED_ARTWORK["The Genesis Show – All Women's CHH Event"][1],
            "assets/events/genesis-show-2026-all-women-v3.jpg",
        )
        self.assertIn("fountainfestwv.com", VERIFIED_ARTWORK["Fountain Fest WV 2026"][1])
        for _title, (_date, image) in VERIFIED_ARTWORK.items():
            self.assertNotIn("fountain-fest-wv-2026.svg", image)
            self.assertNotIn("mission-friends-sacramento-2026.svg", image)
            self.assertNotIn("mayia-boxyard-saturdaze-2026.svg", image)
            self.assertNotIn("mayia-nc-state-fair-2026.svg", image)
            self.assertNotIn("cj-emulous-kickback-2026.svg", image)
            self.assertNotIn("alex-zurdo-zona-zero-2026.svg", image)
            self.assertNotIn("jay-kalyl-desde-antes-2026.svg", image)
            self.assertNotIn("miles-cj-zion-ultra-2026.svg", image)

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

    def test_client_guard_has_no_fabricated_flyers_and_is_idempotent(self):
        text = (ROOT / "assets/verified-event-artwork-guard.js").read_text(encoding="utf-8")
        self.assertIn("if (img.getAttribute(\"src\") !== src)", text)
        self.assertIn("idempotent", text)
        for asset in (
            "miles-cj-zion-ultra-2026.svg",
            "fountain-fest-wv-2026.svg",
            "mission-friends-sacramento-2026.svg",
            "mayia-boxyard-saturdaze-2026.svg",
            "mayia-nc-state-fair-2026.svg",
            "cj-emulous-kickback-2026.svg",
            "alex-zurdo-zona-zero-2026.svg",
            "jay-kalyl-desde-antes-2026.svg",
        ):
            self.assertNotIn(asset, text)

    def test_final_seo_stage_runs_complete_closeout_after_pins(self):
        text = (ROOT / "scripts/finalize_seo_indexing.py").read_text(encoding="utf-8")
        self.assertIn("from pin_verified_event_artwork import pin_site", text)
        self.assertIn("from finalize_sep12_complete_closeout import apply_closeout", text)
        self.assertLess(text.index("pin_site(root)"), text.index("apply_closeout(root, events)"))


if __name__ == "__main__":
    unittest.main()
