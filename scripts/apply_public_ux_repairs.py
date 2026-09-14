from __future__ import annotations

import html
import json
import pathlib
import re
import sys


PUBLIC_BASE = "/"
CSS_NAME = "site-ux-repairs.css"
JS_NAME = "site-ux-repairs.js"
CSS_HREF = f"{PUBLIC_BASE}assets/{CSS_NAME}?v=4"
JS_SRC = f"{PUBLIC_BASE}assets/{JS_NAME}?v=4"


OVERLAY_CSS = r'''/* Kingdom Circuit production UX repairs. */
body [hidden] { display: none !important; }

.kc-skip-link {
  position: fixed;
  top: 10px;
  left: 10px;
  z-index: 10000;
  padding: 12px 16px;
  border: 2px solid #e3b75d;
  border-radius: 8px;
  background: #080808;
  color: #f5f2ea;
  font-weight: 900;
  text-decoration: none;
  transform: translateY(-160%);
}
.kc-skip-link:focus { transform: translateY(0); }

.menu-drawer {
  height: 100dvh !important;
  max-height: 100dvh !important;
  overflow-y: auto !important;
  overscroll-behavior: contain;
  padding-bottom: calc(26px + env(safe-area-inset-bottom)) !important;
}

.footer-status,
.footer-source-warning,
.profile-image-note,
.seo-roster-note,
.profile-count,
.disclaimer,
.form-note,
.form-feedback,
.source-line,
.price-line,
.results-count,
.event-meta dt,
.detail-list dt { color: #b8b4ac !important; }

.field input,
.field select,
.field textarea,
.filter-chip,
.reset-button,
.menu-toggle,
.menu-close,
.secondary-button { border-color: #707070 !important; }

.menu-toggle,
.menu-close,
.filter-chip,
.reset-button,
.official-button,
.primary-button,
.secondary-button,
.kc-show-all-artists,
.seo-social-link,
.artist-platform-link,
body .artist-card .artist-platform-link,
body .seo-card-socials .seo-social-link {
  min-width: 44px !important;
  min-height: 44px !important;
}

.kc-public-directory-toolbar {
  grid-template-columns: minmax(220px, 2fr) minmax(220px, 1fr) auto auto !important;
}
.kc-show-all-artists { align-self: end; }

.kc-honeypot {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}
.kc-correction-note { margin: 0 0 18px; color: #b8b4ac; }

@media (max-width: 900px) {
  .kc-public-directory-toolbar { grid-template-columns: 1fr 1fr !important; }
}

@media (max-width: 640px) {
  body [data-artist-directory] [data-artist-grid],
  body [data-artist-directory] .artist-grid,
  body [data-artist-directory] .seo-artist-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    grid-auto-rows: 1fr !important;
    align-items: stretch !important;
    gap: 10px !important;
  }
  body [data-artist-directory] [data-artist-card] {
    display: flex !important;
    flex-direction: column !important;
    min-width: 0 !important;
    height: 100% !important;
    overflow: hidden !important;
  }
  body [data-artist-directory] .artist-visual {
    display: block !important;
    width: 100% !important;
    height: auto !important;
    min-height: 0 !important;
    aspect-ratio: 1 / 1 !important;
    flex: 0 0 auto !important;
    overflow: hidden !important;
  }
  body [data-artist-directory] .artist-visual img,
  body [data-artist-directory] img.artist-photo {
    display: block !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 0 !important;
    aspect-ratio: 1 / 1 !important;
    object-fit: cover !important;
  }
  body [data-artist-directory] .artist-card-body {
    display: flex !important;
    flex: 1 1 auto !important;
    flex-direction: column !important;
    min-height: 0 !important;
  }
  body [data-artist-directory] .artist-card-footer {
    margin-top: auto !important;
  }
  body [data-artist-directory] [data-artist-card] h2,
  body [data-artist-directory] [data-artist-card] h2 a,
  body [data-artist-directory] [data-artist-card] .artist-card-footer a {
    min-width: 0 !important;
    overflow-wrap: anywhere !important;
    word-break: break-word !important;
  }
  body [data-artist-directory] .kc-artist-filter-form,
  body [data-artist-directory] .kc-upcoming-check,
  body [data-artist-directory] .check-field {
    min-width: 0 !important;
    max-width: 100% !important;
  }
  body [data-artist-directory] .kc-upcoming-check,
  body [data-artist-directory] .check-field {
    white-space: normal !important;
    overflow-wrap: anywhere !important;
  }
  .artist-platform-link,
  .seo-social-link,
  .seo-social-link-compact,
  body .artist-card .artist-platform-link,
  body .seo-card-socials .seo-social-link {
    width: 44px !important;
    height: 44px !important;
    min-width: 44px !important;
    min-height: 44px !important;
  }
  body [data-artist-directory] .artist-card-links,
  body [data-artist-directory] .seo-card-socials {
    display: grid !important;
    grid-template-columns: repeat(2, 44px) !important;
    grid-auto-rows: 44px !important;
    min-height: 96px !important;
    gap: 8px !important;
    align-content: start !important;
  }
  .kc-public-directory-toolbar { grid-template-columns: 1fr !important; }
  .kc-show-all-artists { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto !important; }
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
    scroll-behavior: auto !important;
  }
}
'''


OVERLAY_JS = r'''"use strict";

(() => {
  if (window.__kcPublicUxRepairsInstalled) return;
  window.__kcPublicUxRepairsInstalled = true;

  const one = (selector, root = document) => root.querySelector(selector);
  const all = (selector, root = document) => [...root.querySelectorAll(selector)];

  function isDrawerOpen(drawer) {
    return drawer.classList.contains("open") && drawer.getAttribute("aria-hidden") !== "true";
  }

  function focusableElements(root) {
    return all('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])', root)
      .filter(element => !element.hidden && !element.closest("[hidden],[inert]") && element.getAttribute("aria-hidden") !== "true");
  }

  function setupModalDrawer() {
    const opener = one(".menu-toggle");
    const drawer = one(".menu-drawer");
    const closer = drawer && one(".menu-close", drawer);
    const backdrop = one(".menu-backdrop");
    if (!opener || !drawer || !closer) return;

    let active = false;
    let returnFocus = opener;
    const backgroundState = new Map();
    const originalRole = drawer.getAttribute("role");

    const backgroundElements = () => all(":scope > *", document.body).filter(element =>
      element !== drawer && element !== backdrop && !element.contains(drawer) &&
      !["SCRIPT", "STYLE", "LINK"].includes(element.tagName)
    );

    function makeBackgroundInert() {
      backgroundState.clear();
      backgroundElements().forEach(element => {
        backgroundState.set(element, {
          inert: element.hasAttribute("inert"),
          ariaHidden: element.getAttribute("aria-hidden")
        });
        element.inert = true;
        element.setAttribute("aria-hidden", "true");
      });
    }

    function restoreBackground() {
      backgroundState.forEach((state, element) => {
        if (state.inert) element.setAttribute("inert", "");
        else {
          element.inert = false;
          element.removeAttribute("inert");
        }
        if (state.ariaHidden === null) element.removeAttribute("aria-hidden");
        else element.setAttribute("aria-hidden", state.ariaHidden);
      });
      backgroundState.clear();
    }

    function activate() {
      if (active) return;
      active = true;
      const current = document.activeElement;
      if (current instanceof HTMLElement && !drawer.contains(current)) returnFocus = current;
      else returnFocus = opener;
      drawer.inert = false;
      drawer.removeAttribute("inert");
      drawer.setAttribute("role", "dialog");
      drawer.setAttribute("aria-modal", "true");
      closer.removeAttribute("tabindex");
      closer.focus({ preventScroll: true });
      makeBackgroundInert();
    }

    function deactivate() {
      if (!active) return;
      active = false;
      restoreBackground();
      drawer.removeAttribute("aria-modal");
      if (originalRole === null) drawer.removeAttribute("role");
      else drawer.setAttribute("role", originalRole);
      const target = returnFocus && returnFocus.isConnected ? returnFocus : opener;
      requestAnimationFrame(() => target.focus({ preventScroll: true }));
    }

    function sync() {
      if (isDrawerOpen(drawer)) activate();
      else deactivate();
    }

    new MutationObserver(sync).observe(drawer, {
      attributes: true,
      attributeFilter: ["class", "aria-hidden"]
    });

    document.addEventListener("keydown", event => {
      if (!active || event.key !== "Tab") return;
      const focusable = focusableElements(drawer);
      if (!focusable.length) {
        event.preventDefault();
        drawer.setAttribute("tabindex", "-1");
        drawer.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const current = document.activeElement;
      if (event.shiftKey && (current === first || !drawer.contains(current))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (current === last || !drawer.contains(current))) {
        event.preventDefault();
        first.focus();
      }
    }, true);

    document.addEventListener("focusin", event => {
      if (active && !drawer.contains(event.target)) {
        (focusableElements(drawer)[0] || closer).focus();
      }
    }, true);

    sync();
  }

  function normalizedHref(link) {
    try { return new URL(link.getAttribute("href") || "", document.baseURI).href; }
    catch { return link.getAttribute("href") || ""; }
  }

  function platformName(link) {
    const existing = (link.getAttribute("aria-label") || "").replace(/^Open\s+/i, "").split(/\s+for\s+/i)[0].split(":")[0].trim();
    if (/^(Instagram|Spotify|YouTube|Website)$/i.test(existing)) return existing.replace(/^./, value => value.toUpperCase());
    const text = (link.textContent || "").trim();
    if (/Instagram/i.test(text)) return "Instagram";
    if (/Spotify/i.test(text)) return "Spotify";
    if (/YouTube/i.test(text)) return "YouTube";
    const href = link.getAttribute("href") || "";
    if (/instagram\.com/i.test(href)) return "Instagram";
    if (/spotify\.com/i.test(href)) return "Spotify";
    if (/(?:youtube\.com|youtu\.be)/i.test(href)) return "YouTube";
    return "Website";
  }

  function artistNameFor(link) {
    const card = link.closest("[data-artist-card]");
    if (card) return (one("h2,h3", card)?.textContent || "artist").trim();
    const profile = link.closest(".seo-artist-profile,[data-artist-profile],.profile-hero");
    const heading = profile ? one("h1", profile) : one("main h1");
    return (heading?.textContent || "artist").replace(/\s+(?:Concerts|Tour Dates|Shows).*$/i, "").trim();
  }

  function enhanceCards(root = document) {
    all("[data-event-card]", root).forEach(card => {
      const heading = one("h3 a,h2 a", card);
      const media = one("a.event-media", card);
      const title = (one("h3,h2", card)?.textContent || "this event").trim();
      if (heading && media && normalizedHref(heading) === normalizedHref(media)) {
        media.tabIndex = -1;
        media.setAttribute("aria-hidden", "true");
        media.setAttribute("data-kc-duplicate-link", "true");
      }
      all("a", card).filter(link => /^Official details$/i.test((link.textContent || "").trim())).forEach(link => {
        const suffix = link.target === "_blank" ? " (opens in new tab)" : "";
        link.setAttribute("aria-label", `Official details for ${title}${suffix}`);
      });
    });

    all("[data-artist-card]", root).forEach(card => {
      const heading = one("h2 a,h3 a", card);
      const media = one("a.artist-visual", card);
      if (heading && media && normalizedHref(heading) === normalizedHref(media)) {
        media.tabIndex = -1;
        media.setAttribute("aria-hidden", "true");
        media.setAttribute("data-kc-duplicate-link", "true");
      }
    });

    all(".seo-social-link,[data-artist-social]", root).forEach(link => {
      const artist = artistNameFor(link) || "artist";
      const suffix = link.target === "_blank" ? " (opens in new tab)" : "";
      link.setAttribute("aria-label", `${platformName(link)} for ${artist}${suffix}`);
    });

    if (!one("[data-event-card]", root) && /^\/event\//.test(location.pathname)) {
      const title = (one("main h1")?.textContent || "this event").trim();
      all("a").filter(link => /^Official details$/i.test((link.textContent || "").trim())).forEach(link => {
        const suffix = link.target === "_blank" ? " (opens in new tab)" : "";
        link.setAttribute("aria-label", `Official details for ${title}${suffix}`);
      });
    }
  }

  function setupArtistDirectory() {
    const directory = one("[data-artist-directory]");
    if (!directory) return;
    // The established directory controller owns the Artist, State, Month,
    // upcoming-show, and mobile-grid behavior.  Do not replace it with the
    // simplified search/show-all controller when those controls are present.
    if (one("[data-directory-artist-filter]", directory)) return;
    const grid = one("[data-artist-grid]", directory);
    let cards = grid ? all("[data-artist-card]", grid) : [];
    const deferredCards = one("[data-kc-inactive-artists]", directory);
    const search = one("[data-artist-search]", directory);
    const upcomingOnly = one("[data-has-shows-filter]", directory);
    const showAllButton = one("[data-kc-show-all]", directory);
    const count = one("[data-artist-count]", directory);
    const empty = one("[data-artist-empty]", directory);
    if (!cards.length || !upcomingOnly) return;

    let showAll = !upcomingOnly.checked;
    const activeCount = cards.filter(card => card.dataset.hasShows === "true").length;
    const totalCount = Number(showAllButton?.dataset.totalCount) || cards.length;

    function loadDeferredCards() {
      if (!deferredCards || !grid || !deferredCards.isConnected) return;
      try {
        const template = document.createElement("template");
        template.innerHTML = JSON.parse(deferredCards.textContent || '""');
        grid.append(template.content);
        deferredCards.remove();
        cards = all("[data-artist-card]", grid);
      } catch (error) {
        console.error("Deferred artist cards could not be loaded", error);
      }
    }

    function apply() {
      const needle = String(search?.value || "").trim().toLowerCase();
      let visible = 0;
      cards.forEach(card => {
        const matchesSearch = !needle || String(card.dataset.search || card.textContent || "").toLowerCase().includes(needle);
        const hasShows = card.dataset.hasShows === "true";
        const matches = matchesSearch && (showAll || hasShows);
        card.hidden = !matches;
        card.setAttribute("aria-hidden", matches ? "false" : "true");
        if (matches) visible += 1;
      });
      upcomingOnly.checked = !showAll;
      if (count) {
        count.textContent = !showAll && !needle
          ? `${activeCount} artist${activeCount === 1 ? "" : "s"} with upcoming shows`
          : `${visible} showing · ${cards.length} total`;
      }
      if (empty) {
        empty.hidden = visible !== 0;
        empty.textContent = "No artists match those filters.";
      }
      if (showAllButton) {
        showAllButton.setAttribute("aria-pressed", showAll ? "true" : "false");
        showAllButton.textContent = showAll
          ? "Show artists with shows only"
          : `Show all ${totalCount} artists`;
      }
    }

    if (showAllButton) {
      showAllButton.hidden = false;
      showAllButton.addEventListener("click", () => {
        showAll = !showAll;
        if (showAll) loadDeferredCards();
        apply();
      });
    }
    upcomingOnly.addEventListener("change", () => {
      showAll = !upcomingOnly.checked;
      if (showAll) loadDeferredCards();
      apply();
    });
    search?.addEventListener("input", apply);
    apply();
  }

  function setupCorrectionMode() {
    const form = one("[data-submission-form]");
    if (!form) return;
    const compactFields = {
      date: true,
      local_time: false,
      venue: true,
      city: true,
      state: true,
      artist_lineup: true,
      artwork_url: false,
      relationship: false
    };
    const modeButtons = all("[data-submission-mode]", form);
    const kind = one("[data-submission-kind]", form);
    const submit = one("[data-submission-submit]", form);
    const details = one('[name="details"]', form);
    const detailsLabel = details?.closest("label");
    const detailsCaption = detailsLabel && one("span", detailsLabel);
    const params = new URLSearchParams(location.search);
    const correctionNote = document.createElement("p");
    correctionNote.className = "kc-correction-note";
    correctionNote.hidden = true;
    correctionNote.textContent = "Correction mode only asks for the event, a supporting link, and what needs to change.";
    one(".form-grid", form)?.before(correctionNote);

    function setMode(mode) {
      const correction = mode === "Correction";
      if (kind) kind.value = correction ? "Correction" : "New show";
      modeButtons.forEach(button => {
        const selected = button.dataset.submissionMode === (correction ? "Correction" : "New show");
        button.classList.toggle("active", selected);
        button.setAttribute("aria-pressed", selected ? "true" : "false");
      });
      Object.entries(compactFields).forEach(([name, originallyRequired]) => {
        const field = one(`[name="${name}"]`, form);
        if (!field) return;
        const label = field.closest("label");
        if (label) label.hidden = correction;
        field.required = correction ? false : originallyRequired;
        field.disabled = correction;
      });
      ["event_name", "official_url"].forEach(name => {
        const field = one(`[name="${name}"]`, form);
        if (!field) return;
        field.required = true;
        field.readOnly = correction && Boolean(params.get(name === "event_name" ? "event" : "url"));
      });
      if (details) details.required = correction;
      if (detailsCaption) detailsCaption.textContent = correction
        ? "What needs to be corrected? Include a supporting link."
        : "Additional details (optional)";
      correctionNote.hidden = !correction;
      if (submit) submit.textContent = correction ? "Send Correction" : "Send for Review";
    }

    modeButtons.forEach(button => button.addEventListener("click", () => {
      setMode(button.dataset.submissionMode === "Correction" ? "Correction" : "New show");
    }));
    form.addEventListener("reset", () => requestAnimationFrame(() => setMode("New show")));
    setMode((params.get("type") || "").toLowerCase().includes("correction") ? "Correction" : "New show");
  }

  function install() {
    setupModalDrawer();
    enhanceCards();
    setupArtistDirectory();
    setupCorrectionMode();

    let queued = false;
    new MutationObserver(records => {
      if (queued || !records.some(record => record.addedNodes.length)) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        enhanceCards();
      });
    }).observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})();
'''


def replace_attr(tag: str, name: str, value: str) -> str:
    escaped = html.escape(value, quote=True)
    quoted = re.compile(rf"\s+{re.escape(name)}\s*=\s*([\"']).*?\1", re.I | re.S)
    if quoted.search(tag):
        return quoted.sub(f' {name}="{escaped}"', tag, count=1)
    bare = re.compile(rf"\s+{re.escape(name)}\s*=\s*[^\s>]+", re.I)
    if bare.search(tag):
        return bare.sub(f' {name}="{escaped}"', tag, count=1)
    return tag[:-1] + f' {name}="{escaped}">' if tag.endswith(">") else tag


def add_boolean_attr(tag: str, name: str) -> str:
    if re.search(rf"\s{re.escape(name)}(?:\s|=|/?>)", tag, re.I):
        return tag
    return tag[:-1] + f" {name}>" if tag.endswith(">") else tag


def remove_attr(tag: str, name: str) -> str:
    tag = re.sub(rf"\s+{re.escape(name)}\s*=\s*([\"']).*?\1", "", tag, flags=re.I | re.S)
    tag = re.sub(rf"\s+{re.escape(name)}(?=\s|/?>)", "", tag, flags=re.I)
    return tag


def add_class(tag: str, class_name: str) -> str:
    match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', tag, re.I | re.S)
    if not match:
        return replace_attr(tag, "class", class_name)
    classes = match.group(2).split()
    if class_name in classes:
        return tag
    classes.append(class_name)
    return tag[:match.start(2)] + " ".join(classes) + tag[match.end(2):]


def attr_value(tag: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*([\"'])(.*?)\1", tag, re.I | re.S)
    return html.unescape(match.group(2)).strip() if match else ""


def plain_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(fragment))).strip()


def patch_duplicate_card_link(block: str, heading: str, media_class: str) -> str:
    heading_block = re.search(rf"<{heading}\b[^>]*>(.*?)</{heading}>", block, re.I | re.S)
    heading_link = re.search(r"<a\b[^>]*>", heading_block.group(1), re.I) if heading_block else None
    media_link = re.search(
        rf'<a\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\b{re.escape(media_class)}\b)[^>]*>',
        block,
        re.I | re.S,
    )
    if (
        not heading_link
        or not media_link
        or attr_value(heading_link.group(0), "href") != attr_value(media_link.group(0), "href")
    ):
        return block
    old_tag = media_link.group(0)
    new_tag = replace_attr(old_tag, "tabindex", "-1")
    new_tag = replace_attr(new_tag, "aria-hidden", "true")
    new_tag = replace_attr(new_tag, "data-kc-duplicate-link", "true")
    return block.replace(old_tag, new_tag, 1)


def patch_official_links(block: str, title: str) -> str:
    pattern = re.compile(r"<a\b[^>]*>.*?</a>", re.I | re.S)

    def repl(match: re.Match[str]) -> str:
        anchor = match.group(0)
        opening = anchor.split(">", 1)[0] + ">"
        inner = anchor[len(opening):-4]
        if plain_text(inner).casefold() != "official details":
            return anchor
        suffix = " (opens in new tab)" if attr_value(opening, "target").casefold() == "_blank" else ""
        updated = replace_attr(opening, "aria-label", f"Official details for {title}{suffix}")
        return updated + inner + "</a>"

    return pattern.sub(repl, block)


def platform_for(anchor: str) -> str:
    opening = anchor.split(">", 1)[0] + ">"
    label = attr_value(opening, "aria-label")
    label = re.sub(r"^Open\s+", "", label, flags=re.I).split(" for ", 1)[0].split(":", 1)[0].strip()
    for platform in ("Instagram", "Spotify", "YouTube", "Website"):
        if label.casefold() == platform.casefold():
            return platform
    text = plain_text(anchor)
    for platform in ("Instagram", "Spotify", "YouTube", "Website"):
        if platform.casefold() in text.casefold():
            return platform
    href = attr_value(opening, "href").casefold()
    if "instagram.com" in href:
        return "Instagram"
    if "spotify.com" in href:
        return "Spotify"
    if "youtube.com" in href or "youtu.be" in href:
        return "YouTube"
    return "Website"


def patch_social_links(block: str, artist_name: str) -> str:
    pattern = re.compile(
        r'<a\b(?=[^>]*(?:class\s*=\s*["\'][^"\']*\bseo-social-link\b|\bdata-artist-social\b))[^>]*>.*?</a>',
        re.I | re.S,
    )

    def repl(match: re.Match[str]) -> str:
        anchor = match.group(0)
        opening = anchor.split(">", 1)[0] + ">"
        inner = anchor[len(opening):-4]
        suffix = " (opens in new tab)" if attr_value(opening, "target").casefold() == "_blank" else ""
        updated = replace_attr(opening, "aria-label", f"{platform_for(anchor)} for {artist_name}{suffix}")
        return updated + inner + "</a>"

    return pattern.sub(repl, block)


def patch_event_card(block: str) -> str:
    heading = re.search(r"<h3\b[^>]*>(.*?)</h3>", block, re.I | re.S)
    title = plain_text(heading.group(1)) if heading else "this event"
    block = patch_duplicate_card_link(block, "h3", "event-media")
    return patch_official_links(block, title)


def patch_artist_card(block: str) -> str:
    heading = re.search(r"<h2\b[^>]*>(.*?)</h2>", block, re.I | re.S)
    artist_name = plain_text(heading.group(1)) if heading else "artist"
    block = patch_duplicate_card_link(block, "h2", "artist-visual")
    return patch_social_links(block, artist_name)


def patch_cards(text: str) -> str:
    event_pattern = re.compile(
        r'<article\b(?=[^>]*\bdata-event-card\b)[^>]*>.*?</article>', re.I | re.S
    )
    artist_pattern = re.compile(
        r'<article\b(?=[^>]*\bdata-artist-card\b)[^>]*>.*?</article>', re.I | re.S
    )
    text = event_pattern.sub(lambda match: patch_event_card(match.group(0)), text)
    return artist_pattern.sub(lambda match: patch_artist_card(match.group(0)), text)


def patch_artist_profile_socials(text: str) -> str:
    label = re.search(r'aria-label=["\']Official\s+(.+?)\s+links["\']', text, re.I)
    if label:
        return patch_social_links(text, html.unescape(label.group(1)).strip())
    return text


def remove_redundant_artist_loader(text: str) -> str:
    return re.sub(
        r'\s*<script\b[^>]*\bsrc=["\'][^"\']*assets/artist-filter-fix\.js(?:\?[^"\']*)?["\'][^>]*>\s*</script>',
        "",
        text,
        flags=re.I,
    )


def patch_artist_directory(text: str) -> tuple[str, int, int]:
    # The legacy SEO helper snapshots the initial card list and competes with
    # this deferred-directory controller, producing stale counts after "Show
    # all". Artist profile pages keep that helper for their show filters.
    text = re.sub(
        r'\s*<script\b[^>]*\bsrc=["\'][^"\']*seo-enhancements\.js(?:\?[^"\']*)?["\'][^>]*>\s*</script>',
        "",
        text,
        flags=re.I,
    )
    existing_payload = re.search(
        r'<script\b(?=[^>]*\bdata-kc-inactive-artists\b)[^>]*>(.*?)</script>',
        text,
        re.I | re.S,
    )
    existing_deferred = ""
    if existing_payload:
        try:
            parsed = json.loads(existing_payload.group(1))
            existing_deferred = parsed if isinstance(parsed, str) else ""
        except json.JSONDecodeError:
            existing_deferred = ""

    card_pattern = re.compile(
        r'(<article\b(?=[^>]*\bdata-artist-card\b)[^>]*)(>.*?</article>)', re.I | re.S
    )
    existing_count = len(re.findall(r'<article\b(?=[^>]*\bdata-artist-card\b)', existing_deferred, re.I))
    total = existing_count
    active = 0
    deferred: list[str] = []

    def card_repl(match: re.Match[str]) -> str:
        nonlocal total, active
        total += 1
        opening = match.group(1) + ">"
        has_shows = attr_value(opening, "data-has-shows").casefold() == "true"
        if has_shows:
            active += 1
        else:
            deferred.append(opening + match.group(2)[1:])
            return ""
        return opening + match.group(2)[1:]

    text = card_pattern.sub(card_repl, text)
    if deferred and not existing_payload:
        deferred_markup = "".join(deferred)
        payload = json.dumps(deferred_markup, ensure_ascii=False).replace("<", r"\u003c")
        payload_tag = f'<script type="application/json" data-kc-inactive-artists>{payload}</script>'
        empty_panel = re.search(r'<div\b(?=[^>]*\bdata-artist-empty\b)', text, re.I)
        if not empty_panel:
            raise SystemExit("Artist directory is missing its empty-state marker")
        text = text[:empty_panel.start()] + payload_tag + text[empty_panel.start():]
    text = re.sub(
        r'<input\b(?=[^>]*\bdata-has-shows-filter\b)[^>]*>',
        lambda match: add_boolean_attr(match.group(0), "checked"),
        text,
        count=1,
        flags=re.I,
    )
    text = re.sub(
        r'(<div\b[^>]*class=["\'][^"\']*\bdirectory-toolbar\b[^"\']*["\'][^>]*>)',
        lambda match: add_class(match.group(1), "kc-public-directory-toolbar"),
        text,
        count=1,
        flags=re.I,
    )
    if total and "data-kc-show-all" not in text:
        button = (
            f'<button class="reset-button kc-show-all-artists" type="button" data-kc-show-all '
            f'data-active-count="{active}" data-total-count="{total}" aria-pressed="false" hidden>'
            f"Show all {total} artists</button>"
        )
        count_match = re.search(r'<p\b[^>]*\bdata-artist-count\b[^>]*>', text, re.I)
        if count_match:
            text = text[:count_match.start()] + button + text[count_match.start():]
    text = re.sub(
        r'(<p\b[^>]*\bdata-artist-count\b[^>]*>).*?(</p>)',
        lambda match: match.group(1) + f"{active} artists with upcoming shows" + match.group(2),
        text,
        count=1,
        flags=re.I | re.S,
    )
    return text, active, total


def restore_artist_directory_toolbar(text: str, total: int) -> str:
    """Restore the full directory controls after the SEO overlay simplifies them."""
    if "data-directory-artist-filter" in text:
        return text
    toolbar = re.search(
        r'<div\b[^>]*class=["\'][^"\']*\bdirectory-toolbar\b[^"\']*["\'][^>]*>.*?</div>',
        text,
        re.I | re.S,
    )
    if not toolbar:
        raise SystemExit("Artist directory is missing its filter toolbar")
    markup = (
        '<div class="directory-toolbar kc-directory-toolbar">'
        '<form class="filters kc-artist-filter-form" data-artist-directory-filters '
        'aria-label="Filter artists">'
        '<label class="field"><span>Artist</span><select data-directory-artist-filter>'
        '<option value="">All artists</option></select></label>'
        '<label class="field"><span>State</span><select data-directory-state-filter>'
        '<option value="">All states</option></select></label>'
        '<label class="field"><span>Month</span><select data-directory-month-filter>'
        '<option value="">All months</option></select></label>'
        '<label class="check-field kc-upcoming-check"><input data-has-shows-filter '
        'type="checkbox" checked> Only artists with upcoming shows</label>'
        '<button class="reset-button" data-directory-reset-filters type="button">'
        'Clear filters</button></form>'
        f'<p class="results-count" data-artist-count role="status" aria-live="polite" '
        f'aria-atomic="true">{total} artists</p></div>'
    )
    return text[:toolbar.start()] + markup + text[toolbar.end():]


def patch_input(text: str, name: str, **attributes: str) -> str:
    pattern = re.compile(rf'<(?:input|textarea)\b(?=[^>]*\bname=["\']{re.escape(name)}["\'])[^>]*>', re.I)

    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        for attr_name, value in attributes.items():
            tag = replace_attr(tag, attr_name.replace("_", "-"), value)
        return tag

    return pattern.sub(repl, text, count=1)


def patch_submission_form(text: str) -> str:
    text = patch_input(text, "submitter_name", autocomplete="name")
    text = patch_input(text, "email", autocomplete="email")
    text = patch_input(text, "event_name", autocomplete="off")
    text = patch_input(text, "venue", autocomplete="organization")
    text = patch_input(text, "city", autocomplete="address-level2")
    text = patch_input(
        text,
        "state",
        autocomplete="address-level1",
        autocapitalize="characters",
        pattern="[A-Za-z]{2}",
        title="Two-letter state code",
    )
    form_match = re.search(r'<form\b(?=[^>]*\bdata-submission-form\b)[^>]*>', text, re.I)
    if form_match:
        form_tag = remove_attr(form_match.group(0), "novalidate")
        form_tag = replace_attr(form_tag, "aria-describedby", "kc-form-privacy")
        text = text[:form_match.start()] + form_tag + text[form_match.end():]
    if "data-kc-honeypot" not in text:
        honeypot = (
            '<div class="kc-honeypot" data-kc-honeypot aria-hidden="true">'
            '<label>Leave this field empty<input name="_gotcha" type="text" tabindex="-1" '
            'autocomplete="off"></label></div>'
        )
        grid = re.search(r'<div\b[^>]*class=["\'][^"\']*\bform-grid\b[^"\']*["\'][^>]*>', text, re.I)
        if grid:
            text = text[:grid.start()] + honeypot + text[grid.start():]
    if 'id="kc-form-privacy"' not in text:
        privacy = (
            '<p class="form-note kc-form-privacy" id="kc-form-privacy">'
            "Privacy: Your contact information is used only to review this submission. "
            "Do not include sensitive personal information. Automated spam submissions are screened."
            "</p>"
        )
        note = re.search(r'<p\b[^>]*class=["\'][^"\']*\bform-note\b[^"\']*["\'][^>]*>', text, re.I)
        if note:
            text = text[:note.start()] + privacy + text[note.start():]
    return text


def ensure_page_shell(text: str) -> str:
    main = re.search(r"<main\b[^>]*>", text, re.I)
    if not main:
        return text
    main_tag = replace_attr(main.group(0), "id", "kc-main-content")
    text = text[:main.start()] + main_tag + text[main.end():]
    if "kc-skip-link" not in text:
        body = re.search(r"<body\b[^>]*>", text, re.I)
        if body:
            skip = '<a class="kc-skip-link" href="#kc-main-content">Skip to main content</a>'
            text = text[:body.end()] + skip + text[body.end():]
    text = re.sub(
        rf'{re.escape(PUBLIC_BASE)}assets/{re.escape(CSS_NAME)}(?:\?v=[^"\']*)?',
        CSS_HREF,
        text,
        flags=re.I,
    )
    text = re.sub(
        rf'{re.escape(PUBLIC_BASE)}assets/{re.escape(JS_NAME)}(?:\?v=[^"\']*)?',
        JS_SRC,
        text,
        flags=re.I,
    )
    if CSS_HREF not in text:
        text = re.sub(
            r"</head>",
            f'<link rel="stylesheet" href="{CSS_HREF}" data-kc-public-ux-overlay>\n</head>',
            text,
            count=1,
            flags=re.I,
        )
    if JS_SRC not in text:
        text = re.sub(
            r"</body>",
            f'<script src="{JS_SRC}" defer data-kc-public-ux-overlay></script>\n</body>',
            text,
            count=1,
            flags=re.I,
        )
    return text


def patch_html(path: pathlib.Path, out_dir: pathlib.Path) -> tuple[bool, dict[str, int]]:
    text = path.read_text(encoding="utf-8")
    original = text
    relative = path.relative_to(out_dir).as_posix()
    text = patch_cards(text)
    if relative.startswith("event/"):
        heading = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, re.I | re.S)
        if heading:
            text = patch_official_links(text, plain_text(heading.group(1)))
    if relative.startswith("artists/") and relative != "artists/index.html":
        text = patch_artist_profile_socials(text)
    stats = {"activeArtists": 0, "totalArtists": 0}
    if relative == "artists/index.html":
        # Preserve the resilient directory controller and the complete static
        # artist grid.  It supplies Artist/State/Month filters and the intended
        # two-column mobile layout; deferring cards here broke those features.
        cards = re.findall(r'<article\b(?=[^>]*\bdata-artist-card\b)', text, re.I)
        active = re.findall(
            r'<article\b(?=[^>]*\bdata-artist-card\b)(?=[^>]*\bdata-has-shows=["\']true["\'])',
            text,
            re.I,
        )
        stats["activeArtists"] = len(active)
        stats["totalArtists"] = len(cards)
        text = restore_artist_directory_toolbar(
            text,
            stats["totalArtists"],
        )
    if relative == "submit/index.html":
        text = patch_submission_form(text)
    text = ensure_page_shell(text)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True, stats
    return False, stats


def apply(out_dir: pathlib.Path) -> dict[str, int]:
    if not (out_dir / "index.html").is_file():
        raise SystemExit(f"Missing production site artifact: {out_dir}")
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / CSS_NAME).write_text(OVERLAY_CSS, encoding="utf-8")
    (assets / JS_NAME).write_text(OVERLAY_JS, encoding="utf-8")

    changed = 0
    active_artists = 0
    total_artists = 0
    pages = list(out_dir.rglob("*.html"))
    for page in pages:
        was_changed, stats = patch_html(page, out_dir)
        changed += int(was_changed)
        active_artists = max(active_artists, stats["activeArtists"])
        total_artists = max(total_artists, stats["totalArtists"])
    return {
        "htmlPages": len(pages),
        "htmlPagesChanged": changed,
        "activeArtists": active_artists,
        "totalArtists": total_artists,
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_public_ux_repairs.py SITE_OUTPUT")
    out_dir = pathlib.Path(sys.argv[1]).resolve()
    if not out_dir.is_dir():
        raise SystemExit(f"Missing site output: {out_dir}")
    report = apply(out_dir)
    print(json.dumps({"publicUxRepairsApplied": True, **report}, indent=2))


if __name__ == "__main__":
    main()
