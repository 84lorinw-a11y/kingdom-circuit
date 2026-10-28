# Kingdom Circuit — Daily show discovery audit, 2026-10-28

Audit scope: U.S. including Puerto Rico, future events and announced 2027+, enabled artist roster and aliases. This is a targeted fresh-web check plus a review of the most recent automated collector status, **not** an exhaustive direct all-platform sweep. No speculative event records or artist profiles added.

## Current source snapshot
- 379 enabled artists and 663 configured alias entries in `config/artists.json`.
- `events.json`: 193 rows total, 166 with `startDate >= 2026-10-28`, 49 in 2027+, including 34 Winter Jam 2027 dates. `supplemental-events.json`: 57 rows, including the already-recorded 2027-01-22 nobigdyl. UNPLUGGED at Cannery Hall (AXS).
- Recent October 27 additions: 34 Winter Jam dates and Kaden Jordan 2026-10-30 Gainesville; **these predate this audit** and are not new publications from this run.
- Exclusions checked: Jay Kalyl, DJ Maj and TobyMac absent from enabled roster.
- Existing 808 BEEZY venues/firstSeen verified in catalog: Indiana Tech (Nov 2), North Canton Chapel (Feb 12–13, 2027), earliest `firstSeen=2026-09-02T14:46:37Z`.
- No new, independently verified missing show was found in this targeted run. This is **not** a claim that no shows are missing.

## Primary and priority checks
- WHATUPRG 2026-11-19 Houston, Rockefellers, 7:30 PM catalog; 2026-11-20 Fort Worth, Ridglea Room, 7:30 PM catalog; 2026-11-22 San Antonio, Paper Tiger Side Room, 8 PM show / 7 PM doors. Reach Records confirms all three dates; Eventim independently verifies San Antonio time, address and tickets. DICE primary pages for Houston/Fort Worth could not be directly verified. Preserve all three existing manual IDs and original `firstSeen=2026-09-30T03:02:53.929665Z`.
- Alex Jean Dallas 2026-11-19: venue confirms 8 PM show and 7 PM doors; existing catalog is published. Recurring request says hold, while existing curated policy says owner released hold Oct 8. **No status change** pending reconciliation; preserve identity and provenance.
- DJ Winn / Color Me Courageous Oct 23 and Drea LP / Urban Soul Cafe Oct 4 are past, with no new future confirmed occurrence. Hallowed Be Thy Name Englewood Oct 31: organizer's 6–10 PM event window does not independently establish first performance; retain current time pending confirmation. Christopher Syncere/Kaden Nov 13 Orlando already published with Eventbrite as official details. JIMMY ROCK Legacy prior Sept 26 is past; no new future Legacy performance verified.
- Verified existing duplicate resolution: CJ Emulous Nov 15 GLO Concert is `status=merged` into Miles Minnick GLOVEMBER Nov 14 at The Belasco, 8 PM show / 7 PM doors; preserve merged redirect. Official CJ calendar remains stale.
- Winter Jam 2027 KFC Yum Center official venue confirms Jan 30, 6 PM event, 5 PM doors, Andy Mineo ft. Magic & Bird, and CJ Emulous pre-jam; already represented in catalog.

## Source coverage and limitations
- Latest **historical** main collector (Oct 27): 379 artists configured; 459 configured source checks; 33 official + 11 Ticketmaster candidates; 334 Instagram public-index searches with zero indexed results. This is not complete social coverage.
- Latest **historical** Bandsintown structured collector (Oct 27): 379 artists attempted, 237 resolved, 88 raw upcoming U.S. rows, 11 nonfestival additions in that earlier run; those are **not** new in this audit.
- Latest **historical** expanded source scan (Oct 27): 378 artists attempted; 378 Songkick robots blocks. Never count blocked sources as no events.
- Latest **historical** Eventbrite scan (Oct 27): 379/379 artist searches failed HTTP 405; 0 event pages reached. Direct Eventbrite source checks partial/blocked.
- Latest **historical** official website collector (Oct 27): 233/379 websites checked, 132 warnings, 0 parsed shows. This is incomplete, not zero shows.
- Direct today: selected Reach Records, Eventim, Bandsintown, Songkick, AXS, Ticketmaster/venue, artist and festival pages. DICE direct blocked; Instagram/Facebook/YouTube Community direct complete traversal **not attempted**. Laylo, Linktree, other ticketing/donation platforms, national venue/church/university/radio calendars, complete history/hold/image/link checks **not attempted exhaustively**.
- The last successful GitHub Pages deploy inspected was run 40617936744, completed Oct 28 02:03 UTC, with tests and Pages deployment successful, but **full discovery and expanded source scan skipped**.
- No event-data corrections or new shows published **by this targeted audit**. A new full scan is requested by this commit; its results, any new publications, release checks, deployment and next-refresh retention must be verified from the ensuing workflow before claiming success.

## Primary links
- https://www.reachrecords.com/artists/whatuprg/
- https://www.eventim.us/event/whatuprg/707572
- https://www.thebombfactory.com/events/detail/alex-jean-1626463
- https://www.axs.com/events/1304795/nobigdyl-unplugged-tickets
- https://www.kfcyumcenter.com/events/detail/winter-jam-27
- https://www.ironsharpcommunity.org/upcoming-events
- https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/40617936744
