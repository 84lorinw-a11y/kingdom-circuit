import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_seo_site import event_path
from finalize_pending_details import apply
from preserve_reviewed_discoveries import apply as preserve


class PendingDetailsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.events = [
            e for e in json.loads((ROOT / "config/manual-events.json").read_text())
            if e.get("editorialBatch") == "2026-09-30-whatuprg-announced"
        ]

    def test_refresh_preserves_all_three_verified_dates_without_duplicates(self):
        (self.root / "config").mkdir()
        (self.root / "config/manual-events.json").write_text(json.dumps(self.events))
        rows = [
            {
                "id": "manual:" + e["id"],
                "startDate": e["startDate"],
                "startTime": "19:00",
            }
            for e in self.events
        ]
        preserve(self.root, rows, [], today="2026-10-03")
        snapshot = copy.deepcopy(rows)
        preserve(self.root, rows, [], today="2026-10-03")
        self.assertEqual(rows, snapshot)
        self.assertEqual(
            {(e["city"], e["startDate"]) for e in rows},
            {
                ("Houston", "2026-11-19"),
                ("Fort Worth", "2026-11-20"),
                ("San Antonio", "2026-11-22"),
            },
        )
        for e in rows:
            self.assertFalse(e["detailsPending"])
            self.assertEqual(e["startTime"], "19:30")
            self.assertEqual(e["artists"], ["WHATUPRG", "aftrthght", "De La Cruz"])
            self.assertEqual(e["firstSeen"], "2026-09-30T03:02:53.929665Z")

    def test_verified_page_is_not_relabeled_as_pending(self):
        event = dict(self.events[0], id="manual:" + self.events[0]["id"])
        (self.root / "events.json").write_text(json.dumps([event]))
        path = event_path(event)
        page = self.root / path.strip("/") / "index.html"
        page.parent.mkdir(parents=True)
        schema = {
            "@type": "MusicEvent",
            "startDate": event["startDate"],
            "location": {"@type": "Place", "name": event["venue"]},
            "offers": {"url": event["ticketUrl"]},
        }
        page.write_text(
            '<dl><div><dt>Status</dt><dd>Scheduled</dd></div>'
            f'<div><dt>Venue</dt><dd>{event["venue"]}</dd></div>'
            f'<div><dt>Time</dt><dd>{event["startTime"]}</dd></div></dl>'
            '<script type="application/ld+json">'
            + json.dumps(schema)
            + "</script>"
        )
        card = '<article data-event-card><div class="event-badges"></div><a href="{}">Show</a></article>'
        listing = self.root / "index.html"
        other = card.format("/event/unrelated/")
        listing.write_text(card.format(path) + other)
        apply(self.root)
        first = page.read_text(), listing.read_text()
        apply(self.root)
        self.assertEqual(first, (page.read_text(), listing.read_text()))
        self.assertNotIn("Announced — details pending", first[0])
        self.assertNotIn("data-kc-pending-details", first[1])
        self.assertIn(event["venue"], first[0])
        self.assertIn(event["startTime"], first[0])
        self.assertIn(other, first[1])

    def test_cancelled_pending_record_is_not_relabeled(self):
        event = dict(self.events[0], status="cancelled", detailsPending=True)
        (self.root / "events.json").write_text(json.dumps([event]))
        page = self.root / event_path(event).strip("/") / "index.html"
        page.parent.mkdir(parents=True)
        text = "<dt>Status</dt><dd>Cancelled</dd>"
        page.write_text(text)
        apply(self.root)
        self.assertEqual(page.read_text(), text)


if __name__ == "__main__":
    unittest.main()
