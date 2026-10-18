"""Show prominent sold-out notices only for explicitly reviewed, full events.

Run after the final discovery layout so both its compact cards and the standard
event cards retain the notice. Official artwork bytes stay unchanged.
"""
import argparse
import json
from pathlib import Path
import shutil

from build_seo_site import event_path
from mobile_discovery import Document, replace_spans

ROOT = Path(__file__).resolve().parents[1]
CSS = 'assets/sold-out-artwork.css'
LINK = f'<link rel="stylesheet" href="/{CSS}?v=1">'
BANNER = '<span class="kc-sold-out-banner">SOLD OUT</span>'
BADGE = '<span class="badge kc-sold-out-label">Sold out</span>'


def reviewed_events(site):
    events = {}
    for filename in ('events.json', 'supplemental-events.json'):
        for row in json.loads((site / filename).read_text()):
            if row.get('soldOut') is True and row.get('prominentSoldOut') is True:
                assert row.get('soldOutSourceUrl'), 'Sold-out announcement source required'
                events[event_path(row)] = row
    return events


def transform(text, own_path, events):
    doc = Document(text)
    edits = []
    for node in doc.nodes:
        detail = node.has('event-detail-media') and own_path in events
        card = (node.has('event-media') or node.has('kc-teaser-image')) and node.attrs.get('href') in events
        if (detail or card) and 'data-sold-out-artwork' not in node.attrs:
            edits.append((node.opening_end - 1, node.opening_end - 1, ' data-sold-out-artwork'))
            edits.append((node.closing_start, node.closing_start, BANNER))
        if node.has('event-card') or node.has('kc-discovery-show'):
            links = [n.attrs.get('href') for n in doc.nodes if n.tag == 'a' and node.start < n.start < node.end]
            if not any(link in events for link in links) or 'kc-sold-out-label' in doc.raw(node):
                continue
            # Image links can be aria-hidden; keep a readable status in the copy too.
            copy = next(n for n in doc.nodes if node.start < n.start < node.end
                        and (n.has('event-content') or n.has('kc-teaser-copy')))
            edits.append((copy.opening_end, copy.opening_end, BADGE))
        if node.has('event-detail-copy') and own_path in events and 'kc-sold-out-notice' not in doc.raw(node):
            edits.append((node.opening_end, node.opening_end,
                          '<p class="kc-sold-out-notice"><strong>SOLD OUT</strong> — Registration is closed.</p>'))
    if edits and LINK not in text:
        head = doc.one(lambda n: n.tag == 'head')
        edits.append((head.closing_start, head.closing_start, LINK))
    return replace_spans(text, edits)


def apply(site):
    events = reviewed_events(site)
    changed = 0
    for page in site.rglob('*.html'):
        path = '/' + page.relative_to(site).as_posix().removesuffix('index.html')
        original = page.read_text()
        result = transform(original, path, events)
        if original != result:
            page.write_text(result)
            changed += 1
    if events:
        shutil.copyfile(ROOT / CSS, site / CSS)
    verify(site, events)
    return {'reviewedSoldOutEvents': len(events), 'pagesUpdated': changed}


def verify(site, events):
    for path, event in events.items():
        page = (site / path.lstrip('/') / 'index.html').read_text()
        assert 'data-sold-out-artwork' in page and 'kc-sold-out-notice' in page, path
        assert 'https://schema.org/SoldOut' in page, path
        assert (site / CSS).is_file()
    for file in site.rglob('*.html'):
        relative = file.relative_to(site).as_posix()
        text = file.read_text()
        if any(path in text for path in events):
            assert transform(text, '/' + relative.removesuffix('index.html'), events) == text, relative


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('site', type=Path)
    args = parser.parse_args()
    print(json.dumps(apply(args.site)))
