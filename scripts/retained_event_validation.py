"""Read completed records for validation without restoring them to upcoming feeds."""
import json
from pathlib import Path

try:
    from .prune_past_events import is_past_event, today_cutoff
except ImportError:
    from prune_past_events import is_past_event, today_cutoff


def completed_history_event(root, event_id, cutoff=None):
    path = Path(root) / 'event-history.json'
    if not path.is_file():
        return None
    entries = json.loads(path.read_text(encoding='utf-8'))['events']
    matches = [entry['event'] for entry in entries if entry['event'].get('id') == event_id]
    if len(matches) > 1:
        raise ValueError(f'Duplicate retained event ID: {event_id}')
    if matches and is_past_event(matches[0], cutoff or today_cutoff()):
        return matches[0]
    return None
