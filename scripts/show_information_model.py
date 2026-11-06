"""Normalize collected show facts for the production renderer and schema.

``normalize(event)`` returns an independent copy of the source record. Original
fields survive, except private street/postal addresses and the public description
are sanitized. Consumers should use the derived fields below for publication:

* ``private``, ``soldOut``: explicit admission/availability facts.
* ``description``: publicDescription or description only; never editorial notes.
* ``officialDestination``: {url, label: "Official details", kind} or None.
  kind is tickets, registration, or details. This is also the sole Offer URL.
* ``offer``: a schema.org Offer or None. Private, cancelled, postponed and merged
  records have no offer. Only confirmed direct admission destinations qualify.
* ``schemaStartDate`` / ``schemaEndDate``: ISO dates or known local datetimes,
  with confirmed offsets when available; never invent a timezone.
  Raw time fields are retained for compatibility; use these derived schema values.
* ``venueLocality``: confirmed venue municipality, falling back to market city.
  The original ``city`` remains unchanged for catalog identity and URLs.
* Optional display strings: dateLabel, startTimeLabel, doorsTimeLabel,
  registrationTimeLabel, endTimeLabel, timezoneLabel, priceLabel, organizerName,
  organizerUrl, admissionLabel. Unknown optional values are absent.
* Optional entity links: venueUrl, venueInstagram, organizerWebsite,
  organizerInstagram and eventInstagram. Profile links are Instagram accounts,
  not posts; website labels never point at a ticket-platform/social profile.
  performerInstagrams is derived only when the current artist registry is passed.

Curated URL flags are exact booleans: ticketUrlVerified/registrationUrlVerified.
Known direct ticket-platform event paths may qualify without a flag. Generic
home, artist, social, music and Bandsintown information URLs do not autoqualify.
Structured price is {amount, currency, ticketType?, label?,
includesAllFeesConfirmed?}; only an explicitly confirmed total with currency is
put in Offer. Legacy price strings remain display-only. No network calls occur.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timezone, timedelta
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_PRIVATE = re.compile(r"\b(?:private\s+event|invite[\s-]*only|invitation[\s-]*only|not\s+open\s+to\s+the\s+public)\b", re.I)
PRIVATE_ADDRESS_FIELDS = ('address', 'address2', 'suite', 'postalCode', 'fullAddress')
_UNKNOWN_FACT = {'tbd', 'tba', 'unknown', 'not confirmed', 'not provided', 'to be announced',
                 'to be determined', 'venue not confirmed', 'venue not provided',
                 'venue to be announced', 'venue to be determined',
                 'address not confirmed', 'address not provided'}
_DERIVED = (
    "dateLabel", "startTimeLabel", "doorsTimeLabel", "registrationTimeLabel",
    "endTimeLabel", "timezoneLabel", "priceLabel", "organizerName",
    "organizerUrl", "admissionLabel", "schemaStartDate", "schemaEndDate", "venueLabel", "venueLocality",
    "venueUrl", "venueInstagram", "organizerWebsite", "organizerInstagram",
    "eventInstagram", "performerInstagrams",
)


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def is_private_event(event):
    """Use the same explicit admission rules for HTML, schema and public feeds."""
    return event.get("private") is True or any(_text(event.get(key)).casefold() == "private"
        for key in ("status", "admission", "admissionRestriction")) or any(_PRIVATE.search(_text(event.get(key)))
        for key in ("status", "admission", "admissionRestriction", "title", "venue", "ageRestriction"))


def _url(value):
    value = _text(value)
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"https", "http"} or not parsed.hostname
                or parsed.username or parsed.password or any(c.isspace() for c in value)):
            return ""
        return value
    except ValueError:
        return ""


def _host(value):
    return (urlsplit(value).hostname or "").lower().removeprefix("www.")


def _social_or_music(url):
    host = _host(url)
    return any(host == domain or host.endswith("." + domain) for domain in (
        "instagram.com", "facebook.com", "tiktok.com", "twitter.com", "x.com",
        "youtube.com", "youtu.be", "spotify.com", "music.apple.com",
        "soundcloud.com", "linktr.ee",
    ))


def _instagram_profile(value):
    url = _url(value)
    if not url or _host(url) != 'instagram.com':
        return ''
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError:
        return ''
    if port not in (None, 443, 80):
        return ''
    match = re.fullmatch(r'/([A-Za-z0-9._]{1,30})/?', parsed.path)
    if not match or match[1].casefold() in {
            'p', 'reel', 'reels', 'tv', 'stories', 'accounts', 'explore',
            'direct', 'about', 'legal', 'directory', 'developer', 'challenge'}:
        return ''
    return 'https://www.instagram.com/' + match[1].lower() + '/'


def _entity_website(value):
    url = _url(value)
    if not url or _social_or_music(url):
        return ''
    host = _host(url)
    if re.search(r'(?:^|\.)(?:eventbrite|ticketmaster|livenation|bandsintown|'
                 r'tickettailor|ticketweb|tixr|axs|etix|ticketsource|eventim|'
                 r'showclix|dice|prekindle|stubwire|ticketleap|universe|'
                 r'humanitix|ticketspice|brushfire)\.', host):
        return ''
    return url


def _performer_instagrams(event, artists):
    lookup = {}
    for artist in artists:
        if not isinstance(artist, dict) or artist.get('enabled') is False:
            continue
        name = _text(artist.get('name'))
        if not name:
            continue
        url = _instagram_profile(artist.get('instagramProfile'))
        aliases = artist.get('aliases') if isinstance(artist.get('aliases'), list) else []
        for alias in [name, *aliases]:
            alias = ' '.join(_text(alias).casefold().split())
            if alias:
                lookup.setdefault(alias, set()).add((name, url))
    result, seen = [], set()
    billed = event.get('artists') or []
    if isinstance(billed, str):
        billed = [billed]
    for name in billed:
        if isinstance(name, dict):
            name = name.get('name')
        candidates = lookup.get(' '.join(_text(name).casefold().split()), set())
        if len(candidates) != 1:
            continue
        canonical, url = next(iter(candidates))
        if url and (canonical, url) not in seen:
            result.append({'name': canonical, 'url': url})
            seen.add((canonical, url))
    return result


def _direct_ticket_platform(url):
    """Recognize event paths, never a whole platform or artist profile."""
    host = _host(url)
    path = urlsplit(url).path.rstrip("/")
    patterns = (
        (r"eventbrite\.(?:com|ca|co\.uk)", r"/e/(?:[^/]+-tickets-)?\d+$"),
        (r"(?:ticketmaster\.(?:com|ca|co\.uk)|(?:concerts\.)?livenation\.com)", r"/(?:[^/]+/)?event/[A-Za-z0-9]+(?:/[^/]+)?$"),
        (r"tickettailor\.com", r"/events/[^/]+/\d+(?:/[^/]+)?$"),
        (r"tickettailor\.com", r"/checkout/view-event/id/\d+/chk/[A-Za-z0-9]+$"),
        (r"brushfire\.com", r"/[^/]+/[^/]+/\d+$"),
        (r"ticketweb\.(?:com|ca|uk)", r"/event/[^/]+/\d+$"),
        (r"posh\.vip", r"/e/[^/]+$"),
        (r"axs\.com", r"/events/\d+(?:/[^/]+)*$"),
        (r"tixr\.com", r"/groups/[^/]+/events/[^/]+$"),
        (r"etix\.com", r"/ticket/p/\d+(?:/[^/]+)*$"),
        (r"ticketsource\.(?:com|co\.uk)", r"/.+/e-[A-Za-z0-9]+$"),
        (r"eventim\.com", r"/event/[^/]+-\d+$"),
        (r"(?:wl\.)?eventim\.us", r"/event/[^/]+/\d+$"),
        (r"showclix\.com", r"/event/[^/]+$"),
        (r"dice\.fm", r"/(?:partner/tickets/)?event/[^/]+$"),
        (r"prekindle\.com", r"/event/\d+-[^/]+$"),
        (r"stubwire\.com", r"/e/\d+(?:/[^/]+)*$"),
        (r"events\.ticketleap\.com", r"/tickets/[^/]+/[^/]+$"),
        (r"universe\.com", r"/events/[^/]+-tickets-[A-Za-z0-9]+$"),
        (r"events\.humanitix\.com", r"/[^/]+(?:/tickets)?$"),
        (r"[^.]+\.ticketspice\.com", r"/[^/]+$"),
        # Reviewed November 5, 2026: this dedicated official event root opens
        # the registration selector, including the $15 Shai concert-only pass.
        (r"ready27\.events\.mbts\.edu", r"(?:/registration/select)?$"),
    )
    return any(re.fullmatch(domain, host) and re.fullmatch(event_path, path)
               for domain, event_path in patterns)


def _destination(event):
    for key, flag, kind in (
        ("ticketUrl", "ticketUrlVerified", "tickets"),
        ("registrationUrl", "registrationUrlVerified", "registration"),
    ):
        url = _url(event.get(key))
        if url and event.get(flag) is not False and not _social_or_music(url) and (
            event.get(flag) is True or _direct_ticket_platform(url)
        ):
            return {"url": url, "label": "Official details", "kind": kind}
    for key in ("officialUrl", "ticketUrl", "registrationUrl"):
        url = _url(event.get(key))
        if url:
            # A canonical official link can itself be the event's ticket page.
            # Explicit negative verification still wins over platform detection.
            kind = "tickets" if (key == "officialUrl" and _direct_ticket_platform(url)
                                 and event.get("ticketUrlVerified") is not False) else "details"
            return {"url": url, "label": "Official details", "kind": kind}
    return None


def _date(value):
    raw = _text(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _clock(value):
    raw = _text(value)
    if not re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", raw):
        return None
    try:
        parts = [int(part) for part in raw.split(":")]
        return time(*parts)
    except ValueError:
        return None


def _datetime(value):
    raw = _text(value)
    if "T" not in raw and " " not in raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _zone(value):
    try:
        return ZoneInfo(_text(value)) if _text(value) else None
    except (ZoneInfoNotFoundError, ValueError):
        return None


def _localize(value, zone):
    """Do not choose an offset for an ambiguous or nonexistent local clock."""
    # The province ended the November fallback in 2026. Host databases can
    # lag the rule or use a Mountain abbreviation; the Vancouver region now
    # remains UTC-7. Other B.C. IANA regions retain their own rules.
    if getattr(zone, 'key', '') == 'America/Vancouver' and value.date() >= date(2026, 11, 1):
        return value.replace(tzinfo=timezone(timedelta(hours=-7), 'PT'))
    # Alberta adopted permanent UTC-6 (ABT) on November 1, 2026.
    # https://www.alberta.ca/albertas-new-time-system-abt
    if getattr(zone, 'key', '') == 'America/Edmonton' and value.date() >= date(2026, 11, 1):
        return value.replace(tzinfo=timezone(timedelta(hours=-6), 'ABT'))
    candidates = []
    for fold in (0, 1):
        aware = value.replace(tzinfo=zone, fold=fold)
        roundtrip = aware.astimezone(timezone.utc).astimezone(zone)
        if roundtrip.replace(tzinfo=None) == value:
            candidates.append(aware)
    offsets = {candidate.utcoffset() for candidate in candidates}
    return candidates[0] if len(offsets) == 1 else None


def _temporal(event, prefix, zone, fallback_date=None):
    explicit = _datetime(event.get(prefix + "DateTime"))
    day = _date(event.get(prefix + "Date"))
    clock = _clock(event.get(prefix + "Time"))
    if explicit:
        if explicit.utcoffset() is not None:
            # Explicit source clock and offset are already verified together.
            # Do not let a host's timezone database shift that published clock.
            return explicit.date(), explicit.time(), explicit
        day, clock = explicit.date(), explicit.time()
    day = day or fallback_date
    aware = _localize(datetime.combine(day, clock), zone) if day and clock and zone else None
    return day, clock, aware


def _time_label(value):
    return f"{value.hour % 12 or 12}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"


def _date_label(value):
    return f"{value:%a, %b} {value.day}, {value.year}"


def _timezone_label(aware, zone):
    if (getattr(zone, 'key', '') == 'America/Edmonton'
            and aware.date() >= date(2026, 11, 1)
            and aware.utcoffset() == timedelta(hours=-6)):
        return 'ABT'
    # B.C. names its permanent UTC-7 zone Pacific time from November 2026.
    # Some system tzdata versions abbreviate Vancouver as MST after the change.
    # Keep the verified offset, but use the province's published regional name.
    # https://news.gov.bc.ca/releases/2026AG0013-000209
    if (getattr(zone, 'key', '') == 'America/Vancouver'
            and aware.date() >= date(2026, 11, 1)
            and aware.utcoffset() is not None
            and aware.utcoffset().total_seconds() == -7 * 3600):
        return 'PT'
    if zone:
        local = _localize(aware.replace(tzinfo=None), zone)
        if local and local.utcoffset() == aware.utcoffset():
            return local.tzname()
    # Fixed-offset ISO timestamps have a truthful numeric UTC label when a
    # location's IANA abbreviation cannot be verified against that offset.
    return aware.tzname()


def _schema_datetime(day, clock, aware, zone):
    if aware:
        return aware.isoformat()
    # Google can resolve a supplied local clock from the event location when
    # no timezone is supplied. Preserve that known time without guessing an
    # offset. A known zone's ambiguous/nonexistent DST clock remains date-only.
    if clock and zone is None:
        return datetime.combine(day, clock).isoformat()
    return day.isoformat()


def _amount(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        amount = Decimal(str(value))
        return amount if amount.is_finite() and amount >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def _price(event):
    value = event.get("price")
    if isinstance(value, str):
        return value.strip(), {}
    if not isinstance(value, dict):
        return "", {}
    amount = _amount(value.get("amount"))
    currency = _text(value.get("currency")).upper()
    currency = currency if re.fullmatch(r"[A-Z]{3}", currency) else ""
    ticket_type = _text(value.get("ticketType"))
    label = _text(value.get("label"))
    if not label and amount is not None and currency:
        number = format(amount, "f").rstrip("0").rstrip(".") if "." in format(amount, "f") else format(amount, "f")
        label = f"{ticket_type + ': ' if ticket_type else ''}{number} {currency}"
    offer = {"name": ticket_type} if ticket_type else {}
    if value.get("includesAllFeesConfirmed") is True and amount is not None and currency:
        offer.update(price=int(amount) if amount == amount.to_integral_value() else float(amount),
                     priceCurrency=currency)
    return label, offer


def normalize(event, *, artists=()):
    """Return source facts and safe publication fields without mutating input."""
    try:
        from .catalog_removals import public_event
    except ImportError:
        from catalog_removals import public_event
    event = public_event(event)
    result = deepcopy(event)
    for key in _DERIVED:
        result.pop(key, None)
    # Missing facts have presentation labels, never literal placeholder values
    # in Event location/address fields. Exact reviewed overrides also identify
    # tour names that were incorrectly occupying the venue slot.
    venue = _text(event.get("venue"))
    title = _text(event.get("title"))
    reviewed_placeholder = _text(event.get("unconfirmedVenueValue"))
    # The established production SEO finalizer removes event titles used as
    # location names. Keep that protection in the shared visible/schema model.
    title_placeholder = bool(venue and title and ' '.join(venue.casefold().split()) == ' '.join(title.casefold().split()))
    if (reviewed_placeholder and venue.casefold() == reviewed_placeholder.casefold()) or venue.casefold() in _UNKNOWN_FACT or title_placeholder:
        venue = ""
    result["venue"] = venue
    result["venueLabel"] = venue or "Venue not confirmed"
    venue_city = _text(event.get('venueCity'))
    result['venueLocality'] = (venue_city if venue_city.casefold() not in _UNKNOWN_FACT else '') or _text(event.get('city'))
    for field in ('address', 'address2', 'suite', 'postalCode'):
        if _text(result.get(field)).casefold() in _UNKNOWN_FACT:
            result[field] = ''
    status = _text(event.get("status")).casefold().replace("-", "_").replace(" ", "_")
    private = is_private_event(event)
    result["private"] = bool(private)
    if private:
        for field in PRIVATE_ADDRESS_FIELDS:
            result[field] = ""
    description = _text(event.get("publicDescription")) or _text(event.get("description"))
    if description:
        result["description"] = description
    else:
        result.pop("description", None)

    destination = _destination(event)
    result["officialDestination"] = destination
    sold_out = event.get("soldOut") is True or _text(event.get("ticketAvailability")).casefold() in {"sold_out", "sold out", "soldout"} or status in {"sold_out", "soldout"}
    result["soldOut"] = sold_out
    label, price_fields = _price(event)
    if label:
        result["priceLabel"] = label
    result["offer"] = None
    if (destination and destination["kind"] != "details" and not private and not result.get("locationUnconfirmed")
            and status not in {"cancelled", "canceled", "postponed", "merged"}):
        result["offer"] = {"@type": "Offer", "url": destination["url"], **price_fields}
        if sold_out:
            result["offer"]["availability"] = "https://schema.org/SoldOut"

    zone = _zone(event.get("timezone"))
    start_day, start_clock, start = _temporal(event, "start", zone)
    end_day, end_clock, end = _temporal(event, "end", zone, start_day if event.get("endTime") else None)
    # An earlier end clock does not establish an overnight date. Keep the known
    # clock visible, but do not fabricate tomorrow (or an impossible schema end).
    if start and end:
        # Explicit offsets disambiguate repeated clocks during a DST fallback.
        # Compare instants, including when both datetimes share one ZoneInfo.
        invalid_end = end.astimezone(timezone.utc) < start.astimezone(timezone.utc)
    else:
        invalid_end = bool(start_day and end_day and (end_day < start_day or (
            end_day == start_day and start_clock and end_clock and end_clock < start_clock)))
    if start_day:
        result["schemaStartDate"] = _schema_datetime(start_day, start_clock, start, zone)
        result["dateLabel"] = _date_label(start_day)
        if end_day and end_day > start_day:
            result["dateLabel"] += " – " + _date_label(end_day)
    if end_day and not invalid_end and (event.get("endDate") or event.get("endDateTime") or event.get("endTime") or end):
        result["schemaEndDate"] = _schema_datetime(end_day, end_clock, end, zone)
    for key, clock in (("startTimeLabel", start_clock), ("endTimeLabel", end_clock),
                       ("doorsTimeLabel", _clock(event.get("doorsTime"))),
                       ("registrationTimeLabel", _clock(event.get("registrationTime")))):
        if clock:
            result[key] = _time_label(clock)
    if start:
        result["timezoneLabel"] = _timezone_label(start, zone)
    elif zone:
        result["timezoneLabel"] = zone.key
    # Date rows retain the actual clock time. Each secondary time carries its
    # own known zone; never silently render a naive datetime as UTC.
    for field in ('startTimeLabel', 'doorsTimeLabel', 'registrationTimeLabel', 'endTimeLabel'):
        if field not in result:
            continue
        reference = end if field == 'endTimeLabel' else start
        if zone and start_day and field in ('doorsTimeLabel', 'registrationTimeLabel'):
            # Doors and registration can precede a timezone transition on the
            # show date. Ambiguous/nonexistent clocks must not inherit an offset.
            clock = _clock(event.get('doorsTime' if field == 'doorsTimeLabel' else 'registrationTime'))
            reference = _localize(datetime.combine(start_day, clock), zone) if clock else None
        if reference:
            result[field] += ' ' + _timezone_label(reference, zone)
        elif zone:
            result[field] += ' (' + zone.key + ')'
    if result.get('dateLabel') and result.get('startTimeLabel'):
        result['dateLabel'] += ' - ' + result['startTimeLabel']
    elif result.get('dateLabel') and event.get('primaryTimeKind') == 'doors' and result.get('doorsTimeLabel'):
        # A useful confirmed arrival time stays explicitly doors, not a
        # performance start or a date-time supplied to Google.
        result['dateLabel'] += ' - Doors ' + result['doorsTimeLabel']

    organizer = event.get("organizer")
    if isinstance(organizer, dict):
        if _text(organizer.get("name")):
            result["organizerName"] = organizer["name"].strip()
            if _url(organizer.get("url")):
                result["organizerUrl"] = _url(organizer["url"])
    elif _text(organizer):
        result["organizerName"] = organizer.strip()
    # Some verified production records store the organizer as flat fields.
    # Prefer the canonical organizer, and never attach a legacy URL to it.
    if "organizerName" not in result and _text(event.get("organizerName")):
        result["organizerName"] = _text(event["organizerName"])
        if _url(event.get("organizerUrl")):
            result["organizerUrl"] = _url(event["organizerUrl"])
    if venue:
        for field, clean in (('venueUrl', _entity_website), ('venueInstagram', _instagram_profile)):
            if value := clean(event.get(field)):
                result[field] = value
    if result.get('organizerName'):
        website = _entity_website(event.get('organizerWebsite')) or _entity_website(result.get('organizerUrl'))
        if website:
            result['organizerWebsite'] = website
        social = (organizer.get('instagramProfile') or organizer.get('instagram')) if isinstance(organizer, dict) else None
        social = _instagram_profile(social or event.get('organizerInstagram'))
        if social:
            result['organizerInstagram'] = social
    if social := _instagram_profile(event.get('eventInstagram')):
        result['eventInstagram'] = social
    if performers := _performer_instagrams(event, artists):
        result['performerInstagrams'] = performers
    admission = _text(event.get("admissionRestriction")) or _text(event.get("ageRestriction"))
    if private:
        admission = "Private / invite-only event"
    if admission:
        result["admissionLabel"] = admission
    return result
