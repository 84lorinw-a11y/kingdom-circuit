"""Regression contracts for reviewed November 7 Google-facing corrections."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import organization_identity as org
import url_continuity as uc
from apply_verified_show_information import enrich
from show_information_model import normalize
from show_information import schema_blocks

ROOT = Path(__file__).resolve().parents[1]


class GoogleDataRepairs(unittest.TestCase):
    def test_social_profiles_apply_only_to_our_organization_and_are_idempotent(self):
        other = {'@type': 'Organization', 'name': 'Promoter', 'url': 'https://promoter.test/'}
        artist = {'@type': 'MusicGroup', 'url': org.ORIGIN + '/artists/kb/', 'sameAs': ['https://artist.test/']}
        payload = {'@graph': [{'@type': 'Organization', 'url': org.ORIGIN + '/', 'sameAs': ['https://existing.test/']}, other, artist]}
        source = '<script type="application/ld+json">' + json.dumps(payload) + '</script>'
        updated = org.transform(source)
        graph = schema_blocks(updated)[0][1]['@graph']
        self.assertEqual(graph[0]['sameAs'], ['https://existing.test/', *org.SOCIALS])
        self.assertEqual(graph[1:], [other, artist])
        self.assertEqual(org.transform(updated), updated)

    def test_reviewed_prices_bind_to_exact_ticket_destination_and_prior_label(self):
        pins = json.loads((ROOT / 'config/verified-show-prices.json').read_text())['events']
        for pin in pins:
            with self.subTest(event=pin['id']):
                correction = pin['corrections'][0]
                event = {k: pin[k] for k in ('id', 'startDate', 'city', 'state', 'country')}
                event.update(venue=pin['expectedVenue'], **correction['expected'])
                changed = enrich(event, [pin])
                self.assertEqual(changed['price'], correction['facts']['price'])
                self.assertEqual(enrich(changed, [pin]), changed)
                offer = normalize(changed)['offer']
                self.assertIsNotNone(offer)
                self.assertEqual(offer['price'], float(changed['price']['amount']))
                self.assertEqual(offer['priceCurrency'], 'USD')
                self.assertNotIn('availability', offer)
                self.assertIsNone(normalize(dict(changed, admission='private'))['offer'])
                moved = normalize(dict(changed, ticketUrl='https://www.eventbrite.com/e/new-tickets-123456789'))
                self.assertNotIn('price', moved['offer'] or {})
                self.assertEqual(moved['priceLabel'], 'Price not confirmed for the current ticket link.')
                for updates in ({'price': 'New price + unknown fees'}, {'ticketUrl': 'https://new.test/tickets'}):
                    newer = dict(event, **updates)
                    self.assertEqual(enrich(newer, [pin]), newer)

    def test_reviewed_archive_calendar_filters_and_does_not_restore_removed_artist(self):
        state = uc.empty_state()
        event = dict(id='a', title='Example', startDate='2026-08-28', artists=['Braille'], state='OH')
        state['events']['a'] = dict(path='/event/example/', sourceIds=[], event=event)
        state['events']['b'] = dict(path='/event/other/', sourceIds=[], event=dict(event, id='b', state='TX'))
        rules = {'retainedCalendars': [dict(path='/artists/braille/ohio/', title='Braille Ohio archive', artist='Braille', state='OH'), dict(path='/shows/august-2026/', title='August archive', month='2026-08'), dict(path='/artists/removed/ohio/', title='Removed', artist='Removed', state='OH')]}
        uc.remember_reviewed_calendars(state, rules, {'braille'})
        self.assertEqual(state['pages']['/artists/braille/ohio/']['eventPaths'], ['/event/example/'])
        self.assertEqual(len(state['pages']['/shows/august-2026/']['eventPaths']), 2)
        self.assertNotIn('/artists/removed/ohio/', state['pages'])

    def test_reviewed_merges_preserve_full_billing_and_different_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for filename in [uc.STATE_FILE, uc.RULES_FILE, 'event-history.json', 'config/manual-events.json']:
                target = root / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / filename).read_bytes())
            for filename in uc.FEEDS: uc.save(root / filename, [])
            uc.prepare(root)
            state = uc.load(root / uc.WORK_FILE, {})
            self.assertIn('CJ Emulous', state['events']['official:12ef07b891bbeeefbcb1']['event']['artists'])
            for alias in ['official:0ac72030904117f28951', 'official:29f19c38ff406820fa64', 'bandsintown:108771984', 'bandsintown:108772413', 'bandsintown:108772493']:
                self.assertNotIn(alias, state['events'])
            self.assertIn('manual:808-beezy-bandsintown-108772434', state['events'])
            self.assertIn('manual:808-beezy-bandsintown-108772413', state['events'])

    def test_ambiguous_archives_show_their_own_source_clock_without_public_offer(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            event = dict(title='Archived show', startDate='2026-09-18', startTime='09:45', artists=['808 BEEZY'])
            uc.restore_event(site, '/event/archive/', event, '2026-11-07', session_review=True)
            text = uc.target_file(site, '/event/archive/').read_text()
            self.assertIn('09:45', text)
            self.assertIn('separate performances has not been verified', text)
            self.assertFalse(uc.PageFacts(text).schemas)


if __name__ == '__main__': unittest.main()
