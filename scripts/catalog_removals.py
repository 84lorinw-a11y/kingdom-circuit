"""Owner-requested removals and publication holds for refreshed shows."""
import json
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

# September 28: the owner removed Jay Kalyl from the curated database and
# explicitly requested removal of his profile and every show from the site.
# October 2: remove Propaganda's artist entry and performances, including
# archived/collector records. Host-only billing at another artist's event is
# not a separately confirmed performance by the removed artist.
REMOVED_ARTISTS = {"jay kalyl", "propaganda"}
REVIEW_FILE = Path(__file__).resolve().parents[1] / "config/review-held-events.json"
LOCATION_REVIEW_ID = "official:023c040d4ea33e120949"


def removed_artist(name):
    return re.sub(r"[\s_-]+", " ", str(name or "").casefold()).strip() in REMOVED_ARTISTS


def misattributed_event(event):
    # The Jan 23 idol concert bills @altarego_info (NJ/NY idol duo), not
    # @altaregorecords (Bo Fisher / Justo Chalaire). Keep raw evidence/history.
    if event.get("startDate") == "2027-01-23":
        if str(event.get("id") or "").removeprefix("manual:") == "bandsintown:1040675970":
            return True
        for field in ("officialUrl", "ticketUrl"):
            try:
                url = urlsplit(str(event.get(field) or ""))
                host = (url.hostname or "").lower().removeprefix("www.")
            except ValueError:
                continue
            if url.scheme not in {"http", "https"}:
                continue
            if host == "bandsintown.com" and re.fullmatch(r"/[et]/1040675970(?:[-/].*)?", url.path):
                return True
            if host == "eventbrite.com" and url.path.endswith("-tickets-2003227249629"):
                return True
    # November 5 review: this exact Betsy booking features the Miami jazz
    # pianist, not the Christian singer in our Ryan Ellis roster. Preserve the
    # original evidence/history; exclude only this reviewed date and identity.
    if event.get("startDate") != "2026-11-13":
        return False
    if str(event.get("id") or "").removeprefix("manual:") == "bandsintown:1040781482":
        return True
    for field in ("officialUrl", "ticketUrl"):
        try:
            url = urlsplit(str(event.get(field) or ""))
            host = (url.hostname or "").lower().removeprefix("www.")
        except ValueError:
            continue
        if url.scheme not in {"http", "https"}:
            continue
        if host == "bandsintown.com" and re.fullmatch(r"/[et]/1040781482(?:[-/].*)?", url.path):
            return True
        if host == "thebetsyhotel.com" and url.path.rstrip("/") == (
            "/event-calendar/live-music-intergenerational-jazz-ellis-duo-13"
        ):
            return True
    return False


def withheld_event(event):
    # Artist's November 7 listing explicitly says he is a beat-battle judge,
    # not a performer. Keep the real Flavor Fest concert and other K-Drama sets.
    if event.get("startDate") == "2026-11-07" and (
        str(event.get("id") or "").removeprefix("manual:") == "bandsintown:109046095"
        or any(re.search(r"bandsintown\.com/[et]/109046095(?:[/?#-]|$)",
                         str(event.get(field) or ""))
               for field in ("officialUrl", "ticketUrl"))
    ):
        return True
    # October 8: owner rejected this specific event because the artist match
    # is not reliable. Keep future source refreshes from publishing it.
    rejected_url = "https://www.kingdomtix.org/events/ec10348c-3f78-4c97-95d6-587a5f5fb380"
    if any(str(event.get(field) or "").split("?")[0].rstrip("/") == rejected_url
           for field in ("officialUrl", "ticketUrl")):
        return True
    # Owner authorized withholding this conflicting booking on October 6.
    # It is not a cancellation and not the separate October 10 JWoodz event.
    # A later rescheduled date is eligible for a new review rather than blocked.
    if event.get("startDate") == "2026-11-14" and (
        str(event.get("id") or "").removeprefix("manual:") == "cj-emulous-kickback-grand-prairie-2026"
        or any(str(event.get(field) or "").split("?")[0].rstrip("/") ==
               "https://www.cjemulous.com/event-details/the-kickback-w-cj-emulous"
               for field in ("officialUrl", "ticketUrl"))
    ):
        return True
    return False


def _location_review_identity(event):
    # The artist calendar pairs Texas Motorplex with a Florida locality.
    # November 6: the owner accepts the artist calendar's booking, but neither
    # conflicting location. Keep its exact identity available for redaction.
    if event.get("startDate") != "2026-11-21":
        return False
    if str(event.get("id") or "").removeprefix("manual:") in {
        LOCATION_REVIEW_ID, "bandsintown:1040798191"
    }:
        return True
    if str(event.get("bandsintownEventId") or "") == "1040798191":
        return True
    for field in ("officialUrl", "ticketUrl"):
        raw = str(event.get(field) or "")
        if any(character.isspace() for character in raw):
            continue
        try:
            url = urlsplit(raw)
            host = (url.hostname or "").lower().removeprefix("www.")
            port = url.port
        except ValueError:
            continue
        if (url.scheme in {"http", "https"} and host == "bandsintown.com"
                and not url.username and not url.password
                and port in {None, 443 if url.scheme == "https" else 80}
                and re.fullmatch(r"/[et]/1040798191(?:-[^/]+)?/?", url.path)):
            return True
    return False


def _location_resolution():
    """Only a complete, explicitly approved repository review releases the hold."""
    try:
        records = json.loads(REVIEW_FILE.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(records, list):
        return None
    for record in records:
        if not isinstance(record, dict) or not (
            record.get("excludedEventId") == LOCATION_REVIEW_ID
            and record.get("reviewStatus") == "resolved_location_confirmed"
            and record.get("publish") is True
        ):
            continue
        event = record.get("resolvedEvent")
        if (not isinstance(event, dict) or event.get("id") != LOCATION_REVIEW_ID
                or event.get("startDate") != "2026-11-21"
                or event.get("locationUnconfirmed") is not False):
            continue
        required = ("title", "venue", "address", "city", "state", "country",
                    "timezone", "startTime", "endTime", "startDateTime", "endDateTime",
                    "officialUrl")
        if not all(isinstance(event.get(key), str) and event[key].strip() for key in required):
            continue
        if not isinstance(event.get("artists"), list) or "1K Phew" not in event["artists"]:
            continue
        return event
    return None


def location_review_event(event):
    return _location_review_identity(event) and _location_resolution() is None


def resolved_location_event(event):
    return _location_review_identity(event) and _location_resolution() is not None


def public_event(event):
    """Project reviewed facts without mutating historical/provider evidence.

    Provider refreshes may reintroduce the conflicting venue/locality or a new
    provider ID. Keep raw history and the source input intact; sanitize only
    the independent publication copy, using the exact dated identity above.
    """
    result = deepcopy(event)
    if not _location_review_identity(event):
        return result
    # Retained history records this exact booking on November 3. A provider
    # reimport must not restart its seven-day New Shows discovery window.
    first_seen = '2026-11-03T18:56:47Z'
    result['firstSeen'] = min(first_seen, result.get('firstSeen') or first_seen)
    try:
        from .show_information_model import is_private_event
    except ImportError:
        from show_information_model import is_private_event
    if is_private_event(event):
        result["private"] = True
    resolution = _location_resolution()
    if resolution is not None:
        # Remove stale provider geography, clocks and admission claims before
        # overlaying the explicit review. Identity, continuity and status stay
        # attached to the input record; a stale scheduled seed cannot reopen it.
        for field in (
            "venueCity", "address2", "suite", "fullAddress", "latitude", "longitude",
            "lat", "lng", "lon", "geo", "coordinates", "doorsTime", "registrationTime",
            "registrationLocation", "registrationUrl", "primaryTimeKind", "description",
            "admissionRestriction", "ageRestriction", "offers", "offer", "priceAmount",
            "priceCurrency", "ticketStatus",
        ):
            result.pop(field, None)
        fields = (
            "title", "startDate", "endDate", "venue", "address", "city", "state",
            "postalCode", "country", "timezone", "startTime", "endTime", "startDateTime",
            "endDateTime", "artists", "headliner", "advertisedBilling", "officialBill",
            "lineupExplicit", "musicConfirmed", "eventType", "officialUrl", "ticketUrl",
            "ticketUrlVerified", "registrationUrlVerified", "price", "organizer",
            "organizerUrl", "publicDescription", "scheduleNote", "image", "imageType",
            "imagePosition", "imageOverride", "imageSource", "imageSourceUrl", "confidence",
            "locationUnconfirmed", "sourceName", "authority", "lastVerified", "auditVerified",
        )
        for field in fields:
            if field in resolution:
                result[field] = deepcopy(resolution[field])
        if str(event.get("status") or "").casefold() not in {
            "cancelled", "canceled", "postponed", "rescheduled", "private", "merged"
        }:
            result["status"] = resolution.get("status", "scheduled")
        sources = result.setdefault("sources", [])
        if isinstance(sources, list):
            sources.extend(deepcopy(source) for source in resolution.get("sources", [])
                           if source not in sources)
        return result
    result.update({
        "locationUnconfirmed": True,
        "title": "1K Phew — Live performance",
        "officialUrl": "https://www.reachrecords.com/artists/1k-phew/",
        "ticketUrlVerified": False,
        "registrationUrlVerified": False,
        "publicDescription": "1K Phew's official artist calendar lists a performance on November 21, 2026. Location and important show details are not confirmed.",
        "scheduleNote": "Location, venue, start time, admission and ticket details are not confirmed. Check the official artist calendar for updates before making plans.",
    })
    for field in (
        "venue", "venueCity", "city", "state", "address", "address2", "suite",
        "postalCode", "fullAddress", "latitude", "longitude", "lat", "lng", "lon",
        "geo", "coordinates", "timezone", "startTime", "endTime", "startDateTime",
        "endDateTime", "doorsTime", "registrationTime", "registrationLocation",
        "primaryTimeKind", "ticketUrl", "registrationUrl", "description",
    ):
        result[field] = ""
    return result


def removed_event(event):
    if withheld_event(event) or misattributed_event(event):
        return True
    names = [event.get("headliner"), *event.get("artists", []),
             *event.get("advertisedBilling", []), *event.get("officialBill", [])]
    if any(removed_artist(name) for name in names):
        return True
    # Retain the removal even if a stale feed omits the artist association.
    return bool(re.search(r"\b(?:jay[\s_-]*kalyl|propaganda)\b", " ".join(
        str(event.get(key) or "") for key in ("id", "title")), re.I))


def apply(root: Path):
    for relative in ("events.json", "supplemental-events.json", "config/manual-events.json", "event-history.json"):
        path = root / relative
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        rows = data.get("events", []) if isinstance(data, dict) else data
        kept = [entry for entry in rows if not removed_event(entry.get("event", entry))
                or (relative == "event-history.json" and (
                    misattributed_event(entry.get("event", entry))
                    or location_review_event(entry.get("event", entry))))]
        if relative in {"events.json", "supplemental-events.json"}:
            kept = [public_event(entry) for entry in kept]
        if kept == rows:
            continue
        if isinstance(data, dict):
            data["events"] = kept
        else:
            data = kept
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    apply(Path(__file__).resolve().parents[1])
