"use strict";

(() => {
  const fallback = "/assets/event-fallback.webp";
  // Only source-authorized event/tour art or verified artist imagery belongs here.
  // Do not add Kingdom Circuit-created replacement flyers as source artwork.
  const pins = {
    "the-genesis-show-all-women-s-chh-event-2026-09-19-roswell-9d321d": "/assets/events/genesis-show-2026-all-women-v3.jpg",
    "flavor-fest-2026-saturday-concerts-2026-11-07-tampa-cf7fac": "https://images.squarespace-cdn.com/content/v1/65b435646b1eae535f97c6a3/989d4d2e-f454-4a1b-99df-cc78cf6e6749/FF26-Promo-Saturday-Night.jpg",
    "future-legacy-hip-hop-showcase-2026-10-04-nashville-4bd33c": "https://images.discovery-prod.axs.com/2026/08/uploadedimage_6a871ac3abd11.jpg",
    "miles-minnick-and-cj-emulous-at-zion-ultra-lounge-2026-12-05-chandler-bfff69": "https://i.scdn.co/image/ab6761610000e5eb88d578e199bd2ce1021def5b",
    "fountain-fest-wv-2026-2026-09-18-martinsburg-1cd64d": "https://i0.wp.com/fountainfestwv.com/wp-content/uploads/2026/07/Rare-of-Breed-Promo-.webp?resize=720%2C900&ssl=1",
    "mission-and-special-guests-2026-10-17-sacramento-15909d": "/assets/event-fallback.webp",
    "boxyard-saturdaze-2026-10-10-durham-7853b4": "https://ugc.production.linktr.ee/1c7876eb-77d1-4a43-a2db-def6b24563ac_1000010882.jpeg",
    "mayia-at-the-nc-state-fair-2026-10-17-raleigh-1c07ad": "https://ugc.production.linktr.ee/1c7876eb-77d1-4a43-a2db-def6b24563ac_1000010882.jpeg",
    "syatp-concert-2026-09-23-sierra-vista-121b78": "https://static.wixstatic.com/media/9c331a_e63115b208054353a76258a4897ad76c~mv2.jpeg/v1/fill/w_980%2Ch_653%2Cal_c%2Cq_85%2Cusm_0.66_1.00_0.01%2Cenc_auto/9c331a_e63115b208054353a76258a4897ad76c~mv2.jpeg",
    "live-loud-2026-10-07-chico-1b6570": "https://static.wixstatic.com/media/9c331a_394502e64a45489e872ee2b71bb1a0de~mv2.jpg/v1/fill/w_980%2Ch_543%2Cal_c%2Cq_85%2Cusm_0.66_1.00_0.01%2Cenc_auto/9c331a_394502e64a45489e872ee2b71bb1a0de~mv2.jpg",
    "teen-club-kickoff-back-to-school-concert-2026-10-12-turlock-c869fd": "https://static.wixstatic.com/media/9c331a_7832125534df4c06b583f033fe19273e~mv2.png",
    "the-kickback-2026-11-14-grand-prairie-ce6c40": "https://ugc.production.linktr.ee/e2e0b25c-780f-4b6f-9a4d-48461885e719_DSC01908.jpeg",
    "alex-zurdo-zona-zero-2026-10-18-san-juan-6d6263": "https://i.scdn.co/image/ab6761610000e5eb2c81bb40c3b6962eacf9dc9c",
    "jay-kalyl-desde-antes-tour-2026-10-03-rockville-centre-8ea3e4": "https://i.scdn.co/image/ab6761610000e5eb1269b80aed5d08c40aedfdc3"
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

    if (img.classList.contains("artist-photo")) img.classList.remove("artist-photo");
    if (!img.classList.contains("event-artwork")) img.classList.add("event-artwork");
    delete img.dataset.kcEventArtist;
    delete img.dataset.kcImageIndex;
    delete img.dataset.kcLockPrimary;
    delete img.dataset.kcPrimaryLocked;
    img.onerror = function () {
      this.onerror = null;
      if (this.getAttribute("src") !== fallback) this.src = fallback;
    };
    if (img.getAttribute("src") !== src) img.setAttribute("src", src);
  }

  function enforceNode(node) {
    if (!(node instanceof Element)) return;
    if (node instanceof HTMLImageElement) enforce(node);
    node.querySelectorAll?.(".event-card img, .event-detail-media img").forEach(enforce);
  }

  function run() {
    document.querySelectorAll(".event-card img, .event-detail-media img").forEach(enforce);
  }

  function start() {
    run();
    if (!document.body) return;

    // Watch only new DOM nodes and actual src rewrites. Class observation caused
    // unnecessary full-page rescans on the newly pinned events and could amplify
    // other image repair scripts. Process only the changed image/subtree instead.
    const observer = new MutationObserver(mutations => {
      for (const mutation of mutations) {
        if (mutation.type === "attributes") {
          enforce(mutation.target);
          continue;
        }
        mutation.addedNodes.forEach(enforceNode);
      }
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["src"]
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
