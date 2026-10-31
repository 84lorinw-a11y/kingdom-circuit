"""Canadian bookings must survive U.S.-only collectors and automated publication."""
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collect_bandsintown_rest as collector
import run_bandsintown_refresh as refresh
import add_past_show_archives as archives
import canadian_event_guard as guard
from build_seo_site import event_path
from prune_past_events import prune_source
import test_automation_publication as publication_tests
from scripts.publish_automation_changes import git, publish


def canadian_show(**changes):
    event = dict(id='bandsintown:canadian-booking', title='Light Up The City',
                 country='CA', state='SK', city='Lloydminster', venue='ACTS Church',
                 startDate='2099-02-26', endDate='2099-02-27', artists=['Ant Lee'],
                 authority='artist_calendar', confidence='high', status='scheduled')
    return dict(event, **changes)


class CanadianEventPreservationTests(unittest.TestCase):
    def test_us_only_bandsintown_refresh_does_not_own_canadian_rows(self):
        for country in ['CA', 'CAN', 'Canada']:
            with self.subTest(country=country):
                self.assertFalse(refresh.is_refreshable_bit(canadian_show(country=country)))
        self.assertTrue(refresh.is_refreshable_bit(canadian_show(country='US', state='CA')))

    def test_successful_empty_bandsintown_refresh_retains_canadian_record(self):
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                rows = [canadian_show(), canadian_show(id='bandsintown:second', authority='')]
                for file, data in [('artists.json', []), ('events.json', []),
                                   ('supplemental.json', rows), ('status.json', {})]:
                    (root / file).write_text(json.dumps(data))
                with patch.multiple(collector, ARTISTS_FILE=root/'artists.json',
                                    EVENTS_FILE=root/'events.json', SUPPLEMENTAL_FILE=root/'supplemental.json',
                                    STATUS_FILE=root/'status.json', CANDIDATES_FILE=root/'candidates.json'), \
                     patch.multiple(refresh, SUPPLEMENTAL=root/'supplemental.json', STATUS=root/'status.json'):
                    (refresh.main if wrapped else collector.main)()
                self.assertEqual(rows, json.loads((root/'supplemental.json').read_text()))

    def test_multiday_show_stays_through_final_day_then_can_roll_off(self):
        event = canadian_show()
        self.assertTrue(guard.retention_errors([event], [], '2099-02-27'))
        self.assertEqual([], guard.retention_errors([event], [], '2099-02-28'))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'supplemental-events.json').write_text(json.dumps([event]))
            prune_source(root, '2099-02-27')
            self.assertEqual([event], guard.read_events(root))
            prune_source(root, '2099-02-28')
            self.assertEqual([], guard.read_events(root))

    def test_cancellations_and_explicit_duplicate_aliases_remain_possible(self):
        event = canadian_show()
        cancelled = dict(event, status='cancelled')
        self.assertEqual([], guard.retention_errors([event], [cancelled], '2099-02-26'))
        self.assertEqual([], guard.catalog_errors([cancelled], {'shows':[]}, '2099-02-26'))
        merged = dict(event, id='official:canonical', mergedFromIds=[event['id']])
        self.assertEqual([], guard.retention_errors([event], [merged], '2099-02-26'))
        self.assertTrue(guard.retention_errors([event], [dict(event, country='US')], '2099-02-26'))

    def test_all_current_canadian_bookings_must_reach_shared_catalog(self):
        events = [canadian_show(), *guard.upcoming_canadian(guard.read_events(ROOT), guard.today_cutoff())]
        catalog = {'shows':[{'path':event_path(event)} for event in events]}
        self.assertEqual([], guard.catalog_errors(events, catalog, guard.today_cutoff()))
        for event in events:
            with self.subTest(event=event['id']):
                missing = {'shows':[row for row in catalog['shows'] if row['path'] != event_path(event)]}
                self.assertTrue(guard.catalog_errors(events, missing, guard.today_cutoff()))

    def test_date_and_full_workflows_both_guard_source_and_final_artifact(self):
        workflow = (ROOT/'.github/workflows/update-and-deploy.yml').read_text()
        snapshot = workflow.index('- name: Snapshot Canadian bookings')
        collect = workflow.index('- name: Collect upcoming shows')
        validate = workflow.index('- name: Validate refreshed source before publication')
        save = workflow.index('- name: Save refreshed event data')
        final = workflow.index('- name: Verify Canadian bookings survived')
        upload = workflow.index('- name: Upload Pages artifact')
        self.assertLess(snapshot, collect)
        self.assertLess(validate, save)
        self.assertLess(final, upload)
        for start in (snapshot, validate, final):
            block = workflow[start:].split('\n      - name:', 1)[0]
            self.assertIn('scripts/canadian_event_guard.py', block)
            self.assertNotIn('if:', block)

    def test_bot_cannot_publish_missing_upcoming_canadian_show(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote, owner, bot = publication_tests.AutomationPublicationTests().setup_repo(tmp)
            (owner/'supplemental-events.json').write_text(json.dumps([canadian_show()]))
            git(owner, 'add', '.'); git(owner, 'commit', '-m', 'Verified Canadian show')
            git(owner, 'push', 'origin', 'main')
            git(bot, 'pull', '--ff-only')
            before = git(remote, 'rev-parse', 'main').stdout
            (bot/'supplemental-events.json').write_text('[]')
            with self.assertRaisesRegex(RuntimeError, 'Canadian'):
                publish(bot, ['supplemental-events.json'], ['python repair.py'], 'Do not remove Canada')
            self.assertEqual(before, git(remote, 'rev-parse', 'main').stdout)

    def test_completed_canadian_show_is_available_to_public_archive(self):
        yesterday = (dt.datetime.now(archives.PACIFIC).date()-dt.timedelta(days=1)).isoformat()
        event = canadian_show(startDate=yesterday, endDate=yesterday)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'event-history.json').write_text(json.dumps({'events':[
                {'event':event, 'observedOnOrAfterEventDate':True}]}))
            selected, _ = archives.load_events(root)
            self.assertEqual([event], selected)


if __name__ == '__main__':
    unittest.main()
