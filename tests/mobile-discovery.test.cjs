const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../assets/mobile-seo-preview.js'), 'utf8');

function element(extra = {}) {
  const listeners = {};
  return Object.assign({ hidden: true, value: '', textContent: '', attributes: {},
    addEventListener(name, fn) { (listeners[name] ||= []).push(fn); },
    fire(name) { for (const fn of listeners[name] || []) fn(); },
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this[name]; },
  }, extra);
}

function setup() {
  const select = element({ selectedOptions: [{value: ''}] });
  const open = element({disabled: true});
  const picker = element({ querySelector(s) { return s === 'select' ? select : open; } });
  const filter = element();
  const link = element();
  const reset = element();
  const buttons = ['posters', 'list'].map(view => element({dataset: {showView: view}}));
  const tools = element({querySelectorAll() { return buttons; }, querySelector() { return link; }});
  const classes = new Set();
  const grid = {classList: { toggle(name, active) { active ? classes.add(name) : classes.delete(name); } }};
  const destinations = {textContent: JSON.stringify({TX: {href: '/shows/texas/', name: 'Texas'}})};
  const map = {'[data-state-picker]': picker, '[data-calendar-tools]': tools, '.event-grid': grid,
    '[data-state-filter]': filter, '[data-reset-filters]': reset, '#kc-state-destinations': destinations};
  const document = element({querySelector(s) { return map[s]; }});
  const navigations = [];
  let observer;
  vm.runInNewContext(source, {document, window: {location: {assign(href) {navigations.push(href);}}},
    MutationObserver: class { constructor(fn) {observer = fn;} observe() {} }, queueMicrotask});
  return {select, open, picker, filter, link, reset, buttons, tools, grid, classes, navigations, observer};
}

test('choosing a state does not navigate until View shows is activated', () => {
  const ui = setup();
  ui.select.value = '/shows/texas/';
  ui.select.selectedOptions = [{value: ui.select.value}];
  ui.select.fire('change');
  assert.equal(ui.open.disabled, false);
  assert.deepEqual(ui.navigations, []);
  ui.open.fire('click');
  assert.deepEqual(ui.navigations, ['/shows/texas/']);
});

test('the test picker refuses production or arbitrary external destinations', () => {
  const ui = setup();
  for (const value of ['', 'https://kingdomcircuit.com/shows/texas/', 'https://example.com/']) {
    ui.select.selectedOptions = [{value}];
    ui.open.fire('click');
  }
  assert.deepEqual(ui.navigations, []);
});

test('retired view buttons cannot change the normal show listing', () => {
  const ui = setup();
  ui.buttons[1].fire('click');
  assert.equal(ui.classes.has('kc-quick-list'), false);
  assert.equal(ui.buttons[1].attributes['aria-pressed'], undefined);
  ui.buttons[0].fire('click');
  assert.equal(ui.classes.has('kc-quick-list'), false);
  assert.equal(ui.buttons[0].attributes['aria-pressed'], undefined);
});

test('state-page link follows filtering and disappears after Clear filters', async () => {
  const ui = setup();
  assert.equal(ui.link.hidden, true);
  ui.filter.value = 'TX';
  ui.filter.fire('change');
  assert.equal(ui.link.href, '/shows/texas/');
  assert.equal(ui.link.textContent, 'View all Texas shows →');
  assert.equal(ui.link.hidden, false);
  ui.filter.value = '';
  ui.reset.fire('click');
  await Promise.resolve();
  assert.equal(ui.link.hidden, true);
  assert.equal(ui.link.href, undefined);
});

test('async population of a preselected state updates the destination link', () => {
  const ui = setup();
  ui.filter.value = 'TX';
  ui.observer();
  assert.equal(ui.link.hidden, false);
  assert.equal(ui.link.href, '/shows/texas/');
});
