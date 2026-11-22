"""Future test clocks must expose failures without changing publication clocks."""
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_future_catalog_tests as matrix


class FutureCatalogTestMatrixTests(unittest.TestCase):
    def test_tomorrow_and_calendar_year_ahead_cover_month_year_and_leap_rollover(self):
        for day, expected in [
            (date(2026, 11, 22), (date(2026, 11, 23), date(2027, 11, 22))),
            (date(2026, 11, 30), (date(2026, 12, 1), date(2027, 11, 30))),
            (date(2026, 12, 31), (date(2027, 1, 1), date(2027, 12, 31))),
            (date(2028, 2, 29), (date(2028, 3, 1), date(2029, 2, 28))),
        ]:
            with self.subTest(day=day):
                self.assertEqual(expected, matrix.future_days(day))

    def test_children_receive_future_day_without_mutating_parent_or_export_files(self):
        parent = {'KC_CATALOG_DAY': '2026-11-22', 'PATH': '/safe/bin',
                  **{key: '/real/workflow/output' for key in matrix.CI_OUTPUT_FILES}}
        original = dict(parent)
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            kwargs['stdout'].write('All test fixtures ran.\n')
            self.assertEqual(kwargs['env']['PATH'], '/safe/bin')
            self.assertFalse(set(matrix.CI_OUTPUT_FILES) & kwargs['env'].keys())
            self.assertEqual(kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')
            self.assertEqual(kwargs['timeout'], 600)
            self.assertIs(kwargs['check'], False)
            self.assertIs(kwargs['stderr'], subprocess.STDOUT)
            return SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'matrix.json'
            with patch.dict(os.environ, {'KC_CATALOG_DAY': '2026-11-22'}):
                result = matrix.run_matrix(ROOT, date(2026, 11, 22), report,
                                           environment=parent, runner=runner)
                self.assertEqual(os.environ['KC_CATALOG_DAY'], '2026-11-22')
            self.assertEqual('passed', result['status'])
            self.assertEqual(result, json.loads(report.read_text()))
            self.assertEqual(['2026-11-23', '2027-11-22'], [kw['env']['KC_CATALOG_DAY'] for _, kw in calls])
            self.assertTrue(all(command == [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                            '-p', 'test_*.py', '-q'] for command, _ in calls))
            self.assertTrue(all(Path(row['log']).read_text() == 'All test fixtures ran.\n'
                                for row in result['scenarios']))
        self.assertEqual(original, parent)

    def test_a_failed_future_date_fails_gate_and_keeps_both_results(self):
        returns = iter([1, 0])
        with tempfile.TemporaryDirectory() as tmp:
            def runner(command, **kwargs):
                kwargs['stdout'].write('Fixture failure evidence.\n')
                return SimpleNamespace(returncode=next(returns))
            result = matrix.run_matrix(ROOT, date(2026, 11, 22), Path(tmp) / 'matrix.json',
                                       environment={}, runner=runner)
            self.assertEqual('failed', result['status'])
            self.assertEqual(['failed', 'passed'], [r['status'] for r in result['scenarios']])
            self.assertEqual(1, result['scenarios'][0]['exitCode'])
            self.assertIn('Fixture failure evidence', Path(result['scenarios'][0]['log']).read_text())

    def test_timeout_and_launch_failure_are_persisted_as_failures(self):
        failures = iter([subprocess.TimeoutExpired('python', 600), OSError('not available')])
        with tempfile.TemporaryDirectory() as tmp:
            def runner(command, **kwargs):
                raise next(failures)
            report = Path(tmp) / 'matrix.json'
            result = matrix.run_matrix(ROOT, date(2026, 11, 22), report, environment={}, runner=runner)
            self.assertEqual('failed', result['status'])
            self.assertEqual(['timed_out', 'failed'], [r['status'] for r in result['scenarios']])
            self.assertEqual('OSError', result['scenarios'][1]['error'])
            self.assertIn('exceeded 600 seconds', Path(result['scenarios'][0]['log']).read_text())
            self.assertEqual(result, json.loads(report.read_text()))

    def test_workflow_runs_gate_before_collection_and_preserves_failure_evidence(self):
        workflow = (ROOT / '.github/workflows/update-and-deploy.yml').read_text()
        marker = '      - name: Verify tests across future calendar dates\n'
        self.assertEqual(1, workflow.count(marker))
        block = workflow.split(marker, 1)[1].split('      - name:', 1)[0]
        self.assertIn('timeout-minutes: 25', block)
        self.assertIn('python scripts/verify_future_catalog_tests.py', block)
        self.assertIn('--report "$RUNNER_TEMP/future-catalog-tests.json"', block)
        self.assertNotIn('continue-on-error:', block)
        self.assertNotIn('if:', block)
        self.assertNotIn('GITHUB_ENV', block)
        self.assertLess(workflow.index('      - name: Run all automated tests'), workflow.index(marker))
        self.assertLess(workflow.index(marker), workflow.index('      - name: Collect upcoming shows'))
        evidence = workflow.split('      - name: Keep publication audit evidence', 1)[1]
        self.assertIn('if: always()', evidence)
        self.assertIn('${{ runner.temp }}/future-catalog-tests.json', evidence)
        self.assertIn('${{ runner.temp }}/future-catalog-tests-*.log', evidence)


if __name__ == '__main__':
    unittest.main()
