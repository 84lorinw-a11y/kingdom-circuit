#!/usr/bin/env python3
"""Durable, fail-closed daily claims for the one GitHub publication workflow.

The fallback schedule may claim a missing daily run, never retry a recorded
attempt. All callers hold kingdom-circuit-pages concurrency until the final
receipt is saved. Explicit manual runs remain available for reviewed recovery.
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


def read_state(root):
    path = root / STATE
    state = json.loads(path.read_text()) if path.exists() else {'schemaVersion': 1, 'scheduled': {}}
    if not isinstance(state, dict) or state.get('schemaVersion') != 1 or not isinstance(state.get('scheduled'), dict):
        raise ValueError('Invalid daily publication receipt; refusing to discard prior claims')
    return state


def save_state(root, state):
    (root / STATE).write_text(json.dumps(state, indent=2) + '\n')


def claim(root, event, schedule, requested, message, run_id, attempt, now):
    mode = refresh_mode(event, requested, message, schedule)
    day = now.astimezone(ZoneInfo('America/Chicago' if mode == 'full' else 'America/Los_Angeles')).date().isoformat()
    result = {'run': 'true', 'mode': mode, 'discovery': str(mode == 'full').lower(), 'day': day,
              'reason': 'explicit change or manual request'}
    if event != 'schedule':
        return result
    if schedule not in FULL_SCHEDULES | DATE_SCHEDULES:
        raise ValueError('Unknown scheduled entrypoint; refusing an accidental full scan')
    state = read_state(root)
    latest = state.get('latest', {})
    if (mode == 'dates' and latest.get('mode') == 'full'
            and latest.get('conclusion') == 'success'
            and latest.get('catalogDay') == day
            and latest.get('stages', {}).get('freshness') == 'success'):
        result.update(run='false', reason='Morning sequence already verified today; delayed overnight refresh unnecessary')
        return result
    key = mode + ':' + day
    prior = state['scheduled'].get(key)
    if prior is not None:
        # Even an interrupted or failed run is an attempt, not a missing schedule.
        # A normal Actions rerun must not silently launch another source scan.
        if not isinstance(prior, dict) or not prior.get('runId'):
            raise ValueError('Malformed prior daily claim')
        result.update(run='false', reason=f"Already attempted by run {prior['runId']} ({prior.get('conclusion', 'started')}); no duplicate scan")
        return result
    state['scheduled'][key] = {'runId': str(run_id), 'attempt': str(attempt), 'mode': mode,
        'day': day, 'schedule': schedule, 'startedAt': now.isoformat(), 'conclusion': 'started'}
    save_state(root, state)
    result['reason'] = 'Primary daily sequence' if schedule != '47 4 * * *' else 'Catch-up: no morning sequence had started'
    return result


def verify_claim(root, env):
    key = env['KC_MODE'] + ':' + env['KC_DAY']
    prior = read_state(root)['scheduled'].get(key, {})
    if prior.get('runId') != str(env['GITHUB_RUN_ID']):
        raise ValueError('This run does not own the persisted daily claim; collection refused')


def record(root, env, now):
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
    key = env['KC_MODE'] + ':' + env['KC_DAY']
    prior = state['scheduled'].get(key)
    if prior and prior.get('runId') == run_id:
        prior.update(receipt)
    latest = state.get('latest', {})
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
                       os.environ['GITHUB_RUN_ID'], os.getenv('GITHUB_RUN_ATTEMPT', '1'), now)
        output = os.getenv('GITHUB_OUTPUT')
        if output:
            with open(output, 'a') as handle:
                handle.write(''.join(f'{key}={value}\n' for key, value in result.items()))
        print(json.dumps(result))


if __name__ == '__main__':
    main()
