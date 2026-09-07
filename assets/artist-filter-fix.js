"use strict";

(() => {
  const BASE = "/";
  const STATE_NAMES = {
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

  function isUpcoming(event) {
    const raw = String(event?.endDate || event?.startDate || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return true;
    const today = new Date();
    const localToday = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0")
    ].join("-");
    return raw >= localToday;
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

  function eventHref(event) {
    if (event?.id) return `${BASE}event/?id=${encodeURIComponent(event.id)}`;
    return event?.officialUrl || event?.ticketUrl || `${BASE}shows/`;
  }

  function installStyles() {
    if (document.getElementById("kc-artist-directory-filter-styles")) return;
    const style = document.createElement("style");
    style.id = "kc-artist-directory-filter-styles";
    style.textContent = `
      .kc-directory-toolbar{display:block!important;margin-bottom:24px!important}
      .kc-artist-filter-form{display:grid!important;grid-template-columns:minmax(190px,1.25fr) minmax(165px,.9fr) minmax(175px,.95fr) auto!important;align-items:end!important;gap:12px!important;width:100%!important}
      .kc-artist-filter-form .field{min-width:0!important}
      .kc-artist-filter-form select{width:100%!important;min-height:48px!important}
      .kc-artist-filter-form .reset-button{min-height:48px!important;white-space:nowrap!important}
      .kc-directory-toolbar .results-count{margin:12px 0 0!important;text-align:right!important}
      .kc-directory-dashboard .kc-artist-jump{display:none!important}
      .kc-directory-dashboard{grid-template-columns:minmax(170px,.75fr) minmax(260px,1.35fr)!important}
      @media(max-width:820px){
        .kc-artist-filter-form{grid-template-columns:1fr 1fr!important}
        .kc-artist-filter-form .reset-button{width:100%!important}
        .kc-directory-dashboard{grid-template-columns:1fr 1fr!important}
      }
      @media(max-width:560px){
        .kc-artist-filter-form{grid-template-columns:1fr!important}
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
    const [eventsResponse, supplementalResponse, artistsResponse] = await Promise.all([
      fetch(`${BASE}events.json`, { cache: "no-store" }),
      fetch(`${BASE}supplemental-events.json`, { cache: "no-store" }),
      fetch(`${BASE}config/artists.json`, { cache: "no-store" })
    ]);

    if (!eventsResponse.ok || !artistsResponse.ok) {
      throw new Error("Artist directory filter data could not be loaded");
    }

    const primary = await eventsResponse.json();
    const supplemental = supplementalResponse.ok ? await supplementalResponse.json() : [];
    const artists = await artistsResponse.json();
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
      .filter(event => event && typeof event === "object" && isUpcoming(event))
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

    return { artists, merged, canonicalByAlias, showsByArtist };
  }

  function cardArtistName(card) {
    return card.querySelector("h2 a")?.textContent?.trim() || "";
  }

  function linkNextShows(cards, showsByArtist) {
    cards.forEach(card => {
      const artistName = norm(cardArtistName(card));
      const nextShow = showsByArtist.get(artistName)?.[0];
      const line = card.querySelector(".seo-card-next");
      const strong = line?.querySelector("strong");
      if (!nextShow || !line || !strong || line.querySelector("a")) return;

      const label = document.createElement("a");
      label.className = "seo-card-next-link text-link";
      label.href = eventHref(nextShow);
      label.setAttribute("aria-label", `Open ${cardArtistName(card) || "artist"} next show`);

      const trailingNodes = [];
      let node = strong.nextSibling;
      while (node) {
        const next = node.nextSibling;
        trailingNodes.push(node);
        node = next;
      }
      trailingNodes.forEach(item => label.appendChild(item));
      line.appendChild(label);
    });
  }

  function removeDuplicateArtistJump() {
    const select = document.querySelector("[data-kc-artist-jump]");
    select?.closest(".kc-artist-jump")?.remove();
  }

  async function installDirectoryFilters() {
    const grid = document.querySelector("[data-artist-grid]");
    const artistSelect = document.querySelector("[data-directory-artist-filter]");
    const stateSelect = document.querySelector("[data-directory-state-filter]");
    const monthSelect = document.querySelector("[data-directory-month-filter]");
    const reset = document.querySelector("[data-directory-reset-filters]");
    const count = document.querySelector("[data-artist-count]");
    const empty = document.querySelector("[data-artist-empty]");
    if (!grid || !artistSelect || !stateSelect || !monthSelect || !reset) return;

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
    stateSelect.innerHTML = '<option value="">All states</option>' + states
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
        const shows = data.showsByArtist.get(canonical) || [];
        const statesForArtist = [...new Set(shows.map(event => String(event?.state || "").trim().toUpperCase()).filter(Boolean))];
        const monthsForArtist = [...new Set(shows.map(event => monthKey(event?.startDate)).filter(Boolean))];
        card.dataset.directoryArtist = canonical;
        card.dataset.directoryStates = statesForArtist.join("|");
        card.dataset.directoryMonths = monthsForArtist.join("|");
      });

      const selectedArtist = norm(artistSelect.value);
      const selectedState = String(stateSelect.value || "").toUpperCase();
      const selectedMonth = String(monthSelect.value || "");
      let visible = 0;

      cards.forEach(card => {
        const cardArtist = card.dataset.directoryArtist || norm(cardArtistName(card));
        const cardStates = new Set((card.dataset.directoryStates || "").split("|").filter(Boolean));
        const cardMonths = new Set((card.dataset.directoryMonths || "").split("|").filter(Boolean));
        const matches =
          (!selectedArtist || cardArtist === selectedArtist) &&
          (!selectedState || cardStates.has(selectedState)) &&
          (!selectedMonth || cardMonths.has(selectedMonth));

        card.hidden = !matches;
        if (matches) {
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
        empty.textContent = visible === 0 ? "No artists match those filters." : empty.textContent;
      }
      removeDuplicateArtistJump();
      linkNextShows(cards, data.showsByArtist);
    }

    artistSelect.addEventListener("change", enrichAndApply);
    stateSelect.addEventListener("change", enrichAndApply);
    monthSelect.addEventListener("change", enrichAndApply);
    reset.addEventListener("click", () => {
      artistSelect.value = "";
      stateSelect.value = "";
      monthSelect.value = "";
      enrichAndApply();
    });

    let scheduled = false;
    const observer = new MutationObserver(() => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        enrichAndApply();
      });
    });
    observer.observe(grid, { childList: true });

    enrichAndApply();
  }

  function install() {
    installStyles();
    installDirectoryFilters();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
