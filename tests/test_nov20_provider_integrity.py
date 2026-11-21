"""Exact reviewed provider collisions preserve other events and raw history."""
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import catalog_removals as catalog
import url_continuity as continuity
import add_past_show_archives as archives
import build_seo_site as seo
from show_information_model import normalize as show_information

KEEP_ID = 'bandsintown:109174921'
ALIAS_ID = 'official:22266e20021b7ab47403'
KEEP_PATH = '/event/mike-teezy-at-690-jonestown-rd-2026-12-13-winston-salem-681652/'
ALIAS_PATH = '/event/mike-teezy-690-jonestown-rd-2026-12-13-winston-salem-f56fa7/'
FIRST_SEEN = '2026-11-19T11:45:04Z'
WRONG_ID = 'bandsintown:1040895160'


class ProviderIntegrityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        boundary = patch.object(catalog, 'REVIEW_FILE', self.root / 'config/review-held-events.json')
        boundary.start()
        self.addCleanup(boundary.stop)
        self.accepted = {
            'id': KEEP_ID, 'title': 'Mike Teezy at 690 Jonestown Rd',
            'startDate': '2026-12-13', 'startTime': '16:00', 'timezone': '',
            'venue': '690 Jonestown Rd', 'address': '690 Jonestown Rd',
            'city': 'Winston-Salem', 'state': 'NC', 'country': 'US',
            'artists': ['Mike Teezy'], 'headliner': 'Mike Teezy',
            'status': 'scheduled', 'image': 'assets/artists/mike-teezy-saved.png',
            'officialUrl': 'https://www.bandsintown.com/e/109174921',
            'ticketUrl': 'https://www.bandsintown.com/e/109174921',
        }
        self.alias = dict(self.accepted, id=ALIAS_ID, title='Mike Teezy @ 690 Jonestown Rd',
                          startTime='21:00', endDate='2026-12-14',
                          firstSeen='2026-11-20T11:17:11Z',
                          officialUrl='https://music.apple.com/us/concerts/artist/517774271')
        self.bad = {
            'id': WRONG_ID, 'title': "GRITS at Poor David's Pub",
            'startDate': '2026-12-16', 'startTime': '20:00',
            'venue': "Poor David's Pub", 'city': 'Dallas', 'state': 'TX',
            'country': 'US', 'artists': ['GRITS'], 'headliner': 'GRITS',
            'status': 'scheduled', 'officialUrl': 'https://www.bandsintown.com/e/1040895160',
        }
        self.other = dict(self.bad, id='official:genuine-grits', venue='Concert Hall',
                          officialUrl='https://www.instagram.com/grits/')

    def install_identity(self):
        rules = json.loads((ROOT / continuity.RULES_FILE).read_text())
        matches = [r for r in rules['merges'] if r['keepId'] == KEEP_ID]
        self.assertEqual(1, len(matches))
        self.assertIs(True, matches[0]['identityOnly'])
        self.assertEqual([ALIAS_ID], matches[0]['aliasIds'])
        continuity.save(self.root / continuity.RULES_FILE, {'merges': matches})
        state = continuity.empty_state()
        for event, path in ((self.accepted, KEEP_PATH), (self.alias, ALIAS_PATH)):
            state['events'][event['id']] = {
                'path': path, 'sourceIds': [],
                'event': {k: v for k, v in event.items() if k in continuity.SNAPSHOT_FIELDS},
            }
        continuity.save(self.root / continuity.STATE_FILE, state)
        continuity.save(self.root / 'event-history.json', {'events': [
            {'event': self.accepted, 'firstSeenOnCalendar': FIRST_SEEN}, {'event': self.alias}]})

    def test_wrong_identity_is_exactly_dated_and_uses_exact_provider_links(self):
        rows = [self.bad, dict(self.bad, id='manual:' + WRONG_ID),
                dict(self.bad, id='imported', officialUrl='', bandsintownEventId=1040895160),
                dict(self.bad, id='imported', officialUrl='https://bandsintown.com/t/1040895160?ref=calendar'),
                dict(self.bad, id='imported', officialUrl='https://www.prekindle.com/event/79173-grits-band-holiday-show-dallas')]
        for row in rows:
            with self.subTest(row=row):
                self.assertTrue(catalog.removed_event(row))
                self.assertFalse(catalog.removed_event(dict(row, startDate='2027-12-16')))
        for url in ('https://bandsintown.com/e/10408951600',
                    'https://bandsintown.com.attacker.example/e/1040895160',
                    'https://user:password@bandsintown.com/e/1040895160',
                    'https://bandsintown.com:8443/e/1040895160',
                    'https://prekindle.com/event/791730-grits-band-holiday-show-dallas',
                    'https://prekindle.com.attacker.example/event/79173-grits-band-holiday-show-dallas'):
            self.assertFalse(catalog.removed_event(dict(self.bad, id='unrelated', officialUrl=url)))
        self.assertFalse(catalog.removed_event(self.other))

    def test_filters_public_copies_without_changing_history_or_artist_flags(self):
        for name in ('events.json', 'supplemental-events.json', 'config/manual-events.json'):
            continuity.save(self.root / name, [self.bad, self.other, self.alias])
        history = {'events': [{'event': e} for e in (self.bad, self.other, self.alias)]}
        continuity.save(self.root / 'event-history.json', history)
        continuity.save(self.root / 'config/artists.json', [{'name': 'GRITS', 'enabled': True, 'monitor': True}])
        preserved = {n: (self.root / n).read_bytes() for n in ('event-history.json', 'config/artists.json')}
        catalog.apply(self.root)
        for name in ('events.json', 'supplemental-events.json', 'config/manual-events.json'):
            rows = continuity.load(self.root / name, [])
            self.assertEqual([self.other['id'], ALIAS_ID], [e['id'] for e in rows])
            self.assertEqual(self.other, rows[0])
        for name, original in preserved.items():
            self.assertEqual(original, (self.root / name).read_bytes())
        once = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*.json')}
        catalog.apply(self.root)
        self.assertEqual(once, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*.json')})

    def test_false_grits_route_is_retired_and_never_restored_as_chh_archive(self):
        history = {'events': [{'event': e, 'observedOnOrAfterEventDate': True} for e in (self.bad, self.other)]}
        continuity.save(self.root / 'event-history.json', history)
        continuity.save(self.root / 'config/artists.json', [{'name': 'GRITS'}])
        state = continuity.empty_state()
        site = self.root / '_site'
        for event in (self.bad, self.other):
            path = continuity.generated_path(event)
            state['events'][event['id']] = {'path': path, 'sourceIds': [], 'event': event}
            file = continuity.target_file(site, path)
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('<html><body>Existing concert page</body></html>')
        continuity.save(self.root / continuity.STATE_FILE, state)
        continuity.finalize(self.root, site, '2027-01-01')
        self.assertFalse(continuity.target_file(site, continuity.generated_path(self.bad)).exists())
        self.assertTrue(continuity.target_file(site, continuity.generated_path(self.other)).exists())
        with patch.object(archives, 'catalog_date', return_value=dt.date(2027, 1, 1)):
            selected, _ = archives.load_events(self.root)
        self.assertEqual([self.other['id']], [e['id'] for e in selected])
        self.assertEqual(history, continuity.load(self.root / 'event-history.json', {}))

    def test_clock_projection_preserves_status_earlier_discovery_and_other_events(self):
        for event in (self.accepted, self.alias, dict(self.alias, id='manual:' + ALIAS_ID)):
            before = copy.deepcopy(event)
            row = catalog.public_event(event)
            self.assertEqual(('16:00', '19:00', '2026-12-13', 'America/New_York'),
                             (row['startTime'], row['endTime'], row['endDate'], row['timezone']))
            self.assertEqual('2026-12-13T16:00:00-05:00', row['startDateTime'])
            self.assertEqual('2026-12-13T19:00:00-05:00', row['endDateTime'])
            self.assertEqual(FIRST_SEEN, row['firstSeen'])
            self.assertEqual(event, before)
        early = dict(self.alias, firstSeen='2026-11-01T00:00:00Z', status='postponed')
        self.assertEqual(early['firstSeen'], catalog.public_event(early)['firstSeen'])
        self.assertEqual('postponed', catalog.public_event(early)['status'])
        for row in (dict(self.alias, id=ALIAS_ID + '0'), dict(self.alias, startDate='2027-12-13'), self.other):
            self.assertEqual(row, catalog.public_event(row))

    def test_exact_alias_replays_from_current_feeds_archive_and_registry(self):
        self.install_identity()
        for mode in ('both', 'archive', 'registry'):
            with self.subTest(mode=mode):
                continuity.save(self.root / 'events.json', [self.alias])
                continuity.save(self.root / 'supplemental-events.json', [self.accepted] if mode == 'both' else [])
                if mode == 'registry':
                    continuity.save(self.root / 'event-history.json', {'events': [{'event': self.alias}]})
                history = (self.root / 'event-history.json').read_bytes()
                continuity.prepare(self.root)
                rows = [row for name in continuity.FEEDS for row in continuity.load(self.root / name, [])]
                self.assertEqual({KEEP_ID}, {r['id'] for r in rows})
                for row in rows:
                    self.assertEqual(('16:00', '19:00', '2026-12-13', FIRST_SEEN),
                                     (row['startTime'], row['endTime'], row['endDate'], row['firstSeen']))
                    self.assertEqual(self.accepted['officialUrl'], row['officialUrl'])
                    self.assertIn(ALIAS_ID, row['mergedFromIds'])
                state = continuity.load(self.root / continuity.WORK_FILE, {})
                self.assertNotIn(ALIAS_ID, state['events'])
                self.assertEqual(KEEP_PATH, state['events'][KEEP_ID]['path'])
                self.assertEqual(KEEP_PATH, state['redirects'][ALIAS_PATH])
                self.assertEqual(history, (self.root / 'event-history.json').read_bytes())

    def issac_event(self):
        return {
            'id': 'bandsintown:109183179', 'title': 'Issac Mansfield at THE GALLERY AT YAM',
            'startDate': '2027-02-06', 'startTime': '19:00',
            'venue': 'THE GALLERY AT YAM', 'address': '9850 Walnut Hill Ln suite 427',
            'city': 'North East Dallas', 'state': 'TX', 'country': 'US',
            'artists': ['Issac Mansfield'], 'headliner': 'Issac Mansfield',
            'status': 'scheduled', 'firstSeen': '2026-11-19T11:45:04Z',
            'officialUrl': 'https://www.bandsintown.com/e/109183179?came_from=267',
        }

    def test_dallas_projection_is_exact_and_preserves_source_facts(self):
        event = self.issac_event()
        for row in (event, dict(event, id='manual:' + event['id'], status='postponed')):
            before = copy.deepcopy(row)
            projected = catalog.public_event(row)
            self.assertEqual(dict(row, city='Dallas'), projected)
            self.assertEqual(before, row)
            self.assertEqual(projected, catalog.public_event(projected))
        for change in ({'id': event['id'] + '0'}, {'startDate': '2027-02-07'},
                       {'venue': 'A different venue'}, {'state': 'AR'}, {'country': 'CA'},
                       {'city': 'Plano'}):
            other = dict(event, **change)
            self.assertEqual(other, catalog.public_event(other))

    def test_dallas_feed_city_coverage_schema_and_canonical_stay_consistent(self):
        event = self.issac_event()
        path = '/event/issac-mansfield-at-the-gallery-at-yam-2027-02-06-dallas-7fb117/'
        state = continuity.empty_state()
        state['events'][event['id']] = {
            'path': path, 'sourceIds': [], 'event': dict(event, city='Dallas'),
        }
        continuity.save(self.root / continuity.STATE_FILE, state)
        for name in continuity.FEEDS:
            continuity.save(self.root / name, [event])
        continuity.save(self.root / 'event-history.json', {'events': [{'event': event}]})
        history = (self.root / 'event-history.json').read_bytes()
        continuity.prepare(self.root)
        for name in continuity.FEEDS:
            rows = continuity.load(self.root / name, [])
            self.assertEqual(1, len(rows))
            self.assertEqual('Dallas', rows[0]['city'])
            self.assertEqual(event['officialUrl'], rows[0]['officialUrl'])
        rendered = seo.merge_events(continuity.load(self.root / 'events.json', []), [])
        self.assertEqual('/shows/dallas-texas/', seo.city_path(rendered[0]['city'], rendered[0]['state']))
        self.assertEqual('Dallas', seo.event_schema(rendered[0])['location']['address']['addressLocality'])
        self.assertEqual('Dallas', show_information(event)['venueLocality'])
        self.assertEqual(path, seo.event_path(rendered[0]))
        work = continuity.load(self.root / continuity.WORK_FILE, {})
        self.assertEqual(path, work['events'][event['id']]['path'])
        self.assertEqual(history, (self.root / 'event-history.json').read_bytes())

    def test_duplicate_page_redirects_and_other_same_day_session_remains_separate(self):
        self.install_identity()
        distinct = dict(self.accepted, id='unreviewed:separate-session', startTime='21:00')
        continuity.save(self.root / 'events.json', [self.alias, distinct])
        continuity.save(self.root / 'supplemental-events.json', [self.accepted])
        continuity.prepare(self.root)
        rows = continuity.load(self.root / 'events.json', [])
        self.assertEqual({KEEP_ID, distinct['id']}, {r['id'] for r in rows})
        self.assertEqual('21:00', next(r for r in rows if r['id'] == distinct['id'])['startTime'])
        site = self.root / '_site'
        target = continuity.target_file(site, KEEP_PATH)
        target.parent.mkdir(parents=True)
        content = '<html><head><link rel="canonical" href="' + continuity.ORIGIN + KEEP_PATH + '"></head><body>4 PM through 7 PM</body></html>'
        target.write_text(content)
        continuity.finalize(self.root, site, '2026-11-20')
        alias = continuity.PageFacts(continuity.target_file(site, ALIAS_PATH).read_text())
        self.assertEqual('0; url=' + continuity.ORIGIN + KEEP_PATH, alias.refresh)
        self.assertEqual(continuity.ORIGIN + KEEP_PATH, alias.canonical)
        self.assertEqual(content, target.read_text())
        sitemap = (site / 'sitemap.xml').read_text()
        self.assertIn(KEEP_PATH, sitemap)
        self.assertNotIn(ALIAS_PATH, sitemap)


if __name__ == '__main__':
    unittest.main()
