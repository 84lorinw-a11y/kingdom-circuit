"""Preserve reviewed local dates and the confirmed Scootie Wop reschedule."""
import copy

SCOOTIE_MANUAL_ID = "scootie-wop-match-houston-2026"
SCOOTIE_URL = "https://music.apple.com/us/concerts/ce.b01ccaf9-dcf3-44a6-afbf-4bd6d2fc60ae"
SCOOTIE_CANONICAL_ID = "official:0dd5f599b4db080206cf"
SCOOTIE_PROVIDER_ALIAS = "official:1a0b83a961646c580989"
SCOOTIE_IDS = {SCOOTIE_CANONICAL_ID, SCOOTIE_MANUAL_ID, SCOOTIE_PROVIDER_ALIAS}
SCOOTIE_RESCHEDULE_URL = "https://www.instagram.com/p/DfTOHOODGjO/"
SCOOTIE_REVIEWED_DATES = {"2026-11-14", "2026-11-15", "2027-05-01"}
# Retain the original UTC/local parsing fixture independently of the new date.
SCOOTIE_DATES = {
    "startDate": "2026-11-14", "endDate": "2026-11-14",
    "startTime": "18:00", "endTime": "22:00",
    "timezone": "America/Chicago",
    "startDateTime": "2026-11-14T18:00:00-06:00",
    "endDateTime": "2026-11-14T22:00:00-06:00",
}
SCOOTIE_RESCHEDULE_DATES = {
    "startDate": "2027-05-01", "endDate": "2027-05-01",
    "startTime": "18:00", "endTime": "22:00",
    "timezone": "America/Chicago",
    "startDateTime": "2027-05-01T18:00:00-05:00",
    "endDateTime": "2027-05-01T22:00:00-05:00",
}


def normalize_provider_identity(event):
    """Keep the published identity for exact provider and manual reimports.

    This does not guess matches for other concerts or change historical records.
    Only the known aliases, exact sources and reviewed dates qualify.
    """
    if (event.get('id') in {SCOOTIE_PROVIDER_ALIAS, 'manual:' + SCOOTIE_MANUAL_ID}
            and str(event.get('officialUrl', '')).split('?')[0].rstrip('/')
                in {SCOOTIE_URL, SCOOTIE_RESCHEDULE_URL.rstrip('/')}
            and event.get('startDate') in SCOOTIE_REVIEWED_DATES):
        event['id'] = SCOOTIE_CANONICAL_ID
        return True
    return False


def patch_event(event):
    identifier = str(event.get("id") or "").removeprefix("manual:")
    urls = {str(event.get(key) or "").split("?")[0].rstrip("/")
            for key in ("officialUrl", "ticketUrl")}
    if identifier not in SCOOTIE_IDS and not urls & {SCOOTIE_URL, SCOOTIE_RESCHEDULE_URL.rstrip('/')}:
        return
    # Bound the repair to the superseded UTC/local dates and confirmed new date.
    # A different future move still requires review.
    if event.get("startDate") not in SCOOTIE_REVIEWED_DATES:
        return
    event.update(SCOOTIE_RESCHEDULE_DATES)
    if event.get("status") not in {"cancelled", "canceled", "postponed", "merged"}:
        event["status"] = "rescheduled"
    event.update(previousStartDate="2026-11-14", officialUrl=SCOOTIE_RESCHEDULE_URL,
                 sourceName="APTITUDE official reschedule announcement", auditVerified="2026-11-04",
                 publicDescription="Rescheduled from November 14, 2026 to May 1, 2027. Existing tickets remain valid.")
    event["firstSeen"] = min(event.get("firstSeen") or "2026-08-09T00:00:00Z", "2026-08-09T00:00:00Z")
    source = {"name": "APTITUDE official reschedule announcement", "url": SCOOTIE_RESCHEDULE_URL,
              "type": "manual_verified", "authority": "organizer", "priority": 115}
    event["sources"] = [source] + [row for row in event.get("sources", [])
                                   if row.get("url") != SCOOTIE_RESCHEDULE_URL]


def reconcile_scootie_duplicates(rows):
    """Coalesce simultaneous known reimports without changing the published row."""
    from build_seo_site import event_path, norm

    matches = []
    for index, row in enumerate(rows):
        normalized = copy.deepcopy(row)
        normalize_provider_identity(normalized)
        if (normalized.get('id') == SCOOTIE_CANONICAL_ID
                and normalized.get('startDate') in SCOOTIE_REVIEWED_DATES):
            matches.append((index, row))
    if len(matches) < 2:
        return
    venues = {'match midtown arts & theater center houston',
              'match - midtown arts and theater center houston'}
    for _, row in matches:
        if (norm(row.get('city')) != 'houston' or norm(row.get('state')) != 'tx'
                or {norm(a) for a in row.get('artists', [])} != {'scootie wop'}
                or norm(row.get('venue')) not in venues
                or row.get('startTime') not in (None, '', '18:00')):
            raise ValueError('Scootie Wop duplicate conflicts with the reviewed MATCH performance')
    # The saved public snapshot uses the canonical Apple-provider record.
    # Prefer it even when a manual/provider alias is earlier in the input feed.
    chosen = max((row for _, row in matches), key=lambda row: (
        row.get('id') == SCOOTIE_CANONICAL_ID,
        row.get('ticketUrl') == SCOOTIE_URL))
    wanted = copy.deepcopy(chosen)
    normalize_provider_identity(wanted)
    patch_event(wanted)
    wanted['firstSeen'] = min([wanted['firstSeen']] + [
        row['firstSeen'] for _, row in matches if row.get('firstSeen')])
    for field in ('sources', 'legacyEventPaths', 'mergedFromIds'):
        values = wanted.setdefault(field, [])
        for _, row in matches:
            for value in row.get(field, []):
                if value not in values:
                    values.append(copy.deepcopy(value))
    for _, row in matches:
        # A provider ticket link can be absent from its sources list.
        for field in ('officialUrl', 'ticketUrl'):
            url = row.get(field)
            if url and not any(source.get('url') == url for source in wanted['sources']):
                wanted['sources'].append({'name': 'Retained ' + field,
                                          'url': url, 'type': 'retained_reference'})
        old_path = event_path(row)
        if old_path != event_path(wanted) and old_path not in wanted['legacyEventPaths']:
            wanted['legacyEventPaths'].append(old_path)
        old_id = row['id']
        if old_id != SCOOTIE_CANONICAL_ID and old_id not in wanted['mergedFromIds']:
            wanted['mergedFromIds'].append(old_id)
        if row.get('status') in {'cancelled', 'canceled', 'postponed'}:
            wanted['status'] = row['status']
    indexes = {index for index, _ in matches}
    first = matches[0][0]
    rows[:] = [wanted if index == first else row
               for index, row in enumerate(rows) if index == first or index not in indexes]
