import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_events as collector
from apply_verified_date_corrections import patch_event, SCOOTIE_DATES, SCOOTIE_URL


class LocalConcertDateTests(unittest.TestCase):
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
        self.assertEqual("2026-11-14",event["endDate"])
        rescheduled=dict(event,startDate="2026-12-12",endDate="2026-12-12")
        original=copy.deepcopy(rescheduled);patch_event(rescheduled);self.assertEqual(original,rescheduled)
        other={"id":"another-show","startDate":"2026-11-14","endDate":"2026-11-15","artists":["Scootie Wop"]}
        original=copy.deepcopy(other);patch_event(other);self.assertEqual(original,other)


if __name__ == "__main__":
    unittest.main()
