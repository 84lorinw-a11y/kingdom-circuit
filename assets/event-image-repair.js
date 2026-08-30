"use strict";

(() => {
  const fallback = "/assets/event-fallback.webp";
  const stale = new Set([
    "https://fivetwentycollective.com/wp-content/uploads/2021/03/Rare-of-Breed.jpg",
    "https://rareofbreed.com/cdn/shop/files/202511_RareOfBreed_TheWarehouse-32.jpg?v=1784663742&width=3840",
    "https://ugc.production.linktr.ee/0f6ee994-7bd6-4821-bb79-593f035ae2c9_1F523223-FD9A-4E86-88BE-0A34120C8FAD.jpeg?io=true&size=avatar-v3_0",
    "https://i.scdn.co/image/ab6761610000e5ebe8717d1df4abebcd56989c30"
  ]);
  const candidates = {
    "808 beezy": ["https://pbs.twimg.com/profile_images/1836827722309312512/e5kgorwv.jpg", "https://open.voidware.de/artist/3CltJZLndpJKtpUyRVBB1k"],
    "hulvey": ["https://s1.ticketm.net/dam/a/d4e/a49ecab3-089d-46ff-baa5-7942c994ed4e_SOURCE", "https://open.voidware.de/artist/3zSrc5vUlUxyDdS0KrxFJO"],
    "yumiya!": ["/assets/artists/yumiya-primary.jpg"],
    "rare of breed": ["/assets/artists/rare-of-breed-primary.jpg"],
    "issac mansfield": ["https://i.scdn.co/image/ab6761610000e5eb6d97dd155baa40ea3c14b616", "https://open.voidware.de/artist/1QgXbOPk6XpELZrJOzz33w"],
    "zauntee": ["/assets/artists/zauntee.webp", "https://open.voidware.de/artist/7jyr9Co4MKL1iWML1G7vch"],
    "anike": ["https://resources.tidal.com/images/108dfb26/84ff/447e/b0b7/a3e208c409ed/750x750.jpg", "https://open.voidware.de/artist/0GdzQJqgRL5SHp7kXOKba0"],
    "brenno": ["https://cdn.rapzilla.com/wp-content/uploads/2020/10/23100333/277A3516-e1603484188893.jpg", "https://open.voidware.de/artist/7lBcEp7abNiq3WyHT3RRqV"],
    "parris chariz": ["https://www.invubu.com/images/artists/1200/parris_chariz.jpg", "https://open.voidware.de/artist/2Vt6gyhUH7Vj2cybfQWOqM"],
    "nobigdyl.": ["https://resources.tidal.com/images/66d1df15/192b/4a8f/97c3/30a2b85a36f3/750x750.jpg", "https://open.voidware.de/artist/2d8NsBa8O4C6bgQatFP5V4"],
    "jet trouble": ["https://55promotion.com/kbm24/wp-content/uploads/2025/06/Promo-Headshot-1024x1024.jpg", "https://open.voidware.de/artist/6W2lyFO79SNpk3ZpF0A2s9"],
    "mike teezy": ["https://real.fm/assets/Uploads/MikeTeezy__FocusFillWyItMC4xMSIsIi0wLjE2IiwxMjAwLDYyN10.jpg", "https://open.voidware.de/artist/6tO2zQcTIRfR2Xdsm9XnL7"]
  };

  const normalize = value => String(value || "").toLowerCase().replace(/’/g, "'").replace(/\s+/g, " ").trim();

  function artistKey(img) {
    const explicit = normalize(img?.dataset?.kcEventArtist);
    if (explicit && candidates[explicit]) return explicit;
    const root = img?.closest?.(".event-card, .event-detail, main") || img?.parentElement;
    const artistLine = normalize(root?.querySelector?.(".artist-line")?.textContent || "");
    const text = artistLine || normalize(root?.textContent || "");
    return Object.keys(candidates).find(key => text.includes(key)) || "";
  }

  window.kcEventImageFallback = img => {
    if (!img) return;
    const key = artistKey(img);
    const options = candidates[key] || [];
    const current = String(img.getAttribute("src") || "");
    let index = Number.parseInt(img.dataset.kcImageIndex || "-1", 10) + 1;
    if (index < options.length) {
      img.dataset.kcImageIndex = String(index);
      img.src = options[index];
      return;
    }
    img.onerror = null;
    if (!current.includes(fallback)) img.src = fallback;
  };

  function repair(img) {
    const key = artistKey(img);
    const src = String(img.getAttribute("src") || "");
    if (!key) {
      img.onerror = () => { img.onerror = null; img.src = fallback; };
      return;
    }
    const options = candidates[key];
    const forcePrimary = key === "rare of breed" || key === "yumiya!";
    let idx = options.indexOf(src);
    img.dataset.kcEventArtist = key;
    img.dataset.kcImageIndex = String(idx);
    img.onerror = () => window.kcEventImageFallback(img);
    if (forcePrimary && src !== options[0]) {
      img.dataset.kcImageIndex = "0";
      img.src = options[0];
      return;
    }
    if (!src || src.includes("event-fallback.webp") || stale.has(src)) {
      img.dataset.kcImageIndex = "0";
      img.src = options[0];
    }
  }

  const run = () => document.querySelectorAll(".event-card img, .event-detail img").forEach(repair);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run, { once: true });
  else run();
})();
