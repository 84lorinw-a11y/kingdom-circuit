"""Connect published historical pages without changing current event facts."""
import datetime as dt
import calendar
from collections import defaultdict
import json
from html import escape
import re
from pathlib import Path
from urllib.parse import urlsplit
from mobile_discovery import Document, replace_spans

ARCHIVE = '/shows/archive/'
MARKER = 'data-show-history-links'


def connect(root, site, state, history, today):
    from url_continuity import PageFacts, ORIGIN, target_file, norm
    from build_seo_site import artist_path, city_path, state_path, STATE_NAMES
    from location_navigation import public_cards
    all_shows = site / 'shows/index.html'
    if not all_shows.is_file():
        return {'events': 0, 'months': 0}
    current = set(public_cards(all_shows.read_text()))
    pages = {}
    for file in site.rglob('index.html'):
        path = '/' + file.parent.relative_to(site).as_posix().strip('./') + '/'
        if path == '//': path = '/'
        text = file.read_text(); facts = PageFacts(text)
        if facts.canonical == ORIGIN + path and not facts.refresh:
            pages[path] = (file, text, facts)
    records = {record['path']: history.get(key, record['event'])
               for key, record in state.get('events', {}).items()}
    roster = json.loads((root / 'config/artists.json').read_text()) if (root / 'config/artists.json').is_file() else []
    artists = {norm(a.get('name')): a['name'] for a in roster if a.get('name') and a.get('enabled') is not False}
    archived = []
    for path, (file, text, facts) in pages.items():
        if not path.startswith('/event/') or path in current or 'noindex' in facts.robots:
            continue
        event = records.get(path, {})
        if norm(event.get('status')) == 'private' or re.search(r'Private event\. Not open|invite[ -]only', text, re.I):
            continue
        status = norm(event.get('status'))
        date = str(event.get('startDate') or '')
        if status in {'cancelled', 'canceled'}: label = 'Cancelled'
        elif status == 'postponed': label = 'Postponed'
        elif re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) and date < today: label = 'Past show'
        else: label = 'Previously listed, confirm status'
        title = facts.h1 or event.get('title') or facts.title
        archived.append((date, path, title, label))
        links = [(ARCHIVE, 'Show archive')]
        for name in event.get('artists', []):
            known = artists.get(norm(name))
            if known: links.append((artist_path(known), known + ' shows'))
        region = str(event.get('state') or '')
        city = str(event.get('city') or '')
        if city and region and not event.get('locationUnconfirmed'):
            links.append((city_path(city, region), city + ' shows'))
        if region and not event.get('locationUnconfirmed'):
            links.append((state_path(region), STATE_NAMES.get(region, region) + ' shows'))
        links = list(dict.fromkeys((target, label) for target, label in links
                                 if target == ARCHIVE or target in pages))
        # The current published record determines identity. Never infer from URL dates.
        block = '<nav data-show-history-links aria-label="Related show calendars"><h2>Keep exploring</h2><p>'
        block += ' · '.join(f'<a href="{target}">{escape(label)}</a>' for target, label in links)
        block += '</p></nav>'
        text = replace_block(text, block)
        file.write_text(text)
    months = [(path, facts.h1 or facts.title) for path, (_, _, facts) in pages.items()
              if re.fullmatch(r'/shows/(?:january|february|march|april|may|june|july|august|september|october|november|december)-\d{4}/', path)
              and 'noindex' not in facts.robots
              and dt.date(int(path.strip('/').split('-')[-1]), list(calendar.month_name).index(path.split('/')[2].split('-')[0].title()), 1).isoformat() < today[:7] + '-01']
    if not archived and not months:
        return {'events': 0, 'months': 0}
    body = '<main id="kc-main-content" class="kc-show-archive"><section class="page-hero hero-compact"><p><a href="/shows/">All Shows</a></p><h1>Show archive</h1><p>Previously listed shows and monthly calendars. These are historical records, not the current upcoming calendar.</p></section>'
    if months:
        body += '<section><h2>Monthly calendars</h2><p>' + ' · '.join(f'<a href="{path}">{escape(path.split("/")[2].replace("-", " " ).title())}</a>' for path, title in sorted(months, key=lambda row: dt.datetime.strptime(row[0].split('/')[2], '%B-%Y'), reverse=True)) + '</p></section>'
    body += '<section><h2>Previously listed shows</h2>'
    groups = defaultdict(list)
    for item in sorted(archived, reverse=True):
        date = item[0]
        key = date[:7] if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) and date < today else 'Status updates'
        groups[key].append(item)
    for key in sorted(groups, reverse=True):
        label = dt.date.fromisoformat(key + '-01').strftime('%B %Y') if re.fullmatch(r'\d{4}-\d{2}',key) else key
        body += f'<details><summary>{escape(label)} · {len(groups[key])} listings</summary><ul>'
        for date, path, title, label in groups[key]:
            display_date = dt.date.fromisoformat(date).strftime('%B %-d, %Y') if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) else ''
            detail = (display_date + ' · ' if display_date else '') + label
            body += f'<li><a href="{path}">{escape(title)}</a><br><small>{escape(detail)}</small></li>'
        body += '</ul></details>'
    body += '</section><p><a href="/shows/">Browse upcoming shows</a></p></main>'
    doc = Document(all_shows.read_text()); changes = []
    for n in doc.nodes:
        if n.tag == 'main': changes.append((n.start, n.end, body))
        elif n.tag == 'title': changes.append((n.opening_end, n.closing_start, 'Show archive | Kingdom Circuit'))
        elif n.tag == 'link' and n.attrs.get('rel') == 'canonical': changes.append((n.start, n.end, f'<link rel="canonical" href="{ORIGIN + ARCHIVE}">'))
        elif n.tag == 'script' and n.attrs.get('type') == 'application/ld+json': changes.append((n.start,n.end,''))
        elif n.tag == 'meta' and (n.attrs.get('name') == 'description' or n.attrs.get('property') in {'og:title','og:description','og:url'} or n.attrs.get('name') in {'twitter:title','twitter:description'}):
            key = 'property' if 'property' in n.attrs else 'name'; name = n.attrs[key]
            value = ORIGIN + ARCHIVE if name == 'og:url' else 'Show archive | Kingdom Circuit' if name.endswith('title') else 'Browse previously listed Kingdom Circuit shows and monthly calendars.'
            changes.append((n.start,n.end,f'<meta {key}="{name}" content="{escape(value, quote=True)}">'))
    archive_text = replace_spans(doc.source, changes)
    archive_style = '<style>.kc-show-archive{max-width:960px;margin:auto;padding:24px 16px}.kc-show-archive section{margin-bottom:24px}.kc-show-archive details{border-top:1px solid #39332e}.kc-show-archive summary{padding:14px 0;cursor:pointer;font-weight:600}.kc-show-archive li{margin:16px 0;overflow-wrap:anywhere}.kc-show-archive a:focus-visible{outline:2px solid #ef9988;outline-offset:4px}</style>'
    archive_text = archive_text.replace('</head>', archive_style + '</head>', 1)
    file = target_file(site, ARCHIVE); file.parent.mkdir(parents=True,exist_ok=True);file.write_text(archive_text)
    for path in ['/shows/', *[p for p, _ in months]]:
        file = target_file(site, path)
        block = '<nav data-show-history-links aria-label="Show history"><p><a href="/shows/archive/">Show archive</a> · <a href="/shows/">Upcoming shows</a></p></nav>'
        file.write_text(replace_block(file.read_text(), block))
    return {'events':len(archived), 'months':len(months)}


def replace_block(text, block):
    text = re.sub(r'<nav\b[^>]*data-show-history-links[^>]*>.*?</nav>', '', text, flags=re.S)
    return text.replace('</main>', block + '</main>', 1)
