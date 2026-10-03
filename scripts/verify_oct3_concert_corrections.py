"""Verify final deployed data, pages and images after the complete production build."""
import html
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from apply_oct3_concert_corrections import ROOT, WRONG_NEHEMIAH_IDS, rejected, key
from apply_verified_event_overrides import REVIVAL_NIGHT_EVENT
from apply_verified_show_artwork import BY_ID
from build_seo_site import event_path, fnv
from verify_egr_bizzle_updates import uses_image


def verify(site):
    today = datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
    events = [e for name in ['events.json', 'supplemental-events.json'] for e in json.loads((site / name).read_text())]
    assert not any(rejected(e) for e in events)
    history = json.loads((ROOT / 'event-history.json').read_text())['events']
    assert not any(rejected(e.get('event', e)) for e in history)
    for event_id in WRONG_NEHEMIAH_IDS:
        assert not list((site / 'event').glob(f'*-{fnv(event_id)}/index.html')), event_id
    nehemiah = [e for e in events if 'Nehemiah' in e.get('artists', [])]
    if today <= '2026-10-17':
        assert len([e for e in nehemiah if key(e) == 'adrenaline-valrico-2026-10-17']) == 1
    registry = json.loads((site / 'config/artists.json').read_text())
    artist = next(a for a in json.loads((ROOT / 'config/artists.json').read_text()) if a['name'] == 'Nehemiah')
    assert '15347266' in artist['bandsintownRejectedArtistIds']
    assert artist['socialSearchEnabled'] and not artist['ticketmasterEnabled'] and not artist['textMatchEnabled']
    wanted = json.loads((ROOT / 'config/oct3-verified-concerts.json').read_text())
    wanted.append(REVIVAL_NIGHT_EVENT)
    wanted.append(dict(id='ty-brasel-outlandish-fest-fort-worth-2026',
                       **json.loads((ROOT / 'config/sep26-requested-lineups.json').read_text())['ty-brasel-outlandish-fest-fort-worth-2026']))
    for event_id in ['whatuprg-houston-2026-11-19','whatuprg-dallas-2026-11-20','whatuprg-san-antonio-2026-11-22']:
        wanted.append(dict(BY_ID[event_id], advertisedBilling=['WHATUPRG', 'aftrthght', 'De La Cruz']))
    verified = []
    for expected in wanted:
        if (expected.get('endDate') or expected['startDate']) < today:
            continue
        matches = [e for e in events if key(e) == key(expected)]
        assert matches, expected['id']
        for e in matches:
            for field in ['startDate','startTime','venue','artists','advertisedBilling']:
                if field in expected:
                    assert e.get(field) == expected[field], (expected['id'], field, e.get(field), expected[field])
            path = event_path(e)
            page = site / path.strip('/') / 'index.html'
            text = html.unescape(page.read_text())
            for performer in expected.get('advertisedBilling', []):
                assert performer in text, (e['id'], performer)
            assert (site / e['image'].lstrip('/')).is_file(), e['image']
            original = expected.get('image') or BY_ID[key(e)]['image']
            digest = hashlib.sha256((site / original).read_bytes()).hexdigest()[:24]
            assert e['image'].lstrip('/') == original or re.fullmatch(
                rf'assets/optimized/{digest}-w\d+\.webp', e['image'].lstrip('/'))
            assert uses_image(text, site, original), (e['id'], 'rendered artwork')
            verified.append(dict(id=e['id'], path=path, image=e['image']))
    text = (site / 'artists/nehemiah/index.html').read_text()
    if today <= '2026-10-17':
        assert 'adrenaline' in text.casefold()
    public_artist = next(a for a in registry if a['name'] == 'Nehemiah')
    assert (site / public_artist['imageUrl'].lstrip('/')).is_file()
    print(json.dumps(dict(verifiedConcerts=verified, removedWrongArtistShows=len(WRONG_NEHEMIAH_IDS), nehemiahShows=len(nehemiah)), indent=2))


if __name__ == '__main__':
    verify(Path(sys.argv[1] if len(sys.argv) > 1 else '_site').resolve())
