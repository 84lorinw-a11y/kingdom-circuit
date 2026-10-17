import unittest
from tests.catalog_history import append_completed


class CompletedCatalogRegressionTests(unittest.TestCase):
    def test_only_expected_completed_missing_records_can_be_used(self):
        rows = [{'id': 'present', 'startDate': '2000-01-01', 'title': 'Current value'}]
        history = [{'event': row} for row in [
            {'id': 'present', 'startDate': '2000-01-01', 'title': 'Older value'},
            {'id': 'past', 'startDate': '2000-01-01'},
            {'id': 'future', 'startDate': '9999-01-01'},
            {'id': 'ongoing', 'startDate': '2000-01-01', 'endDate': '9999-01-01'},
            {'id': 'unrelated', 'startDate': '2000-01-01'},
            {'id': 'unknown-date'},
        ]]
        result = append_completed(rows, history, {'present', 'past', 'future', 'ongoing', 'unknown-date'}, '2026-10-17')
        self.assertEqual(['present', 'past'], [r['id'] for r in result])
        self.assertEqual('Current value', result[0]['title'])
        self.assertEqual(1, len(rows))

    def test_multiday_show_is_retained_until_the_day_after_its_end(self):
        history = [{'event': {'id': 'festival', 'startDate': '2026-10-16', 'endDate': '2026-10-18'}}]
        self.assertEqual([], append_completed([], history, {'festival'}, '2026-10-18'))
        self.assertEqual(1, len(append_completed([], history, {'festival'}, '2026-10-19')))
