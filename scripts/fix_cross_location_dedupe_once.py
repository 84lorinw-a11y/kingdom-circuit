#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_app() -> None:
    path = ROOT / "app.js"
    text = path.read_text(encoding="utf-8")
    old = '''  const leftState = normalize(existing.state);
  const rightState = normalize(incoming.state);
  if (leftState && rightState && leftState !== rightState) return false;

  const leftAddress = normalizeEventText(existing.address);
  const rightAddress = normalizeEventText(incoming.address);
  const sameAddress = Boolean(leftAddress && rightAddress && leftAddress === rightAddress);
  const leftCity = normalizeEventCity(existing.city);
  const rightCity = normalizeEventCity(incoming.city);
  if (!sameAddress && (!leftCity || !rightCity || leftCity !== rightCity)) return false;
  if (!eventTimesCompatible(existing, incoming)) return false;
'''
    new = '''  const leftState = normalize(existing.state);
  const rightState = normalize(incoming.state);
  const earlyLeftArtists = eventArtistSet(existing);
  const earlySharedArtist = [...eventArtistSet(incoming)].some(name => earlyLeftArtists.has(name));
  const earlyLeftVenue = normalizeEventVenue(existing.venue);
  const earlyRightVenue = normalizeEventVenue(incoming.venue);
  const earlyVenueTokens = Math.min(
    earlyLeftVenue.split(" ").filter(Boolean).length,
    earlyRightVenue.split(" ").filter(Boolean).length
  );
  const earlyVenueScore = tokenContainment(
    new Set(earlyLeftVenue.split(" ").filter(Boolean)),
    new Set(earlyRightVenue.split(" ").filter(Boolean))
  );
  const strongVenueIdentity = Boolean(
    earlySharedArtist && earlyLeftVenue && earlyRightVenue &&
    earlyVenueTokens >= 2 && earlyVenueScore >= 0.90 && eventTimesCompatible(existing, incoming)
  );
  const crossStateVenueIdentity = strongVenueIdentity && earlyVenueTokens >= 3;
  if (leftState && rightState && leftState !== rightState && !crossStateVenueIdentity) return false;

  const leftAddress = normalizeEventText(existing.address);
  const rightAddress = normalizeEventText(incoming.address);
  const sameAddress = Boolean(leftAddress && rightAddress && leftAddress === rightAddress);
  const leftCity = normalizeEventCity(existing.city);
  const rightCity = normalizeEventCity(incoming.city);
  if (!sameAddress && (!leftCity || !rightCity || leftCity !== rightCity) && !strongVenueIdentity) return false;
  if (!eventTimesCompatible(existing, incoming)) return false;
'''
    if new in text:
        return
    if old not in text:
        raise RuntimeError("app.js target block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_collector() -> None:
    path = ROOT / "scripts" / "update_events.py"
    text = path.read_text(encoding="utf-8")
    old = '''    if not same_date:
        return False
    if normalize_state(str(left.get("state") or "")) != normalize_state(str(right.get("state") or "")):
        return False

    left_address = normalize_address(left.get("address"))
    right_address = normalize_address(right.get("address"))
    same_address = bool(left_address and right_address and left_address == right_address)
    city_match = cities_compatible(left, right)
    if not city_match and not same_address:
        return False

    city = str(left.get("city") or right.get("city") or "")
'''
    new = '''    if not same_date:
        return False

    # Aggregators sometimes geocode an exact venue to a nearby city/state.
    # When the artist, time, and distinctive venue identity agree, prefer that
    # evidence over the provider's location label. Cross-state overrides require
    # 3+ venue tokens to avoid merging generic venues in different states.
    left_venue_identity = normalize_venue(str(left.get("venue") or ""), "")
    right_venue_identity = normalize_venue(str(right.get("venue") or ""), "")
    venue_identity_score = token_containment(left_venue_identity, right_venue_identity)
    venue_identity_tokens = min(len(left_venue_identity.split()), len(right_venue_identity.split()))
    early_overlap = artist_overlap(left, right)
    strong_venue_identity = bool(
        early_overlap
        and left_venue_identity
        and right_venue_identity
        and venue_identity_tokens >= 2
        and venue_identity_score >= 0.90
        and times_compatible(left, right)
    )
    cross_state_venue_identity = strong_venue_identity and venue_identity_tokens >= 3
    left_state = normalize_state(str(left.get("state") or ""))
    right_state = normalize_state(str(right.get("state") or ""))
    if left_state != right_state and not cross_state_venue_identity:
        return False

    left_address = normalize_address(left.get("address"))
    right_address = normalize_address(right.get("address"))
    same_address = bool(left_address and right_address and left_address == right_address)
    city_match = cities_compatible(left, right)
    if not city_match and not same_address and not strong_venue_identity:
        return False

    city = str(left.get("city") or right.get("city") or "")
'''
    if new in text:
        return
    if old not in text:
        raise RuntimeError("update_events.py target block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def dedupe_current_events() -> tuple[int, int]:
    from update_events import merge_events

    path = ROOT / "events.json"
    events = json.loads(path.read_text(encoding="utf-8"))
    before = len(events)
    merged = merge_events(events)
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    stops = [
        event for event in merged
        if event.get("startDate") == "2026-09-08"
        and "Hulvey" in (event.get("artists") or [])
        and "fillmore" in str(event.get("venue") or "").lower()
    ]
    if len(stops) != 1:
        raise RuntimeError(f"Expected one Sept 8 Fillmore Hulvey stop, found {len(stops)}")
    if stops[0].get("state") != "MD":
        raise RuntimeError(f"Expected Ticketmaster MD location to win, got {stops[0].get('state')}")
    return before, len(merged)


def main() -> None:
    patch_app()
    patch_collector()
    before, after = dedupe_current_events()
    print(f"Event dedupe repaired: {before} -> {after} current events")


if __name__ == "__main__":
    main()
