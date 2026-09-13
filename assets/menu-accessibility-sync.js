"use strict";

(() => {
  function start() {
    const opener = document.querySelector(".menu-toggle");
    const drawer = document.querySelector(".menu-drawer");
    const closer = drawer?.querySelector(".menu-close");
    const backdrop = document.querySelector(".menu-backdrop");
    if (!opener || !drawer || !closer) return;

    const links = [...drawer.querySelectorAll(".menu-links a")];
    let wasOpen = drawer.classList.contains("open");

    function sync({ returnFocus = false } = {}) {
      const open = drawer.classList.contains("open");
      drawer.inert = !open;
      drawer.setAttribute("aria-hidden", open ? "false" : "true");
      opener.setAttribute("aria-expanded", open ? "true" : "false");
      [...links, closer].forEach((element) => {
        if (open) element.removeAttribute("tabindex");
        else element.setAttribute("tabindex", "-1");
      });
      if (backdrop) backdrop.hidden = !open;

      if (open && !wasOpen) {
        requestAnimationFrame(() => closer.focus());
      } else if (!open && wasOpen && returnFocus) {
        requestAnimationFrame(() => opener.focus());
      }
      wasOpen = open;
    }

    // Keep accessibility state aligned even when the pre-existing navigation
    // runtime opens/closes the drawer before this enhancement observes the event.
    new MutationObserver(() => sync({ returnFocus: true })).observe(drawer, {
      attributes: true,
      attributeFilter: ["class"],
    });

    // Capture Escape before older document-level handlers so the closed drawer
    // is removed from the tab order and focus reliably returns to the opener.
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || !drawer.classList.contains("open")) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      drawer.classList.remove("open");
      document.body.classList.remove("menu-open");
      sync({ returnFocus: true });
    }, true);

    sync();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
