"use strict";

(() => {
  const fallback = "/assets/event-fallback.webp";
  const targets = [
    {
      artist: "rare of breed",
      src: "/assets/artists/rare-of-breed-primary.jpg?v=20260830-home-1"
    },
    {
      artist: "yumiya!",
      src: "/assets/artists/yumiya-primary.jpg?v=20260830-home-1"
    }
  ];

  const normalize = value => String(value || "").toLowerCase().replace(/’/g, "'").replace(/\s+/g, " ").trim();

  function enforceCard(card) {
    if (!(card instanceof Element)) return;
    const artistLine = normalize(card.querySelector(".artist-line")?.textContent || "");
    const target = targets.find(item => artistLine.includes(item.artist));
    if (!target) return;

    const img = card.querySelector(".event-media img");
    if (!img) return;

    img.dataset.kcPrimaryLocked = "1";
    img.classList.remove("event-artwork");
    img.classList.add("artist-photo");
    img.onerror = function () {
      this.onerror = null;
      this.src = fallback;
    };

    if (img.getAttribute("src") !== target.src) {
      img.setAttribute("src", target.src);
    }
  }

  function enforceGrid(grid) {
    grid.querySelectorAll(".event-card").forEach(enforceCard);
  }

  function start() {
    if (document.body?.dataset?.page !== "home") return;
    const grid = document.querySelector("[data-event-grid]");
    if (!grid) return;

    enforceGrid(grid);
    const observer = new MutationObserver(() => enforceGrid(grid));
    observer.observe(grid, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
