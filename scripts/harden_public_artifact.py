#!/usr/bin/env python3
"""Strip internal catalog feeds from the deploy artifact and install a static UI runtime.

Source JSON/config remains in the repository for normal generation. This script only
changes the final _site artifact that is published to GitHub Pages.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

INTERNAL_FETCH_TARGETS = (
    "events.json",
    "supplemental-events.json",
    "config/artists.json",
    "run-status.json",
)

PUBLIC_RUNTIME = r'''"use strict";
(() => {
  const STATE_NAMES = {AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",CO:"Colorado",CT:"Connecticut",DE:"Delaware",DC:"District of Columbia",FL:"Florida",GA:"Georgia",HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming",PR:"Puerto Rico"};
  const norm = value => String(value || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
  const localDate = value => {
    if (!value) return null;
    const parts = String(value).split("-").map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
    return new Date(parts[0], parts[1] - 1, parts[2]);
  };
  const startOfDay = value => new Date(value.getFullYear(), value.getMonth(), value.getDate());

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

  function fillSelect(select, values, labeler = value => value) {
    if (!select) return;
    const first = select.querySelector("option");
    select.innerHTML = first ? first.outerHTML : "";
    for (const value of values) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = labeler(value);
      select.appendChild(option);
    }
  }

  function dateMatchesMode(card, mode) {
    if (!mode || mode === "all") return true;
    const today = startOfDay(new Date());
    const start = localDate(card.dataset.date);
    const end = localDate(card.dataset.endDate) || start;
    if (!start || !end) return false;
    if (mode === "next30") {
      const last = new Date(today);
      last.setDate(last.getDate() + 30);
      return end >= today && start <= last;
    }
    if (mode === "month") return start.getFullYear() === today.getFullYear() && start.getMonth() === today.getMonth();
    if (mode === "weekend") {
      const friday = new Date(today);
      friday.setDate(friday.getDate() + ((5 - today.getDay() + 7) % 7));
      const sunday = new Date(friday);
      sunday.setDate(sunday.getDate() + 2);
      return end >= friday && start <= sunday;
    }
    return true;
  }

  function bindEventFilters() {
    const form = document.querySelector("[data-event-filters]");
    const grid = document.querySelector("[data-event-grid]");
    if (!form || !grid) return;
    const cards = [...grid.querySelectorAll("[data-event-card]")];
    const search = form.querySelector("[data-search-filter]");
    const artist = form.querySelector("[data-artist-filter]");
    const state = form.querySelector("[data-state-filter]");
    const type = form.querySelector("[data-type-filter]");
    const reset = form.querySelector("[data-reset-filters]");
    const count = document.querySelector("[data-results-count]");
    const empty = document.querySelector("[data-filtered-empty]");
    const chips = [...document.querySelectorAll(".filter-chip[data-date-mode],.filter-chip[data-type-mode]")];

    const artistMap = new Map();
    for (const card of cards) {
      for (const link of card.querySelectorAll(".artist-line a")) {
        const display = String(link.textContent || "").trim();
        if (display) artistMap.set(norm(display), display);
      }
    }
    fillSelect(artist, [...artistMap.keys()].sort((a, b) => artistMap.get(a).localeCompare(artistMap.get(b))), value => artistMap.get(value));
    fillSelect(state, [...new Set(cards.map(card => card.dataset.state).filter(Boolean))].sort(), value => STATE_NAMES[value] || value);

    let dateMode = "all";
    const params = new URLSearchParams(location.search);
    if (params.get("artist") && artist) artist.value = norm(params.get("artist"));
    if (params.get("state") && state) state.value = params.get("state").toUpperCase();

    function apply() {
      const needle = norm(search?.value);
      const artistValue = artist?.value || "";
      const stateValue = state?.value || "";
      const typeValue = type?.value || "";
      let visible = 0;
      for (const card of cards) {
        const names = [...card.querySelectorAll(".artist-line a")].map(link => norm(link.textContent));
        const haystack = norm(card.textContent);
        const match = (!needle || haystack.includes(needle)) &&
          (!artistValue || names.includes(artistValue)) &&
          (!stateValue || card.dataset.state === stateValue) &&
          (!typeValue || card.dataset.type === typeValue) &&
          dateMatchesMode(card, dateMode);
        card.hidden = !match;
        if (match) visible += 1;
      }
      if (count) count.textContent = `${visible} show${visible === 1 ? "" : "s"}`;
      if (empty) empty.hidden = visible !== 0;
    }

    [search, artist, state, type].forEach(control => control?.addEventListener(control === search ? "input" : "change", apply));
    for (const chip of chips) {
      chip.addEventListener("click", () => {
        if (chip.dataset.typeMode) {
          if (type) type.value = chip.dataset.typeMode;
          dateMode = "all";
        } else {
          dateMode = chip.dataset.dateMode || "all";
          if (type) type.value = "";
        }
        chips.forEach(item => item.classList.remove("active"));
        chip.classList.add("active");
        apply();
      });
    }
    reset?.addEventListener("click", () => {
      form.reset();
      dateMode = "all";
      chips.forEach(item => item.classList.toggle("active", item.dataset.dateMode === "all"));
      history.replaceState(null, "", location.pathname);
      apply();
    });
    apply();
  }

  function bindSubmissionForm() {
    const form = document.querySelector("[data-submission-form]");
    if (!form) return;
    const feedback = form.querySelector("[data-submission-feedback]");
    const submit = form.querySelector("[data-submission-submit]");
    const kind = form.querySelector("[data-submission-kind]");
    const eventName = form.querySelector("[data-event-name]");
    const buttons = [...form.querySelectorAll("[data-submission-mode]")];
    const params = new URLSearchParams(location.search);
    const setMode = value => {
      if (kind) kind.value = value;
      buttons.forEach(button => button.classList.toggle("active", button.dataset.submissionMode === value));
      if (submit) submit.textContent = value === "Correction" ? "Send Correction" : "Send for Review";
    };
    buttons.forEach(button => button.addEventListener("click", () => setMode(button.dataset.submissionMode || "New show")));
    if ((params.get("type") || "").includes("correction")) setMode("Correction");
    if (params.get("event") && eventName) eventName.value = params.get("event");
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      if (feedback) feedback.textContent = "Sending submission...";
      if (submit) submit.disabled = true;
      try {
        const response = await fetch(form.action, {method:"POST", body:new FormData(form), headers:{Accept:"application/json"}});
        if (!response.ok) throw new Error();
        form.reset();
        setMode("New show");
        if (feedback) feedback.textContent = "Submission received. The Kingdom Circuit will review the information before publishing or updating the event.";
      } catch (_) {
        if (feedback) feedback.textContent = "The submission could not be sent. Please try again in a few minutes.";
      } finally {
        if (submit) submit.disabled = false;
      }
    });
  }

  function bindGenericFallbacks() {
    const detail = document.querySelector("[data-event-detail]");
    if (detail && !detail.querySelector(".event-detail") && !detail.querySelector("h1")) {
      detail.innerHTML = '<section class="page-hero hero-compact"><h1>Find this event in the current calendar.</h1><p>Kingdom Circuit now publishes permanent event pages instead of loading event data from a public bulk feed.</p><a class="primary-button" href="/shows/">View all shows</a></section>';
    }
    const profile = document.querySelector("[data-artist-profile]");
    if (profile && !profile.querySelector("h1")) {
      profile.innerHTML = '<section class="page-hero hero-compact"><h1>Browse the artist directory.</h1><p>Kingdom Circuit now publishes permanent artist pages instead of loading artist data from a public bulk feed.</p><a class="primary-button" href="/artists/">View artists</a></section>';
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelector(".menu-toggle")?.addEventListener("click", () => setMenuOpen(document.querySelector(".menu-toggle")?.getAttribute("aria-expanded") !== "true"));
    document.querySelector(".menu-close")?.addEventListener("click", () => setMenuOpen(false));
    document.querySelector(".menu-backdrop")?.addEventListener("click", () => setMenuOpen(false));
    document.addEventListener("keydown", event => { if (event.key === "Escape") setMenuOpen(false); });
    bindEventFilters();
    bindSubmissionForm();
    bindGenericFallbacks();
  });
})();
'''


def harden(root: Path) -> dict[str, int]:
    root = root.resolve()
    if not (root / "index.html").is_file():
        raise SystemExit(f"Not a built site artifact: {root}")

    status_path = root / "run-status.json"
    updated_label = ""
    if status_path.is_file():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            stamp = status.get("lastSuccessfulUpdate") or status.get("lastAttempt")
            if stamp:
                dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).astimezone(timezone.utc)
                updated_label = f"{dt.strftime('%b')} {dt.day}, {dt.year}"
        except (ValueError, TypeError, json.JSONDecodeError):
            updated_label = ""

    if updated_label:
        old = '<div id="notice" class="footer-status" data-calendar-status hidden></div>'
        new = f'<div id="notice" class="footer-status" data-calendar-status><span><strong>Calendar updated:</strong> {updated_label}</span></div>'
        for html in root.rglob("*.html"):
            text = html.read_text(encoding="utf-8", errors="ignore")
            if old in text:
                html.write_text(text.replace(old, new), encoding="utf-8")

    removed_json = 0
    for path in list(root.rglob("*.json")):
        path.unlink()
        removed_json += 1

    removed_internal_dirs = 0
    for name in ("config", "workflows", "audit"):
        path = root / name
        if path.exists():
            shutil.rmtree(path)
            removed_internal_dirs += 1

    removed_internal_files = 0
    for pattern in ("*.py", "*.yml", "*.yaml", "*.md", "*.txt"):
        for path in list(root.glob(pattern)):
            if path.name == "robots.txt":
                continue
            path.unlink()
            removed_internal_files += 1
    for name in (".scan-trigger",):
        path = root / name
        if path.exists():
            path.unlink()
            removed_internal_files += 1

    (root / "app.js").write_text(PUBLIC_RUNTIME, encoding="utf-8")

    legacy_artist_filter = root / "assets" / "artist-filter-fix.js"
    if legacy_artist_filter.exists():
        legacy_artist_filter.write_text('"use strict";console.info("Static artist directory filtering enabled");\n', encoding="utf-8")

    for required in (
        "index.html",
        "app.js",
        "styles.css",
        "robots.txt",
        "sitemap.xml",
        "CNAME",
        "shows/index.html",
        "artists/index.html",
        "festivals/index.html",
        "new-shows/index.html",
        "submit/index.html",
        "seo-enhancements.js",
    ):
        path = root / required
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"Public artifact hardening removed a required file: {required}")

    leaked_json = list(root.rglob("*.json"))
    if leaked_json:
        raise SystemExit(f"JSON remained in public artifact: {[str(p.relative_to(root)) for p in leaked_json[:10]]}")
    if (root / "config").exists():
        raise SystemExit("Public config directory remained in artifact")

    for js in root.rglob("*.js"):
        text = js.read_text(encoding="utf-8", errors="ignore")
        if js.name == "app.js" and "form.action" in text:
            # User-initiated Formspree submission is intentionally preserved.
            pass
        for target in INTERNAL_FETCH_TARGETS:
            if target in text:
                raise SystemExit(f"Internal bulk-data endpoint still referenced by {js.relative_to(root)}: {target}")

    return {
        "removedJsonFiles": removed_json,
        "removedInternalDirs": removed_internal_dirs,
        "removedInternalFiles": removed_internal_files,
        "publicHtmlPages": sum(1 for _ in root.rglob("*.html")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", nargs="?", default="_site")
    args = parser.parse_args()
    result = harden(Path(args.site))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
