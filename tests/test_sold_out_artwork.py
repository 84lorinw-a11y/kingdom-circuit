import sys
import json
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from finalize_sold_out_artwork import transform, BADGE, LINK
from mobile_discovery import Document


class SoldOutArtworkTests(unittest.TestCase):
    def test_sold_out_label_preserves_calendar_two_row_layout_and_repairs_old_markup(self):
        for legacy in ('', BADGE):
            text = '<html><head><link rel="stylesheet" href="/assets/sold-out-artwork.css?v=2"></head><body><article class="event-card"><a class="event-media" href="/event/full/"><img src="official.jpg"></a><div class="event-content">' + legacy + '<div class="event-main"><div class="event-badges"><span class="badge badge-gold">Concert</span></div><h3>Reach1</h3><p class="artist-line">EGR</p><dl>Date, venue and city</dl></div><div class="event-footer"><a>Official details</a></div></div></article></body></html>'
            result = transform(text, '/', {'/event/full/':{}})
            doc = Document(result)
            content = doc.one(lambda n:n.has('event-content'))
            self.assertEqual([n.attrs['class'] for n in content.children], ['event-main','event-footer'])
            badges = doc.one(lambda n:n.has('event-badges'))
            self.assertIn(BADGE, doc.raw(badges))
            self.assertEqual(result.count(BADGE), 1)
            self.assertEqual(result.count(LINK), 1)
            self.assertIn('Date, venue and city', result)
            self.assertEqual(result, transform(result, '/', {'/event/full/':{}}))

    def test_future_weekly_cards_keep_sold_out_artwork_and_accessible_label(self):
        card = '<article class="kc-discovery-show"><a class="kc-teaser-image" href="/event/full/"><img src="original.jpg"></a><div class="kc-teaser-copy">A &amp; B</div></article>'
        payload = json.dumps([{'date':'2026-10-24', 'html':card}]).replace('<', '\\u003c')
        text = '<head></head><script id="kc-weekly-shows" type="application/json">' + payload + '</script>'
        result = transform(text, '/', {'/event/full/':{}})
        updated = json.loads(result.split('type="application/json">')[1].split('</script>')[0])[0]['html']
        self.assertIn('kc-sold-out-banner', updated)
        self.assertIn('kc-sold-out-label', updated)
        self.assertIn('src="original.jpg"', updated)
        self.assertIn('A &amp; B', updated)
        self.assertIn('assets/sold-out-artwork.css', result)
        self.assertEqual(result, transform(result, '/', {'/event/full/':{}}))

    def test_reviewed_event_has_visible_and_accessible_status_on_both_card_layouts(self):
        for card, media, copy in [('event-card', 'event-media', 'event-content'),
                                  ('kc-discovery-show', 'kc-teaser-image', 'kc-teaser-copy')]:
            text = f'<html><head></head><body><article class="{card}"><a class="{media}" href="/event/full/" aria-hidden="true"><img src="official.jpg"></a><div class="{copy}"><div class="event-main"><div class="event-badges"></div><h3>Concert</h3></div></div></article></body></html>'
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
