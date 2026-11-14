"""Keep the confirmed Garner provider identity without importing UTC clock facts."""
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

KEEP_ID = 'bandsintown:109149445'
ALIAS_ID = 'official:718febbb9aead6d818e3'
KEEP_PATH = '/event/mike-teezy-at-garner-performing-arts-center-2027-02-27-garner-eb6feb/'
ALIAS_PATH = '/event/mike-teezy-garner-performing-arts-center-2027-02-27-garner-2173a7/'
PROVIDER_URL = ('https://www.bandsintown.com/e/109149445?app_id=js_kingdomcircuit.com'
                '&came_from=267&utm_medium=api&utm_source=public_api&utm_campaign=event')
APPLE_URL = 'https://music.apple.com/us/concerts/artist/517774271'


class MikeTeezyEventIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        boundary = patch.object(catalog, 'REVIEW_FILE', self.root / 'config/review-held-events.json')
        boundary.start()
        self.addCleanup(boundary.stop)
        # The complete accepted provider row from November 14, before correction.
        self.accepted = {
            'id': KEEP_ID, 'title': 'Mike Teezy at Garner Performing Arts Center',
            'startDate': '2027-02-27', 'startTime': '15:00', 'timezone': '',
            'venue': 'Garner Performing Arts Center', 'address': '742 W Garner Rd',
            'city': 'Garner', 'state': 'NC', 'country': 'US', 'artists': ['Mike Teezy'],
            'headliner': 'Mike Teezy', 'eventType': 'concert', 'status': 'scheduled',
            'ticketUrl': PROVIDER_URL, 'officialUrl': PROVIDER_URL,
            'image': 'assets/artists/mike-teezy-saved.png', 'price': '',
            'sourceName': 'Bandsintown',
            'sources': [{'name': 'Bandsintown', 'url': PROVIDER_URL,
                         'type': 'bandsintown_rest', 'authority': 'artist_calendar', 'priority': 74}],
            'confidence': 'medium', 'bandsintownEventId': '109149445',
            'bandsintownArtistId': '4131763', 'bandsintownResolvedName': 'Mike Teezy',
            'bandsintownIdentity': 'exact_name_or_alias', 'trackedArtist': 'Mike Teezy',
        }
        self.alias = {
            key: copy.deepcopy(value) for key, value in self.accepted.items()
            if not key.startswith('bandsintown') and key != 'trackedArtist'
        }
        self.alias.update({
            'id': ALIAS_ID, 'title': 'Mike Teezy @ Garner Performing Arts Center',
            'startTime': '20:00', 'endDate': '2027-02-28',
            'ticketUrl': APPLE_URL, 'officialUrl': APPLE_URL,
            'sourceName': 'Mike Teezy Apple Music concerts',
            'sources': [{'name': 'Mike Teezy Apple Music concerts', 'url': APPLE_URL,
                         'type': 'jsonld', 'authority': 'artist_calendar', 'priority': 74}],
            'lastVerified': '2026-11-14T13:22:47Z', 'confidence': 'high',
            'imageType': 'artist', 'imagePosition': 'center', 'verifiedVersion': 9,
            'firstSeen': '2026-11-14T13:22:47Z',
        })
        rules = json.loads((ROOT / continuity.RULES_FILE).read_text())
        matches = [rule for rule in rules['merges'] if rule['keepId'] == KEEP_ID]
        self.assertEqual(1, len(matches))
        self.assertIs(True, matches[0].get('identityOnly'))
        self.assertEqual([ALIAS_ID], matches[0]['aliasIds'])
        continuity.save(self.root / continuity.RULES_FILE, {'merges': matches})
        state = continuity.empty_state()
        for event, path in ((self.accepted, KEEP_PATH), (self.alias, ALIAS_PATH)):
            state['events'][event['id']] = {
                'path': path, 'sourceIds': [],
                'event': {key: value for key, value in event.items() if key in continuity.SNAPSHOT_FIELDS},
            }
        continuity.save(self.root / continuity.STATE_FILE, state)
        continuity.save(self.root / 'event-history.json', {'events': [
            {'archiveKey': 'id:' + KEEP_ID, 'firstSeenOnCalendar': '2026-11-12T11:40:18Z',
             'event': self.accepted},
            {'archiveKey': 'id:' + ALIAS_ID, 'firstSeenOnCalendar': '2026-11-14T13:22:47Z',
             'event': self.alias},
        ]})
        self.history_bytes = (self.root / 'event-history.json').read_bytes()

    def prepare(self, events, supplemental):
        continuity.save(self.root / 'events.json', events)
        continuity.save(self.root / 'supplemental-events.json', supplemental)
        continuity.prepare(self.root)
        self.assertEqual(self.history_bytes, (self.root / 'event-history.json').read_bytes())
        state = continuity.load(self.root / continuity.WORK_FILE, {})
        self.assertNotIn(ALIAS_ID, state['events'])
        self.assertEqual(KEEP_PATH, state['events'][KEEP_ID]['path'])
        self.assertEqual(KEEP_PATH, state['redirects'][ALIAS_PATH])
        self.assertIn(ALIAS_ID, state['events'][KEEP_ID]['sourceIds'])
        return [row for name in continuity.FEEDS for row in continuity.load(self.root / name, [])]

    def assert_accepted(self, row, expected=None):
        for key, value in (expected or self.accepted).items():
            self.assertEqual(value, row.get(key), key)
        for key in ('endDate', 'endTime', 'firstSeen', 'lastVerified', 'verifiedVersion'):
            self.assertNotIn(key, row)
        self.assertIn(ALIAS_ID, row['mergedFromIds'])

    def test_current_feeds_preserve_every_accepted_fact_and_replay(self):
        for attempt in range(2):
            with self.subTest(attempt=attempt):
                rows = self.prepare([self.alias], [self.accepted])
                self.assertEqual({KEEP_ID}, {row['id'] for row in rows})
                self.assertEqual(2, len(rows))
                for row in rows:
                    self.assert_accepted(row)
                continuity.persist(self.root, self.root / continuity.WORK_FILE)

    def test_alias_reimport_uses_accepted_archive_without_copying_provider_facts(self):
        rows = self.prepare([self.alias], [])
        self.assertEqual(1, len(rows))
        self.assert_accepted(rows[0])

    def test_registry_alone_restores_accepted_facts_when_feeds_and_history_lack_survivor(self):
        continuity.save(self.root / 'event-history.json', {'events': [{'event': self.alias}]})
        self.history_bytes = (self.root / 'event-history.json').read_bytes()
        rows = self.prepare([self.alias], [])
        self.assertEqual(1, len(rows))
        expected = {key: value for key, value in self.accepted.items() if key in continuity.SNAPSHOT_FIELDS}
        self.assert_accepted(rows[0], expected)

    def test_published_alias_redirects_without_changing_survivor_page(self):
        self.prepare([self.alias], [self.accepted])
        site = self.root / '_site'
        target = continuity.target_file(site, KEEP_PATH)
        target.parent.mkdir(parents=True)
        content = ('<html><head><title>Mike Teezy</title>'
                   f'<link rel="canonical" href="{continuity.ORIGIN + KEEP_PATH}"></head>'
                   '<body><main><h1>Mike Teezy at Garner Performing Arts Center</h1>'
                   f'<p>February 27 at 3 PM</p><a href="{PROVIDER_URL}">Tickets</a>'
                   '</main></body></html>')
        target.write_text(content)
        continuity.finalize(self.root, site, '2026-11-14')
        alias = continuity.PageFacts(continuity.target_file(site, ALIAS_PATH).read_text())
        self.assertEqual('0; url=' + continuity.ORIGIN + KEEP_PATH, alias.refresh)
        self.assertEqual(continuity.ORIGIN + KEEP_PATH, alias.canonical)
        self.assertEqual(content, target.read_text())
        sitemap = (site / 'sitemap.xml').read_text()
        self.assertIn(KEEP_PATH, sitemap)
        self.assertNotIn(ALIAS_PATH, sitemap)
        self.assertEqual(self.history_bytes, (self.root / 'event-history.json').read_bytes())

    def test_unreviewed_conflicting_session_remains_separate(self):
        later = dict(self.accepted, id='unreviewed:garner-evening-session', startTime='20:00')
        self.assertFalse(continuity.same_performance(self.accepted, later))
        rows = self.prepare([self.alias, later], [self.accepted])
        self.assertEqual({KEEP_ID, later['id']}, {row['id'] for row in rows})
        distinct = next(row for row in rows if row['id'] == later['id'])
        for key, value in later.items():
            self.assertEqual(value, distinct.get(key), key)
        self.assertEqual([], distinct.get('mergedFromIds'))

    def test_expired_show_retains_correct_archive_and_alias_redirect(self):
        self.assertEqual([], self.prepare([], []))
        site = self.root / '_site'
        simulated_now = dt.datetime.fromisoformat('2027-03-01T12:00:00+00:00')

        class ArchiveClock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return simulated_now.astimezone(tz) if tz else simulated_now.replace(tzinfo=None)

        with patch.object(continuity.dt, 'datetime', ArchiveClock):
            continuity.finalize(self.root, site, '2027-03-01')
        retained = continuity.target_file(site, KEEP_PATH).read_text()
        self.assertIn('This date has passed.', retained)
        self.assertIn('<dd>15:00</dd>', retained)
        self.assertNotIn('<dd>20:00</dd>', retained)
        alias = continuity.PageFacts(continuity.target_file(site, ALIAS_PATH).read_text())
        self.assertEqual('0; url=' + continuity.ORIGIN + KEEP_PATH, alias.refresh)
        self.assertEqual(self.history_bytes, (self.root / 'event-history.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
