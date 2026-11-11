#!/usr/bin/env python3
"""Durable, fail-closed daily claims for the one GitHub publication workflow.

Cron and independent automatic dispatches may claim a missing daily run, never
retry a recorded attempt. All callers hold kingdom-circuit-pages concurrency
until the final receipt is saved. The first explicit run also claims its day
before work; later explicit recovery may override an existing attempt.
"""
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .calendar_maintenance import refresh_mode
except ImportError:
    from calendar_maintenance import refresh_mode

STATE = 'daily-publication-status.json'
FULL_SCHEDULES = {'17 4 * * *', '47 4 * * *'}
DATE_SCHEDULES = {'15 0 * * *'}
TERMINAL = {'success', 'failure', 'cancelled', 'skipped', 'timed_out',
            'action_required', 'neutral', 'stale', 'startup_failure'}


def read_state(root):
    path = root / STATE
    state = json.loads(path.read_text()) if path.exists() else {'schemaVersion': 1, 'scheduled': {}}
    if (not isinstance(state, dict) or state.get('schemaVersion') != 1
            or not isinstance(state.get('scheduled'), dict)
            or not isinstance(state.get('completed', {}), dict)
            or not isinstance(state.get('latest', {}), dict)):
        raise ValueError('Invalid daily publication receipt; refusing to discard prior claims')
    return state


def save_state(root, state):
    (root / STATE).write_text(json.dumps(state, indent=2) + '\n')


def automatic_request(value):
    if isinstance(value, bool):
        return value
    if value in ('', 'false'):
        return False
    if value == 'true':
        return True
    raise ValueError('Invalid automatic fallback flag')


def valid_day(value):
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError('Expected an ISO calendar day')
    return value


def verified_full(receipt, day):
    return (isinstance(receipt, dict) and receipt.get('mode') == 'full'
            and receipt.get('conclusion') == 'success'
            and receipt.get('catalogDay') == day
            and all(receipt.get('stages', {}).get(stage) == 'success'
                    for stage in ('collection', 'live', 'freshness')))


def remember_completed(state, receipt):
    """Keep the latest terminal result per mode/day without replacing its claim."""
    if (not receipt.get('runId') or receipt.get('mode') not in {'full', 'dates'}
            or not receipt.get('day') or receipt.get('conclusion') not in TERMINAL):
        return
    key = receipt['mode'] + ':' + valid_day(receipt['day'])
    completed = state.setdefault('completed', {})
    previous = completed.get(key, {})
    if int(previous.get('runId', 0)) <= int(receipt['runId']):
        completed[key] = dict(receipt)


def claim(root, event, schedule, requested, message, run_id, attempt, now,
          automatic_fallback=False, expected_day=''):
    automatic = automatic_request(automatic_fallback)
    if automatic:
        if event != 'workflow_dispatch' or requested not in {'full', 'dates'}:
            raise ValueError('Automatic fallback requires an explicit dispatch mode')
        valid_day(expected_day)
    mode = refresh_mode(event, requested, message, schedule)
    day = now.astimezone(ZoneInfo('America/Chicago' if mode == 'full' else 'America/Los_Angeles')).date().isoformat()
    required = event == 'schedule' or automatic
    result = {'run': 'true', 'mode': mode, 'discovery': str(mode == 'full').lower(), 'day': day,
              'claim_required': str(required).lower(),
              'reason': 'explicit change or manual request'}
    if event == 'schedule' and schedule not in FULL_SCHEDULES | DATE_SCHEDULES:
        raise ValueError('Unknown scheduled entrypoint; refusing an accidental full scan')
    if automatic and expected_day != day:
        result.update(run='false', reason=f'Automatic request for {expected_day} does not match current {mode} day {day}')
        return result  # A delayed request must not silently claim another day.
    state = read_state(root)
    latest = state.get('latest', {})
    key = mode + ':' + day
    prior = state['scheduled'].get(key)
    if prior is not None and (not isinstance(prior, dict) or not prior.get('runId')):
        raise ValueError('Malformed prior daily claim')
    if not required and prior is not None:
        return result  # Explicit recovery may run without rewriting the first claim.
    if required and mode == 'dates' and any(verified_full(receipt, day) for receipt in
                                          (latest, state['scheduled'].get('full:' + day),
                                           state.get('completed', {}).get('full:' + day))):
        result.update(run='false', reason='Morning sequence already verified today; delayed overnight refresh unnecessary')
        return result
    if required and prior is not None:
        # Even an interrupted or failed run is an attempt, not a missing schedule.
        # A normal Actions rerun must not silently launch another source scan.
        result.update(run='false', reason=f"Already attempted by run {prior['runId']} ({prior.get('conclusion', 'started')}); no duplicate scan")
        return result
    # Compatibility with an explicit run completed by the previous script,
    # which saved only latest. New completions retain a durable day/mode entry.
    if required and latest.get('mode') == mode and latest.get('day') == day and latest.get('runId'):
        result.update(run='false', reason=f"Already attempted by run {latest['runId']} ({latest.get('conclusion', 'started')}); no duplicate scan")
        return result
    state['scheduled'][key] = {'runId': str(run_id), 'attempt': str(attempt), 'mode': mode,
        'day': day, 'schedule': schedule if event == 'schedule' else '',
        'trigger': 'automatic_fallback' if automatic else event,
        'startedAt': now.isoformat(), 'conclusion': 'started'}
    save_state(root, state)
    result['claim_required'] = 'true'
    result['reason'] = ('First explicit daily attempt' if not required else
                        'Independent fallback: no daily attempt recorded' if automatic else
                        'Primary daily sequence' if schedule != '47 4 * * *' else
                        'Catch-up: no morning sequence had started')
    return result


def verify_claim(root, env):
    if env['KC_MODE'] not in {'full', 'dates'}:
        raise ValueError('Invalid daily claim mode')
    valid_day(env['KC_DAY'])
    key = env['KC_MODE'] + ':' + env['KC_DAY']
    prior = read_state(root)['scheduled'].get(key, {})
    if (prior.get('runId') != str(env['GITHUB_RUN_ID'])
            or prior.get('attempt') != str(env.get('GITHUB_RUN_ATTEMPT', '1'))
            or prior.get('conclusion') != 'started'):
        raise ValueError('This run does not own the persisted daily claim; collection refused')


def record(root, env, now):
    if env['KC_MODE'] not in {'full', 'dates'}:
        raise ValueError('Invalid daily result mode')
    valid_day(env['KC_DAY'])
    run_id = str(env['GITHUB_RUN_ID'])
    state = read_state(root)
    stages = {name: env.get('KC_' + name.upper(), '') for name in
              ('collection', 'source_save', 'build', 'deployment', 'live', 'freshness')}
    conclusion = env.get('KC_RESULT', 'failure')
    if conclusion == 'success' and (stages['live'] != 'success' or stages['freshness'] != 'success'):
        raise ValueError('Cannot record successful publication without exact live and freshness verification')
    catalog_day = env.get('KC_CATALOG_DAY', '')
    if conclusion == 'success':
        date.fromisoformat(catalog_day)  # Must come from the verified live report.
    receipt = {'runId': run_id, 'attempt': env.get('GITHUB_RUN_ATTEMPT', '1'),
        'conclusion': conclusion, 'mode': env['KC_MODE'], 'day': env['KC_DAY'],
        'finishedAt': now.isoformat(), 'stages': stages,
        'catalogDay': catalog_day,
        'savedSourceSha': env.get('KC_SOURCE_SHA', ''),
        'htmlUrl': f"https://github.com/{env['GITHUB_REPOSITORY']}/actions/runs/{run_id}"}
    latest = state.get('latest', {})
    remember_completed(state, latest)
    remember_completed(state, receipt)
    if latest.get('runId') and latest.get('mode') in {'full', 'dates'} and latest.get('day'):
        # Older workflows saved explicit attempts only in latest. Retain that
        # proof before another mode replaces it, without changing an older claim.
        previous_key = latest['mode'] + ':' + valid_day(latest['day'])
        state['scheduled'].setdefault(previous_key, dict(latest))
    key = env['KC_MODE'] + ':' + env['KC_DAY']
    prior = state['scheduled'].get(key)
    if prior is None:
        # A completed manual/push attempt counts too, including failures.
        # Preserve the first attempt if a later explicit recovery overrides it.
        # No new environment fields are required by older in-flight workflows.
        state['scheduled'][key] = dict(receipt, trigger=env.get('GITHUB_EVENT_NAME', 'completed_run'))
    elif (prior.get('runId') == run_id
          and prior.get('attempt') == receipt['attempt']):
        prior.update(receipt)
    if int(latest.get('runId', 0)) <= int(run_id):
        state['latest'] = receipt
    save_state(root, state)
    # Preserve the existing public-monitor contract, now written within the lock.
    target = root / 'live-deploy-status.json'
    old = json.loads(target.read_text()) if target.exists() else {}
    if int(old.get('run_id', 0)) <= int(run_id):
        target.write_text(json.dumps({'run_id': int(run_id), 'conclusion': conclusion,
            'head_sha': env.get('GITHUB_SHA', ''), 'html_url': receipt['htmlUrl'],
            'captured_at': now.isoformat(), 'stages': stages}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['claim', 'record', 'verify-claim'])
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.command == 'record':
        record(Path.cwd(), os.environ, now)
    elif args.command == 'verify-claim':
        verify_claim(Path.cwd(), os.environ)
    else:
        result = claim(Path.cwd(), os.getenv('GITHUB_EVENT_NAME', ''), os.getenv('KC_SCHEDULE', ''),
                       os.getenv('KC_REQUESTED_MODE', ''), os.getenv('KC_COMMIT_MESSAGE', ''),
                       os.environ['GITHUB_RUN_ID'], os.getenv('GITHUB_RUN_ATTEMPT', '1'), now,
                       os.getenv('KC_AUTOMATIC_FALLBACK', ''), os.getenv('KC_EXPECTED_DAY', ''))
        output = os.getenv('GITHUB_OUTPUT')
        if output:
            with open(output, 'a') as handle:
                handle.write(''.join(f'{key}={value}\n' for key, value in result.items()))
        print(json.dumps(result))


if __name__ == '__main__':
    main()
