import datetime as dt
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import add_past_show_archives as archives
import verify_oct7_discoveries as oct7
import test_oct7_cancelled_discovery as cancellation


class PostponedEventPreservationTests(unittest.TestCase):
    def setUp(self):
        self.cancelled = cancellation.October7CancellationGuardTests()
        self.cancelled.setUp()
        self.addCleanup(self.cancelled.doCleanups)
        self.fixture = self.cancelled.fixture
        f = self.fixture
        self.cancelled_schema = f.schema(f.event)
        for event in (f.event, f.seed, f.pin):
            event.update(status="postponed", ticketAvailability="postponed", ticketUrl="")
        f.write(f.source, "config/manual-events.json", [f.seed])
        f.detail.write_text(archives.past_page(f.site, f.event, {"kaden-jordan", "kai-uriah"}))

    def verify(self):
        self.cancelled.verify()

    def test_postponed_page_keeps_all_original_structured_facts(self):
        expected = dict(self.cancelled_schema, eventStatus="https://schema.org/EventPostponed")
        self.assertEqual(expected, self.fixture.schema(self.fixture.event))
        self.verify()
        self.fixture.verify_artwork()

    def test_future_and_past_postponements_are_retained_without_completed_claim(self):
        f = self.fixture
        today = dt.datetime.now(archives.PACIFIC).date()
        for offset in (3, -1):
            day = (today + dt.timedelta(days=offset)).isoformat()
            event = dict(f.event, id="manual:postponed-fixture", startDate=day, endDate=day,
                         confidence="high", mergedFromIds=["postponed-alias"])
            records = [{"event": event, "observedOnOrAfterEventDate": False},
                       {"event": dict(event, id="postponed-alias", mergedFromIds=[]),
                        "observedOnOrAfterEventDate": False},
                       {"event": dict(event, id="scheduled-fixture", status="scheduled", mergedFromIds=[]),
                        "observedOnOrAfterEventDate": False}]
            f.write(f.site, "event-history.json", {"events": records})
            selected, _ = archives.load_events(f.site)
            with self.subTest(day=day):
                self.assertEqual([event], selected)
                self.assertEqual(records, json.loads((f.site / "event-history.json").read_text())["events"])
                page = archives.past_page(f.site, event, set())
                self.assertIn("https://schema.org/EventPostponed", page)
                self.assertIn("This event was postponed.", page)
                self.assertIn("New date to be announced.", page)
                self.assertIn("Originally scheduled", page)
                self.assertNotIn("EventCompleted", page)
                self.assertNotIn("This event has passed.", page)
                self.assertNotIn("This event was cancelled.", page)
                self.assertLess(page.index("This event was postponed."), page.index("<article"))
                self.assertIn("<strong>Postponed</strong>", archives.archive_row(event, set()))
                self.assertIn("Show archive", archives.section(selected, set()))

    def test_original_artwork_and_retained_schema_facts_remain_required(self):
        f = self.fixture
        original = f.detail.read_text()
        for change, error in (
            (lambda s: s.update(eventStatus="https://schema.org/EventCancelled"), "postponement schema"),
            (lambda s: s.update(startDate="2026-11-22"), "identity/date"),
            (lambda s: s["location"].update(name="Wrong venue"), "retained venue"),
            (lambda s: s["performer"].pop(), "full billing"),
        ):
            self.cancelled.rewrite_schema(change)
            with self.subTest(error=error), self.assertRaisesRegex(AssertionError, error):
                self.verify()
            f.detail.write_text(original)
        for field in ("image", "organizer"):
            event = dict(f.event); event.pop(field)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "lost retained"):
                f.schema(event)
        f.detail.write_text(original.replace(f.event["image"], "assets/events/wrong.jpg"))
        with self.assertRaisesRegex(AssertionError, "detail artwork"):
            f.verify_artwork()

    def test_postponement_and_new_date_notice_are_both_required(self):
        f = self.fixture
        original = f.detail.read_text()
        for old, new, error in (("This event was postponed.", "This event was cancelled.", "visible postponement"),
                                ("New date to be announced.", "Check with the organizer.", "new date")):
            # Remove the status row as well so the notice assertion cannot be
            # satisfied by an unrelated label elsewhere on the page.
            changed = original.replace(old, new).replace("<dd>Postponed</dd>", "<dd>Unknown</dd>")
            if "visible" in error:
                changed = changed.replace("Postponed event", "Event archive").replace("Postponed:", "Status:")
            f.detail.write_text(changed)
            with self.subTest(error=error), self.assertRaisesRegex(AssertionError, error): self.verify()
            f.detail.write_text(original)

    def test_postponed_record_cannot_return_to_either_public_feed(self):
        f = self.fixture
        for feed in ("events.json", "supplemental-events.json"):
            for status in ("postponed", "cancelled", "scheduled"):
                f.write(f.site, feed, [dict(f.event, status=status)])
                with self.subTest(feed=feed, status=status), self.assertRaisesRegex(AssertionError, "public feed"):
                    self.verify()
                f.write(f.site, feed, [])

    def test_ticket_actions_offers_and_upcoming_placement_remain_forbidden(self):
        f = self.fixture
        original = f.detail.read_text()
        self.cancelled.rewrite_schema(lambda s: s.update(offers={"url": f.event["officialUrl"]}))
        with self.assertRaisesRegex(AssertionError, "purchase offer"): self.verify()
        for label in ("Buy tickets", "RSVP", "Register now"):
            f.detail.write_text(original + '<a href="https://example.com">' + label + '</a>')
            with self.subTest(label=label), self.assertRaisesRegex(AssertionError, "ticket action"): self.verify()
        f.detail.write_text(original)
        for relative in ("shows/index.html", "artists/kaden-jordan/index.html", "artists/kai-uriah/index.html"):
            target = f.site / relative; before = target.read_text()
            target.write_text('<a href="' + f.path + '">Show</a>')
            with self.subTest(relative=relative), self.assertRaisesRegex(AssertionError, "postponed (show listed|artist schedule)"):
                self.verify()
            target.write_text(before)

    def test_postponed_archive_label_cannot_hide_upcoming_leak(self):
        f = self.fixture
        profile = f.site / "artists/kai-uriah/index.html"
        archive = archives.section([f.event], {"kaden-jordan", "kai-uriah"})
        profile.write_text(archive)
        self.verify()
        profile.write_text(archive.replace("<strong>Postponed</strong>", "<strong>Cancelled</strong>"))
        with self.assertRaisesRegex(AssertionError, "unmarked postponed archive"): self.verify()
        profile.write_text('<a href="' + f.path + '">Upcoming show</a>' + archive)
        with self.assertRaisesRegex(AssertionError, "postponed artist schedule"): self.verify()

    def test_only_exact_reviewed_identity_gets_inactive_verification(self):
        f = self.fixture
        for changed in (dict(f.seed, id="other-postponed-event"), dict(f.seed, startDate="2026-11-22")):
            f.write(f.source, "config/manual-events.json", [changed])
            with self.subTest(id=changed["id"]), self.assertRaisesRegex(AssertionError, "missing or duplicate"):
                self.verify()


if __name__ == "__main__": unittest.main()
