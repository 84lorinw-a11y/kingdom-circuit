# The Kingdom Circuit

A free, automated U.S. Christian hip-hop concert and festival calendar.

## Artist portraits are static editorial assets

Artist directory and profile photos must be saved in `assets/artists/` and registered
in `config/artist-portraits.json`. Daily show refreshes reuse these versioned files;
they must not fetch, replace, or remove approved portraits. Sheet/social updates
cannot replace a saved portrait. Event artwork is handled separately.

For an intentional portrait addition/replacement, save the original file, then run:

```sh
python scripts/artist_portraits.py pin "Artist Name" assets/artists/new-portrait.jpg --source "https://official-source/" --position "center"
python scripts/sync_verified_artist_registry.py
```

Review the result and run the complete production build. The release checks require
the approved portrait on both the directory and profile, validate the original checksum,
decode every referenced local image and responsive variant, and reject external photo
dependencies. Missing/corrupt/replaced images stop publication so the previous release
stays live. When intentionally removing an artist, remove their portrait registry and
override entries together. Keep old image files for historical references.

## Master v9

- Removes TobyMac from active CHH monitoring while preserving his name only on Ticketmaster events explicitly shared with KB.
- Moves source-warning details to a small footer notice.
- Standardizes all Official details buttons to the compact size.
- Replaces branded fallback cards with neutral concert artwork.
- Adds approved event or artist images for Turned Up for Christ, Sevin, EGR, FLAME, LifeLight, and Caleb Gordon.
- Adds the verified FLAME Plano show, LifeLight Sioux Falls with KB, 21 future EGR schedule dates, and all eight Caleb Gordon Eden Experience dates.
- Preserves all existing manually verified listings, including Mike Malagies on October 2.

## Required repository secret

- `TICKETMASTER_API_KEY`

## Existing integrations preserved

- Google Analytics: `G-N2KK9XF4TJ`
- Formspree submission endpoint
- Custom domain and GitHub Actions workflow
