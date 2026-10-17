import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_verified_show_artwork as artwork


class VerifiedShowArtworkTests(unittest.TestCase):
    def test_returning_808_calendar_keeps_reviewed_url_flyer_and_original_discovery(self):
        canonical = dict(id='manual:808-beezy-bandsintown-108856031',
                         title='808 BEEZY — Live at FCA Warrior Night', startDate='2026-11-02',
                         startTime='20:00', venue='FCA Warrior Night', city='Fort Wayne',
                         state='IN', artists=['808 BEEZY'], firstSeen='2026-09-12')
        incoming = dict(canonical, id='bandsintown:108856031', title='FCA Warrior Night',
                        firstSeen='2026-10-17', image='artist-photo.webp')
        history = [{'event': copy.deepcopy(canonical), 'firstSeenOnCalendar': '2026-09-11'},
                   {'event': dict(incoming, firstSeen='2026-09-02')},
                   {'event': dict(incoming, startDate='2025-11-02', firstSeen='2025-09-02')}]
        before = copy.deepcopy(history)
        self.assertEqual(1, artwork.reconcile_provider_duplicates({'primary': [incoming]}, history))
        self.assertEqual(canonical['id'], incoming['id'])
        self.assertEqual(canonical['title'], incoming['title'])
        self.assertEqual('2026-09-02', incoming['firstSeen'])
        self.assertEqual(artwork.BY_ID[canonical['id'].removeprefix('manual:')]['image'], incoming['image'])
        self.assertEqual(before, history)

    def test_known_manual_prefix_reimports_keep_already_published_unprefixed_ids(self):
        from build_seo_site import event_path
        for alias, identity in artwork.PROVIDER_ALIASES.items():
            if not alias.startswith('manual:'):
                continue
            canonical = dict(id=identity, title='Reviewed show', startDate=artwork.BY_ID[identity]['startDate'],
                             venue='Reviewed venue', city='Reviewed city', state='TX', artists=['Artist'],
                             timezone='America/Chicago', endTime='23:00', firstSeen='2026-09-01')
            incoming = dict(canonical, id=alias, timezone='', endTime='', firstSeen='2026-10-17')
            wanted_path = event_path(canonical)
            feeds = {'primary': [incoming], 'manual': [canonical]}
            artwork.reconcile_provider_duplicates(feeds)
            self.assertEqual(wanted_path, event_path(incoming))
            self.assertEqual('America/Chicago', incoming['timezone'])
            self.assertEqual('23:00', incoming['endTime'])
            self.assertEqual('2026-09-01', incoming['firstSeen'])

    def test_manual_reimport_keeps_full_billing_without_expanding_curated_profiles(self):
        identity = 'above-the-noise-rooftop-washington-2026-10-31'
        canonical = dict(id=identity, title='Above the Noise', startDate='2026-10-31',
                         venue='Rooftop', city='Washington', state='DC', artists=['Howard Langford'],
                         advertisedBilling=['Nate Period', 'Howard Langford', 'Kevin "KC" Campbell'])
        incoming = dict(canonical, id='manual:' + identity, artists=list(canonical['advertisedBilling']))
        artwork.reconcile_provider_duplicates({'primary': [incoming], 'manual': [canonical]})
        self.assertEqual(['Howard Langford'], incoming['artists'])
        self.assertEqual(3, len(incoming['advertisedBilling']))

    def test_current_manual_artist_associations_win_over_stale_supplemental_copy(self):
        identity = 'above-the-noise-rooftop-washington-2026-10-31'
        seed = dict(id=identity, title='Above the Noise', startDate='2026-10-31',
                    venue='Rooftop', city='Washington', state='DC',
                    artists=['Nate Period', 'Howard Langford', 'Kevin "KC" Campbell'],
                    advertisedBilling=['Nate Period', 'Howard Langford', 'Kevin "KC" Campbell', 'Bre Black'])
        stale = dict(seed, artists=['Howard Langford'])
        incoming = dict(seed, id='manual:' + identity)
        feeds = {'events.json': [incoming], 'supplemental-events.json': [stale],
                 'config/manual-events.json': [seed]}
        artwork.reconcile_provider_duplicates(feeds)
        self.assertEqual(['Nate Period', 'Howard Langford', 'Kevin "KC" Campbell'], incoming['artists'])
        self.assertEqual(incoming['artists'], stale['artists'])
        self.assertNotIn('Bre Black', incoming['artists'])
        self.assertIn('Bre Black', incoming['advertisedBilling'])

    def test_observed_label_calendar_duplicates_keep_published_provider_pages(self):
        for identity, verified in artwork.PUBLISHED_DATES.items():
            alias, canonical_id = next((k, v) for k, v in artwork.PROVIDER_ALIASES.items()
                                       if v.removeprefix('manual:') == identity)
            canonical = dict(id=canonical_id, title='Published concert', **verified, startTime='19:00',
                             venue='Reviewed venue', city='Reviewed city', state='TX', artists=['Artist'])
            incoming = dict(canonical, id=alias, title='Label concert', startTime='')
            feeds = {'primary': [incoming], 'supplemental': [canonical]}
            artwork.reconcile_provider_duplicates(feeds)
            self.assertEqual(canonical_id, incoming['id'])
            self.assertEqual('Published concert', incoming['title'])
            self.assertEqual('19:00', incoming['startTime'])

    def test_reviewed_glovember_keeps_music_time_and_complete_bill(self):
        from apply_sep26_requested_lineups import PATCHES
        canonical = dict(copy.deepcopy(PATCHES['bandsintown:1040378722']),
                         id='bandsintown:1040378722', city='Los Angeles', state='CA')
        incoming = dict(canonical, id='ticketmaster:vv1AaZkfMGkd2fZDG',
                        startTime='19:00', artists=['Miles Minnick'])
        feeds = {'primary': [incoming], 'supplemental': [canonical]}
        self.assertEqual(1, artwork.reconcile_provider_duplicates(feeds))
        self.assertEqual('20:00', incoming['startTime'])
        self.assertIn('CJ Emulous', incoming['artists'])
        self.assertIn('Eli Williams', incoming['advertisedBilling'])
        self.assertEqual(canonical, incoming)

    def test_reviewed_festival_collapses_exact_primary_duplicate_not_other_shows(self):
        from apply_sep26_requested_lineups import PATCHES
        canonical = dict(copy.deepcopy(PATCHES['rock-the-universe-orlando-2027']),
                         id='manual:rock-the-universe-orlando-2027')
        incoming = dict(canonical, id='official:498b9c1935ee983f352d')
        other = dict(canonical, id='separate-unreviewed-performance')
        feeds = {'primary': [incoming, canonical, other]}
        self.assertEqual(1, artwork.reconcile_provider_duplicates(feeds))
        self.assertEqual([canonical['id'], other['id']], [row['id'] for row in feeds['primary']])
        self.assertEqual('2027-01-23', feeds['primary'][0]['endDate'])

    def test_exact_provider_duplicate_preserves_reviewed_identity_details_and_age(self):
        from build_seo_site import event_path, merge_events
        canonical = dict(id='bandsintown:108881783', title='Hulvey at Vines Center',
                         startDate='2026-11-06', startTime='20:00', venue='Vines Center',
                         city='Lynchburg', state='VA', artists=['Hulvey'], status='scheduled',
                         sources=[{'name': 'Reviewed venue'}])
        incoming = dict(canonical, id='official:82953bf17964628bbd9b',
                        title='Hulvey — Live at Vines Center', startTime='',
                        firstSeen='2026-10-17', sources=[{'name': 'Reach Records'}],
                        status='cancelled', image='artist-photo.jpg')
        old_path, canonical_path = event_path(incoming), event_path(canonical)
        feeds = {'events.json': [incoming], 'supplemental-events.json': [canonical]}
        history = [{'event': copy.deepcopy(canonical), 'firstSeenOnCalendar': '2026-09-01'}]
        self.assertEqual(1, artwork.reconcile_provider_duplicates(feeds, history))
        self.assertEqual(canonical, incoming)
        self.assertEqual(canonical_path, event_path(incoming))
        self.assertIn(old_path, incoming['legacyEventPaths'])
        self.assertEqual('20:00', incoming['startTime'])
        self.assertEqual('2026-09-01', incoming['firstSeen'])
        self.assertEqual('cancelled', incoming['status'])
        self.assertEqual(2, len(incoming['sources'][1:]))
        self.assertEqual(artwork.BY_ID[canonical['id']]['image'], incoming['image'])
        self.assertEqual(1, len(merge_events(*feeds.values())))
        once = copy.deepcopy(feeds)
        self.assertEqual(0, artwork.reconcile_provider_duplicates(feeds, history))
        self.assertEqual(once, feeds)

    def test_provider_duplicate_conflicts_fail_instead_of_guessing_or_restoring_history(self):
        canonical = dict(id='bandsintown:108975912', startDate='2026-11-29', startTime='19:00',
                         venue='Variety Playhouse', city='Atlanta', state='GA', artists=['Alex Jean'])
        alias = dict(canonical, id='ticketmaster:Z7r9jZ1AAepra')
        for field, value in [('startDate', '2026-12-01'), ('startTime', '21:00'),
                             ('venue', 'Different venue'), ('artists', ['Another artist'])]:
            feeds = {'primary': [dict(alias, **{field: value})], 'supplemental': [copy.deepcopy(canonical)]}
            before = copy.deepcopy(feeds)
            with self.assertRaisesRegex(ValueError, 'identity conflict'):
                artwork.reconcile_provider_duplicates(feeds)
            self.assertEqual(before, feeds)
        with self.assertRaisesRegex(ValueError, 'missing reviewed record'):
            artwork.reconcile_provider_duplicates({'primary': [alias]})
        unknown = {'primary': [dict(alias, id='unreviewed-provider-id')], 'supplemental': [canonical]}
        before = copy.deepcopy(unknown)
        self.assertEqual(0, artwork.reconcile_provider_duplicates(unknown))
        self.assertEqual(before, unknown)

    def test_retained_identity_only_reconciles_a_current_exact_duplicate(self):
        canonical = dict(id='bandsintown:108975912', title='Reviewed Atlanta concert',
                         startDate='2026-11-29', startTime='19:00', venue='Variety Playhouse',
                         city='Atlanta', state='GA', artists=['Alex Jean'], firstSeen='2026-09-01')
        history = [{'event': copy.deepcopy(canonical)}]
        before = copy.deepcopy(history)
        empty = {'primary': []}
        self.assertEqual(0, artwork.reconcile_provider_duplicates(empty, history))
        self.assertEqual([], empty['primary'])
        incoming = dict(canonical, id='ticketmaster:Z7r9jZ1AAepra', firstSeen='2026-10-17', status='cancelled')
        self.assertEqual(1, artwork.reconcile_provider_duplicates({'primary': [incoming]}, history))
        self.assertEqual(canonical['id'], incoming['id'])
        self.assertEqual('cancelled', incoming['status'])
        self.assertEqual('2026-09-01', incoming['firstSeen'])
        self.assertEqual(before, history)
        moved = dict(canonical, id='ticketmaster:Z7r9jZ1AAepra', startDate='2026-12-01')
        with self.assertRaisesRegex(ValueError, 'identity conflict'):
            artwork.reconcile_provider_duplicates({'primary': [moved]}, history)

    def test_refresh_restores_artwork_without_changing_event_identity_or_details(self):
        for pin in artwork.PINS:
            with self.subTest(event=pin["id"]):
                event = {"id": "manual:" + pin["id"], "startDate": pin["startDate"],
                         "startTime": "19:30", "venue": "Approved venue", "city": "Approved city",
                         "firstSeen": "2026-08-01", "artists": ["Existing curated artist"],
                         "image": "https://example.com/stale-artist.jpg", "imageType": "artist"}
                before = copy.deepcopy(event)
                self.assertTrue(artwork.patch_event(event))
                for key in ("id", "startDate", "startTime", "venue", "city", "firstSeen", "artists"):
                    self.assertEqual(event[key], before[key])
                self.assertEqual(event["image"], pin["image"])
                self.assertTrue((artwork.ROOT / pin["image"]).is_file())
                once = copy.deepcopy(event)
                artwork.patch_event(event)
                self.assertEqual(event, once)

    def test_date_change_and_unrelated_show_do_not_borrow_a_poster(self):
        for event in ({"id": artwork.PINS[0]["id"], "startDate": "2027-09-26"},
                      {"id": "unrelated-event", "startDate": "2026-10-03"}):
            before = copy.deepcopy(event)
            self.assertFalse(artwork.patch_event(event))
            self.assertEqual(event, before)

    def test_ticket_sources_survive_refresh_without_losing_calendar_evidence(self):
        for event_id, provider in (("bandsintown:108945796", "eventbrite.com"),
                                   ("bandsintown:108144023", "ticketmaster.com"),
                                   ("bandsintown:108144061", "ticketmaster.com"),
                                   ("bandsintown:108881783", "liberty.edu")):
            pin = artwork.BY_ID[event_id]
            old_source = {"name": "Bandsintown", "url": "https://www.bandsintown.com/e/original"}
            event = {"id": event_id, "startDate": pin["startDate"], "sources": [old_source],
                     "officialUrl": old_source["url"], "ticketUrl": old_source["url"],
                     "firstSeen": "2026-08-01"}
            artwork.patch_event(event)
            artwork.patch_event(event)
            self.assertIn(provider, event["officialUrl"])
            self.assertEqual(event["ticketUrl"], event["officialUrl"])
            self.assertEqual(event["sources"], [event["sources"][0], old_source])
            self.assertEqual(event["sources"][0]["url"], pin["officialUrl"])
            self.assertEqual(event["firstSeen"], "2026-08-01")

    def test_saved_by_grace_lists_all_five_without_creating_artist_profiles(self):
        pin = artwork.BY_ID["supplemental:issac-mansfield-saved-by-grace-2026"]
        self.assertEqual(pin["advertisedBilling"],
                         ["Issac Mansfield", "Josh Morgan", "DJ CAM", "Lev Nova", "Junado"])
        self.assertEqual(pin["officialBill"], pin["advertisedBilling"])
        self.assertNotIn("artists", pin)

    def test_same_title_tour_stops_keep_their_own_artwork(self):
        from finalize_sep12_complete_closeout import apply_artwork_replacements, event_path
        from pin_verified_event_artwork import patch_event_detail
        rows = [dict(id="manual:shared-tour-elizabeth-2026", title="Shared Tour",
                     startDate="2026-10-02", city="Elizabeth", image="/october-2.jpg"),
                dict(id="manual:shared-tour-rockville-centre-2026", title="Shared Tour",
                     startDate="2026-10-03", city="Rockville Centre", image="/old-photo.jpg")]
        replacement = {"image": "/october-3.jpg", "imageType": "event_artwork",
                       "source": "Organizer", "sourceUrl": "https://example.com", "classification": 1}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "finalize_sep12_complete_closeout.ARTWORK_REPLACEMENTS",
            {("Shared Tour", "2026-10-03"): replacement}
        ):
            root = Path(tmp)
            (root / "events.json").write_text(json.dumps(rows))
            (root / "supplemental-events.json").write_text("[]")
            for row in rows:
                page = root / event_path(row) / "index.html"
                page.parent.mkdir(parents=True)
                detail = f'<h1>{row["title"]}</h1><div class="event-detail-media"><img src="{row["image"]}"></div>'
                page.write_text(patch_event_detail(detail, row["startDate"])[0])
            apply_artwork_replacements(root, rows)
            earlier = (root / event_path(rows[0]) / "index.html").read_text()
            later = (root / event_path(rows[1]) / "index.html").read_text()
            self.assertIn("/october-2.jpg", earlier)
            self.assertIn("/october-3.jpg", later)


if __name__ == "__main__":
    unittest.main()
