import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import coordinated_schedule as schedule


class CoordinatedScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime.fromisoformat('2026-11-11T10:17:00+00:00')

    def claim(self, cron='17 4 * * *', run='100', event='schedule', mode='', now=None,
              automatic=False, day='', attempt='1', message=''):
        return schedule.claim(self.root, event, cron, mode, message, run, attempt, now or self.now,
                              automatic_fallback=automatic, expected_day=day)

    def automatic(self, mode='full', run='101', day='2026-11-11', **changes):
        return self.claim(event='workflow_dispatch', mode=mode, run=run,
                          automatic=True, day=day, **changes)

    def env(self, **changes):
        env = dict(GITHUB_RUN_ID='100', GITHUB_RUN_ATTEMPT='1', GITHUB_REPOSITORY='owner/site',
                    KC_MODE='full', KC_DAY='2026-11-11', KC_RESULT='success',
                    KC_COLLECTION='success', KC_LIVE='success', KC_FRESHNESS='success',
                    KC_CATALOG_DAY='2026-11-11')
        env.update(changes)
        return env

    def test_primary_then_fallback_performs_only_one_full_scan(self):
        first = self.claim()
        self.assertEqual((first['run'], first['mode']), ('true', 'full'))
        second = self.claim('47 4 * * *', run='101')
        self.assertEqual(second['run'], 'false')
        self.assertIn('100', second['reason'])

    def test_fallback_claims_missing_primary_without_a_separate_dispatcher(self):
        result = self.claim('47 4 * * *')
        self.assertEqual(result['run'], 'true')
        self.assertIn('Catch-up', result['reason'])

    def test_failure_and_interruption_do_not_authorize_automatic_rescan(self):
        self.claim()
        state = schedule.read_state(self.root)
        for outcome in ('started', 'failure', 'cancelled', 'success'):
            state['scheduled']['full:2026-11-11']['conclusion'] = outcome
            schedule.save_state(self.root, state)
            self.assertEqual(self.claim('47 4 * * *', run='101')['run'], 'false')

    def test_midnight_dates_and_morning_discovery_are_independent(self):
        self.assertEqual(self.claim('15 0 * * *')['mode'], 'dates')
        self.assertEqual(self.claim(run='101')['run'], 'true')
        self.assertEqual(set(schedule.read_state(self.root)['scheduled']),
                         {'dates:2026-11-11', 'full:2026-11-11'})

    def test_day_keys_follow_local_timezone_across_dst_and_utc_midnight(self):
        cases = [('2026-07-03T09:17:00+00:00', 'full', '2026-07-03'),
                 ('2026-11-11T10:17:00+00:00', 'full', '2026-11-11'),
                 ('2026-11-11T06:30:00+00:00', 'dates', '2026-11-10')]
        for stamp, mode, expected in cases:
            with self.subTest(stamp=stamp):
                result = self.claim(event='workflow_dispatch', mode=mode, now=datetime.fromisoformat(stamp))
                self.assertEqual(result['day'], expected)

    def test_manual_recovery_remains_explicit_and_does_not_rewrite_daily_claim(self):
        self.claim()
        before = (self.root / schedule.STATE).read_bytes()
        result = self.claim(event='workflow_dispatch', mode='full')
        self.assertEqual((result['run'], result['claim_required']), ('true', 'false'))
        self.assertEqual(before, (self.root / schedule.STATE).read_bytes())

    def test_malformed_receipt_unknown_cron_and_lost_claim_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.claim('0 5 * * *')
        with self.assertRaisesRegex(ValueError, 'own'):
            schedule.verify_claim(self.root, self.env())
        (self.root / schedule.STATE).write_text('{broken')
        with self.assertRaises(json.JSONDecodeError):
            self.claim()

    def test_only_claim_owner_can_collect_after_a_publication_race(self):
        self.claim()
        schedule.verify_claim(self.root, self.env())
        wrong = self.env()
        wrong['GITHUB_RUN_ID'] = '101'
        with self.assertRaisesRegex(ValueError, 'own'):
            schedule.verify_claim(self.root, wrong)

    def test_success_receipt_requires_exact_live_and_freshness_checks(self):
        env = self.env()
        env['KC_LIVE'] = 'failure'
        with self.assertRaisesRegex(ValueError, 'exact live'):
            schedule.record(self.root, env, self.now)
        self.assertFalse((self.root / 'live-deploy-status.json').exists())

    def test_receipt_updates_claim_and_late_midnight_does_not_republish(self):
        self.claim()
        schedule.record(self.root, self.env(KC_SOURCE_SHA='abc123'), self.now)
        state = schedule.read_state(self.root)
        self.assertEqual(state['scheduled']['full:2026-11-11']['conclusion'], 'success')
        self.assertEqual(state['latest']['savedSourceSha'], 'abc123')
        self.assertEqual(self.claim('15 0 * * *', run='101')['run'], 'false')
        self.assertEqual(json.loads((self.root / 'live-deploy-status.json').read_text())['run_id'], 100)

    def test_new_day_can_run_without_erasing_previous_day_evidence(self):
        self.claim()
        next_day = datetime.fromisoformat('2026-11-12T10:17:00+00:00')
        self.assertEqual(self.claim(run='101', now=next_day)['run'], 'true')
        self.assertEqual(len(schedule.read_state(self.root)['scheduled']), 2)

    def test_receipt_after_pacific_midnight_does_not_claim_unverified_new_day(self):
        self.claim()
        next_day = datetime.fromisoformat('2026-11-12T08:01:00+00:00')
        schedule.record(self.root, self.env(), next_day)
        self.assertEqual(schedule.read_state(self.root)['latest']['catalogDay'], '2026-11-11')
        self.assertEqual(self.claim('15 0 * * *', run='101', now=next_day)['run'], 'true')

    def test_cron_and_independent_fallback_in_either_order_collect_once(self):
        for first in ('cron', 'automatic'):
            with self.subTest(first=first), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                primary = self.claim() if first == 'cron' else self.automatic(run='100')
                second = self.automatic() if first == 'cron' else self.claim(run='101')
                self.assertEqual(primary['run'], 'true')
                self.assertEqual(primary['claim_required'], 'true')
                self.assertEqual(second['run'], 'false')
                self.assertEqual(self.automatic(run='102')['run'], 'false')
                state = schedule.read_state(self.root)
                self.assertEqual(list(state['scheduled']), ['full:2026-11-11'])
                self.assertEqual(state['scheduled']['full:2026-11-11']['runId'], '100')

    def test_independent_fallback_never_retries_any_recorded_outcome(self):
        self.automatic(run='100')
        state = schedule.read_state(self.root)
        for outcome in ('started', 'failure', 'cancelled', 'success'):
            with self.subTest(outcome=outcome):
                state['scheduled']['full:2026-11-11']['conclusion'] = outcome
                schedule.save_state(self.root, state)
                before = (self.root / schedule.STATE).read_bytes()
                self.assertEqual(self.automatic()['run'], 'false')
                self.assertEqual(self.automatic(run='100', attempt='2')['run'], 'false')
                self.assertEqual((self.root / schedule.STATE).read_bytes(), before)

    def test_automatic_dates_do_not_satisfy_full_discovery(self):
        result = self.automatic(mode='dates', run='100')
        self.assertEqual(result['mode'], 'dates')
        schedule.verify_claim(self.root, self.env(KC_MODE='dates'))
        schedule.record(self.root, self.env(KC_MODE='dates', KC_COLLECTION='skipped'), self.now)
        self.assertEqual(self.automatic()['run'], 'true')
        self.assertEqual(set(schedule.read_state(self.root)['scheduled']),
                         {'dates:2026-11-11', 'full:2026-11-11'})

    def test_automatic_requests_validate_flag_mode_and_expected_day(self):
        cases = [dict(mode=''), dict(mode='typo'), dict(day=''), dict(day='20261111'),
                 dict(day='2026-02-30'), dict(event='push'), dict(automatic='yes')]
        for change in cases:
            with self.subTest(change=change):
                args = dict(event='workflow_dispatch', mode='full', automatic=True, day='2026-11-11')
                args.update(change)
                with self.assertRaises(ValueError):
                    self.claim(**args)
                self.assertFalse((self.root / schedule.STATE).exists())

    def test_delayed_and_future_automatic_requests_do_not_claim_another_day(self):
        for day in ('2026-11-10', '2026-11-12'):
            with self.subTest(day=day):
                self.assertEqual(self.automatic(day=day)['run'], 'false')
                self.assertFalse((self.root / schedule.STATE).exists())

    def test_automatic_day_uses_mode_timezone_and_dst(self):
        cases = [('2026-07-03T09:17:00+00:00', 'full', '2026-07-03'),
                 ('2026-11-11T06:30:00+00:00', 'full', '2026-11-11'),
                 ('2026-11-11T06:30:00+00:00', 'dates', '2026-11-10')]
        for stamp, mode, day in cases:
            with self.subTest(stamp=stamp, mode=mode), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                result = self.automatic(mode=mode, day=day, now=datetime.fromisoformat(stamp))
                self.assertEqual((result['run'], result['day']), ('true', day))

    def test_pinned_replay_and_result_after_midnight_never_allocate_another_claim(self):
        for mode, before, after in (
                ('full', '2026-11-12T05:59:59+00:00', '2026-11-12T06:00:01+00:00'),
                ('dates', '2026-11-12T07:59:59+00:00', '2026-11-12T08:00:01+00:00')):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                plan = self.automatic(mode=mode, run='100', now=datetime.fromisoformat(before))
                env = self.env(KC_MODE=plan['mode'], KC_DAY=plan['day'])
                original = (self.root / schedule.STATE).read_bytes()
                # The publisher replays ownership verification using plan outputs,
                # not a new claim whose day depends on its execution clock.
                schedule.verify_claim(self.root, env)
                self.assertEqual((self.root / schedule.STATE).read_bytes(), original)
                schedule.record(self.root, env, datetime.fromisoformat(after))
                self.assertEqual(list(schedule.read_state(self.root)['scheduled']), [mode + ':2026-11-11'])

    def test_collection_entry_rejects_lost_attempt_or_completed_claim(self):
        self.automatic(run='100')
        original = (self.root / schedule.STATE).read_bytes()
        for change in ({'GITHUB_RUN_ATTEMPT': '2'}, {'GITHUB_RUN_ID': '101'}, {'KC_DAY': '2026-11-12'}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'own'):
                schedule.verify_claim(self.root, self.env(**change))
        self.assertEqual((self.root / schedule.STATE).read_bytes(), original)
        schedule.record(self.root, self.env(), self.now)
        with self.assertRaisesRegex(ValueError, 'own'):
            schedule.verify_claim(self.root, self.env())

    def test_manual_completion_without_new_env_records_first_attempt_even_failure(self):
        for outcome in ('success', 'failure', 'cancelled'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                self.assertFalse((self.root / schedule.STATE).exists())
                # The already-running old workflow did not persist a manual claim.
                schedule.record(self.root, self.env(KC_RESULT=outcome), self.now)
                state = schedule.read_state(self.root)
                self.assertEqual(state['scheduled']['full:2026-11-11']['conclusion'], outcome)
                self.assertEqual(self.automatic()['run'], 'false')
                self.assertEqual(self.claim(run='101')['run'], 'false')

    def test_first_explicit_run_is_durable_even_if_cancelled_before_recording(self):
        for event, message, mode in (('workflow_dispatch', '', 'full'),
                                     ('push', '', 'dates'), ('push', '[full scan]', 'full')):
            with self.subTest(event=event, mode=mode), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                result = self.claim(event=event, mode='full', message=message)
                self.assertEqual((result['run'], result['mode'], result['claim_required']), ('true', mode, 'true'))
                state = schedule.read_state(self.root)
                first = state['scheduled'][mode + ':2026-11-11']
                self.assertEqual((first['runId'], first['trigger'], first['conclusion']), ('100', event, 'started'))
                schedule.verify_claim(self.root, self.env(KC_MODE=mode))
                # Simulate cancellation or failed receipt persistence: no record().
                self.assertEqual(self.automatic(mode=mode)['run'], 'false')
                override = self.claim(event='workflow_dispatch', mode=mode, run='102')
                self.assertEqual((override['run'], override['claim_required']), ('true', 'false'))
                self.assertEqual(schedule.read_state(self.root), state)

    def test_explicit_runs_cannot_overwrite_malformed_daily_claims(self):
        for event in ('workflow_dispatch', 'push'):
            with self.subTest(event=event):
                key = ('full' if event == 'workflow_dispatch' else 'dates') + ':2026-11-11'
                schedule.save_state(self.root, {'schemaVersion': 1, 'scheduled': {key: {}}})
                before = (self.root / schedule.STATE).read_bytes()
                with self.assertRaisesRegex(ValueError, 'Malformed'):
                    self.claim(event=event, mode='full')
                self.assertEqual((self.root / schedule.STATE).read_bytes(), before)

    def test_explicit_manual_override_preserves_original_failed_attempt(self):
        self.automatic(run='100')
        schedule.record(self.root, self.env(KC_RESULT='failure'), self.now)
        prior = schedule.read_state(self.root)['scheduled']['full:2026-11-11']
        self.assertEqual(self.claim(event='workflow_dispatch', mode='full', run='101')['run'], 'true')
        schedule.record(self.root, self.env(GITHUB_RUN_ID='101'), self.now)
        state = schedule.read_state(self.root)
        self.assertEqual(state['scheduled']['full:2026-11-11'], prior)
        self.assertEqual(state['latest']['runId'], '101')
        self.assertEqual(self.automatic(run='102')['run'], 'false')

    def test_durable_full_completion_survives_a_later_dates_result(self):
        schedule.record(self.root, self.env(), self.now)
        schedule.record(self.root, self.env(GITHUB_RUN_ID='101', KC_MODE='dates', KC_COLLECTION='skipped'), self.now)
        before = (self.root / schedule.STATE).read_bytes()
        live = (self.root / 'live-deploy-status.json').read_bytes()
        self.assertEqual(self.automatic(run='102')['run'], 'false')
        self.assertEqual(self.automatic(mode='dates', run='103')['run'], 'false')
        self.assertEqual((self.root / schedule.STATE).read_bytes(), before)
        self.assertEqual((self.root / 'live-deploy-status.json').read_bytes(), live)

    def test_previous_version_latest_attempt_also_prevents_automatic_repetition(self):
        for outcome in ('success', 'failure'):
            with self.subTest(outcome=outcome):
                schedule.save_state(self.root, {'schemaVersion': 1, 'scheduled': {},
                    'latest': {'runId': '99', 'mode': 'full', 'day': '2026-11-11', 'conclusion': outcome}})
                before = (self.root / schedule.STATE).read_bytes()
                self.assertEqual(self.automatic()['run'], 'false')
                self.assertEqual((self.root / schedule.STATE).read_bytes(), before)

    def test_failed_job_rerun_cannot_rewrite_the_original_attempt(self):
        self.automatic(run='100')
        schedule.record(self.root, self.env(KC_RESULT='failure'), self.now)
        prior = schedule.read_state(self.root)['scheduled']['full:2026-11-11']
        schedule.record(self.root, self.env(GITHUB_RUN_ATTEMPT='2', KC_RESULT='failure'), self.now)
        self.assertEqual(schedule.read_state(self.root)['scheduled']['full:2026-11-11'], prior)

    def test_old_latest_only_full_attempt_survives_a_new_dates_receipt(self):
        for outcome in ('success', 'failure'):
            with self.subTest(outcome=outcome):
                old = {'runId': '99', 'attempt': '1', 'mode': 'full', 'day': '2026-11-11',
                       'conclusion': outcome, 'catalogDay': '2026-11-11',
                       'stages': {'collection': 'success', 'live': outcome, 'freshness': outcome}}
                schedule.save_state(self.root, {'schemaVersion': 1, 'scheduled': {}, 'latest': old})
                schedule.record(self.root, self.env(KC_MODE='dates', KC_COLLECTION='skipped'), self.now)
                state = schedule.read_state(self.root)
                self.assertEqual(state['latest']['mode'], 'dates')
                self.assertEqual(state['scheduled']['full:2026-11-11'], old)
                self.assertEqual(state['completed']['full:2026-11-11'], old)
                self.assertEqual(self.automatic()['run'], 'false')

    def test_successful_manual_recovery_remains_visible_after_a_later_dates_result(self):
        self.automatic(run='100')
        schedule.record(self.root, self.env(KC_RESULT='failure'), self.now)
        first = schedule.read_state(self.root)['scheduled']['full:2026-11-11']
        schedule.record(self.root, self.env(GITHUB_RUN_ID='101'), self.now)
        recovered = schedule.read_state(self.root)['completed']['full:2026-11-11']
        schedule.record(self.root, self.env(GITHUB_RUN_ID='102', KC_MODE='dates', KC_COLLECTION='skipped'), self.now)
        state = schedule.read_state(self.root)
        self.assertEqual(state['scheduled']['full:2026-11-11'], first)
        self.assertEqual(first['conclusion'], 'failure')
        self.assertEqual(state['completed']['full:2026-11-11'], recovered)
        self.assertEqual((recovered['runId'], recovered['conclusion']), ('101', 'success'))
        self.assertEqual(state['completed']['dates:2026-11-11']['runId'], '102')
        self.assertEqual(state['latest']['mode'], 'dates')
        result = self.automatic(mode='dates', run='103')
        self.assertEqual(result['run'], 'false')
        self.assertIn('Morning sequence already verified', result['reason'])

    def test_older_terminal_result_cannot_replace_newer_completion(self):
        schedule.record(self.root, self.env(GITHUB_RUN_ID='101'), self.now)
        schedule.record(self.root, self.env(GITHUB_RUN_ID='100', KC_RESULT='failure'), self.now)
        state = schedule.read_state(self.root)
        self.assertEqual(state['completed']['full:2026-11-11']['runId'], '101')
        self.assertEqual(state['completed']['full:2026-11-11']['conclusion'], 'success')
        self.assertEqual(state['latest']['runId'], '101')

    def test_malformed_completed_map_fails_closed_without_discarding_claims(self):
        schedule.save_state(self.root, {'schemaVersion': 1, 'scheduled': {}, 'completed': []})
        before = (self.root / schedule.STATE).read_bytes()
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            self.automatic()
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            schedule.record(self.root, self.env(), self.now)
        self.assertEqual((self.root / schedule.STATE).read_bytes(), before)
