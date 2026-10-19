"""Reviewed crops for existing artist photos, shared by squares and circles.

Each crop is tied to the optimized asset and its intrinsic dimensions. A new
photo therefore keeps its own default framing until it has been reviewed.
"""
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from mobile_discovery import Document, replace_spans

CROPS = json.loads((Path(__file__).resolve().parents[1] /
                    'config/artist-thumbnail-framing.json').read_text())


def frame_portrait(image, slug):
    crop = CROPS.get(slug)
    if not crop:
        return image
    attrs = Document(image).one(lambda n: n.tag == 'img').attrs
    asset, width, height, position, scale, origin = crop
    if (Path(urlsplit(attrs.get('src', '')).path).name != asset
            or attrs.get('width') != str(width) or attrs.get('height') != str(height)):
        return image
    declarations = [s.strip() for s in attrs.get('style', '').split(';')
                    if s.strip() and s.partition(':')[0].strip() not in
                    ('object-position', 'transform', 'transform-origin')]
    declarations += [f'object-position:{position}', f'transform:scale({scale})',
                     f'transform-origin:{origin}']
    style = 'style="' + escape(';'.join(declarations), quote=True) + '"'
    if 'style' in attrs:
        return re.sub(r'style="[^"]*"', lambda _: style, image, count=1)
    return image.replace('<img ', '<img ' + style + ' ', 1)


def frame_directory(source):
    """Change only portrait framing/resolution; preserve every card and link."""
    doc = Document(source)
    changes = []
    for card in doc.nodes:
        if 'data-artist-card' not in card.attrs:
            continue
        part = Document(doc.raw(card))
        link = part.one(lambda n: n.tag == 'a' and n.has('artist-visual'))
        slug = urlsplit(link.attrs['href']).path.strip('/').split('/')[-1]
        image = part.one(lambda n: n.tag == 'img')
        before = part.raw(image)
        after = frame_portrait(before, slug)
        if 'transform:scale(' in after:
            attrs = Document(after).one(lambda n: n.tag == 'img').attrs
            zoom = float(re.search(r'transform:scale\(([\d.]+)\)', after).group(1))
            zoom *= max(int(attrs['width']) / int(attrs['height']), 1)
            # sizes describes the enlarged source, including cover's wide-image
            # crop. The browser still chooses a suitable existing DPR variant.
            sizes = f'(max-width: 900px) {round(50 * zoom)}vw, {round(270 * zoom)}px'
            after = re.sub(r'sizes="[^"]*"', f'sizes="{sizes}"', after)
        if after != before:
            changes.append((card.start + image.start, card.start + image.end, after))
    return replace_spans(source, changes)
