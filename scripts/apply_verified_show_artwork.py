"""Preserve reviewed show images and primary ticket sources across refreshes.

Pins are scoped to an existing event identity and date. They never create an
event, reset discovery age, change schedules, or expand the curated roster.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = json.loads((ROOT / "config/verified-show-artwork.json").read_text())
BY_ID = {pin["id"]: pin for pin in PINS}

# Observed alternate-provider records for the same reviewed performances.
# Do not match by artist/date alone: an artist can play twice on the same day.
PROVIDER_ALIASES = {
    "ticketmaster:Z7r9jZ1AAepra": "bandsintown:108975912",
    "official:82953bf17964628bbd9b": "bandsintown:108881783",
    "ticketmaster:vv1AaZkfMGkd2fZDG": "bandsintown:1040378722",
    "official:498b9c1935ee983f352d": "manual:rock-the-universe-orlando-2027",
    "manual:ty-brasel-outlandish-fest-fort-worth-2026": "ty-brasel-outlandish-fest-fort-worth-2026",
    "manual:above-the-noise-rooftop-washington-2026-10-31": "above-the-noise-rooftop-washington-2026-10-31",
    "manual:marv-de-la-cruz-la-popup-2026-11-14": "marv-de-la-cruz-la-popup-2026-11-14",
    "manual:hhwg-christmas-extravaganza-royse-city-2026-12-12": "hhwg-christmas-extravaganza-royse-city-2026-12-12",
    "official:433b136650c8a5f6b264": "bandsintown:109034401",
    "official:540ae4cdd11793a36815": "bandsintown:1040595947",
    "official:b240438b7b7f8a82189d": "bandsintown:1040597655",
    "official:d890394094e7c9393937": "bandsintown:1040596451",
}
# These four already-published calendar records have no separate artwork pin.
# Their exact duplicate label-calendar links name the same Bandsintown event IDs.
PUBLISHED_DATES = {
    'bandsintown:109034401': {'startDate': '2026-11-13'},
    'bandsintown:1040595947': {'startDate': '2027-02-13'},
    'bandsintown:1040597655': {'startDate': '2027-02-20'},
    'bandsintown:1040596451': {'startDate': '2027-03-20'},
}


def reconcile_provider_duplicates(feeds, history=()):
    """Keep reviewed identity/details when these exact provider duplicates arrive.

    A current exact alias must exist. Its reviewed counterpart may be retained
    in history when the collector has already deduplicated the provider feeds.
    Matching date/venue/city/state/performers are still required. History alone
    never creates a show; conflicts stop publication rather than erase a move.
    """
    from build_seo_site import event_path, norm
    from apply_sep26_requested_lineups import PATCHES
    from catalog_removals import removed_event

    rows = [row for values in feeds.values() for row in values]
    changed = 0
    reconciled = set()
    for alias, canonical_id in PROVIDER_ALIASES.items():
        incoming = [row for row in rows if row.get('id') == alias]
        if not incoming:
            continue
        reviewed = [row for row in rows if row.get('id') == canonical_id]
        if not reviewed:
            retained = [entry.get('event', entry) for entry in history
                        if entry.get('event', entry).get('id') == canonical_id]
            if len(retained) == 1 and not removed_event(retained[0]):
                # Reconcile a currently observed duplicate, not an absent show.
                # A copy prevents rewriting the retained historical evidence.
                reviewed = [copy.deepcopy(retained[0])]
        if not reviewed:
            raise ValueError(f'{alias}: missing reviewed record {canonical_id}')
        # The current manual seed can contain newly verified artist-profile
        # associations that an older supplemental copy has not received yet.
        seed = next((row for row in feeds.get('config/manual-events.json', [])
                     if row.get('id') == canonical_id), None)
        wanted = copy.deepcopy(seed or reviewed[0])
        base_id = canonical_id.removeprefix('manual:')
        verified = BY_ID.get(base_id) or PATCHES.get(base_id) or PUBLISHED_DATES[base_id]
        for row in [*reviewed, *incoming]:
            performers = {norm(a) for a in row.get('artists', [])}
            wanted_performers = {norm(a) for a in wanted.get('artists', [])}
            manual_bill = (alias == 'manual:' + canonical_id
                           and row.get('id') in {alias, canonical_id}
                           and bool(performers)
                           and (wanted_performers | performers)
                               <= {norm(a) for a in wanted.get('advertisedBilling', [])})
            # This exact Ticketmaster alias reports the already-reviewed doors
            # time and only the headliner. The Oct 6 record confirms 8 PM music
            # and the full bill; do not discard either during deduplication.
            glo_alias = row.get('id') == 'ticketmaster:vv1AaZkfMGkd2fZDG'
            same = (row.get('startDate') == wanted.get('startDate') == verified['startDate']
                    and all(norm(row.get(k)) == norm(wanted.get(k)) and norm(row.get(k))
                            for k in ('venue', 'city', 'state'))
                    and (performers == wanted_performers or manual_bill or
                         (glo_alias and performers == {'miles minnick'} and performers < wanted_performers))
                    and bool(wanted.get('artists'))
                    and (not row.get('startTime') or not wanted.get('startTime')
                         or row['startTime'] == wanted['startTime']
                         or (glo_alias and row['startTime'] == '19:00'
                             and wanted['startTime'] == '20:00' and wanted.get('doorsTime') == '19:00')))
            if not same:
                raise ValueError(f'{alias}: reviewed performance identity conflict')
        ages = [row['firstSeen'] for row in [*reviewed, *incoming] if row.get('firstSeen')]
        for entry in history:
            event = entry.get('event', entry)
            if event.get('id') == canonical_id:
                ages.extend(value for value in (event.get('firstSeen'),
                            entry.get('firstSeenOnCalendar')) if value)
        if ages:
            wanted['firstSeen'] = min(ages)
        for key in ('sources', 'legacyEventPaths', 'mergedFromIds'):
            values = copy.deepcopy(wanted.get(key, []))
            for row in incoming:
                for value in row.get(key, []):
                    if value not in values:
                        values.append(copy.deepcopy(value))
            wanted[key] = values
        for row in incoming:
            old_path = event_path(row)
            if old_path != event_path(wanted) and old_path not in wanted['legacyEventPaths']:
                wanted['legacyEventPaths'].append(old_path)
            if alias not in wanted['mergedFromIds']:
                wanted['mergedFromIds'].append(alias)
            # Never turn a newly cancelled/postponed show back into scheduled.
            if norm(row.get('status')) in {'cancelled', 'canceled', 'postponed'}:
                wanted['status'] = row['status']
        patch_event(wanted)
        for row in [*reviewed, *incoming]:
            row.clear()
            row.update(copy.deepcopy(wanted))
        changed += len(incoming)
        reconciled.add(canonical_id)
    # An alias and its canonical record may both have occupied the primary feed.
    # Collapse only the reviewed identities changed above, never unrelated rows.
    if changed:
        for values in feeds.values():
            seen = set()
            kept = []
            for row in values:
                identity = row.get('id')
                if identity in reconciled:
                    if identity in seen:
                        continue
                    seen.add(identity)
                kept.append(row)
            values[:] = kept
    return changed


def patch_event(event):
    event_id = str(event.get("id") or "").removeprefix("manual:")
    pin = BY_ID.get(event_id)
    if not pin or event.get("startDate") != pin["startDate"]:
        return False
    event.update(copy.deepcopy({key: value for key, value in pin.items()
                                if key not in {"id", "startDate"}}))
    if pin.get("officialUrl"):
        # Keep the original calendar evidence, but prioritize the exact ticket
        # page the owner selected. Repeated refreshes must not duplicate it.
        sources = [source for source in event.get("sources", [])
                   if source.get("url") != pin["officialUrl"]]
        event["sources"] = [{"name": pin["sourceName"], "url": pin["officialUrl"],
                             "type": "manual_verified", "authority": "venue_ticket",
                             "priority": 100}] + sources
    return True


def apply(root=ROOT):
    for name in ("events.json", "supplemental-events.json", "config/manual-events.json", "event-history.json"):
        path = root / name
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        rows = data.get("events", []) if isinstance(data, dict) else data
        changed = False
        for entry in rows:
            event = entry.get("event", entry)
            before = copy.deepcopy(event)
            patch_event(event)
            changed = changed or before != event
        if changed:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    apply()
