"""A reviewed identity keeps its original discovery time during feed merging."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import url_continuity as continuity


class DiscoveryAgeTests(unittest.TestCase):
    def event(self, identity, first_seen, **changes):
        return dict({'id': identity, 'title': 'Reviewed concert', 'startDate': '2026-12-29',
                     'startTime': '19:00', 'city': 'Washington', 'state': 'DC',
                     'country': 'US', 'venue': 'Howard Theatre', 'artists': ['Alex Jean'],
                     'status': 'scheduled', 'firstSeen': first_seen}, **changes)

    def test_actual_duplicate_feed_discovery_times_survive_prepare_and_repeat(self):
        cases = json.loads((ROOT / 'tests/fixtures/discovery-age-duplicates.json').read_text())
        for case in cases:
            identity = case['id']
            primary, supplemental = copy.deepcopy(case['primary']), copy.deepcopy(case['supplemental'])
            original = supplemental['firstSeen']
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state = continuity.empty_state()
                state['events'][identity] = {'path': continuity.generated_path(primary), 'sourceIds': [], 'event': primary}
                continuity.save(root / continuity.STATE_FILE, state)
                continuity.save(root / continuity.RULES_FILE, {})
                continuity.save(root / 'events.json', [primary])
                continuity.save(root / 'supplemental-events.json', [supplemental])
                history = {'events': [{'event': supplemental}]}
                continuity.save(root / 'event-history.json', history)
                history_bytes = (root / 'event-history.json').read_bytes()
                for _ in range(2):
                    continuity.prepare(root)
                    for name in ('events.json', 'supplemental-events.json'):
                        actual = continuity.load(root / name, [])[0]
                        self.assertEqual(original, actual['firstSeen'])
                        for key in ('title', 'startDate', 'endDate', 'startTime', 'endTime', 'venue',
                                    'city', 'state', 'country', 'status', 'price', 'verifiedVersion',
                                    'officialUrl', 'ticketUrl'):
                            if key in primary:
                                self.assertEqual(primary[key], actual.get(key), key)
                        self.assertEqual(identity, actual['id'])
                    self.assertEqual(history_bytes, (root / 'event-history.json').read_bytes())
                self.assertEqual(case['primary'], primary)
                self.assertEqual(case['supplemental'], supplemental)

    def test_earliest_instant_wins_even_when_string_sort_order_disagrees(self):
        primary = self.event('manual:show', '2026-10-30T09:00:00-07:00')
        other = self.event('provider:show', '2026-10-30T15:30:00Z')
        before = copy.deepcopy((primary, other))
        result = continuity.merge_details(primary, other)
        self.assertEqual('2026-10-30T15:30:00Z', result['firstSeen'])
        self.assertEqual('manual:show', result['id'])
        self.assertEqual(before, (primary, other))

    def test_equal_instants_preserve_preferred_format_and_invalid_values_do_not_replace_valid_age(self):
        preferred = self.event('manual:show', '2026-10-30T15:30:00Z')
        for value in ('2026-10-30T08:30:00-07:00', 'not confirmed', '2026-10-29', ''):
            with self.subTest(value=value):
                result = continuity.merge_details(preferred, self.event('provider:show', value))
                self.assertEqual(preferred['firstSeen'], result['firstSeen'])

    def test_identity_only_alias_cannot_contribute_discovery_or_other_rejected_facts(self):
        preferred = self.event('manual:show', '2026-10-30T15:30:00Z')
        result = continuity.merge_details(preferred, {'id': 'rejected:alias'})
        self.assertEqual(preferred['firstSeen'], result['firstSeen'])
        self.assertEqual(preferred['venue'], result['venue'])
        self.assertEqual(preferred['artists'], result['artists'])

    def test_valid_age_fills_missing_or_malformed_preferred_age_without_inventing_a_timestamp(self):
        other = self.event('provider:show', '2026-10-30T15:30:00Z')
        for value in (None, '', 'not confirmed', '2026-02-30T12:00:00Z', '2026-10-29'):
            with self.subTest(value=value):
                result = continuity.merge_details(self.event('manual:show', value), other)
                self.assertEqual(other['firstSeen'], result['firstSeen'])
        result = continuity.merge_details(self.event('manual:show', 'not confirmed'), {'id': 'provider:show'})
        self.assertEqual('not confirmed', result['firstSeen'])


if __name__ == '__main__':
    unittest.main()
