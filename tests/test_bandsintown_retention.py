"""A provider's omission is review evidence, not cancellation evidence."""
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_bandsintown_rest as collector
import run_bandsintown_refresh as refresh

ARTIST = {'name': 'Issac Mansfield', 'enabled': True,
          'bandsintownProfile': 'https://www.bandsintown.com/a/15588396-issac-mansfield'}


def show(**changes):
    return dict({'id': 'bandsintown:109105799', 'bandsintownEventId': '109105799',
        'title': "THE KINGDOM'S COOL KIDZ PLAYLIST CONCERT", 'startDate': '2026-11-21',
        'startTime': '18:30', 'venue': "THE KINGDOM'S COOL KIDZ PLAYLIST CONCERT",
        'city': 'Detroit', 'state': 'MI', 'country': 'US', 'status': 'scheduled',
        'artists': ['Issac Mansfield'], 'headliner': 'Issac Mansfield',
        'trackedArtist': 'Issac Mansfield', 'firstSeen': '2026-11-03T18:56:47Z',
        'officialUrl': 'https://www.bandsintown.com/e/109105799',
        'ticketUrl': 'https://www.bandsintown.com/t/109105799?app_id=kc'}, **changes)


def raw(event_id='111', **changes):
    return dict({'id': event_id, 'datetime': '2026-11-14T19:00:00',
        'url': f'https://www.bandsintown.com/e/{event_id}', 'title': 'Another real show',
        'artist_id': '15588396', 'offers': [],
        'venue': {'name': 'Other venue', 'city': 'Detroit', 'region': 'MI', 'country': 'US'}}, **changes)


class MissingProviderRetentionTests(unittest.TestCase):
    def run_refresh(self, prior, response=(), primary=(), artists=None, request_status=200,
                    profile_status=200, day='2026-11-07', collector_override=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in [('artists', artists if artists is not None else [ARTIST]),
                                ('events', list(primary)), ('supplemental', prior),
                                ('status', {'generatedAt': '2000-01-01T00:00:00Z',
                                            'errors': [{'artist': 'Issac Mansfield'}]})]:
                (root/f'{name}.json').write_text(json.dumps(value))
            original = (root/'supplemental.json').read_bytes()
            original_status = (root/'status.json').read_bytes()
            def request(url):
                return (request_status, list(response) if isinstance(response, tuple) else response) if '/events/' in url else (profile_status, {'id': '15588396', 'name': 'Issac Mansfield'})
            with patch.multiple(collector, ARTISTS_FILE=root/'artists.json', EVENTS_FILE=root/'events.json',
                    SUPPLEMENTAL_FILE=root/'supplemental.json', STATUS_FILE=root/'status.json', CANDIDATES_FILE=root/'candidates.json'), \
                 patch.multiple(refresh, SUPPLEMENTAL=root/'supplemental.json', STATUS=root/'status.json'), \
                 patch.object(collector, 'get_json', side_effect=request), patch.object(collector.time, 'sleep'), \
                 patch.object(refresh, 'today_cutoff', return_value=day, create=True), contextlib.redirect_stdout(io.StringIO()):
                if collector_override:
                    with patch.object(collector, 'main', side_effect=lambda: collector_override(root)):
                        try:
                            refresh.main()
                        except (Exception, SystemExit):
                            self.assertEqual((root/'supplemental.json').read_bytes(), original)
                            self.assertEqual((root/'status.json').read_bytes(), original_status)
                            return 'rejected'
                        return 'accepted'
                self.assertEqual(refresh.main(), 0)
            return json.loads((root/'supplemental.json').read_text()), json.loads((root/'status.json').read_text())

    def test_actual_successful_partial_response_keeps_detroit_and_reports_review(self):
        prior = show()
        rows, status = self.run_refresh([prior], [raw()])
        self.assertIn(prior, rows)
        self.assertEqual(status.get('missingProviderShowsRetained'), 1)
        self.assertEqual(status.get('missingProviderReview'), [{'id': prior['id'], 'officialUrl': prior['officialUrl'],
            'reason': 'absent_from_current_provider_output_not_confirmed_cancelled'}])
        self.assertEqual(status['preservedDueToRequestErrors'], 0, 'Old status errors must not describe this successful pass')

    def test_empty_unresolved_failed_and_malformed_api_responses_preserve_us_and_canada(self):
        for country, state in [('US', 'MI'), ('CA', 'ON')]:
            prior = show(country=country, state=state)
            for response, request, profile in [([], 200, 200), (None, 503, 200), ({'error':'bad'},200,200), ([],200,503)]:
                with self.subTest(country=country, response=response, request=request, profile=profile):
                    rows, status = self.run_refresh([prior], response, request_status=request, profile_status=profile)
                    self.assertEqual(rows, [prior])
                    self.assertEqual(status.get('missingProviderShowsRetained'), 1)

    def test_matching_id_merged_id_or_provider_source_in_main_is_a_replacement(self):
        prior = show()
        replacements = [dict(prior, title='Corrected primary record'),
            {'id':'manual:verified', 'mergedFromIds':[prior['id']]},
            {'id':'manual:verified', 'bandsintownEventId':'109105799'},
            {'id':'manual:verified', 'sources':[{'url':'https://www.bandsintown.com/e/109105799-detroit?foo=1'}]},
            {'id':'manual:verified', 'officialUrl':'https://www.bandsintown.com/t/109105799?x=1', 'status':'cancelled'}]
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                rows, status = self.run_refresh([prior], primary=[replacement])
                self.assertEqual(rows, [])
                self.assertEqual(status.get('missingProviderShowsRetained'), 0)

    def test_distinct_same_day_city_show_and_id_substrings_do_not_replace(self):
        primary = dict(show(), id='manual:other', bandsintownEventId='2109105799',
                       officialUrl='https://example.com/109105799', ticketUrl='', venue='Other venue')
        rows, _ = self.run_refresh([show()], primary=[primary])
        self.assertEqual(rows, [show()])

    def test_fresh_same_id_updates_without_retaining_old_record(self):
        rows, status = self.run_refresh([show()], [raw('109105799', datetime='2026-11-21T20:30:00')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['startTime'], '20:30')
        self.assertEqual(status.get('missingProviderShowsRetained'), 0)

    def test_expired_rows_drop_but_ongoing_multiday_remains_through_pacific_final_day(self):
        past = show(startDate='2026-11-06')
        ongoing = dict(past, endDate='2026-11-07')
        for row, expected in [(past, []), (dict(past, endDate='garbage'), []), (ongoing, [ongoing])]:
            with self.subTest(row=row):
                self.assertEqual(self.run_refresh([row])[0], expected)
        self.assertEqual(self.run_refresh([ongoing], day='2026-11-08')[0], [])

    def test_disabled_alias_owner_hold_and_removed_artist_are_not_retained(self):
        disabled = dict(ARTIST, name='Canonical Artist', aliases=['Issac Mansfield'], enabled=False)
        held = show(startDate='2026-11-19', city='Dallas', state='TX', artists=['Alex Jean'], headliner='Alex Jean', trackedArtist='Alex Jean')
        removed = show(artists=['Propaganda'], headliner='Propaganda', trackedArtist='Propaganda')
        excluded = show(artists=['Madison Ryann Ward'], headliner='Madison Ryann Ward', trackedArtist='Madison Ryann Ward')
        for prior, artists in [(show(), [disabled]), (held, [dict(ARTIST,name='Alex Jean')]),
                               (removed, [dict(ARTIST,name='Propaganda')]), (excluded, [dict(ARTIST,name='Madison Ryann Ward')])]:
            with self.subTest(prior=prior, artists=artists):
                self.assertEqual(self.run_refresh([prior], artists=artists)[0], [])

    def test_protected_official_cancelled_postponed_merged_records_win_same_provider_id(self):
        for changes in [{'authority':'official_event'}, {'status':'cancelled'}, {'status':'postponed'}, {'status':'merged'},
                        {'status':'held'}, {'status':'hold'}, {'status':'removed'}, {'holdReason':'Owner hold'}]:
            prior = show(**changes)
            # A changed artist association defeats the collector's broad artist gate;
            # the wrapper must still preserve exact editorial/provider identity.
            prior['artists'] = ['Other confirmed billing']
            with self.subTest(changes=changes):
                rows, _ = self.run_refresh([prior], [raw('109105799', datetime='2026-11-21T20:30:00')])
                self.assertEqual(rows, [prior])

    def test_retention_applies_secondary_artist_exclusions_without_losing_booking_facts(self):
        for excluded in ['Madison Ryann Ward', 'Disabled Guest Alias']:
            prior = show(artists=['Issac Mansfield', excluded, 'Untracked Confirmed Guest'],
                         headliner=excluded, image='assets/events/original.jpg')
            roster = [ARTIST, {'name':'Disabled Guest', 'aliases':['Disabled Guest Alias'], 'enabled':False}]
            expected = dict(prior, artists=['Issac Mansfield', 'Untracked Confirmed Guest'], headliner='Issac Mansfield')
            with self.subTest(excluded=excluded):
                rows, _ = self.run_refresh([prior], artists=roster)
                self.assertEqual(rows, [expected])

    def test_retained_visible_billing_filters_excluded_names_but_preserves_confirmed_guests(self):
        prior = show(artists=['Issac Mansfield', 'Madison Ryann Ward', 'Untracked Confirmed Guest'],
                     advertisedBilling=['Issac Mansfield', 'Madison Ryann Ward', 'Disabled Guest Alias', 'Untracked Confirmed Guest'],
                     officialBill=['Issac Mansfield', 'Madison Ryann Ward', 'Disabled Guest Alias', 'Untracked Confirmed Guest'])
        roster = [ARTIST, {'name':'Disabled Guest', 'aliases':['Disabled Guest Alias'], 'enabled':False}]
        expected = dict(prior, artists=['Issac Mansfield', 'Untracked Confirmed Guest'],
                        advertisedBilling=['Issac Mansfield', 'Untracked Confirmed Guest'],
                        officialBill=['Issac Mansfield', 'Untracked Confirmed Guest'])
        self.assertEqual(self.run_refresh([prior], artists=roster)[0], [expected])

    def test_not_resolved_without_request_error_still_retains_established_booking(self):
        artist = {'name':'Issac Mansfield', 'enabled':True}
        rows, status = self.run_refresh([show()], artists=[artist], profile_status=503)
        self.assertEqual(rows, [show()])
        self.assertEqual(status['requestErrors'], 0)
        self.assertEqual(status['missingProviderShowsRetained'], 1)

    def test_repeated_absence_is_idempotent_and_preserves_earliest_source_facts(self):
        first, _ = self.run_refresh([show()])
        second, status = self.run_refresh(first)
        self.assertEqual(second, [show()])
        self.assertEqual(status.get('missingProviderShowsRetained'), 1)

    def test_missing_malformed_stale_or_invalid_output_receipts_restore_original(self):
        def output(root, rows, status):
            (root/'supplemental.json').write_text(json.dumps(rows))
            if status is not None:
                (root/'status.json').write_text(status)
            return 0
        valid = json.dumps({'generatedAt':datetime.now(timezone.utc).isoformat(), 'errors':[], 'artistsChecked':1, 'requestErrors':0})
        cases = [lambda r:output(r, [], None), lambda r:output(r, [], '{bad'),
                 lambda r:output(r, [], json.dumps({'generatedAt':'2000-01-01T00:00:00Z','errors':[]})),
                 lambda r:output(r, ['bad row'], valid),
                 lambda r:output(r, [], json.dumps({'generatedAt':datetime.now(timezone.utc).isoformat(),'errors':'bad'}))]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.run_refresh([show()], collector_override=case), 'rejected')

    def test_incomplete_or_malformed_current_receipt_rolls_back(self):
        for fields in [{}, {'artistsChecked':True,'requestErrors':0}, {'artistsChecked':0,'requestErrors':0},
                       {'artistsChecked':1,'requestErrors':'0'}, {'artistsChecked':1,'requestErrors':-1}]:
            def output(root):
                (root/'supplemental.json').write_text('[]')
                (root/'status.json').write_text(json.dumps({
                    'generatedAt':datetime.now(timezone.utc).isoformat(), 'errors':[], **fields}))
                return 0
            with self.subTest(fields=fields):
                self.assertEqual(self.run_refresh([show()], collector_override=output), 'rejected')


if __name__ == '__main__':
    unittest.main()
