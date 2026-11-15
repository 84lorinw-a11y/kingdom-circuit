"""Keep publication readers aligned at real saved event date boundaries.

The shared visibility policy is the contract. These tests exercise independent
readers and rendered catalog data rather than reimplementing that policy.
"""
import ast
import copy
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import add_past_show_archives as archives
import artist_engagement as engagement
import build_seo_site as builder
import calendar_maintenance as maintenance
import event_visibility as visibility
from mobile_discovery import Document
import prune_past_events as pruning
import update_events as collector
import verify_live_redesign as redesign


def raw_date_ordering(source):
    """Find a second event membership policy, allowing exact source fact checks.

    Track raw date values through local assignments and date-returning helpers.
    Calls to the canonical visibility helper are not raw source dates.
    Equality assertions, ordering between two source fields, date parsing and
    receipt clocks are unrelated to the failure and remain allowed.
    """
    tree = ast.parse(source)
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    raw_helpers = set()
    canonical = {"event_last_active_date", "event_is_past"}

    def is_raw(node, names):
        if isinstance(node, ast.Name):
            return node.id in names
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant) and node.slice.value in {"startDate", "endDate"}:
                return True
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name in canonical:
                return False
            if name in raw_helpers:
                return True
            if name == "get" and node.args and isinstance(node.args[0], ast.Constant):
                if node.args[0].value in {"startDate", "endDate"}:
                    return True
        return any(is_raw(child, names) for child in ast.iter_child_nodes(node))

    def names_for(function):
        names = set()
        changed = True
        while changed:
            previous = set(names)
            for node in ast.walk(function):
                if isinstance(node, ast.Assign) and is_raw(node.value, names):
                    names.update(target.id for target in node.targets if isinstance(target, ast.Name))
                elif isinstance(node, ast.AnnAssign) and node.value and is_raw(node.value, names):
                    if isinstance(node.target, ast.Name):
                        names.add(node.target.id)
            changed = names != previous
        return names

    changed = True
    while changed:
        previous = set(raw_helpers)
        for function in functions:
            names = names_for(function)
            if any(isinstance(node, ast.Return) and node.value and is_raw(node.value, names)
                   for node in ast.walk(function)):
                raw_helpers.add(function.name)
        changed = raw_helpers != previous

    violations = []
    for function in functions:
        names = names_for(function)
        for node in ast.walk(function):
            if isinstance(node, ast.Compare):
                values = [node.left, *node.comparators]
                if any(isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE))
                       and is_raw(values[index], names) != is_raw(values[index + 1], names)
                       for index, op in enumerate(node.ops)):
                    violations.append((function.name, node.lineno))
    return sorted(set(violations))


def saved_records():
    """Include archive records so the gate keeps testing events after they expire."""
    records = []
    for relative in ("events.json", "supplemental-events.json", "event-history.json",
                     "config/oct3-verified-concerts.json"):
        data = json.loads((ROOT / relative).read_text())
        records.extend(row.get("event", row)
                       for row in (data.get("events", []) if isinstance(data, dict) else data))
    unique = {json.dumps(row, sort_keys=True): row for row in records}
    return list(unique.values())


class CalendarRolloverContractTests(unittest.TestCase):
    def test_saved_records_agree_before_on_and_after_every_visibility_boundary(self):
        checked = 0
        for event in saved_records():
            last = visibility.event_last_active_date(event)
            try:
                boundary = date.fromisoformat(last)
            except (ValueError, TypeError):
                continue
            before = copy.deepcopy(event)
            with self.subTest(event=event.get("id"), boundary=last):
                self.assertEqual(boundary, archives.event_date(event))
                self.assertEqual(boundary, redesign.event_last_date(event))
                for offset, current in ((-1, True), (0, True), (1, False)):
                    day = boundary + timedelta(days=offset)
                    self.assertEqual(not current, pruning.is_past_event(event, day.isoformat()))
                    self.assertEqual(current, collector.event_is_future(event, day))
                    with patch.object(builder, "VISIBILITY_CUTOFF", day):
                        self.assertEqual(current, builder.current(event))
                self.assertEqual(before, event, "Boundary readers must not rewrite accepted source facts")
            checked += 1
        self.assertGreater(checked, 100, "Expected a meaningful current and historical boundary sample")

    def test_holy_ghost_rendered_card_catalog_and_home_counts_roll_over_together(self):
        event = next(row for row in saved_records()
                     if row.get("id") == "manual:the-holy-ghost-experience-chattanooga-2026-11-14")
        original = copy.deepcopy(event)
        # A fixed independent expectation reproduces the incident even if the
        # shared helper itself changes. Keep the actual Event timestamps intact.
        self.assertEqual("2026-11-15T01:00:00-05:00", event["endDateTime"])
        self.assertEqual("2026-11-14", visibility.event_last_active_date(event))
        card = builder.event_card(event, [])
        document = Document(card)
        rendered = document.one(lambda node: "data-event-card" in node.attrs)
        self.assertEqual("2026-11-14", rendered.attrs["data-end-date"])
        schema = builder.event_schema(event)
        self.assertEqual(event["endDateTime"], schema["endDate"])
        self.assertEqual("2026-11-14", pruning.page_last_date(
            '<script type="application/ld+json">' + json.dumps(schema) + '</script>'))

        href = builder.event_path(event)
        profile = "/artists/fixture/"
        home = ('<script id="kc-fan-artists">' + json.dumps([
            {"name": "Fixture", "href": profile, "count": 1}]) + '</script>'
            f'<a class="kc-discovery-artist" href="{profile}"><strong>Fixture</strong>'
            '<span>1 upcoming show</span></a>')
        show = {"path": href, "date": event["startDate"], "end": rendered.attrs["data-end-date"]}
        for day, count in (("2026-11-14", 1), ("2026-11-15", 0), ("2026-11-16", 0)):
            with self.subTest(day=day):
                context = {"asOf": day, "shows": [show], "artists": {
                    "fixture": {"path": profile, "shows": [href]}}}
                output = engagement.reconcile_artist_counts(home, context)
                catalog = {"asOf": day, "shows": [show], "artists": {profile: [href]}}
                self.assertEqual([], maintenance.artist_discovery_errors(output, catalog, day))
                parsed = Document(output)
                inventory = parsed.one(lambda node: node.attrs.get("id") == "kc-fan-artists")
                self.assertEqual(count, json.loads(parsed.text(inventory))[0]["count"])
                if not count:
                    self.assertTrue(maintenance.artist_discovery_errors(home, catalog, day),
                                    "The original stale one-show card must still be rejected")
        self.assertEqual(original, event)

    def test_future_year_and_daylight_saving_boundaries_keep_same_contract(self):
        fixtures = [
            # New Year ending before the Pacific date changes.
            ("2026-12-31", "2027-01-01T01:00:00-05:00", "2026-12-31"),
            # Both explicit offsets in the repeated autumn hour are valid facts.
            ("2027-11-06", "2027-11-07T01:30:00-04:00", "2027-11-06"),
            ("2027-11-06", "2027-11-07T01:30:00-05:00", "2027-11-06"),
            # An event continuing beyond Pacific midnight remains that day.
            ("2027-03-13", "2027-03-14T05:00:00-04:00", "2027-03-14"),
        ]
        for start, end, expected_last in fixtures:
            event = {"id": "fixture:future", "startDate": start, "endDate": end[:10],
                     "endDateTime": end, "endTime": end[11:16]}
            with self.subTest(end=end):
                self.assertEqual(expected_last, visibility.event_last_active_date(event))
                self.assertEqual(date.fromisoformat(expected_last), redesign.event_last_date(event))
                day = date.fromisoformat(expected_last) + timedelta(days=1)
                self.assertTrue(pruning.is_past_event(event, day.isoformat()))
                self.assertFalse(collector.event_is_future(event, day))

    def test_publication_verifiers_cannot_reintroduce_raw_source_date_ordering(self):
        violations = {}
        paths = set((ROOT / "scripts").glob("verify_*.py"))
        paths.update(ROOT / "scripts" / name for name in (
            "apply_oct2_verified_shows.py", "apply_oct3_concert_corrections.py",
            "preserve_reviewed_discoveries.py", "apply_egr_bizzle_updates.py",
            "apply_man_of_faith_joz_shows.py", "apply_sep26_source_corrections.py",
            "apply_rock_the_pines.py"))
        for path in sorted(paths):
            found = raw_date_ordering(path.read_text())
            if found:
                violations[path.name] = found
        self.assertEqual({}, violations, "Upcoming membership must use the shared event visibility policy")

    def test_contract_guard_catches_original_direct_and_hidden_helper_regressions(self):
        direct = '''
def verify(event, today):
    if (event.get("endDate") or event["startDate"]) < today:
        return False
'''
        helper = '''
def event_last_date(event):
    raw = str(event.get("endDate") or event.get("startDate") or "")[:10]
    return date.fromisoformat(raw)
def verify(event, cutoff):
    last = event_last_date(event)
    return last >= cutoff
'''
        correct = '''
def verify(event, expected, cutoff):
    assert event["startDate"] == expected["startDate"]
    assert event["endDate"] == expected["endDate"]
    assert event["startDate"] <= event["endDate"]
    last = date.fromisoformat(event_last_active_date(event))
    return last >= cutoff
'''
        self.assertTrue(raw_date_ordering(direct))
        self.assertTrue(raw_date_ordering(helper))
        self.assertEqual([], raw_date_ordering(correct))


if __name__ == "__main__":
    unittest.main()
