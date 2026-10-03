"""Check the intake's final public artifact, after every production writer."""
import html
import json
from pathlib import Path
import sys

from artist_portraits import verify_site
from build_seo_site import event_path
from catalog_removals import removed_event

ROOT = Path(__file__).resolve().parents[1]
OWNER_HELD_IDS = {"alex-jean-dallas-2026-11-19"}


def verify(site):
    photos = verify_site(site, ROOT)
    registry = json.loads((ROOT / 'config/verified-artist-registry-updates.json').read_text())
    intake = [r for r in registry if 190 <= int(r.get('sheetRosterOrder') or 0) <= 213]
    artists = {r['name']: r for r in json.loads((site / 'config/artists.json').read_text())}
    monitored = {r['name']: r for r in json.loads((ROOT / 'config/artists.json').read_text())}
    for row in intake:
        artist = artists[row['name']]
        assert monitored[row['name']]['enabled'] and monitored[row['name']]['socialSearchEnabled'], row['name']
        for field in ['instagramProfile', 'spotifyProfile', 'youtubeProfile']:
            assert artist.get(field, '') == row.get(field, ''), (row['name'], field)
    assert 'Propaganda' not in artists
    assert not (site / 'artists/propaganda/index.html').exists()
    assert '/artists/propaganda/' not in (site / 'sitemap.xml').read_text()
    events = [r for name in ['events.json', 'supplemental-events.json']
              for r in json.loads((site / name).read_text())]
    assert not any(removed_event(r) for r in events)

    for held_id in OWNER_HELD_IDS:
        assert not any(str(event.get('id')).removeprefix('manual:') == held_id for event in events), held_id
        held_token = held_id.replace('-', ' ')
        for page in site.rglob('*.html'):
            text = html.unescape(page.read_text(encoding='utf-8', errors='ignore')).casefold()
            assert held_token.casefold() not in text, (held_id, page)

    approved = json.loads((ROOT / 'config/oct2-verified-shows.json').read_text())
    patches = json.loads((ROOT / 'config/sep26-requested-lineups.json').read_text())
    for event_id in ['egr-2026-10-10-visalia-ca', 'bandsintown:108975912',
                     'bandsintown:108976155', 'alex-jean-plaza-live-orlando-2026-11-27',
                     'sevin-live-nashville-2026-10-24']:
        approved.append(dict(patches[event_id], id=event_id))
    checked = 0
    for wanted in approved:
        if wanted['id'] in OWNER_HELD_IDS:
            continue
        matches = [e for e in events if str(e.get('id')).removeprefix('manual:') == wanted['id']]
        # The primary and supplemental feeds can overlap, but they must agree.
        assert matches, wanted['id']
        for event in matches:
            for field in ['startTime', 'venue', 'artists', 'advertisedBilling', 'hosts']:
                if field in wanted:
                    assert event.get(field) == wanted[field], (wanted['id'], field, event.get(field))
            page = site / event_path(event).strip('/') / 'index.html'
            assert page.is_file(), page
            text = html.unescape(page.read_text())
            for performer in wanted.get('advertisedBilling', []):
                assert performer in text, (wanted['id'], performer)
        checked += 1
    print(json.dumps(dict(verifiedIntakeArtists=len(intake), checkedConcerts=checked,
                          ownerHeldConcerts=len(OWNER_HELD_IDS), **photos), sort_keys=True))


if __name__ == '__main__':
    verify(Path(sys.argv[1] if len(sys.argv) > 1 else '_site').resolve())
