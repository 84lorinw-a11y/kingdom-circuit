/* Navigation enhancements only. All state/event links exist in the delivered HTML. */
(() => {
  'use strict';
  const picker = document.querySelector('[data-state-picker]');
  if (picker) {
    const select = picker.querySelector('select');
    const button = picker.querySelector('[data-open-state]');
    picker.hidden = false;
    select.addEventListener('change', () => { button.disabled = !select.value; });
    button.addEventListener('click', () => {
      const destination = select.selectedOptions[0]?.value;
      if (destination && destination.startsWith('/shows/')) {
        window.location.assign(destination);
      }
    });
  }
  const tools = document.querySelector('[data-calendar-tools]');
  const grid = document.querySelector('.event-grid');
  if (!tools || !grid) return;
  tools.hidden = false;
  const filter = document.querySelector('[data-state-filter]');
  const link = tools.querySelector('[data-selected-state]');
  const destinations = JSON.parse(document.querySelector('#kc-state-destinations')?.textContent || '{}');
  const sync = () => {
    const state = destinations[filter?.value];
    link.hidden = !state;
    if (state) {
      link.href = state.href;
      link.textContent = `View all ${state.name} shows →`;
    } else {
      link.removeAttribute('href');
      link.textContent = '';
    }
  };
  filter?.addEventListener('change', sync);
  document.querySelector('[data-reset-filters]')?.addEventListener('click', () => queueMicrotask(sync));
  // Existing app may populate its static calendar after async data initialization.
  document.addEventListener('DOMContentLoaded', sync);
  if (filter) new MutationObserver(sync).observe(filter, {childList: true});
  sync();
})();
