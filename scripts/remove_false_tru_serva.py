#!/usr/bin/env python3
"""Existing reviewed event guard, shared by first attempt and race-safe replay."""
import json
import os
from pathlib import Path

FALSE_ID = 'supplemental:tru-serva-truth-tour-las-cruces-2026'
changed = False

for file_name in ('supplemental-events.json', 'events.json', 'config/manual-events.json'):
    path = Path(file_name)
    if not path.exists():
        continue
    original = path.read_text(encoding='utf-8')
    rows = json.loads(original)
    before = len(rows)
    rows = [
        e for e in rows
        if not (
            str(e.get('id') or '') == FALSE_ID
            or (
                str(e.get('title') or '').strip() == 'The Truth Tour — Las Cruces'
                and str(e.get('startDate') or '') == '2026-10-25'
                and any(str(a).strip().casefold() == 'tru-serva' for a in (e.get('artists') or []))
            )
        )
    ]
    if len(rows) != before:
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'{file_name}: removed {before - len(rows)} false listing(s)')
        changed = True

# Official sources identify this as Megan Woods' Truth Tour, not a TRU-SERVA date.
guard = Path('data/verified-false-matches.json')
guard.parent.mkdir(parents=True, exist_ok=True)
existing = []
if guard.exists():
    try:
        existing = json.loads(guard.read_text(encoding='utf-8'))
    except Exception:
        existing = []
marker = {
    'key': 'tru-serva|2026-10-25|las-cruces-nm',
    'artist': 'TRU-SERVA',
    'date': '2026-10-25',
    'city': 'Las Cruces',
    'state': 'NM',
    'reason': "False artist match: Real Life Church, Megan Woods, Ticketmaster, and Live Nation identify this as Megan Woods' The Truth Tour; TRU-SERVA is not on the official lineup.",
    'officialEventUrl': 'https://www.livenation.com/event/rZ7HnEZ1AfFpGV/megan-woods-the-truth-tour-las-cruces-nm',
    'verified': '2026-09-15'
}
existing = [x for x in existing if x.get('key') != marker['key']]
existing.append(marker)
guard_text = json.dumps(existing, indent=2, ensure_ascii=False) + '\n'
old_guard = guard.read_text(encoding='utf-8') if guard.exists() else ''
if old_guard != guard_text:
    guard.write_text(guard_text, encoding='utf-8')
    changed = True

with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
    out.write(f'changed={str(changed).lower()}\n')

