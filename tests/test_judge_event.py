import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_seo_site as builder
from finalize_seo_indexing import repair_event_schema


class JudgeEventTests(unittest.TestCase):
    def test_judges_are_visible_and_linked_but_never_schema_performers(self):
        event = next(e for e in json.loads((ROOT / 'config/manual-events.json').read_text())
                     if e.get('id') == 'whos-got-talent-kissimmee-2026-10-24')
        roster = [{'name':'Biancallove'}, {'name':'GIOVANI'}]
        card = builder.event_card(event, roster)
        self.assertIn('>Event</span>', card)
        self.assertIn('<strong>Judges:</strong>', card)
        self.assertIn('/artists/biancallove/', card)
        self.assertIn('/artists/giovani/', card)
        self.assertIn('<span>Pastor Nomar Ayala</span>', card)
        schema = builder.event_schema(event)
        self.assertEqual(schema['@type'], 'Event')
        self.assertNotIn('performer', schema)
        self.assertEqual(schema['startDate'], '2026-10-24T19:00:00-04:00')
        stale = copy.deepcopy(schema)
        stale.update({'@type':'MusicEvent', 'performer':[{'name':n} for n in event['officialBill']]})
        self.assertTrue(repair_event_schema(stale, event))
        self.assertEqual(stale['@type'], 'Event')
        self.assertNotIn('performer', stale)
        self.assertFalse(repair_event_schema(stale, event))


if __name__ == '__main__':
    unittest.main()
