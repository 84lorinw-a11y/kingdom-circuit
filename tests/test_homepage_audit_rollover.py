"""A portrait regression check must not require a permanent artist booking."""

from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_seo_site as builder
import verify_public_audit as verifier


class HomepageAuditRolloverTests(unittest.TestCase):
    def pages(self, home=""):
        pages = {Path("index.html"): home}
        jimmy_cards = []
        for event_id in (
            "jimmy-rock-worship-wawa-miami-2026",
            "jimmy-rock-rave-worship-centennial-2026",
            "boise-invasion-2026",
            "jimmy-rock-rave-worship-dallas-2026",
        ):
            event = dict(verifier.requested_events.UPSERTS[event_id], id="manual:" + event_id)
            framing = "artist-photo" if "wawa" in event_id else "event-artwork"
            jimmy_cards.append(
                f'<article data-event-card><a href="{builder.event_path(event)}">Show</a>'
                f'<img class="{framing}" src="/assets/optimized/jimmy.webp"></article>'
            )
        pages[Path("artists/jimmy-rock/index.html")] = "".join(jimmy_cards)
        for path, asset in (
            ("event/one-day-fall-festival-2026-evening-concert-2026-10-10-aurora-587532/index.html",
             "/assets/events/one-day-festival-2026-10-10-lineup-crop.png"),
            ("event/reign-volume-one-2026-10-10-brooklyn-fe93fe/index.html",
             "/assets/events/reign-volume-one-2026-10-10-portrait.jpg"),
        ):
            pages[Path(path)] = f'<div class="event-detail-media"><img src="{asset}"></div>'
        pages[Path("event/boxyard-saturdaze-2026-10-10-durham-7853b4/index.html")] = (
            '<a href="https://boxyard.rtp.org/">Official details</a>'
        )
        pages[Path("event/mayia-at-the-nc-state-fair-2026-10-17-raleigh-1c07ad/index.html")] = (
            '<a href="https://ncagr.gov/">Official details</a>'
        )
        return pages

    def card(self, image_class="artist-photo", position="50% 4%"):
        return (
            '<article data-event-card data-date="2026-11-20">'
            '<h3><a href="/event/kurtis-current/">Kurtis Hoppie Live</a></h3>'
            f'<img class="{image_class}" src="/assets/optimized/kurtis.webp" '
            f'style="object-position:{position}"></article>'
        )

    def audit(self, pages, day=date(2026, 11, 21)):
        audit = verifier.Audit()
        with patch.object(builder, "VISIBILITY_CUTOFF", day):
            verifier.verify_requested_live_repairs(pages, audit)
        return audit

    def test_last_booking_can_expire_without_blocking_publication(self):
        event = {"startDate": "2026-11-20", "artists": ["Kurtis Hoppie"]}
        for day in (date(2026, 11, 20), date(2026, 11, 21), date(2026, 12, 1)):
            with self.subTest(day=day), patch.object(builder, "VISIBILITY_CUTOFF", day):
                home = self.card() if builder.current(event) else ""
                self.assertEqual([], self.audit(self.pages(home), day).failures)

    def test_artist_without_current_bookings_need_not_appear(self):
        self.assertEqual([], self.audit(self.pages()).failures)

    def test_artist_with_future_booking_outside_homepage_selection_need_not_appear(self):
        pages = self.pages('<article data-event-card><h3>EGR Live</h3></article>')
        pages[Path("artists/kurtis-hoppie/index.html")] = self.card().replace(
            'data-date="2026-11-20"', 'data-date="2027-02-20"'
        )
        self.assertEqual([], self.audit(pages).failures)

    def test_present_portrait_keeps_approved_crop(self):
        self.assertEqual([], self.audit(self.pages(self.card())).failures)

    def test_present_portrait_with_bad_crop_still_fails(self):
        audit = self.audit(self.pages(self.card(position="50% 50%")))
        self.assertEqual(["homepage Kurtis Hoppie portrait crop regressed"], audit.failures)

    def test_real_event_artwork_does_not_require_portrait_crop(self):
        self.assertEqual([], self.audit(self.pages(self.card("event-artwork", "50% 50%"))).failures)

    def test_unrelated_archive_artwork_guards_are_still_enforced(self):
        pages = self.pages()
        pages.pop(Path("event/reign-volume-one-2026-10-10-brooklyn-fe93fe/index.html"))
        self.assertTrue(any("requested repaired event page is missing" in error
                            for error in self.audit(pages).failures))

    def test_unrelated_current_artist_listing_guard_is_still_enforced(self):
        pages = self.pages()
        pages.pop(Path("artists/jimmy-rock/index.html"))
        self.assertTrue(any("Jimmy Rock repaired listing missing" in error
                            for error in self.audit(pages).failures))


if __name__ == "__main__":
    unittest.main()
