#!/usr/bin/env python3
"""Archive and collect websites within the single coordinated source refresh.

The workflow keeps its named base/expanded collectors, seed merge and validation
steps. This helper never replays those network collectors during publication.
Only exact website identities already accepted in a feed may survive an omission;
current provider/editorial records always win. Standard repairs follow the merge.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from apply_curated_catalog_policy import curate_event, is_known_duplicate_fragment
from canadian_event_guard import today_cutoff
from catalog_removals import removed_event
from collect_bandsintown_rest import country_code
from collect_artist_website_events import eligible_website
import private_events
from run_bandsintown_refresh import exact_identities, norm
from show_information_model import is_private_event

ROOT = Path(__file__).resolve().parents[1]
CACHE = "artist-website-events.json"
STATUS = "artist-website-status.json"
FEEDS = ("events.json", "supplemental-events.json")
INACTIVE = {"cancelled", "canceled", "postponed", "rescheduled", "merged", "held", "hold", "removed"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    value = read_json(path)
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"Expected an array of objects: {path.name}")
    return value


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(root, script, *arguments):
    subprocess.run([sys.executable, str(root / "scripts" / script), *arguments], cwd=root, check=True)


def archive(root):
    run(root, "archive_event_history.py")
    # Retain the retired standalone workflow's validation. The archiver can
    # finish with current rows alone when git history cannot be read.
    history = read_json(root / "event-history.json")
    if (not isinstance(history, dict) or history.get("historyVersion") != 2
            or not isinstance(history.get("events"), list)):
        raise ValueError("Archive must contain version 2 history and an event list")
    summary = history.get("summary")
    if not isinstance(summary, dict) or summary.get("totalArchived") != len(history["events"]):
        raise ValueError("Archive total does not match its event list")
    scanned = summary.get("gitSnapshotsScanned", 0)
    if type(scanned) is not int or scanned < 1:
        raise ValueError("Archive did not scan any git history snapshots")


def refresh_archive_counts(root):
    """Report the normalized archive without filtering or changing its records."""
    history = read_json(root / "event-history.json")
    records = history["events"]
    counts = {
        "totalArchived": len(records),
        "currentlyPresent": sum(1 for record in records if record.get("calendarPresence") == "present"),
        "pastDated": sum(1 for record in records if record.get("dateState") == "past"),
        "observedOnOrAfterEventDate": sum(1 for record in records if record.get("observedOnOrAfterEventDate")),
        "gitHistoryBackfilled": sum(1 for record in records if record.get("observedInGitHistory")),
    }
    if any(history["summary"].get(key) != value for key, value in counts.items()):
        history["summary"].update(counts)
        save(root / "event-history.json", history)


def run_identity():
    return [os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")]


def stamp():
    return datetime.now(timezone.utc)


def parse_stamp(value):
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Expected a timezone-aware timestamp")
    return result


def prepare(root, snapshot):
    """Capture accepted identities before base collection can replace the feeds."""
    accepted = [event for name in FEEDS for event in rows(root / name)]
    candidates = rows(root / CACHE)
    retained = []
    for candidate in candidates:
        matches = [event for event in accepted if exact_identities(candidate) & exact_identities(event)]
        if matches:
            # Do not choose between contradictory copies in separate feeds.
            if any(event != matches[0] for event in matches[1:]):
                continue
            retained.append({"candidate": candidate, "accepted": matches[0]})
    payload = {"version": 1, "sourceRoot": str(root.resolve()), "run": run_identity(),
               "generatedAt": stamp().isoformat(), "acceptedWebsiteEvents": retained}
    archive(root)
    run(root, "sync_verified_artist_websites.py")
    save(snapshot, payload)
    return len(retained)


def read_snapshot(root, snapshot):
    value = read_json(snapshot)
    if (not isinstance(value, dict) or value.get("version") != 1
            or value.get("sourceRoot") != str(root.resolve()) or value.get("run") != run_identity()):
        raise ValueError("Website retention snapshot does not belong to this checkout/run")
    age = stamp() - parse_stamp(value.get("generatedAt"))
    if not -timedelta(minutes=2) <= age <= timedelta(hours=24):
        raise ValueError("Website retention snapshot is stale")
    entries = value.get("acceptedWebsiteEvents")
    if not isinstance(entries, list):
        raise ValueError("Invalid accepted website snapshot")
    for entry in entries:
        if (not isinstance(entry, dict) or not isinstance(entry.get("candidate"), dict)
                or not isinstance(entry.get("accepted"), dict)
                or not exact_identities(entry["candidate"]) & exact_identities(entry["accepted"])):
            raise ValueError("Website snapshot lacks an exact previously accepted identity")
    return entries


def eligible_prior(event, root, artists, cutoff):
    """Only restore an unchanged accepted row; normalization remains authoritative."""
    if (country_code(event.get("country")) not in {"US", "CA"}
            or event.get("holdReason") or norm(event.get("status")) in INACTIVE
            or is_private_event(event) or removed_event(event)
            or is_known_duplicate_fragment(event) or curate_event(event) is None):
        return False
    if any(private_events.matches(event, held) for held in private_events.records(root)):
        return False  # The dedicated private-booking guard owns this record.
    holds = root / "config/review-held-events.json"
    for held in rows(holds) if holds.exists() else []:
        if held.get("publish") is False:
            identities = exact_identities(held.get("event") or {})
            if held.get("excludedEventId"):
                identities.add(held["excludedEventId"])
            if exact_identities(event) & identities:
                return False
    disabled = {norm(name) for artist in artists if artist.get("enabled", True) is False
                for name in [artist.get("name"), *(artist.get("aliases") or [])] if name}
    owner = event.get("trackedArtist") or event.get("headliner")
    if (owner and norm(owner) in disabled) or all(norm(name) in disabled for name in event.get("artists", [])):
        return False
    try:
        start = date.fromisoformat(str(event.get("startDate") or ""))
    except ValueError:
        return False
    try:
        end = date.fromisoformat(str(event.get("endDate") or ""))
    except ValueError:
        end = start
    return max(start, end).isoformat() >= cutoff


def check_status(status, candidates, artists, started):
    enabled = [artist for artist in artists if artist.get("enabled", True)]
    if (not isinstance(status, dict)
            or status.get("mode") != "all-tracked-artists-official-website-scan"
            or status.get("artistsConfigured") != len(enabled)
            or status.get("officialWebsitesChecked") != sum(bool(eligible_website(artist)) for artist in enabled)
            or status.get("eventsFound") != len(candidates)
            or not isinstance(status.get("warnings"), list)
            or type(status.get("warningCount")) is not int
            or status["warningCount"] < len(status["warnings"])):
        raise ValueError("Website collector produced an incomplete status")
    generated = parse_stamp(status.get("generatedAt"))
    if generated < started - timedelta(seconds=2) or generated > stamp() + timedelta(minutes=2):
        raise ValueError("Website collector did not produce a current status")


def websites(root, snapshot):
    entries = read_snapshot(root, snapshot)  # Fail before any collector on a bad snapshot.
    artists = rows(root / "config/artists.json")
    primary = rows(root / FEEDS[0])
    current = primary + rows(root / FEEDS[1])
    originals = {name: (root / name).read_bytes() if (root / name).exists() else None
                 for name in (CACHE, STATUS, FEEDS[0])}
    started = stamp()
    try:
        run(root, "collect_artist_website_events.py")
        fresh = rows(root / CACHE)
        status = read_json(root / STATUS)
        check_status(status, fresh, artists, started)
        present = {identity for event in fresh for identity in exact_identities(event)}
        retained = []
        restored = False
        for entry in entries:
            candidate, accepted = entry["candidate"], entry["accepted"]
            identities = exact_identities(candidate) | exact_identities(accepted)
            if present & identities or not eligible_prior(accepted, root, artists, today_cutoff()):
                continue
            replacements = [event for event in current if identities & exact_identities(event)]
            if any(event != accepted for event in replacements):
                continue  # A new current record wins in full, including cancellation.
            # Restore finalized facts, including firstSeen, before the ordinary
            # merge: re-finalizing only a raw candidate would reset its discovery.
            if not replacements:
                primary.append(deepcopy(accepted))
                restored = True
            # Keep the accepted cache identity even when the unchanged row is
            # already present, so a second omission tomorrow has the same proof.
            fresh.append(deepcopy(candidate))
            retained.append(accepted)
            present.update(identities)
        status["previouslyAcceptedWebsiteShows"] = len(entries)
        status["missingProviderShowsRetained"] = len(retained)
        status["missingProviderReview"] = [{"id": event["id"], "officialUrl": event.get("officialUrl", ""),
            "reason": "absent_from_current_website_output_not_confirmed_cancelled"} for event in retained]
        save(root / CACHE, fresh)
        save(root / STATUS, status)
        if restored:
            save(root / FEEDS[0], primary)
        return len(retained)
    except BaseException:
        for name, original in originals.items():
            path = root / name
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise


def finalize(root):
    archive(root)
    # Historical git snapshots must not override the latest reviewed corrections.
    run(root, "replay_source_update.py", "normalize")
    refresh_archive_counts(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "websites", "finalize"))
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    if args.stage == "finalize":
        finalize(ROOT)
        return 0
    snapshot = args.snapshot
    if snapshot is None:
        runner_temp = os.environ.get("RUNNER_TEMP")
        if not runner_temp:
            parser.error("prepare/websites require --snapshot or RUNNER_TEMP")
        snapshot = Path(runner_temp) / ("accepted-website-events-" + "-".join(run_identity()) + ".json")
    if snapshot.resolve().is_relative_to(ROOT):
        parser.error("The retention snapshot must be outside the published source checkout")
    count = prepare(ROOT, snapshot) if args.stage == "prepare" else websites(ROOT, snapshot)
    print(f"Coordinated source {args.stage}: {count} previously accepted website show(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
