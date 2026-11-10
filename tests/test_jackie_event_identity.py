"""Keep all reviewed tour stops when reviewed provider aliases are reimported."""
import copy
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

PAIRS = (
    ('manual:jackie-hill-perry-blameless-memphis-2027-02-16',
     'ticketmaster:G5viZ_pE35CeO', '19:00',
     '/event/blameless-the-tour-with-jackie-hill-perry-2027-02-16-memphis-770ba0/',
     '/event/blameless-the-tour-with-jackie-hill-perry-2027-02-16-memphis-fed827/'),
    ('manual:jackie-hill-perry-blameless-charlotte-2027-02-18',
     'ticketmaster:G5eVZ_pLsqK3P', '19:00',
     '/event/blameless-the-tour-with-jackie-hill-perry-2027-02-18-charlotte-2b5ff9/',
     '/event/blameless-the-tour-with-jackie-hill-perry-2027-02-18-charlotte-ae81f8/'),
    ('manual:jackie-hill-perry-blameless-new-york-2027-02-24',
     'ticketmaster:k7vGF_pxExPtR', '18:00',
     '/event/blameless-the-tour-with-jackie-hill-perry-2027-02-24-new-york-e69457/',
     '/event/blameless-the-tour-with-jackie-hill-perry-2027-02-24-new-york-b1f6c9/'),
)


class JackieEventIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        boundary = patch.object(catalog, 'REVIEW_FILE', self.root / 'config/review-held-events.json')
        boundary.start()
        self.addCleanup(boundary.stop)
        seeds = [event for event in json.loads((ROOT / 'config/manual-events.json').read_text())
                 if event.get('editorialBatch') == '2026-11-09-jackie-blameless-tour']
        self.assertEqual(15, len(seeds))
        self.manual = [dict(event, id='manual:' + event['id'].removeprefix('manual:')) for event in seeds]
        self.original = {event['id']: event for event in self.manual}
        self.providers = []
        state = continuity.empty_state()
        for event in self.manual:
            state['events'][event['id']] = {
                'path': continuity.generated_path(event), 'sourceIds': [], 'event': event}
        for keep_id, alias_id, clock, keep_path, old_path in PAIRS:
            self.assertEqual(keep_path, continuity.generated_path(self.original[keep_id]))
            self.assertFalse(self.original[keep_id].get('startTime'))
            provider = dict(self.original[keep_id], id=alias_id, startTime=clock,
                            ticketUrl='https://stillblameless.com/tour')
            self.assertEqual(old_path, continuity.generated_path(provider))
            self.providers.append(provider)
            # Also repair a previously retained alias, without losing its URL.
            state['events'][alias_id] = {'path': old_path, 'sourceIds': [], 'event': provider}
        rules = json.loads((ROOT / continuity.RULES_FILE).read_text())
        continuity.save(self.root / continuity.RULES_FILE,
                        {'merges': [rule for rule in rules['merges'] if rule['keepId'] in self.original]})
        continuity.save(self.root / continuity.STATE_FILE, state)
        continuity.save(self.root / 'config/manual-events.json', seeds)
        continuity.save(self.root / 'events.json', self.manual + self.providers)
        continuity.save(self.root / 'supplemental-events.json', [])
        continuity.save(self.root / 'event-history.json', {'events': [{'event': event} for event in self.manual]})

    def assert_tour_preserved(self):
        events = continuity.load(self.root / 'events.json', [])
        self.assertEqual(set(self.original), {event['id'] for event in events})
        self.assertEqual(15, len(events))
        for event in events:
            # Only identity metadata may change. In particular, an unknown
            # reviewed clock is not replaced by a provider's possible show time.
            facts = {key: value for key, value in event.items() if key != 'mergedFromIds'}
            self.assertEqual(self.original[event['id']], facts)
        prepared = continuity.load(self.root / continuity.WORK_FILE, {})
        for keep_id, alias_id, _, keep_path, old_path in PAIRS:
            self.assertNotIn(alias_id, prepared['events'])
            self.assertEqual(keep_path, prepared['events'][keep_id]['path'])
            self.assertEqual(keep_path, prepared['redirects'][old_path])
            self.assertIn(alias_id, prepared['events'][keep_id]['sourceIds'])
        return events, prepared

    def test_prepare_consolidates_provider_rows_before_all_renderers(self):
        protected = {name: (self.root / name).read_bytes()
                     for name in ('config/manual-events.json', 'event-history.json')}
        continuity.prepare(self.root)
        self.assert_tour_preserved()
        for name, original in protected.items():
            self.assertEqual(original, (self.root / name).read_bytes())

    def test_provider_reimport_is_idempotent_and_keeps_reviewed_unknown_times(self):
        continuity.prepare(self.root)
        events, first = self.assert_tour_preserved()
        continuity.persist(self.root, self.root / continuity.WORK_FILE)
        continuity.save(self.root / 'events.json', copy.deepcopy(events + self.providers))
        continuity.prepare(self.root)
        replay, second = self.assert_tour_preserved()
        self.assertEqual(events, replay)
        self.assertEqual(first['redirects'], second['redirects'])
        continuity.prepare(self.root)
        self.assertEqual(replay, continuity.load(self.root / 'events.json', []))

    def test_provider_only_refresh_restores_reviewed_identity_before_artist_cards(self):
        # The collector can retain the provider ID while consolidating the
        # manual seed. The published survivor then exists only in history/state.
        reviewed_ids = {pair[0] for pair in PAIRS}
        primary = [event for event in self.manual if event['id'] not in reviewed_ids]
        continuity.save(self.root / 'events.json', primary + self.providers)
        continuity.prepare(self.root)
        events, _ = self.assert_tour_preserved()

        import national_discovery
        records = [{'href': continuity.generated_path(event),
                    'html': '<article>' + event['id'] + '</article>'} for event in events]
        schedule = ('<main data-kc-rd-artist-profile><section class="kc-rd-profile-shows">'
                    + ''.join('<a class="kc-rd-show-row" href="'
                              + continuity.generated_path(event) + '">Show</a>' for event in events)
                    + '</section></main>')
        rendered = national_discovery.artist_details(schedule, {'records': records})
        self.assertIn('data-artist-show-details', rendered)
        for _, _, _, keep_path, alias_path in PAIRS:
            self.assertIn(keep_path, rendered)
            self.assertNotIn(alias_path, rendered)
        # Keep the actual failing final-render assertion active for a stale URL.
        broken = schedule.replace(PAIRS[0][3], PAIRS[0][4])
        with self.assertRaisesRegex(AssertionError, 'lacks matching full event cards'):
            national_discovery.artist_details(broken, {'records': records})

    def test_unreviewed_provider_session_remains_separate(self):
        other = dict(self.providers[0], id='unreviewed:jackie-late-session', startTime='21:00')
        continuity.save(self.root / 'events.json', self.manual + self.providers + [other])
        continuity.prepare(self.root)
        events = continuity.load(self.root / 'events.json', [])
        self.assertEqual(set(self.original) | {other['id']}, {event['id'] for event in events})
        retained = next(event for event in events if event['id'] == other['id'])
        self.assertEqual(other, {key: value for key, value in retained.items() if key != 'mergedFromIds'})
        self.assertFalse(retained.get('mergedFromIds'))

    def test_old_urls_forward_and_all_fifteen_original_pages_remain_in_sitemap(self):
        continuity.prepare(self.root)
        events, _ = self.assert_tour_preserved()
        site = self.root / '_site'
        originals = {}
        for event in events:
            path = continuity.generated_path(event)
            page = continuity.target_file(site, path)
            page.parent.mkdir(parents=True, exist_ok=True)
            content = ('<html><head><title>Blameless</title><meta name="robots" content="index,follow">'
                       f'<link rel="canonical" href="{continuity.ORIGIN + path}"></head>'
                       f'<body><main><h1>Blameless</h1><p>{event["startDate"]}</p></main></body></html>')
            page.write_text(content)
            originals[path] = content
        continuity.finalize(self.root, site, '2026-11-09')
        sitemap = (site / 'sitemap.xml').read_text()
        for path, content in originals.items():
            self.assertEqual(content, continuity.target_file(site, path).read_text())
            self.assertIn(continuity.ORIGIN + path, sitemap)
        for _, _, _, keep_path, old_path in PAIRS:
            alias = continuity.PageFacts(continuity.target_file(site, old_path).read_text())
            self.assertEqual(continuity.ORIGIN + keep_path, alias.canonical)
            self.assertEqual('0; url=' + continuity.ORIGIN + keep_path, alias.refresh)
            self.assertNotIn(continuity.ORIGIN + old_path, sitemap)


if __name__ == '__main__':
    unittest.main()
