"""Approved no-show discovery + privacy-conscious analytics, production release.

Every changed production byte is reproduced by the baseline parity gate. Source
artist/event JSON, photography, canonicals and game files remain unchanged.
"""
from __future__ import annotations
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape
import json
from pathlib import Path
import re
from mobile_discovery import Document, replace_spans
from national_discovery import card_records
import shutil
BASE = '/'
MANIFEST = 'assets/artist-engagement-manifest.json'
def source_text(site, relative):
    return (site / relative).read_text()

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ('fan-engagement.js', 'fan-engagement.css',
          'fan-instagram.svg', 'fan-arrow-right.svg', 'fan-arrow-up-right.svg')
FILES = frozenset({f'assets/{n}' for n in ASSETS} | {'assets/fan-show-catalog.json', MANIFEST})
VERSION = '20261024-3'

def context(live, as_of=None):
    shows = []
    for r in card_records(source_text(live, 'shows/index.html')):
        shows.append({'path': r['href'], 'name': r['name'], 'date': r['attrs']['data-date'],
                      'end': r['attrs'].get('data-end-date') or r['attrs']['data-date']})
    artists = {}
    for file in sorted((live / 'artists').glob('*/index.html')):
        doc = Document(file.read_text())
        names = [n for n in doc.nodes if n.attrs.get('id') == 'kc-rd-artist-name']
        if not names:
            continue
        rel = file.relative_to(live).as_posix()
        rows = [n.attrs['href'] for n in doc.nodes if n.has('kc-rd-show-row') and 'href' in n.attrs]
        # The upcoming list excludes rows within the preserved archive.
        listing = doc.one(lambda n: n.has('kc-rd-show-list'))
        rows = [BASE + n.attrs['href'].lstrip('/') for n in doc.nodes
                if n.has('kc-rd-show-row') and listing.start < n.start < listing.end]
        artists[rel] = {'name': doc.text(names[0]), 'shows': rows,
                        'empty': not rows, 'path': BASE + rel.removesuffix('index.html')}
    today = as_of or datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
    return {'asOf': today, 'shows': shows, 'artists': artists,
            'count': sum(s['end'] >= today for s in shows)}

def panel(name, count):
    return f'''<section class="kc-empty-discovery" aria-label="More CHH shows and updates" data-empty-discovery>
<p class="kc-empty-message">No upcoming {escape(name)} shows listed right now.</p>
<div class="kc-empty-actions">
<a class="kc-empty-explore" data-empty-action="explore" href="{BASE}shows/#browse-states"><span><strong>Explore <span data-live-show-count>{count}</span> CHH shows</strong><span>Choose your state</span></span><img src="{BASE}assets/fan-arrow-right.svg" width="24" height="24" alt="" aria-hidden="true"></a>
<a class="kc-empty-instagram" data-empty-action="instagram" href="https://www.instagram.com/thekingdomcircuit/" target="_blank" rel="noopener noreferrer" aria-label="Follow The Kingdom Circuit on Instagram for CHH show updates (opens in new tab)"><img class="kc-empty-instagram-logo" src="{BASE}assets/fan-instagram.svg" width="48" height="48" alt="" aria-hidden="true"><span>Follow for<br>CHH Show Updates</span><img class="kc-empty-outbound" src="{BASE}assets/fan-arrow-up-right.svg" width="24" height="24" alt="" aria-hidden="true"></a>
</div></section>'''

def once(text, old, new):
    assert text.count(old) == 1, f'Instrumentation anchor changed: {old[:90]}'
    return text.replace(old, new, 1)

def transform(relative, data, ctx):
    rel = str(relative)
    if rel == 'app.js':
        text = data.decode()
        start = text.index('function trackArtistInteraction(')
        end = text.index('\nfunction ensureArtistSuggestionDialog', start)
        # A single delegated tracker owns social clicks and server acknowledgments.
        text = text[:start] + '''function trackArtistInteraction(action, artistName = "", platform = "") {
  if (action === "artist_suggestion_open" || action === "artist_jump_select") {
    window.KCFanAnalytics?.track(action, {artist_name: action === "artist_jump_select" ? artistName : "", platform});
  }
}''' + text[end:]
        for old, status in [
            ('if (feedback) feedback.textContent = "Submission received. The Kingdom Circuit will review the information before publishing or updating the event.";', 'success'),
            ('if (feedback) feedback.textContent = "The submission could not be sent. Please try again in a few minutes.";', 'error'),
            ('trackArtistInteraction("artist_suggestion_submit", artistName);', 'success'),
            ('feedback.textContent = "The suggestion could not be sent. Please try again in a few minutes.";', 'error')]:
            text = once(text, old, old + f'\n      form.dispatchEvent(new CustomEvent("kc:submission-result", {{bubbles:true, detail:{{status:"{status}"}}}}));')
        return text.encode()
    if rel == 'assets/artist-intake.js':
        text = data.decode()
        for old, status in [('success.hidden = false;', 'success'),
                            ('status.classList.add("is-error");', 'error')]:
            # Error anchor intentionally appears in HTTP and network-error branches.
            expected = 1 if status == 'success' else 2
            assert text.count(old) == expected
            text = text.replace(old, old + f'\n      form.dispatchEvent(new CustomEvent("kc:submission-result", {{bubbles:true, detail:{{status:"{status}"}}}}));')
        return text.encode()
    if not rel.endswith('.html'):
        return data
    text = data.decode()
    config = {'mode': 'production', 'base': BASE, 'version': VERSION, 'pageType': 'other', 'artist': '', 'show': ''}
    if rel in ctx['artists']:
        artist = ctx['artists'][rel]
        config.update(pageType='artist', artist=artist['name'], showPaths=artist['shows'])
        doc = Document(text)
        changes = []
        if artist['empty']:
            empty = doc.one(lambda n: n.has('kc-rd-profile-empty'))
            changes.append((empty.start, empty.end, panel(artist['name'], ctx['count'])))
            for n in doc.nodes:
                if n.has('kc-rd-next--empty'):
                    changes.append((n.start, n.end, ''))
        text = replace_spans(text, changes)
        text = text.replace('</body>', f'<template id="kc-empty-template">{panel(artist["name"],ctx["count"])}</template></body>')
    elif rel.startswith('event/'):
        doc = Document(text)
        titles = [n for n in doc.nodes if n.tag == 'h1']
        if titles:
            assert len(titles) == 1
            config.update(pageType='show', show=doc.text(titles[0]))
    elif rel.startswith('submit/'):
        config['pageType'] = 'submission'
    elif rel == 'index.html':
        config['pageType'] = 'home'
    elif rel.startswith(('shows/', 'festivals/', 'new-shows/')):
        config['pageType'] = 'show_list'
    elif rel == 'artists/index.html':
        config['pageType'] = 'artist_directory'
    config_json = json.dumps(config, ensure_ascii=True).replace('<','\\u003c')
    head = f'<link rel="stylesheet" href="{BASE}assets/fan-engagement.css?v={VERSION}"><script id="kc-fan-config" type="application/json">{config_json}</script><script defer src="{BASE}assets/fan-engagement.js?v={VERSION}"></script>'
    return once(text, '</head>', head + '</head>').encode()

def generated(ctx):
    result = {f'assets/{n}': (ROOT/'assets'/n).read_bytes() for n in ASSETS}
    catalog = {'asOf':ctx['asOf'], 'shows':ctx['shows']}
    result['assets/fan-show-catalog.json'] = (json.dumps(catalog, separators=(',',':'))+'\n').encode()
    return result

def verify(live, site, ctx):
    for rel, data in generated(ctx).items():
        assert (site/rel).read_bytes() == data, f'Engagement asset drift: {rel}'
    empty = 0
    for rel, artist in ctx['artists'].items():
        before, after = Document(source_text(live, rel)), Document((site/rel).read_text())
        # A template is inert; count only a rendered panel before that template.
        template = after.one(lambda n: n.tag == 'template' and n.attrs.get('id') == 'kc-empty-template')
        panels = [n for n in after.nodes if 'data-empty-discovery' in n.attrs and n.start < template.start]
        assert len(panels) == int(artist['empty']), rel
        empty += bool(panels)
        for cls in ('kc-rd-past-shows','kc-rd-profile-section-title'):
            assert [before.raw(n) for n in before.nodes if n.has(cls)] == [after.raw(n) for n in after.nodes if n.has(cls)], f'{rel}: {cls} changed'
        assert [(n.attrs.get('src'),n.attrs.get('srcset')) for n in before.nodes if n.tag=='img'] == [(n.attrs.get('src'),n.attrs.get('srcset')) for n in after.nodes if n.tag=='img' and 'fan-' not in n.attrs.get('src','')], f'{rel}: photo changed'
    return {'version':VERSION, 'asOf':ctx['asOf'], 'count':ctx['count'], 'artistPages':len(ctx['artists']), 'emptyArtistPages':empty, 'analyticsDestination':'existing-production-Google-Analytics'}

def verify_release(site, baseline):
    metadata=json.loads((site/MANIFEST).read_text())
    ctx=context(baseline,metadata['asOf'])
    before={p.relative_to(baseline) for p in baseline.rglob('*') if p.is_file()}
    after={p.relative_to(site) for p in site.rglob('*') if p.is_file()}
    assert before <= after, 'Original files disappeared'
    assert {str(p) for p in after-before} <= FILES, 'Unexpected public files'
    for rel in before:
        expected=transform(rel,(baseline/rel).read_bytes(),ctx)
        assert (site/rel).read_bytes()==expected, f'Unapproved difference: {rel}'
    result=verify(baseline,site,ctx)
    for rel in ctx['artists']:
        text=(site/rel).read_text()
        assert 'G-N2KK9XF4TJ' in text, f'Existing Google tag missing: {rel}'
        assert '/kingdom-circuit-test/' not in text and 'G-NBY8D9JSDH' not in text
    assert (site/'CNAME').read_text().strip()=='kingdomcircuit.com'
    result.update(originalFilesPreserved=len(before),productionIdentityVerified=True)
    return result

def build(site, baseline):
    assert not baseline.exists(), 'Refusing to overwrite release baseline'
    assert not (site/MANIFEST).exists(), 'Engagement already applied'
    shutil.copytree(site,baseline)
    ctx=context(baseline)
    for file in baseline.rglob('*'):
        if not file.is_file():continue
        rel=file.relative_to(baseline)
        if rel.suffix=='.html' or str(rel) in ('app.js','assets/artist-intake.js'):
            (site/rel).write_bytes(transform(rel,file.read_bytes(),ctx))
    for rel,data in generated(ctx).items():
        out=site/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
    info=verify(baseline,site,ctx)
    (site/MANIFEST).write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(verify_release(site,baseline),indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('site',type=Path);parser.add_argument('baseline',type=Path);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();site=args.site.resolve();baseline=args.baseline.resolve()
    assert site!=baseline and site not in baseline.parents and baseline not in site.parents
    if args.check: print(json.dumps(verify_release(site,baseline),indent=2))
    else: build(site,baseline)
