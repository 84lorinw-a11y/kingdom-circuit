import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from apply_mayia_postponement import apply, EVENT_ID, SOURCE
from build_seo_site import scheduled, event_schema


class MayiaPostponementTests(unittest.TestCase):
    def test_stale_calendar_and_new_provider_id_cannot_revive_original_dates(self):
        original = dict(id=EVENT_ID, title='MAYIA at Songs That Speak Conference',
                        startDate='2026-10-23', startTime='16:00', city='Pleasant Garden',
                        artists=['MAYIA'], status='scheduled', firstSeen='2026-09-22')
        duplicate = dict(original, id='bandsintown:new-id', startDate='2026-10-24')
        later = dict(original, startDate='2027-02-20')
        other = dict(original, id='another-mayia-show', title='Another MAYIA show')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'config').mkdir()
            for f in ('config/manual-events.json','events.json','supplemental-events.json'):
                (root/f).write_text(json.dumps([original, duplicate, later, other]))
            (root/'event-history.json').write_text(json.dumps({'events':[{'event':original}]}))
            apply(root)
            for f in ('config/manual-events.json','events.json','supplemental-events.json'):
                rows=json.loads((root/f).read_text())
                for event in rows[:2]:
                    self.assertFalse(scheduled(event))
                    self.assertEqual(event['status'],'postponed')
                    self.assertEqual(event_schema(event)['eventStatus'],'https://schema.org/EventPostponed')
                    self.assertEqual(event['officialUrl'], SOURCE)
                    self.assertEqual(event['firstSeen'], '2026-09-22')
                self.assertEqual(rows[2:], [later,other])
            self.assertEqual(json.loads((root/'event-history.json').read_text())['events'][0]['event']['status'],'postponed')
            before={p:p.read_bytes() for p in root.rglob('*.json')}
            apply(root)
            self.assertEqual(before,{p:p.read_bytes() for p in before})
