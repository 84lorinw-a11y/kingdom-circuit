const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../assets/artist-intake.js'), 'utf8');

function harness(fetcher, values = {}) {
  const fields = Object.entries({artistName: '', submitter_name: 'Test submitter', email: 'test@example.com', website: '', instagram: '', spotify: '', youtube: '', photoUrl: '', environment: 'production', submission_type: 'CHH artist submission', subject: 'Kingdom Circuit artist profile', page_url: '', _gotcha: '', ...values}).map(([name, value]) => ({name, value, disabled: false}));
  const button = {disabled: false, textContent: 'Submit Profile'};
  const status = {textContent: '', classList: {add() {}, remove() {}}};
  const success = {hidden: true, focused: false, focus() {this.focused = true;}};
  let listener;
  const form = {
    action: 'https://formspree.io/f/mljreawj', hidden: false, elements: [...fields, button],
    valid: true, reportValidity() {return this.valid;},
    querySelector: id => id === '#ai-submit' ? button : status,
    addEventListener: (name, fn) => {listener = fn;},
    setAttribute() {}, removeAttribute() {}
  };
  const calls = [];
  class Data extends Map {
    constructor(input) {super(input.elements.filter(f => f.name && !f.disabled).map(f => [f.name, f.value]));}
  }
  vm.runInNewContext(script, {
    document: {querySelector: id => id === '#artist-intake-form' ? form : success},
    window: {location: {origin: 'https://kingdomcircuit.com', pathname: '/submit/artist/', search: '?private=excluded'}},
    FormData: Data,
    fetch: async (...args) => {calls.push(args); return fetcher(...args);}
  });
  return {form, fields, button, status, success, calls, submit: () => listener({preventDefault() {}})};
}
const accepted = () => ({ok: true, status: 200, json: async () => ({ok: true})});

test('required contact fields and flexible profiles submit to the approved endpoint', async () => {
  const h = harness(accepted, {artistName: 'Test Artist', spotify: 'dddd', instagram: '@test'});
  await h.submit();
  const [url, request] = h.calls[0];
  assert.equal(url, 'https://formspree.io/f/mljreawj');
  assert.equal(request.method, 'POST');
  assert.equal(request.headers.Accept, 'application/json');
  assert.equal(request.body.get('spotify'), 'dddd');
  assert.equal(request.body.get('submitter_name'), 'Test submitter');
  assert.equal(request.body.get('email'), 'test@example.com');
  assert.equal(request.body.get('photoUrl'), '');
  assert.equal(request.body.get('_gotcha'), '');
  assert.equal(request.body.get('environment'), 'production');
  assert.equal(request.body.get('page_url'), 'https://kingdomcircuit.com/submit/artist/');
  assert.equal(request.body.has('contactEmail'), false);
  assert.equal(h.form.hidden, true);
  assert.equal(h.success.hidden, false);
  assert.equal(h.success.focused, true);
});

test('invalid required contact fields do not send a request or lose entered details', async () => {
  const h = harness(accepted, {email: '', artistName: 'Keep me', spotify: 'dddd'});
  h.form.valid = false;
  await h.submit();
  assert.equal(h.calls.length, 0);
  assert.equal(h.button.disabled, false);
  assert.equal(h.success.hidden, true);
  assert.equal(h.fields.find(f => f.name === 'artistName').value, 'Keep me');
});

test('only one request can be in flight and no success is shown before confirmation', async () => {
  let resolve;
  const h = harness(() => new Promise(done => {resolve = done;}));
  const pending = h.submit();
  await h.submit();
  assert.equal(h.calls.length, 1);
  assert.equal(h.button.disabled, true);
  assert.equal(h.success.hidden, true);
  resolve(accepted());
  await pending;
  assert.equal(h.button.disabled, false);
  assert.equal(h.success.hidden, false);
});

for (const scenario of [
  ['HTTP failure', () => ({ok: false, status: 500, json: async () => ({ok: false})}), /couldn’t submit/],
  ['rate limit', () => ({ok: false, status: 429, json: async () => ({ok: false})}), /wait a minute/],
  ['rejected response', () => ({ok: true, status: 200, json: async () => ({ok: false})}), /couldn’t submit/],
  ['network failure', () => {throw new Error('offline');}, /couldn’t confirm/],
  ['invalid response', () => ({ok: true, status: 200, json: async () => {throw new Error('not JSON');}}), /couldn’t confirm/]
]) {
  test(`${scenario[0]} retains details and permits a deliberate retry`, async () => {
    let attempt = 0;
    const h = harness(() => ++attempt === 1 ? scenario[1]() : accepted(), {artistName: 'Keep me', spotify: 'dddd'});
    await h.submit();
    assert.equal(h.form.hidden, false);
    assert.equal(h.success.hidden, true);
    assert.equal(h.button.disabled, false);
    assert.match(h.status.textContent, scenario[2]);
    assert.equal(h.fields.find(f => f.name === 'artistName').value, 'Keep me');
    assert.equal(h.fields.find(f => f.name === 'spotify').value, 'dddd');
    assert.equal(h.calls.length, 1);
    await h.submit();
    assert.equal(h.calls.length, 2);
    assert.equal(h.success.hidden, false);
  });
}
