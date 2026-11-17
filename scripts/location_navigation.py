"""Production location navigation over the current verified build.

No event, artist, historical URL, image, date or source record is rewritten.
Promoted structure only. Inputs are the current production build, never test data.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from html import escape, unescape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from mobile_discovery import Document, replace_spans
import hashlib
SITE_BASE = '/'
SITE_ORIGIN = 'https://kingdomcircuit.com'

ROOT = Path(__file__).resolve().parents[1]
VERSION = '20261116-3'
FILES = frozenset({'shows/states/index.html', 'shows/cities/index.html',
                   'assets/location-navigation.css', 'assets/location-navigation.js',
                   'assets/location-navigation-data.json'})
ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 12h14m-6-6 6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>'
SEARCH = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="m16 16 5 5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'
NEARBY = [('orlando-florida','kissimmee-florida'), ('dallas-texas','arlington-texas'),
          ('dallas-texas','fort-worth-texas'), ('phoenix-arizona','mesa-arizona'),
          ('detroit-michigan','belleville-michigan'), ('fort-lauderdale-florida','north-lauderdale-florida')]
CANADIAN_REGIONS = {'Alberta', 'British Columbia', 'Manitoba', 'New Brunswick',
                    'Newfoundland and Labrador', 'Nova Scotia', 'Ontario',
                    'Prince Edward Island', 'Quebec', 'Saskatchewan',
                    'Northwest Territories', 'Nunavut', 'Yukon'}

def country_of(region):
    return 'CA' if region['name'] in CANADIAN_REGIONS else 'US'

def path_of(href):
    path = urlsplit(href).path
    return '/' + path.removeprefix(SITE_BASE).lstrip('/') if path.startswith(SITE_BASE) else path

def href(path):
    return SITE_BASE + path.lstrip('/')

def public_cards(text):
    doc = Document(text)
    records = {}
    for n in doc.nodes:
        if 'data-event-card' not in n.attrs: continue
        part = Document(doc.raw(n))
        heading = next((x for x in part.nodes if x.tag == 'h3'), None)
        if heading is None: continue
        anchor = next((x for x in part.nodes if x.tag == 'a' and heading.start < x.start < heading.end), None)
        if anchor is None: continue
        material = ' '.join(part.text(x) for x in part.nodes if x.has('event-badges')) + ' ' + part.text(heading)
        if re.search(r'private|invite[\s-]?only|cancelled|canceled|postponed', material, re.I): continue
        meta = {}
        for row in (x for x in part.nodes if x.tag == 'div'):
            dt = next((x for x in row.children if x.tag == 'dt'), None)
            dd = next((x for x in row.children if x.tag == 'dd'), None)
            if dt and dd: meta[part.text(dt)] = part.text(dd)
        records[path_of(anchor.attrs['href'])] = {'location':meta.get('Location',''), 'state':n.attrs.get('data-state','')}
    return records

def breadcrumbs(text):
    for value in re.findall(r'<script\b[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', text, re.S):
        obj=json.loads(value)
        if isinstance(obj,dict) and obj.get('@type')=='BreadcrumbList': return obj.get('itemListElement',[])
    return []

def context(live):
    # The final published All Shows calendar already owns expiry and deduplication.
    public = public_cards((live/'shows/index.html').read_text())
    doc=Document((live/'shows/index.html').read_text())
    permanent=doc.one(lambda n:'data-permanent-state-navigation' in n.attrs or (n.tag=='nav' and n.has('kc-state-links') and 'state' in n.attrs.get('aria-label','')))
    regions={}
    for n in doc.nodes:
        if n.tag=='a' and permanent.start<n.start<permanent.end:
            path=path_of(n.attrs['href'])
            label=next((doc.text(child) for child in n.children if child.tag=='span'),doc.text(n))
            regions[path]={'path':path,'name':label,'cities':[]}
    cities={}; locations={}
    for file in sorted((live/'shows').glob('*/index.html')):
        path='/'+file.parent.relative_to(live).as_posix()+'/'
        text=file.read_text();crumb=breadcrumbs(text)
        if path not in regions and not (len(crumb)==3 and path_of(crumb[-1].get('item',''))==path and path_of(crumb[-2].get('item','')) in regions):continue
        members=set(public_cards(text))&set(public)
        if path in regions:
            regions[path].update(count=len(members),events=sorted(members),
                                 codes=sorted({public[event]['state'] for event in members if public[event]['state']}))
        else:
            parent=path_of(crumb[-2]['item'])
            city={'path':path,'name':crumb[-1]['name'],'region':parent,'count':len(members),'events':sorted(members)}
            cities[path]=city
            if members:
                regions[parent]['cities'].append(path)
                for event in members:
                    label=public[event]['location']
                    if label in locations and locations[label]!=path:raise ValueError('Ambiguous city label: '+label)
                    locations[label]=path
    for region in regions.values():
        assert 'count' in region,region
        region['cities'].sort(key=lambda p:(-cities[p]['count'],cities[p]['name']))
    assert regions and cities and public
    template=(live/'about-us/index.html').read_text()
    template_doc=Document(template)
    actions=template_doc.one(lambda n:n.has('kc-rd-actions'))
    ctx={'regions':regions,'cities':cities,'locations':locations,'publicCount':len(public),'template':template,'headerActions':template_doc.raw(actions)}
    ctx['generated']=generate(ctx)
    return ctx

def count_label(n):return f'{n} show'+('' if n==1 else 's')

def location_link(row, cls='kc-location-row', secondary=None):
    sub = secondary if secondary is not None else (count_label(row['count'])+' upcoming' if row['count'] else 'No upcoming shows listed')
    return (f'<a class="{cls}" href="{href(row["path"])}" data-location-entry data-search="{escape(row["name"].casefold(),quote=True)}">'
            f'<span><strong>{escape(row["name"])}</strong><small>{escape(sub)}</small></span>{ARROW}</a>')

def quick_links(ctx):
    top=sorted((c for c in ctx['cities'].values() if c['count']),key=lambda c:(-c['count'],c['name']))[:4]
    links=''.join(f'<a href="{href(c["path"])}">{escape(c["name"])}</a>' for c in top)
    return (f'<section class="kc-location-start" aria-label="Browse shows by location">'
            f'<div class="kc-location-start-actions"><a href="{href("/shows/states/")}"><span>Browse states</span>{ARROW}</a>'
            f'<a href="{href("/shows/cities/")}"><span>Browse cities</span>{ARROW}</a></div>'
            f'<nav class="kc-location-shortcuts" aria-label="Cities with the most upcoming shows">{links}</nav></section>')

def nav(active):
    items=[('All Shows','/shows/'),('States','/shows/states/'),('Cities','/shows/cities/'),('Artists','/artists/'),('Festivals','/festivals/')]
    return '<nav class="kc-location-nav" aria-label="Primary navigation">'+''.join(
        f'<a href="{href(path)}"'+(' aria-current="page"' if path==active else '')+f'>{label}</a>' for label,path in items)+'</nav>'

def menu():
    return (f'<details class="kc-location-menu"><summary aria-label="More navigation"><span>Menu</span>'
            '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M5 12h14M5 17h14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg></summary>'
            f'<nav aria-label="More navigation"><a href="{SITE_BASE}">Home</a><a href="{href("/about-us/")}">About Us</a>'
            f'<a href="{href("/submit/")}">Submit a Show</a><a href="{href("/shows/this-weekend/")}">This Weekend</a>'
            f'<a href="{href("/shows/this-month/")}">This Month</a><a href="{href("/new-shows/")}">New Shows</a></nav></details>')

def transform(relative,data,ctx):
    rel=str(relative)
    if rel=='sitemap.xml':
        text=data.decode()
        for route in ['shows/states/','shows/cities/']:
            url=SITE_ORIGIN+'/'+route
            if '<loc>'+url+'</loc>' not in text:text=text.replace('</urlset>','<url><loc>'+url+'</loc></url></urlset>')
        return text.encode()
    if not rel.endswith('.html'):return data
    text=data.decode()
    if 'class="kc-rd-header' not in text:return data
    if 'data-location-navigation-version=' in text:return data
    doc=Document(text);changes=[]
    path='/' if rel=='index.html' else '/'+rel.removesuffix('index.html')
    active='/shows/cities/' if path in ctx['cities'] or path=='/shows/cities/' else '/shows/states/' if path in ctx['regions'] or path=='/shows/states/' else '/artists/' if path.startswith('/artists/') else '/festivals/' if path.startswith('/festivals/') else '/shows/' if path.startswith(('/shows/','/new-shows/','/event/')) or path=='/' else ''
    header=doc.one(lambda n:n.tag=='header' and n.has('kc-rd-header'))
    hdoc=Document(doc.raw(header));hc=[]
    oldnav=[n for n in hdoc.nodes if n.tag=='nav' and n.has('kc-rd-nav')]
    for n in oldnav:hc.append((n.start,n.end,nav(active)))
    if not oldnav:
        root=hdoc.one(lambda n:n.tag=='header' and n.has('kc-rd-header'));hc.append((root.closing_start,root.closing_start,nav(active)))
    primary=hdoc.one(lambda n:n.has('kc-rd-primary'))
    extras=(ctx.get('headerActions','') if not any(n.has('kc-rd-actions') for n in hdoc.nodes) else '')+menu()
    hc.append((primary.closing_start,primary.closing_start,extras))
    head=replace_spans(hdoc.source,hc).replace('class="kc-rd-header','data-location-navigation-version="'+VERSION+'" class="kc-rd-header',1)
    changes.append((header.start,header.end,head))
    for n in doc.nodes:
        if n.has('footer-links'):
            links=''.join(f'<a href="{href(p)}">{label}</a>' for label,p in [('All Shows','/shows/'),('States','/shows/states/'),('Cities','/shows/cities/'),('Artists','/artists/'),('Festivals','/festivals/'),('About Us','/about-us/'),('Submit a Show','/submit/')])
            changes.append((n.opening_end,n.closing_start,links))
    if rel=='index.html':
        hero=doc.one(lambda n:n.tag=='section' and n.has('kc-discovery-hero'))
        changes.append((hero.end,hero.end,quick_links(ctx)))
    if path in ctx['regions']:
        region=ctx['regions'][path];old=[n for n in doc.nodes if n.tag=='section' and (n.has('kc-city-links') or (n.has('seo-location-strip') and 'Browse cities' in doc.raw(n)))]
        children=[ctx['cities'][c] for c in region['cities']]
        block=(f'<section class="kc-location-related" aria-label="Cities in {escape(region["name"])}"><div class="kc-location-section-heading"><h2>Cities in {escape(region["name"])}</h2><a href="{href("/shows/cities/")}">All cities</a></div><div class="kc-location-related-links">'+''.join(location_link(c,secondary=count_label(c['count'])) for c in children)+'</div></section>') if children else ''
        if old:changes.append((old[0].start,old[0].end,block))
        elif block:
            calendar=doc.one(lambda n:n.tag=='section' and n.has('calendar'));changes.append((calendar.end,calendar.end,block))
    if path in ctx['cities']:
        city=ctx['cities'][path];region=ctx['regions'][city['region']]
        near={('/shows/'+b+'/') for a,b in NEARBY if path=='/shows/'+a+'/'}|{('/shows/'+a+'/') for a,b in NEARBY if path=='/shows/'+b+'/'}
        nearby=[ctx['cities'][p] for p in sorted(near) if p in ctx['cities'] and ctx['cities'][p]['count']]
        choices=nearby or [ctx['cities'][p] for p in region['cities'] if p!=path][:3]
        title='Nearby cities' if nearby else 'More cities in '+region['name']
        if choices:
            block=f'<section class="kc-location-related" aria-label="{escape(title)}"><div class="kc-location-section-heading"><h2>{escape(title)}</h2><a href="{href(city["region"])}">All {escape(region["name"])} shows</a></div><div class="kc-location-related-links">'+''.join(location_link(c,secondary=count_label(c['count'])) for c in choices)+'</div></section>'
            calendar=doc.one(lambda n:n.tag=='section' and n.has('calendar'));changes.append((calendar.end,calendar.end,block))
    if path in ['/shows/','/shows/this-weekend/','/shows/this-month/','/new-shows/']:
        hero=next((n for n in doc.nodes if n.tag=='section' and n.has('page-hero')),None)
        if hero:
            shortcuts=[('All dates','/shows/'),('This Weekend','/shows/this-weekend/'),('This Month','/shows/this-month/'),('New Shows','/new-shows/')]
            block='<nav class="kc-location-dates" aria-label="Show calendars">'+''.join(f'<a href="{href(p)}"'+(' aria-current="page"' if p==path else '')+f'>{label}</a>' for label,p in shortcuts)+'</nav>'
            changes.append((hero.end,hero.end,block))
    # Full event detail addresses retain the shared verified facts renderer.
    # Link city fields on cards, never a venue that happens to equal a city.
    location_values = {child.start for row in doc.nodes
                       if any(child.tag == 'dt' and doc.text(child) == 'Location' for child in row.children)
                       for child in row.children if child.tag == 'dd'}
    detail_sections = [n for n in doc.nodes if n.has('event-detail-copy')]
    for n in doc.nodes:
        if n.start in location_values or n.has('kc-teaser-location'):
            if any(section.start < n.start < section.end for section in detail_sections):
                continue
            value=doc.text(n)
            if value in ctx['locations'] and not n.children:
                if not any(start<=n.start<end for start,end,_ in changes) and not any(a.start<n.start<a.end for a in doc.nodes if 'data-past-shows-archive' in a.attrs):
                    changes.append((n.opening_end,n.closing_start,f'<a class="kc-location-inline" href="{href(ctx["locations"][value])}">{text[n.opening_end:n.closing_start]}</a>'))
    text=replace_spans(text,changes)
    assets=f'<link rel="stylesheet" href="{SITE_BASE}assets/location-navigation.css?v={VERSION}"><script src="{SITE_BASE}assets/location-navigation.js?v={VERSION}" defer></script>'
    # The show facts verifier keeps its stylesheet last in the head.
    # Insert navigation before that stable layer so its idempotence gate holds.
    marker = '<link data-kc-show-information '
    insertion = text.find(marker)
    if insertion >= 0:
        return (text[:insertion] + assets + text[insertion:]).encode()
    return text.replace('</head>',assets+'</head>',1).encode()

def featured_locations(ctx, kind):
    is_city = kind == 'cities'
    rows = ctx['cities'].values() if is_city else ctx['regions'].values()
    return sorted((r for r in rows if r['count'] > 0),
                  key=lambda r: (-r['count'], r['name'].casefold(), r['path']))[:10]

def featured_section(ctx, kind):
    rows = featured_locations(ctx, kind)
    if not rows:
        return ''
    cards = ''
    for row in rows:
        region = f'<small>{escape(ctx["regions"][row["region"]]["name"])}</small>' if kind == 'cities' else ''
        cards += (f'<a class="kc-featured-card" href="{href(row["path"])}" data-featured-location '
                  f'data-show-count="{row["count"]}"><span class="kc-featured-place">{region}'
                  f'<strong>{escape(row["name"])}</strong></span><span class="kc-featured-bottom"><span>{count_label(row["count"])}</span>{ARROW}</span></a>')
    return (f'<section class="kc-featured-locations" aria-labelledby="most-shows-{kind}"><div class="kc-featured-heading"><div>'
            f'<h2 id="most-shows-{kind}">{kind.title()} with the most shows</h2></div>'
            f'<a class="kc-featured-view-all" href="#all-locations">View all {ARROW}</a></div>'
            f'<div class="kc-featured-rail" id="featured-{kind}" data-featured-rail aria-label="{kind.title()} with the most shows">{cards}</div>'
            f'<div class="kc-featured-controls" data-featured-controls hidden><span>Swipe to explore</span><div>'
            f'<button type="button" data-featured-prev aria-label="Previous {kind}" aria-controls="featured-{kind}">{ARROW}</button>'
            f'<button type="button" data-featured-next aria-label="Next {kind}" aria-controls="featured-{kind}">{ARROW}</button></div></div></section>')

def directory(ctx,kind):
    is_city=kind=='cities';regions=sorted((r for r in ctx['regions'].values() if r['count']),key=lambda r:r['name'])
    cities=[c for c in ctx['cities'].values() if c['count']]
    title='CHH shows by city' if is_city else 'CHH shows by state'
    desc=('Browse upcoming CHH concerts by city. Find local shows and open the full city calendar.' if is_city else
          'Browse upcoming CHH concerts by state and province. Find local shows and open the full calendar.')
    options='<option value="">All regions</option>'+''.join(f'<option value="{escape(href(r["path"]))}" data-country="{country_of(r)}" data-codes="{escape(" ".join(r.get("codes", [])),quote=True)}">{escape(r["name"])}</option>' for r in regions)
    city_options='<option value="">All cities</option>'+''.join(f'<option value="{escape(href(c["path"]))}" data-region="{escape(href(c["region"]))}" data-country="{country_of(ctx["regions"][c["region"]])}">{escape(c["name"]+", "+ctx["regions"][c["region"]]["name"])}</option>' for c in sorted(cities,key=lambda c:(c['name'].casefold(),c['path'])))
    search=f'<form class="kc-location-filters" role="search" aria-label="Find a location" data-location-filters hidden><label class="kc-location-search"><span>Search</span><div>{SEARCH}<input type="search" placeholder="Name" data-location-search autocomplete="off" spellcheck="false" enterkeyhint="search" aria-controls="all-locations"></div></label>'
    search+=f'<label><span>City</span><select data-location-city>{city_options}</select></label>'
    search+=f'<label><span>State or province</span><select data-location-region>{options}</select></label>'
    search+='<label><span>Country</span><select data-location-country><option value="">All countries</option><option value="US">United States</option><option value="CA">Canada</option></select></label>'
    search+='</form>'
    groups=''
    if is_city:
        letters=defaultdict(list)
        for c in sorted(cities,key=lambda c:(c['name'].casefold(),ctx['regions'][c['region']]['name'])):
            letters[c['name'][0].upper()].append(c)
        for letter, entries in letters.items():
            links=''
            for c in entries:
                region=ctx['regions'][c['region']]['name']
                search_text=' '.join([c['name'],region,*ctx['regions'][c['region']].get('codes',[])]).casefold()
                links+=(f'<a class="kc-city-list-row" href="{href(c["path"])}" data-location-entry data-search="{escape(search_text,quote=True)}" '
                        f'data-region="{escape(href(c["region"]),quote=True)}" data-city="{escape(href(c["path"]),quote=True)}" data-country="{country_of(ctx["regions"][c["region"]])}"><span class="kc-city-list-place"><strong>{escape(c["name"])}</strong><small>{escape(region)}</small></span>'
                        f'<span class="kc-city-list-count"><strong>{c["count"]}</strong><small>{"show" if c["count"]==1 else "shows"}</small></span>{ARROW}</a>')
            groups+=f'<section class="kc-city-letter-group" data-location-group aria-label="Cities starting with {escape(letter)}"><h3>{escape(letter)}</h3><div class="kc-city-list">{links}</div></section>'
    else:
        entries=[]
        for r in regions:
            entry=location_link(r)
            # A state search also matches its public cities without altering statewide counts.
            names=' '.join([r['name'],*r.get('codes',[]),*(ctx['cities'][p]['name'] for p in r['cities'])]).casefold()
            entry=re.sub(r'data-search="[^"]*"',f'data-search="{escape(names,quote=True)}" data-region="{href(r["path"])}" data-country="{country_of(r)}"',entry,count=1)
            entries.append(entry)
        groups='<div class="kc-location-state-grid" data-location-group>'+''.join(entries)+'</div>'
    total=len(cities) if is_city else len(regions)
    label='cities with upcoming shows' if is_city else 'states and provinces with upcoming shows'
    all_title = 'All cities' if is_city else 'All states and provinces'
    body=(f'<main id="kc-main-content" class="kc-location-directory" data-location-directory data-location-kind="{kind}">'
          f'<nav class="kc-location-breadcrumb" aria-label="Breadcrumb"><a href="{SITE_BASE}">Home</a><span aria-hidden="true">/</span><span aria-current="page">{kind.title()}</span></nav>'
          f'<header class="kc-location-hero"><h1>{title}</h1></header>{search}{featured_section(ctx,kind)}'
          f'<section class="kc-all-locations" id="all-locations" aria-labelledby="all-locations-heading"><h2 id="all-locations-heading" tabindex="-1">{all_title}</h2>'
          f'<div class="kc-location-results-meta"><p class="kc-location-result-count" role="status" aria-live="polite" data-location-count>{total} {label}</p>'
          '<button type="button" class="kc-location-clear" data-location-clear hidden>Clear filters</button></div>'
          f'<div class="kc-location-groups">{groups}</div><div class="kc-location-empty" data-location-empty hidden><h3>No matching locations</h3>'
          '<p>Try another name or clear your filters.</p></div></section><p class="kc-location-note">Counts include public upcoming shows.</p></main>')
    template=ctx['template'];doc=Document(template);main=doc.one(lambda n:n.tag=='main')
    changes=[(main.start,main.end,body)]
    url=SITE_ORIGIN+'/shows/'+kind+'/'
    for n in doc.nodes:
        if n.tag=='title':changes.append((n.opening_end,n.closing_start,escape(title+' | Kingdom Circuit')))
        if n.tag=='link' and n.attrs.get('rel')=='canonical':changes.append((n.start,n.end,f'<link rel="canonical" href="{url}">'))
        if n.tag=='meta' and n.attrs.get('name')=='description':changes.append((n.start,n.end,f'<meta name="description" content="{desc}">'))
        if n.tag=='meta' and n.attrs.get('name') in ['twitter:title','twitter:description']:
            val=title+' | Kingdom Circuit' if n.attrs['name']=='twitter:title' else desc
            changes.append((n.start,n.end,f'<meta name="{n.attrs["name"]}" content="{escape(val,quote=True)}">'))
        if n.tag=='meta' and n.attrs.get('property') in ['og:title','og:description','og:url']:
            val={'og:title':title+' | Kingdom Circuit','og:description':desc,'og:url':url}[n.attrs['property']]
            changes.append((n.start,n.end,f'<meta property="{n.attrs["property"]}" content="{escape(val,quote=True)}">'))
        if n.tag=='script' and n.attrs.get('type')=='application/ld+json':changes.append((n.start,n.end,''))
    page=replace_spans(template,changes)
    page=re.sub(r'<body\b[^>]*>','<body class="kc-location-directory-body">',page,count=1)
    items=cities if is_city else regions
    schema={'@context':'https://schema.org','@graph':[{'@type':'CollectionPage','name':title,'url':url,'description':desc},{'@type':'BreadcrumbList','itemListElement':[{'@type':'ListItem','position':1,'name':'Home','item':SITE_ORIGIN+'/'},{'@type':'ListItem','position':2,'name':kind.title(),'item':url}]},{'@type':'ItemList','itemListElement':[{'@type':'ListItem','position':i+1,'name':r['name'],'url':SITE_ORIGIN+r['path']} for i,r in enumerate(sorted(items,key=lambda r:r['name']))]}]}
    page=page.replace('</head>','<script type="application/ld+json">'+json.dumps(schema).replace('<','\\u003c')+'</script></head>',1)
    return transform('shows/'+kind+'/index.html',page.encode(),ctx)

def generate(ctx):
    return {**{f'assets/location-navigation.{ext}':(ROOT/f'assets/location-navigation.{ext}').read_bytes() for ext in ['css','js']},
            'assets/location-navigation-data.json':json.dumps({'locations':{k:href(v) for k,v in ctx['locations'].items()}},ensure_ascii=False).encode(),
            'shows/states/index.html':directory(ctx,'states'),'shows/cities/index.html':directory(ctx,'cities')}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def html_facts(text):
    """Independent facts that navigation must never change on existing pages."""
    doc = Document(text)
    facts = []
    for node in doc.nodes:
        if (node.tag in ('title', 'img') or
            (node.tag == 'meta' and node.attrs.get('name') in ('robots', 'description')) or
            (node.tag == 'link' and node.attrs.get('rel') == 'canonical') or
            (node.tag == 'script' and node.attrs.get('type') == 'application/ld+json')):
            facts.append(doc.raw(node))
    cards = []
    for node in doc.nodes:
        if 'data-event-card' in node.attrs:
            cards.append(re.sub(r'<a class="kc-location-inline"[^>]*>(.*?)</a>', r'\1', doc.raw(node), flags=re.S))
    return facts, cards


def snapshot(site, baseline):
    """Copy HTML only; hash all data and images without duplicating large media."""
    assert not baseline.exists(), 'Refusing to overwrite the release baseline'
    assert baseline != site and baseline not in site.parents and site not in baseline.parents
    baseline.mkdir(parents=True)
    hashes = {}
    for path in sorted(site.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(site)
        raw = path.read_bytes()
        hashes[rel.as_posix()] = digest(raw)
        if path.suffix == '.html' or rel.as_posix() == 'sitemap.xml':
            target = baseline / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    (baseline / 'structure-source-hashes.json').write_text(json.dumps(hashes, sort_keys=True))


def verify_current(site):
    """Check actual final pages after URL retention and sitemap finalization."""
    ctx = context(site)
    sitemap = (site / 'sitemap.xml').read_text()
    verified_locations = 0
    for kind in ('states', 'cities'):
        rel = f'shows/{kind}/index.html'
        text = (site / rel).read_text()
        doc = Document(text)
        canonical = SITE_ORIGIN + '/shows/' + kind + '/'
        assert doc.one(lambda n: n.tag == 'link' and n.attrs.get('rel') == 'canonical').attrs['href'] == canonical
        assert 'noindex' not in doc.one(lambda n: n.tag == 'meta' and n.attrs.get('name') == 'robots').attrs['content']
        assert 'G-N2KK9XF4TJ' in text, f'Production analytics absent: {rel}'
        assert '<loc>' + canonical + '</loc>' in sitemap, f'Directory absent from sitemap: {kind}'
        assert len([n for n in doc.nodes if n.tag == 'h1']) == 1
        assert all(value not in text for value in ('/kingdom-circuit-test/', '84lorinw-a11y.github.io', 'G-TESTDISABLED'))
        rows = ctx['cities'] if kind == 'cities' else ctx['regions']
        expected = {r['path']: r for r in rows.values() if r['count'] > 0}
        entries = [n for n in doc.nodes if 'data-location-entry' in n.attrs]
        assert len(entries) == len(expected)
        assert {path_of(n.attrs['href']) for n in entries} == set(expected)
        for node in entries:
            row = expected[path_of(node.attrs['href'])]
            if kind == 'cities':
                part = Document(doc.raw(node))
                count = part.one(lambda n: n.has('kc-city-list-count'))
                assert part.text(count) == str(row['count']) + ('show' if row['count'] == 1 else 'shows')
            else:
                assert count_label(row['count']) + ' upcoming' in doc.text(node)
            assert (site / row['path'].strip('/') / 'index.html').is_file()
        featured = [n for n in doc.nodes if 'data-featured-location' in n.attrs]
        expected_featured = featured_locations(ctx, kind)
        assert [path_of(n.attrs['href']) for n in featured] == [r['path'] for r in expected_featured]
        assert [int(n.attrs['data-show-count']) for n in featured] == [r['count'] for r in expected_featured]
        schemas = [json.loads(doc.raw(n).split('>', 1)[1].rsplit('</script>', 1)[0]) for n in doc.nodes
                   if n.tag == 'script' and n.attrs.get('type') == 'application/ld+json']
        schema_items = [obj for graph in schemas for obj in graph.get('@graph', [graph]) if obj.get('@type') == 'ItemList']
        assert len(schema_items) == 1
        assert {x['url'] for x in schema_items[0]['itemListElement']} == {SITE_ORIGIN + p for p in expected}
        assert not re.search(r'"@type":\s*"(?:MusicEvent|Event|Offer)"', text)
        verified_locations += len(entries)
    province_links = 0
    city_connections = 0
    for path, region in ctx['regions'].items():
        doc = Document((site / path.strip('/') / 'index.html').read_text())
        links = {n.attrs.get('href') for n in doc.nodes if n.tag == 'a'}
        assert all(href(child) in links for child in region['cities']), region['name']
        if country_of(region) == 'CA':
            province_links += len(region['cities'])
    for path, city in ctx['cities'].items():
        if not city['count']:
            continue
        doc = Document((site / path.strip('/') / 'index.html').read_text())
        near = {'/shows/' + b + '/' for a, b in NEARBY if path == '/shows/' + a + '/'} | {'/shows/' + a + '/' for a, b in NEARBY if path == '/shows/' + b + '/'}
        expected = [p for p in sorted(near) if p in ctx['cities'] and ctx['cities'][p]['count']]
        expected = expected or [p for p in ctx['regions'][city['region']]['cities'] if p != path][:3]
        if expected:
            sections = [n for n in doc.nodes if n.tag == 'section' and n.has('kc-location-related')]
            links = {n.attrs.get('href') for section in sections for n in doc.nodes if n.tag == 'a' and section.start < n.start < section.end}
            assert all(href(p) in links for p in expected), path
            city_connections += len(expected)
    for rel in ('index.html', 'shows/index.html', 'artists/index.html', 'about-us/index.html'):
        doc = Document((site / rel).read_text())
        nav_node = doc.one(lambda n: n.tag == 'nav' and n.has('kc-location-nav'))
        assert [doc.text(n) for n in nav_node.children if n.tag == 'a'] == ['All Shows', 'States', 'Cities', 'Artists', 'Festivals']
    return {'version': VERSION, 'publicUpcomingShows': ctx['publicCount'], 'directoryLocations': verified_locations,
            'canadianProvinceLinks': province_links, 'cityConnections': city_connections,
            'productionIdentityVerified': True}


def verify_preservation(site, baseline):
    hashes = json.loads((baseline / 'structure-source-hashes.json').read_text())
    ctx = context(baseline)
    files = {p.relative_to(site).as_posix() for p in site.rglob('*') if p.is_file()}
    assert set(hashes) <= files, 'An existing production file was removed'
    assert files - set(hashes) <= FILES, 'Unexpected public files were added'
    protected = 0
    for rel, before_hash in hashes.items():
        actual = (site / rel).read_bytes()
        if rel.endswith('.html') or rel == 'sitemap.xml':
            before = (baseline / rel).read_bytes()
            expected = transform(rel, before, ctx)
            assert actual == expected, f'Unexpected structural difference: {rel}'
            if rel.endswith('.html'):
                assert html_facts(before.decode()) == html_facts(actual.decode()), f'Original facts changed: {rel}'
        else:
            assert digest(actual) == before_hash, f'Original data or media changed: {rel}'
            protected += 1
    for rel, expected in ctx['generated'].items():
        assert (site / rel).read_bytes() == expected, f'Directory generation drift: {rel}'
    return {'originalFilesPreserved': len(hashes), 'dataAndMediaFilesUnchanged': protected,
            'existingPageFactsAndShowCardsPreserved': True, **verify_current(site)}


def apply(site, baseline):
    assert (site / 'CNAME').read_text().strip() == 'kingdomcircuit.com'
    for route in ('shows/states/index.html', 'shows/cities/index.html'):
        assert not (site / route).exists(), f'Directory already exists before the structural stage: {route}'
    snapshot(site, baseline)
    ctx = context(baseline)
    for source in sorted(baseline.rglob('*.html')):
        rel = source.relative_to(baseline)
        (site / rel).write_bytes(transform(rel, source.read_bytes(), ctx))
    (site / 'sitemap.xml').write_bytes(transform('sitemap.xml', (baseline / 'sitemap.xml').read_bytes(), ctx))
    for rel, data in ctx['generated'].items():
        target = site / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return verify_preservation(site, baseline)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', required=True, type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--verify-current', action='store_true')
    args = parser.parse_args()
    if args.verify_current:
        result = verify_current(args.site.resolve())
    else:
        assert args.baseline, 'A baseline outside the public artifact is required'
        operation = verify_preservation if args.check else apply
        result = operation(args.site.resolve(), args.baseline.resolve())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
