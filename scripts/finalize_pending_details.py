"""Label announced shows with incomplete details after imported renderers run."""
import json
import re


def detail_html(document, event):
    document = re.sub(r'(<dt>Status</dt><dd>).*?(</dd>)',
                      r'\1Announced — details pending\2', document, count=1)
    if not event.get("startTime") and "<dt>Time</dt>" not in document:
        document = document.replace('<dt>Venue</dt>',
            '<dt>Time</dt><dd>Pending</dd></div><div><dt>Venue</dt>', 1)

    def schema(match):
        data = json.loads(match[2])

        def clean(value):
            if isinstance(value, list):
                for item in value:
                    clean(item)
            elif isinstance(value, dict):
                if value.get("@type") in ("MusicEvent", "Event"):
                    if not event.get("ticketUrl"):
                        value.pop("offers", None)
                    if not event.get("startTime"):
                        value["startDate"] = event["startDate"]
                    location = value.get("location", {})
                    if event.get("venue") in ("", "Venue pending"):
                        location.pop("name", None)
                for item in value.values():
                    if isinstance(item, (dict, list)):
                        clean(item)

        clean(data)
        return match[1] + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + match[3]

    return re.sub(r'(<script\b[^>]*type="application/ld\+json"[^>]*>)(.*?)(</script>)',
                  schema, document, flags=re.S)


def apply(site):
    from build_seo_site import event_path
    pending = {}
    for name in ("events.json", "supplemental-events.json"):
        path = site / name
        if path.exists():
            for event in json.loads(path.read_text()):
                if event.get("detailsPending") and event.get("status") == "scheduled":
                    pending[event_path(event)] = event
    if not pending:
        return
    badge = '<span class="badge" data-kc-pending-details>Details pending</span>'

    def card(match):
        text = match[0]
        if any(f'href="{path}"' in text for path in pending) and 'data-kc-pending-details' not in text:
            text = text.replace('<div class="event-badges">', '<div class="event-badges">' + badge, 1)
        return text

    for page in site.rglob("*.html"):
        original = page.read_text()
        text = re.sub(r'<article\b[^>]*data-event-card[^>]*>.*?</article>', card, original, flags=re.S)
        path = '/' + str(page.parent.relative_to(site)) + '/'
        if path in pending:
            text = detail_html(text, pending[path])
        if text != original:
            page.write_text(text)
