"use strict";

console.info("Kingdom Circuit production multipage build loaded");

const BASE = "/";
const LIVE_EVENTS_URL = `${BASE}events.json`;
const LIVE_ARTISTS_URL = `${BASE}config/artists.json`;
const SITE_BUILD = "production-v1";
const SUPPLEMENTAL_EVENTS_URL = `${BASE}supplemental-events.json?v=2`;
const RUN_STATUS_URL = `${BASE}run-status.json`;
const FALLBACK_EVENT_IMAGE = `${BASE}assets/event-fallback.webp`;
const STATE_NAMES = {AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",CO:"Colorado",CT:"Connecticut",DE:"Delaware",DC:"District of Columbia",FL:"Florida",GA:"Georgia",HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming"};

const ARTIST_OVERRIDES = {
  "kb": {
    spotifyProfile: "https://open.spotify.com/artist/77IKXFvO7SpWrq8hflrUXc"
  },
  "skema boy": {
    imageUrl: "assets/artists/skema-boy.webp",
    instagramProfile: "https://www.instagram.com/skema.boy/",
    spotifyProfile: "https://open.spotify.com/artist/1KTljUXZGt7HkAFFEnDBn1",
    youtubeProfile: "https://www.youtube.com/@skemaboy",
    officialProfile: "https://rixonentertainment.com/skema-boy"
  },
  "zauntee": {
    imageUrl: "assets/artists/zauntee.webp",
    imagePosition: "50% 32%",
    officialProfile: "https://zauntee.com/",
    instagramProfile: "https://www.instagram.com/zauntee/",
    youtubeProfile: "https://www.youtube.com/results?search_query=Zauntee+official"
  }
};

let EVENTS = [];
let ARTISTS = [];

const esc = value => String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
const normalize = value => String(value || "").trim().toLocaleLowerCase();

async function loadJson(primary, fallback) {
  try {
    const response = await fetch(primary, { cache: "no-store" });
    if (!response.ok) throw new Error(`${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn(`Primary data unavailable; using ${fallback}`, error);
    const response = await fetch(`${BASE}${fallback}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Could not load ${fallback}`);
    return await response.json();
  }
}

async function loadOptionalJson(url) {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.warn("Supplemental event data was unavailable.", error);
    return [];
  }
}

function applyArtistOverrides(artists) {
  return artists.map(artist => ({ ...artist, ...(ARTIST_OVERRIDES[normalize(artist.name)] || {}) }));
}

function eventArtistSet(event) {
  return new Set((event.artists || []).map(normalize));
}

function sameEvent(existing, incoming) {
  if (!existing || !incoming || existing.startDate !== incoming.startDate) return false;
  if (normalize(existing.city) !== normalize(incoming.city)) return false;
  const sameVenue = normalize(existing.venue) && normalize(existing.venue) === normalize(incoming.venue);
  const existingArtists = eventArtistSet(existing);
  const sharedArtist = [...eventArtistSet(incoming)].some(name => existingArtists.has(name));
  return sameVenue || sharedArtist;
}

function shouldUseIncomingImage(existing, incoming) {
  if (!incoming.image) return false;
  if (incoming.imageOverride) return true;
  if (!existing.image) return true;
  const current = normalize(existing.image);
  return current === "assets/event-fallback.webp" || current.endsWith("/assets/event-fallback.webp") || existing.imageType === "fallback";
}

function mergeEventLists(primary, supplemental) {
  const merged = primary.map(event => ({ ...event, artists: [...(event.artists || [])] }));
  supplemental.forEach(incoming => {
    const existing = merged.find(event => sameEvent(event, incoming));
    if (!existing) {
      merged.push(incoming);
      return;
    }
    existing.artists = [...new Set([...(existing.artists || []), ...(incoming.artists || [])])];
    if (shouldUseIncomingImage(existing, incoming)) {
      existing.image = incoming.image;
      existing.imageType = incoming.imageType || existing.imageType;
      existing.imagePosition = incoming.imagePosition || existing.imagePosition;
    }
    if (!existing.firstSeen) existing.firstSeen = incoming.firstSeen;
  });
  return merged;
}

function localAssetUrl(value) {
  if (!value) return "";
  if (/^https?:\/\//i.test(value)) return value.replace(/^http:\/\//i, "https://");
  return `${BASE}${value.replace(/^\//, "")}`;
}

function artistConfig(name) {
  const target = normalize(name);
  return ARTISTS.find(artist => normalize(artist.name) === target || (artist.aliases || []).some(alias => normalize(alias) === target));
}

function eventImage(event) {
  const config = artistConfig(event.headliner || event.artists?.[0]);
  return localAssetUrl(event.image || config?.imageUrl) || FALLBACK_EVENT_IMAGE;
}

function imageClass(event) {
  return event.imageType === "event_artwork" ? "event-artwork" : "artist-photo";
}

function imagePosition(event) {
  return event.imagePosition || artistConfig(event.headliner)?.imagePosition || "center";
}

function parseLocalDate(value) {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day, 12, 0, 0, 0);
}

function formatDate(event) {
  const date = parseLocalDate(event.startDate);
  if (!date) return "Date to be announced";
  let text = new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" }).format(date);
  if (event.startTime) {
    const [hour, minute] = event.startTime.split(":").map(Number);
    const time = new Date(2000, 0, 1, hour, minute || 0);
    text += ` - ${new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(time)}`;
  }
  return text;
}

function sourceText(event) {
  return event.sourceName || event.sources?.[0]?.name || "Official source";
}

function eventDetailUrl(event) {
  return `${BASE}event/?id=${encodeURIComponent(event.id)}`;
}

function artistProfileUrl(name) {
  return `${BASE}artists/profile/?name=${encodeURIComponent(name)}`;
}

function artistLinks(event) {
  return (event.artists || []).map(name => `<a href="${artistProfileUrl(name)}">${esc(name)}</a>`).join(" - ");
}

function isNew(event) {
  if (!event.firstSeen) return false;
  const seen = new Date(event.firstSeen);
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 14);
  return seen >= cutoff;
}

function eventCard(event) {
  const search = [event.title, event.venue, event.city, event.state, event.sourceName, ...(event.artists || [])].join(" ").toLocaleLowerCase();
  const artists = (event.artists || []).map(normalize).join("|");
  const img = eventImage(event);
  const location = [event.city, event.state].filter(Boolean).join(", ") || "Location to be announced";
  const price = event.price ? `<p class="price-line">Listed price: ${esc(event.price)}</p>` : "";
  const recent = isNew(event) ? `<span class="badge">New to Kingdom Circuit</span>` : "";
  return `<article class="event-card" data-event-card data-search="${esc(search)}" data-artists="${esc(artists)}" data-state="${esc(event.state || "")}" data-type="${esc(event.eventType || "concert")}" data-date="${esc(event.startDate || "")}" data-end-date="${esc(event.endDate || event.startDate || "")}">
    <a class="event-media" href="${eventDetailUrl(event)}" aria-label="View ${esc(event.title)}"><img class="${imageClass(event)}" src="${esc(img)}" alt="${esc(event.title)} image" loading="lazy" style="object-position:${esc(imagePosition(event))}" onerror="this.onerror=null;this.className='event-artwork';this.src='${FALLBACK_EVENT_IMAGE}';"></a>
    <div class="event-content"><div class="event-main"><div class="event-badges"><span class="badge badge-gold">${esc(event.eventType === "festival" ? "Festival" : "Concert")}</span>${recent}</div><h3><a href="${eventDetailUrl(event)}">${esc(event.title)}</a></h3><p class="artist-line">${artistLinks(event)}</p><dl class="event-meta"><div><dt>Date</dt><dd>${esc(formatDate(event))}</dd></div><div><dt>Venue</dt><dd>${esc(event.venue || "Venue to be announced")}</dd></div><div><dt>Location</dt><dd>${esc(location)}</dd></div></dl>${price}</div><div class="event-footer"><a class="official-button" href="${esc(event.officialUrl || event.ticketUrl || "#")}" target="_blank" rel="noopener">Official details</a><p class="source-line">Source: ${esc(sourceText(event))}</p></div></div>
  </article>`;
}

function filterEvents(mode) {
  const today = new Date();
  if (mode === "festival") return EVENTS.filter(event => event.eventType === "festival");
  if (mode === "month") return EVENTS.filter(event => { const date = parseLocalDate(event.startDate); return date && date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth(); });
  if (mode === "new") return EVENTS.filter(isNew);
  return EVENTS;
}

function fillSelect(select, values, labeler = value => value) {
  if (!select) return;
  const first = select.querySelector("option");
  select.innerHTML = first ? first.outerHTML : "";
  values.forEach(value => select.insertAdjacentHTML("beforeend", `<option value="${esc(value)}">${esc(labeler(value))}</option>`));
}

function startOfDay(value) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function dateMatchesMode(startDate, endDate, mode) {
  if (!mode || mode === "all") return true;
  const today = startOfDay(new Date());
  const start = parseLocalDate(startDate);
  const end = parseLocalDate(endDate) || start;
  if (!start || !end) return false;
  if (mode === "next30") { const last = new Date(today); last.setDate(last.getDate() + 30); return end >= today && start <= last; }
  if (mode === "month") return start.getFullYear() === today.getFullYear() && start.getMonth() === today.getMonth();
  if (mode === "weekend") { const friday = new Date(today); friday.setDate(friday.getDate() + ((5 - today.getDay() + 7) % 7)); const sunday = new Date(friday); sunday.setDate(sunday.getDate() + 2); return end >= friday && start <= sunday; }
  return true;
}

function setupEventFilters(cards) {
  const form = document.querySelector("[data-event-filters]");
  if (!form) return;
  const search = form.querySelector("[data-search-filter]");
  const artist = form.querySelector("[data-artist-filter]");
  const state = form.querySelector("[data-state-filter]");
  const type = form.querySelector("[data-type-filter]");
  const reset = form.querySelector("[data-reset-filters]");
  const count = document.querySelector("[data-results-count]");
  const empty = document.querySelector("[data-filtered-empty]");
  const chips = [...document.querySelectorAll(".filter-chip[data-date-mode],.filter-chip[data-type-mode]")];
  let dateMode = "all";
  const params = new URLSearchParams(location.search);
  if (params.get("artist") && artist) artist.value = normalize(params.get("artist"));
  if (params.get("state") && state) state.value = params.get("state").toUpperCase();

  function apply() {
    const needle = normalize(search?.value);
    const artistValue = artist?.value || "";
    const stateValue = state?.value || "";
    const typeValue = type?.value || "";
    let visible = 0;
    cards.forEach(card => {
      const names = (card.dataset.artists || "").split("|");
      const match = (!needle || (card.dataset.search || "").includes(needle)) && (!artistValue || names.includes(artistValue)) && (!stateValue || card.dataset.state === stateValue) && (!typeValue || card.dataset.type === typeValue) && dateMatchesMode(card.dataset.date, card.dataset.endDate, dateMode);
      card.hidden = !match;
      if (match) visible += 1;
    });
    if (count) count.textContent = `${visible} show${visible === 1 ? "" : "s"}`;
    if (empty) empty.hidden = visible !== 0;
  }

  [search, artist, state, type].forEach(control => control?.addEventListener(control === search ? "input" : "change", apply));
  chips.forEach(chip => chip.addEventListener("click", () => {
    if (chip.dataset.typeMode) { if (type) type.value = chip.dataset.typeMode; dateMode = "all"; }
    else { dateMode = chip.dataset.dateMode || "all"; if (type) type.value = ""; }
    chips.forEach(item => item.classList.remove("active"));
    chip.classList.add("active");
    apply();
  }));
  reset?.addEventListener("click", () => { form.reset(); dateMode = "all"; chips.forEach(item => item.classList.toggle("active", item.dataset.dateMode === "all")); apply(); });
  apply();
}

function renderEventList() {
  const grid = document.querySelector("[data-event-grid]");
  if (!grid) return;
  const mode = document.querySelector("[data-event-list-mode]")?.dataset.eventListMode || "all";
  const list = filterEvents(mode).sort((a, b) => (a.startDate || "").localeCompare(b.startDate || "") || (a.startTime || "").localeCompare(b.startTime || ""));
  grid.innerHTML = list.map(eventCard).join("");
  document.querySelector("[data-loading-panel]")?.remove();
  const artistValues = [...new Set(list.flatMap(event => event.artists || []).map(normalize))].sort();
  const displayByNorm = new Map(list.flatMap(event => event.artists || []).map(name => [normalize(name), name]));
  fillSelect(document.querySelector("[data-artist-filter]"), artistValues, value => displayByNorm.get(value) || value);
  const states = [...new Set(list.map(event => event.state).filter(Boolean))].sort();
  fillSelect(document.querySelector("[data-state-filter]"), states, state => STATE_NAMES[state] || state);
  setupEventFilters([...grid.querySelectorAll("[data-event-card]")]);
  if (mode === "month") {
    const now = new Date();
    const label = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(now);
    const title = document.querySelector("[data-current-month-title]");
    if (title) title.textContent = `Christian Hip-Hop Shows in ${label}`;
    document.querySelector("[data-month-show-count]")?.replaceChildren(String(list.length));
    document.querySelector("[data-month-state-count]")?.replaceChildren(String(new Set(list.map(event => event.state).filter(Boolean)).size));
    document.querySelector("[data-month-festival-count]")?.replaceChildren(String(list.filter(event => event.eventType === "festival").length));
  }
}

function friendlyCategory(value) {
  return ({core:"Core CHH",reach:"Reach Records",crossover:"Crossover",group:"Group",legacy:"Legacy"})[value] || "CHH artist";
}

function spotifyInfo(artist) {
  const directProfile = artist.spotifyProfile || (artist.spotifyId ? `https://open.spotify.com/artist/${encodeURIComponent(artist.spotifyId)}` : "");
  if (directProfile) return { url: directProfile, exact: true, status: "Open verified Spotify profile" };
  return { url: "", exact: false, status: "Spotify link pending verification" };
}

function instagramInfo(artist) {
  return artist.instagramProfile ? { url: artist.instagramProfile, status: "Open verified Instagram profile" } : { url: "", status: "Instagram link pending verification" };
}

function youtubeInfo(artist) {
  const official = artist.youtubeProfile || (/youtu\.be|youtube\.com/i.test(artist.officialProfile || "") ? artist.officialProfile : "");
  return official ? { url: official, status: "Open verified YouTube profile" } : { url: "", status: "YouTube link pending verification" };
}

function websiteInfo(artist) {
  const candidate = artist.website || artist.officialWebsite || artist.officialProfile || "";
  const isPlatform = /instagram\.com|open\.spotify\.com|youtu\.be|youtube\.com|music\.apple\.com|bandsintown\.com/i.test(candidate);
  return candidate && !isPlatform ? { url: candidate, status: "Open official website" } : { url: "", status: "Website link pending verification" };
}

function compactPlatformLink(label, info) {
  if (!info.url) return `<span class="artist-platform-link is-missing" title="${esc(info.status)}">${esc(label)}</span>`;
  return `<a class="artist-platform-link" href="${esc(info.url)}" target="_blank" rel="noopener" title="${esc(info.status)}">${esc(label)}</a>`;
}

function renderArtistDirectory() {
  const grid = document.querySelector("[data-artist-grid]");
  if (!grid) return;
  const byArtist = new Map();
  EVENTS.forEach(event => (event.artists || []).forEach(name => {
    const key = normalize(name);
    if (!byArtist.has(key)) byArtist.set(key, []);
    byArtist.get(key).push(event);
  }));
  const enabled = ARTISTS.filter(artist => artist.enabled !== false).sort((a, b) => (a.rosterOrder || 9999) - (b.rosterOrder || 9999) || a.name.localeCompare(b.name));
  grid.innerHTML = enabled.map(artist => {
    const events = byArtist.get(normalize(artist.name)) || [];
    const instagram = instagramInfo(artist);
    const spotify = spotifyInfo(artist);
    return `<article class="artist-card artist-card-text" data-artist-card data-search="${esc(normalize([artist.name, ...(artist.aliases || []), artist.label].join(" ")))}" data-has-shows="${events.length > 0}">
      <a class="artist-visual artist-visual-empty" href="${artistProfileUrl(artist.name)}" aria-label="View ${esc(artist.name)}"></a>
      <div class="artist-card-body"><h2><a href="${artistProfileUrl(artist.name)}">${esc(artist.name)}</a></h2><p>${events.length} upcoming show${events.length === 1 ? "" : "s"}</p><div class="artist-card-links">${compactPlatformLink("Instagram", instagram)}${compactPlatformLink("Spotify", spotify)}</div><div class="artist-card-footer"><a class="text-link" href="${artistProfileUrl(artist.name)}">View artist</a></div></div>
    </article>`;
  }).join("");
  document.querySelector("[data-artist-loading]")?.remove();
  const cards = [...grid.querySelectorAll("[data-artist-card]")];
  const search = document.querySelector("[data-artist-search]");
  const show = document.querySelector("[data-has-shows-filter]");
  const count = document.querySelector("[data-artist-count]");
  const empty = document.querySelector("[data-artist-empty]");
  function apply() {
    const needle = normalize(search?.value);
    const requireShows = Boolean(show?.checked);
    let visible = 0;
    cards.forEach(card => {
      const ok = (!needle || (card.dataset.search || "").includes(needle)) && (!requireShows || card.dataset.hasShows === "true");
      card.hidden = !ok;
      if (ok) visible += 1;
    });
    if (count) count.textContent = `${visible} artist${visible === 1 ? "" : "s"}`;
    if (empty) empty.hidden = visible !== 0;
  }
  search?.addEventListener("input", apply);
  show?.addEventListener("change", apply);
  apply();
}

function platformCard(label, info) {
  if (!info.url) return `<div class="profile-platform-card is-missing"><span class="profile-platform-label">${esc(label)}</span><span class="profile-platform-status">${esc(info.status)}</span></div>`;
  return `<a class="profile-platform-card" href="${esc(info.url)}" target="_blank" rel="noopener"><span class="profile-platform-label">${esc(label)}</span><span class="profile-platform-status">${esc(info.status)}</span></a>`;
}

function renderArtistProfile() {
  const root = document.querySelector("[data-artist-profile]");
  if (!root) return;
  const name = new URLSearchParams(location.search).get("name") || "";
  const artist = artistConfig(name);
  if (!artist) {
    root.innerHTML = `<section class="page-hero hero-compact"><h1>Artist not found.</h1><a class="primary-button" href="${BASE}artists/">Return to artists</a></section>`;
    return;
  }
  const events = EVENTS.filter(event => (event.artists || []).some(item => normalize(item) === normalize(artist.name))).sort((a, b) => (a.startDate || "").localeCompare(b.startDate || ""));
  root.innerHTML = `<section class="profile-hero profile-hero-no-image"><div><p class="eyebrow">Artist profile</p><h1>${esc(artist.name)}</h1><p class="profile-image-note">Artist image pending verification.</p><div class="profile-platforms">${platformCard("Instagram", instagramInfo(artist))}${platformCard("Spotify", spotifyInfo(artist))}${platformCard("YouTube", youtubeInfo(artist))}${platformCard("Website", websiteInfo(artist))}</div><p class="profile-count">${events.length} upcoming U.S. show${events.length === 1 ? "" : "s"} currently listed.</p></div></section><section class="calendar"><div class="calendar-heading"><div><p class="eyebrow">Verified listings</p><h2>Upcoming ${esc(artist.name)} Shows</h2></div><p class="results-count">${events.length} shows</p></div><div class="event-grid">${events.map(eventCard).join("") || '<div class="empty-panel">No upcoming U.S. shows are currently confirmed.</div>'}</div></section>`;
  document.title = `${artist.name} Shows | The Kingdom Circuit`;
  ensureCanonical(`${location.origin}${BASE}artists/profile/?name=${encodeURIComponent(artist.name)}`);
  setMetaDescription(`Find verified upcoming U.S. shows and official links for ${artist.name}.`);
}

function renderEventDetail() {
  const root = document.querySelector("[data-event-detail]");
  if (!root) return;
  const id = new URLSearchParams(location.search).get("id");
  const event = EVENTS.find(item => item.id === id);
  if (!event) {
    root.innerHTML = `<section class="page-hero hero-compact"><h1>Event not found.</h1><a class="primary-button" href="${BASE}shows/">View all shows</a></section>`;
    return;
  }
  const img = eventImage(event);
  const locationText = [event.city, event.state].filter(Boolean).join(", ");
  root.innerHTML = `<article class="event-detail"><div class="event-detail-media"><img class="${imageClass(event)}" src="${esc(img)}" alt="${esc(event.title)}" style="object-position:${esc(imagePosition(event))}" onerror="this.onerror=null;this.className='event-artwork';this.src='${FALLBACK_EVENT_IMAGE}';"></div><div class="event-detail-copy"><p class="eyebrow">${esc(event.eventType === "festival" ? "Festival" : "Concert")}</p><h1>${esc(event.title)}</h1><p class="artist-line">${artistLinks(event)}</p><dl class="detail-list"><div><dt>Date</dt><dd>${esc(formatDate(event))}</dd></div><div><dt>Venue</dt><dd>${esc(event.venue || "Venue to be announced")}</dd></div><div><dt>Location</dt><dd>${esc(locationText || "Location to be announced")}</dd></div>${event.price ? `<div><dt>Price</dt><dd>${esc(event.price)}</dd></div>` : ""}<div><dt>Source</dt><dd>${esc(sourceText(event))}</dd></div></dl><a class="primary-button" href="${esc(event.officialUrl || event.ticketUrl || "#")}" target="_blank" rel="noopener">Official details</a><p class="disclaimer">Event details, availability, pricing, and lineups may change. Confirm final information with the official organizer or ticket provider before purchasing or traveling.</p></div></article>`;
  document.title = `${event.title} | The Kingdom Circuit`;
  ensureCanonical(`${location.origin}${BASE}event/?id=${encodeURIComponent(event.id)}`);
  setMetaDescription(`${event.title} in ${locationText || "the United States"}. View verified event details and the official source.`);
}


function ensureCanonical(url) {
  let link = document.querySelector('link[rel="canonical"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "canonical";
    document.head.appendChild(link);
  }
  link.href = url;
}

function setMetaDescription(text) {
  let meta = document.querySelector('meta[name="description"]');
  if (!meta) {
    meta = document.createElement("meta");
    meta.name = "description";
    document.head.appendChild(meta);
  }
  meta.content = text;
}

async function renderCalendarStatus() {
  const root = document.querySelector("[data-calendar-status]");
  if (!root) return;
  try {
    const response = await fetch(RUN_STATUS_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(String(response.status));
    const status = await response.json();
    const updated = status.lastSuccessfulUpdate || status.lastAttempt;
    const updatedText = updated
      ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(new Date(updated))
      : "Update time unavailable";
    const warnings = Number(status.warningCount || 0);
    const published = Number(status.eventsPublished || EVENTS.length || 0);
    root.innerHTML = `<span><strong>Calendar updated:</strong> ${esc(updatedText)}</span><span>${published} automated listing${published === 1 ? "" : "s"}</span>${warnings ? `<span class="footer-source-warning">${warnings} source check${warnings === 1 ? "" : "s"} unavailable; published listings remain verified.</span>` : ""}`;
    root.hidden = false;
  } catch (error) {
    console.warn("Calendar status was unavailable.", error);
    root.hidden = true;
  }
}

function setMenuOpen(open) {
  const toggle = document.querySelector(".menu-toggle");
  const drawer = document.querySelector(".menu-drawer");
  const backdrop = document.querySelector(".menu-backdrop");
  if (!toggle || !drawer || !backdrop) return;
  toggle.setAttribute("aria-expanded", String(open));
  drawer.setAttribute("aria-hidden", String(!open));
  drawer.classList.toggle("open", open);
  backdrop.hidden = !open;
  document.body.classList.toggle("menu-open", open);
}

document.querySelector(".menu-toggle")?.addEventListener("click", () => setMenuOpen(document.querySelector(".menu-toggle")?.getAttribute("aria-expanded") !== "true"));
document.querySelector(".menu-close")?.addEventListener("click", () => setMenuOpen(false));
document.querySelector(".menu-backdrop")?.addEventListener("click", () => setMenuOpen(false));
document.addEventListener("keydown", event => { if (event.key === "Escape") setMenuOpen(false); });

function setupSubmissionForm() {
  const form = document.querySelector("[data-submission-form]");
  if (!form) return;
  const feedback = form.querySelector("[data-submission-feedback]");
  const submit = form.querySelector("[data-submission-submit]");
  const kind = form.querySelector("[data-submission-kind]");
  const eventName = form.querySelector("[data-event-name]");
  const buttons = [...form.querySelectorAll("[data-submission-mode]")];
  const params = new URLSearchParams(location.search);
  function setMode(value) {
    if (kind) kind.value = value;
    buttons.forEach(button => button.classList.toggle("active", button.dataset.submissionMode === value));
    if (submit) submit.textContent = value === "Correction" ? "Send Correction" : "Send for Review";
  }
  buttons.forEach(button => button.addEventListener("click", () => setMode(button.dataset.submissionMode || "New show")));
  if ((params.get("type") || "").includes("correction")) setMode("Correction");
  if (params.get("event") && eventName) eventName.value = params.get("event");
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    if (feedback) feedback.textContent = "Sending submission...";
    if (submit) submit.disabled = true;
    try {
      const response = await fetch(form.action, { method: "POST", body: new FormData(form), headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error();
      form.reset();
      setMode("New show");
      if (feedback) feedback.textContent = "Submission received. The Kingdom Circuit will review the information before publishing or updating the event.";
    } catch {
      if (feedback) feedback.textContent = "The submission could not be sent. Please try again in a few minutes.";
    } finally {
      if (submit) submit.disabled = false;
    }
  });
}

async function boot() {
  try {
    const [liveEvents, liveArtists, supplemental] = await Promise.all([
      loadJson(LIVE_EVENTS_URL, "events.json"),
      loadJson(LIVE_ARTISTS_URL, "config/artists.json"),
      loadOptionalJson(SUPPLEMENTAL_EVENTS_URL)
    ]);
    ARTISTS = applyArtistOverrides(liveArtists);
    EVENTS = mergeEventLists(liveEvents, supplemental);
  } catch (error) {
    console.error(error);
    document.querySelectorAll(".loading-panel").forEach(element => { element.textContent = "The calendar could not load its data. Please refresh in a moment."; });
    return;
  }
  renderEventList();
  renderArtistDirectory();
  renderArtistProfile();
  renderEventDetail();
  setupSubmissionForm();
  renderCalendarStatus();
}

boot();
