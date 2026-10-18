"""Publish the approved, unlisted game without changing any existing live files."""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
RELEASE = json.loads((ROOT / 'config/chh-game-release.json').read_text())
TEXT = {'.html', '.css', '.mjs'}
SHARE_PATH = 'play/assets/chh-show-night-share-20261018.jpg'


def share_metadata():
    title = 'CHH Show Night | Kingdom Circuit'
    description = 'Bring your crew. Play the artist challenges. Rep the merch. All glory to Jesus.'
    image = 'https://kingdomcircuit.com/' + SHARE_PATH
    values = [('og:type', 'website'), ('og:site_name', 'Kingdom Circuit'),
              ('og:title', title), ('og:description', description),
              ('og:url', 'https://kingdomcircuit.com/play/'), ('og:image', image),
              ('og:image:secure_url', image), ('og:image:type', 'image/jpeg'),
              ('og:image:width', '600'), ('og:image:height', '600'),
              ('og:image:alt', 'CHH Show Night concert scene with Steven, Eli, Joz and the crowd')]
    return ('<meta name="description" content="' + description + '">' +
            ''.join(f'<meta property="{key}" content="{value}">' for key, value in values) +
            '<meta name="twitter:card" content="summary">' +
            f'<meta name="twitter:title" content="{title}">' +
            f'<meta name="twitter:description" content="{description}">' +
            f'<meta name="twitter:image" content="{image}">')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def expected_files(source, release=RELEASE):
    source = Path(source)
    manifest_bytes = (source / 'test-overrides/chh-show-night-manifest.json').read_bytes()
    assert digest(manifest_bytes) == release['manifestSHA256'], 'Approved game manifest pin changed'
    manifest = json.loads(manifest_bytes)
    assert len(manifest) == release['fileCount'], 'Approved inventory changed'
    game = source / 'test-overrides/chh-show-night'
    actual = {p.relative_to(game).as_posix() for p in game.rglob('*') if p.is_file()}
    assert actual == set(manifest), 'Unexpected or missing game source files'
    expected = {}
    for name, sha in manifest.items():
        relative = PurePosixPath(name)
        assert not relative.is_absolute() and '..' not in relative.parts, 'Unsafe game path'
        assert relative.suffix in TEXT | {'.webp', '.png', '.m4a'}, 'Unexpected file type'
        path = game / name
        assert not path.is_symlink(), 'Game sources may not be symlinks'
        data = path.read_bytes()
        assert digest(data) == sha, 'Game source mismatch: ' + name
        if relative.suffix in TEXT:
            text = data.decode('utf-8')
            # Only remove test labels. Preserve gameplay, endpoint, paths and media.
            text = text.replace(' · TEST PREVIEW', '').replace('Kingdom Circuit Test', 'Kingdom Circuit')
            if name == 'index.html' and release.get('shareImageSHA256'):
                text = text.replace('</title>', '</title>' + share_metadata(), 1)
            assert not any(marker in text for marker in ('TEST PREVIEW', 'G-TEST-DISABLED', '/kingdom-circuit-test/', 'PLAY_PASSWORD', '/api/login'))
            data = text.encode('utf-8')
        expected['play/' + name] = data
    if release.get('shareImageSHA256'):
        share = (ROOT / 'game-release/chh-show-night-share-20261018.jpg').read_bytes()
        assert digest(share) == release['shareImageSHA256'], 'Share image changed'
        assert share.startswith(b'\xff\xd8\xff'), 'Share image must be JPEG'
        expected[SHARE_PATH] = share
    return expected


def inventory(site, exclude_game=False):
    return {p.relative_to(site).as_posix(): digest(p.read_bytes())
            for p in site.rglob('*') if p.is_file()
            and not (exclude_game and p.relative_to(site).parts[0] == 'play')}


def verify(site, source, baseline, release=RELEASE):
    site, baseline = Path(site), Path(baseline)
    expected = expected_files(source, release)
    before = json.loads(baseline.read_text())
    current = inventory(site)
    assert set(current) == set(before) | set(expected), 'Unexpected live artifact additions/removals'
    assert inventory(site, exclude_game=True) == before, 'An existing live file changed'
    for name, data in expected.items():
        assert (site / name).read_bytes() == data, 'Published game mismatch: ' + name
        if Path(name).suffix in TEXT:
            text = data.decode()
            for ref in re.findall(r'''(?:from\s+|(?:href|src)=)["'](\.[^"']+|/play/[^"']+)''', text):
                ref = ref.split('?')[0].split('#')[0]
                target = site / ref.lstrip('/') if ref.startswith('/') else (site / name).parent / ref
                assert target.is_file(), 'Missing game dependency: ' + ref
    page = (site / 'play/index.html').read_text()
    assert '<meta name="robots" content="noindex,nofollow">' in page
    assert '<meta name="score-service" content="https://script.google.com/macros/s/' in page
    assert 'Content-Security-Policy' in page and 'https://script.googleusercontent.com' in page
    assert 'type="password"' not in page
    if release.get('shareImageSHA256'):
        assert share_metadata() in page and (site / SHARE_PATH).is_file(), 'Share preview missing'
    for name in before:
        if Path(name).suffix in {'.html', '.xml'}:
            text = (site / name).read_text()
            assert not re.search(r'''["'>](?:https://kingdomcircuit\.com)?/play(?:/|["'<])''', text), 'Game unexpectedly linked: ' + name
    return {'url': 'https://kingdomcircuit.com/play/', 'gameFiles': len(expected),
            'existingFilesByteIdentical': len(before), 'passwordRequired': False,
            'directLinkOnly': True, 'approvedSource': release['sourceCommit']}


def build(site, source, baseline, release=RELEASE):
    site, baseline = Path(site), Path(baseline)
    assert (site / 'CNAME').read_text().strip() == 'kingdomcircuit.com', 'Production host required'
    assert not (site / 'play').exists(), 'Do not overwrite an existing live route'
    assert site.resolve() not in baseline.resolve().parents, 'Baseline must stay outside the published artifact'
    expected = expected_files(source, release)
    baseline.write_text(json.dumps(inventory(site), sort_keys=True) + '\n')
    for name, data in expected.items():
        target = site / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return verify(site, source, baseline, release)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('site', type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps((verify if args.check else build)(args.site, args.source, args.baseline), indent=2))
