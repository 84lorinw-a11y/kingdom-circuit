"use strict";

(() => {
  const fallback = "/assets/event-fallback.webp";
  const pins = {
    "the-genesis-show-all-women-s-chh-event-2026-09-19-roswell-9d321d": "/assets/events/genesis-show-2026-all-women-v3.jpg",
    "flavor-fest-2026-saturday-concerts-2026-11-07-tampa-cf7fac": "https://images.squarespace-cdn.com/content/v1/65b435646b1eae535f97c6a3/989d4d2e-f454-4a1b-99df-cc78cf6e6749/FF26-Promo-Saturday-Night.jpg",
    "future-legacy-hip-hop-showcase-2026-10-04-nashville-4bd33c": "https://images.discovery-prod.axs.com/2026/08/uploadedimage_6a871ac3abd11.jpg",
    "miles-minnick-and-cj-emulous-at-zion-ultra-lounge-2026-12-05-chandler-bfff69": "/assets/events/miles-cj-zion-ultra-2026.svg",
    "fountain-fest-wv-2026-2026-09-18-martinsburg-1cd64d": "/assets/events/fountain-fest-wv-2026.svg",
    "mission-and-special-guests-2026-10-17-sacramento-15909d": "/assets/events/mission-friends-sacramento-2026.svg",
    "boxyard-saturdaze-2026-10-10-durham-7853b4": "/assets/events/mayia-boxyard-saturdaze-2026.svg",
    "mayia-at-the-nc-state-fair-2026-10-17-raleigh-1c07ad": "/assets/events/mayia-nc-state-fair-2026.svg",
    "syatp-concert-2026-09-23-sierra-vista-121b78": "https://static.wixstatic.com/media/9c331a_e63115b208054353a76258a4897ad76c~mv2.jpeg/v1/fill/w_980%2Ch_653%2Cal_c%2Cq_85%2Cusm_0.66_1.00_0.01%2Cenc_auto/9c331a_e63115b208054353a76258a4897ad76c~mv2.jpeg",
    "live-loud-2026-10-07-chico-1b6570": "https://static.wixstatic.com/media/9c331a_394502e64a45489e872ee2b71bb1a0de~mv2.jpg/v1/fill/w_980%2Ch_543%2Cal_c%2Cq_85%2Cusm_0.66_1.00_0.01%2Cenc_auto/9c331a_394502e64a45489e872ee2b71bb1a0de~mv2.jpg",
    "teen-club-kickoff-back-to-school-concert-2026-10-12-turlock-c869fd": "https://static.wixstatic.com/media/9c331a_7832125534df4c06b583f033fe19273e~mv2.png",
    "the-kickback-2026-11-14-grand-prairie-ce6c40": "/assets/events/cj-emulous-kickback-2026.svg",
    "alex-zurdo-zona-zero-2026-10-18-san-juan-6d6263": "/assets/events/alex-zurdo-zona-zero-2026.svg",
    "jay-kalyl-desde-antes-tour-2026-10-03-rockville-centre-8ea3e4": "/assets/events/jay-kalyl-desde-antes-2026.svg"
  };

  function slugFor(img) {
    const card = img.closest?.(".event-card");
    const href = card?.querySelector?.('a[href*="/event/"]')?.getAttribute("href") || "";
    const match = href.match(/\/event\/([^/]+)\//i);
    if (match) return match[1].toLowerCase();

    const pathMatch = location.pathname.match(/^\/event\/([^/]+)\//i);
    return pathMatch ? pathMatch[1].toLowerCase() : "";
  }

  function enforce(img) {
    if (!(img instanceof HTMLImageElement)) return;
    const slug = slugFor(img);
    const src = pins[slug];
    if (!src) return;

    img.classList.remove("artist-photo");
    img.classList.add("event-artwork");
    delete img.dataset.kcEventArtist;
    delete img.dataset.kcImageIndex;
    delete img.dataset.kcLockPrimary;
    delete img.dataset.kcPrimaryLocked;
    img.onerror = function () {
      this.onerror = null;
      this.src = fallback;
    };
    if (img.getAttribute("src") !== src) img.setAttribute("src", src);
  }

  function run() {
    document.querySelectorAll(".event-card img, .event-detail-media img").forEach(enforce);
  }

  function start() {
    run();
    if (!document.body) return;
    new MutationObserver(run).observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["src", "class"]
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
