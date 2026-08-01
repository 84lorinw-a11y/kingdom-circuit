# The Kingdom Circuit — Master v6

A free GitHub Pages website and daily collector for verified U.S. Christian hip-hop and faith-driven music shows.

## What v6 changes

- Replaces the public warning phrase **Updated with source gaps** with the cleaner **Calendar updated** label.
- Keeps the timestamp and status indicator so visitors can still see when the calendar last refreshed.
- Removes the Local Show Watch section and all browser-based alert code.
- Leaves the collector schedule, show-validation rules, duplicate handling, images, filters, submissions, and event-retirement behavior unchanged.
- Retains all Master v5 data-quality and design improvements.

## Current configuration

- 113 tracked artists and groups
- 54 approved website and event feeds
- Ticketmaster Discovery API integration
- One per-artist public Instagram search each scheduled run
- Known Instagram post registry
- Source-backed fallback events for listings that cannot be parsed reliably

## Publishing rules

1. High-confidence qualifying events publish automatically.
2. Uncertain or conflicting events do not publish.
3. Source priority: official event/festival, venue or ticket seller, artist/label, then aggregator.
4. Festival performers must be explicitly named by the official festival/event source.
5. Official event artwork wins; otherwise the first-billed approved artist image is used.
6. U.S. music performances only.
7. Near-duplicates merge while all useful source links are retained.

## Image rules

- Official event or festival artwork is used when it is available from an authoritative source.
- Otherwise, the first-billed artist's approved image is used.
- `config/artists.json` can define `imageUrl`, `imagePosition`, and `preferArtistImage` for an artist.
- 1K Phew is configured to use `assets/artists/1k-phew.webp` when authoritative event artwork is unavailable.

## Show submissions

The on-site form gathers the required event details and opens a prefilled GitHub Issue. This keeps the site free and prevents anonymous spam, but the submitter needs a free GitHub account for the final step.

## Instagram coverage

The free workflow does not log into Instagram or bypass access controls. It searches the public web index once for every configured artist and checks configured post/Reel URLs. Stories, private accounts, deleted posts, and posts that are not publicly indexed cannot be seen. A display name alone is not enough to auto-publish; the result must identify a configured official account or known official post and include complete event details.

## Important files

- `config/artists.json` — roster, aliases, optional official Instagram profile, Ticketmaster settings, and approved image overrides
- `config/official-sources.json` — approved website/event source registry
- `config/known-instagram-posts.json` — official Instagram post/Reel URLs to monitor
- `config/manual-events.json` — source-backed fallbacks for listings that cannot be parsed reliably
- `scripts/instagram_monitor.py` — free public Instagram discovery and strict validation
- `scripts/update_events.py` — collection, validation, image selection, public-title cleanup, and duplicate merging
- `tests/test_update_events.py` — automated rule tests
- `events.json` — generated public event list
- `run-status.json` — latest collector diagnostics and unresolved Instagram candidates

## Ticketmaster key

Keep the existing GitHub repository secret named `TICKETMASTER_API_KEY`. Never place the key in a public file.

## Automation

The existing GitHub Action runs daily at 11:23 UTC, on repository updates, and when started manually. It runs the tests, collects shows, refreshes `events.json` and `run-status.json`, and redeploys GitHub Pages.

## Event retirement

Single-day shows remain available through their event date and are removed on the next collector run after that date. Multi-day festivals remain through their listed final date.
