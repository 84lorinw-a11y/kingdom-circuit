import importlib.util
import json
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_events.py"
SPEC = importlib.util.spec_from_file_location("update_events", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DummyClient:
    def __init__(self, pages=None):
        self.pages = pages or {}

    def get_text(self, url):
        if url not in self.pages:
            raise MODULE.CollectorError(f"No fixture for {url}")
        return self.pages[url]


class UpdateEventsTests(unittest.TestCase):
    def setUp(self):
        self.alias_lookup = {
            "1k phew": "1K Phew",
            "hulvey": "Hulvey",
            "kb": "KB",
            "lecrae": "Lecrae",
            "caleb gordon": "Caleb Gordon",
            "indie tribe": "indie tribe.",
            "nobigdyl": "nobigdyl.",
            "social club misfits": "Social Club Misfits",
            "rare of breed": "Rare of Breed",
            "parris chariz": "Parris Chariz",
            "nf": "NF",
            "mike malagies": "Mike Malagies",
        }

    def test_normalize_name_handles_punctuation(self):
        self.assertEqual(MODULE.normalize_name("nobigdyl."), "nobigdyl")
        self.assertEqual(MODULE.normalize_name("Torey D'Shaun"), "torey d shaun")
        self.assertEqual(MODULE.normalize_name("Q-Flo"), "q flo")

    def test_non_show_filter(self):
        self.assertTrue(MODULE.is_non_show("Parking Pass Only - Forrest Frank"))
        self.assertTrue(MODULE.is_non_show("VIP Early Entry Package Add-On"))
        self.assertFalse(MODULE.is_non_show("Forrest Frank: The Jesus Generation Tour"))

    def test_merge_events_combines_artists_and_sources(self):
        first = {
            "id": "ticketmaster:1",
            "title": "Example Festival",
            "startDate": "2099-07-10",
            "startTime": "19:00",
            "venue": "Venue not provided",
            "city": "Minneapolis",
            "state": "MN",
            "artists": ["Lecrae"],
            "ticketUrl": "https://tickets.example/1",
            "sourcePriority": 70,
            "sources": [{"name": "Ticketmaster", "url": "https://tickets.example/1"}],
        }
        second = {
            "id": "official:2",
            "title": "Example Festival 2099",
            "startDate": "2099-07-10",
            "startTime": "19:00",
            "venue": "Example Arena",
            "city": "Minneapolis",
            "state": "MN",
            "artists": ["KB"],
            "officialUrl": "https://festival.example",
            "sourcePriority": 100,
            "sources": [{"name": "Official", "url": "https://festival.example"}],
        }
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["artists"], ["KB", "Lecrae"])
        self.assertEqual(merged[0]["venue"], "Example Arena")
        self.assertEqual(len(merged[0]["sources"]), 2)

    def test_jsonld_event_extraction(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "MusicEvent",
          "name": "Test Concert",
          "startDate": "2099-08-01T19:00:00-05:00",
          "location": {
            "@type": "Place",
            "name": "Test Venue",
            "address": {
              "@type": "PostalAddress",
              "addressLocality": "Minneapolis",
              "addressRegion": "MN",
              "addressCountry": "US"
            }
          },
          "performer": {"@type": "Person", "name": "KB"},
          "url": "https://example.com/test"
        }
        </script>
        </head></html>
        """
        parser = MODULE.JsonLdScriptParser()
        parser.feed(html)
        self.assertEqual(len(parser.scripts), 1)
        payload = json.loads(parser.scripts[0])
        events = list(MODULE.iter_event_objects(payload))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "Test Concert")

    def test_reach_parser_uses_artist_page_fallback(self):
        html = """
        <html><body>
          <h1>01</h1><h5>Aug</h5><h5>2099</h5><h4></h4>
          <h6>Pneuma Church</h6><h6>Chattanooga, TN</h6>
          <a href="https://www.bandsintown.com/e/test">RSVP</a>
        </body></html>
        """
        events = MODULE.collect_reach_records_source(
            {
                "name": "Reach Records - 1K Phew",
                "artist": "1K Phew",
                "priority": 90,
            },
            "https://www.reachrecords.com/artists/1k-phew/",
            html,
            self.alias_lookup,
            "2098-01-01T00:00:00Z",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["artists"], ["1K Phew"])
        self.assertEqual(events[0]["startDate"], "2099-08-01")
        self.assertEqual(events[0]["city"], "Chattanooga")

    def test_reach_parser_deduplicates_state_name_and_code(self):
        html = """
        <html><body>
          <h1>06</h1><h5>Aug</h5><h5>2099</h5><h4>Hulvey</h4>
          <h6>Holy Smoke! 2099</h6><h6>Nashville, Tennessee</h6>
          <h1>06</h1><h5>Aug</h5><h5>2099</h5><h4>Hulvey</h4>
          <h6>Holy Smoke! 2099</h6><h6>Nashville, TN</h6>
        </body></html>
        """
        events = MODULE.collect_reach_records_source(
            {"name": "Reach Records calendar"},
            "https://www.reachrecords.com/events/",
            html,
            self.alias_lookup,
            "2098-01-01T00:00:00Z",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["state"], "TN")

    def test_tpr_parser_extracts_tour_card(self):
        html = """
        <html><body>
          <h1>Caleb Gordon - The Eden Experience</h1>
          <div>Aug 14, 2099 7:00PM Phoenix, AZ Event Info Buy Tickets</div>
          <a href="https://tprlive.co/products/test">Buy Tickets</a>
        </body></html>
        """
        events = MODULE.collect_tpr_source(
            {
                "name": "TPR - Caleb Gordon",
                "eventTitle": "Caleb Gordon - The Eden Experience",
                "artists": ["Caleb Gordon"],
            },
            "https://tprlive.co/collections/test",
            html,
            self.alias_lookup,
            "2098-01-01T00:00:00Z",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["startDate"], "2099-08-14")
        self.assertEqual(events[0]["startTime"], "19:00")
        self.assertEqual(events[0]["city"], "Phoenix")

    def test_holy_smoke_parser_extracts_multiday_festival(self):
        html = """
        <html><head><meta property="og:image" content="https://example.com/holy.jpg"></head>
        <body>
          <h1>HOLY SMOKE! 2099</h1>
          <h3>AUGUST 6, 7, + 8, 2099</h3>
          <h3>ROCKETOWN - NASHVILLE, TN</h3>
          <div>$140.00 USD</div>
        </body></html>
        """
        events = MODULE.collect_holy_smoke_source(
            {
                "name": "Holy Smoke official",
                "artists": ["indie tribe.", "Hulvey"],
                "venue": "Rocketown",
                "city": "Nashville",
                "state": "TN",
            },
            "https://indietribe.us/products/holy-smoke-2099",
            html,
            DummyClient(),
            self.alias_lookup,
            "2098-01-01T00:00:00Z",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["startDate"], "2099-08-06")
        self.assertEqual(events[0]["endDate"], "2099-08-08")
        self.assertEqual(events[0]["eventType"], "festival")

    def test_space_city_parser_uses_event_url_not_sidebar_dates(self):
        html = """
        <html><body>
          <h2>Space City Church</h2>
          <h3>October 25, 2099</h3>
          <div>4:00 pm to 8:00 pm</div>
          <p>Space City Fest is a fall celebration.</p>
          <div>VIEW SIMILAR EVENTS</div>
          <div>September 1, 2099</div>
        </body></html>
        """
        events = MODULE.collect_space_city_source(
            {
                "name": "Space City Fest - Discovery Green",
                "eventTitle": "Space City Fest",
                "artists": ["Lecrae"],
                "venue": "Discovery Green",
                "city": "Houston",
                "state": "TX",
                "startTime": "16:00",
            },
            "https://www.discoverygreen.com/event/space-city-church/october-25-2099-400-pm/",
            html,
            self.alias_lookup,
            "2098-01-01T00:00:00Z",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["startDate"], "2099-10-25")
        self.assertEqual(events[0]["artists"], ["Lecrae"])


    def test_christian_hits_parser_extracts_rural_festival(self):
        html = """
        <html><body>
          <a href="https://www.ruralmusic.org/event-details/rural-music-festival-2099">
            Rural Music Festival 2099: 8/28/99 - 8/30/99
          </a>
          <div>Isle, MN</div>
          <div>Social Club Misfits, Rare of Breed, Jason Crabb</div>
        </body></html>
        """
        events = MODULE.collect_christian_hits_source(
            {"name": "ChristianHits show feed"},
            "https://christianhits.net/shows.php",
            html,
            self.alias_lookup,
            "2098-01-01T00:00:00Z",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["startDate"], "2099-08-28")
        self.assertEqual(events[0]["endDate"], "2099-08-30")
        self.assertEqual(events[0]["city"], "Isle")
        self.assertEqual(events[0]["artists"], ["Rare of Breed", "Social Club Misfits"])

    def test_christian_festivals_parser_extracts_tracked_lineup(self):
        html = """
        <html><body>
          <h2>Uprise Festival 2099</h2>
          <div>September 11 - September 12, 2099 | Shippensburg, PA</div>
          <div>Hulvey - KB - 1K Phew - Other Artist</div>
          <a href="https://festival.example">Get Tickets or More Information</a>
        </body></html>
        """
        events = MODULE.collect_christian_festivals_source(
            {"name": "Festival directory"},
            "https://www.christianhits.net/festivals.php",
            html,
            self.alias_lookup,
            "2098-01-01T00:00:00Z",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["startDate"], "2099-09-11")
        self.assertEqual(events[0]["endDate"], "2099-09-12")
        self.assertEqual(events[0]["artists"], ["1K Phew", "Hulvey", "KB"])

    def test_bandsintown_public_parser_follows_only_upcoming_event_links(self):
        artist_html = """
        <html><body>
          <div>All concerts &amp; live streams</div>
          <div>AUG</div><div>22</div><div>SAT</div>
          <a href="/e/upcoming">Space City Church South Houston, TX</a>
          <div>Get tickets</div>
          <div>Past shows</div>
          <a href="/e/past">Old Venue Nashville, TN</a>
        </body></html>
        """
        detail_html = """
        <html><head><script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "MusicEvent",
          "name": "Konnect Concert Series",
          "startDate": "2099-08-22T18:00:00-05:00",
          "location": {
            "@type": "Place",
            "name": "Space City Church",
            "address": {
              "@type": "PostalAddress",
              "addressLocality": "Houston",
              "addressRegion": "TX",
              "addressCountry": "US"
            }
          },
          "performer": {"@type": "Person", "name": "Parris Chariz"},
          "url": "https://www.bandsintown.com/e/upcoming"
        }
        </script></head></html>
        """
        original_robots = MODULE.robots_allows
        MODULE.robots_allows = lambda _url: True
        try:
            events = MODULE.collect_bandsintown_public_source(
                {
                    "name": "Parris Chariz Bandsintown",
                    "artist": "Parris Chariz",
                },
                "https://www.bandsintown.com/a/parris-chariz",
                artist_html,
                DummyClient({"https://www.bandsintown.com/e/upcoming": detail_html}),
                self.alias_lookup,
                "2098-01-01T00:00:00Z",
            )
        finally:
            MODULE.robots_allows = original_robots
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["artists"], ["Parris Chariz"])
        self.assertEqual(events[0]["startDate"], "2099-08-22")

    def test_wix_event_list_parser_follows_event_details(self):
        list_html = """
        <html><body>
          <a href="/event-details/test-show">Test Show</a>
        </body></html>
        """
        detail_html = """
        <html><head><script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "MusicEvent",
          "name": "Mike Malagies Live",
          "startDate": "2099-10-03T19:00:00-04:00",
          "location": {
            "@type": "Place",
            "name": "Test Church",
            "address": {
              "@type": "PostalAddress",
              "addressLocality": "Tampa",
              "addressRegion": "FL",
              "addressCountry": "US"
            }
          },
          "url": "https://www.mikemalagiesofficial.com/event-details/test-show"
        }
        </script></head></html>
        """
        original_robots = MODULE.robots_allows
        MODULE.robots_allows = lambda _url: True
        try:
            events = MODULE.collect_wix_event_list_source(
                {"name": "Mike official", "artist": "Mike Malagies"},
                "https://www.mikemalagiesofficial.com/event-list",
                list_html,
                DummyClient({
                    "https://www.mikemalagiesofficial.com/event-details/test-show": detail_html
                }),
                self.alias_lookup,
                "2098-01-01T00:00:00Z",
            )
        finally:
            MODULE.robots_allows = original_robots
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["artists"], ["Mike Malagies"])
        self.assertEqual(events[0]["city"], "Tampa")

    def test_rural_parser_extracts_official_range(self):
        html = """
        <html><body>
          <h1>Rural Music Festival 2099</h1>
          <div>Aug 28, 2099, 12:00 PM – Aug 30, 2099, 8:00 PM</div>
        </body></html>
        """
        events = MODULE.collect_rural_festival_source(
            {
                "name": "Rural official",
                "eventTitle": "Rural Music Festival 2099",
                "artists": ["Social Club Misfits", "Rare of Breed"],
                "city": "Isle",
                "state": "MN",
            },
            "https://www.ruralmusic.org/event-details/test",
            html,
            self.alias_lookup,
            "2098-01-01T00:00:00Z",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["startDate"], "2099-08-28")
        self.assertEqual(events[0]["endDate"], "2099-08-30")
        self.assertEqual(events[0]["startTime"], "12:00")


    def test_numeric_only_artist_alias_is_not_matched_in_prices(self):
        lookup = {"350": "350", "nf": "NF"}
        self.assertEqual(MODULE.match_artists_in_text("Tickets are $350", lookup), [])
        self.assertEqual(MODULE.match_artists_in_text("NF live in concert", lookup), ["NF"])

    def test_safe_url_rejects_javascript(self):
        self.assertEqual(MODULE.safe_url("javascript:alert(1)"), "")
        self.assertEqual(MODULE.safe_url("https://example.com"), "https://example.com")


if __name__ == "__main__":
    unittest.main()
