/* Progressive enhancement only: all discovery destinations and shows are static HTML. */
(() => {
  'use strict';
  const normalize = value => String(value || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').trim();
  const activeOn = (card, date) => (card.endDate || card.date || '9999-12-31') >= date;
  const previewExpired = (weekEnd, today) => !!weekEnd && weekEnd < today;
  const matches = (card, filters, date) => activeOn(card, date) &&
    (!filters.q || normalize(card.search).includes(normalize(filters.q))) &&
    (!filters.artist || (card.artists || '').split('|').includes(filters.artist)) &&
    (!filters.state || card.state === filters.state) &&
    (!filters.type || card.type === filters.type);
  if (typeof module !== 'undefined' && module.exports) module.exports = {normalize, activeOn, matches, previewExpired};
  if (typeof document === 'undefined') return;

  function init() {
    const parts = new Intl.DateTimeFormat('en-US', {timeZone: 'America/Los_Angeles', year:'numeric', month:'2-digit', day:'2-digit'}).formatToParts(new Date());
    const part = type => parts.find(p => p.type === type).value;
    const today = `${part('year')}-${part('month')}-${part('day')}`;
    document.querySelectorAll('[data-discovery-show]').forEach(card => { card.hidden = !activeOn(card.dataset, today); });
    document.querySelectorAll('.kc-discovery-section').forEach(section => {
      const empty = section.querySelector('[data-discovery-empty]');
      if (empty) empty.hidden = !!section.querySelector('[data-discovery-show]:not([hidden])');
      if (previewExpired(section.dataset.previewWeekEnd, today)) {
        // A delayed daily build must never label last week's cards as this week.
        const shelf = section.querySelector('[data-fan-shelf]');
        if (shelf) shelf.hidden = true;
        const notice = document.createElement('p');
        notice.textContent = 'Weekly previews are refreshing. ';
        const calendar = document.createElement('a');
        calendar.href = '/shows/';
        calendar.textContent = 'Browse all upcoming shows';
        notice.append(calendar);
        section.append(notice);
        if (empty) empty.hidden = true;
      }
    });
    const params = new URLSearchParams(location.search);
    const form = document.querySelector('[data-event-filters]');
    const weekend = document.querySelector('[data-weekend-page]');
    if (!form) return;
    const search = form.querySelector('[data-search-filter]');
    if (!weekend) {
      // The established calendar owns its filtering; only initialize the home search.
      if (search && params.has('q')) {
        search.value = params.get('q').slice(0, 160);
        search.dispatchEvent(new Event('input', {bubbles:true}));
      }
      return;
    }
    const cards = [...document.querySelectorAll('[data-event-card]')];
    const artist = form.querySelector('[data-artist-filter]');
    const state = form.querySelector('[data-state-filter]');
    const type = form.querySelector('[data-type-filter]');
    const count = document.querySelector('[data-results-count]');
    const empty = document.querySelector('[data-filtered-empty]');
    const destinations = JSON.parse(document.querySelector('#kc-state-destinations')?.textContent || '{}');
    const artists = new Map();
    cards.forEach(card => card.querySelectorAll('.artist-line a').forEach(link => artists.set(normalize(link.textContent), link.textContent.trim())));
    const populate = (select, values, label) => {
      if (!select) return;
      while (select.options.length > 1) select.remove(1);
      values.forEach(value => { const option = document.createElement('option'); option.value = value; option.textContent = label(value); select.appendChild(option); });
    };
    populate(artist, [...artists.keys()].sort((a,b) => artists.get(a).localeCompare(artists.get(b))), value => artists.get(value));
    populate(state, [...new Set(cards.map(c => c.dataset.state).filter(Boolean))].sort(), value => destinations[value]?.name || value);
    if (search) search.value = (params.get('q') || '').slice(0,160);
    if (artist) artist.value = normalize(params.get('artist'));
    if (state) state.value = (params.get('state') || '').toUpperCase();
    const apply = () => {
      const filters = {q:search?.value, artist:artist?.value, state:state?.value, type:type?.value};
      let visible = 0;
      cards.forEach(card => { card.hidden = !matches(card.dataset, filters, today); if (!card.hidden) visible++; });
      if (count) count.textContent = `${visible} show${visible === 1 ? '' : 's'}`;
      if (empty) empty.hidden = visible !== 0;
    };
    [search, artist, state, type].forEach(control => control?.addEventListener(control === search ? 'input' : 'change', apply));
    form.querySelector('[data-reset-filters]')?.addEventListener('click', () => {
      form.reset(); apply();
      state?.dispatchEvent(new Event('change', {bubbles:true}));
    });
    form.addEventListener('submit', event => { event.preventDefault(); apply(); });
    const expired = weekend.querySelector('.kc-weekend-expired');
    if (expired) expired.hidden = weekend.dataset.weekendEnd >= today;
    apply();
    state?.dispatchEvent(new Event('change', {bubbles:true}));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
