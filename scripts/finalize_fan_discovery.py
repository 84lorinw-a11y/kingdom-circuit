"""Apply and independently verify the reviewed production discovery layout.

The baseline is the freshly built, fully verified production artifact, not an
older preview snapshot. Keep the baseline outside the uploaded Pages directory.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import shutil

import mobile_discovery as mobile
import national_discovery as national

MANIFEST = 'assets/fan-discovery-manifest.json'
NEW_FILES = {national.ABOUT_PATH, national.WEEKEND_PATH, MANIFEST}
ASSET_FILES = {'assets/' + name for name in (*mobile.ASSETS, *national.ASSETS)}
FORBIDDEN = ('/kingdom-circuit-test/', '84lorinw-a11y.github.io',
             'G-TESTDISABLED', 'G-TEST-DISABLED', 'data-live-mirror', '/test-card-preview/')


def production_identity(site):
    assert (site / 'CNAME').read_text().strip() == 'kingdomcircuit.com', 'Wrong production CNAME'
    robots = (site / 'robots.txt').read_text()
    assert 'Sitemap: https://kingdomcircuit.com/sitemap.xml' in robots
    assert not any(line.strip().lower() == 'disallow: /' for line in robots.splitlines()), 'Production is blocked'
    for relative in ('index.html', national.ABOUT_PATH, national.WEEKEND_PATH):
        if not (site / relative).exists():
            continue
        doc = mobile.Document((site / relative).read_text())
        path = '/' if relative == 'index.html' else '/' + relative.removesuffix('index.html')
        assert doc.one(lambda n: n.tag == 'link' and n.attrs.get('rel') == 'canonical').attrs['href'] == national.SITE_ORIGIN + path
        robots_meta = doc.one(lambda n: n.tag == 'meta' and n.attrs.get('name') == 'robots')
        assert 'noindex' not in robots_meta.attrs['content'].lower(), relative
        assert 'G-N2KK9XF4TJ' in doc.source, f'Production analytics missing: {relative}'
    for path in site.rglob('*'):
        if path.is_file() and path.suffix in ('.html', '.js', '.css'):
            text = path.read_text()
            for forbidden in FORBIDDEN:
                assert forbidden not in text, f'Test leak in {path.relative_to(site)}: {forbidden}'


def verify(site, baseline):
    manifest = json.loads((site / MANIFEST).read_text())
    assert manifest['deploymentEnvironment'] == 'production'
    assert manifest['sourceReview'] == '36be2c60'
    assert manifest['nationalDiscovery']['version'] == national.VERSION
    context = national.load_context(baseline, date.fromisoformat(manifest['nationalDiscovery']['asOfDate']))
    before_files = {p.relative_to(baseline) for p in baseline.rglob('*') if p.is_file()}
    after_files = {p.relative_to(site) for p in site.rglob('*') if p.is_file()}
    assert before_files <= after_files, f'Original files disappeared: {before_files - after_files}'
    assert {p.as_posix() for p in after_files - before_files} <= NEW_FILES | ASSET_FILES, 'Unexpected public files'
    changed = []
    for relative in sorted(before_files):
        before = (baseline / relative).read_bytes()
        expected = national.combined_transform(relative, before, context)
        after = (site / relative).read_bytes()
        assert after == expected, f'Unapproved difference: {relative}'
        if before != after:
            changed.append(relative.as_posix())
    mobile_result = mobile.verify_overlay(baseline, site, national_home=True)
    national_result = national.verify(baseline, site, context)
    production_identity(site)
    return {'productionIdentityVerified': True, 'originalFilesPreserved': len(before_files),
            'originalHtmlPagesPreserved': sum(p.suffix == '.html' for p in before_files),
            'changedFiles': len(changed), 'newPages': [national.ABOUT_PATH, national.WEEKEND_PATH],
            'mobile': mobile_result, 'national': national_result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('site', type=Path)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    site, baseline = args.site.resolve(), args.baseline.resolve()
    assert site != baseline and site not in baseline.parents and baseline not in site.parents, 'Baseline must be outside the public artifact'
    if not args.check:
        assert not baseline.exists(), 'Refusing to overwrite release baseline'
        production_identity(site)
        shutil.copytree(site, baseline)
        mobile.apply(site, baseline)
        national.apply(site, baseline)
    print(json.dumps(verify(site, baseline), indent=2))


if __name__ == '__main__':
    main()
