"""Acceptance must notice omissions even when every generated view agrees."""
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_seo_site import artist_path, event_path


class PublicationInventoryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('publication_inventory'),
                             'Independent publication inventory validator is missing')
        self.inventory = importlib.import_module('publication_inventory')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.site = self.repo / '_site'
        self.day = '2026-11-09'
        self.artist = {'name': 'Alpha Artist', 'aliases': ['Alpha'], 'enabled': True}
        self.event = {'id': 'manual:alpha-show', 'title': 'Alpha Live',
                      'startDate': self.day, 'endDate': self.day,
                      'artists': ['Alpha Artist'], 'headliner': 'Alpha Artist',
                      'city': 'Dallas', 'state': 'TX', 'country': 'US',
                      'venue': 'Main Hall', 'status': 'scheduled'}
        self.write('config/artists.json', [self.artist])
        self.write('config/owner-reviewed-roster.json', {'artists': [self.artist], 'removedArtists': []})
        self.write('config/event-identity-overrides.json', {})
        self.write('config/url-continuity.json', {'events': {}, 'redirects': {}, 'pages': {}})
        self.write('events.json', [self.event])
        self.write('supplemental-events.json', [])
        self.catalog = {'asOf': self.day, 'shows': [self.show(self.event)],
                        'artists': {artist_path(self.artist['name']): [event_path(self.event)]}}
        self.save_catalog()
        self.page(event_path(self.event))

    def write(self, relative, value):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def show(self, event, path=None):
        return {'path': path or event_path(event), 'name': event['title'],
                'date': event['startDate'], 'end': event.get('endDate') or event['startDate']}

    def page(self, path):
        target = self.site / path.strip('/') / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('<html><body>Published event</body></html>')

    def save_catalog(self):
        self.write('_site/assets/fan-show-catalog.json', self.catalog)

    def verify(self):
        return self.inventory.verify(self.site, self.day, repo=self.repo)

    def assert_error(self, fragment):
        self.assertTrue(any(fragment in error for error in self.verify()['errors']), fragment)

    def test_missing_catalog_row_and_page_still_fails_from_source(self):
        self.catalog['shows'] = []
        self.catalog['artists'][artist_path(self.artist['name'])] = []
        self.save_catalog()
        (self.site / event_path(self.event).strip('/') / 'index.html').unlink()
        self.assert_error('missing from catalog')

    def test_valid_inventory_is_read_only(self):
        before = {p.relative_to(self.repo): p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}
        result = self.verify()
        self.assertEqual([], result['errors'])
        self.assertEqual(1, result['expectedShows'])
        self.assertEqual(1, result['expectedArtists'])
        self.assertEqual(before, {p.relative_to(self.repo): p.read_bytes() for p in self.repo.rglob('*') if p.is_file()})

    def test_new_source_show_requires_publication_without_fixed_count(self):
        new = dict(self.event, id='manual:new-show', title='New Show', startDate='2026-11-10', endDate='2026-11-10')
        self.write('events.json', [self.event, new])
        self.assert_error('missing from catalog')
        self.catalog['shows'].append(self.show(new))
        self.catalog['artists'][artist_path(self.artist['name'])].append(event_path(new))
        self.save_catalog()
        self.page(event_path(new))
        self.assertEqual([], self.verify()['errors'])

    def test_date_rollover_allows_completed_show_to_leave_current_catalog(self):
        self.day = '2026-11-10'
        self.catalog.update(asOf=self.day, shows=[], artists={artist_path(self.artist['name']): []})
        self.save_catalog()
        self.assertEqual([], self.verify()['errors'])

    def test_multi_day_show_stays_current_until_its_end_date(self):
        self.event.update(startDate='2026-11-08', endDate='2026-11-10')
        self.write('events.json', [self.event])
        self.catalog['shows'] = []
        self.catalog['artists'] = {artist_path(self.artist['name']): []}
        self.save_catalog()
        self.assert_error('missing from catalog')

    def test_retained_canonical_url_and_source_alias_are_one_show(self):
        keep = '/event/original-published-alpha/'
        alias = dict(self.event, id='provider:alpha', title='Corrected Alpha Title')
        self.write('events.json', [self.event, alias])
        self.write('_url-continuity-state.json', {'events': {self.event['id']: {
            'path': keep, 'sourceIds': [alias['id']], 'event': self.event}}, 'redirects': {event_path(alias): keep}})
        self.catalog['shows'] = [self.show(self.event, keep)]
        self.catalog['artists'] = {artist_path(self.artist['name']): [keep]}
        self.save_catalog()
        self.page(keep)
        self.assertEqual([], self.verify()['errors'])
        self.assertEqual(1, self.verify()['expectedShows'])

    def test_reviewed_identity_rule_resolves_path_without_new_persisted_state(self):
        keep = '/event/reviewed-alpha/'
        self.write('config/event-identity-overrides.json', {'merges': [{
            'keepId': self.event['id'], 'keepPath': keep, 'aliasIds': ['provider:alpha'], 'aliasPaths': []}]})
        self.catalog['shows'] = [self.show(self.event, keep)]
        self.catalog['artists'] = {artist_path(self.artist['name']): [keep]}
        self.save_catalog()
        self.page(keep)
        self.assertEqual([], self.verify()['errors'])

    def test_artist_alias_maps_to_roster_profile(self):
        self.event['artists'] = ['Alpha']
        self.write('events.json', [self.event])
        self.assertEqual([], self.verify()['errors'])

    def test_missing_artist_membership_fails_even_when_show_exists(self):
        self.catalog['artists'][artist_path(self.artist['name'])] = []
        self.save_catalog()
        self.assert_error('artist membership')

    def test_removed_or_extra_roster_profile_fails(self):
        self.catalog['artists'] = {'/artists/unapproved/': []}
        self.save_catalog()
        self.assert_error('missing artist profile')
        self.assert_error('unexpected artist profile')

    def test_canadian_private_and_unknown_location_bookings_remain_required(self):
        for extra in ({'country': 'CA', 'state': 'ON', 'city': 'Toronto'},
                      {'status': 'private'}, {'locationUnconfirmed': True, 'city': '', 'state': ''}):
            with self.subTest(extra=extra):
                self.write('events.json', [dict(self.event, **extra)])
                self.catalog['shows'] = []
                self.catalog['artists'][artist_path(self.artist['name'])] = []
                self.save_catalog()
                self.assert_error('missing from catalog')

    def test_inactive_foreign_and_owner_removed_shows_are_not_current_inventory(self):
        rows = [dict(self.event, id='inactive:'+status, status=status) for status in ('cancelled', 'canceled', 'postponed', 'merged')]
        rows += [dict(self.event, id='foreign:show', country='GB', state=''),
                 dict(self.event, id='removed:show', artists=['Removed Artist'], headliner='Removed Artist'),
                 dict(self.event, id='held:show', startDate='2026-11-14', endDate='2026-11-14',
                      officialUrl='https://www.cjemulous.com/event-details/the-kickback-w-cj-emulous')]
        self.write('config/owner-reviewed-roster.json', {'artists': [self.artist], 'removedArtists': ['Removed Artist']})
        self.write('events.json', [self.event, *rows])
        self.assertEqual([], self.verify()['errors'])

    def test_missing_detail_page_fails_with_catalog_intact(self):
        (self.site / event_path(self.event).strip('/') / 'index.html').unlink()
        self.assert_error('missing event page')

    def test_duplicate_catalog_rows_and_memberships_are_rejected(self):
        self.catalog['shows'] *= 2
        self.catalog['artists'][artist_path(self.artist['name'])] *= 2
        self.save_catalog()
        self.assert_error('duplicate catalog')
        self.assert_error('duplicate artist membership')

    def test_catalog_date_must_match_source(self):
        self.catalog['shows'][0]['date'] = '2026-11-10'
        self.save_catalog()
        self.assert_error('source date mismatch')

    def test_missing_source_input_fails_closed(self):
        (self.repo / 'events.json').unlink()
        self.assert_error('source inventory')

    def test_source_facts_ignore_consistent_artifact_feed_and_schema_changes(self):
        self.assertTrue(callable(getattr(self.inventory, 'source_records', None)),
                        'Source-fact projection must be independent of generated feeds')
        self.event.update(startTime='19:30', timezone='America/Chicago', address='100 Source Street')
        self.write('events.json', [self.event])
        self.write('_site/events.json', [dict(self.event, startTime='21:00', address='999 Wrong Street')])
        records = self.inventory.source_records(self.repo, self.day)
        self.assertEqual('2026-11-09T19:30:00-06:00', records[event_path(self.event)]['schemaStartDate'])
        self.assertEqual('100 Source Street', records[event_path(self.event)]['address'])

    def test_source_facts_preserve_cross_feed_bill_and_missing_facts(self):
        self.assertTrue(callable(getattr(self.inventory, 'source_records', None)),
                        'Source-fact projection must preserve merged source details')
        self.write('supplemental-events.json', [dict(self.event, artists=['Guest Artist'],
                                                    image='assets/known-image.webp')])
        record = self.inventory.source_records(self.repo, self.day)[event_path(self.event)]
        self.assertEqual(['Alpha Artist', 'Guest Artist'], record['artists'])
        self.assertEqual('assets/known-image.webp', record['image'])


if __name__ == '__main__':
    unittest.main()
