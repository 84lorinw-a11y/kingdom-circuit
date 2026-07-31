# The Kingdom Circuit — Master v4

A free GitHub Pages website and daily collector for verified U.S. Christian hip-hop and faith-driven music shows.

## What v4 adds

- Stronger near-duplicate merging for shortened venue names, sponsor suffixes, and city suffixes.
- Clear public titles when a source incorrectly uses the venue name as the event title.
- "Venue to be announced" instead of internal placeholder wording.
- A gold calendar-status state when source checks return warnings and a red state for update errors.
- Quick filters for this weekend, the next 30 days, this month, and festivals.
- Collapsed festival lineups with an expandable full lineup.
- Real image elements with useful alternative text instead of decorative background images.
- Free local browser alerts that highlight new shows matching a saved artist or state on return visits.
- A clean on-site submission form that prepares a verified GitHub submission.
- 32 automated validation tests.

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
5. Official event artwork wins; otherwise the first-billed artist image is used.
6. U.S. music performances only.
7. Near-duplicates merge while all useful source links are retained.

## Free local alerts

The alert feature stores an artist and/or state preference in the visitor's browser. When the visitor returns, newly added matching shows are highlighted. It does not collect email addresses and does not require a backend or account.

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

The existing GitHub Action runs daily, on repository updates, and when started manually. It runs the tests, collects shows, refreshes `events.json` and `run-status.json`, and redeploys GitHub Pages.
