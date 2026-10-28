import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_seo_site import event_path
from finalize_event_schedules import apply
from finalize_seo_indexing_core import concert_start_only


class EventSchedulesTest(unittest.TestCase):
    def test_prejam_is_distinct_from_main_show_and_survives_final_cleanup(self):
        event = {'id': 'manual:example', 'title': 'Example', 'city': 'Duluth',
                 'startDate': '2027-01-17', 'startTime': '17:00',
                 'scheduleDetails': [{'label': 'General entry', 'text': '4:00 PM'},
                                     {'label': 'Pre-Jam begins', 'text': '4:00 PM'},
                                     {'label': 'Main show', 'text': '5:00 PM'}],
                 'scheduleNote': 'CJ Emulous is part of Pre-Jam. All times local.'}
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / 'events.json').write_text(json.dumps([event]))
            page = site / event_path(event).strip('/') / 'index.html'
            page.parent.mkdir(parents=True)
            original = '<dl class="detail-list"><div><dt>Date</dt><dd>January 17</dd></div></dl>'
            page.write_text(original)
            untouched = site / 'other.html'
            untouched.write_text(original)
            apply(site)
            first = page.read_text()
            apply(site)
            self.assertEqual(first, page.read_text())
            self.assertEqual(original, untouched.read_text())
            cleaned = concert_start_only(first)
            self.assertIn('<dt>Pre-Jam begins</dt><dd>4:00 PM</dd>', cleaned)
            self.assertIn('<dt>Main show</dt><dd>5:00 PM</dd>', cleaned)
            self.assertIn('<dt>General entry</dt><dd>4:00 PM</dd>', cleaned)
            self.assertEqual(cleaned.count('data-kc-event-schedule'), 1)
            self.assertIn('CJ Emulous', cleaned)

    def test_source_text_is_escaped(self):
        event = {'id': 'manual:escape', 'title': 'Example', 'city': 'Duluth',
                 'startDate': '2027-01-17',
                 'scheduleDetails': [{'label': 'Address', 'text': '<b>Venue & Hall</b>'}]}
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / 'events.json').write_text(json.dumps([event]))
            page = site / event_path(event).strip('/') / 'index.html'
            page.parent.mkdir(parents=True)
            page.write_text('<dl class="detail-list"></dl>')
            apply(site)
            self.assertIn('&lt;b&gt;Venue &amp; Hall&lt;/b&gt;', page.read_text())


if __name__ == '__main__':
    unittest.main()
