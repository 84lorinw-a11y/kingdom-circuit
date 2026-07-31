# The Kingdom Circuit — Master v3

A free GitHub Pages website and daily collector for verified U.S. Christian hip-hop and faith-driven music shows.

## What v3 adds

- Checks all 113 configured artists individually through a free public Instagram search-index scan.
- Reads known official Instagram post/Reel URLs, including Mike Malagies' current announcement Reel.
- Auto-publishes an Instagram event only when the official artist identity, future date, U.S. city/state, and live-music context are explicit.
- Keeps uncertain Instagram findings in `run-status.json` as internal candidates instead of publishing them.
- Adds verified listings for Steven Malcolm, Scootie Wop, and Mike Teezy.
- Adds dedicated Steven Malcolm, Scootie Wop, and Mike Teezy source feeds.
- Preserves Master v2's strict duplicate, festival-lineup, image, U.S.-only, and music-only rules.

## Current configuration

- 113 tracked artists and groups
- 54 approved website and event feeds
- Ticketmaster Discovery API integration
- One per-artist public Instagram search each scheduled run
- Known Instagram post registry
- 11 source-backed fallback events
- 26 automated validation tests

## Publishing rules

1. High-confidence qualifying events publish automatically.
2. Uncertain or conflicting events do not publish.
3. Source priority: official event/festival, venue or ticket seller, artist/label, then aggregator.
4. Festival performers must be explicitly named by the official festival/event source.
5. Official event artwork wins; otherwise the first-billed artist image is used.
6. U.S. music performances only.
7. Near-duplicates merge while all useful source links are retained.

## Instagram coverage

The free workflow does not log into Instagram or bypass access controls. It searches the public web index once for every configured artist and checks configured post/Reel URLs. Stories, private accounts, deleted posts, and posts that are not publicly indexed cannot be seen. A display name alone is not enough to auto-publish; the result must identify a configured official account or known official post and include complete event details.

## Important files

- `config/artists.json` — roster, aliases, optional official Instagram profile, Ticketmaster settings, and approved image overrides
- `config/official-sources.json` — approved website/event source registry
- `config/known-instagram-posts.json` — official Instagram post/Reel URLs to monitor
- `config/manual-events.json` — source-backed fallbacks for listings that cannot be parsed reliably
- `scripts/instagram_monitor.py` — free public Instagram discovery and strict validation
- `scripts/update_events.py` — collection, validation, image selection, and duplicate merging
- `tests/test_update_events.py` — automated rule tests
- `events.json` — generated public event list
- `run-status.json` — latest collector diagnostics and unresolved Instagram candidates

## Ticketmaster key

Keep the existing GitHub repository secret named `TICKETMASTER_API_KEY`. Never place the key in a public file.

## Automation

The existing GitHub Action runs daily, on repository updates, and when started manually. It runs the tests, collects shows, refreshes `events.json` and `run-status.json`, and redeploys GitHub Pages.
