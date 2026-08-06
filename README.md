# The Kingdom Circuit

A free, automated U.S. Christian hip-hop concert and festival calendar.

## Master v7

- Expanded monitored roster with independent and legacy CHH artists.
- Daily Ticketmaster, label, promoter, artist, festival, and public-source monitoring.
- Added official Sevin/HOG MOB tour parsing.
- Added verified Hope Fest, Turned Up for Christ, and Faith Jam listings.
- Show submissions and corrections use a private email form rather than GitHub Issues.
- `Just announced` begins August 10, 2026 and appears only for genuinely new listings for seven days.

## Required repository secret

- `TICKETMASTER_API_KEY`

## One-time form setup

Create a Formspree form, then replace the placeholder in `the submission endpoint near the top of app.js` with the form ID. The public site sees only the random form endpoint, not the recipient email address.
