import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_sep26_source_corrections as repair
from apply_verified_show_information import apply as apply_reviewed_information, enrich
from finalize_seo_indexing_core import concert_start_only
from prune_past_events import prune_source
from show_information_model import normalize
from tests.catalog_history import append_completed


class SourceCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.other = {"id": "other-mike-teezy", "artists": ["Mike Teezy"], "startDate": "2026-11-07", "venue": "Another venue"}
        self.old = {"id": "official:4e2fc5c7c02ab1d34b9e", "artists": ["Mike Teezy"], "startTime": "18:00"}
        self.oasis = {"id": "manual:" + repair.OASIS_ID, "startDate": "2026-09-26", "startTime": "20:00", "endDate": "2026-09-26", "firstSeen": "2026-09-01T00:00:00Z"}
        self.save("events.json", [self.other, self.old, self.oasis, dict(
            repair.CLEVELAND, startTime="20:00", artists=["KB", "Brenno", "Porsha Love"],
            advertisedBilling=["KB", "Brenno", "Taylor Wells", "Porsha Love"],
            image="assets/artists/kb.webp", imageType="artist", imageOverride=False)])
        self.save("supplemental-events.json", [{"id": "supplemental:beyond-the-walls-3-brenno-2026"}])
        self.save("config/manual-events.json", [])
        self.save("event-history.json", {"summary": {"total": 2}, "events": [
            {"archiveKey": "old-mike", "firstSeenOnCalendar": "2026-08-20", "event": copy.deepcopy(self.old)},
            {"archiveKey": "oasis", "event": copy.deepcopy(self.oasis)}]})

    def save(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def read(self, path):
        return json.loads((self.root / path).read_text())

    def unity_refresh(self, canonical_current=True):
        registry = json.loads((repair.ROOT / "config/verified-show-information.json").read_text())
        reviewed = next(row for row in registry["events"] if row["id"] == "bandsintown:109072940")
        self.save("config/verified-show-information.json", {"version": 1, "events": [reviewed]})
        # compact_event returns the queried artist only. The scan preserves
        # artwork overrides, not reviewed venue names or the complete bill.
        canonical = dict(id="bandsintown:109072940", title="UNITY POP-UP TOUR",
                         startDate="2026-11-14", startTime="11:00", timezone="",
                         venue="UNITY POP-UP TOUR", address="801 Dorscher Rd",
                         city="Orlando", state="FL", country="US",
                         artists=["Issac Mansfield"], status="scheduled",
                         ticketUrl=reviewed["corrections"][0]["expected"]["ticketUrl"],
                         sources=[{"name": "Issac artist calendar"}], firstSeen="2026-11-10")
        alias = dict(canonical, id="bandsintown:109044233",
                     title="SYL noiZ at Grace Bible Church of Central Florida",
                     venue="Grace Bible Church of Central Florida", artists=["SYL noiZ"],
                     sources=[{"name": "SYL artist calendar"}])
        retained = enrich(canonical, [reviewed])
        retained["artists"] = ["Issac Mansfield", "GIOVANI"]
        retained["firstSeen"] = "2026-10-24T14:08:55Z"
        self.save("events.json", [self.other])
        self.save("supplemental-events.json", [alias] + ([canonical] if canonical_current else []))
        self.save("event-history.json", {"events": [{"archiveKey": "unity", "event": retained}]})
        return canonical, alias, retained

    def test_unity_refresh_corrects_known_provider_venue_before_duplicate_validation(self):
        from build_seo_site import event_path
        for canonical_current in (True, False):
            for status in ("scheduled", "cancelled"):
                with self.subTest(canonical_current=canonical_current, status=status):
                    canonical, alias, retained = self.unity_refresh(canonical_current)
                    rows = self.read("supplemental-events.json")
                    rows[0]["status"] = status
                    self.save("supplemental-events.json", rows)
                    repair.apply(self.root, "2026-11-10")
                    rows = self.read("supplemental-events.json")
                    self.assertEqual(1, len(rows))
                    event = rows[0]
                    self.assertEqual(canonical["id"], event["id"])
                    self.assertEqual("Grace Bible Church of Central Florida", event["venue"])
                    self.assertEqual("11:00", event["startTime"])
                    self.assertEqual(["Issac Mansfield", "GIOVANI", "SYL noiZ"], event["artists"])
                    self.assertEqual(["Issac Mansfield", "SYL noiZ", "GIOVANI", "Landy", "Cory BiNks"], event["advertisedBilling"])
                    self.assertEqual("assets/events/issac-unity-pop-up-orlando-2026-11-14-official.webp", event["image"])
                    self.assertEqual(retained["ticketUrl"], event["ticketUrl"])
                    self.assertEqual(retained["firstSeen"], event["firstSeen"])
                    self.assertEqual(status, event["status"])
                    self.assertEqual(event_path(retained), event_path(event))
                    self.assertIn(event_path(alias), event["legacyEventPaths"])
                    self.assertIn(alias["id"], event["mergedFromIds"])
                    self.assertIn({"name": "SYL artist calendar"}, event["sources"])
                    self.assertIn(self.other, self.read("events.json"))
                    before = {str(p): p.read_bytes() for p in self.root.rglob("*.json")}
                    repair.apply(self.root, "2026-11-10")
                    self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*.json")})

    def test_unity_refresh_keeps_rejecting_changed_venue_and_time(self):
        for index in (0, 1):
            for change in ({"venue": "New confirmed venue"}, {"startTime": "19:00"}):
                with self.subTest(index=index, change=change):
                    self.unity_refresh()
                    rows = self.read("supplemental-events.json")
                    rows[index].update(change)
                    self.save("supplemental-events.json", rows)
                    with self.assertRaisesRegex(ValueError, "bandsintown:109044233: reviewed performance identity conflict"):
                        repair.apply(self.root, "2026-11-10")

    def test_stale_collection_is_consolidated_without_removing_unrelated_show(self):
        repair.apply(self.root, "2026-09-26")
        events = self.read("events.json")
        self.assertIn(self.other, events)
        cleveland = [row for row in events if repair.identity(row) == repair.CLEVELAND_ID]
        self.assertEqual(1, len(cleveland))
        self.assertEqual("19:30", cleveland[0]["startTime"])
        self.assertEqual(["KB", "Brenno", "Mike Teezy", "Porsha Love", "Taylor Wells", "Renzoe", "Eli Williams"], cleveland[0]["advertisedBilling"])
        self.assertIn("Mike Teezy", cleveland[0]["artists"])
        self.assertNotIn("Renzoe", cleveland[0]["artists"])
        self.assertEqual("assets/events/beyond-the-walls-cleveland-2026-11-07.jpg", cleveland[0]["image"])
        self.assertEqual("event_artwork", cleveland[0]["imageType"])
        self.assertTrue(cleveland[0]["imageOverride"])
        self.assertEqual("2026-07-30T03:46:47Z", cleveland[0]["firstSeen"])
        self.assertTrue(all(conflict.get("resolvedBy") for conflict in cleveland[0]["sourceConflicts"]))
        self.assertEqual([], self.read("supplemental-events.json"))
        history = self.read("event-history.json")
        self.assertEqual("merged", history["events"][0]["event"]["status"])
        self.assertEqual("2026-08-20", history["events"][0]["firstSeenOnCalendar"])
        self.save("supplemental-events.json", [self.old])
        repair.apply(self.root, "2026-09-26")
        self.assertEqual(events, self.read("events.json"))

    def test_reschedule_preserves_age_links_and_history_and_is_idempotent(self):
        repair.apply(self.root, "2026-09-26")
        oasis = next(row for row in self.read("events.json") if repair.identity(row) == repair.OASIS_ID)
        self.assertEqual("2026-09-27T19:00:00-04:00", oasis["startDateTime"])
        self.assertEqual("2026-09-01T00:00:00Z", oasis["firstSeen"])
        self.assertNotIn("endDate", oasis)
        self.assertEqual("rescheduled", oasis["status"])
        self.assertTrue(oasis["legacyEventPaths"])
        self.assertEqual("2026-09-27", self.read("event-history.json")["events"][1]["event"]["startDate"])
        before = {str(p): p.read_bytes() for p in self.root.rglob("*.json")}
        repair.apply(self.root, "2026-09-26")
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*.json")})
        repair.apply(self.root, "2026-11-08")
        self.assertEqual([self.other], self.read("events.json"))

    def test_public_doors_cleanup_preserves_concert_start_and_official_link(self):
        start = '<div><dt>Date</dt><dd>Sep 27 - 7:00 PM</dd></div>'
        link = '<a href="https://example.com">Official details</a>'
        self.assertEqual(start + link, concert_start_only(start + '<div><dt>Doors</dt><dd>5:30 PM</dd></div>' + link))

    def test_reviewed_cleveland_clock_survives_november_8_archive_rollover(self):
        registry = json.loads((repair.ROOT / "config/verified-show-information.json").read_text())
        reviewed = next(row for row in registry["events"] if row["id"] == repair.CLEVELAND_ID)
        self.save("config/verified-show-information.json", {"version": 1, "events": [reviewed]})
        approved = enrich(copy.deepcopy(repair.CLEVELAND), [reviewed])
        entry = {"archiveKey": "canonical-cleveland", "firstSeenOnCalendar": "2026-07-30",
                 "lastSeenOnCalendar": "2026-11-07", "event": approved}
        unrelated = {"archiveKey": "unrelated", "event": copy.deepcopy(self.other)}
        self.save("event-history.json", {"summary": {"total": 2}, "events": [entry, unrelated]})
        self.save("events.json", [approved])

        repair.apply(self.root, "2026-11-07")
        apply_reviewed_information(self.root)
        current = next(row for row in self.read("events.json") if row["id"] == repair.CLEVELAND_ID)
        self.assertEqual("20:00", current["startTime"])

        # Exercise the real workflow boundary: the next day removes the live
        # row, repairs retained history, then validates that historical record.
        prune_source(self.root, "2026-11-08")
        repair.apply(self.root, "2026-11-08")
        apply_reviewed_information(self.root)
        self.assertFalse(any(row["id"] == repair.CLEVELAND_ID for row in self.read("events.json")))
        history = self.read("event-history.json")
        archived = append_completed([], history["events"], {repair.CLEVELAND_ID}, "2026-11-08")[0]
        self.assertEqual("20:00", archived["startTime"])
        self.assertEqual("19:30", archived["doorsTime"])
        self.assertNotEqual("doors", archived.get("primaryTimeKind"))
        self.assertEqual("2026-11-07T20:00:00-05:00", normalize(archived)["schemaStartDate"])
        self.assertNotIn("endDate", archived)
        for field in ("id", "firstSeen", "officialUrl", "ticketUrl", "legacyEventPaths",
                      "advertisedBilling", "officialBill", "sources"):
            self.assertEqual(current[field], archived[field], field)
        self.assertEqual({k: v for k, v in entry.items() if k != "event"},
                         {k: v for k, v in history["events"][0].items() if k != "event"})
        self.assertEqual(unrelated, history["events"][1])
        repair.apply(self.root, "2026-11-08")
        apply_reviewed_information(self.root)
        self.assertEqual(history, self.read("event-history.json"))


if __name__ == "__main__":
    unittest.main()
