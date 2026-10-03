"""Release gate for the owner-reviewed roster, socials and saved portraits."""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from owner_roster import ROOT, norm, removed_names, snapshot, verify_records
from artist_portraits import load_portraits, verify_site as verify_portraits

FIELDS = ("website", "instagramProfile", "spotifyProfile", "youtubeProfile", "officialImageSource")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.add(dict(attrs).get("href", ""))


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.casefold().replace("&", " and ")).strip("-")


def verify(site: Path | None = None):
    root = site or ROOT
    artists = json.loads((root / "config/artists.json").read_text())
    verify_records(artists)
    by_name = {norm(a["name"]): a for a in artists}
    updates = json.loads((ROOT / "config/verified-artist-registry-updates.json").read_text())
    expected = {norm(a["name"]) for a in snapshot() if a["verified"]}
    assert {norm(a["name"]) for a in updates} == expected, "Verified handoff differs from owner review"
    # Internal verification/provenance fields are intentionally removed from
    # the public JSON. Check approval against the durable source registry.
    source_artists = json.loads((ROOT / "config/artists.json").read_text())
    assert {norm(a["name"]) for a in source_artists if a.get("sourceRegistryVerified")} == expected, "Verification status drift"
    portraits = {norm(n): p for n, p in load_portraits(ROOT).items()}
    for update in updates:
        name = update["name"]
        artist = by_name[norm(name)]
        for field in (FIELDS[:-1] if site else FIELDS):
            assert artist.get(field, "") == update.get(field, ""), (name, field, "reviewed link changed")
        assert norm(name) in portraits, (name, "missing saved portrait")
        if site:
            page = site / "artists" / slug(name) / "index.html"
            parser = Links()
            parser.feed(page.read_text())
            for field in FIELDS[:-1]:
                url = update.get(field)
                assert not url or url in parser.hrefs, (name, field, "missing public profile link")
    if site:
        sitemap = (site / "sitemap.xml").read_text()
        directory = (site / "artists/index.html").read_text()
        for name in removed_names():
            path = "/artists/" + slug(name) + "/"
            assert not (site / path.lstrip("/")).exists(), (name, "deleted profile restored")
            assert path not in sitemap and path not in directory, (name, "deleted profile still linked")
        verify_portraits(site, ROOT)
    return {"artists": len(artists), "verified": len(expected), "removed": len(removed_names())}


if __name__ == "__main__":
    print("Owner-reviewed roster verified:", verify(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None))
