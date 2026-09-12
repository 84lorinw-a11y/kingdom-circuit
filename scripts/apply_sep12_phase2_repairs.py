#!/usr/bin/env python3
"""Durable phase-2 repairs confirmed by the September 12, 2026 audit."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENT_FILES = (
    ROOT / "events.json",
    ROOT / "supplemental-events.json",
    ROOT / "config" / "manual-events.json",
)

TRUTHX_EVENTBRITE_ID = "1989610293948"
TRUTHX_NOTE = "Official ticket provider lists this event as sold out. Sold out is not a cancellation."

SEVIN_HOGMOB_URL = "https://hogmob.com/sevin-live-concert/"
SEVIN_BROKEN_TICKET_IDS = {
    "1976535062579",  # Kansas City — Sep 26
    "1976535113732",  # Nashville — Oct 24
    "1976534090672",  # Charlotte — Nov 21
    "1976538907078",  # Sacramento — Dec 5
}
SEVIN_NOTE = "HOG MOB confirms the show date; current ticket availability needs confirmation."

ZAUNTEE_MERCURY_ID = "ticketmaster:k7vGF_CBswXt6"
ZAUNTEE_MERCURY_NOTE = "Official venue listing specifies an 18+ age restriction."


def load(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise SystemExit(f"Expected an event array in {path}")
    return value


def save(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_note(event: dict, note: str) -> None:
    current = str(event.get("notes") or "").strip()
    if note not in current:
        event["notes"] = f"{current} {note}".strip()


def is_broken_sevin_ticket(url: object) -> bool:
    text = str(url or "")
    return any(ticket_id in text for ticket_id in SEVIN_BROKEN_TICKET_IDS)


def apply() -> dict[str, int]:
    report = {"truthxSoldOut": 0, "sevinTicketsRemoved": 0, "mercuryAgeRestriction": 0}

    for path in EVENT_FILES:
        rows = load(path)
        changed = False
        for event in rows:
            serialized = json.dumps(event, ensure_ascii=False)

            if TRUTHX_EVENTBRITE_ID in serialized:
                # Sold out remains a scheduled event; never convert it to cancelled.
                if str(event.get("status") or "scheduled").casefold() in {"cancelled", "canceled"}:
                    event["status"] = "scheduled"
                event["soldOut"] = True
                event["ticketAvailability"] = "sold_out"
                append_note(event, TRUTHX_NOTE)
                report["truthxSoldOut"] += 1
                changed = True

            if is_broken_sevin_ticket(event.get("ticketUrl")):
                event["ticketUrl"] = ""
                event["ticketAvailability"] = "needs_confirmation"
                append_note(event, SEVIN_NOTE)
                event["sources"] = [
                    source for source in (event.get("sources") or [])
                    if not (isinstance(source, dict) and is_broken_sevin_ticket(source.get("url")))
                ]
                if not event.get("officialUrl"):
                    event["officialUrl"] = SEVIN_HOGMOB_URL
                report["sevinTicketsRemoved"] += 1
                changed = True

            if event.get("id") == ZAUNTEE_MERCURY_ID:
                event["ageRestriction"] = "18+"
                append_note(event, ZAUNTEE_MERCURY_NOTE)
                report["mercuryAgeRestriction"] += 1
                changed = True

        if changed:
            save(path, rows)

    return report


def check() -> None:
    all_rows: list[dict] = []
    for path in EVENT_FILES:
        all_rows.extend(load(path))

    truthx = [event for event in all_rows if TRUTHX_EVENTBRITE_ID in json.dumps(event, ensure_ascii=False)]
    if truthx:
        for event in truthx:
            if event.get("soldOut") is not True or event.get("ticketAvailability") != "sold_out":
                raise SystemExit("TruthX sold-out state is not durable")
            if str(event.get("status") or "").casefold() in {"cancelled", "canceled"}:
                raise SystemExit("TruthX sold-out state was incorrectly converted to cancellation")

    for event in all_rows:
        if is_broken_sevin_ticket(event.get("ticketUrl")):
            raise SystemExit(f"Broken Sevin Eventbrite ticket URL remains: {event.get('id')}")

    mercury = [event for event in all_rows if event.get("id") == ZAUNTEE_MERCURY_ID]
    if mercury and any(event.get("ageRestriction") != "18+" for event in mercury):
        raise SystemExit("Zauntee Mercury Lounge 18+ restriction is missing")


def main() -> int:
    print(json.dumps(apply(), indent=2))
    check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
