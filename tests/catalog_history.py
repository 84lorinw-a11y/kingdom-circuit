"""Historical regression inputs, not a fallback for the public calendar.

Reviewed event tests must keep exercising completed shows without requiring
them to remain in the upcoming feed forever. Only the previously tested IDs
in the manifest may fall back to retained history, and only AFTER their end
date. Existing runtime rows always win, including incorrect rows; future or
ongoing missing shows remain missing and therefore still fail their tests.
This helper never writes to or repairs production data.
"""
import json
from pathlib import Path
from scripts.prune_past_events import is_past_event, today_cutoff

ROOT = Path(__file__).resolve().parents[1]


def append_completed(rows, history, expected_ids, cutoff):
    result = list(rows)
    present = {row.get('id') for row in result}
    for entry in history:
        event = entry['event']
        event_id = event.get('id')
        if event_id in expected_ids and event_id not in present and is_past_event(event, cutoff):
            result.append(event)
            present.add(event_id)
    return result


def load_catalog(path):
    path = Path(path)
    rows = json.loads(path.read_text(encoding='utf-8'))
    if path.name not in ('events.json', 'supplemental-events.json'):
        return rows
    expected = json.loads((ROOT / 'tests/fixtures/catalog-regression-ids.json').read_text())
    history = json.loads((ROOT / 'event-history.json').read_text())['events']
    return append_completed(rows, history, set(expected[path.name]), today_cutoff())
