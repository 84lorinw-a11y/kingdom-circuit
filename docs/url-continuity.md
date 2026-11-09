# Published URL continuity

The production workflow reconciles source identities after collector/curation steps, then performs URL reconciliation after every presentation overlay. It saves `config/url-continuity.json` only after GitHub Pages deployment succeeds. That state is durable source data; do not replace it with a build timestamp or regenerate it from only the current calendar.

`config/event-identity-overrides.json` records reviewed source-ID merges, their surviving published paths, verified historical redirects and ambiguous groups that must remain separate. Different start times, venues, dates or status do not auto-merge. Automatic new-provider matching requires matching date, city, region, venue, title, artists and a specific official/ticket URL with compatible known sessions. Preserve unknown/conflicting pairs for review.

A reviewed merge may set `identityOnly: true` when the alias's facts have been rejected. Its source identity and old URLs are retained, but its fields cannot fill gaps in the verified survivor during current-feed or archived-history replay. This is an explicit reviewed exception, not a broader automatic matching rule.

The registry retains the selected URL when the underlying title, date, city or provider record changes. Existing builders may generate a changed path; the final pass moves the finished page to its recorded address and rewrites internal links, structured data, sharing URLs and catalog paths. The changed path and remembered aliases become lightweight zero-second HTML forwarding pages. These are HTTP 200 HTML responses, not server-side 301s. Meta refresh works without JavaScript; the supplemental `location.replace` retains query strings/fragments and avoids a redundant Back entry when JavaScript runs. Forwarding pages contain no analytics tag or Event/Offer markup.

Missing redirect destinations, cycles, conflicting identities, alias entries in the sitemap, wrong canonicals and fabricated modification dates fail the final gate. Intentionally removed artists/events remain removed. Retained pages for disappeared shows state whether the last recorded date passed, was cancelled/postponed/private, or is no longer in the current calendar; an unconfirmed future listing is not represented as a currently scheduled Event.

Modification dates use fingerprints of rendered main content, meaningful links/images, page title/description/canonical and structured data. Deployment scripts, build receipts, CSS and analytics do not establish a content change. Unknown historical dates stay absent; an observed meaningful change receives its publication date, and identical rebuilds preserve it. Initial fingerprints were captured from the November 1 public-site audit. The public `url-continuity-manifest.json` receipt allows the release gate to verify dates against the artifact; internal source records remain in the repository registry.

Useful commands:

```sh
python scripts/url_continuity.py --prepare
# Run the complete production generation/overlay pipeline.
python scripts/url_continuity.py --site _site
python scripts/url_continuity.py --site _site --check
# CI only, after successful deployment:
python scripts/publish_url_state.py
```

The publisher uses a fresh checkout, updates only the registry, retries competing Git pushes without force, and refuses to overwrite a newer deployed state. The original provider feeds remain owned by their existing collectors. Unit tests are in `tests/test_url_continuity.py`; live follow-through should sample an old link, its canonical destination, the duplicate survivor, and sitemap/Google canonical selection.

Reviewed historical calendar recovery uses `retainedCalendars` in the identity override registry. It derives archive links from retained event identities with exact artist/state/city/month filters; empty or removed-artist calendars are not fabricated. Remembered aliases still forward to their reviewed destination and stay out of the sitemap. In November 7 recovery, the removed Vic Lucas and Chad Jones profiles remain removed.

After restoration, the final pass applies the shared indexing policy to all artist/state and city calendars. Calendars without current show cards keep their URLs, self-canonicals and historical links with `noindex,follow`, and leave the sitemap. Their continuity records remain available; a verified upcoming card makes the same calendar indexable again. This also applies on repeat finalization of an existing artifact. The final gate rejects incorrect calendar robots directives or a missing eligible calendar sitemap entry. Artist profiles, state/province pages, dated-month archives, individual event archives and existing event noindex decisions retain their separate policies.

An identical rendered card is not sufficient proof of an identical performance. The three 808 BEEZY groups in `reviewRequired` have conflicting source clocks. Their archived pages now display their own recorded clock and source, with an explicit uncertainty note, and do not emit Event/Offer markup. Only source IDs with confirmed equivalent performance identity are consolidated.
