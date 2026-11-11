import copy
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import add_past_show_archives as archives
import verify_oct8_reviewed_discoveries as discoveries
import verify_show_artwork as artwork


class CancelledEventPreservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name) / "source"
        self.site = Path(temporary.name) / "site"
        for root in (self.source, self.site):
            (root / "config").mkdir(parents=True)
        self.identity = "babytooth-experience-huntington-beach-2026-11-21"
        self.path = "/event/kaden-jordan-the-babytooth-experience-2026-11-21-huntington-beach-f08073/"
        self.event = {
            "id": "manual:" + self.identity, "title": "Kaden Jordan — The Babytooth Experience",
            "startDate": "2026-11-21", "endDate": "2026-11-21", "startTime": "",
            "city": "Huntington Beach", "state": "CA", "country": "US",
            "venue": "15202 Transistor Lane", "address": "15202 Transistor Lane", "postalCode": "92649",
            "artists": ["Kaden Jordan", "Kai Uriah"], "advertisedBilling": ["Kaden Jordan", "Kai Uriah"],
            "officialUrl": "https://partiful.com/e/9wVqEVujrtfNv03Vr5C7", "ticketUrl": "",
            "status": "cancelled", "ticketAvailability": "cancelled", "eventType": "concert",
            "image": "assets/events/babytooth-experience-huntington-beach-2026-11-21.jpg",
            "imageType": "event_artwork", "organizer": {"name": "Kaden Jordan"},
        }
        self.seed = dict(self.event, id=self.identity, editorialBatch=discoveries.BATCH)
        self.pin = {key: self.seed[key] for key in ("id", "startDate", "status", "image", "imageType")}
        self.history = {"version": 1, "events": {self.event["id"]: {
            "path": self.path, "sourceIds": [], "event": copy.deepcopy(self.event)}}}
        self.write(self.source, "config/manual-events.json", [self.seed])
        self.write(self.source, "config/url-continuity.json", self.history)
        roster = [{"name": "Kaden Jordan"}, {"name": "Kai Uriah"},
                  {"name": "REDEEMED", "instagramProfile": "https://www.instagram.com/redeemedmuzic33/",
                   "bandsintownProfile": "https://www.bandsintown.com/a/15645685-redeemed"}]
        for root in (self.source, self.site): self.write(root, "config/artists.json", roster)
        self.write(self.site, "events.json", [])
        self.write(self.site, "supplemental-events.json", [])
        image = self.site / self.event["image"]
        image.parent.mkdir(parents=True)
        image.write_bytes(b"retained original poster")
        self.detail = self.site / self.path.strip("/") / "index.html"
        self.detail.parent.mkdir(parents=True)
        self.detail.write_text(archives.past_page(self.site, self.event, {"kaden-jordan", "kai-uriah"}))
        for path in ("shows", "artists/kaden-jordan", "artists/kai-uriah"):
            target = self.site / path / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("No upcoming performances")

    @staticmethod
    def write(root, name, value):
        (root / name).write_text(json.dumps(value))

    def verify_artwork(self):
        with patch.object(artwork, "ROOT", self.source), patch.object(artwork, "PINS", [self.pin]):
            artwork.verify(self.site)

    def verify_discoveries(self):
        with patch.object(discoveries, "ROOT", self.source), patch.object(discoveries.builder, "current", return_value=True):
            discoveries.verify(self.site)

    def test_cancelled_seed_uses_existing_published_url_in_both_guards(self):
        self.assertNotEqual(artwork.builder.event_path(self.seed), self.path)
        self.verify_artwork()
        self.verify_discoveries()

    def test_missing_retained_page_is_not_silently_replaced_by_recomputed_path(self):
        wrong = self.site / artwork.builder.event_path(self.seed).strip("/") / "index.html"
        wrong.parent.mkdir(parents=True)
        self.detail.rename(wrong)
        with self.assertRaises(FileNotFoundError): self.verify_artwork()
        with self.assertRaises(FileNotFoundError): self.verify_discoveries()

    def test_cancellation_schema_is_still_required(self):
        self.detail.write_text(self.detail.read_text().replace("EventCancelled", "EventScheduled"))
        with self.assertRaisesRegex(AssertionError, "missing cancellation"): self.verify_artwork()
        with self.assertRaisesRegex(AssertionError, "cancellation schema"): self.verify_discoveries()

    def test_original_flyer_is_still_required(self):
        self.detail.write_text(self.detail.read_text().replace(self.event["image"], "assets/events/wrong.jpg"))
        with self.assertRaisesRegex(AssertionError, "detail artwork"): self.verify_artwork()
        with self.assertRaisesRegex(AssertionError, "approved image"): self.verify_discoveries()

    def test_cancelled_show_still_cannot_reappear_in_upcoming_or_artist_schedule(self):
        target = self.site / "shows/index.html"
        target.write_text('<a href="' + self.path + '">Cancelled show</a>')
        with self.assertRaisesRegex(AssertionError, "cancelled show listed"): self.verify_discoveries()
        target.write_text("")
        (self.site / "artists/kaden-jordan/index.html").write_text('<a href="' + self.path + '">Show</a>')
        with self.assertRaisesRegex(AssertionError, "cancelled artist schedule"): self.verify_discoveries()

    def test_mismatched_date_ambiguous_or_unsafe_history_fails_closed(self):
        for change, error in (
            (lambda h: h["events"][self.event["id"]]["event"].update(startDate="2026-11-22"), "retained URL date"),
            (lambda h: h["events"].update({"other": dict(h["events"][self.event["id"]], sourceIds=[self.event["id"]])}), "ambiguous retained"),
            (lambda h: h["events"][self.event["id"]].update(path="/event/../../outside/"), "unsafe retained"),
        ):
            history = copy.deepcopy(self.history); change(history)
            self.write(self.source, "config/url-continuity.json", history)
            with self.subTest(error=error), self.assertRaisesRegex(AssertionError, error): self.verify_artwork()

    def schema(self, event):
        text = archives.past_page(self.site, event, {"kaden-jordan", "kai-uriah"})
        return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)[1])

    def test_reviewed_cancellation_retains_every_prior_structured_fact(self):
        expected = {"@context": "https://schema.org", "@type": "MusicEvent",
                    "name": self.event["title"], "startDate": "2026-11-21", "endDate": "2026-11-21",
                    "eventStatus": "https://schema.org/EventCancelled",
                    "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
                    "url": "https://kingdomcircuit.com" + self.path,
                    "image": ["https://kingdomcircuit.com/" + self.event["image"]],
                    "location": {"@type": "Place", "name": self.event["venue"], "address": {
                        "@type": "PostalAddress", "addressLocality": "Huntington Beach", "addressRegion": "CA",
                        "addressCountry": "US", "streetAddress": self.event["address"], "postalCode": "92649"}},
                    "performer": [{"@type": "MusicGroup", "name": n} for n in self.event["artists"]],
                    "organizer": {"@type": "Organization", "name": "Kaden Jordan"}}
        self.assertEqual(expected, self.schema(self.event))
        # The recorded history is already cancelled: later builds retain facts.
        self.assertEqual(expected, self.schema(self.event))
        self.assertNotIn("offers", expected)

    def test_other_cancelled_or_completed_schemas_are_unchanged(self):
        for event in (dict(self.event, id="manual:other-cancellation"),
                      dict(self.event, startDate="2026-11-22"), dict(self.event, status="scheduled")):
            schema = self.schema(event)
            for field in ("image", "endDate", "organizer"):
                self.assertNotIn(field, schema)

    def test_missing_reviewed_cancellation_facts_block_rendering(self):
        for field in ("image", "organizer"):
            event = dict(self.event); event.pop(field)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "lost retained"):
                self.schema(event)


if __name__ == "__main__": unittest.main()
