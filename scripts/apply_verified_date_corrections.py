"""Preserve reviewed local dates when a provider reimports UTC day boundaries."""

SCOOTIE_IDS = {"official:0dd5f599b4db080206cf", "scootie-wop-match-houston-2026"}
SCOOTIE_URL = "https://music.apple.com/us/concerts/ce.b01ccaf9-dcf3-44a6-afbf-4bd6d2fc60ae"
SCOOTIE_CANONICAL_ID = "official:0dd5f599b4db080206cf"
SCOOTIE_PROVIDER_ALIAS = "official:1a0b83a961646c580989"
SCOOTIE_DATES = {
    "startDate": "2026-11-14", "endDate": "2026-11-14",
    "startTime": "18:00", "endTime": "22:00",
    "timezone": "America/Chicago",
    "startDateTime": "2026-11-14T18:00:00-06:00",
    "endDateTime": "2026-11-14T22:00:00-06:00",
}


def normalize_provider_identity(event):
    """Keep the published identity after this exact source's UTC/local ID change.

    This does not guess matches for other concerts or change historical records.
    Only the observed provider alias, exact source and reviewed dates qualify.
    """
    if (event.get('id') == SCOOTIE_PROVIDER_ALIAS
            and str(event.get('officialUrl', '')).split('?')[0].rstrip('/') == SCOOTIE_URL
            and event.get('startDate') in {'2026-11-14', '2026-11-15'}):
        event['id'] = SCOOTIE_CANONICAL_ID
        return True
    return False


def patch_event(event):
    identifier = str(event.get("id") or "").removeprefix("manual:")
    urls = {str(event.get(key) or "").split("?")[0].rstrip("/")
            for key in ("officialUrl", "ticketUrl")}
    if identifier not in SCOOTIE_IDS and SCOOTIE_URL not in urls:
        return
    # Do not overwrite a later reschedule. These are the old UTC/local dates
    # for this specific performance, not a rule for other Scootie Wop shows.
    if event.get("startDate") not in {"2026-11-14", "2026-11-15"}:
        return
    event.update(SCOOTIE_DATES)
