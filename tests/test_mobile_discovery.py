import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mobile_discovery as preview


CARD = '<article class="event-card" data-event-card data-state="TX"><a href="/event/example/">Example</a></article>'
HEAD = '<head><meta name="robots" content="index,follow"><title>Texas concerts</title><link rel="canonical" href="https://kingdomcircuit.com/shows/texas/"></head>'
LOCATION = (HEAD + '<body><main><section class="page-hero seo-location-hero"><h1>Texas shows</h1></section>'
            '<section class="seo-location-strip"><p>Featured artists</p><a href="/artists/a/">Artist</a></section>'
            '<section class="seo-location-strip"><p>Browse cities</p><a href="/shows/houston-texas/">Houston</a></section>'
            '<section class="calendar"><h2>Upcoming</h2><div class="event-grid">' + CARD + '</div></section>'
            '<section class="past-shows-archive" data-past-shows-archive><details><summary>Past shows</summary><article class="past-show-row">Past</article></details></section></main></body>')
STATES = [{'name': 'Texas', 'href': '/shows/texas/', 'relative': 'shows/texas/index.html', 'count': 1, 'code': 'TX'},
          {'name': 'New Mexico', 'href': '/shows/new-mexico/', 'relative': 'shows/new-mexico/index.html', 'count': 0, 'code': ''}]


class MobileSeoPreviewTests(unittest.TestCase):
    def test_shows_come_before_artists_without_changing_cards_or_metadata(self):
        output = preview.transform(Path('shows/texas/index.html'), LOCATION.encode(), STATES).decode()
        self.assertLess(output.index(CARD), output.index('id="state-artists"'))
        self.assertIn(HEAD.removesuffix('</head>'), output)
        self.assertIn('id="past-shows"', output)
        self.assertIn('id="upcoming-shows"', output)
        self.assertIn('Browse cities', output)
        self.assertEqual(output.count(CARD), 1)

    def test_home_finder_before_mission_and_calendar_preserves_content(self):
        home = (HEAD + '<body><section class="kc-rd-home-hero"><p class="eyebrow">Tagline</p><h1>Title</h1>'
                '<p class="mission-statement">Mission</p><div class="kc-rd-home-stats">Counts</div></section>'
                '<section class="calendar"><div class="event-grid">' + CARD + '</div></section></body>')
        output = preview.transform(Path('index.html'), home.encode(), STATES).decode()
        self.assertLess(output.index('id="browse-states"'), output.index('mission-statement'))
        self.assertLess(output.index('id="browse-states"'), output.index(CARD))
        self.assertEqual(output.count('<h1>'), 1)
        self.assertIn('New Mexico', output)
        self.assertIn('Check for dates', output)

    def test_state_directory_is_static_not_a_javascript_only_select(self):
        html = preview.finder(STATES)
        self.assertIn('<a href="/shows/texas/">', html)
        self.assertIn('<a href="/shows/new-mexico/">', html)
        self.assertIn('data-state-picker hidden', html)

    def test_all_shows_keeps_top_discovery_compact_and_preserves_filter_form(self):
        form = '<form data-event-filters><select data-state-filter><option>All states</option></select></form>'
        page = HEAD + '<body><section class="page-hero"><h1>Shows</h1></section><section class="calendar">' + form + '<div class="event-grid">' + CARD + '</div></section><section data-permanent-state-navigation><a href="/shows/texas/">Texas</a></section></body>'
        output = preview.transform(Path('shows/index.html'), page.encode(), STATES).decode()
        self.assertIn('kc-state-finder-compact', output)
        self.assertIn(form, output)
        self.assertLess(output.index('id="browse-states"'), output.index(form))
        self.assertNotIn('data-state-picker', output)

    def test_non_target_pages_and_data_are_byte_identical(self):
        for relative in ('events.json', 'artists/a/index.html', 'event/example/index.html', 'assets/photo.jpg', 'app.js'):
            self.assertEqual(preview.transform(Path(relative), LOCATION.encode(), STATES), LOCATION.encode())

    def test_rejects_second_overlay_instead_of_duplicating_navigation(self):
        result = preview.transform(Path('shows/texas/index.html'), LOCATION.encode(), STATES)
        with self.assertRaises(ValueError):
            preview.transform(Path('shows/texas/index.html'), result, STATES)

    def test_empty_location_retains_archive_and_never_invents_shows(self):
        empty = LOCATION.replace(CARD, '').replace('Upcoming</h2>', 'Stay tuned for more shows</h2>')
        result = preview.transform(Path('shows/texas/index.html'), empty.encode(), STATES).decode()
        self.assertNotIn('data-event-card', result)
        self.assertIn('Stay tuned for more shows', result)
        self.assertIn('past-show-row', result)

    def test_upcoming_anchor_does_not_create_new_page_urls(self):
        output = preview.transform(Path('shows/texas/index.html'), LOCATION.encode(), STATES).decode()
        self.assertIn('href="#upcoming-shows"', output)
        self.assertNotIn('/texas-chh-shows/', output)


if __name__ == '__main__':
    unittest.main()
