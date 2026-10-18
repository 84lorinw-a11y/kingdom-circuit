import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from finalize_sold_out_artwork import transform


class SoldOutArtworkTests(unittest.TestCase):
    def test_reviewed_event_has_visible_and_accessible_status_on_both_card_layouts(self):
        for card, media, copy in [('event-card', 'event-media', 'event-content'),
                                  ('kc-discovery-show', 'kc-teaser-image', 'kc-teaser-copy')]:
            text = f'<html><head></head><body><article class="{card}"><a class="{media}" href="/event/full/" aria-hidden="true"><img src="official.jpg"></a><div class="{copy}"><h3>Concert</h3></div></article></body></html>'
            result = transform(text, '/', {'/event/full/': {}})
            self.assertIn('kc-sold-out-banner', result)
            self.assertIn('kc-sold-out-label', result)
            self.assertIn('src="official.jpg"', result)
            self.assertEqual(result, transform(result, '/', {'/event/full/': {}}))
            self.assertEqual(text, transform(text, '/', {'/event/different/': {}}))

    def test_detail_page_keeps_flyer_and_adds_registration_status(self):
        text = '<html><head></head><body><div class="event-detail-media"><img src="official.jpg"></div><div class="event-detail-copy"><h1>Concert</h1></div></body></html>'
        result = transform(text, '/event/full/', {'/event/full/': {}})
        self.assertIn('Registration is closed.', result)
        self.assertIn('src="official.jpg"', result)
        self.assertEqual(result, transform(result, '/event/full/', {'/event/full/': {}}))
        self.assertEqual(text, transform(text, '/event/open/', {'/event/full/': {}}))
