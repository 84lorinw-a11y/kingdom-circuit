"""Independent date maintenance and final/live calendar freshness checks."""
import argparse
import concurrent.futures
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
import time
import urllib.request
from zoneinfo import ZoneInfo
from mobile_discovery import Document
from national_discovery import card_records

def today():
    return datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()

def refresh_mode(event, requested='', message=''):
    if event == 'workflow_dispatch':
        return 'dates' if requested == 'dates' else 'full'
    return 'full' if event == 'push' and '[full scan]' in message else 'dates'

def catalog_errors(catalog, day):
    errors=[]
    if catalog.get('asOf') != day: errors.append(f'catalog asOf {catalog.get("asOf")} differs from {day}')
    paths=set()
    for show in catalog.get('shows',[]):
        path=show.get('path',''); end=show.get('end') or show.get('date','')
        if path in paths: errors.append(f'duplicate catalog path: {path}')
        paths.add(path)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',end) or end<day: errors.append(f'expired or invalid catalog date: {path}')
    if not paths: errors.append('upcoming catalog is empty')
    return errors

def artist_errors(html, shows, day):
    doc=Document(html); errors=[]
    configs=[n for n in doc.nodes if n.attrs.get('id')=='kc-fan-config']
    if not configs:return ['artist configuration missing']
    config=json.loads(doc.text(configs[0]))
    if not config.get('artist'):return []  # Redirects and the generic profile route.
    by_path={s['path']:s for s in shows if (s.get('end') or s['date'])>=day}
    expected=[p for p in dict.fromkeys(config.get('showPaths',[])) if p in by_path]
    next_nodes=[n for n in doc.nodes if n.has('kc-rd-next-show')]
    next_path=next_nodes[0].attrs.get('href') if next_nodes else None
    if next_path!=(expected[0] if expected else None):errors.append('next show is not the first current show')
    totals=[n for n in doc.nodes if n.has('kc-rd-upcoming-total')]
    if not totals or not re.match(r'^'+str(len(expected))+r'\b',doc.text(totals[0])): errors.append('artist upcoming count differs from catalog')
    lists=[n for n in doc.nodes if n.has('kc-rd-show-list')]
    if lists:
        rows=[n.attrs.get('href') for n in doc.nodes if n.has('kc-rd-show-row') and lists[0].start<n.start<lists[0].end]
        if rows!=expected:errors.append('artist rows contain expired or absent catalog records')
    for node in doc.nodes:
        if 'data-live-show-count' in node.attrs and doc.text(node)!=str(len(by_path)):errors.append('discovery count differs from catalog')
    return errors

def week_window(day):
    d=date.fromisoformat(day);start=d-timedelta(days=d.weekday())
    return tuple((start+timedelta(days=n)).isoformat() for n in [0,6,7,13])

def page_errors(pages,catalog,day):
    errors=catalog_errors(catalog,day)
    all_paths=[s['path'] for s in catalog.get('shows',[])]
    records=card_records(pages['shows/index.html'])
    if set(r['href'] for r in records)!=set(all_paths):errors.append('All Shows differs from the shared catalog')
    home=Document(pages['index.html'])
    homes=[n for n in home.nodes if 'data-national-home' in n.attrs]
    if not homes or homes[0].attrs.get('data-preview-as-of')!=day: errors.append('homepage weekly preview date is stale')
    start,end,next_start,next_end=week_window(day)
    for section_id,lo,hi in [('kc-week-shelf',start,end),('kc-next-shelf',next_start,next_end)]:
        shelves=[n for n in home.nodes if n.attrs.get('id')==section_id]
        if not shelves:errors.append('missing weekly shelf: '+section_id);continue
        for node in home.nodes:
            if 'data-discovery-show' not in node.attrs or not shelves[0].start<node.start<shelves[0].end:continue
            begins=node.attrs.get('data-date','');ends=node.attrs.get('data-end-date') or begins
            if ends<max(day,lo) or begins>hi:errors.append('show outside current weekly window: '+section_id)
    for path,html in pages.items():
        if re.fullmatch(r'artists/[^/]+/index.html',path):
            errors.extend(path+': '+e for e in artist_errors(html,catalog['shows'],day))
    return errors

def verify_site(site,day):
    catalog=json.loads((site/'assets/fan-show-catalog.json').read_text())
    paths=[site/'index.html',site/'shows/index.html',*(site/'artists').glob('*/index.html')]
    pages={p.relative_to(site).as_posix():p.read_text() for p in paths}
    return {'asOf':day,'upcoming':len(catalog['shows']),'artistsChecked':len(paths)-2,'errors':page_errors(pages,catalog,day)}

def verify_live(origin,day):
    def read(path):
        req=urllib.request.Request(origin.rstrip('/')+'/'+path,headers={'User-Agent':'KingdomCircuit-freshness-check','Cache-Control':'no-cache'})
        with urllib.request.urlopen(req,timeout=35) as response:return response.read().decode()
    catalog=json.loads(read('assets/fan-show-catalog.json'))
    artists=catalog.get('artists',{})
    # Build verification checks every artist; the public check checks a rotating
    # sample plus every artist whose first show is today, the rollover boundary.
    keys=sorted(artists); offset=date.fromisoformat(day).toordinal()%max(1,len(keys))
    sample=(keys+keys)[offset:offset+12]
    by_path={s['path']:s for s in catalog['shows']}
    sample+= [k for k,v in artists.items() if v and by_path.get(v[0],{}).get('date')==day]
    paths=['index.html','shows/index.html',*(k.strip('/')+'/index.html' for k in dict.fromkeys(sample))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        pages=dict(zip(paths,pool.map(read,paths)))
    return {'asOf':day,'upcoming':len(catalog['shows']),'artistsChecked':len(paths)-2,'errors':page_errors(pages,catalog,day)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',action='store_true');parser.add_argument('--site',type=Path);parser.add_argument('--live');parser.add_argument('--day');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.mode:
        mode=refresh_mode(os.getenv('KC_EVENT_NAME',''),os.getenv('KC_REQUESTED_MODE',''),os.getenv('KC_COMMIT_MESSAGE',''))
        print('discovery='+str(mode=='full').lower());print('mode='+mode)
    else:
        day=args.day or today()
        result=verify_live(args.live,day) if args.live else verify_site(args.site,day)
        text=json.dumps(result,indent=2)+'\n';print(text)
        if args.output:args.output.write_text(text)
        raise SystemExit(bool(result['errors']))
