"""Rendered cleanup must not invent event merges after source reconciliation."""
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import apply_public_audit_repairs as repair
import build_seo_site as builder
import national_discovery as discovery
import verify_public_audit as verifier


class RenderedEventIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.site = Path(temporary.name)
        self.manual = {
            'id': 'manual:reviewed-tour-stop', 'title': 'Reviewed Tour',
            'startDate': '2027-02-16', 'endDate': '2027-02-16',
            'city': 'Memphis', 'state': 'TN', 'venue': 'Minglewood Hall',
            'artists': ['Example Artist'], 'status': 'scheduled',
        }
        self.provider = dict(self.manual, id='provider:new-tour-stop', startTime='19:00')

    def card(self, event):
        path = self.site / builder.event_path(event).strip('/') / 'index.html'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('<main>Event detail</main>')
        return builder.event_card(event, [])

    def cleaned(self, cards):
        counters = Counter()
        text = repair.repair_cards(''.join(cards), self.site, Path('shows/index.html'), counters)
        return repair.CARD_RE.findall(text), counters

    def test_primary_cards_expose_known_and_unknown_time_without_guessing(self):
        for event, clock in ((self.manual, ''), (self.provider, '19:00')):
            with self.subTest(clock=clock):
                opening = self.card(event).split('>', 1)[0]
                self.assertEqual(clock, repair.get_attr(opening, 'data-start-time'))
        self.assertNotIn('startTime', self.manual)

    def test_all_shows_cards_supply_every_unmerged_artist_schedule_row(self):
        # The production failure had an unknown reviewed time and a new provider
        # time. Cleanup dropped the base card but the artist schedule kept its URL.
        cards, counters = self.cleaned([self.card(self.manual), self.card(self.provider)])
        hrefs = [builder.event_path(event) for event in (self.manual, self.provider)]
        schedule = ('<article data-kc-rd-artist-profile><section class="kc-rd-profile-shows">'
                    + ''.join(f'<a class="kc-rd-show-row" href="{href}">Show</a>' for href in hrefs)
                    + '</section></article>')
        context = {'records': discovery.card_records(''.join(cards))}
        result = discovery.artist_details(schedule, context)
        self.assertEqual(hrefs, [row['href'] for row in discovery.card_records(result)])
        self.assertEqual(0, counters['duplicateEventCardsRemoved'])
        # The independent missing-card assertion remains strict.
        with self.assertRaisesRegex(AssertionError, 'lacks matching full event cards'):
            discovery.artist_details(schedule, {'records': context['records'][:1]})

    def test_distinct_ids_with_identical_known_or_unknown_times_remain_separate(self):
        for clock in ('', '19:00'):
            with self.subTest(clock=clock):
                first = dict(self.manual, startTime=clock)
                second = dict(first, id='unreviewed:separate-performance')
                cards, counters = self.cleaned([self.card(first), self.card(second)])
                self.assertEqual(2, len(cards))
                self.assertEqual(0, counters['duplicateEventCardsRemoved'])

    def test_repeated_internal_event_url_collapses_despite_metadata_variations(self):
        first = self.card(self.manual)
        path = builder.event_path(self.manual)
        second = self.card(dict(self.manual, startTime='19:00')).replace(
            f'href="{path}"', f'href="https://kingdomcircuit.com{path}?from=artist#details"')
        cards, counters = self.cleaned([first, second])
        self.assertEqual(1, len(cards))
        self.assertEqual(1, counters['duplicateEventCardsRemoved'])
        audit = verifier.Audit()
        verifier.verify_counts(Path('shows/index.html'), first + second, audit)
        self.assertTrue(any('duplicate visible event cards' in failure for failure in audit.failures))

    def test_external_event_links_use_metadata_fallback_instead_of_url_identity(self):
        path = builder.event_path(self.manual)
        first = self.card(self.manual).replace(path, 'https://tickets.example/event/first/')
        second = first.replace('/event/first/', '/event/second/')
        cards, _ = self.cleaned([first, second])
        self.assertEqual(1, len(cards))

    def test_fallback_does_not_merge_distinct_times_or_incomplete_cards(self):
        first = self.card(self.manual).replace(builder.event_path(self.manual), '#details')
        later = self.card(self.provider).replace(builder.event_path(self.provider), '#details')
        cards, _ = self.cleaned([first, later])
        self.assertEqual(2, len(cards))
        incomplete = '<article class="event-card" data-event-card><h3>Unidentified show</h3></article>'
        cards, _ = self.cleaned([incomplete, incomplete])
        self.assertEqual(2, len(cards))


if __name__ == '__main__':
    unittest.main()
