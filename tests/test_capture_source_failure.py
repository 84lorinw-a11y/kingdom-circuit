"""Failure artifacts expose public conflict facts, never private rows or secrets."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import capture_source_failure as capture


def show(**changes):
    return dict({"id": "bandsintown:12345", "title": "Public concert", "startDate": "2026-11-21",
        "startTime": "19:00", "doorsTime": "18:00", "timezone": "America/Chicago", "venue": "Public Hall",
        "city": "Austin", "state": "TX", "country": "US", "artists": ["Confirmed Artist"],
        "status": "scheduled"}, **changes)


class CaptureSourceFailureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.write("config/private-events.json", [])
        self.write("config/review-held-events.json", [])
        for name in capture.FEEDS:
            self.write(name, [])

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def test_exact_public_facts_survive_but_nonallowlisted_values_never_leave_source(self):
        event = show(address="Private street details", officialUrl="https://provider.example/?apikey=SOURCE_SECRET",
                     sources=[{"url": "https://api.example/?token=NESTED_SECRET"}],
                     notes="freeform confidential note", error="request failed with SECRET_ERROR")
        self.write("events.json", [event])
        self.write("run-status.json", {"warnings": ["https://api.example/?apikey=STATUS_SECRET"]})
        self.write("cache/ticketmaster-attractions.json", {"value": "CACHE_SECRET"})
        self.write("config/extra.json", {"value": "CONFIG_SECRET"})
        before = (self.root / "events.json").read_bytes()
        report = capture.snapshot(self.root)
        self.assertEqual(report["inputs"]["events.json"]["events"], [show()])
        text = json.dumps(report)
        for forbidden in ["Private street", "http", "SECRET", "confidential", "run-status", "cache/", "config/"]:
            self.assertNotIn(forbidden, text)
        self.assertEqual((self.root / "events.json").read_bytes(), before)

    def test_url_and_credential_text_misplaced_in_allowed_fields_are_omitted(self):
        self.write("events.json", [show(title="https://api.example/?apikey=TITLE_SECRET",
            venue="Venue https://user:PASS@host.example/private", city="api_key=CITY_SECRET",
            artists=["Confirmed Artist", "www.example.com/?token=ARTIST_SECRET"])])
        event = capture.snapshot(self.root)["inputs"]["events.json"]["events"][0]
        self.assertNotIn("title", event)
        self.assertNotIn("venue", event)
        self.assertNotIn("city", event)
        self.assertEqual(event["artists"], ["Confirmed Artist"])
        self.assertNotIn("SECRET", json.dumps(event))

    def test_private_policy_alias_and_hold_records_are_omitted_in_full(self):
        self.write("config/private-events.json", [show(id="manual:private", mergedFromIds=["bandsintown:12345"])])
        self.write("config/review-held-events.json", [{"publish": False, "excludedEventId": "official:held"}])
        events = [show(venue="PRIVATE_VENUE"), show(id="official:flagged-private", private=True),
                  show(id="official:held"), show(id="official:pending", holdReason="Private review"),
                  show(id="official:new-private-alias", mergedFromIds=["manual:private"]),
                  show(id="official:state-held", status="held"), show(id="official:visible", status="cancelled")]
        self.write("events.json", events)
        report = capture.snapshot(self.root)
        self.assertEqual(report["inputs"]["events.json"]["omittedCount"], 6)
        self.assertEqual(report["inputs"]["events.json"]["events"], [show(id="official:visible", status="cancelled")])
        self.assertNotIn("PRIVATE_VENUE", json.dumps(report))

    def test_existing_dated_owner_rejection_is_not_copied(self):
        self.write("events.json", [show(id="bandsintown:109046095", startDate="2026-11-07",
                                       artists=["K-Drama"], venue="HELD_VENUE")])
        result = capture.snapshot(self.root)["inputs"]["events.json"]
        self.assertEqual(result["events"], [])
        self.assertEqual(result["omittedCount"], 1)

    def test_missing_or_malformed_privacy_policy_captures_no_records(self):
        self.write("events.json", [show(venue="POTENTIALLY_PRIVATE")])
        for name in ("config/private-events.json", "config/review-held-events.json"):
            with self.subTest(name=name):
                self.write(name, {"invalid": "SECRET_POLICY"})
                report = capture.snapshot(self.root)
                self.assertEqual(report["policyStatus"], "unavailable")
                self.assertEqual(report["inputs"], {})
                self.assertNotIn("SECRET_POLICY", json.dumps(report))
                self.write(name, [])
        (self.root / "config/private-events.json").unlink()
        self.assertEqual(capture.snapshot(self.root)["inputs"], {})

    def test_missing_malformed_and_symlink_inputs_emit_metadata_without_raw_errors(self):
        (self.root / "events.json").unlink()
        (self.root / "supplemental-events.json").write_text('invalid {"apikey":"PARSE_SECRET"')
        target = self.root / "outside.json"
        target.write_text('[{"title":"SYMLINK_SECRET"}]')
        path = self.root / "artist-website-events.json"
        path.unlink()
        path.symlink_to(target)
        result = capture.snapshot(self.root)
        self.assertEqual(result["inputs"], {"events.json": {"status": "missing"},
            "supplemental-events.json": {"status": "unreadable"},
            "artist-website-events.json": {"status": "unreadable"}})
        self.assertNotIn("SECRET", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
