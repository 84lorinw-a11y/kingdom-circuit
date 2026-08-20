#!/usr/bin/env python3
"""Sync the Aug. 20 verified artist registry rows into production data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"

SOCIALS: dict[str, dict[str, str]] = {
    "Brenno": {"website":"https://www.brennomusic.live/","instagramProfile":"https://www.instagram.com/brenno.music/","spotifyProfile":"https://open.spotify.com/artist/7lBcEp7abNiq3WyHT3RRqV","youtubeProfile":"https://www.youtube.com/@brenno.music1/videos"},
    "Shepherd": {"website":"https://www.shepherd.live/","instagramProfile":"https://www.instagram.com/shepherd_music/","spotifyProfile":"https://open.spotify.com/artist/0YHuTR40zc9yqfoSSArQxU?si=uLy6lYIBTr6JOUAC3VCQRw&dl_branch=1&nd=1&dlsi=9e8b14d62f1848e4","youtubeProfile":"https://www.youtube.com/channel/UCc6gnoGyHriWXsAEX-OcueQ"},
    "Kai Uriah": {"instagramProfile":"https://www.instagram.com/kaiuriah/?hl=en","spotifyProfile":"https://open.spotify.com/artist/6IdKInshEI8ywJ99v6gVKM","youtubeProfile":"https://www.youtube.com/@kaiuriah"},
    "Hyper Fenton": {"website":"https://hyperfenton.com/?srsltid=AfmBOooF879r3FwdrhkdtvTJm7pVqTdkh89fyt-Dk4UoXInfWloW7xKh","instagramProfile":"https://www.instagram.com/hyperfenton/?hl=en","spotifyProfile":"https://open.spotify.com/artist/2q5QIs6iibW6xyHZZRSeh2","youtubeProfile":"https://music.youtube.com/playlist?list=OLAK5uy_mriMUrHlhyB3ejFMfLTlJohVxDbdscX5s"},
    "Brea Miles": {"website":"https://www.alwaysbrea.com/","instagramProfile":"https://www.instagram.com/alwaysbrea","spotifyProfile":"https://open.spotify.com/artist/2S8dO0fwL0qup5Eo7OHs5i","youtubeProfile":"https://www.youtube.com/breamiles"},
    "Issac Mansfield": {"website":"https://www.issacmansfield.com/","instagramProfile":"https://www.instagram.com/issacmansfield/","spotifyProfile":"https://open.spotify.com/artist/1QgXbOPk6XpELZrJOzz33w","youtubeProfile":"https://www.youtube.com/@issac.mansfield/featured"},
    "Tylan1k": {"instagramProfile":"https://www.instagram.com/tylanthechosen1/?hl=en","spotifyProfile":"https://open.spotify.com/artist/6PY88og97O47AlwuyFFRhr","youtubeProfile":"https://www.youtube.com/channel/UCeJ8yMp5bJjTxBp_COGNB6w"},
    "Jabari Heavens": {"instagramProfile":"https://www.instagram.com/jabariheavens/","spotifyProfile":"https://open.spotify.com/artist/2ORjCgiRF9ZIK4gak1CsYP","youtubeProfile":"https://www.youtube.com/@JabariHeavens"},
    "Rhema Soul": {"instagramProfile":"https://www.instagram.com/rhemasoul/","spotifyProfile":"https://open.spotify.com/artist/6kqgFtlPJHyqqffmlDTTzd","youtubeProfile":"https://www.youtube.com/@RhemaSoul/featured"},
    "Shonlock": {"website":"http://www.shonlock.com/","instagramProfile":"https://www.instagram.com/shonlock/","spotifyProfile":"https://open.spotify.com/artist/0Fs18mA7TFMvYVRNX4dNTt","youtubeProfile":"https://music.youtube.com/@Shonlock"},
    "Viktory": {"instagramProfile":"https://www.instagram.com/viktoryr4/?hl=en","spotifyProfile":"https://open.spotify.com/artist/7jKYoI3eKh85xfqK7TAlN5","youtubeProfile":"https://www.youtube.com/@ViktoriousMusic"},
    "T-Bone": {"website":"http://houseoftbone.com/","instagramProfile":"https://www.instagram.com/tboneoficial/?hl=en","spotifyProfile":"https://open.spotify.com/artist/6h2GxbU7emrTikSWxbMyxd","youtubeProfile":"https://www.youtube.com/channel/UCxQgnrqdZe_2qAR9jzyVmmg"},
    "Bishop Freeze": {"website":"https://www.sozomissions.com/music/bishop-freeze","instagramProfile":"https://www.instagram.com/bishopfreeze_/","spotifyProfile":"https://open.spotify.com/artist/1epkzUW5gL4DHjW8rlPa3P","youtubeProfile":"https://www.youtube.com/@sozomissions"},
}

BEYOND_THE_WALLS = {
    "id":"supplemental:beyond-the-walls-3-brenno-2026","title":"Beyond The Walls 3","startDate":"2026-11-07","startTime":"19:30","timezone":"America/New_York",
    "venue":"The Cambridge Room at House of Blues Cleveland","address":"308 Euclid Ave","city":"Cleveland","state":"OH","country":"US",
    "artists":["KB","Brenno","Porsha Love"],"headliner":"KB","eventType":"concert","status":"onsale",
    "ticketUrl":"https://www.ticketmaster.com/beyond-the-walls-3-cleveland-ohio-11-07-2026/event/05006488EE58E30A",
    "officialUrl":"https://www.ticketmaster.com/beyond-the-walls-3-cleveland-ohio-11-07-2026/event/05006488EE58E30A","image":"","price":"",
    "sourceName":"Ticketmaster / Brenno official upcoming shows","authority":"venue_ticket","confidence":"high","lineupExplicit":True,
    "sources":[
        {"name":"Ticketmaster","url":"https://www.ticketmaster.com/beyond-the-walls-3-cleveland-ohio-11-07-2026/event/05006488EE58E30A","type":"manual_verified","authority":"venue_ticket","priority":100},
        {"name":"Brenno official upcoming shows","url":"https://www.brennomusic.live/","type":"manual_verified","authority":"artist_calendar","priority":100}
    ]
}

def load(path: Path) -> list[dict[str, Any]]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,list): raise SystemExit(f"Expected JSON array: {path}")
    return value

def write(path: Path, value: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

def norm(value: Any) -> str: return str(value or "").strip().casefold()

def is_beyond_walls(event: dict[str, Any]) -> bool:
    return str(event.get("startDate") or "")=="2026-11-07" and norm(event.get("city"))=="cleveland" and "beyond the walls" in norm(event.get("title"))

def main() -> int:
    artists=load(ARTISTS_FILE); events=load(EVENTS_FILE); supplemental=load(SUPPLEMENTAL_FILE)
    by_name={norm(item.get("name")):item for item in artists}
    for name,links in SOCIALS.items():
        artist=by_name.get(norm(name))
        if not artist: raise SystemExit(f"Artist missing from production registry: {name}")
        artist.update(links)

    corrected=[]; found_ticketmaster=False
    for event in events:
        if not is_beyond_walls(event):
            corrected.append(event); continue
        if norm(event.get("sourceName"))=="mike teezy apple music concerts":
            continue
        if norm(event.get("sourceName"))=="ticketmaster":
            found_ticketmaster=True
            names=list(event.get("artists") or [])
            if "Brenno" not in names:
                try: names.insert(names.index("KB")+1,"Brenno")
                except ValueError: names.append("Brenno")
            event["artists"]=names
        corrected.append(event)
    if not found_ticketmaster: raise SystemExit("Expected Ticketmaster Beyond The Walls 3 record was not found")

    supplemental=[item for item in supplemental if norm(item.get("id"))!=norm(BEYOND_THE_WALLS["id"])]
    supplemental.append(BEYOND_THE_WALLS)
    supplemental.sort(key=lambda item:(str(item.get("startDate") or "9999-12-31"),norm(item.get("title"))))

    write(ARTISTS_FILE,artists); write(EVENTS_FILE,corrected); write(SUPPLEMENTAL_FILE,supplemental)
    for name in SOCIALS:
        artist=by_name[norm(name)]
        for required in ("instagramProfile","spotifyProfile","youtubeProfile"):
            if not artist.get(required): raise SystemExit(f"{name} missing {required} after registry sync")
    live=[item for item in corrected if is_beyond_walls(item)]
    if len(live)!=1 or "Brenno" not in live[0].get("artists",[]): raise SystemExit("Beyond The Walls 3 did not normalize correctly")
    print(f"Synced verified socials for {len(SOCIALS)} artists; Beyond The Walls 3 normalized.")
    return 0

if __name__=="__main__": raise SystemExit(main())
