from __future__ import annotations

import html
import pathlib
import re


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _shorten(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    clipped = text[: limit + 1].rsplit(" ", 1)[0].rstrip(" -–—:|,")
    return clipped or text[:limit].rstrip()


def _replace_title(text: str) -> str:
    match = re.search(r"<title>(.*?)</title>", text, flags=re.I | re.S)
    if not match:
        return text
    current = _plain(match.group(1))
    if len(current) <= 60:
        return text

    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", text, flags=re.I | re.S)
    if not h1:
        return text
    topic = _plain(h1.group(1))
    suffix = " | Kingdom Circuit"
    replacement = _shorten(topic, 60 - len(suffix)) + suffix
    escaped = html.escape(replacement, quote=False)
    text = text[: match.start(1)] + escaped + text[match.end(1) :]

    og = re.search(r'<meta property="og:title" content="([^"]*)">', text, flags=re.I)
    if og:
        text = text[: og.start(1)] + html.escape(replacement, quote=True) + text[og.end(1) :]
    return text


def _trim_meta_description(text: str) -> str:
    match = re.search(r'<meta name="description" content="([^"]*)">', text, flags=re.I)
    if not match:
        return text
    current = html.unescape(match.group(1))
    if len(current) <= 155:
        return text
    replacement = html.escape(_shorten(current, 155), quote=True)
    return text[: match.start(1)] + replacement + text[match.end(1) :]


def _enrich_past_page(text: str) -> str:
    marker = '<p class="eyebrow">Past show</p>'
    if marker not in text or 'data-seo-past-context' in text:
        return text

    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", text, flags=re.I | re.S)
    title = _plain(h1.group(1)) if h1 else "this event"
    city_match = re.search(r"<dt>Location</dt><dd>(.*?)</dd>", text, flags=re.I | re.S)
    location = _plain(city_match.group(1)) if city_match else "the listed location"
    artist_match = re.search(r'<p class="artist-line">(.*?)</p>', text, flags=re.I | re.S)
    artists = _plain(artist_match.group(1)) if artist_match else "the listed artists"

    block = (
        '<section class="page-section past-event-context" data-seo-past-context>'
        '<h2>About this archived show</h2>'
        f'<p>This page preserves the verified Kingdom Circuit listing for {html.escape(title)} in {html.escape(location)}. '
        f'The archived lineup included {html.escape(artists)}. Keeping past event pages available helps fans confirm concert history, '
        'venues, dates, and previously announced lineups without confusing completed events with the current live calendar.</p>'
        '<p>Looking for a current Christian hip-hop concert instead? Use the upcoming-shows links on this page or browse the full '
        'Kingdom Circuit calendar. New listings are added as official artist, venue, promoter, festival, and ticketing sources are '
        'verified. Before making travel plans or buying tickets for any future event, always confirm the latest date, venue, lineup, '
        'availability, and admission details with the official organizer or ticket provider.</p>'
        '</section>'
    )
    return text.replace('</article></section></main>', '</article>' + block + '</section></main>', 1)


def apply_seo_audit_fixes(root: pathlib.Path) -> dict[str, int]:
    root = root.resolve()
    changed = 0
    enriched = 0
    titles = 0
    metas = 0

    home = root / "index.html"
    if home.is_file():
        text = home.read_text(encoding="utf-8", errors="ignore")
        old = text
        text = re.sub(
            r"<title>Christian Hip-Hop Shows, Concerts &amp; Festivals \| Kingdom Circuit</title>",
            "<title>Christian Hip-Hop Shows &amp; Festivals | Kingdom Circuit</title>",
            text,
            count=1,
        )
        if text != old:
            home.write_text(text, encoding="utf-8")
            changed += 1
            titles += 1

    event_root = root / "event"
    if event_root.is_dir():
        for page in event_root.glob("*/index.html"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            original = text
            before_title = text
            text = _replace_title(text)
            if text != before_title:
                titles += 1
            before_meta = text
            text = _trim_meta_description(text)
            if text != before_meta:
                metas += 1
            before_context = text
            text = _enrich_past_page(text)
            if text != before_context:
                enriched += 1
            if text != original:
                page.write_text(text, encoding="utf-8")
                changed += 1

    return {"pagesChanged": changed, "pastPagesEnriched": enriched, "titlesShortened": titles, "metaDescriptionsTrimmed": metas}
