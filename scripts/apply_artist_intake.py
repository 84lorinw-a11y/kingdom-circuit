"""Restore the approved artist form after imported redesign/refresh passes."""
from pathlib import Path
from html.parser import HTMLParser
import argparse
import hashlib
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
ROUTE = 'submit/artist/index.html'
URL = 'https://kingdomcircuit.com/submit/artist/'
ENDPOINT = 'https://formspree.io/f/mljreawj'
MAIN = re.compile(r'<main\b[^>]*>.*?</main>', re.S)


def version(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def apply(site):
    target = site / ROUTE
    page = target.read_text()
    assert f'href="{URL}"' in page and 'G-N2KK9XF4TJ' in page, 'Expected production artist page'
    main = (ROOT / 'templates/artist-intake.html.tmpl').read_text().strip()
    page, count = MAIN.subn(lambda _: main, page)
    assert count == 1, 'Expected exactly one main element'
    # Preserve production navigation, analytics, CSP, metadata and shared scripts.
    page = re.sub(r'<link\b[^>]*href="/assets/artist-intake\.css\?v=[^"]*"[^>]*>\n?', '', page)
    page = re.sub(r'<script\b[^>]*src="/assets/artist-intake\.js\?v=[^"]*"[^>]*></script>\n?', '', page)
    tags = []
    for ext in ('css', 'js'):
        source = ROOT / f'assets/artist-intake.{ext}'
        shutil.copyfile(source, site / 'assets' / source.name)
        url = f'/assets/{source.name}?v={version(source)}'
        tags.append(f'<link rel="stylesheet" href="{url}">' if ext == 'css' else f'<script defer src="{url}"></script>')
    assert page.count('</head>') == 1
    page = page.replace('</head>', '\n'.join(tags) + '\n</head>')
    target.write_text(page)
    verify(site)


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def verify(site):
    page = (site / ROUTE).read_text()
    assert MAIN.search(page).group() == (ROOT / 'templates/artist-intake.html.tmpl').read_text().strip(), 'Artist form was overwritten'
    parser = Elements()
    parser.feed(page)
    forms = [a for t, a in parser.tags if t == 'form']
    assert len(forms) == 1 and forms[0].get('id') == 'artist-intake-form'
    assert forms[0].get('action') == ENDPOINT and forms[0].get('method') == 'post'
    assert not {'novalidate', 'data-kc-artist-submit-form', 'data-submission-form'} & forms[0].keys()
    fields = {a.get('name'): a for t, a in parser.tags if t in ('input', 'textarea')}
    public = {'artistName', 'submitter_name', 'email', 'photoUrl', 'website', 'instagram', 'spotify', 'youtube'}
    assert set(fields) == public | {'submission_type', 'subject', 'environment', 'page_url'}
    for name, attrs in fields.items():
        assert ('required' in attrs) == (name in {'submitter_name', 'email'})
        assert not {'pattern', 'maxlength'} & attrs.keys()
        assert attrs.get('type', 'text') == ('email' if name == 'email' else 'text' if name in public else 'hidden')
    assert fields['environment']['value'] == 'production'
    assert fields['page_url']['value'] == URL
    assert fields['submission_type']['value'] == 'CHH artist submission'
    assert 'kc-rd-header' in page and 'kc-redesign-v1.js' in page
    assert 'G-N2KK9XF4TJ' in page and f'href="{URL}"' in page
    policies = [a['content'] for t, a in parser.tags if t == 'meta' and a.get('http-equiv', '').lower() == 'content-security-policy']
    assert len(policies) == 1 and "form-action 'self' https://formspree.io" in policies[0]
    for marker in ('kingdom-circuit-test', 'TEST FORM', '[Test site]', 'noindex', 'G-TEST-DISABLED'):
        assert marker not in page, f'Test identity leaked: {marker}'
    for ext in ('css', 'js'):
        source = ROOT / f'assets/artist-intake.{ext}'
        built = site / 'assets' / source.name
        assert built.read_bytes() == source.read_bytes(), f'Outdated {source.name}'
        assert page.count(f'/assets/{source.name}?v={version(source)}') == 1
    print('Production artist intake verified: approved fields, required contacts, flexible profiles, production identity and assets.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('site', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    (verify if args.check else apply)(args.site)
