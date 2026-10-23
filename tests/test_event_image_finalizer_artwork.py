import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from finalize_live_event_images import patch_html_page, repair_fallbacks_in_block


class EventArtworkPreservationTests(unittest.TestCase):
    def markup(self, artist, src, image_class="event-artwork"):
        return (f'<img class="{image_class}" src="{src}">'
                f'<p class="artist-line"><a>{artist}</a></p>')

    def test_verified_flyers_survive_card_and_detail_finalization(self):
        for artist in ("yumiya!", "Rare of Breed"):
            for src in ("/assets/events/official-flyer.jpg", "/assets/optimized/abc-w800.webp"):
                with self.subTest(artist=artist, src=src):
                    markup = self.markup(artist, src)
                    self.assertEqual((markup, False), repair_fallbacks_in_block(markup))
                    with tempfile.TemporaryDirectory() as temp:
                        page = pathlib.Path(temp) / "event" / "show" / "index.html"
                        page.parent.mkdir(parents=True)
                        page.write_text(f"<html><head></head><body>{markup}</body></html>")
                        self.assertEqual((0, 0), patch_html_page(page, set()))
                        self.assertIn(markup, page.read_text())

    def test_generic_or_artist_images_still_get_known_good_portraits(self):
        for artist, slug in (("yumiya!", "yumiya"), ("Rare of Breed", "rare-of-breed")):
            for src, css in (("/assets/event-fallback.webp", "event-artwork"),
                             ("/old-portrait.jpg", "artist-photo")):
                with self.subTest(artist=artist, src=src):
                    updated, changed = repair_fallbacks_in_block(self.markup(artist, src, css))
                    self.assertTrue(changed)
                    self.assertIn(f"/assets/artists/{slug}-primary.jpg?v=", updated)
                    self.assertIn('data-kc-lock-primary="1"', updated)


if __name__ == "__main__":
    unittest.main()
