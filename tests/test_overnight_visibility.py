"""A confirmed overnight ending must agree across daily publication surfaces."""
import copy
from datetime import date, datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import event_visibility as visibility
import prune_past_events as pruning
import build_seo_site as builder
import add_past_show_archives as archive
import canadian_event_guard as canadian
import update_events as collector


def overnight(**changes):
    return dict(id='fixture:overnight', title='Overnight showcase',
                startDate='2026-11-13', endDate='2026-11-14',
                startTime='22:00', endTime='01:00',
                startDateTime='2026-11-13T22:00:00-06:00',
                endDateTime='2026-11-14T01:00:00-06:00',
                country='CA', state='AB', city='Calgary', venue='Confirmed hall',
                artists=['Fixture artist'], confidence='high',
                **changes)


class OvernightVisibilityTests(unittest.TestCase):
    def test_accepted_end_is_completed_at_pacific_rollover_without_rewriting_dates(self):
        event = overnight()
        original = copy.deepcopy(event)
        self.assertEqual('2026-11-13', visibility.event_last_active_date(event))
        self.assertFalse(pruning.is_past_event(event, '2026-11-13'))
        self.assertTrue(pruning.is_past_event(event, '2026-11-14'))
        with patch.object(builder, 'VISIBILITY_CUTOFF', date(2026, 11, 14)):
            self.assertFalse(builder.current(event))
        self.assertFalse(collector.event_is_future(event, date(2026, 11, 14)))
        self.assertEqual([], canadian.upcoming_canadian([event], '2026-11-14'))
        self.assertEqual(date(2026, 11, 13), archive.event_date(event))
        self.assertEqual(original, event)

    def test_exact_midnight_is_completed_but_one_second_later_remains_that_day(self):
        event = overnight()
        event.update(endDateTime='2026-11-14T00:00:00-08:00', endTime='00:00')
        self.assertEqual('2026-11-13', visibility.event_last_active_date(event))
        event.update(endDateTime='2026-11-14T00:00:01-08:00', endTime='00:00:01')
        self.assertEqual('2026-11-14', visibility.event_last_active_date(event))

    def test_actual_multiday_and_unknown_end_clocks_remain(self):
        for changes in (
            {'endDate': '2026-11-15', 'endTime':'20:00', 'endDateTime':'2026-11-15T20:00:00-06:00'},
            {'endDateTime': ''}, {'endDateTime': '2026-11-14T01:00:00'},
            {'endDateTime': 'unconfirmed'},
        ):
            event = {**overnight(), **changes}
            self.assertFalse(pruning.is_past_event(event, '2026-11-14'))
        self.assertFalse(visibility.event_is_past({'startDate':'2026-02-30'}, '2026-11-14'))

    def test_contradictory_dates_clocks_and_reversed_instants_do_not_remove_early(self):
        for changes in (
            {'endDateTime': '2026-11-13T23:00:00-06:00'},
            {'endTime': '03:00'}, {'endTime': 'unconfirmed'},
            {'startDateTime': '2026-11-14T02:00:00-06:00'},
            {'startDate': '2026-11-15'},
        ):
            event = {**overnight(), **changes}
            self.assertEqual('2026-11-14', visibility.event_last_active_date(event))

    def test_schema_and_display_keep_actual_dates_while_cards_use_visibility_boundary(self):
        event = overnight()
        card = builder.event_card(event, [])
        self.assertIn('data-date="2026-11-13"', card)
        self.assertIn('data-end-date="2026-11-13"', card)
        self.assertIn('Nov 13', card)
        schema = builder.event_schema(event)
        self.assertEqual(event['endDateTime'], schema['endDate'])
        self.assertEqual(event['startDateTime'], schema['startDate'])
        page = '<script type="application/ld+json">' + json.dumps(schema) + '</script>'
        self.assertEqual('2026-11-13', pruning.page_last_date(page))

    def test_source_and_artifact_pruning_remove_only_completed_overnight(self):
        completed = overnight()
        ongoing = {**overnight(), 'id':'fixture:continuing', 'endDate':'2026-11-15',
                   'endDateTime':'2026-11-15T01:00:00-06:00'}
        history = {'events':[{'event':copy.deepcopy(completed), 'observedOnOrAfterEventDate':True}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'events.json').write_text(json.dumps([completed,ongoing]))
            (root/'event-history.json').write_text(json.dumps(history))
            history_bytes = (root/'event-history.json').read_bytes()
            report = pruning.prune_source(root, '2026-11-14')
            self.assertEqual(1, report['removed'])
            self.assertEqual([ongoing], json.loads((root/'events.json').read_text()))
            self.assertEqual(history_bytes,(root/'event-history.json').read_bytes())
            page = root/'event/fixture/index.html'; page.parent.mkdir(parents=True)
            page.write_text('<script type="application/ld+json">'+json.dumps(builder.event_schema(completed))+'</script>')
            self.assertEqual({'fixture'}, pruning.remove_past_event_pages(root, '2026-11-14'))

    def test_archive_selects_completed_overnight_and_preserves_original_record(self):
        event = overnight()
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026,11,14,8,0,tzinfo=tz)
        with tempfile.TemporaryDirectory() as tmp, patch.object(archive.dt,'datetime',FixedDateTime):
            root = Path(tmp)
            history = {'events':[{'event':event, 'observedOnOrAfterEventDate':True}]}
            (root/'event-history.json').write_text(json.dumps(history))
            selected, _ = archive.load_events(root)
            self.assertEqual([event], selected)
            self.assertEqual(history,json.loads((root/'event-history.json').read_text()))


if __name__ == '__main__':
    unittest.main()
