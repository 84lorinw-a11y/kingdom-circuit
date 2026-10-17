import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from scripts.retained_event_validation import completed_history_event

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import apply_sep11_catalog_audit as audit
import apply_echo_nights_official as echo


class RetainedValidationTests(unittest.TestCase):
    def test_only_completed_unique_history_can_satisfy_an_absent_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [{'id':'past','startDate':'2026-10-01'},
                    {'id':'ongoing','startDate':'2026-10-01','endDate':'2026-10-20'},
                    {'id':'future','startDate':'2026-11-01'}, {'id':'unknown'}]
            (root/'event-history.json').write_text(json.dumps({'events':[{'event':e} for e in rows]}))
            cutoff = '2026-10-17'
            self.assertEqual('past',completed_history_event(root,'past',cutoff)['id'])
            for event_id in ('ongoing','future','unknown','missing'):
                self.assertIsNone(completed_history_event(root,event_id,cutoff))
            (root/'event-history.json').write_text(json.dumps({'events':[{'event':rows[0]},{'event':rows[0]}]}))
            with self.assertRaisesRegex(ValueError,'Duplicate retained event'):
                completed_history_event(root,'past',cutoff)

    def test_existing_bad_record_is_not_masked_by_good_history(self):
        with patch('retained_event_validation.completed_history_event', return_value={'id':'a','artists':['Correct']}):
            with self.assertRaisesRegex(SystemExit,'missing artists'):
                audit.assert_event([{'id':'a','artists':['Wrong']}],'a',['Correct'])

    def test_missing_future_record_still_fails(self):
        with patch('retained_event_validation.completed_history_event',return_value=None):
            with self.assertRaisesRegex(SystemExit,'Expected one'):
                audit.assert_event([], 'missing', ['Artist'])

    def test_echo_history_validation_never_recreates_runtime_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for filename in echo.SOURCE_FILES:
                (root/filename).write_text('[]\n')
            record={'id':echo.EVENT_ID,'image':echo.IMAGE,'officialUrl':echo.TICKET_URL}
            with patch('retained_event_validation.completed_history_event',return_value=record):
                self.assertEqual(0,echo.enforce_json(root))
            for filename in echo.SOURCE_FILES:
                self.assertEqual('[]\n',(root/filename).read_text())
            with patch('retained_event_validation.completed_history_event',return_value={**record,'image':'wrong'}):
                with self.assertRaisesRegex(SystemExit,'do not match'):
                    echo.enforce_json(root)


if __name__ == '__main__':
    unittest.main()
