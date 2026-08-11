"use strict";

const menuToggle = document.querySelector(".menu-toggle");
const menuDrawer = document.querySelector(".menu-drawer");
const menuClose = document.querySelector(".menu-close");
const menuBackdrop = document.querySelector(".menu-backdrop");

function setMenuOpen(open) {
  if (!menuToggle || !menuDrawer || !menuBackdrop) return;
  menuToggle.setAttribute("aria-expanded", String(open));
  menuDrawer.setAttribute("aria-hidden", String(!open));
  menuDrawer.classList.toggle("open", open);
  menuBackdrop.hidden = !open;
  document.body.classList.toggle("menu-open", open);
  if (open) menuClose?.focus();
}

menuToggle?.addEventListener("click", () => {
  setMenuOpen(menuToggle.getAttribute("aria-expanded") !== "true");
});
menuClose?.addEventListener("click", () => setMenuOpen(false));
menuBackdrop?.addEventListener("click", () => setMenuOpen(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMenuOpen(false);
});
menuDrawer?.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => setMenuOpen(false));
});

function parseLocalDate(value) {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day, 12, 0, 0, 0);
}

function startOfDay(value) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function dateMatchesMode(startDate, endDate, mode) {
  if (mode === "all" || !mode) return true;
  const today = startOfDay(new Date());
  const start = parseLocalDate(startDate);
  const end = parseLocalDate(endDate) || start;
  if (!start || !end) return false;

  if (mode === "next30") {
    const last = new Date(today);
    last.setDate(last.getDate() + 30);
    return end >= today && start <= last;
  }

  if (mode === "month") {
    return start.getFullYear() === today.getFullYear() && start.getMonth() === today.getMonth();
  }

  if (mode === "weekend") {
    const day = today.getDay();
    const daysUntilFriday = (5 - day + 7) % 7;
    const friday = new Date(today);
    friday.setDate(friday.getDate() + daysUntilFriday);
    const sunday = new Date(friday);
    sunday.setDate(sunday.getDate() + 2);
    return end >= friday && start <= sunday;
  }

  return true;
}

function setupEventFilters() {
  const grid = document.querySelector("[data-event-grid]");
  const form = document.querySelector("[data-event-filters]");
  if (!grid || !form) return;

  const cards = [...grid.querySelectorAll("[data-event-card]")];
  const search = form.querySelector("[data-search-filter]");
  const artist = form.querySelector("[data-artist-filter]");
  const state = form.querySelector("[data-state-filter]");
  const type = form.querySelector("[data-type-filter]");
  const reset = form.querySelector("[data-reset-filters]");
  const count = document.querySelector("[data-results-count]");
  const empty = document.querySelector("[data-filtered-empty]");
  const chips = [...document.querySelectorAll(".filter-chip[data-date-mode], .filter-chip[data-type-mode]")];
  let dateMode = "all";

  const url = new URL(window.location.href);
  const queryArtist = url.searchParams.get("artist");
  const queryState = url.searchParams.get("state");
  const queryType = url.searchParams.get("type");
  if (queryArtist && artist) artist.value = queryArtist.toLocaleLowerCase();
  if (queryState && state) state.value = queryState.toUpperCase();
  if (queryType && type) type.value = queryType.toLocaleLowerCase();

  function apply() {
    const needle = (search?.value || "").trim().toLocaleLowerCase();
    const artistValue = artist?.value || "";
    const stateValue = state?.value || "";
    const typeValue = type?.value || "";
    let visible = 0;

    cards.forEach((card) => {
      const artists = (card.dataset.artists || "").split("|").filter(Boolean);
      const matches =
        (!needle || (card.dataset.search || "").includes(needle)) &&
        (!artistValue || artists.includes(artistValue)) &&
        (!stateValue || card.dataset.state === stateValue) &&
        (!typeValue || card.dataset.type === typeValue) &&
        dateMatchesMode(card.dataset.date, card.dataset.endDate, dateMode);
      card.hidden = !matches;
      if (matches) visible += 1;
    });

    if (count) count.textContent = `${visible} show${visible === 1 ? "" : "s"}`;
    if (empty) empty.hidden = visible !== 0;
  }

  [search, artist, state, type].forEach((control) => {
    control?.addEventListener(control === search ? "input" : "change", apply);
  });

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      if (chip.dataset.typeMode) {
        if (type) type.value = chip.dataset.typeMode;
        dateMode = "all";
      } else {
        dateMode = chip.dataset.dateMode || "all";
        if (type && chip.dataset.dateMode) type.value = "";
      }
      chips.forEach((item) => item.classList.remove("active"));
      chip.classList.add("active");
      apply();
    });
  });

  reset?.addEventListener("click", () => {
    form.reset();
    dateMode = "all";
    chips.forEach((chip) => chip.classList.toggle("active", chip.dataset.dateMode === "all"));
    apply();
  });

  apply();
}

function setupArtistDirectory() {
  const grid = document.querySelector("[data-artist-grid]");
  if (!grid) return;
  const cards = [...grid.querySelectorAll("[data-artist-card]")];
  const search = document.querySelector("[data-artist-search]");
  const showFilter = document.querySelector("[data-has-shows-filter]");
  const count = document.querySelector("[data-artist-count]");
  const empty = document.querySelector("[data-artist-empty]");

  function apply() {
    const needle = (search?.value || "").trim().toLocaleLowerCase();
    const requireShows = Boolean(showFilter?.checked);
    let visible = 0;
    cards.forEach((card) => {
      const matches = (!needle || (card.dataset.search || "").includes(needle)) &&
        (!requireShows || card.dataset.hasShows === "true");
      card.hidden = !matches;
      if (matches) visible += 1;
    });
    if (count) count.textContent = `${visible} artist${visible === 1 ? "" : "s"}`;
    if (empty) empty.hidden = visible !== 0;
  }

  search?.addEventListener("input", apply);
  showFilter?.addEventListener("change", apply);
  apply();
}

function setupSubmissionForm() {
  const form = document.querySelector("[data-submission-form]");
  if (!form) return;
  const feedback = form.querySelector("[data-submission-feedback]");
  const submit = form.querySelector("[data-submission-submit]");
  const kind = form.querySelector("[data-submission-kind]");
  const eventName = form.querySelector("[data-event-name]");
  const modeButtons = [...form.querySelectorAll("[data-submission-mode]")];
  const params = new URLSearchParams(window.location.search);

  function setMode(value) {
    if (kind) kind.value = value;
    modeButtons.forEach((button) => button.classList.toggle("active", button.dataset.submissionMode === value));
    if (submit) submit.textContent = value === "Correction" ? "Send Correction" : "Send for Review";
  }

  modeButtons.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.submissionMode || "New show")));

  if ((params.get("type") || "").includes("correction")) setMode("Correction");
  if (params.get("event") && eventName) eventName.value = params.get("event");
  if (params.get("artist") && eventName) eventName.value = `${params.get("artist")} profile correction`;
  if (params.get("url")) {
    const notes = form.querySelector('textarea[name="details"]');
    if (notes) notes.value = `Page to review: ${params.get("url")}\n`;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    if (feedback) feedback.textContent = "Sending submission...";
    if (submit) submit.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error("Submission failed");
      form.reset();
      setMode("New show");
      if (feedback) feedback.textContent = "Submission received. Thank you for helping strengthen the Christian hip-hop community. The Kingdom Circuit will review the information before publishing or updating the event.";
    } catch {
      if (feedback) feedback.textContent = "The submission could not be sent. Please try again in a few minutes.";
    } finally {
      if (submit) submit.disabled = false;
    }
  });
}

setupEventFilters();
setupArtistDirectory();
setupSubmissionForm();
