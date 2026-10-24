import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import calendar_maintenance as maintenance


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

