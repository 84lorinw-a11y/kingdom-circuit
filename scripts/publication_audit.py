"""Read-only final site acceptance, followed by a content-addressed release receipt.

Run AFTER every page writer and BEFORE upload. Unknown source facts stay unknown.
This checks publication consistency, not whether Google has indexed the release.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

import calendar_maintenance as calendar
from mobile_discovery import Document
import show_information
import url_continuity as continuity

ORIGIN = continuity.ORIGIN
EVENT_TYPES = {'Event', 'MusicEvent', 'Festival'}
MANIFEST = 'publication-manifest.json'
ROOT = Path(__file__).resolve().parents[1]


def issue(kind, path, **facts):
    return dict(kind=kind, path=path, **facts)


def walk(value):
    if isinstance(value, list):
        for child in value:
            yield from walk(child)
    elif isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from walk(child)


def types(node):
    value = node.get('@type', [])
    return set(value if isinstance(value, list) else [value])


def page_url(file, site):
    rel = file.relative_to(site).as_posix()
    return '/' + (rel.removesuffix('index.html') if rel.endswith('index.html') else rel)


def norm(value):
    return ' '.join(str(value or '').casefold().split())


def robots_errors(site, paths, agent='Googlebot'):
    file = site / 'robots.txt'
    if not file.is_file():
        return [issue('missing_robots_file', '/robots.txt')]
    parser = RobotFileParser()
    parser.parse(file.read_text().splitlines())
    errors = []
    if ORIGIN + '/sitemap.xml' not in (parser.site_maps() or []):
        errors.append(issue('robots_sitemap_missing', '/robots.txt'))
    for path in paths:
        if not parser.can_fetch(agent, ORIGIN + path):
            errors.append(issue('robots_blocks_public_page', path, agent=agent))
    return errors


def audit_documents(site, redirects, sitemap):
    errors, pages, events, counts = [], {}, {}, Counter()
    for file in sorted(site.rglob('*.html')):
        path = page_url(file, site)
        text = file.read_text()
        try:
            facts = continuity.PageFacts(text)
            doc = Document(text)
            nodes = [node for schema in facts.schemas for node in walk(schema)]
            schemas = [node for node in nodes if types(node) & EVENT_TYPES]
        except Exception as exc:
            errors.append(issue('invalid_jsonld_or_html_parse', path, error=str(exc)))
            continue
        for node in nodes:
            counts.update(t for t in types(node) if t)
        for link in facts.links:
            try:
                resource = local_resource(site, path, link)
                if resource and not resource[1].is_file():
                    errors.append(issue('missing_internal_link_target', path, target=resource[0]))
            except ValueError as exc:
                errors.append(issue('invalid_internal_link', path, target=link, error=str(exc)))
        events[path] = schemas
        in_sitemap = ORIGIN + path in sitemap
        info = dict(canonical=facts.canonical, robots=facts.robots, sitemap=in_sitemap,
                    redirect=bool(facts.refresh), eventSchemaCount=len(schemas))
        pages[path] = info
        canonicals = [n for n in doc.nodes if n.tag == 'link' and n.attrs.get('rel') == 'canonical']
        robots = [n for n in doc.nodes if n.tag == 'meta' and n.attrs.get('name', '').lower() == 'robots']
        if path == '/404.html':
            if in_sitemap or schemas:
                errors.append(issue('error_document_indexing_or_schema', path))
            continue
        if path == '/play/':
            if (set(facts.robots.replace(' ', '').split(',')) != {'noindex', 'nofollow'}
                    or in_sitemap or facts.schemas or facts.canonical):
                errors.append(issue('game_indexing_policy', path))
            continue
        expected = ORIGIN + redirects.get(path, path)
        if len(canonicals) != 1 or facts.canonical != expected:
            errors.append(issue('canonical_mismatch', path, actual=facts.canonical, expected=expected, count=len(canonicals)))
        if len(robots) != 1:
            errors.append(issue('robots_tag_count', path, count=len(robots)))
        if in_sitemap and ('noindex' in facts.robots.casefold() or facts.refresh or facts.canonical != ORIGIN + path):
            errors.append(issue('sitemap_nonindexable_or_noncanonical', path, **info))
        if not in_sitemap and 'noindex' not in facts.robots.casefold() and not facts.refresh and facts.canonical == ORIGIN + path:
            errors.append(issue('indexable_page_missing_from_sitemap', path))
        directive = continuity.calendar_robots(path, text)
        if path not in redirects and directive and facts.robots != directive:
            errors.append(issue('calendar_policy_mismatch', path, expected=directive, **info))
        for schema in schemas:
            if schema.get('url') and schema['url'] != facts.canonical:
                errors.append(issue('event_schema_url_mismatch', path, actual=schema['url'], expected=facts.canonical))
            if schema.get('eventStatus') == 'https://schema.org/EventCompleted':
                errors.append(issue('invalid_event_completed_status', path))
            if schema.get('startDate') and schema.get('endDate') and str(schema['endDate'])[:10] < str(schema['startDate'])[:10]:
                errors.append(issue('event_end_before_start_day', path))
    for url in sorted(sitemap):
        if not url.startswith(ORIGIN + '/') or url.removeprefix(ORIGIN) not in pages:
            errors.append(issue('sitemap_missing_or_external_page', url))
    return dict(errors=errors, pages=pages, events=events, schemaTypes=dict(counts))


def event_fact_errors(path, record, schemas):
    errors = []
    if record.get('private') or record.get('locationUnconfirmed'):
        return [issue('private_or_unconfirmed_event_schema', path)] if schemas else []
    if len(schemas) != 1:
        errors.append(issue('public_current_event_schema_count', path, count=len(schemas)))
    status = {'cancelled': 'EventCancelled', 'canceled': 'EventCancelled',
              'postponed': 'EventPostponed', 'rescheduled': 'EventRescheduled'}.get(norm(record.get('status')), 'EventScheduled')
    for schema in schemas:
        for key, expected in {'name': record.get('title'), 'url': ORIGIN + path,
                              'eventStatus': 'https://schema.org/' + status,
                              'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
                              'startDate': record.get('schemaStartDate'),
                              'endDate': record.get('schemaEndDate'), 'offers': record.get('offer')}.items():
            if schema.get(key) != expected:
                errors.append(issue('source_schema_fact_mismatch', path, field=key, expected=expected, actual=schema.get(key)))
        location = schema.get('location') or {}
        address = location.get('address') or {}
        expected = {'name': record.get('venue') or '',
                    'streetAddress': ', '.join(v for v in (record.get('address'), record.get('address2') or record.get('suite')) if v),
                    'addressLocality': record.get('venueLocality') or '', 'addressRegion': record.get('state') or '',
                    'postalCode': record.get('postalCode') or '', 'addressCountry': record.get('country') or 'US'}
        for key, value in expected.items():
            actual = location.get(key) if key == 'name' else address.get(key)
            if norm(actual) != norm(value):
                errors.append(issue('source_location_mismatch', path, field=key, expected=value, actual=actual))
        expected_performers = {norm(v) for v in record.get('advertisedBilling') or record.get('artists', [])}
        expected_performers -= {norm(v) for v in record.get('unconfirmedArtists', [])}
        if record.get('billingRole') == 'judges':
            expected_performers = set()
        actual = schema.get('performer') or []
        actual = [actual] if isinstance(actual, dict) else actual
        actual_performers = {norm(p.get('name')) for p in actual}
        if actual_performers != expected_performers:
            errors.append(issue('performer_membership_mismatch', path, expected=sorted(expected_performers), actual=sorted(actual_performers)))
    return errors


def private_page_errors(path, text):
    """Validate canonical private pages after URL reconciliation, not old aliases."""
    errors = []
    facts = continuity.PageFacts(text)
    if facts.refresh or not re.search(r'private|invite.only', text, re.I):
        errors.append(issue('private_canonical_label_missing', path))
    for node in (n for value in facts.schemas for n in walk(value)):
        if types(node) & (EVENT_TYPES | {'Offer', 'AggregateOffer'}):
            errors.append(issue('private_public_schema_leak', path))
    return errors


def local_resource(site, source_path, reference):
    if not isinstance(reference, str) or not reference.strip() or reference.startswith(('#', 'data:', 'blob:', 'mailto:', 'tel:', 'javascript:')):
        return None
    parsed = urlsplit(urljoin(ORIGIN + source_path, reference))
    if parsed.scheme not in ('http', 'https') or parsed.netloc != urlsplit(ORIGIN).netloc:
        return None
    path = unquote(parsed.path)
    file = (site / path.lstrip('/')).resolve()
    if not file.is_relative_to(site.resolve()):
        raise ValueError('Resource escapes site root: ' + reference)
    if file.is_dir() or path.endswith('/'):
        file = file / 'index.html'
    return path, file


def build_manifest(site, release_id, day, image_pages):
    """Hash all pages, live feeds, JS/CSS/fonts and current imagery; no network I/O.

    Archive artwork is deliberately excluded from required imagery. The receipt
    contains public paths and digests only, never unpublished source records.
    """
    files, errors, queue, seen = {}, [], [], set()
    def add(path, file, status=200):
        if path in seen:
            return
        seen.add(path)
        if file.is_symlink() or not file.resolve().is_relative_to(site.resolve()) or not file.is_file():
            errors.append(issue('missing_or_unsafe_resource', '/', resource=path))
            return
        raw = file.read_bytes()
        kind = 'html' if file.suffix == '.html' else 'resource'
        files[path] = dict(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), status=status, kind=kind)
        if file.suffix in {'.html', '.css', '.json', '.webmanifest'}:
            queue.append((path, file))
    for file in sorted(site.rglob('*.html')):
        add(page_url(file, site), file)
    for name in ('robots.txt', 'sitemap.xml', 'events.json', 'supplemental-events.json', 'run-status.json',
                 'event-history.json', 'config/artists.json', 'url-continuity-manifest.json',
                 'assets/fan-show-catalog.json'):
        file = site / name
        if file.is_file():
            add('/' + name, file)
    while queue:
        path, file = queue.pop()
        text = file.read_text()
        references = []
        if file.suffix == '.html':
            doc = Document(text)
            for node in doc.nodes:
                if node.tag == 'script' and node.attrs.get('src'):
                    references.append(node.attrs['src'])
                if node.tag == 'link' and set(node.attrs.get('rel', '').split()) & {'stylesheet', 'icon', 'preload', 'modulepreload', 'manifest', 'apple-touch-icon'}:
                    references.append(node.attrs.get('href'))
                if path in image_pages and node.tag in {'img', 'source'}:
                    references.append(node.attrs.get('src'))
                    references.extend(item.strip().split(' ')[0] for item in node.attrs.get('srcset', '').split(',') if item.strip())
            # Inline CSS resources (including artist backgrounds).
            references.extend(re.findall(r'url\(\s*[\"\']?([^\)\"\']+)', text))
        elif file.suffix == '.css':
            references.extend(re.findall(r'url\(\s*[\"\']?([^\)\"\']+)', text))
            references.extend(re.findall(r'@import\s+[\"\']([^\"\']+)', text))
        elif file.suffix == '.webmanifest':
            references.extend(icon.get('src') for icon in json.loads(text).get('icons', []))
        elif file.suffix == '.json' and path in {'/assets/fan-show-catalog.json', '/config/artists.json'}:
            def strings(value):
                if isinstance(value, str):
                    yield value
                elif isinstance(value, list):
                    for child in value: yield from strings(child)
                elif isinstance(value, dict):
                    for child in value.values(): yield from strings(child)
            references.extend(s for s in strings(json.loads(text)) if re.search(r'\.(?:webp|jpg|jpeg|png|svg|gif)(?:\?|$)', s, re.I))
        for reference in references:
            try:
                # Registry/catalog JSON stores site-root-relative image names;
                # browsers resolve these through the app's root URL helper.
                base = '/' if file.suffix == '.json' else path
                resource = local_resource(site, base, reference)
                if resource:
                    add(*resource)
            except (ValueError, OSError) as exc:
                errors.append(issue('invalid_resource_reference', path, resource=reference, error=str(exc)))
    if '/404.html' in files:
        files['/__publication-audit-not-found__/'] = dict(files['/404.html'], status=404, kind='not-found')
    else:
        errors.append(issue('missing_error_document', '/404.html'))
    return dict(schemaVersion=1, releaseId=release_id, asOf=day, files=dict(sorted(files.items()))), errors


def verify(site, day, repo=ROOT):
    errors, checks = [], {}
    manifest = json.loads((site / 'url-continuity-manifest.json').read_text())
    catalog = json.loads((site / 'assets/fan-show-catalog.json').read_text())
    sitemap_list = [n.text for n in ET.parse(site / 'sitemap.xml').findall('.//{*}loc')]
    documents = audit_documents(site, manifest['redirects'], set(sitemap_list))
    errors.extend(documents['errors'])
    errors.extend(robots_errors(site, [p for p, facts in documents['pages'].items() if facts['sitemap']]))
    if len(set(sitemap_list)) != len(sitemap_list):
        errors.append(issue('duplicate_sitemap_urls', '/sitemap.xml'))
    ctx = show_information.context(site)
    import publication_inventory
    source_records = publication_inventory.source_records(repo, day)
    for path, record in source_records.items():
        errors.extend(event_fact_errors(path, record, documents['events'].get(path, [])))
        if record.get('private'):
            errors.extend(private_page_errors(path, (site / path.strip('/') / 'index.html').read_text()))
    for path, expected in catalog['artists'].items():
        doc = Document((site / path.strip('/') / 'index.html').read_text())
        configs = [n for n in doc.nodes if n.attrs.get('id') == 'kc-fan-config']
        actual = json.loads(doc.text(configs[0])).get('showPaths', []) if len(configs) == 1 else None
        if actual != expected:
            errors.append(issue('artist_membership_catalog_mismatch', path, expected=expected, actual=actual))
    from private_events import verify_public_feeds
    def private_feeds():
        verify_public_feeds(site, repo)
        return {'currentPrivateCanonicalPages': sum(bool(r.get('private')) for r in source_records.values()),
                'publicFeedAddressesRedacted': True}
    for label, check in (
        ('sourceInventory', lambda: publication_inventory.verify(site, day, repo=repo)),
        ('calendar', lambda: calendar.verify_site(site, day)),
        ('showInformation', lambda: show_information.verify(site, ctx)),
        ('privateEvents', private_feeds),
    ):
        try:
            checks[label] = check()
            if checks[label].get('errors'):
                errors.append(issue('native_check_errors', label, errors=checks[label]['errors']))
        except Exception as exc:
            checks[label] = {'error': str(exc)}
            errors.append(issue('native_check_failure', label, error=str(exc)))
    return dict(htmlPages=len(documents['pages']), sitemapUrls=len(sitemap_list),
                currentEvents=len(catalog['shows']), artistProfilesChecked=len(catalog['artists']),
                schemaTypes=documents['schemaTypes'], checks=checks, errors=errors), set(ctx['paths']) | set(catalog['artists']) | {'/', '/shows/', '/artists/', '/festivals/'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--day', default=calendar.today())
    parser.add_argument('--release-id', required=True)
    parser.add_argument('--report', type=Path, default=Path('publication-audit.json'))
    parser.add_argument('--summary', type=Path, default=Path('publication-audit.md'))
    args = parser.parse_args()
    if not args.release_id.strip():
        parser.error('release-id must be nonempty')
    site = args.site.resolve()
    # A failed rerun must never leave an old acceptance receipt behind.
    (site / MANIFEST).unlink(missing_ok=True)
    report = dict(releaseId=args.release_id, asOf=args.day, checkedAt=datetime.now(timezone.utc).isoformat())
    try:
        result, image_pages = verify(site, args.day, args.source.resolve())
        report.update(result)
        if not report['errors']:
            manifest, errors = build_manifest(site, args.release_id, args.day, image_pages)
            report['errors'].extend(errors)
            resources = [p for p, entry in manifest['files'].items() if entry['kind'] == 'resource']
            report['errors'].extend(robots_errors(site, resources))
            report['errors'].extend(robots_errors(site, [p for p in resources if re.search(r'\.(?:webp|jpg|jpeg|png|svg|gif)$', p, re.I)], 'Googlebot-Image'))
            report['filesChecked'] = len(manifest['files'])
            report['bytesChecked'] = sum(item['size'] for item in manifest['files'].values())
            if not report['errors']:
                (site / MANIFEST).write_text(json.dumps(manifest, separators=(',', ':'), sort_keys=True) + '\n')
    except Exception as exc:
        report.setdefault('errors', []).append(issue('audit_failed', '/', error=f'{type(exc).__name__}: {exc}'))
    report['status'] = 'failed' if report['errors'] else 'passed'
    report['provenance'] = {
        'runId': os.environ.get('GITHUB_RUN_ID'), 'attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
        'pinnedSources': {key: os.environ[key] for key in
                          ('APPROVED_SEO_REF', 'APPROVED_REDESIGN_REF', 'APPROVED_GAME_REF')
                          if key in os.environ},
        'sourceDigests': {name: hashlib.sha256((args.source / name).read_bytes()).hexdigest()
                          for name in ('events.json', 'supplemental-events.json', 'config/artists.json',
                                       'config/event-identity-overrides.json', '_url-continuity-state.json')
                          if (args.source / name).is_file()},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['## Final publication audit: ' + report['status'], '', 'Release: `' + args.release_id + '`', '',
             f"HTML pages: {report.get('htmlPages', 0)}; upcoming shows: {report.get('currentEvents', 0)}; artist profiles: {report.get('artistProfilesChecked', 0)}.", '',
             'Every required check runs after the final page writers. This verifies technical publication, not Google indexing.']
    lines.extend('\n- ' + json.dumps(e, ensure_ascii=False) for e in report['errors'][:50])
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text('\n'.join(lines) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}, indent=2))
    return bool(report['errors'])


if __name__ == '__main__':
    sys.exit(main())
