# Show information publication

The owner approved the reviewed show-information structure for production on November 5, 2026, using current production records. TEST catalogs and research overrides are not promoted.

`show_information.py` runs after the existing presentation layers on every production build. It preserves current event URLs, artwork, billing, source catalogs, archives and artist data. `show_information_model.py` supplies the visible facts and corresponding Event structured data from the same record.

- Keep Status, Date, Venue and Location. Display available public street, suite, postal code and country. Show confirmed local start times with their known timezone.
- Put a known **Organizer / promoter** in its own row immediately after Location. Do not infer the host from the ticket platform or Kingdom Circuit.
- Put available descriptions, prices, doors, other secondary times, billed roles and practical information in the native **More show details** disclosure. This content exists in the initial HTML.
- Keep one **Official details** action pointing to the best verified official ticket or registration destination. Any structured Offer must use the same visible destination. Information-only destinations do not create ticket offers.
- Display a verified base price when supplied, but publish a numeric Offer price only when the amount, currency and inclusion of mandatory fees are confirmed.
- Keep known age restrictions by the action. Keep private shows listed and labeled; omit their street/postal address and public Event/Offer structured data.
- Keep list cards compact. Unknown optional facts are omitted; missing core address/start-time facts remain honestly unconfirmed.

The normal release checks verify idempotence, shared visible/schema facts, unchanged source bytes, current dates/counts, Canadian retention, private labels and established URLs. Missing information can be researched later without replacing the current production catalog.
