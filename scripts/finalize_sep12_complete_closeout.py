#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import pathlib
import re
import shutil
from urllib.parse import quote

BASE_URL = "https://kingdomcircuit.com"
FALLBACK = "/assets/event-fallback.webp"

PRIVATE_OR_UNCONFIRMED_IDS = {
    "manual:egr-2026-09-12-corpus-christi-tx",
}

ARTWORK_REPLACEMENTS = {
    ("Fountain Fest WV 2026", "2026-09-18"): {
        "image": "https://i0.wp.com/fountainfestwv.com/wp-content/uploads/2026/07/Rare-of-Breed-Promo-.webp?resize=720%2C900&ssl=1",
        "imageType": "event_artwork",
        "source": "Fountain Fest WV official performer promotion",
        "sourceUrl": "https://fountainfestwv.com/",
        "classification": 1,
    },
    ("Jay Kalyl — Desde Antes Tour", "2026-10-03"): {
        "image": "https://i.scdn.co/image/ab6761610000e5eb1269b80aed5d08c40aedfdc3",
        "imageType": "artist",
        "source": "Jay Kalyl verified Spotify artist profile",
        "sourceUrl": "https://open.spotify.com/",
        "classification": 3,
    },
    ("Boxyard Saturdaze", "2026-10-10"): {
        "image": "https://ugc.production.linktr.ee/1c7876eb-77d1-4a43-a2db-def6b24563ac_1000010882.jpeg",
        "imageType": "artist",
        "source": "MAYIA official Linktree",
        "sourceUrl": "https://linktr.ee/mayiawarren",
        "classification": 3,
    },
    ("MAYIA at the NC State Fair", "2026-10-17"): {
        "image": "https://ugc.production.linktr.ee/1c7876eb-77d1-4a43-a2db-def6b24563ac_1000010882.jpeg",
        "imageType": "artist",
        "source": "MAYIA official Linktree",
        "sourceUrl": "https://linktr.ee/mayiawarren",
        "classification": 3,
    },
    ("Alex Zurdo: Zona Zero", "2026-10-18"): {
        "image": "https://i.scdn.co/image/ab6761610000e5eb2c81bb40c3b6962eacf9dc9c",
        "imageType": "artist",
        "source": "Alex Zurdo verified Spotify artist profile",
        "sourceUrl": "https://open.spotify.com/",
        "classification": 3,
    },
    ("The Kickback", "2026-11-14"): {
        "image": "https://ugc.production.linktr.ee/e2e0b25c-780f-4b6f-9a4d-48461885e719_DSC01908.jpeg",
        "imageType": "artist",
        "source": "CJ Emulous official Linktree",
        "sourceUrl": "https://linktr.ee/cjemulous",
        "classification": 3,
    },
    ("Miles Minnick & CJ Emulous at Zion Ultra Lounge", "2026-12-05"): {
        "image": "https://i.scdn.co/image/ab6761610000e5eb88d578e199bd2ce1021def5b",
        "imageType": "artist",
        "source": "Miles Minnick verified Spotify artist profile",
        "sourceUrl": "https://open.spotify.com/",
        "classification": 3,
    },
    ("Mission and Special Guests", "2026-10-17"): {
        "image": "assets/artists/mission-primary.jpg",
        "imageType": "artist",
        "source": "Mission official YouTube channel",
        "sourceUrl": "https://www.youtube.com/channel/UCBaU_Xh4fyokc-ckyCeYv3w",
        "classification": 3,
    },
}

FAKE_ASSETS = {
    "/assets/events/miles-cj-zion-ultra-2026.svg",
    "/assets/events/fountain-fest-wv-2026.svg",
    "/assets/events/mission-friends-sacramento-2026.svg",
    "/assets/events/mayia-boxyard-saturdaze-2026.svg",
    "/assets/events/mayia-nc-state-fair-2026.svg",
    "/assets/events/cj-emulous-kickback-2026.svg",
    "/assets/events/alex-zurdo-zona-zero-2026.svg",
    "/assets/events/jay-kalyl-desde-antes-2026.svg",
}


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or "")).replace("’", "'")).strip().casefold()


def load_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def write_json(path: pathlib.Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def event_key(event: dict) -> tuple[str, str]:
    return str(event.get("title") or ""), str(event.get("startDate") or "")[:10]


def is_daytime_808_unconfirmed(event: dict) -> bool:
    artists = [norm(x) for x in event.get("artists") or []]
    if "808 beezy" not in artists or "rwg tour 2026" not in norm(event.get("title")):
        return False
    time = str(event.get("startTime") or "")
    match = re.match(r"^(\d{1,2}):(\d{2})", time)
    return bool(match and int(match.group(1)) < 16)


def should_hide_public(event: dict) -> bool:
    return str(event.get("id") or "") in PRIVATE_OR_UNCONFIRMED_IDS or is_daytime_808_unconfirmed(event)


def public_src(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return FALLBACK
    if raw.startswith(("https://", "http://", "/")):
        return raw
    return "/" + raw.lstrip("/")


def abs_src(value: object) -> str:
    src = public_src(value)
    if src.startswith("http://"):
        return "https://" + src[7:]
    if src.startswith("https://"):
        return src
    return BASE_URL + src


def event_path(event: dict) -> str:
    from build_seo_site import event_path as canonical_event_path
    return canonical_event_path(event).strip("/")


def remove_hidden_events(root: pathlib.Path, source_events: list[dict]) -> dict:
    hidden = [e for e in source_events if should_hide_public(e)]
    hidden_ids = {str(e.get("id") or "") for e in hidden}
    hidden_slugs = {event_path(e).split("/")[-1] for e in hidden}
    json_removed = 0
    for rel in ("events.json", "supplemental-events.json"):
        path = root / rel
        rows = load_json(path)
        if not isinstance(rows, list):
            continue
        kept = [e for e in rows if not (isinstance(e, dict) and str(e.get("id") or "") in hidden_ids)]
        json_removed += len(rows) - len(kept)
        if len(kept) != len(rows):
            write_json(path, kept)

    pages_removed = 0
    for slug in hidden_slugs:
        target = root / "event" / slug
        if target.exists():
            shutil.rmtree(target)
            pages_removed += 1

    card_removed = 0
    card_re = re.compile(r'<article\b(?=[^>]*class="[^"]*\bevent-card\b[^"]*")[^>]*>.*?</article>', re.I | re.S)
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        original = text
        def repl(match: re.Match[str]) -> str:
            nonlocal card_removed
            block = match.group(0)
            if any(f"/event/{slug}/" in block for slug in hidden_slugs):
                card_removed += 1
                return ""
            return block
        text = card_re.sub(repl, text)
        if text != original:
            page.write_text(text, encoding="utf-8")

    sitemap = root / "sitemap.xml"
    sitemap_removed = 0
    if sitemap.exists():
        text = sitemap.read_text(encoding="utf-8")
        for slug in hidden_slugs:
            text, count = re.subn(rf"\s*<url>.*?<loc>{re.escape(BASE_URL + '/event/' + slug + '/')}</loc>.*?</url>", "", text, flags=re.S)
            sitemap_removed += count
        sitemap.write_text(text, encoding="utf-8")

    return {
        "sourceRecordsPreserved": len(hidden),
        "publicJsonRowsRemoved": json_removed,
        "publicPagesRemoved": pages_removed,
        "publicCardsRemoved": card_removed,
        "sitemapEntriesRemoved": sitemap_removed,
        "hiddenIds": sorted(hidden_ids),
    }


def replace_attr(tag: str, name: str, value: str) -> str:
    escaped = html.escape(value, quote=True)
    pattern = rf'\s+{re.escape(name)}=(["\']).*?\1'
    if re.search(pattern, tag, flags=re.I | re.S):
        return re.sub(pattern, f' {name}="{escaped}"', tag, count=1, flags=re.I | re.S)
    return tag[:-1] + f' {name}="{escaped}">'


def remove_attr(tag: str, name: str) -> str:
    return re.sub(rf'\s+{re.escape(name)}=(["\']).*?\1', "", tag, flags=re.I | re.S)


def patch_image_tag(tag: str, src: str, image_type: str, *, detail: bool = False, artist_key: str = "") -> str:
    src = public_src(src)
    tag = replace_attr(tag, "src", src)
    tag = replace_attr(tag, "loading", "eager" if detail else "lazy")
    tag = replace_attr(tag, "decoding", "async")
    tag = replace_attr(tag, "width", "1200")
    tag = replace_attr(tag, "height", "675")
    tag = replace_attr(tag, "sizes", "(max-width: 900px) 100vw, 42vw" if detail else "(max-width: 900px) 100vw, 320px")
    tag = replace_attr(tag, "srcset", f"{src} 1200w")
    if src.startswith("http"):
        tag = replace_attr(tag, "referrerpolicy", "no-referrer")
    else:
        tag = remove_attr(tag, "referrerpolicy")
    if artist_key:
        tag = replace_attr(tag, "data-artist-key", artist_key)
    for old in ("data-kc-event-artist", "data-kc-image-index", "data-kc-lock-primary", "data-kc-primary-locked"):
        tag = remove_attr(tag, old)
    tag = remove_attr(tag, "onerror")
    fallback = html.escape(FALLBACK, quote=True)
    tag = tag[:-1] + f''' onerror="if(!this.dataset.kcFallbackUsed){{this.dataset.kcFallbackUsed='1';this.src='{fallback}';this.removeAttribute('srcset');}}else{{this.onerror=null;}}">'''
    classes = re.search(r'class=(["\'])(.*?)\1', tag, flags=re.I | re.S)
    wanted = "event-artwork" if image_type == "event_artwork" else "artist-photo"
    if image_type == "fallback":
        wanted = "event-artwork"
    if classes:
        values = [c for c in classes.group(2).split() if c not in {"event-artwork", "artist-photo"}]
        values.append(wanted)
        tag = tag[:classes.start()] + f'class="{" ".join(values)}"' + tag[classes.end():]
    else:
        tag = tag[:-1] + f' class="{wanted}">'
    return tag


def apply_artwork_replacements(root: pathlib.Path, source_events: list[dict]) -> dict:
    replacements = 0
    for rel in ("events.json", "supplemental-events.json"):
        path = root / rel
        rows = load_json(path)
        if not isinstance(rows, list):
            continue
        changed = False
        for e in rows:
            if not isinstance(e, dict):
                continue
            rep = ARTWORK_REPLACEMENTS.get(event_key(e))
            if not rep:
                continue
            e["image"] = rep["image"]
            e["imageType"] = rep["imageType"]
            e["imagePosition"] = "center"
            e["imageOverride"] = rep["imageType"] != "fallback"
            e["imageSourceName"] = rep["source"]
            e["imageSourceUrl"] = rep["sourceUrl"]
            changed = True
            replacements += 1
        if changed:
            write_json(path, rows)

    card_re = re.compile(r'<article\b(?=[^>]*class="[^"]*\bevent-card\b[^"]*")[^>]*>.*?</article>', re.I | re.S)
    html_replacements = 0
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        original = text
        def card_repl(match: re.Match[str]) -> str:
            nonlocal html_replacements
            block = match.group(0)
            title_m = re.search(r"<h3\b[^>]*>(.*?)</h3>", block, re.I | re.S)
            date_m = re.search(r'data-date=["\']([^"\']+)["\']', block, re.I)
            if not title_m:
                return block
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(title_m.group(1)))).strip()
            date = date_m.group(1)[:10] if date_m else ""
            rep = ARTWORK_REPLACEMENTS.get((title, date))
            if not rep:
                return block
            artist_line = re.search(r'<p\b[^>]*class="[^"]*\bartist-line\b[^"]*"[^>]*>(.*?)</p>', block, re.I | re.S)
            artist_key = ""
            if artist_line:
                names = re.findall(r"<a\b[^>]*>(.*?)</a>", artist_line.group(1), re.I | re.S)
                if names:
                    artist_key = norm(re.sub(r"<[^>]+>", " ", html.unescape(names[0])))
            updated, n = re.subn(r"<img\b[^>]*>", lambda m: patch_image_tag(m.group(0), rep["image"], rep["imageType"], artist_key=artist_key), block, count=1, flags=re.I)
            html_replacements += n
            return updated
        text = card_re.sub(card_repl, text)

        if page.parent.parent == root / "event":
            h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, re.I | re.S)
            if h1:
                title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h1.group(1)))).strip()
                rep = next((r for (t, _d), r in ARTWORK_REPLACEMENTS.items() if norm(t) == norm(title)), None)
                if rep:
                    media = re.search(r'(<div\b[^>]*class="[^"]*\bevent-detail-media\b[^"]*"[^>]*>\s*)(?:<a\b[^>]*>\s*)?(<img\b[^>]*>)(?:\s*</a>)?', text, re.I | re.S)
                    if media:
                        image = patch_image_tag(media.group(2), rep["image"], rep["imageType"], detail=True)
                        href = html.escape(public_src(rep["image"]), quote=True)
                        replacement = media.group(1) + f'<a class="event-image-enlarge" href="{href}" target="_blank" rel="noopener" aria-label="Open full-size event image">{image}</a>'
                        text = text[:media.start()] + replacement + text[media.end():]
                        html_replacements += 1
        if text != original:
            page.write_text(text, encoding="utf-8")

    fake_refs = []
    for page in root.rglob("*.html"):
        text = html.unescape(page.read_text(encoding="utf-8", errors="ignore"))
        for asset in FAKE_ASSETS:
            if asset in text:
                fake_refs.append(f"{page.relative_to(root)}:{asset}")
    if fake_refs:
        raise SystemExit("Fabricated event artwork still referenced: " + " | ".join(fake_refs[:20]))
    return {"jsonRecordsReplaced": replacements, "htmlImagesReplaced": html_replacements}


def enhance_all_images(root: pathlib.Path) -> dict:
    images = 0
    details_linked = 0
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        original = text
        def img_repl(m: re.Match[str]) -> str:
            nonlocal images
            tag = m.group(0)
            srcm = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, re.I)
            if not srcm:
                return tag
            src = html.unescape(srcm.group(1))
            if "/assets/logo" in src or "favicon" in src:
                return tag
            detail = "event-detail-media" in text[max(0, m.start()-220):m.start()]
            image_type = "event_artwork" if "event-artwork" in tag else ("fallback" if "event-fallback" in src else "artist")
            keym = re.search(r'data-artist-key=["\']([^"\']+)["\']', tag, re.I)
            key = keym.group(1) if keym else ""
            images += 1
            return patch_image_tag(tag, src, image_type, detail=detail, artist_key=key)
        text = re.sub(r"<img\b[^>]*>", img_repl, text, flags=re.I)
        if page.parent.parent == root / "event":
            pattern = re.compile(r'(<div\b[^>]*class="[^"]*\bevent-detail-media\b[^"]*"[^>]*>\s*)(<img\b[^>]*>)(\s*</div>)', re.I | re.S)
            def wrap(m: re.Match[str]) -> str:
                nonlocal details_linked
                tag = m.group(2)
                srcm = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, re.I)
                if not srcm:
                    return m.group(0)
                details_linked += 1
                href = html.escape(html.unescape(srcm.group(1)), quote=True)
                return m.group(1) + f'<a class="event-image-enlarge" href="{href}" target="_blank" rel="noopener" aria-label="Open full-size event image">{tag}</a>' + m.group(3)
            text = pattern.sub(wrap, text, count=1)
        if text != original:
            page.write_text(text, encoding="utf-8")
    return {"imagesEnhanced": images, "detailImagesLinked": details_linked}


def meta_content(text: str, name: str = "", prop: str = "") -> str:
    key = prop or name
    attr = "property" if prop else "name"
    m = re.search(rf'<meta\s+{attr}=["\']{re.escape(key)}["\']\s+content=["\']([^"\']*)["\']', text, re.I)
    return html.unescape(m.group(1)) if m else ""


def set_meta(text: str, *, name: str = "", prop: str = "", content: str) -> str:
    escaped = html.escape(content, quote=True)
    key = prop or name
    attr = "property" if prop else "name"
    pattern = rf'<meta\s+(?:property|name)=["\']{re.escape(key)}["\']\s+content=["\'][^"\']*["\']\s*/?>'
    tag = f'<meta {attr}="{key}" content="{escaped}">'
    if re.search(pattern, text, re.I):
        return re.sub(pattern, tag, text, count=1, flags=re.I)
    return re.sub(r"</head>", tag + "\n</head>", text, count=1, flags=re.I)


def canonical_url(text: str, page: pathlib.Path, root: pathlib.Path) -> str:
    m = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', text, re.I)
    if m:
        return html.unescape(m.group(1))
    rel = page.relative_to(root).as_posix()
    if rel == "index.html":
        return BASE_URL + "/"
    if rel.endswith("/index.html"):
        return BASE_URL + "/" + rel[:-10]
    return BASE_URL + "/" + rel


def metadata_and_schema(root: pathlib.Path) -> dict:
    pages = 0
    breadcrumb_removed = 0
    jsonld_pattern = re.compile(r'(<script[^>]+type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)', re.I | re.S)
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        original = text
        title_m = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
        title = re.sub(r"\s+", " ", html.unescape(title_m.group(1))).strip() if title_m else "The Kingdom Circuit"
        desc = meta_content(text, name="description") or "Christian hip-hop shows, festivals, artists and live events."
        url = canonical_url(text, page, root)
        image_m = re.search(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', text, re.I | re.S)
        image = abs_src(image_m.group(1)) if image_m else BASE_URL + FALLBACK
        text = set_meta(text, prop="og:title", content=title)
        text = set_meta(text, prop="og:description", content=desc)
        text = set_meta(text, prop="og:url", content=url)
        text = set_meta(text, prop="og:image", content=image)
        text = set_meta(text, name="twitter:card", content="summary_large_image")
        text = set_meta(text, name="twitter:title", content=title)
        text = set_meta(text, name="twitter:description", content=desc)
        text = set_meta(text, name="twitter:image", content=image)

        breadcrumb_seen = False
        def jsonld_repl(m: re.Match[str]) -> str:
            nonlocal breadcrumb_seen, breadcrumb_removed
            try:
                payload = json.loads(m.group(2))
            except json.JSONDecodeError:
                return m.group(0)
            def fix(obj):
                nonlocal breadcrumb_seen, breadcrumb_removed
                if isinstance(obj, list):
                    out = []
                    for item in obj:
                        fixed = fix(item)
                        if fixed is not None:
                            out.append(fixed)
                    return out
                if not isinstance(obj, dict):
                    return obj
                typ = obj.get("@type")
                if typ == "BreadcrumbList":
                    if breadcrumb_seen:
                        breadcrumb_removed += 1
                        return None
                    breadcrumb_seen = True
                if "image" in obj:
                    if isinstance(obj["image"], list):
                        obj["image"] = [abs_src(v) for v in obj["image"]]
                    elif isinstance(obj["image"], str):
                        obj["image"] = abs_src(obj["image"])
                if obj.get("eventStatus") == "https://schema.org/EventCompleted":
                    obj.pop("eventStatus", None)
                loc = obj.get("location")
                if isinstance(loc, dict):
                    if norm(loc.get("name")) == norm(obj.get("name")):
                        loc.pop("name", None)
                    addr = loc.get("address")
                    if isinstance(addr, dict):
                        for k in list(addr):
                            if not str(addr[k] or "").strip():
                                addr.pop(k, None)
                for k, v in list(obj.items()):
                    if isinstance(v, (list, dict)):
                        fixed = fix(v)
                        if fixed is None:
                            obj.pop(k, None)
                        else:
                            obj[k] = fixed
                return obj
            payload = fix(payload)
            if payload is None or payload == []:
                return ""
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
            return m.group(1) + encoded + m.group(3)
        text = jsonld_pattern.sub(jsonld_repl, text)
        if text != original:
            page.write_text(text, encoding="utf-8")
            pages += 1
    return {"pagesUpdated": pages, "duplicateBreadcrumbsRemoved": breadcrumb_removed}


ACCESSIBILITY_JS = r''' "use strict";
(() => {
  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => [...r.querySelectorAll(s)];
  function setupDrawer() {
    const opener = $(".menu-toggle"), drawer = $(".menu-drawer"), closer = $(".menu-close"), backdrop = $(".menu-backdrop");
    if (!opener || !drawer || !closer) return;
    let returnFocus = opener;
    const links = $$(".menu-links a", drawer);
    const setClosed = (closed) => {
      drawer.inert = closed;
      drawer.setAttribute("aria-hidden", closed ? "true" : "false");
      [...links, closer].forEach(el => closed ? el.setAttribute("tabindex","-1") : el.removeAttribute("tabindex"));
    };
    const open = () => {
      returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : opener;
      drawer.classList.add("open"); document.body.classList.add("menu-open");
      opener.setAttribute("aria-expanded","true"); if (backdrop) backdrop.hidden=false;
      setClosed(false); requestAnimationFrame(() => closer.focus());
    };
    const close = () => {
      drawer.classList.remove("open"); document.body.classList.remove("menu-open");
      opener.setAttribute("aria-expanded","false"); if (backdrop) backdrop.hidden=true;
      setClosed(true); if (returnFocus?.focus) returnFocus.focus();
    };
    setClosed(!drawer.classList.contains("open"));
    opener.addEventListener("click", e => { e.preventDefault(); e.stopImmediatePropagation(); open(); }, true);
    closer.addEventListener("click", e => { e.preventDefault(); e.stopImmediatePropagation(); close(); }, true);
    backdrop?.addEventListener("click", e => { e.preventDefault(); e.stopImmediatePropagation(); close(); }, true);
    document.addEventListener("keydown", e => { if (e.key==="Escape" && drawer.classList.contains("open")) { e.preventDefault(); close(); }});
  }
  function setupFilters() {
    const count=$(".results-count"); if(count){count.setAttribute("role","status");count.setAttribute("aria-live","polite");count.setAttribute("aria-atomic","true");}
    $$(".filter-chip").forEach(chip => {
      const sync=()=>chip.setAttribute("aria-pressed",chip.classList.contains("active")?"true":"false");
      sync(); new MutationObserver(sync).observe(chip,{attributes:true,attributeFilter:["class"]});
      chip.addEventListener("click",()=>requestAnimationFrame(()=>{sync();chip.focus();}));
    });
  }
  function correctionPrefill() {
    const form=$("[data-submission-form]"); if(!form) return;
    const p=new URLSearchParams(location.search); if((p.get("type")||"").toLowerCase()!=="correction") return;
    const kind=$("[data-submission-kind]",form); if(kind) kind.value="Correction";
    $$("[data-submission-mode]",form).forEach(btn=>{const a=btn.getAttribute("data-submission-mode")==="Correction";btn.classList.toggle("active",a);btn.setAttribute("aria-pressed",a?"true":"false");});
    const name=$('[name="event_name"]',form), official=$('[name="official_url"]',form), details=$('[name="details"]',form);
    if(name){name.value=p.get("event")||"";name.readOnly=true;}
    if(official){official.value=p.get("url")||"";official.readOnly=true;}
    ["date","local_time","venue","city","state","artist_lineup","artwork_url","relationship"].forEach(n=>{const f=$(`[name="${n}"]`,form);if(!f)return;f.required=false;const l=f.closest("label");if(l)l.hidden=true;});
    if(details){details.required=true;const s=details.closest("label")?.querySelector("span");if(s)s.textContent="What needs to be corrected? Include a supporting source.";}
    const id=p.get("event_id");if(id){let h=$('[name="event_id"]',form);if(!h){h=document.createElement("input");h.type="hidden";h.name="event_id";form.append(h);}h.value=id;}
  }
  setupDrawer(); setupFilters(); correctionPrefill();
})();'''

ACCESSIBILITY_CSS = r'''
.field span,.check-field,.event-meta dt,.detail-list dt,.source-line,.price-line,.results-count,.form-note,.form-feedback,.profile-count,.disclaimer,.trust-line{color:#b8b4ac}
.primary-button:hover,.official-button:hover,.secondary-button:hover{background:#d3a552;color:#080808}
:focus-visible{outline:3px solid #e3b75d;outline-offset:3px}
.event-image-enlarge{display:block;width:100%;height:100%}
.event-image-enlarge img{width:100%;height:100%}
'''


def install_accessibility(root: pathlib.Path) -> dict:
    (root / "assets").mkdir(parents=True, exist_ok=True)
    (root / "assets/sep12-closeout.js").write_text(ACCESSIBILITY_JS + "\n", encoding="utf-8")
    (root / "assets/sep12-closeout.css").write_text(ACCESSIBILITY_CSS + "\n", encoding="utf-8")
    pages = corrections = put_us_on = 0
    event_rows = []
    for rel in ("events.json", "supplemental-events.json"):
        v = load_json(root / rel)
        if isinstance(v, list):
            event_rows.extend(e for e in v if isinstance(e, dict))
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        original = text
        if "/assets/sep12-closeout.css" not in text:
            text = re.sub(r"</head>", '<link rel="stylesheet" href="/assets/sep12-closeout.css">\n</head>', text, count=1, flags=re.I)
        if "/assets/sep12-closeout.js" not in text:
            text = re.sub(r"</body>", '<script src="/assets/sep12-closeout.js" defer></script>\n</body>', text, count=1, flags=re.I)
        text = re.sub(r'(<nav\b[^>]*class=["\'][^"\']*\bmenu-drawer\b[^"\']*["\'][^>]*)(>)', lambda m: m.group(1) + ('' if re.search(r'\binert\b', m.group(1)) else ' inert') + m.group(2), text, count=1, flags=re.I)
        def chip(m: re.Match[str]) -> str:
            tag = m.group(0)
            pressed = "true" if re.search(r'class=["\'][^"\']*\bactive\b', tag, re.I) else "false"
            return replace_attr(tag, "aria-pressed", pressed)
        text = re.sub(r'<button\b(?=[^>]*class=["\'][^"\']*\bfilter-chip\b)[^>]*>', chip, text, flags=re.I)
        text = re.sub(r'<[^>]+class=["\'][^"\']*\bresults-count\b[^"\']*["\'][^>]*>', lambda m: replace_attr(replace_attr(replace_attr(m.group(0), "role", "status"), "aria-live", "polite"), "aria-atomic", "true"), text, flags=re.I)
        if page.parent.parent == root / "event":
            h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, re.I | re.S)
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h1.group(1)))).strip() if h1 else ""
            match = next((e for e in event_rows if norm(e.get("title")) == norm(title) and event_path(e) == str(page.parent.relative_to(root)).replace("\\", "/")), None)
            if match and "Suggest a correction" not in text:
                url = canonical_url(text, page, root)
                href = "/submit/?type=correction&event=" + quote(title) + "&url=" + quote(url, safe="") + "&event_id=" + quote(str(match.get("id") or ""))
                text = text.replace("</article>", f'<p class="event-correction"><a class="text-link" href="{html.escape(href, quote=True)}">Suggest a correction</a></p></article>', 1)
                corrections += 1
        if page.relative_to(root).as_posix() == "artists/index.html" and "Put Us On" not in text:
            text = text.replace("</section>", '<p><a class="secondary-button" href="/submit/?type=artist">Put Us On</a></p></section>', 1)
            put_us_on += 1
        if text != original:
            page.write_text(text, encoding="utf-8")
            pages += 1
    return {"pagesEnhanced": pages, "correctionLinks": corrections, "putUsOnTriggers": put_us_on}


def classify_image(event: dict) -> tuple[int, str, str]:
    key = event_key(event)
    if key in ARTWORK_REPLACEMENTS:
        r = ARTWORK_REPLACEMENTS[key]
        return int(r["classification"]), str(r["source"]), str(r["sourceUrl"])
    img = public_src(event.get("image"))
    typ = str(event.get("imageType") or "")
    source = str(event.get("imageSourceName") or event.get("sourceName") or "")
    source_url = str(event.get("imageSourceUrl") or event.get("officialUrl") or event.get("ticketUrl") or "")
    if "event-fallback" in img:
        return 4, source or "Neutral Kingdom Circuit fallback", source_url
    if typ == "event_artwork":
        return (2 if "tour" in norm(event.get("title")) else 1), source, source_url
    return 3, source, source_url


def write_artwork_inventory(root: pathlib.Path) -> dict:
    rows = []
    events = []
    seen = set()
    for rel in ("events.json", "supplemental-events.json"):
        v = load_json(root / rel)
        if isinstance(v, list):
            events.extend(e for e in v if isinstance(e, dict))
    for e in events:
        ident = str(e.get("id") or "") or repr(event_key(e))
        if ident in seen:
            continue
        seen.add(ident)
        cls, source, source_url = classify_image(e)
        rows.append({
            "id": e.get("id"), "title": e.get("title"), "date": str(e.get("startDate") or "")[:10],
            "city": e.get("city"), "state": e.get("state"), "image": public_src(e.get("image")),
            "classification": cls,
            "classificationLabel": {1: "Correct show-specific artwork", 2: "Correct official tour artwork", 3: "Verified artist portrait", 4: "Generic Kingdom Circuit placeholder", 5: "Blank, broken, or incorrect"}[cls],
            "source": source, "sourceUrl": source_url, "artworkStillNeeded": cls in {4, 5},
        })
    write_json(root / "artwork-audit.json", rows)
    return {"eventsInventoried": len(rows), "artworkStillNeeded": sum(1 for r in rows if r["artworkStillNeeded"]), "incorrectOrBroken": sum(1 for r in rows if r["classification"] == 5)}


def verify_closeout(root: pathlib.Path) -> dict:
    fake_refs = []
    completed = instock = correction_pages = 0
    for page in root.rglob("*.html"):
        text = html.unescape(page.read_text(encoding="utf-8", errors="ignore"))
        completed += int("https://schema.org/EventCompleted" in text)
        instock += int('"availability":"https://schema.org/InStock"' in text or '"availability": "https://schema.org/InStock"' in text)
        for asset in FAKE_ASSETS:
            if asset in text:
                fake_refs.append(f"{page.relative_to(root)}:{asset}")
        if page.parent.parent == root / "event" and "Suggest a correction" in text:
            correction_pages += 1
    failures = []
    if fake_refs:
        failures.append("fabricated-artwork:" + "|".join(fake_refs[:8]))
    if completed:
        failures.append(f"EventCompleted:{completed}")
    if instock:
        failures.append(f"automatic-InStock:{instock}")
    if not (root / "assets/sep12-closeout.js").exists():
        failures.append("missing-accessibility-runtime")
    audit = load_json(root / "artwork-audit.json")
    if not isinstance(audit, list) or not audit:
        failures.append("missing-artwork-inventory")
    if failures:
        raise SystemExit("September 12 closeout verification failed: " + ", ".join(failures))
    return {"correctionPages": correction_pages, "artworkAuditRows": len(audit), "fabricatedArtworkRefs": len(fake_refs), "eventCompletedRefs": completed, "automaticInStockRefs": instock}


def apply_closeout(root: pathlib.Path, source_events: list[dict]) -> dict:
    root = root.resolve()
    report = {
        "attendance": remove_hidden_events(root, source_events),
        "artwork": apply_artwork_replacements(root, source_events),
        "images": enhance_all_images(root),
        "metadata": metadata_and_schema(root),
        "accessibility": install_accessibility(root),
    }
    report["inventory"] = write_artwork_inventory(root)
    report["verify"] = verify_closeout(root)
    report["brandingBlocker"] = "Exact approved monochrome stage-and-speakers source asset is not present in the repository or available as a publishable binary; existing logo is preserved unchanged."
    write_json(root / "sep12-closeout-report.json", report)
    return report
