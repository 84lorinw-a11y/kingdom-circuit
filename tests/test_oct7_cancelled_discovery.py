import copy
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_oct7_discoveries as oct7
import test_cancelled_event_preservation as preservation


class October7CancellationGuardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = preservation.CancelledEventPreservationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        f.seed["editorialBatch"] = oct7.BATCH
        f.write(f.source, "config/manual-events.json", [f.seed])
        archived = []
        for identity in ("bandsintown:1040305060", "manual:after-doves-at-the-cg-nashville-2026-10-06"):
            event = {"id": identity, "title": "Retained October 6 show", "startDate": "2026-10-06",
                     "endDate": "2026-10-06", "endDateTime": "2026-10-07T00:00:00-05:00",
                     "city": "Nashville", "state": "TN", "artists": []}
            archived.append({"event": event})
            page = f.site / oct7.builder.event_path(event).strip("/") / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text("Past show")
        self.archived = archived
        f.write(f.source, "event-history.json", {"events": archived})

    def verify(self):
        with patch.object(oct7, "ROOT", self.fixture.source), patch.object(oct7.builder, "current", return_value=True):
            oct7.verify(self.fixture.site)

    def rewrite_schema(self, change):
        f = self.fixture
        text = f.detail.read_text()
        match = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', text, re.S)
        schema = json.loads(match[2]); change(schema)
        f.detail.write_text(text[:match.start(2)] + json.dumps(schema) + text[match.end(2):])

    def test_exact_cancelled_seed_passes_without_active_row(self):
        self.verify()

    def test_cancelled_or_scheduled_row_in_either_raw_feed_is_rejected(self):
        f = self.fixture
        for feed in ("events.json", "supplemental-events.json"):
            for status in ("cancelled", "scheduled"):
                f.write(f.site, feed, [dict(f.event, status=status)])
                with self.subTest(feed=feed, status=status), self.assertRaisesRegex(AssertionError, "public feed"):
                    self.verify()
                f.write(f.site, feed, [])

    def test_recomputed_page_cannot_replace_missing_retained_page(self):
        f = self.fixture
        wrong = f.site / oct7.builder.event_path(f.seed).strip("/") / "index.html"
        wrong.parent.mkdir(parents=True); f.detail.rename(wrong)
        with self.assertRaises(FileNotFoundError): self.verify()

    def test_original_artwork_and_full_visible_billing_remain_required(self):
        f = self.fixture; original = f.detail.read_text()
        for token, error in ((f.event["image"], "source artwork"), ("Kai Uriah", "Kai Uriah")):
            f.detail.write_text(original.replace(token, "wrong"))
            with self.subTest(token=token), self.assertRaisesRegex(AssertionError, error): self.verify()
            f.detail.write_text(original)

    def test_cancelled_schema_identity_date_venue_and_full_billing_remain_required(self):
        f = self.fixture; original = f.detail.read_text()
        for change, error in (
            (lambda s: s.update(eventStatus="https://schema.org/EventScheduled"), "cancellation schema"),
            (lambda s: s.update(startDate="2026-11-22"), "identity/date"),
            (lambda s: s["location"].update(name="Wrong venue"), "retained venue"),
            (lambda s: s["performer"].pop(), "full billing"),
            (lambda s: s.update(url="https://kingdomcircuit.com/event/wrong/"), "schema URL"),
        ):
            self.rewrite_schema(change)
            with self.subTest(error=error), self.assertRaisesRegex(AssertionError, error): self.verify()
            f.detail.write_text(original)

    def test_cancelled_show_cannot_have_purchase_offer_or_ticket_action(self):
        f = self.fixture; original = f.detail.read_text()
        self.rewrite_schema(lambda s: s.update(offers={"url": f.event["officialUrl"]}))
        with self.assertRaisesRegex(AssertionError, "purchase offer"): self.verify()
        for label in ("Buy tickets", "Get Tickets", "RSVP", "Register now"):
            f.detail.write_text(original + '<a href="https://example.com">' + label + '</a>')
            with self.subTest(label=label), self.assertRaisesRegex(AssertionError, "ticket action"): self.verify()
        f.detail.write_text(original)

    def test_cancelled_show_stays_off_discovery_and_artist_schedules(self):
        f = self.fixture
        for relative in ("shows/index.html", "artists/kaden-jordan/index.html", "artists/kai-uriah/index.html"):
            target = f.site / relative; original = target.read_text()
            target.write_text('<a href="' + f.path + '">Show</a>')
            with self.subTest(relative=relative), self.assertRaisesRegex(AssertionError, "cancelled (show listed|artist schedule)"):
                self.verify()
            target.write_text(original)

    def test_marked_artist_archive_is_retained_but_cannot_hide_upcoming_leak(self):
        f = self.fixture
        profile = f.site / "artists/kai-uriah/index.html"
        archive = '<section class="past-shows-archive" data-past-shows-archive><a href="' + f.path + '"><strong>Cancelled</strong> · Show</a></section>'
        profile.write_text(archive)
        self.verify()
        profile.write_text(archive.replace("Cancelled", "Upcoming"))
        with self.assertRaisesRegex(AssertionError, "unmarked cancelled archive"): self.verify()
        profile.write_text('<a href="' + f.path + '">Upcoming show</a>' + archive)
        with self.assertRaisesRegex(AssertionError, "cancelled artist schedule"): self.verify()

    def test_other_ids_or_dates_do_not_get_a_cancellation_bypass(self):
        f = self.fixture
        for changed in (dict(f.seed, id="another-cancelled-event"), dict(f.seed, startDate="2026-11-22")):
            f.write(f.source, "config/manual-events.json", [changed])
            with self.subTest(changed=changed["id"]), self.assertRaisesRegex(AssertionError, "missing or duplicate"):
                self.verify()

    def test_scheduled_event_still_requires_exact_feed_row_facts_and_listing(self):
        f = self.fixture
        seed = dict(f.seed, status="scheduled", ticketAvailability="available", ticketUrl=f.event["officialUrl"])
        event = dict(seed, id="manual:" + seed["id"])
        f.write(f.source, "config/manual-events.json", [seed])
        with self.assertRaisesRegex(AssertionError, "missing or duplicate"): self.verify()
        f.write(f.site, "events.json", [event])
        with self.assertRaisesRegex(AssertionError, "shows list"): self.verify()
        (f.site / "shows/index.html").write_text('<a href="' + f.path + '">Show</a>')
        self.verify()
        f.write(f.site, "events.json", [dict(event, venue="Wrong venue")])
        with self.assertRaisesRegex(AssertionError, "venue"): self.verify()

    def test_october6_archive_checks_remain_required(self):
        f = self.fixture
        old = self.archived[0]["event"]
        page = f.site / oct7.builder.event_path(old).strip("/") / "index.html"
        page.write_text("No notice")
        with self.assertRaisesRegex(AssertionError, "missing archive notice"): self.verify()


if __name__ == "__main__": unittest.main()
