#!/usr/bin/env python3
"""Replay reviewed source operations on a fresh checkout after a bot push race."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

CURATION = ['apply_curated_catalog_policy.py', 'apply_sep13_content_repairs.py',
    'apply_miles_cj_fall_2026_repairs.py', 'apply_trnscnd_submission.py',
    'apply_rock_the_pines.py', 'apply_egr_bizzle_updates.py',
    'apply_man_of_faith_joz_shows.py', 'apply_sep26_source_corrections.py']
SOURCE_REPAIRS = ['apply_curated_catalog_policy.py', 'apply_sep12_live_audit_repairs.py',
    'permanent_state_pages.py --source .', 'prune_past_events.py --source .',
    'apply_sevin_official_schedule.py', 'apply_live_artist_overrides.py --source .',
    'apply_deonte_hall_submission.py', *CURATION[1:],
    'apply_oct2_verified_shows.py', 'apply_oct3_concert_corrections.py']


def run(script):
    subprocess.run([sys.executable, 'scripts/' + script.split()[0], *script.split()[1:]], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['catalog', 'full', 'websites', 'fall', 'audit', 'status'])
    kind = parser.parse_args().kind
    if kind == 'catalog':
        for script in CURATION: run(script)
    elif kind == 'fall':
        run('ensure_verified_fall_2026_shows.py')
        run('apply_miles_cj_fall_2026_repairs.py')
    elif kind == 'audit':
        for script in ['enforce_sep11_catalog_audit.py', 'sync_verified_artist_registry.py', 'enforce_sep11_catalog_audit.py']: run(script)
        subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-q'], check=True)
    elif kind in ('full', 'websites'):
        run('sync_verified_artist_registry.py')
        if kind == 'websites': run('sync_verified_artist_websites.py')
        subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-q'], check=True)
        if kind == 'full' or os.environ.get('GITHUB_EVENT_NAME') == 'push':
            config = Path('config/official-sources.json')
            original = config.read_bytes()
            try:
                run('apply_priority_source_fallbacks.py')
                run('update_events.py')
                if kind == 'full': run('scan_all_artist_sources.py')
                for script in SOURCE_REPAIRS if kind == 'full' else ['apply_curated_catalog_policy.py', 'apply_sevin_official_schedule.py']:
                    run(script)
            finally:
                config.write_bytes(original)
        if kind == 'websites':
            run('collect_artist_website_events.py')
            run('merge_artist_website_events.py')
            subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-q'], check=True)
    else:
        import json
        from datetime import datetime, timezone
        path = Path('live-deploy-status.json')
        old = json.loads(path.read_text()) if path.exists() else {}
        # An older completion must not replace the receipt for a newer run.
        if int(old.get('run_id', 0)) > int(os.environ['RUN_ID']): return
        path.write_text(json.dumps({'run_id': int(os.environ['RUN_ID']),
            'conclusion': os.environ['RESULT'], 'head_sha': os.environ['HEAD_SHA'],
            'html_url': os.environ['RUN_URL'],
            'captured_at': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n')


if __name__ == '__main__':
    main()
