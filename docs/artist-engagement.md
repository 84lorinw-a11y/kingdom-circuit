# Artist discovery and Google Analytics release

Owner approved production deployment after TEST audits pass. Empty profiles retain photos, social links, headings and archives, adding the reviewed Explore/live-count/state and Instagram actions. `scripts/artist_engagement.py` applies this after the existing discovery/sold-out verification and independently reconstructs all permitted changes against a fresh baseline. Existing files, data and pictures remain intact. It fails closed if form callback anchors change.

The same reviewed browser client runs in TEST with delivery disabled. Production uses the existing Google tag/property (G-N2KK9XF4TJ; 549068474); no new property or parallel reporting database. No local event log. Source-artist attribution persists in session storage for 30 minutes only. Form contents are never included; outbound URLs reduce to host and internal paths strip querystrings. Search/UTM values are bounded and redact obvious contact data.

The catalog count uses unique current All Shows URLs, inclusive end dates and the same Pacific calendar cutoff as existing listings. Build/render and client date rollover are tested. New shows arrive with the site’s existing daily build; visible artist pages refresh their catalog every five minutes.

Events: artist_view, show_view, empty_shows_impression (once/page, 50% visible), empty_shows_click, event_select, ticket_referral, instagram_referral, artist_social_click, artist_jump_select, artist_suggestion_open, search_results, state_select, form_start, form_attempt, form_success, form_error, traffic_arrival, page_engagement, web_performance, site_error. Submission success comes only from an actual server acknowledgment. Ticket referrals are not purchases; Instagram referrals are not confirmed follows. Performance values are diagnostics rather than certified Core Web Vitals.

Google configuration at promotion: event-scoped artist_name, show_name, action, placement, source_artist, source_action, page_type, platform, destination_host, form_type, error_type, search_term, state, dates, artist_filter, show_type, metric. Built-in device/source/medium/page dimensions remain available. Numeric result_count, show_count, visible_seconds, scroll_percent. Avoid summing duplicate enhanced-measurement form events. Preserve production history and acquisition settings.

Do not enable Google tracking in TEST. The mistakenly created TEST property was moved to Google Trash on October 24 after the owner clarified the requirement.

## October 24 tracking correction (20261024-4)

- Restores the existing async Google tag on the homepage. About inherits that shell. The final build now requires exactly one live loader, bootstrap and configuration on every instrumented HTML page; a disabled comment is not accepted as a tag.
- Adds `artist_select` for destination artist profiles, `facebook_referral` for Kingdom Circuit's own Facebook, and `collection_select` for weekend/month/city/category navigation. `state_select` is limited to the final state directory and records its human-readable state name.
- `ticket_referral` retains its historical name but now includes `referral_type`: `ticket`, `registration`, or `information`. Official-details clicks are not ticket purchases. Do not add generic enhanced-measurement outbound clicks to the custom totals.
- Search result `action` distinguishes `initial_results`, `search_change`, `filter_change`, `search_submit`, and `history_navigation`. Initial page display is not a visitor search.
- Placement identifies homepage artist shelves, this-week/next-week shelves, artist search results and the artist directory. Destination artist/show names come from the selected card.
- Google definitions add event-scoped `referral_type` and separate numeric diagnostic fields `lcp_ms` (milliseconds), `layout_shift_sum` (standard) and `max_interaction_ms` (milliseconds). Do not sum these diagnostics into a site score or describe the last two as certified CLS/INP.

The existing **Kingdom Circuit — Fan actions** exploration is the reporting destination. Production history is preserved; tracking cannot backfill unrecorded homepage/About visits. TEST continues to strip the Google loader and bootstrap and sends no analytics.
