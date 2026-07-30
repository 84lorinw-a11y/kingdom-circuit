# The Kingdom Circuit

A free GitHub Pages website and scheduled event collector for U.S.-based Christian hip-hop shows.

## What is included

- Responsive black, cream, and gold event website
- Search, artist, state, and event-type filters
- Registry of 50 Christian hip-hop artists
- Daily GitHub Actions automation
- Official-site Schema.org event extraction
- Optional Ticketmaster Discovery API integration
- Duplicate detection and U.S.-only filtering
- Automatic event sorting, status display, and source links
- GitHub show-submission form

## How the automation works

Every day, GitHub Actions runs `scripts/update_events.py`. The collector:

1. Checks approved official artist and label pages for structured event data.
2. Checks Ticketmaster for exact artist matches when `TICKETMASTER_API_KEY` is configured.
3. Excludes parking passes, add-ons, non-U.S. listings, and past events.
4. Merges duplicates and writes the final list to `events.json`.
5. Deploys the refreshed site to GitHub Pages.

No paid AI model is required. This is a free scheduled collector. It is intentionally conservative: it publishes only high-confidence structured listings rather than guessing from social posts or flyers.

## First-time setup

Follow [`SETUP-CHECKLIST.md`](SETUP-CHECKLIST.md).

## Important files

- `config/artists.json` — tracked artists and aliases
- `config/official-sources.json` — approved official pages
- `config/manual-events.json` — optional verified events not found automatically
- `events.json` — generated public show list
- `run-status.json` — latest collector status
- `scripts/update_events.py` — collection and deduplication logic
- `.github/workflows/update-and-deploy.yml` — daily schedule and deployment

## Ticketmaster coverage

Ticketmaster's Discovery API is optional but recommended. Add the API key as a GitHub repository secret named `TICKETMASTER_API_KEY`. Do not paste it into code or commit it to the repository.

## Limitations

No single event source covers every Christian hip-hop show. Official pages that do not expose structured event data may require a future source-specific connector. Social platforms are not scraped. Review the Actions log periodically for source errors or unmatched artists.
