from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re
import shutil
from collections import defaultdict

REPO = pathlib.Path.cwd()
OUT = REPO / "_site"
SITE = "https://kingdomcircuit.com"
TODAY = dt.date.today()
GA_ID = "G-N2KK9XF4TJ"
STATE_NAMES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado","CT":"Connecticut","DE":"Delaware","DC":"District of Columbia","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"
}


def esc(v): return html.escape(str(v or ""), quote=True)
def norm(v): return str(v or "").strip().casefold()

def slug(v):
    v = norm(v).replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", v).strip("-") or "item"

def fnv(v):
    h = 0x811C9DC5
    for b in str(v).encode():
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"[:6]

def event_slug(e):
    return f"{slug(e.get('title') or 'event')}-{e.get('startDate','')}-{slug(e.get('city',''))}-{fnv(e.get('id') or json.dumps(e,sort_keys=True))}"

def event_path(e): return f"/event/{event_slug(e)}/"
def artist_path(name): return f"/artists/{slug(name)}/"
def state_path(code): return f"/shows/{slug(STATE_NAMES.get(code,code))}/"
def city_path(city, code): return f"/shows/{slug(city)}-{slug(STATE_NAMES.get(code,code))}/"
def absolute(path): return SITE.rstrip("/") + "/" + path.lstrip("/")

def image_url(value):
    if not value: return SITE + "/assets/event-fallback.webp"
    if str(value).startswith("http"): return str(value).replace("http://","https://",1)
    return absolute(str(value))

def current(e):
    raw = e.get("endDate") or e.get("startDate")
    try: return dt.date.fromisoformat(str(raw)[:10]) >= TODAY
    except Exception: return True

def same_event(a,b):
    if a.get("startDate") != b.get("startDate") or norm(a.get("city")) != norm(b.get("city")): return False
    same_venue = norm(a.get("venue")) and norm(a.get("venue")) == norm(b.get("venue"))
    shared = bool({norm(x) for x in a.get("artists",[])} & {norm(x) for x in b.get("artists",[])})
    return bool(same_venue or shared)

def merge_events(primary, supplemental):
    out = [dict(e, artists=list(e.get("artists",[]))) for e in primary]
    for inc in supplemental:
        found = next((e for e in out if same_event(e,inc)), None)
        if not found:
            out.append(dict(inc, artists=list(inc.get("artists",[]))))
            continue
        found["artists"] = list(dict.fromkeys([*found.get("artists",[]), *inc.get("artists",[])]))
        for k in ("image","imageType","imagePosition","firstSeen"):
            if not found.get(k) and inc.get(k): found[k] = inc[k]
    return out

def format_date(e):
    raw = e.get("startDate")
    if not raw: return "Date to be announced"
    try:
        d = dt.date.fromisoformat(raw[:10]); text = d.strftime("%a, %b %-d, %Y")
    except Exception: text = raw
    if e.get("startTime"):
        try:
            h,m = map(int,e["startTime"].split(":")[:2]); text += f" - {h%12 or 12}:{m:02d} {'AM' if h<12 else 'PM'}"
        except Exception: pass
    return text

def source_text(e): return e.get("sourceName") or ((e.get("sources") or [{}])[0].get("name")) or "Official source"

def artist_cfg(artists,name):
    t=norm(name)
    return next((a for a in artists if norm(a.get("name"))==t or t in {norm(x) for x in a.get("aliases",[])}),{})

def spotify(a): return a.get("spotifyProfile") or (f"https://open.spotify.com/artist/{a['spotifyId']}" if a.get("spotifyId") else "")
def instagram(a): return a.get("instagramProfile","")
def youtube(a): return a.get("youtubeProfile","")
def website(a):
    x=a.get("website") or a.get("officialWebsite") or a.get("officialProfile") or ""
    return "" if re.search(r"instagram\.com|open\.spotify\.com|youtube\.com|youtu\.be|bandsintown\.com",x,re.I) else x

def header():
    return '''<header class="site-header"><div class="header-inner"><a class="brand" href="/" aria-label="The Kingdom Circuit home"><img src="/assets/logo.png" alt="The Kingdom Circuit - Christian hip-hop, live and connected"></a><button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-menu" aria-label="Open navigation"><span></span><span></span><span></span></button></div></header><div class="menu-backdrop" hidden></div><nav class="menu-drawer" id="site-menu" aria-label="Primary navigation" aria-hidden="true"><div class="menu-drawer-head"><span>Explore Kingdom Circuit</span><button class="menu-close" type="button" aria-label="Close navigation">x</button></div><div class="menu-links"><a href="/">Home</a><a href="/shows/">All Shows</a><a href="/shows/this-month/">This Month</a><a href="/festivals/">Festivals</a><a href="/new-shows/">New Shows</a><a href="/artists/">Artists</a><a href="/submit/">Submit a Show</a></div><p class="menu-mission">Christian hip-hop, live and connected.</p></nav>'''

def footer():
    return '''<footer class="site-footer"><div><strong>The Kingdom Circuit</strong><p>Christian hip-hop, live and connected.</p></div><div class="footer-links"><a href="/shows/">All Shows</a><a href="/artists/">Artists</a><a href="/festivals/">Festivals</a><a href="/submit/">Submit a Show</a></div><p class="footer-note">Event details may change; confirm with the official source before traveling.</p></footer>'''

def head(title, desc, canonical, schemas=None):
    schema_html="".join(f'<script type="application/ld+json">{json.dumps(s,separators=(",",":"),ensure_ascii=False).replace("</","<\\/")}</script>' for s in (schemas or []))
    return f'''<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta name="robots" content="index,follow"><meta name="description" content="{esc(desc)}"><meta name="theme-color" content="#080808"><link rel="canonical" href="{esc(absolute(canonical))}"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/styles.css?v=10.3"><meta property="og:type" content="website"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{esc(absolute(canonical))}"><script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script><script src="/seo-static.js?v=1" defer></script><title>{esc(title)}</title>{schema_html}</head>'''

def page(title,desc,canonical,body,schemas=None): return f'<!DOCTYPE html><html lang="en">{head(title,desc,canonical,schemas)}<body>{header()}<main>{body}</main>{footer()}</body></html>'

def breadcrumbs(items):
    parts=[]
    for i,(name,path) in enumerate(items): parts.append(esc(name) if i==len(items)-1 else f'<a class="text-link" href="{path}">{esc(name)}</a>')
    return '<p class="eyebrow">'+' / '.join(parts)+'</p>'

def breadcrumb_schema(items):
    return {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":i+1,"name":n,"item":absolute(p)} for i,(n,p) in enumerate(items)]}

def event_schema(e):
    start=e.get("startDate","")+("T"+e["startTime"] if e.get("startTime") else "")
    data={"@context":"https://schema.org","@type":"MusicEvent","name":e.get("title") or "Christian hip-hop event","startDate":start,"eventAttendanceMode":"https://schema.org/OfflineEventAttendanceMode","eventStatus":"https://schema.org/EventScheduled","url":absolute(event_path(e)),"image":[image_url(e.get("image"))],"location":{"@type":"Place","name":e.get("venue") or "Venue to be announced","address":{"@type":"PostalAddress","streetAddress":e.get("address") or "","addressLocality":e.get("city") or "","addressRegion":e.get("state") or "","addressCountry":"US"}},"performer":[{"@type":"MusicGroup","name":n} for n in e.get("artists",[])]}
    if e.get("endDate"): data["endDate"]=e["endDate"]
    url=e.get("officialUrl") or e.get("ticketUrl")
    if url: data["offers"]={"@type":"Offer","url":url,"availability":"https://schema.org/InStock"}
    return data

def event_card(e,artists):
    cfg=artist_cfg(artists,e.get("headliner") or ((e.get("artists") or [""])[0]))
    img=image_url(e.get("image") or cfg.get("imageUrl")); pos=e.get("imagePosition") or cfg.get("imagePosition") or "center"
    typ="event-artwork" if e.get("imageType")=="event_artwork" else "artist-photo"
    location=", ".join(x for x in (e.get("city"),e.get("state")) if x) or "Location to be announced"
    artists_html=" - ".join(f'<a href="{artist_path(n)}">{esc(n)}</a>' for n in e.get("artists",[]))
    official=e.get("officialUrl") or e.get("ticketUrl") or "#"
    return f'''<article class="event-card" data-event-card data-state="{esc(e.get('state'))}" data-type="{esc(e.get('eventType') or 'concert')}" data-date="{esc(e.get('startDate'))}" data-end-date="{esc(e.get('endDate') or e.get('startDate'))}"><a class="event-media" href="{event_path(e)}"><img class="{typ}" src="{esc(img)}" alt="{esc(e.get('title'))} image" loading="lazy" decoding="async" width="1200" height="675" style="object-position:{esc(pos)}"></a><div class="event-content"><div class="event-main"><div class="event-badges"><span class="badge badge-gold">{esc('Festival' if e.get('eventType')=='festival' else 'Concert')}</span></div><h3><a href="{event_path(e)}">{esc(e.get('title'))}</a></h3><p class="artist-line">{artists_html}</p><dl class="event-meta"><div><dt>Date</dt><dd>{esc(format_date(e))}</dd></div><div><dt>Venue</dt><dd>{esc(e.get('venue') or 'Venue to be announced')}</dd></div><div><dt>Location</dt><dd>{esc(location)}</dd></div></dl></div><div class="event-footer"><a class="official-button" href="{esc(official)}" target="_blank" rel="noopener">Official details</a><p class="source-line">Source: {esc(source_text(e))}</p></div></div></article>'''

def write_page(path,content):
    target=OUT/path.strip("/")/"index.html" if path!="/" else OUT/"index.html"
    target.parent.mkdir(parents=True,exist_ok=True); target.write_text(content,encoding="utf-8")

def patch_meta(path,title,desc,canonical):
    if not path.exists(): return
    text=path.read_text(encoding="utf-8")
    text=re.sub(r'<title>.*?</title>',f'<title>{esc(title)}</title>',text,flags=re.S)
    text=re.sub(r'<meta name="description" content="[^"]*">',f'<meta name="description" content="{esc(desc)}">',text)
    text=re.sub(r'<meta name="robots" content="[^"]*">','<meta name="robots" content="index,follow">',text)
    text=re.sub(r'<link rel="canonical"[^>]*>\s*','',text)
    text=text.replace('</head>',f'  <link rel="canonical" href="{absolute(canonical)}">\n</head>')
    text=re.sub(r'/app\.js\?v=[^"\']+','/app.js?v=13.0-seo',text)
    path.write_text(text,encoding="utf-8")

def prerender_events(path,shows,artists):
    if not path.exists(): return
    text=path.read_text(encoding="utf-8")
    text=text.replace('<div class="event-grid" data-event-grid></div>',f'<div class="event-grid" data-event-grid>{"".join(event_card(e,artists) for e in shows)}</div>')
    text=re.sub(r'<div class="loading-panel" data-loading-panel>.*?</div>','',text,flags=re.S)
    text=re.sub(r'<p class="results-count" data-results-count>.*?</p>',f'<p class="results-count" data-results-count>{len(shows)} shows</p>',text,flags=re.S)
    path.write_text(text,encoding="utf-8")

def prerender_artists(path,events,artists):
    if not path.exists(): return
    by=defaultdict(list)
    for e in events:
        for n in e.get("artists",[]): by[norm(n)].append(e)
    cards=[]
    for a in sorted((x for x in artists if x.get("enabled") is not False),key=lambda x:(x.get("rosterOrder",9999),x.get("name","").casefold())):
        n=a.get("name",""); count=len(by[norm(n)])
        cards.append(f'<article class="artist-card artist-card-text" data-artist-card data-has-shows="{str(bool(count)).lower()}"><a class="artist-visual artist-visual-empty" href="{artist_path(n)}" aria-label="View {esc(n)}"></a><div class="artist-card-body"><h2><a href="{artist_path(n)}">{esc(n)}</a></h2><p>{count} upcoming show{"s" if count!=1 else ""}</p><div class="artist-card-footer"><a class="text-link" href="{artist_path(n)}">View artist</a></div></div></article>')
    text=path.read_text(encoding="utf-8").replace('<div class="artist-grid" data-artist-grid></div>',f'<div class="artist-grid" data-artist-grid>{"".join(cards)}</div>')
    text=re.sub(r'<div class="loading-panel" data-artist-loading>.*?</div>','',text,flags=re.S)
    text=re.sub(r'<p class="results-count" data-artist-count>.*?</p>',f'<p class="results-count" data-artist-count>{len(cards)} artists</p>',text,flags=re.S)
    path.write_text(text,encoding="utf-8")

def patch_app(path):
    if not path.exists(): return
    text=path.read_text(encoding="utf-8")
    helper='''\nfunction seoSlug(value){return String(value||"").trim().toLowerCase().replace(/&/g," and ").replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"")||"item";}\nfunction seoFNV(value){let h=0x811c9dc5;const bytes=new TextEncoder().encode(String(value||""));for(const b of bytes){h^=b;h=Math.imul(h,0x01000193)>>>0;}return h.toString(16).padStart(8,"0").slice(0,6);}\nfunction seoEventSlug(event){return [seoSlug(event.title||"event"),event.startDate||"",seoSlug(event.city||"")].filter(Boolean).join("-")+"-"+seoFNV(event.id||JSON.stringify(event));}\n'''
    if "function seoSlug(" not in text:
        idx=text.find("function eventDetailUrl")
        if idx<0: raise RuntimeError("eventDetailUrl not found in app.js")
        text=text[:idx]+helper+text[idx:]
    text=re.sub(r'function eventDetailUrl\(event\)\s*\{.*?\n\}', 'function eventDetailUrl(event) { return `${BASE}event/${seoEventSlug(event)}/`; }', text, count=1, flags=re.S)
    text=re.sub(r'function artistProfileUrl\(name\)\s*\{.*?\n\}', 'function artistProfileUrl(name) { return `${BASE}artists/${seoSlug(name)}/`; }', text, count=1, flags=re.S)
    path.write_text(text,encoding="utf-8")

def main():
    events=json.loads((REPO/"events.json").read_text(encoding="utf-8"))
    artists=json.loads((REPO/"config/artists.json").read_text(encoding="utf-8"))
    supplemental=json.loads((REPO/"supplemental-events.json").read_text(encoding="utf-8")) if (REPO/"supplemental-events.json").exists() else []
    events=sorted([e for e in merge_events(events,supplemental) if current(e)],key=lambda e:(e.get("startDate",""),e.get("startTime",""),e.get("title","")))

    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    for item in REPO.iterdir():
        if item.name in {".git",".github","_site","tests","scripts","cache"}: continue
        dest=OUT/item.name
        shutil.copytree(item,dest) if item.is_dir() else shutil.copy2(item,dest)

    patch_app(OUT/"app.js")
    patch_meta(OUT/"index.html","Christian Hip-Hop Shows & Concerts | The Kingdom Circuit","Find verified Christian hip-hop concerts, Christian rap shows, festivals, tours, and live events across the United States.","/")
    patch_meta(OUT/"shows/index.html","Christian Hip-Hop Shows & Concerts | The Kingdom Circuit","Browse upcoming verified Christian hip-hop concerts, Christian rap shows, tours, festivals, and live events across the United States.","/shows/")
    patch_meta(OUT/"shows/this-month/index.html",f"Christian Hip-Hop Shows in {TODAY.strftime('%B %Y')} | The Kingdom Circuit",f"Find verified Christian hip-hop concerts and festivals happening in {TODAY.strftime('%B %Y')}.","/shows/this-month/")
    patch_meta(OUT/"festivals/index.html","Christian Hip-Hop Festivals | The Kingdom Circuit","Discover upcoming U.S. festivals with confirmed Christian hip-hop and Christian rap artists.","/festivals/")
    patch_meta(OUT/"new-shows/index.html","New Christian Hip-Hop Shows | The Kingdom Circuit","See Christian hip-hop concerts and festivals recently added to The Kingdom Circuit.","/new-shows/")
    patch_meta(OUT/"artists/index.html","Christian Hip-Hop Artist Directory | The Kingdom Circuit","Browse Christian hip-hop artists and find verified upcoming concerts and official profiles.","/artists/")

    prerender_events(OUT/"index.html",events,artists); prerender_events(OUT/"shows/index.html",events,artists)
    prerender_events(OUT/"shows/this-month/index.html",[e for e in events if e.get("startDate","").startswith(TODAY.strftime("%Y-%m"))],artists)
    prerender_events(OUT/"festivals/index.html",[e for e in events if e.get("eventType")=="festival"],artists)
    cutoff=TODAY-dt.timedelta(days=14)
    recent=[]
    for e in events:
        try:
            if dt.datetime.fromisoformat(str(e.get("firstSeen","")).replace("Z","+00:00")).date()>=cutoff: recent.append(e)
        except Exception: pass
    prerender_events(OUT/"new-shows/index.html",recent,artists); prerender_artists(OUT/"artists/index.html",events,artists)

    urls=["/","/shows/","/shows/this-month/","/festivals/","/new-shows/","/artists/","/submit/"]
    by_state=defaultdict(list); by_city=defaultdict(list); by_month=defaultdict(list)
    for e in events:
        if e.get("state"): by_state[e["state"]].append(e)
        if e.get("city") and e.get("state"): by_city[(e["city"],e["state"])].append(e)
        try:
            d=dt.date.fromisoformat(e.get("startDate","")[:10]); by_month[(d.year,d.month)].append(e)
        except Exception: pass

    for e in events:
        p=event_path(e); urls.append(p); loc=", ".join(x for x in (e.get("city"),e.get("state")) if x); names=", ".join(e.get("artists",[])) or e.get("headliner") or "CHH artists"
        crumbs=[("Shows","/shows/")]
        if e.get("state"): crumbs.append((STATE_NAMES.get(e["state"],e["state"]),state_path(e["state"])))
        crumbs.append((e.get("title") or "Event",p))
        img=image_url(e.get("image")); cls="event-artwork" if e.get("imageType")=="event_artwork" else "artist-photo"; artist_links=" - ".join(f'<a href="{artist_path(n)}">{esc(n)}</a>' for n in e.get("artists",[])); official=e.get("officialUrl") or e.get("ticketUrl") or "#"
        body=f'<section class="event-detail-section">{breadcrumbs(crumbs)}<article class="event-detail"><div class="event-detail-media"><img class="{cls}" src="{esc(img)}" alt="{esc(e.get("title"))}" width="1200" height="675"></div><div class="event-detail-copy"><p class="eyebrow">{esc("Festival" if e.get("eventType")=="festival" else "Concert")}</p><h1>{esc(e.get("title"))}</h1><p class="artist-line">{artist_links}</p><dl class="detail-list"><div><dt>Date</dt><dd>{esc(format_date(e))}</dd></div><div><dt>Venue</dt><dd>{esc(e.get("venue") or "Venue to be announced")}</dd></div><div><dt>Location</dt><dd>{esc(loc)}</dd></div><div><dt>Source</dt><dd>{esc(source_text(e))}</dd></div></dl><a class="primary-button" href="{esc(official)}" target="_blank" rel="noopener">Official details</a><p class="disclaimer">Event details may change. Confirm final information with the official organizer or ticket provider before purchasing or traveling.</p></div></article></section>'
        write_page(p,page(f"{e.get('title')} - {loc} | The Kingdom Circuit",f"{names} live in {loc} on {format_date(e)}. Verified official show details.",p,body,[event_schema(e),breadcrumb_schema(crumbs)]))

    for a in (x for x in artists if x.get("enabled") is not False):
        n=a.get("name") or "Artist"; p=artist_path(n); urls.append(p); shows=[e for e in events if norm(n) in {norm(x) for x in e.get("artists",[])}]; crumbs=[("Artists","/artists/"),(n,p)]
        links=[]
        for label,url in (("Instagram",instagram(a)),("Spotify",spotify(a)),("YouTube",youtube(a)),("Website",website(a))):
            if url: links.append(f'<a class="secondary-button" href="{esc(url)}" target="_blank" rel="noopener">{label}</a>')
        body=f'<section class="profile-section">{breadcrumbs(crumbs)}<section class="profile-hero profile-hero-no-image"><div><p class="eyebrow">Artist profile</p><h1>{esc(n)}</h1><div class="profile-links">{"".join(links)}</div><p class="profile-count">{len(shows)} upcoming U.S. show{"s" if len(shows)!=1 else ""} currently listed.</p></div></section><section class="calendar"><div class="calendar-heading"><div><p class="eyebrow">Verified listings</p><h2>Upcoming {esc(n)} Shows</h2></div><p class="results-count">{len(shows)} shows</p></div><div class="event-grid">{"".join(event_card(e,artists) for e in shows) if shows else "<div class=\"empty-panel\">No upcoming U.S. shows are currently confirmed.</div>"}</div></section></section>'
        write_page(p,page(f"{n} Concerts & Tour Dates | The Kingdom Circuit",f"Find upcoming {n} Christian hip-hop concerts, tour dates, festivals, and verified official show links.",p,body,[breadcrumb_schema(crumbs)]))

    for code,shows in by_state.items():
        name=STATE_NAMES.get(code,code); p=state_path(code); urls.append(p); crumbs=[("Shows","/shows/"),(name,p)]; body=f'<section class="page-hero hero-compact">{breadcrumbs(crumbs)}<p class="eyebrow">{esc(name)}</p><h1>Christian Hip-Hop Shows in {esc(name)}</h1><p class="hero-text">Browse upcoming verified CHH concerts, Christian rap shows, and festivals in {esc(name)}.</p></section><section class="calendar"><div class="event-grid">{"".join(event_card(e,artists) for e in shows)}</div></section>'; write_page(p,page(f"Christian Hip-Hop Shows in {name} | The Kingdom Circuit",f"Find upcoming Christian hip-hop concerts and festivals in {name}.",p,body,[breadcrumb_schema(crumbs)]))
    for (city,code),shows in by_city.items():
        state=STATE_NAMES.get(code,code); p=city_path(city,code); urls.append(p); crumbs=[("Shows","/shows/"),(state,state_path(code)),(city,p)]; body=f'<section class="page-hero hero-compact">{breadcrumbs(crumbs)}<p class="eyebrow">{esc(city)}, {esc(code)}</p><h1>Christian Hip-Hop Shows in {esc(city)}</h1><p class="hero-text">Browse upcoming verified CHH concerts and festivals in {esc(city)}, {esc(state)}.</p></section><section class="calendar"><div class="event-grid">{"".join(event_card(e,artists) for e in shows)}</div></section>'; write_page(p,page(f"Christian Hip-Hop Shows in {city}, {code} | The Kingdom Circuit",f"Find upcoming Christian hip-hop concerts and festivals in {city}, {state}.",p,body,[breadcrumb_schema(crumbs)]))
    for (year,month),shows in by_month.items():
        d=dt.date(year,month,1); label=d.strftime("%B %Y"); p=f"/shows/{d.strftime('%B').lower()}-{year}/"; urls.append(p); crumbs=[("Shows","/shows/"),(label,p)]; body=f'<section class="page-hero hero-compact">{breadcrumbs(crumbs)}<p class="eyebrow">Monthly calendar</p><h1>Christian Hip-Hop Shows in {label}</h1><p class="hero-text">Browse verified CHH concerts and festivals scheduled for {label}.</p></section><section class="calendar"><div class="event-grid">{"".join(event_card(e,artists) for e in shows)}</div></section>'; write_page(p,page(f"Christian Hip-Hop Shows in {label} | The Kingdom Circuit",f"Find Christian hip-hop concerts and festivals in {label}.",p,body,[breadcrumb_schema(crumbs)]))

    (OUT/"seo-static.js").write_text('''"use strict";function setMenuOpen(o){const t=document.querySelector(".menu-toggle"),d=document.querySelector(".menu-drawer"),b=document.querySelector(".menu-backdrop");if(!t||!d||!b)return;t.setAttribute("aria-expanded",String(o));d.setAttribute("aria-hidden",String(!o));d.classList.toggle("open",o);b.hidden=!o;document.body.classList.toggle("menu-open",o)}document.querySelector(".menu-toggle")?.addEventListener("click",()=>setMenuOpen(document.querySelector(".menu-toggle")?.getAttribute("aria-expanded")!=="true"));document.querySelector(".menu-close")?.addEventListener("click",()=>setMenuOpen(false));document.querySelector(".menu-backdrop")?.addEventListener("click",()=>setMenuOpen(false));''',encoding="utf-8")
    unique=list(dict.fromkeys(urls)); xml=['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']+[f'<url><loc>{esc(absolute(u))}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>' for u in unique]+['</urlset>']; (OUT/"sitemap.xml").write_text("\n".join(xml)+"\n",encoding="utf-8"); (OUT/"robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: https://kingdomcircuit.com/sitemap.xml\n",encoding="utf-8")
    manifest={"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"mode":"production-indexable","events":len(events),"artists":len([a for a in artists if a.get("enabled") is not False]),"urls":len(unique),"eventPages":len(events),"artistPages":len([a for a in artists if a.get("enabled") is not False])}; (OUT/"seo-build-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    assert manifest["artists"]>=250 and manifest["events"]>=20 and manifest["urls"]>=400
    assert (OUT/"CNAME").read_text().strip()=="kingdomcircuit.com"
    print(json.dumps(manifest,indent=2))

if __name__=="__main__": main()
