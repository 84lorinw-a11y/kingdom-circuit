# Kingdom Circuit — daily show discovery audit, 2026-10-29

**Scope:** Enabled roster, aliases, future United States including Puerto Rico, announced 2027+ dates. **Classification: targeted manual verification + latest automated collector telemetry, not an exhaustive all-platform direct scan.**

## Source snapshot (GitHub main, 2026-10-29 05:00 Central)
- **379 enabled artists, 663 aliases** (`config/artists.json`).
- **194 catalog rows; 166 dated October 29, 2026 or later; 49 dated 2027+** (`events.json`). `config/manual-events.json` contains 280 source records; `supplemental-events.json` 59; verified artist website seeds 22.
- **Recently published before this audit:** Don Ready, *It Must Be God Experience*, October 30, 2026, 7 PM–10 PM, The Gathering Church, 121 Walnut St, Evansville, IN; 6:30 PM doors. Eventbrite organizer page confirms headliner, age policy and start. Original `firstSeen=2026-10-29T00:53:31Z`. It was **already committed and visible** before this audit, not an addition by this audit.
- **New events published by this audit: 0.** This is **not** a conclusion that no missing events exist.

## Existing-show correction applied — Don Ready, Los Angeles, November 6
**Not a new show.** Already listed as `manual:don-ready-club-217-los-angeles-2026-11-06` with original `firstSeen=2026-10-05T18:39:31Z`. The original Official Details link was a Google Forms registration. A **complete organizer Eventbrite listing** confirms the same event, Don Ready as headliner, Friday Nov 6, **8 PM event start**, 6111 S Gramercy Place, Los Angeles CA 90047, free entry, 16+ and free parking. **The Don Ready performance happens later; exact set time remains unannounced**. Do not mislabel 8 PM as a verified Don Ready set time.

- **Updated** the existing `config/manual-events.json` and `events.json` records to use Eventbrite for `ticketUrl` and `officialUrl`, while retaining the original Club 2:17 Google Form and Instagram flyer as alternate sources.
- Preserved **stable ID, earliest legitimate firstSeen, approved event artwork, event title, city/date/venue, associations, and original sources**. No duplicate or artist profile created.
- Durable source commit: https://github.com/84lorinw-a11y/kingdom-circuit/commit/520f6d2cd5fe92face21479c5e9b7fc3248d1544
- Published-catalog correction / full-scan trigger commit: https://github.com/84lorinw-a11y/kingdom-circuit/commit/f5d5b451795d7acbbf4e5aece76e3981808ddd95
- Primary Eventbrite: https://www.eventbrite.com/e/christian-latin-rap-club-night-w-don-ready-free-event-tickets-2003215547628
- Original approved flyer remains `assets/events/don-ready-club-217-los-angeles-2026-11-06.jpg`.

**Deployment:** A full discovery run was triggered by the `[full scan]` commit message. At initial status check, [run 40854383759](https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/40854383759) was **pending** behind a separate dates-only push run [40854358404](https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/40854358404), whose tests were in progress. **No audit-generated successful deployment, live-link verification, or post-refresh retention is claimed yet.**

## WHATUPRG existing Texas dates (do not duplicate)
- **Nov 19 Houston:** Rockefellers, 3620 Washington Ave, **7:30 PM catalog time**; aftrthght and De La Cruz billed. Reach Records, Apple Music, secondary concert pages corroborate. DICE direct checkout could not be fetched; concert start vs doors is **not independently reverified** today.
- **Nov 20 Dallas market, physical Fort Worth:** Ridglea Room, **6025 Camp Bowie Blvd**, **7:30 PM catalog time**; aftrthght and De La Cruz billed. Official venue confirms address. DICE direct checkout blocked; doors/show separation not independently reverified today.
- **Nov 22 San Antonio:** Paper Tiger **Side Room**, 2410 N St Mary's St, **8 PM show / 7 PM doors**, confirmed directly by Eventim with GA/VIP ticket options.
- Preserve IDs `manual:whatuprg-houston-2026-11-19`, `manual:whatuprg-dallas-2026-11-20`, `manual:whatuprg-san-antonio-2026-11-22`, and their `firstSeen=2026-09-30T03:02:53.929665Z`. No changes made.
- Sources: https://www.reachrecords.com/artists/whatuprg/ ; https://www.eventim.us/event/whatuprg/707572 ; https://theridglea.com/ ; https://www.whatuprg.com/tour

## Held and unresolved
- **Alex Jean Dallas Nov 19:** Official Bomb Factory confirms **8 PM show / 7 PM doors**, Reece as special guest, The Studio at The Bomb Factory. Existing catalog is published. Recurring prompt says hold, while prior explicit owner policy released hold Oct 8. **No status change** to avoid silently overwriting conflicting instructions; owner-policy reconciliation remains needed. https://www.thebombfactory.com/events/detail/alex-jean-1626463
- **DJ Winn / Color Me Courageous Oct 23:** Now past; DJ billing unverified; Eventbrite direct access limited. No retroactive association.
- **Drea LP / Urban Soul Cafe:** Oct 4 Nashville date is past; no new future instance verified. https://drealp.com/home
- **Hallowed Be Thy Name Oct 31, Englewood CO:** Organizer's **6–10 PM general event window** at Holy Spirit & Fire Church, 3190 S Grant St, does **not** independently establish the first performance start. Catalog says 7 PM. Hold time correction; separate Denver Altar Ego event should remain distinct. https://www.ironsharpcommunity.org/upcoming-events/hallowed-be-thy-name-weekend
- **Christopher Syncere / Kaden Jordan Nov 13:** Existing *The Renovation Project* at The Gathering Place, Orlando, 7 PM, with Eventbrite as official details. Direct Eventbrite reader blocked; no duplicate. https://www.eventbrite.com/e/the-renovation-project-tickets-2002811792987
- **JIMMY ROCK Legacy:** Prior Sep 26 date is past; no future JIMMY ROCK Legacy date confirmed. Do not confuse the already-listed Nov 21 *Legacy Conf Miami* lineup (Tommy Royale, Shepherd, GIOVANI) with JIMMY ROCK.
- **808 BEEZY:** Existing Nov 2 Indiana Tech and Feb 12–13 2027 North Canton Chapel venues and original Sep 2 firstSeen remain correct; no change.
- **Awake-Fest Nov 14:** Skema Boy and Zauntee already associated with existing manual festival entry. Bandsintown held candidates **must not** be published as duplicates. https://www.becrecordings.com/zauntee
- **2027+ and Puerto Rico:** 49 catalog rows in 2027+; Winter Jam dates already represented. Puerto Rico remains eligible; no new future PR show confirmed in sampled sources. No exhaustive 2027+ discovery performed.
- **Geographic caveat:** Public calendar also displays Canada (Saskatchewan, Ontario). This audit's discovery scope is U.S. plus PR; no global-site Canada policy change was authorized.

## Coverage ledger — attempted / successful / manual / partial / blocked / not attempted
**Fresh targeted manual checks** are separate from **historical automated collector status**; neither represents a full 379-artist direct-web sweep.

| Source family | Classification and evidence |
|---|---|
| GitHub roster, current events, manual, supplemental, seed, explicit review holds | **Successful targeted reads:** 379 artists, 663 aliases, 194 catalog rows, 280 manual, 59 supplemental, 22 seeds; review-held file inspected. **Full history** could not be read through connector; not exhaustively reconciled. |
| GitHub durable write | **Successful:** Existing Don Ready LA source and catalog corrected, preserving ID/firstSeen/art. |
| GitHub tests/full scan/deploy | **Attempted/queued:** Full-scan run 40854383759 pending at first check; no final result yet. Earlier [40797203471](https://github.com/84lorinw-a11y/kingdom-circuit/actions/runs/40797203471) successfully tested/deployed but **discovery steps skipped**. |
| Main configured official sources/Ticketmaster | **Historical partial:** Oct 28 main collector 379 configured artists; 33 official + 12 Ticketmaster events found; 334 Instagram indexed queries with 7 results but **0 verified social event additions**. These are candidate counts, not this run's publications. |
| Artist official websites, tour pages, embedded calendars, bio/Linktree, Laylo | **Historical partial + targeted manual:** 233/379 websites attempted, 132 warnings, zero extracted by collector. Targeted WHATUPRG, Drea LP, label/venue/organizer checked. Linktree/Laylo not systematically traversed. |
| Bandsintown | **Historical structured successful/partial:** 379 attempted, 237 resolved, 90 raw future U.S. rows, 14 earlier nonfestival publications, 2 held festival candidates, 0 request errors. **Those 14 predate this audit**. |
| Songkick | **Historical blocked:** 379/379 artist scans robots-blocked. Targeted indexed pages available; not a complete current sweep. |
| Eventbrite | **Historical blocked / manual successful:** 379/379 automated artist searches HTTP 405; direct pages may HTTP 429. **Organizer Eventbrite page for Don Ready LA was successfully retrieved through indexed search** and used to correct the existing record. Blocked searches are not “no shows.” |
| Apple Music concerts | **Manual partial:** WHATUPRG/808 BEEZY concert feeds cross-checked; not all artists. |
| Eventim | **Manual successful targeted:** WHATUPRG San Antonio primary ticket page confirms 8 PM show, 7 PM doors, Side Room. |
| Ticketmaster, Live Nation, AXS, DICE | **Partial / DICE blocked direct:** Alex Jean AXS/venue, WHATUPRG DICE references; no full platform-wide sweep. |
| Instagram, Facebook, YouTube Community | **Indexed partial / direct not attempted:** Original Club 2:17 Instagram flyer retained; authenticated full social traversal not performed. |
| TicketWeb, Prekindle, TicketSpice, Ticket Tailor, Brushfire, iTickets, TicketSource, Partiful, FareHarbor, Ticketera, Humanitix, SimpleTix, TicketSignup, Ticketleap, POSH, ExpressTix, BoletosExpress | **Not attempted systematically** today; existing links only. |
| Givebutter, OneCause, Zeffy, Donorbox, Blackbaud, Qgiv, Constant Contact Events, Realm, ROLLER | **Partial / mostly not attempted:** Iron Sharp organizer and Donorbox registration reference; other systems not independently swept. |
| Reach Records, TPR Live, HOG MOB, Holy Culture, ChristianHits, Awakening Events, FlavorFest, TRNSCND, Outlandish, Overflow, Passion Fest, Nu Wave, Reach1 | **Partial:** Reach Records, BEC/Zauntee and selected organizer/festival references; not every promoter individually searched today. |
| Venue, church, university, museum, community, parks, tourism, radio calendars | **Partial:** Ridglea, Bomb Factory, Iron Sharp, Gathering Church, selected public venue listings. Not nationwide exhaustive coverage. |
| Artwork, cancellation/reschedule, redirect, live links, artist association, post-refresh retention | **Partial:** Protected Don Ready LA approved flyer and identity, priority event links; no complete image/HTTP audit. **Post-refresh survival pending** new full-scan completion. |

**Integrity:** Jay Kalyl removed; DJ Maj/TobyMac excluded; no new artist profiles, duplicates, speculative dates, or unauthorized hold/artwork changes. Corrections are **not** counted as new shows.
