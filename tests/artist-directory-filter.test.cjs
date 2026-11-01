const test = require('node:test');
const assert = require('node:assert/strict');
const {matchingShows, eventHref, canonicalEventPath, uniqueArtistShows, nextShowLabel, updateCardShows, syncDirectoryFilters, emptyMessage, STATE_NAMES} = require('../assets/artist-filter-fix.js');

// Frozen public records keep this regression valid after upcoming feeds prune dates.
const {events, catalog} = require('./fixtures/artist-directory-public-shows.json');
const sarnia = events.find(e => e.id === 'manual:ant-lee-light-up-the-city-sarnia-2026-11-13');
const lloydminster = events.find(e => e.id === 'manual:ant-lee-light-up-the-city-lloydminster-2027-02-26');
const shows = [sarnia, lloydminster];
const paths = [
  '/event/light-up-the-city-ant-lee-2026-11-13-sarnia-61f1c1/',
  '/event/light-up-the-city-ant-lee-2027-02-26-lloydminster-c950ee/'
];

test('Ontario in November and Saskatchewan in February match the same event, not separate shows', () => {
  assert.ok(sarnia && lloydminster, 'Frozen Canadian fixtures must be present');
  assert.deepEqual(matchingShows(shows, 'ON', '2026-11'), [sarnia]);
  assert.deepEqual(matchingShows(shows, 'SK', '2027-02'), [lloydminster]);
  assert.deepEqual(matchingShows(shows, 'ON', '2027-02'), []);
  assert.deepEqual(matchingShows(shows, 'SK', '2026-11'), []);
  assert.deepEqual(matchingShows(shows), shows);
});

test('manual and bare feed IDs for Flavor Fest count as one published booking', () => {
  const lecrae = events.filter(e => e.artists.includes('Lecrae'));
  assert.equal(lecrae.length, 3, 'Frozen primary and supplemental feeds reproduce the duplicate');
  const unique = uniqueArtistShows(lecrae, catalog, '/artists/lecrae/');
  assert.equal(unique.length, 2);
  assert.equal(matchingShows(unique, 'FL', '2026-11').length, 1);
  assert.equal(matchingShows(unique, 'GA', '2027-05').length, 1);
  assert.equal(eventHref(unique[0], catalog, '/artists/lecrae/'),
    '/event/flavor-fest-2026-saturday-concerts-2026-11-07-tampa-cf7fac/');
  assert.equal(uniqueArtistShows(lecrae, null, '/artists/lecrae/').length, 3,
    'Without a published match, distinct source IDs must not be guessed away');
});

test('same-day distinct published shows and ambiguous legacy records stay separate', () => {
  const first = {...sarnia, id: 'first', title: 'Afternoon performance', startTime: '15:00'};
  const second = {...sarnia, id: 'second', title: 'Evening performance', startTime: '19:00'};
  const firstPath = '/event/afternoon-performance/', secondPath = '/event/evening-performance/';
  const sameDay = {artists: {'/artists/ant-lee/': [firstPath, secondPath]}, shows: [first, second].map((e, i) => ({
    path: [firstPath, secondPath][i], name: e.title, date: e.startDate, venue: e.venue,
    location: `${e.city}, ${e.state}`
  }))};
  assert.deepEqual(uniqueArtistShows([first, {...first, id: 'manual:first'}, second], sameDay,
    '/artists/ant-lee/'), [first, second]);
  const ambiguous = [{...first, id: 'unknown-afternoon', title: 'Tour show'},
    {...second, id: 'unknown-evening', title: 'Tour show'}];
  assert.equal(canonicalEventPath(ambiguous[0], sameDay, '/artists/ant-lee/'), null);
  assert.deepEqual(uniqueArtistShows(ambiguous, sameDay, '/artists/ant-lee/'), ambiguous);
  const otherPerformance = {...sarnia, id: 'same-title-different-time', startTime: '15:00'};
  assert.equal(canonicalEventPath(otherPerformance, catalog, '/artists/ant-lee/'), null);
  assert.deepEqual(uniqueArtistShows([sarnia, otherPerformance], catalog, '/artists/ant-lee/'),
    [sarnia, otherPerformance]);
});

test('frozen Charlotte feeds with room and supporting-billing suffixes resolve only with the same published time', () => {
  const charlotte = events.filter(e => e.city === 'Charlotte');
  assert.equal(charlotte.length, 2);
  assert.equal(uniqueArtistShows(charlotte, catalog, '/artists/skema-boy/').length, 1);
  assert.equal(eventHref(charlotte[1], catalog, '/artists/skema-boy/'),
    '/event/zauntee-god-remembers-tour-2026-11-04-charlotte-3114fc/');
  const differentTime = {...charlotte[1], id: 'distinct-time', startTime: '17:00'};
  assert.equal(uniqueArtistShows([charlotte[0], differentTime], catalog, '/artists/skema-boy/').length, 2);
  const noTime = {...charlotte[1], id: 'unknown-time', startTime: ''};
  assert.equal(canonicalEventPath(noTime, catalog, '/artists/skema-boy/'), null);
});

function filterControls() {
  const control = values => ({value: '', options: values.map(value => ({value})), handlers: {},
    addEventListener(type, handler) {this.handlers[type] = handler;}});
  return {artistSelect: control(['', 'Ant Lee', '180MINDSET']), stateSelect: control(['', 'ON', 'SK']),
    monthSelect: control(['', '2026-11', '2027-02']),
    upcomingOnly: {...control([]), checked: true, defaultChecked: true}, reset: control([])};
}

test('a shared directory URL restores all controls before rendering, including unchecked upcoming', () => {
  const controls = filterControls(), listeners = {}, snapshots = [];
  const browser = {location: {href: 'https://kingdomcircuit.com/artists/?artist=Ant+Lee&state=SK&month=2027-02&upcoming=0'},
    history: {}, addEventListener(type, fn) {listeners[type] = fn;}};
  syncDirectoryFilters(controls, () => snapshots.push([controls.artistSelect.value, controls.stateSelect.value,
    controls.monthSelect.value, controls.upcomingOnly.checked]), browser);
  assert.deepEqual(snapshots, [['Ant Lee', 'SK', '2027-02', false]]);
  assert.deepEqual(matchingShows(shows, controls.stateSelect.value, controls.monthSelect.value), [lloydminster]);
  // Browser back / bfcache restores the URL even if another initialization reset a control.
  controls.stateSelect.value = '';
  controls.upcomingOnly.checked = true;
  listeners.pageshow();
  assert.deepEqual(snapshots.at(-1), ['Ant Lee', 'SK', '2027-02', false]);
  browser.location.href = 'https://kingdomcircuit.com/artists/?artist=Ant+Lee&state=ON&month=2026-11&upcoming=1';
  listeners.popstate();
  assert.deepEqual(snapshots.at(-1), ['Ant Lee', 'ON', '2026-11', true]);
});

test('filter edits replace the directory history entry and reset survives reload without losing unrelated URL data', () => {
  const controls = filterControls(), saved = [], listeners = {};
  const browser = {location: {href: 'https://kingdomcircuit.com/artists/?ref=shared#artists'},
    history: {state: {retained: true}, replaceState(state, _, href) {
      saved.push({state, href}); browser.location.href = new URL(href, browser.location.href).href;
    }}, addEventListener(type, fn) {listeners[type] = fn;}};
  syncDirectoryFilters(controls, () => {}, browser);
  assert.equal(controls.upcomingOnly.checked, true);
  assert.equal(saved.length, 0, 'Initial hydration must not rewrite an untouched URL');
  controls.artistSelect.value = 'Ant Lee'; controls.stateSelect.value = 'SK'; controls.monthSelect.value = '2027-02';
  controls.monthSelect.handlers.change();
  const current = new URL(browser.location.href);
  assert.equal(current.searchParams.get('artist'), 'Ant Lee');
  assert.equal(current.searchParams.get('state'), 'SK');
  assert.equal(current.searchParams.get('month'), '2027-02');
  assert.equal(current.searchParams.get('upcoming'), '1');
  assert.equal(current.searchParams.get('ref'), 'shared');
  assert.equal(current.hash, '#artists');
  assert.deepEqual(saved[0].state, {retained: true});
  controls.reset.handlers.click();
  assert.equal(new URL(browser.location.href).searchParams.has('artist'), false);
  assert.equal(new URL(browser.location.href).searchParams.get('upcoming'), '0');
  const reloaded = filterControls();
  syncDirectoryFilters(reloaded, () => {}, browser);
  assert.equal(reloaded.upcomingOnly.checked, false);
  assert.equal(reloaded.stateSelect.value, '');
});

test('unavailable URL options safely clear while Canadian labels and upcoming recovery remain explicit', () => {
  const controls = filterControls();
  syncDirectoryFilters(controls, () => {}, {location: {href: 'https://kingdomcircuit.com/artists/?artist=Unknown&state=XX&month=not-a-month'},
    addEventListener() {}});
  assert.deepEqual([controls.artistSelect.value, controls.stateSelect.value, controls.monthSelect.value], ['', '', '']);
  assert.deepEqual([STATE_NAMES.BC, STATE_NAMES.ON, STATE_NAMES.SK], ['British Columbia', 'Ontario', 'Saskatchewan']);
  assert.match(emptyMessage(true), /Uncheck “Only artists with upcoming shows”/);
  assert.equal(emptyMessage(false), 'No artists match those filters.');
});

test('next-show links use the published event path, including a revised published title', () => {
  assert.equal(eventHref(sarnia, catalog, '/artists/ant-lee/'), paths[0]);
  assert.equal(eventHref(lloydminster, catalog, '/artists/ant-lee/'), paths[1]);
  assert.equal(eventHref({...lloydminster, title: 'Alternate source title'}, catalog, '/artists/ant-lee/'), paths[1]);
  const conflicting = {...catalog, artists: {'/artists/ant-lee/': [paths[0]]}};
  assert.match(eventHref(lloydminster, conflicting, '/artists/ant-lee/'), /^\/event\/\?id=/);
  assert.match(eventHref(sarnia, null, '/artists/ant-lee/'), /^\/event\/\?id=/);
});

test('date labels retain the event calendar date and omit speculative time', () => {
  assert.equal(nextShowLabel(lloydminster), 'Fri, Feb 26, 2027 · Lloydminster, SK');
  assert.equal(nextShowLabel(sarnia), 'Fri, Nov 13, 2026 · Sarnia, ON');
});

test('card content updates together and reset restores the original upcoming summary', () => {
  const node = text => ({textContent: text, children: [], setAttribute(k,v) {this[k]=v;},
    replaceChildren(...children) {this.children=children;}});
  const count = node('2 upcoming shows'), strong = node('Next:'), line = node(''), states = node('');
  line.querySelector = () => strong;
  const heading = {textContent: 'Ant Lee', getAttribute: () => '/artists/ant-lee/'};
  const card = {querySelector: selector => ({'h2 a': heading, '.artist-card-body > p': count,
    '.seo-card-next': line, '.seo-card-states': states})[selector]};
  global.document = {createElement: () => node(''), createTextNode: text => node(text)};
  try {
    updateCardShows(card, matchingShows(shows, 'SK', '2027-02'), true, catalog);
    assert.equal(count.textContent, '1 matching show');
    assert.equal(strong.textContent, 'Next match:');
    assert.equal(line.children[2].href, paths[1]);
    assert.match(line.children[2].textContent, /Feb 26, 2027 · Lloydminster, SK/);
    assert.equal(states.children[0].textContent, 'Matching:');
    assert.equal(states.children[1].textContent, ' SK');

    updateCardShows(card, matchingShows(shows, 'ON', '2026-11'), true, catalog);
    assert.equal(line.children[2].href, paths[0]);
    assert.match(line.children[2].textContent, /Nov 13, 2026 · Sarnia, ON/);

    updateCardShows(card, matchingShows(shows), false, catalog);
    assert.equal(count.textContent, '2 upcoming shows');
    assert.equal(strong.textContent, 'Next:');
    assert.equal(states.children[1].textContent, ' ON, SK');
    assert.equal(line.children[2].href, paths[0]);
  } finally { delete global.document; }
});
