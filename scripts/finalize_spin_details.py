"""Keep the approved SPIN session split clear after production page overlays."""
from __future__ import annotations

from html import escape
from pathlib import Path
import re

from apply_man_of_faith_joz_shows import EVENTS
from build_seo_site import event_path


def public_path(event: dict) -> str:
    return event_path(dict(event, id='manual:' + event['id']))


def finalize_spin_details(site: Path) -> None:
    events = {e['id']: e for e in EVENTS if e['id'].startswith('spin-awards-')}
    for event in events.values():
        page = site / public_path(event).strip('/') / 'index.html'
        if not page.exists():
            continue
        text = page.read_text()
        # Redirects and archived summaries must retain their existing behavior.
        if 'class="detail-list"' not in text or 'http-equiv="refresh"' in text:
            continue
        text = re.sub(r'<section data-kc-spin-program="true">.*?</section>', '', text, flags=re.S)
        text = re.sub(r'<p data-kc-spin-billing-label="true">.*?</p>', '', text, flags=re.S)
        if event.get('billingLabel'):
            text = text.replace('<p class="artist-line">',
                '<p data-kc-spin-billing-label="true"><strong>' + escape(event['billingLabel']) +
                '</strong></p><p class="artist-line">', 1)
        rows = ''.join('<div><dt>' + escape(row['label']) + '</dt><dd>' + escape(row['text']) +
                       '</dd></div>' for row in event['programSchedule'])
        links = ''.join('<li><a href="' + escape(link['url'], quote=True) +
                        '" target="_blank" rel="noopener">' + escape(link['label']) + '</a></li>'
                        for link in event.get('eventLinks', []))
        related = events[event['relatedEventId']]
        content = '<section data-kc-spin-program="true"><h2>Schedule &amp; admission</h2>'
        content += '<dl class="detail-list">' + rows + '</dl>'
        if event.get('programNote'):
            content += '<p>' + escape(event['programNote']) + '</p>'
        if links:
            content += '<ul>' + links + '</ul>'
        content += '<p><a href="' + public_path(related) + '">' + escape(event['relatedEventLabel']) + '</a></p></section>'
        text, count = re.subn(r'(<dl class="detail-list">.*?</dl>)',
                             lambda match: match.group(1) + content, text, count=1, flags=re.S)
        if count != 1:
            raise ValueError(f'SPIN event details missing: {page}')
        page.write_text(text)
