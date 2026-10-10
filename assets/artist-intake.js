"use strict";
(() => {
  const form = document.querySelector("#artist-intake-form");
  if (!form) return;
  const button = form.querySelector("#ai-submit");
  const status = form.querySelector("#ai-submit-status");
  const success = document.querySelector("#ai-success");
  let sending = false;
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (sending) return;
    if (!form.reportValidity()) return;
    sending = true;
    const data = new FormData(form);
    data.set("page_url", window.location.origin + window.location.pathname);
    const controls = Array.from(form.elements).map(control => [control, control.disabled]);
    controls.forEach(([control]) => { control.disabled = true; });
    form.setAttribute("aria-busy", "true");
    button.textContent = "Submitting…";
    status.classList.remove("is-error");
    status.textContent = "";
    try {
      const response = await fetch(form.action, {
        method: "POST", body: data, headers: {Accept: "application/json"}
      });
      const result = await response.json();
      if (!response.ok || result.ok !== true) {
        status.textContent = response.status === 429
          ? "Please wait a minute and try again. Your details are still here."
          : "We couldn’t submit your profile. Your details are still here—please try again.";
        status.classList.add("is-error");
        return;
      }
      form.hidden = true;
      success.hidden = false;
      success.focus();
    } catch (_) {
      status.classList.add("is-error");
      status.textContent = "We couldn’t confirm your submission. Your details are still here. Check your connection before trying again.";
    } finally {
      sending = false;
      controls.forEach(([control, disabled]) => { control.disabled = disabled; });
      form.removeAttribute("aria-busy");
      button.textContent = "Submit Profile";
    }
  });
})();
