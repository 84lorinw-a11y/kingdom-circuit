# The Kingdom Circuit

A free, automated U.S. Christian hip-hop concert and festival calendar.

## Master v8

- Expands the monitored roster from 140 to 300 artists and groups.
- Includes the current high-streaming CHH priority set plus active, emerging, legacy, crossover, international, label, collective, and festival-lineup artists.
- Uses three monitoring priorities: 100 priority-one, 100 priority-two, and 100 priority-three artists.
- Runs identity-safe Ticketmaster matching for 205 artists and blocks ambiguous names from unsafe free-text matching.
- Runs public social-index checks for the 99 highest-priority active artists.
- Expands official and exact artist-calendar sources from 68 to 83.
- Preserves manually verified shows because this update intentionally does not replace `config/manual-events.json`.

## Required repository secret

- `TICKETMASTER_API_KEY`

## Existing integrations preserved

This targeted update does not replace the website HTML, Google Analytics tag, Formspree endpoint, event artwork, current generated event feed, or manual event file.
