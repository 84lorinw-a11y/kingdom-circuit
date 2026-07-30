# The Kingdom Circuit

A free GitHub Pages website and scheduled collector for U.S. Christian hip-hop shows.

## Included in this build

- 58 tracked artists
- 49 approved source feeds
- Daily GitHub Actions updates
- Ticketmaster Discovery API integration
- Reach Records consolidated and artist calendars
- Holy Culture, ChristianHits shows, and ChristianHits festival monitoring
- TPR Live, Awakening Events, and official artist tour pages
- Holy Smoke, Space City Fest, Rural Music Festival, Uprise Festival, OneFest, and Off The Charts coverage
- NF, Mike Malagies, Social Club Misfits, and Reflection Music Group monitoring
- Duplicate removal, U.S.-only filtering, and stale-event protection
- Search and filters for artist, state, event type, date, and free events

## Verified fallback events

`config/manual-events.json` contains seven source-backed listings that are retained even when a site blocks automated retrieval:

- Holy Smoke 2026
- OneFest 2026
- Off The Charts Music Festival 2026
- Konnect Concert Series
- Rural Music Festival 2026
- Uprise Festival 2026
- Space City Fest 2026

## How it works

Each day, `.github/workflows/update-and-deploy.yml` runs `scripts/update_events.py`. The collector checks the approved source registry, queries Ticketmaster, removes past and duplicate records, writes `events.json`, and deploys the site.

No paid AI service is required. The system uses free scheduled automation and conservative extraction rules.

## Important files

- `config/artists.json` — tracked artists and aliases
- `config/official-sources.json` — approved source registry
- `config/manual-events.json` — verified fallback events
- `scripts/update_events.py` — collection and deduplication logic
- `events.json` — generated public event list
- `run-status.json` — latest run diagnostics
- `.github/workflows/update-and-deploy.yml` — daily schedule and deployment

## Ticketmaster key

The repository secret must remain named `TICKETMASTER_API_KEY`. Never place the key in a public file.

## Limitations

No source covers every show. Social posts and image-only flyers are not auto-published because they are difficult to verify reliably. The manual fallback file is used for important verified events that are poorly structured online.
