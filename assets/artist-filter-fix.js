"use strict";

(() => {
  const BASE = "/";

  function norm(value) {
    return String(value || "").trim().toLowerCase();
  }

  function installMobileSocialGridStyles() {
    if (document.getElementById("kc-mobile-social-grid")) return;
    const style = document.createElement("style");
    style.id = "kc-mobile-social-grid";
    style.textContent = `
      @media (max-width: 600px) {
        .seo-card-socials {
          display: grid !important;
          grid-template-columns: repeat(2, max-content) !important;
          gap: 10px 12px !important;
          justify-content: center !important;
          align-items: center !important;
          width: 100% !important;
          margin-left: 0 !important;
          margin-right: 0 !important;
        }
        .seo-card-socials .seo-social-link {
          margin: 0 !important;
        }
      }
    `;
    document.head.appendChild(style);
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

  async function linkNextShows() {
    const cards = [...document.querySelectorAll("[data-artist-card]")];
    if (!cards.length) return;

    try {
      const [eventsResponse, supplementalResponse, artistsResponse] = await Promise.all([
        fetch(`${BASE}events.json`, { cache: "no-store" }),
        fetch(`${BASE}supplemental-events.json`, { cache: "no-store" }),
        fetch(`${BASE}config/artists.json`, { cache: "no-store" })
      ]);

      if (!eventsResponse.ok || !artistsResponse.ok) return;

      const primary = await eventsResponse.json();
      const supplemental = supplementalResponse.ok ? await supplementalResponse.json() : [];
      const artists = await artistsResponse.json();
      if (!Array.isArray(primary) || !Array.isArray(artists)) return;

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

      cards.forEach(card => {
        const artistName = norm(card.querySelector("h2 a")?.textContent);
        const nextShow = showsByArtist.get(artistName)?.[0];
        const line = card.querySelector(".seo-card-next");
        const strong = line?.querySelector("strong");
        if (!nextShow || !line || !strong || line.querySelector("a")) return;

        const label = document.createElement("a");
        label.className = "seo-card-next-link text-link";
        label.href = eventHref(nextShow);
        label.setAttribute("aria-label", `Open ${card.querySelector("h2 a")?.textContent?.trim() || "artist"} next show`);

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
    } catch (error) {
      console.warn("Unable to link artist next-show cards", error);
    }
  }

  function applyUpcomingArtistFilter() {
    const checkbox = document.querySelector("[data-has-shows-filter]");
    if (!checkbox) return;

    document.querySelectorAll("[data-artist-card]").forEach(card => {
      const hasUpcomingShows = card.dataset.hasShows === "true";
      if (checkbox.checked && !hasUpcomingShows) {
        card.style.setProperty("display", "none", "important");
        card.setAttribute("aria-hidden", "true");
      } else {
        card.style.removeProperty("display");
        card.removeAttribute("aria-hidden");
      }
    });
  }

  function install() {
    installMobileSocialGridStyles();

    const checkbox = document.querySelector("[data-has-shows-filter]");
    const grid = document.querySelector("[data-artist-grid]");
    if (!checkbox || !grid) return;

    checkbox.addEventListener("change", applyUpcomingArtistFilter);
    new MutationObserver(() => {
      applyUpcomingArtistFilter();
      linkNextShows();
    }).observe(grid, { childList: true, subtree: false });
    applyUpcomingArtistFilter();
    linkNextShows();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
