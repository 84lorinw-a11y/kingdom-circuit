"use strict";

// Reliable direct image sources for artists whose registry image reference is a
// profile/page URL rather than a directly embeddable image. These are only
// presentation overrides; the canonical source URLs remain in the registry.
const KC_ARTIST_IMAGE_OVERRIDES = {
  "808 beezy": "https://pbs.twimg.com/profile_images/1836827722309312512/e5kgorwv.jpg",
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

    // Bandsintown rows may contain a guessed local file path that does not exist.
    // Ignore that guessed event path and use the best verified image we already
    // have for the headliner. If no headliner image exists yet, fall back to the
    // site's standard event artwork rather than rendering a broken image.
    if (kcIsBandsintownEvent(event)) {
      return kcBestHeadlinerImage(event) || (typeof FALLBACK_EVENT_IMAGE !== "undefined" ? FALLBACK_EVENT_IMAGE : "/assets/event-fallback.webp");
    }

    const artist = typeof artistConfig === "function" ? artistConfig(event?.headliner || event?.artists?.[0]) : null;
    const artistOverride = kcDirectArtistImage(artist);
    if (artistOverride && !event?.image) return artistOverride;
    return kcOriginalEventImage(event);
  };
}

// Spotify's oEmbed response can supply a direct thumbnail for verified direct
// artist profiles. This fills remaining registry cards without treating search
// URLs or generic page URLs as images.
async function kcResolveSpotifyImage(artist) {
  const key = kcImageKey(artist?.name);
  const profile = KC_SPOTIFY_PROFILE_OVERRIDES[key] || String(artist?.spotifyProfile || "");
  if (!/^https:\/\/open\.spotify\.com\/artist\/[A-Za-z0-9]+/i.test(profile)) return "";
  try {
    const response = await fetch(`https://open.spotify.com/oembed?url=${encodeURIComponent(profile)}`, { mode: "cors" });
    if (!response.ok) return "";
    const data = await response.json();
    return /^https?:\/\//i.test(data?.thumbnail_url || "") ? data.thumbnail_url : "";
  } catch {
    return "";
  }
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
  if (img.src !== url) {
    img.dataset.kcImageRepair = "true";
    img.onerror = () => {
      img.onerror = null;
      const fallback = img.dataset.fallbackSrc || "";
      if (fallback && img.src !== fallback) {
        img.src = fallback;
        return;
      }
      if (visual) {
        visual.classList.add("artist-visual-empty");
        visual.textContent = String(artistName || "?").trim().charAt(0).toUpperCase() || "?";
      }
    };
    img.src = url;
  }
}

async function kcRepairArtistCards() {
  if (typeof ARTISTS === "undefined" || !Array.isArray(ARTISTS)) return;
  for (const artist of ARTISTS) {
    const key = kcImageKey(artist?.name);
    const card = [...document.querySelectorAll("[data-artist-card]")]
      .find(node => kcImageKey(node.dataset.artistKey) === key);
    if (!card) continue;
    const existing = card.querySelector(".artist-visual img");
    if (existing && existing.complete && existing.naturalWidth > 0) continue;
    const direct = kcDirectArtistImage(artist) || await kcResolveSpotifyImage(artist);
    if (direct) kcSetArtistVisual(card, direct, artist.name);
  }
}

async function kcRepairArtistProfile() {
  const root = document.querySelector("[data-artist-profile]");
  if (!root || typeof artistConfig !== "function") return;
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
  img.src = direct;
  hero.classList.remove("profile-hero-no-image");
  root.querySelector(".profile-image-note")?.remove();
}

function kcRepairEventCards() {
  const hopeImage = KC_EVENT_IMAGE_OVERRIDES["manual:hope-fest-daytona-2026"];
  document.querySelectorAll(".event-card, .event-detail").forEach(card => {
    const text = (card.textContent || "").toLocaleLowerCase();
    const img = card.querySelector("img");
    if (!img) return;
    if (text.includes("hope fest 2026")) {
      if (img.src !== hopeImage) img.src = hopeImage;
      return;
    }
    if (text.includes("808 beezy")) {
      const beezy = KC_ARTIST_IMAGE_OVERRIDES["808 beezy"];
      if (img.src !== beezy) img.src = beezy;
    }
  });
}

function kcRepairImages() {
  kcRepairEventCards();
  void kcRepairArtistCards();
  void kcRepairArtistProfile();
}

const kcImageObserver = new MutationObserver(() => kcRepairImages());
kcImageObserver.observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("DOMContentLoaded", kcRepairImages, { once: true });
window.setTimeout(kcRepairImages, 500);
window.setTimeout(kcRepairImages, 1500);
