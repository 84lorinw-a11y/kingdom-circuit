"""A complete attempt is distinct from success at every discovery provider."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify_discovery_receipt.py'


class DiscoveryReceiptTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'The current-pass receipt gate is not implemented')
        spec = importlib.util.spec_from_file_location('verify_discovery_receipt', SCRIPT)
        self.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gate)
        self.started = '2026-11-10T10:17:00+00:00'
        self.now = datetime(2026, 11, 10, 11, 0, tzinfo=timezone.utc)
        self.artists = [{'name': 'First Artist', 'website': 'https://first.example/', 'enabled': True},
                        {'name': 'Second Artist'}, {'name': 'Disabled Artist', 'enabled': False}]
        rows = [{'artist': artist, 'source': source, 'status': status, 'eventsFound': 0}
                for artist in ('First Artist', 'Second Artist')
                for source, status in [('Bandsintown', 'delegated_to_structured_rest'),
                                       ('Songkick', 'blocked_by_robots')]]
        rows.append({'artist': 'First Artist', 'source': 'official website', 'status': 'failed',
                     'url': 'https://first.example/', 'eventsFound': 0, 'error': 'HTTP 429'})
        self.full = {'generatedAt': '2026-11-10T10:40:00Z', 'artistsChecked': 2,
                     'sourceResults': rows, 'sourceStatusCounts': dict(Counter(row['status'] for row in rows)),
                     'bandsintown': {'discoveryMode': 'structured_rest', 'status': 'ok',
                         'artistsAttempted': 2, 'resolved': 1, 'rawUpcomingUSRows': 3,
                         'rawUpcomingCARows': 1, 'rawUpcomingRows': 4, 'newEventsPublished': 1,
                         'festivalCandidatesHeld': 0, 'requestErrors': 1}}
        self.bit = {'generatedAt': '2026-11-10T10:30:00Z', 'artistsChecked': 2, 'artistsResolved': 1,
                    'rawUpcomingUSRows': 3, 'rawUpcomingCARows': 1, 'rawUpcomingRows': 4,
                    'newNonFestivalShowsPublished': 1, 'festivalCandidatesHeld': 0, 'requestErrors': 1,
                    'errors': [{'artist': 'Second Artist', 'error': 'HTTP 503'}]}
        self.websites = {'generatedAt': '2026-11-10T10:41:00Z', 'artistsConfigured': 2,
                         'officialWebsitesChecked': 1, 'mode': 'all-tracked-artists-official-website-scan',
                         'warningCount': 1, 'warnings': ['First Artist: HTTP 429']}
        self.eventbrite = {'generatedAt': '2026-11-10T10:50:00Z', 'artistsChecked': 2,
                           'searchFailures': 2, 'detailFailures': 0,
                           'artistResults': [{'artist': name, 'status': 'failed', 'error': 'HTTP 405'}
                                             for name in ('First Artist', 'Second Artist')]}

    def verify(self):
        return self.gate.verify_receipts(self.artists, self.full, self.bit, self.websites,
                                         self.eventbrite, self.started, self.now)

    def test_complete_attempts_with_provider_errors_are_truthful_limitations(self):
        result = self.verify()
        self.assertEqual([], result['errors'])
        self.assertEqual('complete_with_limitations', result['status'])
        self.assertEqual(2, result['artistsExpected'])
        self.assertEqual('per_artist', result['stages']['expanded']['evidence'])
        self.assertEqual('aggregate_aligned_with_expanded_delegation', result['stages']['bandsintown']['evidence'])
        self.assertFalse(result['publicationVerified'])
        self.assertTrue(any(item.get('status') == 'blocked_by_robots' for item in result['limitations']))
        self.assertTrue(any(item.get('stage') == 'eventbrite' for item in result['limitations']))

    def test_accessible_complete_pass_has_no_artificial_limitations(self):
        for row in self.full['sourceResults']:
            if row['source'] != 'Bandsintown':
                row['status'] = 'ok'
        self.full['sourceStatusCounts'] = dict(Counter(row['status'] for row in self.full['sourceResults']))
        self.bit.update(artistsResolved=2, requestErrors=0, errors=[])
        self.full['bandsintown'].update(resolved=2, requestErrors=0)
        self.websites.update(warningCount=0, warnings=[], eventsFound=0, missingProviderShowsRetained=3)
        for row in self.eventbrite['artistResults']:
            row.update(status='ok', error='')
        self.eventbrite['searchFailures'] = 0
        result = self.verify()
        self.assertEqual('complete', result['status'])
        self.assertEqual([], result['limitations'])
        self.assertEqual(3, result['stages']['websites']['retainedMissingProviderShows'])

    def test_request_error_total_cannot_omit_all_error_evidence(self):
        self.bit['errors'] = []
        self.assertTrue(any('requestErrors' in error for error in self.verify()['errors']))

    def test_malformed_eventbrite_status_returns_failure_evidence(self):
        self.eventbrite['artistResults'][0]['status'] = {'not': 'a status'}
        self.assertEqual('incomplete', self.verify()['status'])

    def test_correct_count_cannot_hide_replaced_artist_identity(self):
        for row in self.full['sourceResults']:
            if row['artist'] == 'Second Artist':
                row['artist'] = 'Wrong Artist'
        result = self.verify()
        self.assertEqual('incomplete', result['status'])
        self.assertTrue(any('Second Artist' in error for error in result['errors']))
        self.assertTrue(any('Wrong Artist' in error for error in result['errors']))

    def test_duplicate_or_missing_mandatory_surface_cannot_pass(self):
        self.full['sourceResults'][3] = deepcopy(self.full['sourceResults'][2])
        self.full['sourceStatusCounts'] = dict(Counter(row['status'] for row in self.full['sourceResults']))
        errors = self.verify()['errors']
        self.assertTrue(any('duplicate' in error.lower() for error in errors))
        self.assertTrue(any('Songkick' in error and 'Second Artist' in error for error in errors))

    def test_missing_configured_official_site_is_not_a_complete_pass(self):
        self.full['sourceResults'].pop()
        self.full['sourceStatusCounts'] = dict(Counter(row['status'] for row in self.full['sourceResults']))
        self.assertTrue(any('official website' in error for error in self.verify()['errors']))

    def test_each_stage_must_be_newer_than_current_collection_start(self):
        for stage in ('full', 'bit', 'websites', 'eventbrite'):
            report = getattr(self, stage)
            old = report['generatedAt']
            report['generatedAt'] = '2026-11-10T10:16:59Z'
            with self.subTest(stage=stage):
                self.assertTrue(any('current pass' in error for error in self.verify()['errors']))
            report['generatedAt'] = old

    def test_future_or_unzoned_timestamps_are_rejected(self):
        for stamp in ('2026-11-10T11:01:00Z', '2026-11-10T10:40:00'):
            with self.subTest(stamp=stamp):
                self.full['generatedAt'] = stamp
                self.assertTrue(self.verify()['errors'])

    def test_bandsintown_must_match_the_embedded_current_pass_summary(self):
        self.bit['artistsResolved'] = 2
        self.assertTrue(any('resolved' in error for error in self.verify()['errors']))

    def test_bandsintown_timestamp_cannot_follow_the_full_scan_summary(self):
        self.bit['generatedAt'] = '2026-11-10T10:45:00Z'
        self.assertTrue(any('after expanded' in error for error in self.verify()['errors']))

    def test_global_bandsintown_failure_is_not_mistaken_for_individual_limitations(self):
        self.full['bandsintown']['status'] = 'failed_preserved_prior'
        self.assertTrue(any('Bandsintown' in error for error in self.verify()['errors']))

    def test_status_counter_must_describe_actual_rows(self):
        self.full['sourceStatusCounts']['blocked_by_robots'] = 0
        self.assertTrue(any('sourceStatusCounts' in error for error in self.verify()['errors']))

    def test_unattempted_source_status_is_not_an_access_limitation(self):
        self.full['sourceResults'][1]['status'] = 'pending'
        self.full['sourceStatusCounts'] = dict(Counter(row['status'] for row in self.full['sourceResults']))
        self.assertTrue(any('pending' in error for error in self.verify()['errors']))

    def test_eventbrite_identity_substitution_and_partial_website_scan_fail(self):
        self.eventbrite['artistResults'][1]['artist'] = 'Wrong Artist'
        self.websites['officialWebsitesChecked'] = 0
        errors = self.verify()['errors']
        self.assertTrue(any('eventbrite' in error and 'Second Artist' in error for error in errors))
        self.assertTrue(any('officialWebsitesChecked' in error for error in errors))

    def test_invalid_enabled_flags_or_duplicate_roster_names_fail_closed(self):
        self.artists.append({'name': 'First Artist'})
        self.assertTrue(any('duplicate' in error.lower() for error in self.verify()['errors']))
        self.artists.pop()
        self.artists[0]['enabled'] = 'false'
        self.assertTrue(any('enabled' in error for error in self.verify()['errors']))

    def test_boolean_aggregate_counts_and_unreported_request_errors_fail(self):
        self.bit['requestErrors'] = False
        self.assertTrue(self.verify()['errors'])
        self.bit['requestErrors'] = 0
        self.full['bandsintown']['requestErrors'] = 0
        self.assertTrue(any('requestErrors' in error for error in self.verify()['errors']))

    def test_missing_or_future_collection_start_fails_closed(self):
        for stamp in ('', '2026-11-11T10:17:00Z'):
            with self.subTest(stamp=stamp):
                self.started = stamp
                self.assertEqual('incomplete', self.verify()['status'])

    def test_cli_reads_current_pass_environment_and_writes_failure_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / 'config').mkdir()
            for path, value in [('config/artists.json', self.artists), ('full-scan-status.json', self.full),
                                ('bandsintown-status.json', self.bit), ('artist-website-status.json', self.websites),
                                ('eventbrite-scan-status.json', self.eventbrite)]:
                (source / path).write_text(json.dumps(value))
            output = source / 'receipt.json'
            environment = os.environ | {'KC_COLLECTION_STARTED_AT': '2099-01-01T00:00:00Z'}
            environment.pop('GITHUB_STEP_SUMMARY', None)  # Keep fixture failures out of the real CI summary.
            result = subprocess.run([sys.executable, str(SCRIPT), '--source', str(source), '--report', str(output)],
                                    env=environment,
                                    capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            report = json.loads(output.read_text())
            self.assertEqual('incomplete', report['status'])
            self.assertTrue(report['errors'])


if __name__ == '__main__':
    unittest.main()
