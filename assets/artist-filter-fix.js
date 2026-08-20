"use strict";

(() => {
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
    const checkbox = document.querySelector("[data-has-shows-filter]");
    const grid = document.querySelector("[data-artist-grid]");
    if (!checkbox || !grid) return;

    checkbox.addEventListener("change", applyUpcomingArtistFilter);
    new MutationObserver(applyUpcomingArtistFilter).observe(grid, { childList: true, subtree: false });
    applyUpcomingArtistFilter();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
