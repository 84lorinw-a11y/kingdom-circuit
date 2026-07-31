# The Kingdom Circuit — Master v2

A free GitHub Pages website and scheduled collector for verified U.S. Christian hip-hop and faith-driven music shows.

## What changed in v2

- Rebuilds the event list from current sources instead of retaining old v1 records.
- Merges near-duplicates such as minor venue-name variations while preserving every source link.
- Publishes festivals only when an official festival or event source explicitly confirms the lineup.
- Prevents artist and label pages from adding unconfirmed performers to festivals.
- Uses official event artwork first. Otherwise it uses the first-billed artist's approved base image.
- Rejects source logos and label logos as event images.
- Publishes U.S. music performances only. Speaking events, conferences, workshops, and uncertain listings are excluded.
- Includes all current Reach Records artists plus a broad CHH, crossover, collective, and legacy roster.

## Current configuration

- 113 tracked artists and groups
- 49 approved source feeds
- Ticketmaster Discovery API integration
- Reach Records consolidated and artist calendars
- TPR, Awakening Events, official artist pages, selected festival pages, and corroborating CHH calendars
- Verified fallbacks for Holy Smoke, Space City Fest, Rural Music Festival, OneFest, Uprise, Off The Charts, and the Konnect Concert Series

## Publishing rules

1. High-confidence qualifying events publish automatically.
2. Uncertain or conflicting events do not publish.
3. Source priority is: official event/festival, venue or ticket seller, artist/label, then aggregator.
4. Festival lineups must be explicit on an official festival/event source.
5. Official event artwork wins. If none exists, the first-billed artist's base image is used.
6. U.S. music performances only.

## Important files

- `config/artists.json` — canonical roster, aliases, Ticketmaster settings, and optional approved `imageUrl` overrides
- `config/official-sources.json` — approved source registry
- `config/manual-events.json` — source-backed fallbacks and official-social confirmations that cannot be parsed reliably
- `scripts/update_events.py` — collection, validation, image selection, and duplicate merging
- `tests/test_update_events.py` — automated rule tests
- `events.json` — generated public event list
- `run-status.json` — latest collector diagnostics

## Images

Artist base-image priority is:

1. An approved `imageUrl` in `config/artists.json`
2. The artist image returned by the verified Ticketmaster attraction
3. The neutral Kingdom Circuit fallback if neither is available

A label or source logo is never selected as event artwork.

## Ticketmaster key

The existing GitHub repository secret must remain named `TICKETMASTER_API_KEY`. Never place the key in a public file.

## Social-only announcements

The free workflow does not log into or scrape closed social platforms. An official artist, festival, venue, or promoter social announcement can be added to `config/manual-events.json` as a verified fallback. It will then auto-publish with the rest of the calendar.

## Maintenance

The GitHub Action runs the tests first. If a rule test fails, the site is not redeployed. The collector then refreshes sources, writes the cleaned event list, commits data changes, and deploys GitHub Pages.
