"""Organizer domains survive refreshes and agree in visible and Google markup."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_oct3_concert_corrections as replay
import show_information as show
from show_information_model import normalize
from test_show_information import fixture, record


class OrganizerUrlTests(unittest.TestCase):
    def test_reviewed_promoter_urls_survive_stale_feed_and_repeated_refresh(self):
        seeds = [row for row in json.loads((ROOT / 'config/oct3-verified-concerts.json').read_text())
                 if row.get('editorialBatch') == '2026-11-09-jackie-blameless-tour']
        self.assertEqual(len(seeds), 15)
        expected = {
            'jackie-hill-perry-blameless-chicago-2027-02-26': 'TPR.',
            'jackie-hill-perry-blameless-orlando-2027-03-06': 'TPR Presents',
        }
        stale = deepcopy(seeds)
        for row in stale:
            if row['id'] in expected:
                row['organizer'] = expected[row['id']]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config').mkdir()
            for name, value in (
                ('config/oct3-verified-concerts.json', seeds),
                ('config/manual-events.json', stale),
                ('events.json', [dict(row, id='manual:' + row['id']) for row in stale]),
                ('supplemental-events.json', []),
                ('event-history.json', {'events': [{'event': row} for row in stale]}),
            ):
                (root / name).write_text(json.dumps(value))
            replay.apply(root, today='2026-11-10')
            for name in ('config/manual-events.json', 'events.json', 'event-history.json'):
                rows = json.loads((root / name).read_text())
                if isinstance(rows, dict):
                    rows = [entry['event'] for entry in rows['events']]
                self.assertEqual(len(rows), 15)
                for row in rows:
                    identity = row['id'].removeprefix('manual:')
                    if identity in expected:
                        self.assertEqual(row['organizer'], {'name': expected[identity], 'url': 'https://tprlive.co/'})
                        self.assertEqual(normalize(row)['organizerUrl'], 'https://tprlive.co/')
                    else:
                        self.assertNotIn('organizer', row)
            before = {path: path.read_bytes() for path in root.rglob('*.json')}
            replay.apply(root, today='2026-11-10')
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob('*.json')})

    def test_final_check_rejects_missing_or_wrong_schema_and_visible_organizer_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / 'assets').mkdir()
            (site / 'config').mkdir()
            (site / 'event/sample').mkdir(parents=True)
            current = {**record(organizer={'name': 'TPR.', 'url': 'https://tprlive.co/'}),
                       'canonicalPath': '/event/sample/'}
            (site / 'events.json').write_text(json.dumps([current]))
            (site / 'supplemental-events.json').write_text('[]')
            (site / 'config/artists.json').write_text('[]')
            (site / 'assets/fan-show-catalog.json').write_text(json.dumps({
                'shows': [{'path': '/event/sample/', 'date': '2027-01-29'}]}))
            page = site / 'event/sample/index.html'
            page.write_text(fixture())
            show.build(site)
            correct = page.read_text()
            for kind in ('schema-missing', 'schema-wrong', 'visible-missing', 'visible-wrong'):
                with self.subTest(kind=kind):
                    if kind.startswith('schema'):
                        node, value = show.schema_blocks(correct)[0]
                        organizer = next(show.event_schemas(value))['organizer']
                        if kind == 'schema-missing':
                            organizer.pop('url')
                        else:
                            organizer['url'] = 'https://wrong.example/'
                        changed = correct[:node.opening_end] + json.dumps(value) + correct[node.closing_start:]
                        message = 'Organizer schema URL mismatch'
                    else:
                        doc = show.Document(correct)
                        row = doc.one(lambda n: 'data-kc-organizer' in n.attrs)
                        link = next(n for n in doc.nodes if n.tag == 'a' and row.start < n.start < row.end)
                        replacement = doc.text(link) if kind == 'visible-missing' else correct[link.start:link.end].replace('https://tprlive.co/', 'https://wrong.example/')
                        changed = correct[:link.start] + replacement + correct[link.end:]
                        message = 'Organizer visible link mismatch'
                    page.write_text(changed)
                    with self.assertRaisesRegex(AssertionError, message):
                        show.verify(site)
            page.write_text(correct)
            show.verify(site)


if __name__ == '__main__':
    unittest.main()
