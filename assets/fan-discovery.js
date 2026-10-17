/* Production, dependency-free progressive enhancement. Static links/cards remain crawlable. */
(() => {
  'use strict';
  const normalize = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[’']/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  const searchMatch = (haystack, query) => {
    const h = normalize(haystack), q = normalize(query);
    return !q || h.includes(q) || h.replace(/ /g, '').includes(q.replace(/ /g, ''));
  };
  const addDays = (day, amount) => {
    const d = new Date(day + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + amount);
    return d.toISOString().slice(0, 10);
  };
  const weekEnd = day => addDays(day, (7 - new Date(day + 'T12:00:00Z').getUTCDay()) % 7);
  const modes = {all:'All dates', week:'This week', weekend:'This weekend', upcoming:'Next week', next30:'Next 30 days', month:'This month'};
  const dateMatch = (start, end, mode, today) => {
    if (!start || (end || start) < today) return false;
    const last = end || start;
    if (mode === 'week') return start <= weekEnd(today);
    if (mode === 'upcoming') return start > weekEnd(today) && start <= addDays(weekEnd(today), 7);
    if (mode === 'weekend') return start <= weekEnd(today) && last >= addDays(weekEnd(today), -2);
    if (mode === 'next30') return start <= addDays(today, 29);
    if (mode === 'month') return start <= today.slice(0,7) + '-31';
    return true;
  };
  const matches = (card, filters, today) => searchMatch(card.search, filters.q) &&
    (!filters.artist || (card.artists || '').split('|').some(a => normalize(a) === normalize(filters.artist))) &&
    (!filters.state || card.state === filters.state) && (!filters.type || card.type === filters.type) &&
    dateMatch(card.date, card.endDate, filters.dates, today);
  const artistMatches = (artists, query) => !normalize(query) ? [] : artists.filter(a => searchMatch(a.name, query)).sort((a,b) =>
    Number(normalize(b.name) === normalize(query)) - Number(normalize(a.name) === normalize(query)) || a.name.localeCompare(b.name));
  const calendarScope = pathname => pathname.replace(/index\.html$/, '').endsWith('/shows/this-weekend/') ? 'weekend' :
    pathname.replace(/index\.html$/, '').endsWith('/shows/this-month/') ? 'month' : 'all';
  function completeCalendarURL(pathname, filters) {
    const scope = calendarScope(pathname);
    if (scope === 'all' || filters.dates === scope) return null;
    const params = new URLSearchParams();
    ['q','state','artist','type','dates'].forEach(key => {
      if (filters[key] && !(key === 'dates' && filters[key] === 'all')) params.set(key, filters[key]);
    });
    return '/shows/' + (params.size ? '?' + params : '');
  }
  function syncStateShortcut(link, destinations, value) {
    if (!link) return;
    const state = destinations[value];
    const valid = state?.href?.startsWith('/shows/');
    link.hidden = !valid;
    if (valid) { link.href = state.href; link.textContent = `View all ${state.name} shows →`; }
    else { link.removeAttribute('href'); link.textContent = ''; }
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {normalize, searchMatch, addDays, weekEnd, dateMatch, matches, artistMatches, profileLink, calendarScope, completeCalendarURL, syncStateShortcut};
  if (typeof document === 'undefined') return;

  const todayString = () => {
    const parts = new Intl.DateTimeFormat('en-US', {timeZone:'America/Los_Angeles',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    return ['year','month','day'].map(k => parts.find(p => p.type === k).value).join('-');
  };
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; };
  function profileLink(artist) {
    if (!artist.href?.startsWith('/artists/')) return null;
    const link = el('a','kc-profile-link'); link.href = artist.href;
    const avatar = el('span','kc-profile-avatar'); avatar.setAttribute('aria-hidden','true');
    const words = String(artist.name || '').trim().split(/\s+/);
    const initials = words.length > 1 ? words[0][0] + words.at(-1)[0] : Array.from(words[0]).slice(0,2).join('');
    avatar.append(el('span','kc-profile-initials',initials.toUpperCase()));
    if (artist.portrait?.src?.startsWith('/assets/')) {
      const photo = el('img'); photo.alt = ''; photo.width = 72; photo.height = 72;
      photo.loading = 'lazy'; photo.decoding = 'async';
      photo.style.objectPosition = artist.portrait.position || 'center';
      photo.addEventListener('error', () => photo.remove(), {once:true});
      photo.src = artist.portrait.src; avatar.append(photo);
    }
    const copy = el('span','kc-profile-copy');
    copy.append(el('strong','',artist.name), el('small','',artist.count ? `${artist.count} upcoming show${artist.count === 1 ? '' : 's'} · Official socials & show history` : 'Official socials & show history · No upcoming dates listed'));
    link.append(avatar, copy, el('span','kc-profile-action','View artist profile'));
    return link;
  }
  function artistSuggestions(form, query) {
    const artists = JSON.parse(document.querySelector('#kc-fan-artists')?.textContent || '[]');
    const box = el('section','kc-fan-artist-results kc-fan-suggestions'); box.hidden = true;
    box.id = 'kc-home-artist-results'; box.setAttribute('aria-label','Artist profile suggestions');
    const status = el('p','kc-discovery-sr-only'); status.setAttribute('role','status');
    const links = el('div');
    box.append(el('h2','','Artist profiles'), links); form.after(box); form.append(status);
    query.setAttribute('aria-controls',box.id);
    query.addEventListener('input', () => {
      const found = normalize(query.value).length >= 2 ? artistMatches(artists,query.value).slice(0,6) : [];
      links.replaceChildren(); found.forEach(a => { const link=profileLink(a); if(link) links.append(link); });
      box.hidden = !links.childElementCount;
      status.textContent = found.length ? `${found.length} artist profile suggestions available below. Search still shows matching events.` : '';
    });
    query.addEventListener('keydown', event => {
      if (event.key === 'Escape') box.hidden = true;
      if (event.key === 'ArrowDown' && !box.hidden) { event.preventDefault(); links.querySelector('a')?.focus(); }
    });
    box.addEventListener('keydown', event => {
      if (event.key === 'Escape') { box.hidden = true; query.focus(); }
    });
  }
  function shelves() {
    document.querySelectorAll('[data-fan-shelf]').forEach(wrap => {
      const shelf = wrap.querySelector('.kc-fan-shelf'), controls = wrap.querySelector('.kc-fan-shelf-controls');
      const prev = wrap.querySelector('[data-shelf-prev]'), next = wrap.querySelector('[data-shelf-next]');
      const update = () => { controls.hidden = shelf.scrollWidth <= shelf.clientWidth + 3; prev.disabled = shelf.scrollLeft <= 3; next.disabled = shelf.scrollLeft + shelf.clientWidth >= shelf.scrollWidth - 3; };
      const move = direction => { const first = [...shelf.children].find(n => !n.hidden); shelf.scrollBy({left:direction * ((first?.getBoundingClientRect().width || shelf.clientWidth) + 12), behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'}); };
      prev.addEventListener('click', () => move(-1)); next.addEventListener('click', () => move(1));
      shelf.addEventListener('keydown', event => { if (event.target !== shelf) return; if (['ArrowLeft','ArrowRight'].includes(event.key)) { event.preventDefault(); move(event.key === 'ArrowLeft' ? -1 : 1); } });
      shelf.addEventListener('scroll', update, {passive:true});
      new ResizeObserver(update).observe(shelf); update();
    });
  }
  function homeFinder() {
    const form = document.querySelector('[data-fan-finder]'); if (!form) return;
    artistSuggestions(form, form.elements.q);
    form.addEventListener('submit', event => {
      const state = form.elements.state;
      // States with no current inventory still have their permanent useful page.
      if (state.value && !form.elements.q.value && form.elements.dates.value === 'all') {
        const href = state.selectedOptions[0].dataset.stateHref;
        if (href?.startsWith('/shows/')) { event.preventDefault(); location.assign(href); }
      }
    });
    form.elements.state.addEventListener('change', () => form.requestSubmit());
    form.elements.dates.addEventListener('change', () => form.requestSubmit());
  }
  function calendar() {
    const form = document.querySelector('[data-event-filters]');
    const grid = document.querySelector('[data-event-grid], .event-grid');
    if (!form || !grid) return;
    const query = form.querySelector('[data-search-filter]'), state = form.querySelector('[data-state-filter]');
    const artist = form.querySelector('[data-artist-filter]'), type = form.querySelector('[data-type-filter]');
    const reset = form.querySelector('[data-reset-filters]');
    if (!query || !state || !artist || !type) return;
    const destinations = JSON.parse(document.querySelector('#kc-state-destinations')?.textContent || '{}');
    const neighbors = JSON.parse(document.querySelector('#kc-fan-neighbors')?.textContent || '{}');
    const artistNames = new Map(), stateNames = new Set();
    grid.querySelectorAll('[data-event-card]').forEach(card => {
      if (card.dataset.state) stateNames.add(card.dataset.state);
      card.querySelectorAll('.artist-line a').forEach(a => artistNames.set(normalize(a.textContent),a.textContent.trim()));
    });
    const populate = (control, entries) => {
      while (control.options.length > 1) control.remove(1);
      entries.forEach(([value,name]) => { const option = el('option','',name); option.value = value; control.append(option); });
    };
    populate(artist,[...artistNames].sort((a,b) => a[1].localeCompare(b[1])));
    const allStates = new Map([...stateNames].map(s => [s,destinations[s]?.name || s]));
    Object.entries(neighbors).forEach(([key,s]) => { if(key.length === 2 || !Object.values(destinations).some(d => d.name === s.name)) allStates.set(key,s.name); });
    populate(state,[...allStates].sort((a,b) => a[1].localeCompare(b[1])));
    form.classList.add('kc-fan-filters');
    const extra = el('details'), summary = el('summary', '', 'More filters');
    const fields = el('div','kc-fan-extra-fields');
    extra.append(summary, fields); fields.append(artist.closest('label'), type.closest('label'));
    const datesLabel = el('label','field'), datesText = el('span','','Dates'), dates = el('select');
    dates.setAttribute('aria-label','Dates');
    Object.entries(modes).forEach(([value,label]) => { const option = el('option','',label); option.value = value; dates.append(option); });
    datesLabel.append(datesText, dates);
    form.append(state.closest('label'), datesLabel, extra); if (reset) fields.append(reset);
    const quick = document.querySelector('.quick-filters'); if (quick) quick.hidden = true;
    const chips = el('div','kc-fan-active'); chips.setAttribute('aria-label','Selected filters'); form.after(chips);
    const artistBox = el('section','kc-fan-artist-results'); artistBox.hidden = true;
    const artistHeading = el('h2','','Matching artists'), artistLinks = el('div');
    artistBox.append(artistHeading, artistLinks, el('p','','Artist profiles are shown regardless of your location or date filters.'));
    chips.after(artistBox);
    const alternatives = el('section','kc-neighbor-states'); alternatives.hidden = true;
    alternatives.setAttribute('aria-label','Alternative states with upcoming shows');
    artistBox.after(alternatives);
    const artists = JSON.parse(document.querySelector('#kc-fan-artists')?.textContent || '[]');
    const setValue = (control, value) => {
      if (control.tagName === 'SELECT' && value && ![...control.options].some(o => o.value === value)) {
        const option = el('option','',value); option.value = value; control.append(option);
      }
      control.value = value;
    };
    const readURL = () => {
      const p = new URLSearchParams(location.search);
      query.value = (p.get('q') || '').slice(0,160);
      setValue(state, p.get('state') || ''); setValue(artist, p.get('artist') || ''); setValue(type, p.get('type') || '');
      dates.value = modes[p.get('dates')] ? p.get('dates') : calendarScope(location.pathname);
      extra.open = !!(artist.value || type.value);
    };
    readURL();
    const count = document.querySelector('[data-results-count]'), empty = document.querySelector('[data-filtered-empty]');
    function apply(writeURL = true) {
      const filters = {q:query.value, state:state.value, artist:artist.value, type:type.value, dates:dates.value};
      // Date landing pages contain only their own window. Broader choices must
      // use the complete calendar, retaining every other selected filter.
      const destination = completeCalendarURL(location.pathname, filters);
      if (destination) { location.replace(destination); return; }
      // This controller owns input, chips, reset and history; older target-phase
      // change listeners do not run after its capture-phase filtering handler.
      syncStateShortcut(document.querySelector('[data-selected-state]'), destinations, state.value);
      let visible = 0; const today = todayString();
      grid.querySelectorAll('[data-event-card]').forEach(card => { card.hidden = !matches(card.dataset,filters,today); if (!card.hidden) visible++; });
      if (count) count.textContent = `${visible} show${visible === 1 ? '' : 's'}`;
      if (empty) empty.hidden = visible !== 0;
      artistLinks.replaceChildren();
      const found = artistMatches(artists, query.value); artistBox.hidden = found.length === 0;
      found.slice(0,8).forEach(a => {
        const link = profileLink(a); if(link) artistLinks.append(link);
      });
      if (found.length > 8) { const all = el('a','','Browse all artists →'); all.href = '/artists/'; artistLinks.append(all); }
      alternatives.replaceChildren();
      const nearby = neighbors[state.value]?.neighbors || [];
      alternatives.hidden = visible !== 0 || !state.value || !nearby.length;
      if (!alternatives.hidden) {
        alternatives.append(el('h2','','Explore shows in neighboring states'),el('p','','These links show all upcoming dates and artists in each state, not your current filters. Check the city and travel distance before making plans.'));
        const nav = el('nav','kc-state-links'); nav.setAttribute('aria-label','Neighboring states with shows');
        nearby.forEach(s => { if(!s.href.startsWith('/shows/') || !s.count) return; const a=el('a'); a.href=s.href; a.append(el('span','',s.name),el('small','',`${s.count} upcoming`)); nav.append(a); });
        alternatives.append(nav);
      }
      chips.replaceChildren();
      [[query,'Search'],[state,'State'],[dates,'Dates'],[artist,'Artist'],[type,'Type']].forEach(([control,label]) => {
        if (!control.value || (control === dates && control.value === 'all')) return;
        const value = control.selectedOptions?.[0]?.textContent || control.value;
        const button = el('button','',`${value} ×`); button.type = 'button'; button.setAttribute('aria-label',`Remove ${label.toLowerCase()} filter: ${value}`);
        button.addEventListener('click', () => { control.value = control === dates ? 'all' : ''; apply(); control.focus(); }); chips.append(button);
      });
      if (writeURL) {
        const url = new URL(location.href);
        ['q','state','artist','type','dates'].forEach(k => { if (filters[k] && !(k === 'dates' && filters[k] === 'all')) url.searchParams.set(k,filters[k]); else url.searchParams.delete(k); });
        history.replaceState(history.state,'',url);
      }
    }
    // One filter owner prevents older app listeners from undoing date/search matches.
    ['input','change'].forEach(name => form.addEventListener(name, event => {
      if (![query,state,artist,type,dates].includes(event.target)) return;
      event.stopImmediatePropagation(); apply();
    }, true));
    form.addEventListener('submit', event => { event.preventDefault(); event.stopImmediatePropagation(); apply(); }, true);
    reset?.addEventListener('click', event => { event.preventDefault(); event.stopImmediatePropagation(); query.value = ''; [state,artist,type].forEach(c => c.value = ''); dates.value = 'all'; extra.open = false; apply(); }, true);
    window.addEventListener('popstate', () => { readURL(); apply(false); });
    // The production calendar can finish rendering after initial HTML hydration.
    new MutationObserver(() => apply(false)).observe(grid,{childList:true});
    apply(false);
  }
  function init() { shelves(); homeFinder(); calendar(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => requestAnimationFrame(init), {once:true});
  else requestAnimationFrame(init);
})();
