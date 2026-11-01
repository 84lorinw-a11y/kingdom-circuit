# Kingdom Circuit — Daily Show Discovery Audit
**2026-11-01, 05:00 America/Chicago**

**Classification:** Partial manual primary-source checks + production repository inspection + full discovery requested. **Not** an independent complete 412-artist/all-platform/all-social sweep. Do not treat blocked or unattempted sources as zero events.

## Result and deployment

- **Current source roster:** **412 enabled artists, 707 configured alias entries** in `config/artists.json`. This differs from October 31 collector telemetry (379), which is historical.
- **Source snapshot:** `events.json` **194 records**, **151** dated November 1 or later, **49** dated 2027+. `config/manual-events.json` **290**; `supplemental-events.json` **66**; website seeds **22**. Source counts are not deduplicated public show counts.
- **New shows published by this audit:** **0 confirmed**. This is not a finding that no missing shows exist.
- **Existing-show correction:** Found a live **duplicate Mike Malagies Dec 12 Kissimmee** listing. Canonical curated show `manual:mike-malagies-its-a-god-night-orlando-2026-12-12` starts **5 PM** at Sun on the Beach/Old Town, with original `firstSeen=2026-10-30T02:10:10.097556+00:00`. Weaker official-source import `official:5f5e88420934ba61cf99` incorrectly says **10 PM**, making two public cards for the same artist/date/venue. [Apple Music artist calendar](https://music.apple.com/us/concerts/artist/1573408784) independently displays **5 PM**; [official TicketSpice](https://itsagodnight.ticketspice.com/its-a-god-night-orlando) is the canonical ticket destination but was not directly retrievable. Added **exact-ID duplicate suppression** to `scripts/apply_curated_catalog_policy.py` ([commit 3660240](https://github.com/84lorinw-a11y/kingdom-circuit/commit/3660240e9b5eae97b868bb4fbee5a2c1bffea674)), plus regression test ([commit 898baf0](https://github.com/84lorinw-a11y/kingdom-circuit/commit/898baf04501e90c9078677e1ba16557910440fee)). **Correction, not a new show.** Canonical ID, firstSeen, approved artwork and primary ticket URL left untouched.
- **Release:** [Date-mode deployment 41300159959](https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/41300159959) in progress when checked; [full discovery run 41300171714](https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/41300171714) queued. **No new deployment, full-scan completion, live duplicate removal, or next-refresh retention verified yet.** Previous successful release [41276189578](https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/41276189578) completed at **2026-11-01 05:24 UTC**, before this audit's changes.

## WHATUPRG Texas — three existing IDs preserved

| Date | Location | Start vs doors | Source and limitations |
|---|---|---|---|
| Thu Nov 19 | Rockefellers, 3620 Washington Ave, Houston TX | Catalog **7:30 PM show / 7 PM doors** | [DICE primary](https://dice.fm/partner/tickets/event/yo5xer-whatuprg-w-aftrthght-de-la-cruz-19th-nov-rockerfellers-houston-tickets) returned **HTTP 403**; artist tour and artist-linked feeds support lineup WHATUPRG, aftrthght, De La Cruz. Show-vs-doors and current ticket inventory not independently reverified today. |
| Fri Nov 20 | Ridglea Room, **6025 Camp Bowie Blvd, Fort Worth TX** (Dallas market) | Catalog **7:30 PM show / 7 PM doors** | [Apple Music](https://music.apple.com/us/concerts/ce.e00598d2-79d2-42aa-b79f-2db87443d56c) confirms 7:30 PM and performers; its **3309 Winthrop Ave** is a bad aggregator address; [official venue](https://theridglea.com/ridglea-room/) confirms **6025 Camp Bowie**. [DICE](https://dice.fm/partner/tickets/event/mxynyr-whatuprg-w-aftrthght-de-la-cruz-20th-nov-ridglea-room-fort-worth-tickets) returned HTTP 403. |
| Sun Nov 22 | Paper Tiger **Side Room**, 2410 N St Mary's St, San Antonio TX | **8 PM show / 7 PM doors** | [Eventim official primary ticket page](https://www.eventim.us/event/whatuprg/707572) confirms room, show, doors, GA/VIP. Artist tour supports aftrthght and De La Cruz. |

Preserved IDs `manual:whatuprg-houston-2026-11-19`, `manual:whatuprg-dallas-2026-11-20`, `manual:whatuprg-san-antonio-2026-11-22` and earliest `firstSeen=2026-09-30T03:02:53.929665Z`. All three are visible on [November live calendar](https://kingdomcircuit.com/shows/november-2026/). No new copies.

## Unresolved, protected, or past leads

- **Alex Jean Nov 19 Dallas:** [The Bomb Factory official page](https://www.thebombfactory.com/events/detail/alex-jean-1626463) confirms **The Studio at The Bomb Factory**, **2727 Canton St**, **8 PM show / 7 PM doors**, Reece support. Existing event is public; recurring prompt requests **hold**, while the repo policy and test document an **October 8 owner release**. No destructive hold change was made under this unresolved conflicting instruction. Flagged for owner-policy reconciliation.
- **DJ Winn Color Me Courageous Oct 23:** past; DJ Winn performer association unverified; Eventbrite was rate-limited. Do not invent a listing.
- **Drea LP Urban Soul Cafe:** [official artist calendar](https://drealp.com/home) shows **October 4 Nashville**, past; no future verified date in targeted searches.
- **Hallowed Be Thy Name Oct 31 Englewood:** now past. [Organizer](https://www.ironsharpcommunity.org/upcoming-events/hallowed-be-thy-name-weekend) confirms **6–10 PM overall event**, Holy Spirit & Fire Church, but not first music time. Existing 7 PM concert time was not independently verified; distinct from Denver Altar Ego event.
- **Christopher Syncere / Kaden Jordan Nov 13 Orlando:** already cataloged as **The Renovation Project**, The Gathering Place, 8287 Curry Ford Rd, **7 PM show / 6:30 PM doors**, with 2RU, JAYSOTO and MEMO. [Eventbrite authoritative Official Details](https://www.eventbrite.com/e/the-renovation-project-tickets-2002811792987) returned HTTP 429; retain it, no duplicate.
- **JIMMY ROCK Legacy:** prior Sep 26 event past; Nov 21 Legacy Conf Miami has **Tommy Royale, Shepherd, GIOVANI**, not verified JIMMY ROCK. Jan 31 Columbus Linktree mention lacks an unambiguous year/venue/primary ticket page; **hold**, not a 2027 publication. Nov 20 Belleville [Diamondback venue](https://www.diamondbackmusichall.com/tm-event/rave-jesus-rave-revival-tour-2/) independently verifies **7 PM show / 6 PM doors / 5 PM VIP**, Rave Jesus headline, JIMMY ROCK and Maxxer support; existing correction retained. Nov 22 Columbus first music time unverified.
- **2027+:** 49 future 2027+ source rows, including already published Winter Jam tour and Rock the Pines; **no newly verified 2027 roster show** in sampled external searches. 1K Phew Feb 13 Atlanta / Feb 20 New York / Mar 20 Elgin aggregator morning timestamps remain **unverified concert start**. **808 BEEZY Feb 12–13 North Canton bookings are private**, not public ticketed shows. **Puerto Rico eligible**; no new PR roster performance verified in targeted searches.
- **Exclusions:** Jay Kalyl remains removed, DJ Maj/TobyMac not added as profiles; no profiles inferred from flyers.

## Source coverage ledger

**Successful targeted:** GitHub roster/aliases/current catalog/manual/supplemental/website seeds/selected holds and guards; official Eventim, Bomb Factory, Ridglea, Iron Sharp, Diamondback and Apple Music artist calendars. GitHub write operations succeeded for duplicate guard/test.

**Attempted/manual partial:** WHATUPRG artist tour and artist-linked calendar; Drea LP official site; JIMMY ROCK/Legacy leads; targeted 2027 festivals, Reach, venue and organizer calendars; selected Eventbrite/TicketWeb/TicketSpice/AXS references. These are not complete all-artist or all-platform sweeps.

**Blocked direct:** DICE Houston and Fort Worth HTTP **403**; Eventbrite Renovation Project HTTP **429**; TicketSpice canonical checkout inaccessible; TicketWeb Columbus direct **530**. Do not infer absence.

**Historical automated collector, October 31 (not this audit's completed run):**
- Bandsintown: **412 attempted / 254 resolved / 90 raw upcoming U.S. rows / 11 previously published nonfestival**; those 11 are **not new publications by this audit**.
- Official websites: **253 of 412 checked**, **143 warnings**, **0 extracted**; parsing failures/blocks cannot be counted as no events.
- Eventbrite: **379/379 searches failed HTTP 405**; no event detail pages reached. The run predates the current 412 roster.
- Songkick: **379/379 blocked by robots** in last expanded scan, also predating roster update.
- Main collector: **492 checks**, 38 official and 13 Ticketmaster candidates, 369 Instagram indexed queries attempted, 1 indexed result and 0 published social events. This is not authenticated Instagram/Facebook/YouTube Community coverage.

**Not systematically attempted:** Facebook/YouTube Community full feeds, authenticated Instagram, Laylo/Linktree all-artist traversal; TicketWeb, Prekindle, Ticket Tailor, Brushfire, iTickets, TicketSource, Partiful, FareHarbor, Ticketera, Humanitix, SimpleTix, TicketSignup, Ticketleap, POSH, ExpressTix, BoletosExpress platform sweeps; Givebutter, OneCause, Zeffy, Donorbox, Blackbaud, Qgiv, Constant Contact Events, Realm, ROLLER comprehensive searches; all configured promoter/festival and venue/church/university/museum/parks/tourism/radio calendars. Some named providers were sampled via existing records, **not exhaustively searched**.

**Not verified end-to-end:** every image, link, cancellation/reschedule, historical redirect, full event history, source refresh retention, or completed audit-generated deployment. No complete coverage claim.

**Next check:** finish [full discovery run 41300171714](https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/41300171714); verify tests, publication count, public removal of the erroneous Mike Malagies 10 PM duplicate, retained 5 PM event, approved image/links/associations, and survival after next refresh.

## Follow-up verification and corrections (November 1, later morning)

- **Alex Jean Dallas owner hold reinstated:** The latest repeated owner instruction explicitly requires the November 19 Dallas listing to remain on hold. [Policy commit f82404b](https://github.com/84lorinw-a11y/kingdom-circuit/commit/f82404b4e2f1d0115b2cc5a10ab635cbf900d105) now filters this specific Dallas/date/artist appearance (including its provider alias) from future public curation; [regression test 0c7d91d](https://github.com/84lorinw-a11y/kingdom-circuit/commit/0c7d91d4b26d816aafd5212f21861fd7b63c6b4c) protects the hold without affecting Orlando. The existing original event in `config/manual-events.json` retains its ID and `firstSeen` for eventual authorized release. **Public removal and next-refresh persistence remain pending deployment.**
- **Separate September 11 catalog guard CI failure:** [Run 41300987673](https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/41300987673) failed 2 of 564 tests because the runner lacked Pillow, not because the concert catalog failed validation. Initial attempt to reuse the production-only backend installer also failed outside the release workflow. [Fix f8a8217](https://github.com/84lorinw-a11y/kingdom-circuit/commit/f8a8217e50ec8bf4f1a5a5fc34d0c751740c6504) explicitly installs the same pinned `Pillow==12.3.0` and verifies WebP support before tests. **The corrected guard has not yet been confirmed green.**
- **Live-versus-source discrepancy:** Fresh [live shows page](https://kingdomcircuit.com/shows/) still displayed both Mike Malagies December 12 Kissimmee records (5 PM curated and erroneous 10 PM imported) when checked. Latest `events.json` has **only the canonical 5 PM record**, with the original `firstSeen` and approved image. This is **not** verified live until the pending deployment removes the duplicate.
- **Full discovery/deployment:** [Run 41300171714](https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/41300171714) was still in expanded source scan when checked; later push-triggered runs queued. No new shows published by this follow-up; no end-to-end release, image/link or next-refresh verification claimed. The earlier source-coverage ledger still applies.
