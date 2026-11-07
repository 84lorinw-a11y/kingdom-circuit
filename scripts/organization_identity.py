"""Label the site's official social profiles after presentation overlays."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from show_information import schema_blocks
from mobile_discovery import replace_spans

ORIGIN = 'https://kingdomcircuit.com'
SOCIALS = ['https://www.instagram.com/thekingdomcircuit/',
           'https://www.facebook.com/profile.php?id=61593510924754']


def organizations(value):
    if isinstance(value, list):
        for child in value: yield from organizations(child)
    elif isinstance(value, dict):
        if value.get('@type') == 'Organization' and str(value.get('url', '')).rstrip('/') == ORIGIN:
            yield value
        for child in value.values():
            if isinstance(child, (dict, list)): yield from organizations(child)


def transform(text):
    changes = []
    for node, value in schema_blocks(text):
        updated = deepcopy(value)
        for organization in organizations(updated):
            previous = organization.get('sameAs', [])
            if isinstance(previous, str): previous = [previous]
            organization['sameAs'] = list(dict.fromkeys([*previous, *SOCIALS]))
        if updated != value:
            changes.append((node.opening_end, node.closing_start,
                json.dumps(updated, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')))
    return replace_spans(text, changes)


def run(site, check=False):
    home = (site / 'index.html').read_text()
    assert any(list(organizations(value)) for _, value in schema_blocks(home)), 'Homepage organization missing'
    changed = 0
    for page in site.rglob('*.html'):
        original = page.read_text()
        updated = transform(original)
        if check:
            assert updated == original, f'Official organization profiles missing: {page}'
        elif updated != original:
            page.write_text(updated)
            changed += 1
    return {'organizationPagesUpdated': changed, 'officialProfiles': SOCIALS}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.site, args.check), indent=2))
