import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_events as collector
from apply_verified_date_corrections import (patch_event, normalize_provider_identity,
    SCOOTIE_DATES, SCOOTIE_URL, SCOOTIE_CANONICAL_ID, SCOOTIE_PROVIDER_ALIAS)


class LocalConcertDateTests(unittest.TestCase):
    def test_observed_provider_id_change_keeps_existing_public_identity(self):
        from apply_verified_show_artwork import patch_event as pin_artwork
        import build_seo_site as builder
        event={'id':SCOOTIE_PROVIDER_ALIAS,'officialUrl':SCOOTIE_URL,
               'title':'Scootie Wop at MATCH','city':'Houston','startDate':'2026-11-15',
               'firstSeen':'2026-08-09','status':'cancelled'}
        self.assertTrue(normalize_provider_identity(event))
        patch_event(event); pin_artwork(event)
        self.assertEqual(SCOOTIE_CANONICAL_ID,event['id'])
        self.assertEqual('2027-05-01',event['startDate'])
        self.assertEqual('2026-08-09',event['firstSeen'])
        self.assertEqual('cancelled',event['status'])
        self.assertEqual('assets/events/scootie-wop-chh-matters-rescheduled-2027-05-01.jpg',event['image'])
        self.assertEqual(builder.event_path(dict(event,id=SCOOTIE_CANONICAL_ID)),builder.event_path(event))
        self.assertFalse(normalize_provider_identity(event))

    def test_manual_only_refresh_keeps_published_identity_and_rescheduled_schema(self):
        import build_seo_site as builder
        announcement = 'https://www.instagram.com/p/DfTOHOODGjO/'
        seed = {'id': 'scootie-wop-match-houston-2026', 'title': 'Scootie Wop at MATCH',
                'startDate': '2027-05-01', 'startTime': '18:00',
                'venue': 'MATCH - Midtown Arts and Theater Center Houston',
                'address': '3400 Main St', 'city': 'Houston', 'state': 'TX',
                'artists': ['Scootie Wop'], 'officialUrl': announcement,
                'ticketUrl': 'https://www.bandsintown.com/e/1039613019',
                'status': 'rescheduled', 'previousStartDate': '2026-11-14'}
        event = collector.normalize_manual_event(seed, '2026-11-04T00:00:00Z')
        self.assertTrue(normalize_provider_identity(event))
        patch_event(event)
        self.assertEqual(SCOOTIE_CANONICAL_ID, event['id'])
        self.assertEqual('2026-08-09T00:00:00Z', event['firstSeen'])
        self.assertEqual('2027-05-01T18:00:00-05:00', event['startDateTime'])
        self.assertEqual('2027-05-01T22:00:00-05:00', event['endDateTime'])
        self.assertEqual('3400 Main St', event['address'])
        self.assertEqual(['Scootie Wop'], event['artists'])
        self.assertEqual(announcement, event['officialUrl'])
        schema = builder.event_schema(event)
        self.assertEqual('https://schema.org/EventRescheduled', schema['eventStatus'])
        self.assertEqual('2026-11-14', schema['previousStartDate'])
        self.assertIn('from Sat, Nov 14, 2026 to Sat, May 1, 2027', builder.rescheduled_notice(event))
        before = copy.deepcopy(event)
        patch_event(event)
        self.assertEqual(before, event)

    def test_stale_source_replay_updates_dates_and_keeps_history_wrappers(self):
        import apply_sep26_source_corrections as repair
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config').mkdir()
            stale = {'id': SCOOTIE_PROVIDER_ALIAS, 'title': 'Scootie Wop at MATCH',
                     'officialUrl': SCOOTIE_URL, 'startDate': '2026-11-15',
                     'endDate': '2026-11-15', 'startTime': '18:00',
                     'venue': 'MATCH - Midtown Arts and Theater Center Houston',
                     'address': '3400 Main St', 'city': 'Houston', 'state': 'TX',
                     'artists': ['Scootie Wop'], 'firstSeen': '2026-11-04T00:00:00Z'}
            other = dict(stale, id='another-scootie-show', officialUrl='https://example.test/other')
            history = {'historyVersion': 2, 'events': [
                {'archiveKey': 'id:' + SCOOTIE_PROVIDER_ALIAS,
                 'firstArchivedAt': '2026-10-17T19:05:03Z',
                 'firstSeenOnCalendar': '2026-08-09T00:00:00Z',
                 'calendarPresence': 'absent', 'reappearedCount': 0,
                 'event': dict(stale, image='original-flyer.jpg')} ]}
            inputs = {'events.json': [stale, other], 'supplemental-events.json': [],
                      'config/manual-events.json': [], 'event-history.json': history}
            for name, value in inputs.items():
                (root / name).write_text(json.dumps(value))
            repair.apply(root, '2026-11-04')
            current = json.loads((root / 'events.json').read_text())
            event = next(row for row in current if row['id'] == SCOOTIE_CANONICAL_ID)
            self.assertEqual('2027-05-01', event['startDate'])
            self.assertEqual('rescheduled', event['status'])
            self.assertEqual('2026-08-09T00:00:00Z', event['firstSeen'])
            self.assertIn(other, current)
            entry = json.loads((root / 'event-history.json').read_text())['events'][0]
            self.assertEqual({k: v for k, v in history['events'][0].items() if k != 'event'},
                             {k: v for k, v in entry.items() if k != 'event'})
            self.assertEqual(SCOOTIE_PROVIDER_ALIAS, entry['event']['id'])
            self.assertEqual('2027-05-01', entry['event']['startDate'])
            self.assertEqual('original-flyer.jpg', entry['event']['image'])
            once = {name: (root / name).read_bytes() for name in inputs}
            repair.apply(root, '2026-11-04')
            self.assertEqual(once, {name: (root / name).read_bytes() for name in inputs})

    def test_archive_bot_does_not_restore_superseded_date_from_git_snapshot(self):
        from archive_event_history import canonicalize_known_event_identity
        stale = {'id': SCOOTIE_PROVIDER_ALIAS, 'officialUrl': SCOOTIE_URL,
                 'startDate': '2026-11-14', 'firstSeen': '2026-08-09T00:00:00Z',
                 'image': 'original-flyer.jpg', 'status': 'scheduled'}
        before = copy.deepcopy(stale)
        retained = canonicalize_known_event_identity(stale)
        self.assertEqual('2027-05-01', retained['startDate'])
        self.assertEqual(SCOOTIE_PROVIDER_ALIAS, retained['id'])
        self.assertEqual('original-flyer.jpg', retained['image'])
        self.assertEqual('rescheduled', retained['status'])
        self.assertEqual(before, stale)

    def test_provider_identity_fix_does_not_touch_reschedules_or_other_sources(self):
        base={'id':SCOOTIE_PROVIDER_ALIAS,'officialUrl':SCOOTIE_URL,'startDate':'2026-11-14'}
        for changed in ({'id':'another-event'},{'officialUrl':'https://example.test/other'},
                        {'startDate':'2026-12-12'}):
            event={**base,**changed}; before=copy.deepcopy(event)
            self.assertFalse(normalize_provider_identity(event))
            self.assertEqual(before,event)

    def event(self, start, end):
        raw = {
            "@type": "MusicEvent", "name": "Scootie Wop at MATCH",
            "startDate": start, "endDate": end, "url": SCOOTIE_URL,
            "location": {"name": "MATCH", "address": {
                "addressLocality": "Houston", "addressRegion": "TX", "addressCountry": "US"}},
            "performer": {"name": "Scootie Wop"},
        }
        return collector.collect_jsonld_source_from_html(
            {"timezone": "America/Chicago", "artist": "Scootie Wop", "parser": "jsonld"},
            SCOOTIE_URL, '<script type="application/ld+json">' + json.dumps(raw) + '</script>',
            {collector.normalize_name("Scootie Wop"): "Scootie Wop"}, "2026-10-05T00:00:00Z")[0]

    def test_utc_next_day_is_same_local_concert_evening(self):
        event = self.event("2026-11-15T00:00:00Z", "2026-11-15T04:00:00Z")
        for key, expected in SCOOTIE_DATES.items():
            self.assertEqual(expected, event[key], key)
        merged = collector.merge_two_events({"id": "existing", "sourcePriority": 1}, event)
        for key in ("startDate", "endDate", "startTime", "timezone"):
            self.assertEqual(SCOOTIE_DATES[key], merged[key], key)

    def test_daylight_saving_and_real_multiple_days_are_preserved(self):
        event = self.event("2026-10-10T00:00:00Z", "2026-10-11T03:00:00Z")
        self.assertEqual("2026-10-09", event["startDate"])
        self.assertEqual("19:00", event["startTime"])
        self.assertEqual("2026-10-10", event["endDate"])
        self.assertEqual("2026-10-10T22:00:00-05:00", event["endDateTime"])

    def test_naive_dates_are_not_shifted_or_assigned_guessed_timezones(self):
        self.assertEqual(("2026-11-14", "18:00"), collector.parse_date_prefix("2026-11-14T18:00:00", "America/Chicago"))
        self.assertEqual(("2026-11-14", ""), collector.parse_date_prefix("2026-11-14", "America/Chicago"))
        self.assertEqual(("2026-11-15", "00:00"), collector.parse_date_prefix("2026-11-15T00:00:00Z"))

    def test_reviewed_correction_preserves_identity_age_artwork_and_cancellation(self):
        event = {"id": "official:0dd5f599b4db080206cf", "startDate": "2026-11-14",
                 "endDate": "2026-11-15", "status": "cancelled", "firstSeen": "2026-08-09T00:00:00Z",
                 "image": "approved.jpg", "artists": ["Scootie Wop"]}
        protected = {k:copy.deepcopy(v) for k,v in event.items() if k not in SCOOTIE_DATES}
        patch_event(event);once=copy.deepcopy(event);patch_event(event)
        self.assertEqual(once,event)
        self.assertEqual(protected,{k:event[k] for k in protected})
        self.assertEqual("2027-05-01",event["endDate"])
        rescheduled=dict(event,startDate="2026-12-12",endDate="2026-12-12")
        original=copy.deepcopy(rescheduled);patch_event(rescheduled);self.assertEqual(original,rescheduled)
        other={"id":"another-show","startDate":"2026-11-14","endDate":"2026-11-15","artists":["Scootie Wop"]}
        original=copy.deepcopy(other);patch_event(other);self.assertEqual(original,other)


if __name__ == "__main__":
    unittest.main()
