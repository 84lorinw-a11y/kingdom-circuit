"use strict";

(() => {
  const BASE = "/";
  const STATE_NAMES = {
    BC:"British Columbia",ON:"Ontario",SK:"Saskatchewan",
    AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",CO:"Colorado",CT:"Connecticut",DE:"Delaware",DC:"District of Columbia",FL:"Florida",GA:"Georgia",HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming"
  };

  function norm(value) {
    return String(value || "").trim().toLowerCase();
  }

  function monthKey(value) {
    const raw = String(value || "").slice(0, 7);
    return /^\d{4}-\d{2}$/.test(raw) ? raw : "";
  }

  function monthLabel(key) {
    if (!/^\d{4}-\d{2}$/.test(key)) return key;
    const [year, month] = key.split("-").map(Number);
    return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
      .format(new Date(Date.UTC(year, month - 1, 1)));
  }

  function catalogToday(now = new Date()) {
    const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit'
    }).formatToParts(now).map(part => [part.type, part.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  }

  function isUpcoming(event, day = catalogToday()) {
    const raw = String(event?.endDate || event?.startDate || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return true;
    return raw >= day;
  }

  function isPublished(event) {
    return !["cancelled", "canceled", "postponed", "merged"].includes(norm(event?.status));
  }

  function eventKey(event) {
    if (event?.id) return `id:${event.id}`;
    return [
      event?.startDate,
      event?.startTime,
      event?.title,
      event?.venue,
      event?.city,
      event?.state,
      ...(event?.artists || [])
    ].map(norm).join("|");
  }

  function matchingShows(shows, state = "", month = "") {
    return shows.filter(event =>
      (!state || String(event?.state || "").trim().toUpperCase() === state) &&
      (!month || monthKey(event?.startDate) === month)
    );
  }

  function canonicalEventPath(event, catalog, artistPath) {
    // Use published paths, rather than rebuilding a slug that may have changed.
    const artistPaths = catalog?.artists?.[artistPath];
    const allowed = Array.isArray(artistPaths) ? new Set(artistPaths) : null;
    if (event?.canonicalPath && (!allowed || allowed.has(event.canonicalPath)) &&
        catalog?.shows?.some(show => show.path === event.canonicalPath)) return event.canonicalPath;
    const location = [event?.city, event?.state].filter(Boolean).join(", ");
    const time = /^(\d{1,2}):(\d{2})$/.exec(String(event?.startTime || ""));
    const hour = time ? Number(time[1]) : null;
    const clock = time ? `${hour % 12 || 12}:${time[2]} ${hour >= 12 ? "pm" : "am"}` : null;
    const samePlaceAndDate = (Array.isArray(catalog?.shows) ? catalog.shows : []).filter(show =>
      /^\/event\/[^/?#]+\/$/.test(show?.path || "") &&
      (!allowed || allowed.has(show.path)) &&
      String(show.date || "").slice(0, 10) === String(event?.startDate || "").slice(0, 10) &&
      norm(show.location) === norm(location)
    ).filter(show => {
      const publishedClock = /(?:^| - )(\d{1,2}:\d{2} [ap]m)$/.exec(norm(show.when));
      return !clock || !publishedClock || publishedClock[1] === clock;
    });
    const candidates = samePlaceAndDate.filter(show => norm(show.venue) === norm(event?.venue));
    const exact = candidates.filter(show => norm(show.name) === norm(event?.title));
    if (exact.length === 1) return exact[0].path;
    if (allowed && candidates.length === 1) return candidates[0].path;
    // Supplemental listings can omit a room suffix and append supporting
    // billing. Require the same published artist, date, city, time and a unique
    // title/venue prefix match; never collapse an ambiguous same-day schedule.
    if (allowed && time) {
      const named = samePlaceAndDate.filter(show => {
        const name = norm(show.name), title = norm(event?.title);
        const venue = norm(event?.venue), publishedVenue = norm(show.venue);
        return venue && (publishedVenue === venue || publishedVenue.startsWith(`${venue} `)) &&
          (title === name || title.startsWith(`${name} - `) || title.startsWith(`${name} — `)) &&
          norm(show.when).endsWith(` - ${clock}`);
      });
      if (named.length === 1) return named[0].path;
    }
    return null;
  }

  function uniqueArtistShows(shows, catalog, artistPath) {
    const seen = new Set();
    return shows.filter(event => {
      // Different feeds can publish the same booking with different IDs. Only
      // merge them when the published catalog resolves them to the same page;
      // ambiguous or unmapped same-day performances retain separate identities.
      const path = canonicalEventPath(event, catalog, artistPath);
      const key = path ? `path:${path}` : eventKey(event);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function catalogArtistShows(catalog, artistPath, day = catalogToday()) {
    if (!Array.isArray(catalog?.shows) || !catalog.artists || typeof catalog.artists !== 'object') return null;
    const byPath = new Map(catalog.shows.map(show => [show.path, show]));
    return [...new Set(catalog.artists[artistPath] || [])].map(path => byPath.get(path))
      .filter(show => show && (show.end || show.date || '') >= day)
      .sort((a, b) => a.date.localeCompare(b.date))
      .map(show => {
        // Published locations already use the site's state/province suffix.
        const place = /^(.*),\s*([A-Z]{2})$/.exec(show.location || '');
        return {id: `catalog:${show.path}`, canonicalPath: show.path, title: show.name,
          startDate: show.date, endDate: show.end || show.date, venue: show.venue,
          city: place ? place[1] : show.location || '', state: place ? place[2] : ''};
      });
  }

  function eventHref(event, catalog, artistPath) {
    const path = canonicalEventPath(event, catalog, artistPath);
    if (path) return path;
    if (event?.id) return `${BASE}event/?id=${encodeURIComponent(event.id)}`;
    return event?.officialUrl || event?.ticketUrl || `${BASE}shows/`;
  }

  function nextShowLabel(event) {
    const raw = String(event?.startDate || "").slice(0, 10);
    const date = /^\d{4}-\d{2}-\d{2}$/.test(raw)
      ? new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(new Date(`${raw}T12:00:00Z`))
      : raw;
    return [date, [event?.city, event?.state].filter(Boolean).join(", ")].filter(Boolean).join(" · ");
  }

  function syncDirectoryFilters(controls, apply, browser) {
    const { artistSelect, stateSelect, monthSelect, upcomingOnly, reset } = controls;
    const defaultUpcoming = upcomingOnly.defaultChecked;
    const selects = { artist: artistSelect, state: stateSelect, month: monthSelect };
    function restore() {
      const params = new URL(browser.location.href).searchParams;
      Object.entries(selects).forEach(([key, select]) => {
        const wanted = params.get(key) || "";
        const option = Array.from(select.options).find(item => norm(item.value) === norm(wanted));
        select.value = option?.value || "";
      });
      upcomingOnly.checked = params.has("upcoming") ? params.get("upcoming") !== "0" : defaultUpcoming;
      apply();
    }
    function change() {
      const url = new URL(browser.location.href);
      Object.entries(selects).forEach(([key, select]) => {
        if (select.value) url.searchParams.set(key, select.value);
        else url.searchParams.delete(key);
      });
      url.searchParams.set("upcoming", upcomingOnly.checked ? "1" : "0");
      // Replace this directory visit, so Back from a show restores its filters
      // without stepping through each individual selection.
      try { browser.history.replaceState(browser.history.state, "", url.pathname + url.search + url.hash); } catch (_) {}
      apply();
    }
    [...Object.values(selects), upcomingOnly].forEach(control => control.addEventListener("change", change));
    reset.addEventListener("click", () => {
      Object.values(selects).forEach(select => { select.value = ""; });
      upcomingOnly.checked = false;
      change();
    });
    browser.addEventListener("popstate", restore);
    browser.addEventListener("pageshow", restore);
    restore();
    return restore;
  }

  function emptyMessage(upcomingOnly) {
    return upcomingOnly
      ? 'No artists with upcoming shows match these filters. Uncheck “Only artists with upcoming shows” to include all artists.'
      : "No artists match those filters.";
  }

  function installStyles() {
    if (document.getElementById("kc-artist-directory-filter-styles")) return;
    const style = document.createElement("style");
    style.id = "kc-artist-directory-filter-styles";
    style.textContent = `
      .kc-directory-toolbar{display:block!important;margin-bottom:24px!important}
      .kc-artist-filter-form{display:grid!important;grid-template-columns:minmax(180px,1.2fr) minmax(150px,.9fr) minmax(165px,.95fr) minmax(220px,1.05fr) auto!important;align-items:end!important;gap:12px!important;width:100%!important}
      .kc-artist-filter-form .field{min-width:0!important}
      .kc-artist-filter-form select{width:100%!important;min-height:48px!important}
      .kc-artist-filter-form .reset-button{min-height:48px!important;white-space:nowrap!important}
      .kc-upcoming-check{display:flex!important;align-items:center!important;gap:9px!important;min-height:48px!important;margin:0!important;padding:0 4px!important;white-space:nowrap!important}
      .kc-upcoming-check input{width:18px!important;height:18px!important;flex:0 0 auto!important;margin:0!important;accent-color:var(--gold,#c84a32)}
      .kc-directory-toolbar .results-count{margin:12px 0 0!important;text-align:right!important}
      .kc-directory-dashboard .kc-artist-jump{display:none!important}
      .kc-directory-dashboard{grid-template-columns:minmax(170px,.75fr) minmax(260px,1.35fr)!important}
      @media(max-width:1050px){
        .kc-artist-filter-form{grid-template-columns:1fr 1fr 1fr!important}
        .kc-upcoming-check{grid-column:1/3!important}
        .kc-artist-filter-form .reset-button{width:100%!important}
      }
      @media(max-width:820px){
        .kc-artist-filter-form{grid-template-columns:1fr 1fr!important}
        .kc-upcoming-check{grid-column:1/2!important}
        .kc-directory-dashboard{grid-template-columns:1fr 1fr!important}
      }
      @media(max-width:560px){
        .kc-artist-filter-form{grid-template-columns:1fr!important}
        .kc-upcoming-check{grid-column:auto!important}
        .kc-directory-toolbar .results-count{text-align:left!important}
        .kc-directory-dashboard{grid-template-columns:1fr!important}
      }
      @media (max-width: 600px) {
        .seo-card-socials {
          display: grid !important;
          grid-template-columns: repeat(4, 38px) !important;
          column-gap: 2px !important;
          row-gap: 0 !important;
          justify-content: center !important;
          align-items: center !important;
          width: 100% !important;
          margin: 10px 0 4px !important;
        }
        .seo-card-socials .seo-social-link {
          display: grid !important;
          place-items: center !important;
          width: 38px !important;
          height: 38px !important;
          min-width: 38px !important;
          padding: 6px !important;
          margin: 0 !important;
        }
        .seo-card-socials .seo-brand-icon {
          width: 22px !important;
          height: 22px !important;
          flex-basis: 22px !important;
        }
        .seo-artist-card .artist-card-footer { margin-top: 8px !important; }
      }
    `;
    document.head.appendChild(style);
  }

  async function loadDirectoryData() {
    const [eventsResponse, supplementalResponse, artistsResponse, catalogResponse] = await Promise.all([
      fetch(`${BASE}events.json`, { cache: "no-store" }),
      fetch(`${BASE}supplemental-events.json`, { cache: "no-store" }),
      fetch(`${BASE}config/artists.json`, { cache: "no-store" }),
      fetch(`${BASE}assets/fan-show-catalog.json`, { cache: "no-cache" }).catch(() => null)
    ]);

    if (!eventsResponse.ok || !artistsResponse.ok) {
      throw new Error("Artist directory filter data could not be loaded");
    }

    const primary = await eventsResponse.json();
    const supplemental = supplementalResponse.ok ? await supplementalResponse.json() : [];
    const artists = await artistsResponse.json();
    const catalog = catalogResponse?.ok ? await catalogResponse.json().catch(() => null) : null;
    if (!Array.isArray(primary) || !Array.isArray(artists)) {
      throw new Error("Artist directory filter data is malformed");
    }

    const canonicalByAlias = new Map();
    artists.forEach(artist => {
      const name = norm(artist?.name);
      if (!name) return;
      canonicalByAlias.set(name, name);
      (artist?.aliases || []).forEach(alias => canonicalByAlias.set(norm(alias), name));
    });

    const merged = [];
    const seen = new Set();
    [...primary, ...(Array.isArray(supplemental) ? supplemental : [])]
      .filter(event => event && typeof event === "object" && isUpcoming(event) && isPublished(event))
      .forEach(event => {
        const key = eventKey(event);
        if (seen.has(key)) return;
        seen.add(key);
        merged.push(event);
      });

    const showsByArtist = new Map();
    merged.forEach(event => {
      const attached = new Set();
      (event.artists || []).forEach(rawName => {
        const canonical = canonicalByAlias.get(norm(rawName)) || norm(rawName);
        if (!canonical || attached.has(canonical)) return;
        attached.add(canonical);
        if (!showsByArtist.has(canonical)) showsByArtist.set(canonical, []);
        showsByArtist.get(canonical).push(event);
      });
    });

    showsByArtist.forEach(shows => {
      shows.sort((a, b) =>
        String(a.startDate || "").localeCompare(String(b.startDate || "")) ||
        String(a.startTime || "").localeCompare(String(b.startTime || ""))
      );
    });

    return { artists, merged, canonicalByAlias, showsByArtist, catalog };
  }

  function cardArtistName(card) {
    return card.querySelector("h2 a")?.textContent?.trim() || "";
  }

  function updateCardShows(card, shows, filtered, catalog) {
      const nextShow = shows[0];
      const count = card.querySelector(".artist-card-body > p");
      if (count) count.textContent = `${shows.length} ${filtered ? "matching" : "upcoming"} show${shows.length === 1 ? "" : "s"}`;
      const line = card.querySelector(".seo-card-next");
      const strong = line?.querySelector("strong");
      const states = card.querySelector(".seo-card-states");
      if (states) {
        const title = document.createElement("strong");
        title.textContent = filtered ? "Matching:" : "Upcoming:";
        const values = [...new Set(shows.map(event => event.state).filter(Boolean))].join(", ");
        states.replaceChildren(title, document.createTextNode(` ${values}`));
        states.hidden = !values;
      }
      if (!line || !strong) return;
      line.hidden = !nextShow;
      if (!nextShow) return;
      strong.textContent = filtered ? "Next match:" : "Next:";

      const label = document.createElement("a");
      label.className = "seo-card-next-link text-link";
      label.href = eventHref(nextShow, catalog, card.querySelector("h2 a")?.getAttribute("href"));
      label.setAttribute("aria-label", `Open ${cardArtistName(card) || "artist"} next${filtered ? " matching" : ""} show`);
      label.textContent = nextShowLabel(nextShow);
      line.replaceChildren(strong, document.createTextNode(" "), label);
  }

  function removeDuplicateArtistJump() {
    const select = document.querySelector("[data-kc-artist-jump]");
    select?.closest(".kc-artist-jump")?.remove();
  }

  function ensureFilterMarkup() {
    const directory = document.querySelector("[data-artist-directory]");
    if (!directory) return false;
    let toolbar = directory.querySelector(".directory-toolbar");
    if (!toolbar) {
      toolbar = document.createElement("div");
      toolbar.className = "directory-toolbar kc-directory-toolbar";
      directory.prepend(toolbar);
    }
    if (!toolbar.querySelector("[data-directory-artist-filter]") || !toolbar.querySelector("[data-has-shows-filter]")) {
      toolbar.classList.add("kc-directory-toolbar");
      toolbar.innerHTML = `<form class="filters kc-artist-filter-form" data-artist-directory-filters aria-label="Filter artists"><label class="field"><span>Artist</span><select data-directory-artist-filter><option value="">All artists</option></select></label><label class="field"><span>State</span><select data-directory-state-filter><option value="">All states</option></select></label><label class="field"><span>Month</span><select data-directory-month-filter><option value="">All months</option></select></label><label class="check-field kc-upcoming-check"><input data-has-shows-filter type="checkbox"> Only artists with upcoming shows</label><button class="reset-button" data-directory-reset-filters type="button">Clear filters</button></form><p class="results-count" data-artist-count>Loading...</p>`;
    }
    const empty = directory.querySelector("[data-artist-empty]");
    if (empty) empty.textContent = "No artists match those filters.";
    const state = toolbar.querySelector("[data-directory-state-filter]");
    const stateLabel = state?.closest("label")?.querySelector("span");
    if (stateLabel) stateLabel.textContent = "State / province";
    return true;
  }

  async function installDirectoryFilters() {
    if (!ensureFilterMarkup()) return;
    const grid = document.querySelector("[data-artist-grid]");
    const artistSelect = document.querySelector("[data-directory-artist-filter]");
    const stateSelect = document.querySelector("[data-directory-state-filter]");
    const monthSelect = document.querySelector("[data-directory-month-filter]");
    const upcomingOnly = document.querySelector("[data-has-shows-filter]");
    const reset = document.querySelector("[data-directory-reset-filters]");
    const count = document.querySelector("[data-artist-count]");
    const empty = document.querySelector("[data-artist-empty]");
    if (!grid || !artistSelect || !stateSelect || !monthSelect || !upcomingOnly || !reset) return;

    let data;
    try {
      data = await loadDirectoryData();
    } catch (error) {
      console.warn("Unable to build artist directory filters", error);
      return;
    }

    const artistNames = data.artists
      .filter(artist => artist?.enabled !== false && artist?.name)
      .map(artist => String(artist.name).trim())
      .sort((a, b) => a.localeCompare(b, "en", { sensitivity: "base" }));

    artistSelect.innerHTML = '<option value="">All artists</option>' + artistNames
      .map(name => `<option value="${name.replace(/&/g, "&amp;").replace(/"/g, "&quot;")}">${name.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</option>`)
      .join("");

    const states = [...new Set(data.merged.map(event => String(event?.state || "").trim().toUpperCase()).filter(Boolean))]
      .sort((a, b) => (STATE_NAMES[a] || a).localeCompare(STATE_NAMES[b] || b));
    stateSelect.innerHTML = '<option value="">All states / provinces</option>' + states
      .map(code => `<option value="${code}">${STATE_NAMES[code] || code}</option>`)
      .join("");

    const months = [...new Set(data.merged.map(event => monthKey(event?.startDate)).filter(Boolean))].sort();
    monthSelect.innerHTML = '<option value="">All months</option>' + months
      .map(key => `<option value="${key}">${monthLabel(key)}</option>`)
      .join("");

    function enrichAndApply() {
      const cards = [...grid.querySelectorAll("[data-artist-card]")];
      if (!cards.length) return;

      cards.forEach(card => {
        const displayName = cardArtistName(card);
        const canonical = data.canonicalByAlias.get(norm(displayName)) || norm(displayName);
        const artistPath = card.querySelector("h2 a")?.getAttribute("href");
        const shows = catalogArtistShows(data.catalog, artistPath) ?? uniqueArtistShows(
          (data.showsByArtist.get(canonical) || []).filter(event => isUpcoming(event)), data.catalog, artistPath);
        const statesForArtist = [...new Set(shows.map(event => String(event?.state || "").trim().toUpperCase()).filter(Boolean))];
        const monthsForArtist = [...new Set(shows.map(event => monthKey(event?.startDate)).filter(Boolean))];
        card.dataset.directoryArtist = canonical;
        card.dataset.directoryStates = statesForArtist.join("|");
        card.dataset.directoryMonths = monthsForArtist.join("|");
        card.dataset.directoryHasShows = shows.length > 0 ? "true" : "false";
        card._kcUpcomingShows = shows;
      });

      const selectedArtist = norm(artistSelect.value);
      const selectedState = String(stateSelect.value || "").toUpperCase();
      const selectedMonth = String(monthSelect.value || "");
      const requireUpcoming = upcomingOnly.checked;
      let visible = 0;

      cards.forEach(card => {
        const cardArtist = card.dataset.directoryArtist || norm(cardArtistName(card));
        const shows = Array.isArray(card._kcUpcomingShows) ? card._kcUpcomingShows : [];
        const matchedShows = matchingShows(shows, selectedState, selectedMonth);
        const matchesEventPair = matchedShows.length > 0;
        const hasUpcoming = card.dataset.directoryHasShows === "true";
        const matches =
          (!selectedArtist || cardArtist === selectedArtist) &&
          ((!selectedState && !selectedMonth) || matchesEventPair) &&
          (!requireUpcoming || hasUpcoming);

        card.hidden = !matches;
        if (matches) {
          updateCardShows(card, matchedShows, Boolean(selectedState || selectedMonth), data.catalog);
          card.style.removeProperty("display");
          card.removeAttribute("aria-hidden");
          visible += 1;
        } else {
          card.style.setProperty("display", "none", "important");
          card.setAttribute("aria-hidden", "true");
        }
      });

      if (count) count.textContent = visible === cards.length ? `${visible} artists` : `${visible} showing · ${cards.length} total`;
      if (empty) {
        empty.hidden = visible !== 0;
        empty.textContent = visible === 0 ? emptyMessage(requireUpcoming) : empty.textContent;
      }
      removeDuplicateArtistJump();
    }

    const restoreFilters = syncDirectoryFilters(
      { artistSelect, stateSelect, monthSelect, upcomingOnly, reset }, enrichAndApply, window
    );
    const refreshCatalog = event => {
      const catalog = event?.detail || window.KCFanCatalog;
      if (Array.isArray(catalog?.shows) && catalog.artists) data.catalog = catalog;
      enrichAndApply();
    };
    document.addEventListener('kc:catalog-updated', refreshCatalog);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshCatalog(); });
    window.setInterval(refreshCatalog, 60000);
    refreshCatalog();

    let scheduled = false;
    const observer = new MutationObserver(() => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        restoreFilters();
      });
    });
    observer.observe(grid, { childList: true });

  }

  function install() {
    installStyles();
    installDirectoryFilters();
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { matchingShows, eventHref, canonicalEventPath, uniqueArtistShows, catalogArtistShows, catalogToday, isUpcoming, nextShowLabel, updateCardShows, syncDirectoryFilters, emptyMessage, STATE_NAMES };
  }
  if (typeof document === "undefined") return;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
