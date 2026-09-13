"use strict";

// Reliable direct image sources for artists whose registry image reference is a
// profile/page URL rather than a directly embeddable image. These are only
// presentation overrides; the canonical source URLs remain in the registry.
const KC_ARTIST_IMAGE_OVERRIDES = {
  "808 beezy": "https://pbs.twimg.com/profile_images/1836827722309312512/e5kgorwv.jpg",
  "parris chariz": "https://images.squarespace-cdn.com/content/v1/5dcb525470489e545ccc40e9/1712680680873-0035Z6FC03TADRGONB2Y/parris%2Bchariz.jpeg",
  "mike teezy": "https://real.fm/assets/Uploads/MikeTeezy__FocusFillWyItMC4xMSIsIi0wLjE2IiwxMjAwLDYyN10.jpg",
  "porsha love": "https://unavatar.io/instagram/porshalove",
  "nicky gracious": "https://unavatar.io/instagram/nickygracious",
  "asap preach": "https://unavatar.io/instagram/asappreach",
  "kijan boone": "https://unavatar.io/instagram/kijanboone",
  "don ready": "https://unavatar.io/instagram/donready",
  "y shadey": "https://unavatar.io/instagram/yshadey",
  "dante' pride": "https://unavatar.io/instagram/dantepride",
  "rare of breed": "https://unavatar.io/instagram/rareofbreed",
  "brother bo": "https://unavatar.io/instagram/brotherbo",
  "tommy chapa": "https://unavatar.io/instagram/tommychapa",
  "b. cody shields": "https://unavatar.io/instagram/bcodyshields",
  "santana rose": "https://unavatar.io/instagram/santanarose",
  "dj winn": "https://unavatar.io/instagram/djwinn",
  "big holy": "https://unavatar.io/instagram/bigholy",
  "redeemed": "https://unavatar.io/instagram/redeemed",
  "rua young": "https://is1-ssl.mzstatic.com/image/thumb/AMCArtistImages221/v4/b5/c9/41/b5c941ba-b72a-0e77-ac56-a1599aa0a2e6/file_cropped.png/4653x4653bb.jpg",
  "kurtis hoppie": "https://i.scdn.co/image/ab6761610000e5eb26d1bb2607e2ef0ea4328051",
  "holy gabbana": "https://static.wixstatic.com/media/b944f9_2e07baa6dfe148559bac17e750f7c8dd~mv2.png/v1/fill/w_412%2Ch_880%2Cfp_0.50_0.38%2Cq_90%2Cusm_0.66_1.00_0.01%2Cenc_avif%2Cquality_auto/IMG_5036_HEIC.png",
  "christopher syncere": "https://i.scdn.co/image/ab6761610000e5eb58b2b20624119284dbf7e303"
};

// Direct Spotify identities verified independently for rows whose sheet value is
// still a search URL. Used only to resolve a thumbnail, not to replace the
// canonical registry field in this patch.
const KC_SPOTIFY_PROFILE_OVERRIDES = {
  "brother bo": "https://open.spotify.com/artist/3cmp77GMj0JNM3YHYquhMo",
  "b. cody shields": "https://open.spotify.com/artist/4chyF3tNUYqQdgS0SQtOT6",
  "redeemed": "https://open.spotify.com/artist/240g9DqmeKizlyyCZtL22Y"
};

const KC_EVENT_IMAGE_OVERRIDES = {
  "supplemental:image-override-hope-fest-daytona-2026": "https://riverfrontshopsofdaytona.com/wp-content/uploads/2026/07/DDA_Events_HopeFest_2026.jpg",
  "manual:hope-fest-daytona-2026": "https://riverfrontshopsofdaytona.com/wp-content/uploads/2026/07/DDA_Events_HopeFest_2026.jpg"
};

const KC_SPOTIFY_IMAGE_CACHE = new Map();
const KC_SPOTIFY_IMAGE_INFLIGHT = new Map();
let kcRepairScheduled = false;
let kcProfileRepairInFlight = null;

function kcImageKey(value) {
  return String(value || "").trim().toLocaleLowerCase();
}

function kcDirectArtistImage(artist) {
  return KC_ARTIST_IMAGE_OVERRIDES[kcImageKey(artist?.name)] || "";
}

function kcBestHeadlinerImage(event) {
  const artist = typeof artistConfig === "function" ? artistConfig(event?.headliner || event?.artists?.[0]) : null;
  if (!artist) return "";
  const direct = kcDirectArtistImage(artist);
  if (direct) return direct;
  if (typeof artistImageInfo === "function") {
    const info = artistImageInfo(artist);
    if (info?.url) return info.url;
    if (info?.fallbackUrl) return info.fallbackUrl;
  }
  return "";
}

function kcIsBandsintownEvent(event) {
  if (String(event?.id || "").startsWith("bandsintown:")) return true;
  if (kcImageKey(event?.sourceName) === "bandsintown") return true;
  return Array.isArray(event?.sources) && event.sources.some(source => kcImageKey(source?.type) === "bandsintown_rest");
}

// Override the synchronous render helpers before app.js finishes its async boot.
if (typeof artistImageInfo === "function") {
  const kcOriginalArtistImageInfo = artistImageInfo;
  artistImageInfo = function(artist) {
    const direct = kcDirectArtistImage(artist);
    const original = kcOriginalArtistImageInfo(artist);
    if (!direct) return original;
    return {
      url: direct,
      fallbackUrl: original?.url && original.url !== direct ? original.url : (original?.fallbackUrl || ""),
      position: artist?.imagePosition || original?.position || "center"
    };
  };
}

if (typeof eventImage === "function") {
  const kcOriginalEventImage = eventImage;
  eventImage = function(event) {
    const eventOverride = KC_EVENT_IMAGE_OVERRIDES[String(event?.id || "")];
    if (eventOverride) return eventOverride;

    const currentImage = String(event?.image || "");
    if (event?.imageType === "event_artwork" && currentImage && !currentImage.includes("event-fallback")) {
      return kcOriginalEventImage(event);
    }

    if (kcIsBandsintownEvent(event)) {
      return kcBestHeadlinerImage(event) || (typeof FALLBACK_EVENT_IMAGE !== "undefined" ? FALLBACK_EVENT_IMAGE : "/assets/event-fallback.webp");
    }

    const artist = typeof artistConfig === "function" ? artistConfig(event?.headliner || event?.artists?.[0]) : null;
    const artistOverride = kcDirectArtistImage(artist);
    if (artistOverride && (!currentImage || currentImage.includes("event-fallback"))) return artistOverride;
    return kcOriginalEventImage(event);
  };
}

// Profile-only Spotify fallback. Cache both completed and in-flight lookups so a
// DOM mutation cannot start duplicate requests for the same artist.
async function kcResolveSpotifyImage(artist) {
  const key = kcImageKey(artist?.name);
  if (!key) return "";
  if (KC_SPOTIFY_IMAGE_CACHE.has(key)) return KC_SPOTIFY_IMAGE_CACHE.get(key);
  if (KC_SPOTIFY_IMAGE_INFLIGHT.has(key)) return KC_SPOTIFY_IMAGE_INFLIGHT.get(key);

  const profile = KC_SPOTIFY_PROFILE_OVERRIDES[key] || String(artist?.spotifyProfile || "");
  if (!/^https:\/\/open\.spotify\.com\/artist\/[A-Za-z0-9]+/i.test(profile)) {
    KC_SPOTIFY_IMAGE_CACHE.set(key, "");
    return "";
  }

  const request = (async () => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 3500);
    try {
      const response = await fetch(`https://open.spotify.com/oembed?url=${encodeURIComponent(profile)}`, {
        mode: "cors",
        signal: controller.signal
      });
      if (!response.ok) return "";
      const data = await response.json();
      return /^https?:\/\//i.test(data?.thumbnail_url || "") ? data.thumbnail_url : "";
    } catch {
      return "";
    } finally {
      window.clearTimeout(timer);
    }
  })();

  KC_SPOTIFY_IMAGE_INFLIGHT.set(key, request);
  const resolved = await request;
  KC_SPOTIFY_IMAGE_INFLIGHT.delete(key);
  KC_SPOTIFY_IMAGE_CACHE.set(key, resolved);
  return resolved;
}

function kcSetArtistVisual(card, url, artistName) {
  if (!card || !url) return;
  const visual = card.querySelector(".artist-visual");
  if (!visual) return;
  let img = visual.querySelector("img");
  if (!img) {
    visual.classList.remove("artist-visual-empty");
    visual.textContent = "";
    img = document.createElement("img");
    img.alt = artistName || "Artist";
    img.loading = "lazy";
    img.decoding = "async";
    img.referrerPolicy = "no-referrer";
    visual.appendChild(img);
  }
  if (img.getAttribute("src") !== url) {
    img.dataset.kcImageRepair = "true";
    img.onerror = () => {
      img.onerror = null;
      const fallback = img.dataset.fallbackSrc || "";
      if (fallback && img.getAttribute("src") !== fallback) {
        img.src = fallback;
        return;
      }
      visual.classList.add("artist-visual-empty");
      visual.textContent = String(artistName || "?").trim().charAt(0).toUpperCase() || "?";
    };
    img.src = url;
  }
}

// Never fan out Spotify oEmbed requests across the full artist directory. The
// previous implementation could start overlapping full-directory repair passes
// whenever a missing image inserted a child node, which became expensive as the
// roster grew. Directory repair is now synchronous and limited to known direct
// overrides; ordinary registry images/fallbacks remain handled by app.js.
function kcRepairArtistCards() {
  if (typeof ARTISTS === "undefined" || !Array.isArray(ARTISTS)) return;
  const artistsByKey = new Map(ARTISTS.map(artist => [kcImageKey(artist?.name), artist]));
  document.querySelectorAll("[data-artist-card]").forEach(card => {
    const key = kcImageKey(card.dataset.artistKey);
    const artist = artistsByKey.get(key);
    if (!artist) return;
    const existing = card.querySelector(".artist-visual img");
    if (existing && existing.complete && existing.naturalWidth > 0) return;
    const direct = kcDirectArtistImage(artist);
    if (direct) kcSetArtistVisual(card, direct, artist.name);
  });
}

async function kcRepairArtistProfile() {
  const root = document.querySelector("[data-artist-profile]");
  if (!root || typeof artistConfig !== "function") return;
  if (kcProfileRepairInFlight) return kcProfileRepairInFlight;

  kcProfileRepairInFlight = (async () => {
    const name = new URLSearchParams(location.search).get("name") || "";
    const artist = artistConfig(name);
    if (!artist) return;
    const current = root.querySelector(".profile-visual img");
    if (current && current.complete && current.naturalWidth > 0) return;
    const direct = kcDirectArtistImage(artist) || await kcResolveSpotifyImage(artist);
    if (!direct) return;
    const hero = root.querySelector(".profile-hero");
    if (!hero) return;
    let visual = hero.querySelector(".profile-visual");
    if (!visual) {
      visual = document.createElement("div");
      visual.className = "profile-visual";
      hero.prepend(visual);
    }
    let img = visual.querySelector("img");
    if (!img) {
      img = document.createElement("img");
      img.alt = artist.name || "Artist";
      img.decoding = "async";
      img.referrerPolicy = "no-referrer";
      visual.appendChild(img);
    }
    if (img.getAttribute("src") !== direct) img.src = direct;
    hero.classList.remove("profile-hero-no-image");
    root.querySelector(".profile-image-note")?.remove();
  })();

  try {
    await kcProfileRepairInFlight;
  } finally {
    kcProfileRepairInFlight = null;
  }
}

function kcRepairEventCards() {
  const hopeImage = KC_EVENT_IMAGE_OVERRIDES["manual:hope-fest-daytona-2026"];
  document.querySelectorAll(".event-card, .event-detail").forEach(card => {
    const text = (card.textContent || "").toLocaleLowerCase();
    const img = card.querySelector("img");
    if (!img) return;
    if (text.includes("hope fest 2026")) {
      if (img.getAttribute("src") !== hopeImage) img.src = hopeImage;
      return;
    }
    if (String(img.getAttribute("src") || "").includes("/assets/event-fallback.webp")) {
      for (const [artistName, url] of Object.entries(KC_ARTIST_IMAGE_OVERRIDES)) {
        if (!text.includes(artistName)) continue;
        if (img.getAttribute("src") !== url) img.src = url;
        return;
      }
    }
  });
}

function kcRepairImages() {
  kcRepairEventCards();
  kcRepairArtistCards();
  void kcRepairArtistProfile();
}

function kcScheduleRepair() {
  if (kcRepairScheduled) return;
  kcRepairScheduled = true;
  window.requestAnimationFrame(() => {
    kcRepairScheduled = false;
    kcRepairImages();
  });
}

function kcStartImageRepair() {
  kcScheduleRepair();
  const roots = [
    document.querySelector("[data-event-grid]"),
    document.querySelector("[data-event-detail]"),
    document.querySelector("[data-artist-grid]"),
    document.querySelector("[data-artist-profile]")
  ].filter(Boolean);

  if (roots.length) {
    const observer = new MutationObserver(kcScheduleRepair);
    roots.forEach(root => observer.observe(root, { childList: true, subtree: true }));
  }

  window.setTimeout(kcScheduleRepair, 500);
  window.setTimeout(kcScheduleRepair, 1500);
}

if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", kcStartImageRepair, { once: true });
} else {
  kcStartImageRepair();
}
