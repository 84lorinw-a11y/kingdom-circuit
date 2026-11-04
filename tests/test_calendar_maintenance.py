import copy
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import calendar_maintenance as maintenance
from build_seo_site import event_path


class CalendarMaintenanceTests(unittest.TestCase):
    def test_midnight_schedule_never_discovers_and_5am_dispatch_still_does(self):
        self.assertEqual(maintenance.refresh_mode('schedule', '', ''), 'dates')
        self.assertEqual(maintenance.refresh_mode('workflow_dispatch', '', ''), 'full')
        self.assertEqual(maintenance.refresh_mode('workflow_dispatch', 'dates', ''), 'dates')
        self.assertEqual(maintenance.refresh_mode('push', '', 'fix page'), 'dates')
        self.assertEqual(maintenance.refresh_mode('push', '', 'refresh [full scan]'), 'full')

    def test_freshness_detects_stale_catalog_expired_dates_and_duplicate_paths(self):
        good={'asOf':'2026-10-24','shows':[{'path':'/event/a/','date':'2026-10-21','end':'2026-10-24'}]}
        self.assertEqual(maintenance.catalog_errors(good, '2026-10-24'), [])
        bad={'asOf':'2026-10-23','shows':[{'path':'/event/a/','date':'2026-10-23'}, {'path':'/event/a/','date':'2026-10-23'}]}
        failures=maintenance.catalog_errors(bad,'2026-10-24')
        self.assertTrue(any('asOf' in e for e in failures))
        self.assertTrue(any('expired' in e for e in failures))
        self.assertTrue(any('duplicate' in e for e in failures))

    def test_owner_hold_catches_dallas_without_hiding_other_alex_jean_shows(self):
        cards = [
            {'attrs': {'data-date': '2026-11-19', 'data-state': 'TX'},
             'meta': {'Location': 'Dallas, TX'}, 'artists': '<a>Alex Jean</a>'},
            {'attrs': {'data-date': '2026-11-27', 'data-state': 'FL'},
             'meta': {'Location': 'Orlando, FL'}, 'artists': '<a>Alex Jean</a>'},
            {'attrs': {'data-date': '2026-11-19', 'data-state': 'TX'},
             'meta': {'Location': 'Houston, TX'}, 'artists': '<a>WHATUPRG</a>'},
        ]
        self.assertEqual(len(maintenance.owner_hold_errors(cards)), 1)
        self.assertEqual(maintenance.owner_hold_errors(cards[1:]), [])

    def test_artist_check_rejects_yesterday_next_show_even_with_a_future_show(self):
        html='''<script id="kc-fan-config" type="application/json">{"artist":"Test","showPaths":["/event/yesterday/","/event/future/"]}</script>
        <a class="kc-rd-next-show" href="/event/yesterday/"></a>
        <span class="kc-rd-upcoming-total">2 upcoming</span>
        <div class="kc-rd-show-list"><a class="kc-rd-show-row" href="/event/yesterday/"></a><a class="kc-rd-show-row" href="/event/future/"></a></div>'''
        shows=[{'path':'/event/future/','date':'2026-11-01','end':'2026-11-01'}]
        errors=maintenance.artist_errors(html,shows,'2026-10-24')
        self.assertTrue(any('next show' in e for e in errors))
        self.assertTrue(any('count' in e for e in errors))
        self.assertTrue(any('expired or absent' in e for e in errors))

    def test_weekly_windows_follow_monday_across_month_and_year_boundaries(self):
        self.assertEqual(maintenance.week_window('2026-10-26'), ('2026-10-26','2026-11-01','2026-11-02','2026-11-08'))
        self.assertEqual(maintenance.week_window('2026-12-31'), ('2026-12-28','2027-01-03','2027-01-04','2027-01-10'))


class LiveCalendarCanonicalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        (self.root / 'config').mkdir()
        self.day = '2099-02-26'
        self.events = [
            dict(id='manual:renamed-canadian', title='Updated venue showcase',
                 startDate=self.day, endDate=self.day, city='Surrey', state='BC',
                 country='CA', artists=['Test Artist'], status='scheduled'),
            dict(id='manual:other-canadian', title='Other Canadian concert',
                 startDate=self.day, endDate=self.day, city='Saskatoon', state='SK',
                 country='CA', artists=['Other Artist'], status='scheduled'),
        ]
        self.original_path = event_path(dict(self.events[0], title='Original announced showcase'))
        self.other_path = event_path(self.events[1])
        self.registry = {'events': {
            self.events[0]['id']: {'path': self.original_path, 'sourceIds': ['provider:renamed-alias']},
            self.events[1]['id']: {'path': self.other_path, 'sourceIds': []},
        }}

    def verify_live(self, paths, with_registry=True):
        registry_file = self.root / 'config/url-continuity.json'
        if with_registry:
            registry_file.write_text(json.dumps(self.registry))
        catalog = {'asOf': self.day, 'artists': {}, 'shows': [
            {'path': path, 'date': self.day, 'end': self.day} for path in paths]}
        home = (f'<div data-national-home data-preview-as-of="{self.day}"></div>'
                '<section id="kc-week-shelf"></section><section id="kc-next-shelf"></section>')
        cards = ''.join(
            f'<article data-event-card><h3><a href="{path}">Concert</a></h3>'
            '<img src="/flyer.jpg"><p class="artist-line">Test Artist</p>'
            '<div class="event-badges"></div></article>' for path in paths)
        responses = {'/assets/fan-show-catalog.json': json.dumps(catalog),
                     '/index.html': home, '/shows/index.html': cards}
        original_events = copy.deepcopy(self.events)
        original_registry = registry_file.read_bytes() if registry_file.exists() else None
        with patch.object(maintenance, '__file__', str(self.root / 'scripts/calendar_maintenance.py')), \
             patch.object(maintenance, 'read_events', return_value=self.events), \
             patch.object(maintenance.urllib.request, 'urlopen',
                          side_effect=lambda request, timeout: io.BytesIO(
                              responses[urlsplit(request.full_url).path].encode())):
            result = maintenance.verify_live('https://example.invalid', self.day)
        self.assertEqual(self.events, original_events, 'Live checking must not mutate source records')
        if original_registry is not None:
            self.assertEqual(registry_file.read_bytes(), original_registry)
        return result['errors']

    def test_live_renamed_show_uses_local_published_identity(self):
        self.assertNotEqual(self.original_path, event_path(self.events[0]))
        self.assertEqual(self.verify_live([self.original_path, self.other_path]), [])

    def test_live_source_id_alias_uses_same_local_published_identity(self):
        self.events[0]['id'] = 'provider:renamed-alias'
        self.assertEqual(self.verify_live([self.original_path, self.other_path]), [])

    def test_live_alias_route_cannot_mask_missing_canonical_listing(self):
        errors = self.verify_live([event_path(self.events[0]), self.other_path])
        self.assertEqual(errors, [f'Canadian show missing from published catalog: {self.original_path}'])

    def test_live_missing_other_canadian_still_fails(self):
        errors = self.verify_live([self.original_path])
        self.assertEqual(errors, [f'Canadian show missing from published catalog: {self.other_path}'])

    def test_live_unregistered_show_keeps_generated_path_fallback(self):
        self.events[0]['id'] = 'manual:new-canadian-show'
        generated = event_path(self.events[0])
        self.assertEqual(self.verify_live([generated, self.other_path]), [])

    def test_live_without_registry_keeps_generated_path_fallback(self):
        self.assertEqual(self.verify_live([event_path(event) for event in self.events],
                                          with_registry=False), [])
