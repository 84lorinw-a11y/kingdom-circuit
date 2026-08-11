# The Kingdom Circuit — Master v10

This release converts Kingdom Circuit from a single-page calendar into a multi-page static website while preserving the existing event collector, artist roster, manual events, Google Analytics, Formspree submissions, brand assets, and custom domain.

## Generated pages

- `/` — mission-led homepage plus the complete searchable calendar
- `/shows/` — all verified shows
- `/shows/this-month/` — current-month shows, updated automatically
- `/festivals/` — verified festival listings
- `/new-shows/` — shows first added to Kingdom Circuit within the last 14 days
- `/artists/` — searchable artist directory
- `/artists/<artist>/` — artist image, verified links, and upcoming shows; no biography
- `/submit/` — private Formspree show and correction submission form
- `/shows/<event>/` — individual event pages with Event structured data
- `/states/<state>/` — automatically generated state pages

## Automation

The existing daily collector still runs at 11:23 UTC. After collecting and deduplicating events, `scripts/build_site.py` regenerates the complete site, sitemap, artist pages, event pages, and location pages before deployment.

## Important

This package intentionally does not include `events.json`, `run-status.json`, or the Ticketmaster cache. Uploading it will preserve the live collected event data and GitHub secret.
