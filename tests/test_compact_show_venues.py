"""Compact artist venues must agree with the same normalized show facts."""
from html import escape
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from show_information import listing_transform
from show_information_model import normalize


class CompactShowVenueTests(unittest.TestCase):
    path = '/event/rwg-tour-2026-2026-11-10-lewiston-b4fad8/'

    def record(self, **changes):
        return normalize({'id': 'bandsintown:109085594', 'title': 'RWG TOUR 2026',
                          'venue': 'RWG TOUR 2026', 'startDate': '2026-11-10',
                          'startTime': '08:15', 'city': 'Lewiston', 'state': 'ME',
                          'country': 'US', **changes})

    def compact(self, venue='RWG TOUR 2026', status=''):
        aria = f'Tue, Nov 10, 2026 - 8:15 AM, Lewiston, ME, {venue} | RWG TOUR 2026'
        if status:
            aria += ' | ' + status
        return (f'<a class="kc-rd-show-row" href="{self.path}" aria-label="{escape(aria, quote=True)}">'
                '<span class="kc-rd-show-date"><span>NOV</span><strong>10</strong></span>'
                '<span class="kc-rd-show-place"><strong>Lewiston, ME</strong>'
                f'<span class="kc-rd-show-venue">{escape(venue)}</span>'
                '<span class="kc-rd-event-title">RWG TOUR 2026</span>'
                + (f'<span class="kc-rd-event-status">{escape(status)}</span>' if status else '')
                + '</span><span class="kc-rd-chevron" aria-hidden="true">›</span></a>')

    def next_show(self, venue='RWG TOUR 2026', time='8:15 AM'):
        return (f'<a class="kc-rd-next kc-rd-next-show" href="{self.path}">'
                '<span><span class="kc-rd-next-kicker">Next show · NOV 10</span>'
                '<strong class="kc-rd-next-place">Lewiston, ME</strong>'
                f'<span class="kc-rd-next-venue">{escape(venue)} · {time}</span>'
                '<span class="kc-rd-event-title">RWG TOUR 2026</span></span></a>')

    def patch(self, text, row=None):
        return listing_transform(text, {'paths': {self.path: row or self.record()}})

    def test_unknown_venue_changes_only_its_span_and_accessible_venue_not_title(self):
        original = self.compact()
        expected = original.replace('ME, RWG TOUR 2026 |', 'ME, Venue not confirmed |').replace(
            '<span class="kc-rd-show-venue">RWG TOUR 2026</span>',
            '<span class="kc-rd-show-venue">Venue not confirmed</span>')
        result = self.patch(original)
        self.assertEqual(result, expected)
        self.assertEqual(self.patch(result), result)

    def test_next_show_preserves_existing_clock_and_every_other_byte(self):
        original = self.next_show()
        expected = original.replace('class="kc-rd-next-venue">RWG TOUR 2026 · 8:15 AM',
                                    'class="kc-rd-next-venue">Venue not confirmed · 8:15 AM')
        result = self.patch(original)
        self.assertEqual(result, expected)
        self.assertEqual(self.patch(result), result)

    def test_confirmed_venues_including_middots_and_private_status_stay_unchanged(self):
        for venue in ('North Canton Chapel', 'Auditorium · West Wing'):
            with self.subTest(venue=venue):
                row = self.record(venue=venue, private=True, address='Private street', postalCode='99999')
                original = self.compact(venue, 'Private Event — not open to the public') + self.next_show(venue)
                self.assertEqual(self.patch(original, row), original)
                self.assertNotIn('Private street', original)
                self.assertNotIn('99999', original)
        unknown_private = self.record(private=True, address='Private street', postalCode='99999')
        changed = self.patch(self.compact(status='Private Event — not open to the public'), unknown_private)
        self.assertIn('Private Event — not open to the public', changed)
        self.assertIn('Venue not confirmed', changed)
        self.assertNotIn('Private street', changed)

    def test_escaped_venue_labels_and_out_of_catalog_archive_rows_are_safe(self):
        row = self.record(venue='Chapel <West> & Hall')
        changed = self.patch(self.compact(), row)
        self.assertIn('Chapel &lt;West&gt; &amp; Hall', changed)
        self.assertNotIn('<West>', changed)
        self.assertEqual(self.patch(changed, row), changed)
        archived = self.compact().replace(self.path, '/event/past-show/')
        self.assertEqual(self.patch(archived), archived)


if __name__ == '__main__':
    unittest.main()
