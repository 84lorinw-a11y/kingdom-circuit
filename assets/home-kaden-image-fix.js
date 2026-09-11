"use strict";

(() => {
  const artist = "kaden jordan";
  const src = "https://open.voidware.de/artist/0mbpzxELAS9luV27PUDEZH";
  const fallback = "/assets/event-fallback.webp";
  const normalize = value => String(value || "").toLowerCase().replace(/’/g, "'").replace(/\s+/g, " ").trim();

  function fix(card) {
    if (!(card instanceof Element)) return;
    if (normalize(card.querySelector(".artist-line")?.textContent || "") !== artist) return;
    const img = card.querySelector(".event-media img");
    if (!img) return;
    img.classList.remove("event-artwork");
    img.classList.add("artist-photo");
    img.onerror = function () {
      this.onerror = null;
      this.src = fallback;
    };
    if (img.getAttribute("src") !== src) img.setAttribute("src", src);
  }

  function start() {
    if (document.body?.dataset?.page !== "home") return;
    const grid = document.querySelector("[data-event-grid]");
    if (!grid) return;
    grid.querySelectorAll(".event-card").forEach(fix);
    new MutationObserver(() => grid.querySelectorAll(".event-card").forEach(fix))
      .observe(grid, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
