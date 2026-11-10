"""Website outages must not erase accepted shows or resurrect editorial holds."""
import contextlib
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import coordinated_source_refresh as refresh


ARTIST = {"name": "Accepted Artist", "enabled": True, "verified": True,
          "sourceRegistryVerified": True, "website": "https://artist.example/tour"}


def show(**changes):
    return dict({"id": "official:accepted-website-show", "title": "Verified show",
        "startDate": "2026-11-21", "startTime": "19:00", "venue": "Approved venue",
        "city": "Detroit", "state": "MI", "country": "US", "status": "scheduled",
        "artists": ["Accepted Artist", "Confirmed Guest"], "headliner": "Accepted Artist",
        "trackedArtist": "Accepted Artist", "firstSeen": "2026-09-01T12:00:00Z",
        "image": "assets/events/approved.jpg", "imageOverride": True,
        "legacyEventPaths": ["/event/existing-stable-path/"],
        "officialUrl": "https://artist.example/tour/verified-show"}, **changes)


class CoordinatedSourceRefreshTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "source"
        self.root.mkdir()
        self.snapshot = Path(self.directory.name) / "accepted.json"
        self.write("config/artists.json", [ARTIST])
        self.write("config/private-events.json", [])
        self.write("config/review-held-events.json", [])
        self.write("events.json", [show()])
        self.write("supplemental-events.json", [])
        self.write(refresh.CACHE, [show()])
        self.write(refresh.STATUS, {"old": "status"})
        self.addCleanup(patch.stopall)
        patch.object(refresh, "today_cutoff", return_value="2026-11-10").start()
        patch.dict(refresh.os.environ, {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}).start()

    def write(self, name, value):
        refresh.save(self.root / name, value)

    def read(self, name):
        return refresh.read_json(self.root / name)

    def archive_command(self, root, script, *args):
        if script == "archive_event_history.py":
            events = [{"archiveKey": "id:" + event["id"], "event": event}
                      for name in refresh.FEEDS for event in self.read(name)]
            self.write("event-history.json", {"historyVersion": 2, "events": events,
                "summary": {"totalArchived": len(events), "gitSnapshotsScanned": 1}})

    def prepare(self):
        with patch.object(refresh, "run", side_effect=self.archive_command) as command:
            result = refresh.prepare(self.root, self.snapshot)
        return result, [tuple(call.args[1:]) for call in command.call_args_list]

    def collect(self, fresh=(), warnings=(), status_changes=None, failure=None):
        def command(root, script, *args):
            self.assertEqual((root, script, args), (self.root, "collect_artist_website_events.py", ()))
            self.write(refresh.CACHE, list(fresh))
            artists = [row for row in self.read("config/artists.json") if row.get("enabled", True)]
            status = {"generatedAt": datetime.now(timezone.utc).isoformat(),
                "mode": "all-tracked-artists-official-website-scan",
                "artistsConfigured": len(artists),
                "officialWebsitesChecked": sum(bool(refresh.eligible_website(row)) for row in artists),
                "eventsFound": len(fresh), "warnings": list(warnings), "warningCount": len(warnings)}
            status.update(status_changes or {})
            self.write(refresh.STATUS, status)
            if failure:
                raise failure
        with patch.object(refresh, "run", side_effect=command):
            return refresh.websites(self.root, self.snapshot)

    def test_prepare_archives_before_sync_and_snapshots_only_exact_accepted_candidates(self):
        raw = show(firstSeen="2026-11-09T12:00:00Z", image="unreviewed-provider-image.jpg")
        unaccepted = show(id="official:unaccepted", officialUrl="https://artist.example/tour/another")
        self.write(refresh.CACHE, [raw, unaccepted])
        before = (self.root / "config/artists.json").read_bytes()
        count, commands = self.prepare()
        self.assertEqual(commands, [("archive_event_history.py",), ("sync_verified_artist_websites.py",)])
        self.assertEqual(count, 1)
        self.assertEqual(refresh.read_snapshot(self.root, self.snapshot), [{"candidate": raw, "accepted": show()}])
        self.assertEqual((self.root / "config/artists.json").read_bytes(), before)

    def test_exact_accepted_alias_is_supported_but_conflicting_feed_copies_are_not_chosen(self):
        canonical = show(id="manual:canonical", mergedFromIds=[show()["id"]])
        self.write("events.json", [canonical])
        self.assertEqual(self.prepare()[0], 1)
        self.write("supplemental-events.json", [dict(canonical, startTime="20:00")])
        self.assertEqual(self.prepare()[0], 0)

    def test_partial_and_empty_scan_restore_exact_finalized_facts_and_earliest_discovery(self):
        for fresh in [[], [show(id="official:new", startDate="2026-11-22")]]:
            with self.subTest(fresh=fresh):
                raw = show(firstSeen="2026-11-09T12:00:00Z", image="provider.jpg")
                self.write("events.json", [show()])
                self.write(refresh.CACHE, [raw, show(id="official:never-accepted")])
                self.prepare()
                self.write("events.json", [])  # Base collection omitted the website-only show.
                self.assertEqual(self.collect(fresh, warnings=["Website timed out"]), 1)
                self.assertEqual(self.read("events.json"), [show()])
                self.assertEqual(self.read(refresh.CACHE), fresh + [raw])
                status = self.read(refresh.STATUS)
                self.assertEqual(status["eventsFound"], len(fresh), "Retained rows are not fresh discoveries")
                self.assertEqual(status["warningCount"], 1)
                self.assertEqual(status["missingProviderShowsRetained"], 1)

    def test_repeated_application_does_not_duplicate_or_overwrite_finalized_records(self):
        self.prepare()
        self.write("events.json", [])
        self.assertEqual(self.collect(), 1)
        before = self.read("events.json")
        before_cache = self.read(refresh.CACHE)
        self.assertEqual(self.collect(), 1)
        self.assertEqual(self.read("events.json"), before)
        self.assertEqual(self.read(refresh.CACHE), before_cache)
        # The next daily snapshot still has proof of prior acceptance.
        self.prepare()
        self.write("events.json", [])
        self.assertEqual(self.collect(), 1)
        self.assertEqual(self.read("events.json"), before)

    def test_restored_record_survives_actual_seed_merge_with_original_facts_and_first_seen(self):
        import merge_artist_website_events as merger
        from update_events import normalize_manual_event
        raw = normalize_manual_event(show(image="assets/events/provider-image.jpg"), "2026-11-09T12:00:00Z")
        raw["id"] = show()["id"]
        self.assertEqual(len(merger.finalize_events([raw], {}, date(2026, 11, 10))), 1)
        self.write(refresh.CACHE, [raw])
        self.prepare()
        self.write("events.json", [])
        self.collect()
        with patch.multiple(merger, ROOT=self.root, EVENTS_FILE=self.root / "events.json",
                WEBSITE_EVENTS_FILE=self.root / refresh.CACHE, ARTISTS_FILE=self.root / "config/artists.json",
                ATTRACTION_CACHE_FILE=self.root / "attraction-cache.json", STATUS_FILE=self.root / "run-status.json",
                SEED_EVENTS_FILE=self.root / "config/artist-website-seed-events.json"), \
                patch.object(merger, "now_utc", return_value=datetime(2026, 11, 10, tzinfo=timezone.utc)), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(merger.main(), 0)
        self.assertEqual(self.read("events.json"), [show()])
        self.assertEqual(self.read("run-status.json")["artistWebsiteEventsAdded"], 0)

    def test_fresh_same_identity_changed_time_cancellation_and_postponement_win(self):
        self.prepare()
        for changes in [{"startTime": "20:30"}, {"status": "cancelled"}, {"status": "postponed"},
                        {"id": "manual:new-canonical", "mergedFromIds": [show()["id"]]}]:
            with self.subTest(changes=changes):
                self.write("events.json", [])
                fresh = show(**changes)
                self.assertEqual(self.collect([fresh]), 0)
                self.assertEqual(self.read(refresh.CACHE), [fresh])
                self.assertEqual(self.read("events.json"), [])

    def test_current_primary_or_supplemental_replacement_wins_without_cache_resurrection(self):
        self.prepare()
        for target in refresh.FEEDS:
            for status in ["scheduled", "cancelled", "postponed", "private"]:
                with self.subTest(target=target, status=status):
                    for name in refresh.FEEDS:
                        self.write(name, [])
                    replacement = show(id="manual:replacement", mergedFromIds=[show()["id"]],
                                       status=status, startDate="2026-12-21")
                    self.write(target, [replacement])
                    self.assertEqual(self.collect(), 0)
                    self.assertEqual(self.read(target), [replacement])
                    self.assertEqual(self.read(refresh.CACHE), [])

    def test_prior_cancelled_postponed_held_private_and_owner_review_are_never_revived(self):
        variants = [{"status": value} for value in refresh.INACTIVE | {"private"}]
        variants += [{"holdReason": "Owner review"}, {"private": True}]
        for changes in variants:
            with self.subTest(changes=changes):
                record = show(**changes)
                self.write("events.json", [record])
                self.write(refresh.CACHE, [record])
                self.prepare()
                self.write("events.json", [])
                self.assertEqual(self.collect(), 0)
        for name, policy in [("config/private-events.json", [show(status="private")]),
                             ("config/review-held-events.json", [{"publish": False, "excludedEventId": show()["id"]}])]:
            with self.subTest(policy=name):
                self.write("config/private-events.json", [])
                self.write("config/review-held-events.json", [])
                self.write("events.json", [show()])
                self.write(refresh.CACHE, [show()])
                self.prepare()
                self.write(name, policy)  # New editorial decision after the snapshot.
                self.write("events.json", [])
                self.assertEqual(self.collect(), 0)
                self.assertEqual(self.read(name), policy)

    def test_disabled_alias_and_known_owner_hold_are_not_retained_and_roster_is_unchanged(self):
        self.prepare()
        disabled = dict(ARTIST, name="Canonical Artist", aliases=["Accepted Artist"], enabled=False,
                        verified=False, sourceRegistryVerified=False)
        self.write("config/artists.json", [disabled])
        before = (self.root / "config/artists.json").read_bytes()
        self.write("events.json", [])
        self.assertEqual(self.collect(), 0)
        self.assertEqual((self.root / "config/artists.json").read_bytes(), before)
        held = show(id="manual:cj-emulous-kickback-grand-prairie-2026", startDate="2026-11-14")
        self.write("config/artists.json", [ARTIST])
        self.write("events.json", [held])
        self.write(refresh.CACHE, [held])
        self.prepare()
        self.write("events.json", [])
        self.assertEqual(self.collect(), 0)

    def test_canadian_and_ongoing_multiday_facts_survive_but_expired_rows_do_not(self):
        for record, expected in [(show(country="CA", city="Toronto", state="ON"), 1),
                (show(startDate="2026-11-09", endDate="2026-11-10"), 1),
                (show(startDate="2026-11-09"), 0), (show(country="GB"), 0)]:
            with self.subTest(record=record):
                self.write("events.json", [record])
                self.write(refresh.CACHE, [record])
                self.prepare()
                self.write("events.json", [])
                self.assertEqual(self.collect(), expected)
                self.assertEqual(self.read("events.json"), [record] if expected else [])

    def test_exception_invalid_or_stale_status_restores_original_files_and_fails(self):
        self.prepare()
        self.write("events.json", [])
        originals = {name: (self.root / name).read_bytes() for name in (refresh.CACHE, refresh.STATUS, "events.json")}
        cases = [{"failure": subprocess.CalledProcessError(1, ["collector"])},
                 {"status_changes": {"artistsConfigured": 0}},
                 {"status_changes": {"eventsFound": 99}},
                 {"status_changes": {"generatedAt": "2000-01-01T00:00:00Z"}},
                 {"status_changes": {"warningCount": -1}}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises((ValueError, subprocess.CalledProcessError)):
                self.collect(**changes)
            for name, original in originals.items():
                self.assertEqual((self.root / name).read_bytes(), original)

    def test_missing_wrong_run_old_and_unaccepted_snapshots_fail_before_collection(self):
        self.prepare()
        original = refresh.read_json(self.snapshot)
        invalid = [dict(original, run=["other-run", "1"]), dict(original, sourceRoot="/other/checkout"),
            dict(original, generatedAt=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat()),
            dict(original, acceptedWebsiteEvents=[{"candidate": show(), "accepted": show(id="other")}])]
        for value in invalid:
            refresh.save(self.snapshot, value)
            with patch.object(refresh, "run") as command, self.assertRaises(ValueError):
                refresh.websites(self.root, self.snapshot)
            command.assert_not_called()
        self.snapshot.unlink()
        with patch.object(refresh, "run") as command, self.assertRaises(FileNotFoundError):
            refresh.websites(self.root, self.snapshot)
        command.assert_not_called()

    def test_finalize_archives_then_repairs_without_collecting(self):
        with patch.object(refresh, "run", side_effect=self.archive_command) as command:
            refresh.finalize(self.root)
        self.assertEqual([tuple(call.args[1:]) for call in command.call_args_list],
                         [("archive_event_history.py",), ("replay_source_update.py", "normalize")])

    def test_finalize_recounts_after_existing_reviewed_removal_without_changing_records_or_metadata(self):
        import catalog_removals
        retained = [{"archiveKey": "id:kept", "event": show(), "calendarPresence": "present",
                     "dateState": "past", "observedOnOrAfterEventDate": True, "observedInGitHistory": True,
                     "firstSeenOnCalendar": "2026-09-01T12:00:00Z"},
                    {"archiveKey": "id:also-kept", "event": show(id="also-kept"),
                     "calendarPresence": "absent", "dateState": "upcoming"}]
        excluded = {"archiveKey": "id:owner-removed", "event": show(id="owner-removed", artists=["Propaganda"]),
                    "calendarPresence": "present", "dateState": "past",
                    "observedOnOrAfterEventDate": True, "observedInGitHistory": True}
        report = {"historyVersion": 2, "updatedAt": "2026-11-10T12:00:00Z", "customMetadata": {"retain": True},
                  "events": retained + [excluded], "summary": {"totalArchived": 3, "currentlyPresent": 2,
                      "pastDated": 2, "observedOnOrAfterEventDate": 2, "gitHistoryBackfilled": 2,
                      "gitSnapshotsScanned": 7, "unrelatedMetric": 42}}
        def command(root, script, *args):
            if script == "archive_event_history.py":
                self.write("event-history.json", report)
            else:
                self.assertEqual((script, args), ("replay_source_update.py", ("normalize",)))
                catalog_removals.apply(root)  # The established policy removes the reviewed artist.
                self.assertEqual(self.read("event-history.json")["events"], retained)
        with patch.object(refresh, "run", side_effect=command):
            refresh.finalize(self.root)
        expected = dict(report, events=retained, summary=dict(report["summary"], totalArchived=2,
            currentlyPresent=1, pastDated=1, observedOnOrAfterEventDate=1, gitHistoryBackfilled=1))
        self.assertEqual(self.read("event-history.json"), expected)
        before = (self.root / "event-history.json").read_bytes()
        refresh.refresh_archive_counts(self.root)
        self.assertEqual((self.root / "event-history.json").read_bytes(), before)

    def test_both_archive_stages_reject_invalid_history_shape_counts_and_git_proof(self):
        valid = {"historyVersion": 2, "events": [{"event": show()}],
                 "summary": {"totalArchived": 1, "gitSnapshotsScanned": 1}}
        invalid = [[], dict(valid, historyVersion=1), dict(valid, events={}), dict(valid, summary={}),
            dict(valid, summary={"totalArchived": 2, "gitSnapshotsScanned": 1}),
            dict(valid, summary={"totalArchived": 1, "gitSnapshotsScanned": 0}),
            dict(valid, summary={"totalArchived": 1}),
            dict(valid, summary={"totalArchived": 1, "gitSnapshotsScanned": "1"})]
        for stage in ("prepare", "finalize"):
            for report in invalid:
                with self.subTest(stage=stage, report=report):
                    def command(root, script, *args):
                        self.assertEqual(script, "archive_event_history.py")
                        self.write("event-history.json", report)
                    with patch.object(refresh, "run", side_effect=command) as runner, self.assertRaises(ValueError):
                        if stage == "prepare":
                            refresh.prepare(self.root, self.snapshot)
                        else:
                            refresh.finalize(self.root)
                    runner.assert_called_once_with(self.root, "archive_event_history.py")
                    self.assertFalse(self.snapshot.exists(), "Invalid archive must not create retention proof")

    def test_actual_archiver_current_only_success_cannot_bypass_either_stage(self):
        import archive_event_history as archiver
        for stage in ("prepare", "finalize"):
            with self.subTest(stage=stage):
                def command(root, script, *args):
                    self.assertEqual(script, "archive_event_history.py")
                    archiver.main()
                with patch.multiple(archiver, ROOT=self.root, HISTORY_FILE=self.root / "event-history.json",
                        EVENT_FILES=tuple(self.root / name for name in refresh.FEEDS)), \
                        patch.object(archiver, "git_event_snapshots", return_value=[]), \
                        patch.object(refresh, "run", side_effect=command) as runner, \
                        contextlib.redirect_stdout(io.StringIO()), \
                        self.assertRaisesRegex(ValueError, "did not scan any git history"):
                    if stage == "prepare":
                        refresh.prepare(self.root, self.snapshot)
                    else:
                        refresh.finalize(self.root)
                self.assertEqual(self.read("event-history.json")["summary"]["totalArchived"], 1)
                runner.assert_called_once_with(self.root, "archive_event_history.py")
                self.assertFalse(self.snapshot.exists())


if __name__ == "__main__":
    unittest.main()
