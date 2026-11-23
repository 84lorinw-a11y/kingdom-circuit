"""Regressions for conflicting published titles and delayed browser rendering."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mobile_discovery import Document
import show_title_consistency as titles


class ShowTitleConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.path = '/event/amplify-original-url/'
        self.expected = titles.expected_titles({self.path: {'title': 'AMPLIFY', 'private': True}})

    def check(self, source, page='/artists/808-beezy/'):
        return titles.page_checks(Document(source), page, self.expected)

    def test_original_private_card_detail_and_artist_disagreement_is_detected(self):
        card = f'<h3><a href="{self.path}">AMPLIFY — Private Event</a></h3>'
        detail = '<h1>808 BEEZY — AMPLIFY</h1>'
        row = (f'<a class="kc-rd-show-row" href="{self.path}">'
               '<span class="kc-rd-event-title">808 BEEZY — AMPLIFY</span></a>')
        for source, page in ((card, '/shows/'), (detail, self.path), (row, '/artists/808-beezy/')):
            with self.subTest(page=page):
                errors = self.check(source, page)['errors']
                self.assertEqual(len(errors), 1)
                self.assertEqual(errors[0]['event'], self.path)
                self.assertEqual(errors[0]['expected'], 'AMPLIFY (Private Event)')

    def test_consistent_surfaces_accept_generic_links_and_longer_seo_titles(self):
        source = (f'<title>AMPLIFY (Private Event) in Ohio | Kingdom Circuit</title>'
                  f'<h1>AMPLIFY (Private Event)</h1>'
                  f'<h3><a href="{self.path}">AMPLIFY (Private Event)</a></h3>'
                  f'<a href="{self.path}">Event details</a>'
                  f'<a href="https://other.example{self.path}">Unrelated show</a>'
                  f'<a class="kc-rd-next-show" href="{self.path}"><span>Next show</span>'
                  '<span class="kc-rd-event-title">AMPLIFY (Private Event)</span></a>')
        result = self.check(source, self.path)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['counts'], {'eventHeading': 1, 'listingTitle': 1, 'artistScheduleTitle': 1})

    def test_stale_inert_homepage_inventory_is_detected_before_rollover(self):
        data = json.dumps([{'html': f'<h3><a href="{self.path}">Old name</a></h3>'}])
        result = self.check(f'<script type="application/json" id="kc-weekly-shows">{data}</script>', '/')
        self.assertEqual(result['errors'][0]['surface'], 'homepageRolloverTitle')
        self.assertEqual(result['counts'], {'homepageRolloverTitle': 1})

    def test_catalog_and_client_config_cannot_restore_an_old_title(self):
        catalog = {'shows': [{'path': self.path, 'name': 'Old name'}]}
        self.assertEqual(titles.catalog_checks(catalog, self.expected)['errors'][0]['surface'], 'catalogTitle')
        source = ('<h1>AMPLIFY (Private Event)</h1><script type="application/json" '
                  'id="kc-fan-config">{"show":"Old name"}</script>')
        self.assertEqual(self.check(source, self.path)['errors'][0]['surface'], 'eventClientTitle')

    def test_html_escaping_and_layout_whitespace_are_not_false_mismatches(self):
        expected = {'/event/sample/': 'Artist & Friends'}
        source = '<h3><a href="https://kingdomcircuit.com/event/sample/?from=home">Artist &amp;\n Friends</a></h3>'
        self.assertEqual(titles.page_checks(Document(source), '/', expected)['errors'], [])

    def test_missing_artist_title_and_duplicate_event_heading_fail(self):
        row = f'<a class="kc-rd-show-row" href="{self.path}"><span>Ohio</span></a>'
        self.assertEqual(self.check(row)['errors'][0]['kind'], 'artist_show_title_count')
        self.assertEqual(self.check('<h1>One</h1><h1>Two</h1>', self.path)['errors'][0]['kind'], 'show_title_heading_count')

    def test_legacy_link_identity_is_resolved_without_renaming_the_url(self):
        source = '<h3><a href="/event/old-url/">AMPLIFY (Private Event)</a></h3>'
        self.assertEqual(titles.page_checks(Document(source), '/shows/', self.expected,
                         {'/event/old-url/': self.path})['errors'], [])


if __name__ == '__main__':
    unittest.main()
