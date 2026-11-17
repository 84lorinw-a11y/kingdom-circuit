# Location navigation

The production workflow runs `scripts/location_navigation.py` after the existing presentation and show information layers. It reads the current generated All Shows calendar and location calendars. It never reads the test checkout or changes source show records, artist records, artwork or existing calendar URLs.

The layer adds States and Cities directories, five primary navigation links, location search and selectors, clickable city labels, selected nearby city connections, and province links. Directories include only locations with public upcoming shows. Featured locations sort by distinct public show count, then name and URL. Private, cancelled and postponed listings do not contribute to discovery counts. The existing calendar pipeline owns expiration and identity reconciliation.

Before changes, the layer saves original HTML and hashes every artifact file outside the public site. Its preservation gate checks all original files, every image and data file, existing metadata, structured data, artwork references and show cards. The final current content gate verifies directory counts, production identity, sitemap inclusion and location connections after URL continuity runs.

The new directories are core indexable pages in the shared SEO classifier. URL continuity records actual page changes after navigation is applied. The publication manifest includes the dynamic location mapping. Existing source inventory, show information, privacy, calendar freshness and exact live release checks remain mandatory.

The show information stylesheet stays last in its existing head position so its independent idempotence check remains effective. Navigation assets are inserted before it.

Local verification uses `tests/test_location_navigation.py` and the existing full test suites. Production uses the normal dates publication mode and current source data. No test HTML, feeds or generated assets should be promoted directly.

Historical connections are finalized by `scripts/history_navigation.py` inside the URL continuity pass, before sitemap fingerprints are recorded. The compact Show archive is linked from All Shows, contains ordinary links inside native month disclosures, and reconnects published historical events and past month calendars. Retained events link to existing artist, city and state calendars using verified retained identities. Private and noindex notices are excluded from archive promotion. Current public cards, show facts and original artwork are unchanged.
