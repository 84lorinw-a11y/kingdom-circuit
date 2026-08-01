"use strict";

const REPOSITORY_URL = "https://github.com/84lorinw-a11y/kingdom-circuit";
const JUST_ANNOUNCED_DAYS = 7;

const state = {
  events: [],
  filters: {
    search: "",
    artist: "",
    state: "",
    type: "",
    dateMode: "all"
  }
};

const elements = {
  events: document.getElementById("events"),
  resultsCount: document.getElementById("results-count"),
  notice: document.getElementById("notice"),
  lastUpdated: document.getElementById("last-updated"),
  statusDot: document.getElementById("status-dot"),
  statusLabel: document.getElementById("status-label"),
  search: document.getElementById("search-filter"),
  artist: document.getElementById("artist-filter"),
  state: document.getElementById("state-filter"),
  type: document.getElementById("type-filter"),
  reset: document.getElementById("reset-filters"),
  quickFilters: [...document.querySelectorAll(".filter-chip")],
  openSubmit: document.getElementById("open-submit"),
  submissionDialog: document.getElementById("submission-dialog"),
  submissionForm: document.getElementById("submission-form"),
  submissionFeedback: document.getElementById("submission-feedback")
};

function safeHttpUrl(value) {
  try {
    const url = new URL(String(value));
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function safeImageUrl(value) {
  try {
    const url = new URL(String(value), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function safeObjectPosition(value) {
  const candidate = String(value || "").trim().toLowerCase();
  const pattern = /^(?:left|center|right|\d{1,3}(?:\.\d+)?%)(?:\s+(?:top|center|bottom|\d{1,3}(?:\.\d+)?%))?$/;
  return pattern.test(candidate) ? candidate : "center";
}

function localDate(dateText) {
  const parts = String(dateText || "").split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    return null;
  }
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function startOfDay(value) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function addDays(value, amount) {
  const result = new Date(value);
  result.setDate(result.getDate() + amount);
  return result;
}

function formatDate(dateText) {
  const value = localDate(dateText);
  if (!value) {
    return "Date not provided";
  }
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(value);
}

function formatTime(timeText) {
  if (!timeText) {
    return "";
  }
  const match = String(timeText).match(/^(\d{1,2}):(\d{2})/);
  if (!match) {
    return String(timeText);
  }
  const value = new Date(2000, 0, 1, Number(match[1]), Number(match[2]));
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit"
  }).format(value);
}

function formatUpdateTime(value) {
  if (!value) {
    return "Waiting for the first automated update";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Update time unavailable";
  }
  return `Updated ${new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short"
  }).format(parsed)}`;
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (text !== undefined) {
    element.textContent = text;
  }
  return element;
}

function eventSearchText(event) {
  return [
    event.title,
    event.venue,
    event.city,
    event.state,
    ...(Array.isArray(event.artists) ? event.artists : [])
  ].join(" ").toLowerCase();
}

function eventMatchesDateMode(event, mode) {
  if (!mode || mode === "all") {
    return true;
  }
  const start = localDate(event.startDate);
  const end = localDate(event.endDate || event.startDate);
  if (!start || !end) {
    return false;
  }

  const today = startOfDay(new Date());
  let rangeStart = today;
  let rangeEnd = today;

  if (mode === "next30") {
    rangeEnd = addDays(today, 30);
  } else if (mode === "month") {
    rangeStart = new Date(today.getFullYear(), today.getMonth(), 1);
    rangeEnd = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  } else if (mode === "weekend") {
    const day = today.getDay();
    if (day === 6) {
      rangeStart = today;
      rangeEnd = addDays(today, 1);
    } else if (day === 0) {
      rangeStart = today;
      rangeEnd = today;
    } else {
      rangeStart = addDays(today, (5 - day + 7) % 7);
      rangeEnd = addDays(rangeStart, 2);
    }
  }

  return start <= rangeEnd && end >= rangeStart;
}

function filteredEvents() {
  return state.events.filter((event) => {
    const searchMatch = !state.filters.search ||
      eventSearchText(event).includes(state.filters.search.toLowerCase());
    const artistMatch = !state.filters.artist ||
      (event.artists || []).includes(state.filters.artist);
    const stateMatch = !state.filters.state || event.state === state.filters.state;
    const typeMatch = !state.filters.type || event.eventType === state.filters.type;
    return searchMatch && artistMatch && stateMatch && typeMatch &&
      eventMatchesDateMode(event, state.filters.dateMode);
  });
}

function badge(text, className = "") {
  return createElement("span", `badge ${className}`.trim(), text);
}

function isJustAnnounced(event) {
  if (!event.firstSeen) {
    return false;
  }
  const firstSeen = new Date(event.firstSeen);
  if (Number.isNaN(firstSeen.getTime())) {
    return false;
  }
  const age = Date.now() - firstSeen.getTime();
  return age >= 0 && age <= JUST_ANNOUNCED_DAYS * 24 * 60 * 60 * 1000;
}

function eventImageAlt(event) {
  if (event.imageType === "event_artwork" || event.eventType === "festival") {
    return `Official artwork for ${event.title || "this event"}`;
  }
  const artist = event.headliner || (event.artists || [])[0] || "Christian hip-hop artist";
  return `${artist} artist image for ${event.title || "an upcoming show"}`;
}

function createEventImage(event) {
  const media = createElement("div", "event-media");
  const image = document.createElement("img");
  image.className = `event-image event-image--${event.imageType || "fallback"}`;
  image.loading = "lazy";
  image.decoding = "async";
  image.alt = eventImageAlt(event);
  image.src = safeImageUrl(event.image) || "assets/logo.png";
  image.style.objectPosition = safeObjectPosition(event.imagePosition);
  image.addEventListener("error", () => {
    if (!image.dataset.fallbackApplied) {
      image.dataset.fallbackApplied = "true";
      image.src = "assets/logo.png";
      image.alt = `The Kingdom Circuit fallback artwork for ${event.title || "this event"}`;
      image.style.objectPosition = "center";
    }
  }, { once: true });
  media.appendChild(image);
  return media;
}

function createLineup(event) {
  const artists = Array.isArray(event.artists) ? event.artists.filter(Boolean) : [];
  if (!artists.length) {
    return createElement("p", "artist-line", "Artist lineup not provided");
  }
  if (artists.length <= 4) {
    return createElement("p", "artist-line", artists.join(" · "));
  }

  const details = createElement("details", "lineup-details");
  const summary = createElement("summary", "artist-line");
  summary.append(`${artists.slice(0, 4).join(" · ")} `);
  summary.appendChild(createElement("span", "lineup-more", `+${artists.length - 4} more`));
  details.appendChild(summary);
  details.appendChild(createElement("p", "lineup-full", artists.join(" · ")));
  return details;
}

function correctionUrl(event) {
  const title = `Correction: ${event.title || "event listing"}`;
  const body = [
    "Please describe the correction and provide an official source.",
    "",
    `Event: ${event.title || ""}`,
    `Date: ${event.startDate || ""}`,
    `Location: ${event.city || ""}, ${event.state || ""}`,
    `Current official link: ${event.officialUrl || event.ticketUrl || ""}`,
    "",
    "Correction:",
    "Official source URL:"
  ].join("\n");
  return `${REPOSITORY_URL}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}

function renderEvent(event) {
  const card = createElement("article", "event-card");
  card.appendChild(createEventImage(event));

  const content = createElement("div", "event-content");
  const main = createElement("div", "event-main");
  const badges = createElement("div", "event-badges");
  badges.appendChild(badge(event.eventType === "festival" ? "Festival" : "Concert", "gold"));
  if (isJustAnnounced(event)) {
    badges.appendChild(badge("Just announced", "announced"));
  }
  if (event.status && !["scheduled", "onsale"].includes(event.status)) {
    badges.appendChild(badge(event.status, event.status === "cancelled" ? "cancelled" : ""));
  }
  if (event.stale) {
    badges.appendChild(badge("Rechecking"));
  }
  main.appendChild(badges);
  main.appendChild(createElement("h3", "", event.title || "Untitled event"));
  main.appendChild(createLineup(event));

  const meta = createElement("div", "event-meta");
  const dateLine = [formatDate(event.startDate), formatTime(event.startTime)]
    .filter(Boolean)
    .join(" · ");
  meta.appendChild(createElement("p", "", dateLine));
  const venue = event.venue && event.venue !== "Venue not provided"
    ? event.venue
    : "Venue to be announced";
  meta.appendChild(createElement(
    "p",
    "",
    [venue, [event.city, event.state].filter(Boolean).join(", ")]
      .filter(Boolean)
      .join(" · ")
  ));
  if (event.price) {
    meta.appendChild(createElement("p", "", `Listed price: ${event.price}`));
  }
  main.appendChild(meta);
  content.appendChild(main);

  const actions = createElement("div", "event-actions");
  const ticketUrl = safeHttpUrl(event.ticketUrl || event.officialUrl);
  if (ticketUrl && event.status !== "cancelled") {
    const ticket = createElement("a", "ticket-link", "Official details");
    ticket.href = ticketUrl;
    ticket.target = "_blank";
    ticket.rel = "noopener";
    actions.appendChild(ticket);
  } else {
    actions.appendChild(createElement("span", "badge cancelled", "No active ticket link"));
  }

  const sourceBlock = createElement("div", "source-link");
  const sources = (Array.isArray(event.sources) ? event.sources : [])
    .filter((source) => source && safeHttpUrl(source.url));
  if (sources.length) {
    sourceBlock.append(sources.length === 1 ? "Source: " : "Sources: ");
    sources.slice(0, 3).forEach((source, index) => {
      if (index) {
        sourceBlock.append(" · ");
      }
      const sourceAnchor = createElement("a", "", source.name || "Official source");
      sourceAnchor.href = safeHttpUrl(source.url);
      sourceAnchor.target = "_blank";
      sourceAnchor.rel = "noopener";
      sourceBlock.appendChild(sourceAnchor);
    });
    if (sources.length > 3) {
      sourceBlock.append(` · +${sources.length - 3} more`);
    }
  } else {
    sourceBlock.textContent = event.sourceName ? `Source: ${event.sourceName}` : "Source verified";
  }
  actions.appendChild(sourceBlock);

  const correction = createElement("a", "correction-link", "Report a correction");
  correction.href = correctionUrl(event);
  correction.target = "_blank";
  correction.rel = "noopener";
  actions.appendChild(correction);

  content.appendChild(actions);
  card.appendChild(content);
  return card;
}

function render() {
  const events = filteredEvents();
  elements.events.replaceChildren();
  elements.resultsCount.textContent = `${events.length} ${events.length === 1 ? "show" : "shows"}`;

  if (!events.length) {
    elements.events.appendChild(createElement(
      "div",
      "empty-state",
      "No verified shows match these filters. Clear the filters or check again after the next daily update."
    ));
    return;
  }

  const fragment = document.createDocumentFragment();
  events.forEach((event) => fragment.appendChild(renderEvent(event)));
  elements.events.appendChild(fragment);
}

function populateSelect(select, values) {
  const existing = new Set([...select.options].map((option) => option.value));
  values.forEach((value) => {
    if (!value || existing.has(value)) {
      return;
    }
    select.appendChild(new Option(value, value));
    existing.add(value);
  });
}

function updateQuickFilterState() {
  elements.quickFilters.forEach((button) => {
    const dateActive = button.dataset.dateMode && button.dataset.dateMode === state.filters.dateMode;
    const festivalActive = button.dataset.typeMode === "festival" && state.filters.type === "festival";
    button.classList.toggle("active", Boolean(dateActive || festivalActive));
    button.setAttribute("aria-pressed", String(Boolean(dateActive || festivalActive)));
  });
}

function configureFilters() {
  const artists = [...new Set(state.events.flatMap((event) => event.artists || []))]
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b));
  const states = [...new Set(state.events.map((event) => event.state))]
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b));

  populateSelect(elements.artist, artists);
  populateSelect(elements.state, states);

  elements.search.addEventListener("input", (event) => {
    state.filters.search = event.target.value.trim();
    render();
  });
  elements.artist.addEventListener("change", (event) => {
    state.filters.artist = event.target.value;
    render();
  });
  elements.state.addEventListener("change", (event) => {
    state.filters.state = event.target.value;
    render();
  });
  elements.type.addEventListener("change", (event) => {
    state.filters.type = event.target.value;
    updateQuickFilterState();
    render();
  });
  elements.quickFilters.forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.dateMode) {
        state.filters.dateMode = button.dataset.dateMode;
      }
      if (button.dataset.typeMode === "festival") {
        state.filters.type = state.filters.type === "festival" ? "" : "festival";
        elements.type.value = state.filters.type;
      }
      updateQuickFilterState();
      render();
    });
  });
  elements.reset.addEventListener("click", () => {
    state.filters = { search: "", artist: "", state: "", type: "", dateMode: "all" };
    elements.search.value = "";
    elements.artist.value = "";
    elements.state.value = "";
    elements.type.value = "";
    updateQuickFilterState();
    render();
  });
}

async function loadStatus() {
  try {
    const response = await fetch(`run-status.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Status request failed: ${response.status}`);
    }
    const status = await response.json();
    const warnings = Array.isArray(status.warnings) ? status.warnings : [];
    const errors = Array.isArray(status.errors) ? status.errors : [];
    let severity = "ok";
    if (errors.length || ["partial", "needs_configuration", "error"].includes(status.status)) {
      severity = "error";
    } else if (warnings.length || status.status === "warning") {
      severity = "warning";
    }

    elements.lastUpdated.textContent = formatUpdateTime(status.lastSuccessfulUpdate || status.lastAttempt);
    elements.statusDot.className = `status-dot ${severity}`;
    elements.statusLabel.textContent = severity === "ok"
      ? "Calendar current"
      : severity === "warning"
        ? "Calendar updated"
        : "Update issue";

    elements.notice.hidden = !(errors.length || warnings.length);
    if (!elements.notice.hidden) {
      elements.notice.className = `notice ${severity}`;
      elements.notice.textContent = errors.length
        ? `The latest update encountered ${errors.length} ${errors.length === 1 ? "error" : "errors"}. Verified listings remain available while the collector retries.`
        : `The calendar updated, but ${warnings.length} source ${warnings.length === 1 ? "check was" : "checks were"} temporarily unavailable. Published listings remain verified.`;
      elements.notice.title = [...errors, ...warnings].slice(0, 5).join("\n");
    }
  } catch {
    elements.lastUpdated.textContent = "Update status unavailable";
    elements.statusDot.className = "status-dot error";
    elements.statusLabel.textContent = "Status unavailable";
  }
}

function submissionBody() {
  return [
    "Please review this show for The Kingdom Circuit.",
    "",
    `Event name: ${document.getElementById("submit-event-name").value.trim()}`,
    `Date: ${document.getElementById("submit-date").value}`,
    `Local time: ${document.getElementById("submit-time").value || "Not provided"}`,
    `Venue: ${document.getElementById("submit-venue").value.trim()}`,
    `City and state: ${document.getElementById("submit-city").value.trim()}, ${document.getElementById("submit-state").value.trim().toUpperCase()}`,
    `Confirmed artist lineup: ${document.getElementById("submit-lineup").value.trim()}`,
    `Official event or ticket URL: ${document.getElementById("submit-url").value.trim()}`,
    `Official artwork URL: ${document.getElementById("submit-artwork").value.trim() || "Not provided"}`,
    `Submitter relationship: ${document.getElementById("submit-relationship").value.trim()}`,
    "",
    "Confirmation: This is a U.S. music performance and the source above is official or directly authorized."
  ].join("\n");
}

function configureSubmissionDialog() {
  elements.openSubmit.addEventListener("click", () => {
    if (typeof elements.submissionDialog.showModal === "function") {
      elements.submissionDialog.showModal();
    } else {
      elements.submissionDialog.setAttribute("open", "");
    }
  });

  elements.submissionDialog.addEventListener("click", (event) => {
    if (event.target === elements.submissionDialog && typeof elements.submissionDialog.close === "function") {
      elements.submissionDialog.close();
    }
  });

  elements.submissionForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const officialUrl = safeHttpUrl(document.getElementById("submit-url").value.trim());
    if (!officialUrl) {
      elements.submissionFeedback.textContent = "Enter a valid official URL beginning with https://";
      return;
    }
    const eventName = document.getElementById("submit-event-name").value.trim();
    const issueUrl = `${REPOSITORY_URL}/issues/new?title=${encodeURIComponent(`Show submission: ${eventName}`)}&body=${encodeURIComponent(submissionBody())}`;
    elements.submissionFeedback.textContent = "Opening the prepared submission...";
    window.open(issueUrl, "_blank", "noopener");
  });
}

async function loadEvents() {
  try {
    const response = await fetch(`events.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Event request failed: ${response.status}`);
    }
    const payload = await response.json();
    if (!Array.isArray(payload)) {
      throw new Error("events.json must contain a JSON array");
    }
    state.events = payload
      .filter((event) => event && typeof event === "object")
      .sort((a, b) => {
        const left = `${a.startDate || "9999-12-31"} ${a.startTime || "23:59"}`;
        const right = `${b.startDate || "9999-12-31"} ${b.startTime || "23:59"}`;
        return left.localeCompare(right);
      });
    configureFilters();
    updateQuickFilterState();
    render();
  } catch (error) {
    elements.resultsCount.textContent = "Unable to load";
    elements.events.replaceChildren(createElement(
      "div",
      "empty-state",
      "The show list could not be loaded. Refresh the page or check the latest GitHub Actions run."
    ));
    console.error(error);
  }
}

configureSubmissionDialog();
Promise.all([loadStatus(), loadEvents()]);
