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

    def claim(self, cron='17 4 * * *', run='100', event='schedule', mode='', now=None):
        return schedule.claim(self.root, event, cron, mode, '', run, '1', now or self.now)

    def env(self, **changes):
        return dict(GITHUB_RUN_ID='100', GITHUB_RUN_ATTEMPT='1', GITHUB_REPOSITORY='owner/site',
                    KC_MODE='full', KC_DAY='2026-11-11', KC_RESULT='success',
                    KC_LIVE='success', KC_FRESHNESS='success', KC_CATALOG_DAY='2026-11-11', **changes)

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
        self.assertEqual(self.claim(event='workflow_dispatch', mode='dates')['mode'], 'dates')
        self.assertEqual(self.claim(event='workflow_dispatch', mode='full')['run'], 'true')
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
