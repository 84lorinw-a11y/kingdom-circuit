"use strict";

(() => {
  function relaxUrlField(field) {
    if (!(field instanceof HTMLInputElement)) return;
    if (field.dataset.kcFlexibleUrl === "true") return;
    if (field.type !== "url") return;

    field.dataset.kcFlexibleUrl = "true";
    field.type = "text";
    field.inputMode = "url";
    field.autocapitalize = "none";
    field.autocomplete = "url";
    field.spellcheck = false;
  }

  function normalizeUrlValue(field) {
    if (!(field instanceof HTMLInputElement)) return;
    if (field.dataset.kcFlexibleUrl !== "true") return;

    const value = String(field.value || "").trim();
    if (!value) return;

    if (value.startsWith("//")) {
      field.value = `https:${value}`;
      return;
    }

    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(value)) return;

    // Make common bare website/social links clickable after submission while
    // still allowing any other non-empty text through for manual review.
    if (/^(?:www\.)?[^\s/@]+\.[^\s]+/i.test(value)) {
      field.value = `https://${value}`;
    }
  }

  function scan(root = document) {
    root.querySelectorAll?.('input[type="url"]').forEach(relaxUrlField);
    if (root.matches?.('input[type="url"]')) relaxUrlField(root);
  }

  scan();

  const observer = new MutationObserver(records => {
    records.forEach(record => {
      record.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) scan(node);
      });
    });
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener("submit", event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    form.querySelectorAll('input[data-kc-flexible-url="true"]').forEach(normalizeUrlValue);
  }, true);
})();
