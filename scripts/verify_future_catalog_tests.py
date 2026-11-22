"""Detect test fixture expiry before it blocks a later daily publication.

The complete Python suite runs with tomorrow's catalog day and one year ahead in
separate subprocesses. The real publication clock, schedule claims, collection
timestamps and source records are not changed. Each child has a fixed time limit;
failures remain failures and their logs are preserved for diagnosis.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from catalog_clock import catalog_date

ROOT = Path(__file__).resolve().parents[1]
SUITE_TIMEOUT_SECONDS = 600
CI_OUTPUT_FILES = ('GITHUB_ENV', 'GITHUB_OUTPUT', 'GITHUB_PATH', 'GITHUB_STATE', 'GITHUB_STEP_SUMMARY')


def future_days(day):
    try:
        next_year = day.replace(year=day.year + 1)
    except ValueError:
        # February 29 has no same day in the following year.
        next_year = day.replace(year=day.year + 1, day=28)
    return (day + timedelta(days=1), next_year)


def child_environment(parent, day):
    environment = dict(parent)
    environment['KC_CATALOG_DAY'] = day.isoformat()
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    # Tests may exercise clock export helpers, but must never export the test
    # date or a test output into the remaining production workflow steps.
    for key in CI_OUTPUT_FILES:
        environment.pop(key, None)
    return environment


def run_matrix(source, day, report, *, environment=None, runner=subprocess.run,
               clock=time.monotonic, timeout_seconds=SUITE_TIMEOUT_SECONDS):
    if timeout_seconds <= 0:
        raise ValueError('The future date suite requires a positive timeout')
    source, report = Path(source), Path(report)
    report.parent.mkdir(parents=True, exist_ok=True)
    parent = dict(os.environ if environment is None else environment)
    result = {'schemaVersion': 1, 'status': 'running', 'baseCatalogDay': day.isoformat(),
              'parentCatalogDay': parent.get('KC_CATALOG_DAY'),
              'suiteTimeoutSeconds': timeout_seconds, 'scenarios': []}

    def save():
        report.write_text(json.dumps(result, indent=2) + '\n')

    save()
    for scenario in future_days(day):
        started = clock()
        logfile = report.parent / f'future-catalog-tests-{scenario.isoformat()}.log'
        row = {'catalogDay': scenario.isoformat(), 'log': str(logfile), 'status': 'failed'}
        with logfile.open('w') as output:
            try:
                completed = runner(
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-q'],
                    cwd=source, env=child_environment(parent, scenario), stdout=output,
                    stderr=subprocess.STDOUT, check=False, timeout=timeout_seconds,
                )
                row['exitCode'] = completed.returncode
                row['status'] = 'passed' if completed.returncode == 0 else 'failed'
            except subprocess.TimeoutExpired:
                row['status'] = 'timed_out'
                output.write(f'\nFuture catalog test suite exceeded {timeout_seconds} seconds.\n')
            except OSError as exc:
                row['error'] = type(exc).__name__
                output.write(f'\nUnable to start future catalog test suite: {type(exc).__name__}.\n')
        row['elapsedSeconds'] = round(clock() - started, 3)
        result['scenarios'].append(row)
        save()
        print(f'Future catalog test date {scenario}: {row["status"]}; log {logfile}', flush=True)
    result['status'] = 'passed' if all(row['status'] == 'passed' for row in result['scenarios']) else 'failed'
    save()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = run_matrix(args.source, catalog_date(), args.report)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
