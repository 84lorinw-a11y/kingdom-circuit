"""Keep the reviewed Mike correction through source replay and URL retention."""
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
import apply_curated_catalog_policy as curation
import catalog_removals as catalog
import preserve_reviewed_discoveries as discoveries
import url_continuity as continuity

KEEP_ID = 'manual:mike-malagies-its-a-god-night-orlando-2026-12-12'
OLD_ID = 'official:5f5e88420934ba61cf99'
KEEP_PATH = '/event/mike-malagies-it-s-a-god-night-orlando-2026-12-12-kissimmee-4cf61c/'
OLD_PATH = '/event/mike-malagies-sun-on-the-beach-2026-12-12-kissimmee-eeaa01/'
OFFICIAL = 'https://itsagodnight.ticketspice.com/its-a-god-night-orlando'
ARTWORK = 'assets/events/mike-malagies-orlando-2026-12-12.png'


class MikeEventIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.site = self.root / '_site'
        self.site.mkdir()
        boundary = patch.object(catalog, 'REVIEW_FILE', self.root / 'config/review-held-events.json')
        boundary.start()
        self.addCleanup(boundary.stop)
        self.seed = {
            'id': KEEP_ID.removeprefix('manual:'),
            'title': 'Mike Malagies — It’s A God Night (Orlando)',
            'startDate': '2026-12-12', 'startTime': '17:00', 'doorsTime': '16:00',
            'timezone': 'America/New_York', 'venue': 'Sun on the Beach — Old Town',
            'city': 'Kissimmee', 'state': 'FL', 'country': 'US',
            'artists': ['Mike Malagies'], 'status': 'scheduled',
            'officialUrl': OFFICIAL, 'ticketUrl': OFFICIAL,
            'image': ARTWORK, 'imageType': 'event_artwork',
            'firstSeen': '2026-10-30T02:10:10.097556+00:00',
            'editorialBatch': '2026-10-29-mike-orlando-g2g',
        }
        self.current = dict(self.seed, id=KEEP_ID)
        self.old = dict(self.current, id=OLD_ID, title='Mike Malagies @ Sun On the Beach',
                        startTime='22:00', endDate='2026-12-13',
                        venue='Sun On The Beach',
                        officialUrl='https://music.apple.com/us/concerts/artist/1573408784',
                        ticketUrl='https://music.apple.com/us/concerts/artist/1573408784',
                        image='assets/artists/mike-malagies-official-hires-oct22.webp',
                        imageType='artist')
        continuity.save(self.root / 'config/manual-events.json', [self.seed])

    def restore(self, events, supplemental=None):
        discoveries.apply(self.root, events, supplemental if supplemental is not None else [],
                          today='2026-11-09')
        return next(event for event in events if event['id'] == KEEP_ID)

    def assert_reviewed_facts(self, event):
        for key in ('title', 'startDate', 'startTime', 'doorsTime', 'timezone', 'venue',
                    'city', 'state', 'country', 'artists', 'status', 'officialUrl',
                    'ticketUrl', 'image', 'imageType', 'firstSeen'):
            self.assertEqual(self.current[key], event.get(key), key)
        self.assertNotIn('endDate', event)

    def test_source_restoration_preserves_curated_legacy_identity(self):
        curated = curation.curate_event(copy.deepcopy(self.current))
        self.assertEqual([OLD_PATH], curated['legacyEventPaths'])
        self.assertTrue(curation.is_known_duplicate_fragment(self.old))
        restored = self.restore([curated])
        self.assertEqual([OLD_PATH], restored.get('legacyEventPaths'))
        self.assertEqual(curated['legacyEventNotice'], restored.get('legacyEventNotice'))
        self.assert_reviewed_facts(restored)
        self.assertEqual([self.seed], continuity.load(self.root / 'config/manual-events.json', []))

    def test_restoration_unions_explicit_history_without_copying_stale_facts(self):
        current = dict(self.current, legacyEventPaths=[OLD_PATH], mergedFromIds=[OLD_ID],
                       legacyEventNotice='Reviewed correction', startTime='22:00')
        extra = dict(self.current, legacyEventPaths=[OLD_PATH, '/event/older-reviewed-link/'],
                     mergedFromIds=[OLD_ID, 'reviewed:older'])
        events, supplemental = [current], [extra]
        restored = self.restore(events, supplemental)
        self.assertEqual([OLD_PATH, '/event/older-reviewed-link/'], restored.get('legacyEventPaths'))
        self.assertEqual([OLD_ID, 'reviewed:older'], restored.get('mergedFromIds'))
        self.assertEqual('Reviewed correction', restored.get('legacyEventNotice'))
        self.assert_reviewed_facts(restored)
        self.assertEqual([], supplemental)
        first = copy.deepcopy(restored)
        self.assertEqual(first, self.restore(events, supplemental))

    def test_reviewed_override_retires_old_identity_and_survives_replay(self):
        rules = json.loads((ROOT / continuity.RULES_FILE).read_text())
        mike_rules = {'merges': [group for group in rules['merges'] if group['keepId'] == KEEP_ID]}
        state = continuity.empty_state()
        for event, path in ((self.current, KEEP_PATH), (self.old, OLD_PATH)):
            state['events'][event['id']] = {'path': path, 'sourceIds': [], 'event': event}
        continuity.save(self.root / continuity.STATE_FILE, state)
        continuity.save(self.root / continuity.RULES_FILE, mike_rules)
        continuity.save(self.root / 'events.json', [self.current])
        continuity.save(self.root / 'supplemental-events.json', [])
        continuity.save(self.root / 'event-history.json', {'events': [{'event': self.old}]})
        # No transient legacy fields: the reviewed identity rule must independently
        # repair already-published registry entries left by the earlier source loss.
        continuity.prepare(self.root)
        prepared = continuity.load(self.root / continuity.WORK_FILE, {})
        self.assertNotIn(OLD_ID, prepared['events'])
        self.assertEqual(KEEP_PATH, prepared['redirects'].get(OLD_PATH))
        self.assertIn(OLD_ID, prepared['events'][KEEP_ID]['sourceIds'])
        self.assert_reviewed_facts(continuity.load(self.root / 'events.json', [])[0])
        target = continuity.target_file(self.site, KEEP_PATH)
        target.parent.mkdir(parents=True)
        content = ('<html><head><title>Mike</title><meta name="robots" content="index,follow">'
                   f'<link rel="canonical" href="{continuity.ORIGIN + KEEP_PATH}"></head>'
                   '<body><main><h1>Mike Malagies</h1><p>December 12 at 5 PM</p>'
                   f'<a href="{OFFICIAL}">Tickets</a><img src="/{ARTWORK}"></main></body></html>')
        target.write_text(content)
        continuity.finalize(self.root, self.site, '2026-11-09')
        alias = continuity.PageFacts(continuity.target_file(self.site, OLD_PATH).read_text())
        self.assertEqual('0; url=' + continuity.ORIGIN + KEEP_PATH, alias.refresh)
        self.assertEqual(continuity.ORIGIN + KEEP_PATH, alias.canonical)
        self.assertNotIn(OLD_PATH, (self.site / 'sitemap.xml').read_text())
        self.assertIn(KEEP_PATH, (self.site / 'sitemap.xml').read_text())
        self.assertEqual(content, target.read_text())
        continuity.persist(self.root, self.root / continuity.WORK_FILE)
        # A later provider import goes through the existing reviewed suppression
        # and seed restoration before continuity preparation, as production does.
        replay = [curation.curate_event(event) for event in (self.old, self.current)
                  if not curation.is_known_duplicate_fragment(event)]
        self.restore(replay)
        continuity.save(self.root / 'events.json', replay)
        continuity.prepare(self.root)
        continuity.finalize(self.root, self.site, '2026-11-10')
        replayed = continuity.load(self.root / continuity.WORK_FILE, {})
        self.assertNotIn(OLD_ID, replayed['events'])
        self.assertEqual(KEEP_PATH, replayed['redirects'][OLD_PATH])
        self.assertEqual([KEEP_ID], [event['id'] for event in continuity.load(self.root / 'events.json', [])])
        self.assert_reviewed_facts(continuity.load(self.root / 'events.json', [])[0])

    def test_unreviewed_conflicting_sessions_remain_distinct(self):
        late = dict(self.current, id='unreviewed:late-session', startTime='22:00')
        self.assertFalse(continuity.same_performance(self.current, late))
        continuity.save(self.root / 'events.json', [self.current, late])
        continuity.save(self.root / 'supplemental-events.json', [])
        continuity.prepare(self.root)
        self.assertEqual({KEEP_ID, late['id']},
                         {event['id'] for event in continuity.load(self.root / 'events.json', [])})

    def test_archived_survivor_does_not_inherit_rejected_provider_facts(self):
        rules = json.loads((ROOT / continuity.RULES_FILE).read_text())
        continuity.save(self.root / continuity.RULES_FILE,
                        {'merges': [group for group in rules['merges'] if group['keepId'] == KEEP_ID]})
        state = continuity.empty_state()
        state['events'][KEEP_ID] = {'path': KEEP_PATH, 'sourceIds': [OLD_ID], 'event': self.current}
        state['redirects'][OLD_PATH] = KEEP_PATH
        continuity.save(self.root / continuity.STATE_FILE, state)
        # Once the show expires, no current row exists to overwrite facts copied
        # from the rejected provider snapshot during explicit alias preparation.
        continuity.save(self.root / 'events.json', [])
        continuity.save(self.root / 'supplemental-events.json', [])
        continuity.save(self.root / 'event-history.json',
                        {'events': [{'event': self.current}, {'event': self.old}]})
        original_history = (self.root / 'event-history.json').read_bytes()
        for day in ('2026-12-14', '2026-12-15'):
            with self.subTest(day=day):
                continuity.prepare(self.root)
                prepared = continuity.load(self.root / continuity.WORK_FILE, {})
                archived = prepared['events'][KEEP_ID]['event']
                expected = {key: value for key, value in self.current.items()
                            if key in continuity.SNAPSHOT_FIELDS}
                self.assertEqual(expected, archived)
                self.assertNotIn(OLD_ID, prepared['events'])
                self.assertEqual(KEEP_PATH, prepared['redirects'][OLD_PATH])
                simulated_now = dt.datetime.fromisoformat(day + 'T12:00:00+00:00')

                class ArchiveClock(dt.datetime):
                    @classmethod
                    def now(cls, tz=None):
                        return simulated_now.astimezone(tz) if tz else simulated_now.replace(tzinfo=None)

                with patch.object(continuity.dt, 'datetime', ArchiveClock):
                    continuity.finalize(self.root, self.site, day)
                alias = continuity.PageFacts(continuity.target_file(self.site, OLD_PATH).read_text())
                self.assertEqual('0; url=' + continuity.ORIGIN + KEEP_PATH, alias.refresh)
                self.assertEqual(continuity.ORIGIN + KEEP_PATH, alias.canonical)
                self.assertNotIn(OLD_PATH, (self.site / 'sitemap.xml').read_text())
                continuity.persist(self.root, self.root / continuity.WORK_FILE)
                self.assertEqual(original_history, (self.root / 'event-history.json').read_bytes())

    def test_reviewed_provider_reimport_cannot_fill_rejected_fields(self):
        rules = json.loads((ROOT / continuity.RULES_FILE).read_text())
        continuity.save(self.root / continuity.RULES_FILE,
                        {'merges': [group for group in rules['merges'] if group['keepId'] == KEEP_ID]})
        state = continuity.empty_state()
        state['events'][KEEP_ID] = {'path': KEEP_PATH, 'sourceIds': [], 'event': self.current}
        for rows in ([self.current, self.old], [self.old]):
            with self.subTest(current_ids=[event['id'] for event in rows]):
                continuity.save(self.root / continuity.STATE_FILE, state)
                continuity.save(self.root / 'events.json', rows)
                continuity.save(self.root / 'supplemental-events.json', [])
                continuity.prepare(self.root)
                events = continuity.load(self.root / 'events.json', [])
                self.assertEqual([KEEP_ID], [event['id'] for event in events])
                self.assert_reviewed_facts(events[0])
                prepared = continuity.load(self.root / continuity.WORK_FILE, {})
                self.assertEqual(KEEP_PATH, prepared['redirects'][OLD_PATH])
                self.assertIn(OLD_ID, prepared['events'][KEEP_ID]['sourceIds'])


if __name__ == '__main__':
    unittest.main()
