#!/usr/bin/env python3
"""Check the requested content in the final artifact, after all design layers."""
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import apply_rock_the_pines as rock
import apply_trnscnd_submission as trnscnd
import build_seo_site as builder


def verify(site: Path) -> None:
    artists = json.loads((site / "config/artists.json").read_text())
    reviewed = json.loads((Path(__file__).resolve().parents[1] / "config/verified-artist-registry-updates.json").read_text())
    for name in trnscnd.PROFILED_ARTISTS:
        artist = next(a for a in artists if a["name"] == name)
        expected = next(a for a in reviewed if a["name"] == name)
        text = html.unescape((site / builder.artist_path(name).strip("/") / "index.html").read_text())
        for field in ("instagramProfile", "spotifyProfile", "youtubeProfile"):
            assert artist[field] == expected[field], (name, field)
            assert f'href="{expected[field]}"' in text, (name, field, "missing public link")
        image = next(tag for tag in re.findall(r'<img\b[^>]*>', text) if f'alt="{name}"' in tag)
        source = re.search(r'\bsrc="([^"]+)"', image)[1]
        assert "/assets/optimized/" in source and (site / urlsplit(source).path.lstrip("/")).is_file(), name
    for source in (trnscnd.EVENT, rock.EVENT):
        if not builder.current(source):
            continue
        event = dict(source, id="manual:" + source["id"])
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        assert "event-detail--landscape" in detail, href
        line = re.search(r'<p class="artist-line">(.*?)</p>', detail, re.S)[1]
        assert all(name in html.unescape(line) for name in source["advertisedBilling"]), href
        for page in ("index.html", "shows/index.html"):
            text = (site / page).read_text()
            cards = re.findall(r'<article\b[^>]*data-event-card[^>]*>.*?</article>', text, re.S)
            card = next(card for card in cards if href in card)
            assert all(name in html.unescape(card) for name in source["advertisedBilling"]), (page, href)
        assert "/artists/leah-dates/" not in detail and "/artists/lj-the-messenger/" not in detail
    print("Final content verified: complete billing, landscape flyers, four artist portraits and verified social links")


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
