import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_echo_nights_official as echo_nights  # noqa: E402


class EchoNightsOfficialArtworkTests(unittest.TestCase):
    def test_full_resolution_ticketspice_gallery_poster_is_locked(self):
        image = ROOT / echo_nights.IMAGE
        payload = image.read_bytes()

        self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual((1054, 1492), struct.unpack(">II", payload[16:24]))
        self.assertEqual(
            "f5c33b0bc686decdd307d8f7b0af34822944bcecbc880acca4e91612caca79b1",
            hashlib.sha256(payload).hexdigest(),
        )
        self.assertIn("promo%20poster", echo_nights.IMAGE_SOURCE_URL)

    def test_all_runtime_sources_use_the_portrait_poster(self):
        for filename in echo_nights.SOURCE_FILES:
            rows = json.loads((ROOT / filename).read_text(encoding="utf-8"))
            matches = [row for row in rows if row.get("id") == echo_nights.EVENT_ID]
            self.assertEqual(1, len(matches), filename)
            event = matches[0]
            self.assertEqual(echo_nights.IMAGE, event.get("image"), filename)
            self.assertEqual("event_artwork", event.get("imageType"), filename)
            self.assertTrue(event.get("imageOverride"), filename)
            self.assertEqual(echo_nights.IMAGE_SOURCE_URL, event.get("imageSourceUrl"), filename)

    def test_calendar_card_and_event_detail_are_pinned_to_same_poster(self):
        card = f'''<article class="event-card"><img class="artist-photo" src="/wrong.jpg"><h3>{echo_nights.TITLE}</h3></article>'''
        detail = f'''<!doctype html><h1>{echo_nights.TITLE}</h1>
        <div class="event-detail-media"><a class="event-image-enlarge" href="/wrong.jpg"><img src="/wrong.jpg"></a></div>
        <script type="application/ld+json">{{"@type":"MusicEvent","name":"{echo_nights.TITLE}","image":["/wrong.jpg"]}}</script>'''

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            event_dir = root / "event" / "echo-nights-26"
            event_dir.mkdir(parents=True)
            (root / "index.html").write_text(card, encoding="utf-8")
            (event_dir / "index.html").write_text(detail, encoding="utf-8")

            self.assertEqual(2, echo_nights.patch_html(root))

            card_output = (root / "index.html").read_text(encoding="utf-8")
            detail_output = (event_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn(echo_nights.PUBLIC_IMAGE, card_output)
            self.assertIn('class="event-artwork"', card_output)
            self.assertIn('width="1054"', card_output)
            self.assertIn('height="1492"', card_output)
            self.assertIn(f'href="{echo_nights.PUBLIC_IMAGE}"', detail_output)
            self.assertIn(echo_nights.ABSOLUTE_IMAGE, detail_output)

    def test_public_artifact_pin_does_not_restore_private_source_fields(self):
        private_values = {field: "private" for field in echo_nights.PRIVATE_FIELDS}
        event = {"id": echo_nights.EVENT_ID, **private_values}

        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp) / "_site"
            site.mkdir()
            (site / "seo-build-manifest.json").write_text("{}", encoding="utf-8")
            for filename in echo_nights.SOURCE_FILES:
                (site / filename).write_text(json.dumps([event]), encoding="utf-8")

            self.assertEqual(2, echo_nights.enforce_json(site))

            for filename in echo_nights.SOURCE_FILES:
                output = json.loads((site / filename).read_text(encoding="utf-8"))[0]
                self.assertEqual(echo_nights.IMAGE, output.get("image"), filename)
                for field in echo_nights.PRIVATE_FIELDS:
                    self.assertNotIn(field, output, f"{filename}: {field}")

if __name__ == "__main__":
    unittest.main()
