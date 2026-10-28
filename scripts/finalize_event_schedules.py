"""Keep source-verified admission and performance schedules visible after overlays."""
from html import escape
import json
import re


def apply(site):
    from build_seo_site import event_path
    schedules = {}
    for name in ('events.json', 'supplemental-events.json'):
        source = site / name
        if source.exists():
            for event in json.loads(source.read_text()):
                if event.get('scheduleDetails'):
                    schedules[event_path(event)] = event
    for path, event in schedules.items():
        page = site / path.strip('/') / 'index.html'
        if not page.exists():
            continue
        original = page.read_text()
        if 'http-equiv="refresh"' in original or 'class="detail-list"' not in original:
            continue
        document = re.sub(r'<section data-kc-event-schedule>.*?</section>', '', original, flags=re.S)
        rows = ''.join('<div><dt>' + escape(row['label']) + '</dt><dd>' +
                       escape(row['text']) + '</dd></div>' for row in event['scheduleDetails'])
        content = '<section data-kc-event-schedule><h2>Schedule &amp; admission</h2>'
        content += '<dl class="detail-list">' + rows + '</dl>'
        if event.get('scheduleNote'):
            content += '<p>' + escape(event['scheduleNote']) + '</p>'
        content += '</section>'
        document, count = re.subn(r'(<dl class="detail-list">.*?</dl>)',
                                 lambda m: m[0] + content, document, count=1, flags=re.S)
        if count != 1:
            raise ValueError(f'Event schedule could not be displayed: {path}')
        if document != original:
            page.write_text(document)
