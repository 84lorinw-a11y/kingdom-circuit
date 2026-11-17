(() => {
  'use strict';
  const script = document.querySelector('script[src*="/assets/location-navigation.js"]');
  const root = script ? new URL('../', script.src) : null;
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().trim();
  document.querySelectorAll('[data-location-directory]').forEach(directory => {
    const filter = directory.querySelector('[data-location-filters]');
    const input = directory.querySelector('[data-location-search]');
    const region = directory.querySelector('[data-location-region]');
    const selectedCity = directory.querySelector('[data-location-city]');
    const country = directory.querySelector('[data-location-country]');
    const clear = directory.querySelector('[data-location-clear]');
    const status = directory.querySelector('[data-location-count]');
    const empty = directory.querySelector('[data-location-empty]');
    const groups = Array.from(directory.querySelectorAll('[data-location-group]'));
    const city = directory.dataset.locationKind === 'cities';
    const featured = directory.querySelector('.kc-featured-locations');
    const heading = directory.querySelector('#all-locations-heading');
    const originalHeading = heading.textContent;
    const regionOptions = Array.from(region.options).map(option => option.cloneNode(true));
    const regionCodes = new Set(regionOptions.flatMap(option => normalize(option.dataset.codes || '').split(/\s+/).filter(Boolean)));
    const cityOptions = Array.from(selectedCity.options).map(option => option.cloneNode(true));
    const rebuild = (select, options, include) => {
      const value = select.value;
      select.replaceChildren(...options.filter(option => !option.value || include(option)).map(option => option.cloneNode(true)));
      select.value = Array.from(select.options).some(option => option.value === value) ? value : '';
    };
    const syncOptions = () => {
      rebuild(region, regionOptions, option => !country.value || option.dataset.country === country.value);
      rebuild(selectedCity, cityOptions, option => (!country.value || option.dataset.country === country.value) && (!region.value || option.dataset.region === region.value));
    };
    const rememberFilters = () => {
      try {
        history.replaceState({...history.state, kcLocationFilters: {
          path: location.pathname, query: input.value, country: country.value,
          region: region.value, city: selectedCity.value
        }}, '');
      } catch { /* Browsing still works if history storage is unavailable. */ }
    };
    const restoreFilters = () => {
      const saved = history.state?.kcLocationFilters;
      if (!saved || saved.path !== location.pathname) return;
      input.value = saved.query || '';
      country.value = saved.country || '';
      syncOptions();
      region.value = saved.region || '';
      syncOptions();
      selectedCity.value = saved.city || '';
    };
    const update = () => {
      const term = normalize(input.value); let count = 0;
      const terms = term.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
      const cityRegion = selectedCity.selectedOptions[0]?.dataset.region;
      const filtered = !!(term || region.value || selectedCity.value || country.value);
      groups.forEach(group => {
        let visible = 0;
        group.querySelectorAll('[data-location-entry]').forEach(entry => {
          const entryRegion = entry.dataset.region || group.dataset.region;
          const searchable = normalize(entry.dataset.search + ' ' + (group.dataset.regionName || ''));
          const words = searchable.split(/[^\p{L}\p{N}]+/u);
          const match = (!region.value || region.value === entryRegion) &&
            (!country.value || country.value === entry.dataset.country) &&
            (!selectedCity.value || (city ? selectedCity.value === entry.dataset.city : cityRegion === entryRegion)) &&
            terms.every(word => regionCodes.has(word) ? words.includes(word) : searchable.includes(word));
          entry.hidden = !match; if (match) visible++;
        });
        group.hidden = visible === 0; count += visible;
      });
      status.textContent = `${count} ${city ? (count === 1 ? 'city' : 'cities') : (count === 1 ? 'state or province' : 'states and provinces')} with upcoming shows`;
      empty.hidden = count > 0; clear.hidden = !filtered;
      if (featured) featured.hidden = filtered;
      heading.textContent = filtered ? (city ? 'Matching cities' : 'Matching states and provinces') : originalHeading;
      rememberFilters();
    };
    restoreFilters();
    update();
    window.addEventListener('pageshow', () => { restoreFilters(); update(); });
    filter.hidden = false;
    filter.addEventListener('submit', event => {
      event.preventDefault();
      update();
      heading.focus();
    });
    input.addEventListener('input', update);
    region.addEventListener('change', () => { syncOptions(); update(); });
    country.addEventListener('change', () => { syncOptions(); update(); });
    selectedCity.addEventListener('change', () => {
      const option = selectedCity.selectedOptions[0];
      if (option?.value) { country.value = option.dataset.country; rebuild(region, regionOptions, item => item.dataset.country === country.value); region.value = option.dataset.region; }
      syncOptions(); update();
    });
    clear.addEventListener('click', () => { input.value = ''; country.value = ''; region.value = ''; selectedCity.value = ''; syncOptions(); update(); input.focus(); });
  });
  document.querySelectorAll('.kc-featured-locations').forEach(section => {
    const rail = section.querySelector('[data-featured-rail]');
    const controls = section.querySelector('[data-featured-controls]');
    const previous = section.querySelector('[data-featured-prev]');
    const next = section.querySelector('[data-featured-next]');
    const refresh = () => {
      const max = rail.scrollWidth - rail.clientWidth;
      controls.hidden = max < 2;
      previous.disabled = rail.scrollLeft < 2;
      next.disabled = rail.scrollLeft >= max - 2;
    };
    const move = direction => {
      const card = rail.querySelector('[data-featured-location]');
      const distance = card.getBoundingClientRect().width + parseFloat(getComputedStyle(rail).columnGap);
      rail.scrollBy({left:direction * distance,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    };
    previous.addEventListener('click', () => move(-1));
    next.addEventListener('click', () => move(1));
    rail.addEventListener('scroll', refresh, {passive:true});
    new ResizeObserver(refresh).observe(rail);
    refresh();
  });
  const menus = document.querySelectorAll('.kc-location-menu');
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    menus.forEach(menu => { if (menu.open) { menu.open = false; menu.querySelector('summary').focus(); } });
  });
  document.addEventListener('click', event => menus.forEach(menu => { if (!menu.contains(event.target)) menu.open = false; }));
  // Progressive enhancement for cards generated by the existing show filters.
  // Initial HTML already contains the same crawlable location anchors.
  if (root) fetch(new URL('assets/location-navigation-data.json', root))
    .then(response => { if (!response.ok) throw new Error('Location navigation unavailable'); return response.json(); })
    .then(data => {
      const linkLocations = () => document.querySelectorAll('.event-meta dd, .kc-teaser-location').forEach(node => {
        if (node.querySelector('a') || node.closest('[data-past-shows-archive], .event-detail-copy')) return;
        if (node.tagName === 'DD' && node.parentElement.querySelector('dt')?.textContent.trim() !== 'Location') return;
        const target = data.locations[node.textContent.trim()];
        if (!target) return;
        const anchor = document.createElement('a'); anchor.className = 'kc-location-inline';
        anchor.href = target; anchor.textContent = node.textContent; node.replaceChildren(anchor);
      });
      linkLocations();
      let queued = false;
      const observer = new MutationObserver(() => {
        if (queued) return; queued = true;
        requestAnimationFrame(() => { queued = false; observer.disconnect(); linkLocations(); observer.observe(document.querySelector('main'), {childList:true,subtree:true}); });
      });
      const main = document.querySelector('main'); if (main) observer.observe(main, {childList:true,subtree:true});
    }).catch(() => { /* Static links and directory browsing remain available. */ });
})();
