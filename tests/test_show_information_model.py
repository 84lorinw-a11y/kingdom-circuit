import copy
import pathlib
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from show_information_model import normalize


class ShowInformationModelTests(unittest.TestCase):
    def event(self, **fields):
        return {"title": "A real concert", "startDate": "2027-01-29",
                "startTime": "21:00", "timezone": "America/Chicago", **fields}

    def test_source_is_preserved_without_mutation_and_notes_are_not_description(self):
        source = self.event(country="CA", notes="Internal research, do not publish", artists=["Artist"])
        before = copy.deepcopy(source)
        result = normalize(source)
        self.assertNotIn("description", result)
        self.assertEqual(result["country"], "CA")
        result["artists"].append("Other")
        self.assertEqual(source, before)

    def test_new_source_details_replace_previously_unconfirmed_venue(self):
        placeholder = self.event(venue='RWG TOUR 2026', unconfirmedVenueValue='RWG TOUR 2026')
        self.assertEqual(normalize(placeholder)['venueLabel'], 'Venue not confirmed')
        refreshed = normalize({**placeholder, 'venue': 'Confirmed Hall', 'address': '100 Main St'})
        self.assertEqual(refreshed['venueLabel'], 'Confirmed Hall')
        self.assertEqual(refreshed['address'], '100 Main St')

    def test_event_titles_are_not_restored_as_venue_names(self):
        for title in ('RWG TOUR 2026', 'UNITY POP-UP TOUR', "THE KINGDOM'S COOL KIDZ PLAYLIST CONCERT"):
            result = normalize(self.event(title=title, venue=title, address='8809 Schoolcraft'))
            self.assertEqual(result['venue'], '')
            self.assertEqual(result['venueLabel'], 'Venue not confirmed')
            self.assertEqual(result['address'], '8809 Schoolcraft')
        confirmed = normalize(self.event(title='An evening at Chapel', venue='Chapel'))
        self.assertEqual(confirmed['venue'], 'Chapel')

    def test_explicit_venue_announcement_placeholders_remain_unknown(self):
        for venue in ('Venue to be announced', 'VENUE TO BE DETERMINED'):
            with self.subTest(venue=venue):
                result = normalize(self.event(venue=venue))
                self.assertEqual(result['venue'], '')
                self.assertEqual(result['venueLabel'], 'Venue not confirmed')

    def test_public_description_precedes_legacy_description(self):
        result = normalize(self.event(publicDescription=" Public copy ", description="Other", notes="Internal"))
        self.assertEqual(result["description"], "Public copy")
        self.assertEqual(normalize({"description": " Legacy copy "})["description"], "Legacy copy")

    def test_dst_offsets_come_from_event_date(self):
        winter = normalize(self.event())
        summer = normalize(self.event(startDate="2027-07-29"))
        self.assertEqual(winter["schemaStartDate"], "2027-01-29T21:00:00-06:00")
        self.assertEqual(summer["schemaStartDate"], "2027-07-29T21:00:00-05:00")
        self.assertEqual((winter["timezoneLabel"], summer["timezoneLabel"]), ("CST", "CDT"))

    def test_secondary_clocks_use_their_own_spring_and_fall_offsets(self):
        for day, doors, registration, start_label, doors_label, registration_label in (
            ('2027-03-14', '01:30', '01:15', '3:30 AM EDT', '1:30 AM EST', '1:15 AM EST'),
            ('2027-11-07', '00:30', '00:15', '3:30 AM EST', '12:30 AM EDT', '12:15 AM EDT'),
        ):
            with self.subTest(day=day):
                result = normalize(self.event(startDate=day, startTime='03:30',
                    doorsTime=doors, registrationTime=registration, timezone='America/New_York'))
                self.assertEqual(result['startTimeLabel'], start_label)
                for field, expected in (('doorsTimeLabel', doors_label),
                                        ('registrationTimeLabel', registration_label)):
                    with self.subTest(field=field):
                        self.assertEqual(result[field], expected)

    def test_ambiguous_and_nonexistent_secondary_clocks_keep_zone_name_fallback(self):
        for day, doors, registration, doors_label, registration_label in (
            ('2027-11-07', '01:15', '01:45', '1:15 AM', '1:45 AM'),
            ('2027-03-14', '02:15', '02:45', '2:15 AM', '2:45 AM'),
        ):
            with self.subTest(day=day):
                result = normalize(self.event(startDate=day, startTime='03:30',
                    doorsTime=doors, registrationTime=registration, timezone='America/New_York'))
                for field, expected in (('doorsTimeLabel', doors_label),
                                        ('registrationTimeLabel', registration_label)):
                    with self.subTest(field=field):
                        self.assertEqual(result[field], expected + ' (America/New_York)')

    def test_explicit_end_offsets_determine_order_during_fall_back(self):
        earlier = '2027-11-07T01:45:00-04:00'
        later = '2027-11-07T01:15:00-05:00'
        for start, end, valid in ((earlier, later, True), (later, earlier, False)):
            with self.subTest(start=start, end=end):
                result = normalize(self.event(startDate='2027-11-07', startTime='',
                    startDateTime=start, endDateTime=end, timezone='America/New_York'))
                self.assertEqual(result['schemaStartDate'], start)
                if valid:
                    self.assertEqual(result.get('schemaEndDate'), end)
                    elapsed = datetime.fromisoformat(result['schemaEndDate']) - datetime.fromisoformat(result['schemaStartDate'])
                    self.assertEqual(elapsed, timedelta(minutes=30))
                else:
                    self.assertNotIn('schemaEndDate', result)

    def test_auto_localized_end_order_and_elapsed_time_across_dst_changes(self):
        for day, start_clock, end_clock, start_iso, end_iso, elapsed in (
            ('2027-03-14', '01:30', '03:30', '2027-03-14T01:30:00-05:00',
             '2027-03-14T03:30:00-04:00', timedelta(hours=1)),
            ('2027-11-07', '00:30', '02:30', '2027-11-07T00:30:00-04:00',
             '2027-11-07T02:30:00-05:00', timedelta(hours=3)),
        ):
            with self.subTest(day=day):
                result = normalize(self.event(startDate=day, startTime=start_clock,
                    endTime=end_clock, timezone='America/New_York'))
                self.assertEqual(result['schemaStartDate'], start_iso)
                self.assertEqual(result['schemaEndDate'], end_iso)
                self.assertEqual(datetime.fromisoformat(result['schemaEndDate']) -
                                 datetime.fromisoformat(result['schemaStartDate']), elapsed)
                reversed_result = normalize(self.event(startDate=day, startTime=end_clock,
                    endTime=start_clock, timezone='America/New_York'))
                self.assertEqual(reversed_result['schemaStartDate'], end_iso)
                self.assertNotIn('schemaEndDate', reversed_result)

    def test_bc_permanent_pacific_time_does_not_display_mountain_time(self):
        source = self.event(startDate='2026-11-07', startTime='19:30',
            startDateTime='2026-11-07T19:30:00-07:00', endTime='22:00',
            timezone='America/Vancouver', city='Surrey', state='BC', country='CA')
        result = normalize(source)
        self.assertEqual(result['schemaStartDate'], '2026-11-07T19:30:00-07:00')
        self.assertEqual(result['startTimeLabel'], '7:30 PM PT')
        self.assertEqual(result['endTimeLabel'], '10:00 PM PT')

    def test_alberta_permanent_time_uses_correct_offset_and_label(self):
        source = self.event(startDate='2026-11-13', startTime='22:00',
                           timezone='America/Edmonton', city='Calgary', state='AB', country='CA')
        result = normalize(source)
        self.assertEqual(result['schemaStartDate'], '2026-11-13T22:00:00-06:00')
        self.assertEqual(result['startTimeLabel'], '10:00 PM ABT')

    def test_verified_explicit_clock_and_offset_win_over_conflicting_host_timezone(self):
        source = self.event(startDate='2026-11-13', startTime='22:00',
            startDateTime='2026-11-13T22:00:00-07:00', endDate='2026-11-14', endTime='01:00',
            endDateTime='2026-11-14T01:00:00-07:00', timezone='America/Edmonton')
        # Exercise the failure even on machines with an accurate IANA database.
        with patch('show_information_model._zone', return_value=timezone(timedelta(hours=-6), 'CST')):
            result = normalize(source)
        self.assertEqual(result['schemaStartDate'], '2026-11-13T22:00:00-07:00')
        self.assertEqual(result['schemaEndDate'], '2026-11-14T01:00:00-07:00')
        self.assertEqual(result['startTimeLabel'], '10:00 PM UTC-07:00')
        self.assertEqual(result['endTimeLabel'], '1:00 AM UTC-07:00')
        self.assertNotIn('CST', result['dateLabel'])
        consistent = normalize(self.event(startDateTime='2027-01-29T21:00:00-06:00'))
        self.assertEqual(consistent['startTimeLabel'], '9:00 PM CST')

    def test_ambiguous_and_nonexistent_clocks_do_not_choose_an_offset(self):
        for day, clock in (("2026-11-01", "01:30"), ("2027-03-14", "02:30")):
            result = normalize(self.event(startDate=day, startTime=clock))
            self.assertEqual(result["schemaStartDate"], day)
        explicit = normalize(self.event(startDateTime="2026-11-01T01:30:00-06:00"))
        self.assertEqual(explicit["schemaStartDate"], "2026-11-01T01:30:00-06:00")

    def test_date_only_and_unknown_zone_never_invent_midnight_or_offset(self):
        result = normalize({"startDate": "2027-01-29", "timezone": "America/Chicago"})
        self.assertEqual(result["schemaStartDate"], "2027-01-29")
        self.assertNotIn("startTimeLabel", result)
        unknown = normalize(self.event(timezone="Invalid/Zone"))
        self.assertEqual(unknown["schemaStartDate"], "2027-01-29T21:00:00")
        self.assertEqual(unknown["startTimeLabel"], "9:00 PM")
        offset = normalize({"startDateTime": "2027-01-29T21:00:00-06:00"})
        self.assertEqual(offset["schemaStartDate"], "2027-01-29T21:00:00-06:00")

    def test_known_start_and_end_local_clocks_survive_without_timezone(self):
        for fields in ({'startDate': '2027-01-29', 'startTime': '21:00', 'endTime': '22:00'},
                       {'startDateTime': '2027-01-29T21:00:00', 'endDateTime': '2027-01-29T22:00:00'}):
            result = normalize(fields)
            self.assertEqual(result['schemaStartDate'], '2027-01-29T21:00:00')
            self.assertEqual(result['schemaEndDate'], '2027-01-29T22:00:00')
            self.assertEqual(result['startTimeLabel'], '9:00 PM')
            self.assertNotIn('timezoneLabel', result)
        self.assertNotIn('schemaEndDate', normalize({'startDate': '2027-01-29', 'startTime': '21:00', 'endTime': '02:00'}))

    def test_optional_end_and_admission_clocks(self):
        result = normalize(self.event(endTime="22:00", doorsTime="20:00", registrationTime="20:30"))
        self.assertEqual(result["schemaEndDate"], "2027-01-29T22:00:00-06:00")
        self.assertEqual((result["doorsTimeLabel"], result["registrationTimeLabel"], result["endTimeLabel"]), ("8:00 PM CST", "8:30 PM CST", "10:00 PM CST"))
        self.assertNotIn("schemaEndDate", normalize(self.event()))
        self.assertNotIn("schemaEndDate", normalize(self.event(endTime="00:00")))
        overnight = normalize(self.event(endDate="2027-01-30", endTime="00:00"))
        self.assertEqual(overnight["schemaEndDate"], "2027-01-30T00:00:00-06:00")

    def test_private_is_explicit_and_clears_street_but_not_country(self):
        for fields in ({"status": "private"}, {"admission": "invite only"},
                       {"title": "Listening session — Invite-Only"},
                       {"venue": "Private event"}, {"ageRestriction": "Invitation only"}):
            result = normalize(self.event(**fields, address="123 Hidden St", postalCode="A1A 1A1", country="CA", ticketUrl="https://posh.vip/e/a-show"))
            self.assertTrue(result["private"])
            self.assertEqual((result["address"], result["postalCode"], result["country"]), ("", "", "CA"))
            self.assertIsNone(result["offer"])
        self.assertFalse(normalize(self.event(title="Youth Night", ageRestriction="Ages 13–18"))["private"])
        self.assertFalse(normalize(self.event(title="Private Thoughts album tour"))["private"])

    def test_venue_city_is_presentation_locality_without_mutating_market_identity(self):
        source = self.event(city='St. Louis', venueCity='St. Charles',
                            fullAddress='2002 Arena Pkwy, St. Charles, MO 63303')
        before = dict(source)
        result = normalize(source)
        self.assertEqual(result['venueLocality'], 'St. Charles')
        self.assertEqual(result['city'], 'St. Louis')
        self.assertEqual(source, before)
        for missing in ('', 'TBD', 'Not confirmed'):
            self.assertEqual(normalize(self.event(city='St. Louis', venueCity=missing))['venueLocality'], 'St. Louis')

    def test_generic_information_and_profiles_are_not_ticket_offers(self):
        for url in ("https://www.bandsintown.com/e/123-an-event", "https://www.eventbrite.com/",
                    "https://www.ticketmaster.com/artist/123", "https://artist.example/",
                    "https://www.instagram.com/artist/", "https://open.spotify.com/artist/123"):
            result = normalize(self.event(ticketUrl=url))
            self.assertIsNone(result["offer"], url)
            self.assertEqual(result["officialDestination"]["kind"], "details")

    def test_direct_ticket_is_preferred_and_label_is_always_official_details(self):
        ticket = "https://www.eventbrite.com/e/a-real-concert-tickets-2000000123456"
        result = normalize(self.event(ticketUrl=ticket, officialUrl="https://artist.example/", ticketLabel="Buy now"))
        self.assertEqual(result["officialDestination"], {"url": ticket, "kind": "tickets", "label": "Official details"})
        self.assertEqual(result["offer"], {"@type": "Offer", "url": ticket})
        verified = normalize(self.event(registrationUrl="https://ready27.events.example/", registrationUrlVerified=True))
        self.assertEqual(verified["officialDestination"]["kind"], "registration")
        self.assertEqual(verified["officialDestination"]["label"], "Official details")
        self.assertIsNotNone(verified["offer"])

    def test_existing_direct_platform_shapes_and_spoofed_hosts(self):
        for url in (
            "https://www.livenation.com/event/rZ7HnEZ1AfGUq7/a-concert",
            "https://dice.fm/partner/tickets/event/abc12-a-concert-tickets",
            "https://wl.eventim.us/event/a-concert/707572?afflky=Venue",
            "https://events.ticketleap.com/tickets/organizer/a-canadian-concert",
            "https://www.tickettailor.com/checkout/view-event/id/9144465/chk/28bb42e7981e7b98ad292022136429f3/",
            "https://brushfire.com/anthemnights/dmv/643773",
            "https://events.humanitix.com/g-ng-in-concert-one-night-only/tickets",
        ):
            self.assertEqual(normalize(self.event(ticketUrl=url))["offer"]["url"], url)
        for url in ("https://eventbrite.com.attacker.example/e/a-concert-tickets-123",
                    "https://www.livenation.com/artist/123/", "https://dice.fm/partner/tickets/",
                    "https://www.tickettailor.com/checkout/view-event/", "https://brushfire.com/anthemnights/",
                    "https://brushfire.com.attacker.example/anthemnights/dmv/643773",
                    "https://events.humanitix.com/a-show/tickets/unverified-subpath"):
            self.assertIsNone(normalize(self.event(ticketUrl=url))["offer"])

    def test_verification_flags_are_boolean_and_cannot_turn_social_into_offer(self):
        for flag in ("true", 1, False):
            self.assertIsNone(normalize(self.event(ticketUrl="https://artist.example/", ticketUrlVerified=flag))["offer"])
        result = normalize(self.event(ticketUrl="https://www.instagram.com/artist/", ticketUrlVerified=True))
        self.assertIsNone(result["offer"])
        self.assertIsNone(normalize(self.event(ticketUrl="javascript:alert(1)", ticketUrlVerified=True))["officialDestination"])

    def test_reviewed_ready27_registration_root_retains_source_url_and_one_destination(self):
        for url in ('https://ready27.events.mbts.edu/', 'https://ready27.events.mbts.edu/registration/select'):
            result = normalize(self.event(ticketUrl=url, officialUrl='https://spurgeoncollege.com/ready-conference/'))
            self.assertEqual(result['officialDestination']['url'], url)
            self.assertEqual(result['offer']['url'], url)
        for url in ('https://ready28.events.mbts.edu/', 'https://ready27.events.mbts.edu/schedule/',
                    'https://ready27.events.mbts.edu.attacker.example/'):
            self.assertIsNone(normalize(self.event(ticketUrl=url))['offer'])

    def test_price_strings_are_display_only_and_totals_require_currency_and_fees(self):
        source = self.event(ticketUrl="https://posh.vip/e/a-show", price="Concert only: $15")
        legacy = normalize(source)
        self.assertEqual(legacy["priceLabel"], "Concert only: $15")
        self.assertNotIn("price", legacy["offer"])
        structured = {"amount": "15", "currency": "USD", "ticketType": "Concert only", "includesAllFeesConfirmed": False}
        result = normalize({**source, "price": structured})
        self.assertEqual(result["offer"]["name"], "Concert only")
        self.assertNotIn("price", result["offer"])
        total = normalize({**source, "price": {**structured, "includesAllFeesConfirmed": True}})
        self.assertEqual((total["offer"]["price"], total["offer"]["priceCurrency"]), (15, "USD"))
        for price in ({"amount": "15", "includesAllFeesConfirmed": True},
                      {"amount": "NaN", "currency": "USD", "includesAllFeesConfirmed": True},
                      {"amount": "-1", "currency": "USD", "includesAllFeesConfirmed": True}):
            self.assertNotIn("price", normalize({**source, "price": price})["offer"])
        free = normalize({**source, "price": {"amount": 0, "currency": "CAD", "includesAllFeesConfirmed": True}})
        self.assertEqual(free["offer"]["price"], 0)

    def test_sold_out_is_explicit_and_closed_events_have_no_offer(self):
        source = self.event(ticketUrl="https://posh.vip/e/a-show")
        self.assertNotIn("availability", normalize(source)["offer"])
        for fields in ({"soldOut": True}, {"ticketAvailability": "sold_out"}):
            self.assertEqual(normalize({**source, **fields})["offer"]["availability"], "https://schema.org/SoldOut")
        self.assertNotIn("availability", normalize({**source, "soldOut": "true"})["offer"])
        for status in ("cancelled", "canceled", "postponed", "merged"):
            self.assertIsNone(normalize({**source, "status": status})["offer"])
        self.assertIsNotNone(normalize({**source, "status": "rescheduled"})["offer"])

    def test_organizer_uses_only_supplied_name_and_valid_url(self):
        result = normalize(self.event(organizer={"name": "The venue", "url": "https://venue.example/"}, ageRestriction="All ages"))
        self.assertEqual((result["organizerName"], result["organizerUrl"], result["admissionLabel"]), ("The venue", "https://venue.example/", "All ages"))
        legacy = normalize(self.event(organizer="Real organizer", officialUrl="https://ticket.example/"))
        self.assertEqual(legacy["organizerName"], "Real organizer")
        self.assertNotIn("organizerUrl", legacy)

    def test_collected_flat_organizer_fields_survive_repeated_normalization(self):
        for name, url in (
            ("Urban Soul Cafe", None),
            ("Strength to Stand / Scott Dawson Evangelistic Association", "https://www.strengthtostand.org/"),
            ("Church of God Youth and Discipleship", "https://www.cogyd.org/mywinterfest"),
        ):
            with self.subTest(organizer=name):
                source = self.event(organizerName=" " + name + " ")
                if url:
                    source["organizerUrl"] = " " + url + " "
                before = copy.deepcopy(source)
                result = normalize(source)
                self.assertEqual(result.get("organizerName"), name)
                self.assertEqual(result.get("organizerUrl"), url)
                self.assertEqual(normalize(result), result)
                self.assertEqual(source, before)

    def test_canonical_organizer_wins_without_borrowing_a_flat_organizer_url(self):
        for canonical, expected_url in (
            ({"name": "Current promoter", "url": "https://current.example/"}, "https://current.example/"),
            ({"name": "Current promoter", "url": "javascript:alert(1)"}, None),
            ("Current promoter", None),
        ):
            with self.subTest(organizer=canonical):
                result = normalize(self.event(organizer=canonical, organizerName="Old promoter",
                                              organizerUrl="https://old.example/"))
                self.assertEqual(result["organizerName"], "Current promoter")
                self.assertEqual(result.get("organizerUrl"), expected_url)
                self.assertEqual(normalize(result), result)

    def test_flat_organizer_rejects_unsafe_urls_and_requires_a_name(self):
        for url in ("javascript:alert(1)", "https://user:secret@promoter.example/",
                    "https://promoter.example/a b", "//promoter.example/"):
            with self.subTest(url=url):
                result = normalize(self.event(organizerName="Confirmed promoter", organizerUrl=url))
                self.assertEqual(result.get("organizerName"), "Confirmed promoter")
                self.assertNotIn("organizerUrl", result)
        result = normalize(self.event(organizerName=" ", organizerUrl="https://promoter.example/"))
        self.assertNotIn("organizerName", result)
        self.assertNotIn("organizerUrl", result)


if __name__ == "__main__":
    unittest.main()
