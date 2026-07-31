"use strict";

const state = {
  events: [],
  filters: {
    search: "",
    artist: "",
    state: "",
    type: ""
  }
};

const elements = {
  events: document.getElementById("events"),
  resultsCount: document.getElementById("results-count"),
  notice: document.getElementById("notice"),
  lastUpdated: document.getElementById("last-updated"),
  statusDot: document.getElementById("status-dot"),
  search: document.getElementById("search-filter"),
  artist: document.getElementById("artist-filter"),
  state: document.getElementById("state-filter"),
  type: document.getElementById("type-filter"),
  reset: document.getElementById("reset-filters")
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

function localDate(dateText) {
  const parts = String(dateText).split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    return null;
  }
  return new Date(parts[0], parts[1] - 1, parts[2]);
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
  const match = String(timeText).match(/^(\d{2}):(\d{2})/);
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

function filteredEvents() {
  return state.events.filter((event) => {
    const searchMatch = !state.filters.search ||
      eventSearchText(event).includes(state.filters.search.toLowerCase());
    const artistMatch = !state.filters.artist ||
      (event.artists || []).includes(state.filters.artist);
    const stateMatch = !state.filters.state || event.state === state.filters.state;
    const typeMatch = !state.filters.type || event.eventType === state.filters.type;
    return searchMatch && artistMatch && stateMatch && typeMatch;
  });
}

function badge(text, className = "") {
  return createElement("span", `badge ${className}`.trim(), text);
}

function renderEvent(event) {
  const card = createElement("article", "event-card");

  const image = createElement("div", "event-image");
  const imageUrl = safeImageUrl(event.image);
  if (imageUrl) {
    image.style.backgroundImage = `linear-gradient(145deg, rgba(8,8,8,.1), rgba(8,8,8,.55)), url("${imageUrl.replaceAll('"', '%22')}")`;
  }
  card.appendChild(image);

  const content = createElement("div", "event-content");
  const main = createElement("div", "event-main");
  const badges = createElement("div", "event-badges");
  badges.appendChild(badge(event.eventType === "festival" ? "Festival" : "Concert", "gold"));
  if (event.status && !["scheduled", "onsale"].includes(event.status)) {
    badges.appendChild(badge(event.status, event.status === "cancelled" ? "cancelled" : ""));
  }
  if (event.stale) {
    badges.appendChild(badge("Rechecking"));
  }
  main.appendChild(badges);

  main.appendChild(createElement("h3", "", event.title || "Untitled event"));
  main.appendChild(createElement(
    "p",
    "artist-line",
    Array.isArray(event.artists) && event.artists.length
      ? event.artists.join(" · ")
      : "Artist lineup not provided"
  ));

  const meta = createElement("div", "event-meta");
  const dateLine = [formatDate(event.startDate), formatTime(event.startTime)]
    .filter(Boolean)
    .join(" · ");
  meta.appendChild(createElement("p", "", dateLine));
  meta.appendChild(createElement(
    "p",
    "",
    [event.venue, [event.city, event.state].filter(Boolean).join(", ")]
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
    sources.slice(0, 4).forEach((source, index) => {
      if (index) {
        sourceBlock.append(" · ");
      }
      const sourceAnchor = createElement("a", "", source.name || "Official source");
      sourceAnchor.href = safeHttpUrl(source.url);
      sourceAnchor.target = "_blank";
      sourceAnchor.rel = "noopener";
      sourceBlock.appendChild(sourceAnchor);
    });
    if (sources.length > 4) {
      sourceBlock.append(` · +${sources.length - 4} more`);
    }
  } else {
    sourceBlock.textContent = event.sourceName ? `Source: ${event.sourceName}` : "Source verified";
  }
  actions.appendChild(sourceBlock);
  content.appendChild(actions);

  card.appendChild(content);
  return card;
}

function render() {
  const events = filteredEvents();
  elements.events.replaceChildren();
  elements.resultsCount.textContent = `${events.length} ${events.length === 1 ? "show" : "shows"}`;

  if (!events.length) {
    const message = state.events.length
      ? "No shows match the current filters."
      : "No verified upcoming shows are available yet. The collector will check again automatically.";
    elements.events.appendChild(createElement("div", "empty-state", message));
    return;
  }

  const fragment = document.createDocumentFragment();
  events.forEach((event) => fragment.appendChild(renderEvent(event)));
  elements.events.appendChild(fragment);
}

function addOptions(select, values) {
  const fragment = document.createDocumentFragment();
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    fragment.appendChild(option);
  });
  select.appendChild(fragment);
}

function configureFilters() {
  const artists = [...new Set(state.events.flatMap((event) => event.artists || []))]
    .sort((a, b) => a.localeCompare(b));
  const states = [...new Set(state.events.map((event) => event.state).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));
  addOptions(elements.artist, artists);
  addOptions(elements.state, states);

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
    render();
  });
  elements.reset.addEventListener("click", () => {
    state.filters = { search: "", artist: "", state: "", type: "" };
    elements.search.value = "";
    elements.artist.value = "";
    elements.state.value = "";
    elements.type.value = "";
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
    elements.lastUpdated.textContent = formatUpdateTime(status.lastSuccessfulUpdate || status.lastAttempt);
    elements.statusDot.classList.add(status.status === "ok" ? "ok" : "warning");
    if (Array.isArray(status.errors) && status.errors.length) {
      elements.notice.hidden = false;
      elements.notice.textContent = status.status === "needs_configuration"
        ? "The free official-site checks are active. Ticketmaster coverage will begin after its API key is connected."
        : "Some sources could not be checked during the latest update. Existing listings remain available while they are rechecked.";
    }
  } catch {
    elements.lastUpdated.textContent = "Update status unavailable";
    elements.statusDot.classList.add("warning");
  }
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

Promise.all([loadStatus(), loadEvents()]);
