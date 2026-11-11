import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { decide, healthResponse, localClock, runCheck, validateReceipt } from './worker.mjs';

const DATE = '2026-11-11';
const FULL_NOW = new Date(`${DATE}T11:30:00Z`); // 05:30 CST
const DATE_NOW = new Date(`${DATE}T09:00:00Z`); // 01:00 PST
const blank = () => ({ schemaVersion: 1, scheduled: {} });
const catalog = (day = DATE, count = 2) => ({ asOf: day, shows: Array.from({ length: count }, () => ({})) });
const attempt = (mode, conclusion = 'success', day = DATE) => ({ runId: '123', mode, day, conclusion,
  catalogDay: day, stages: { collection: mode === 'full' ? 'success' : 'skipped',
    source_save: 'success', build: 'success', deployment: 'success', live: 'success', freshness: 'success' } });
const stateWith = (mode, conclusion = 'success', day = DATE) => ({ schemaVersion: 1,
  scheduled: { [`${mode}:${day}`]: attempt(mode, conclusion, day) } });

class KV {
  constructor() { this.map = new Map(); this.writes = []; }
  async get(key) { return this.map.get(key) ?? null; }
  async put(key, value) { this.writes.push(key); this.map.set(key, value); }
}

function setup(options = {}) {
  const kv = options.kv || new KV();
  const calls = [], logs = [];
  const env = { ENABLED: 'true', GITHUB_TOKEN: 'do-not-expose-this-test-secret', WATCHDOG_STATE: kv, ...options.env };
  const fetcher = async (url, init) => {
    calls.push({ url, method: init?.method || 'GET', body: init?.body, headers: init?.headers, redirect: init?.redirect, signal: init?.signal });
    // Cloudflare Request supports follow/manual, not Node's redirect:error.
    if (init?.redirect === 'error') throw new TypeError('Unsupported redirect mode');
    if (options.redirectAt && url.includes(options.redirectAt))
      return new Response(null, { status: options.redirectStatus || 302,
        headers: { Location: 'https://untrusted-redirect.example/target' } });
    if (url.includes('/dispatches')) {
      assert(kv.map.has(`dispatch:${JSON.parse(init.body).inputs.refresh_mode}:${DATE}`), 'claim precedes POST');
      if (options.postThrows) throw new Error('secret network exception do-not-expose-this-test-secret');
      return new Response(null, { status: options.postStatus || 204 });
    }
    if (options.apiFails) return new Response('', { status: 503 });
    if (url.includes('raw.githubusercontent.com/')) return Response.json(options.state ?? blank());
    if (url.includes('fan-show-catalog')) return Response.json(options.catalog ?? catalog());
    const status = new URL(url).searchParams.get('status');
    const runs = options.active?.filter(x => x.status === status) || [];
    return Response.json({ total_count: options.totalCount ?? runs.length, workflow_runs: runs });
  };
  return { env, calls, logs, kv, deps: { now: options.now || FULL_NOW, fetch: fetcher, log: x => logs.push(x) } };
}

test('dates and full windows use the correct IANA timezone across DST', () => {
  assert.equal(localClock(new Date('2026-07-11T10:30:00Z'), 'America/Chicago').minutes, 330);
  assert.equal(localClock(FULL_NOW, 'America/Chicago').minutes, 330);
  for (const now of [FULL_NOW, new Date('2026-07-11T10:30:00Z')]) {
    const day = localClock(now, 'America/Los_Angeles').day;
    assert.equal(decide({ now, state: blank(), catalog: catalog(day) }).mayDispatch, true);
  }
  assert.equal(decide({ now: DATE_NOW, state: blank(), catalog: catalog('2026-11-10') }).mode, 'dates');
});

test('window boundaries are inclusive and there is no recovery after the full window', () => {
  for (const iso of ['2026-11-11T11:15:00Z', '2026-11-11T13:15:00Z'])
    assert.equal(decide({ now: new Date(iso), state: blank(), catalog: catalog() }).mayDispatch, true);
  const after = decide({ now: new Date('2026-11-11T13:16:00Z'), state: blank(), catalog: catalog() });
  assert.equal(after.mayDispatch, false); assert.equal(after.status, 'missing');
  const before = decide({ now: new Date('2026-11-11T08:44:00Z'), state: blank(), catalog: catalog('2026-11-10') });
  assert.equal(before.mayDispatch, false);
});

test('date backup does not publish when live date already current', () => {
  assert.equal(decide({ now: DATE_NOW, state: blank(), catalog: catalog() }).status, 'healthy');
});

test('current date is insufficient evidence for full collection', () => {
  assert.equal(decide({ now: FULL_NOW, state: blank(), catalog: catalog() }).mayDispatch, true);
});

test('queued or running publication is left alone, even if calendar stale', () => {
  for (const status of ['queued', 'in_progress']) {
    const result = decide({ now: FULL_NOW, state: blank(), catalog: catalog('2026-11-10'), activeRuns: [{ id: 123, status }] });
    assert.equal(result.status, 'active'); assert.equal(result.mayDispatch, false);
  }
});

test('any recorded attempt blocks a second attempt, including failed/cancelled/unfinished', () => {
  for (const conclusion of ['failure', 'cancelled', 'started', 'timed_out']) {
    const result = decide({ now: FULL_NOW, state: stateWith('full', conclusion), catalog: catalog('2026-11-10') });
    assert.equal(result.status, 'failed'); assert.equal(result.mayDispatch, false);
  }
});

test('matching latest manual receipt also blocks duplicates; prior day does not', () => {
  const state = { ...blank(), latest: attempt('full', 'failure') };
  assert.equal(decide({ now: FULL_NOW, state, catalog: catalog() }).mayDispatch, false);
  assert.equal(decide({ now: FULL_NOW, state: stateWith('full', 'success', '2026-11-10'), catalog: catalog() }).mayDispatch, true);
});

test('a later verified manual recovery supersedes the failed first claim for health', () => {
  const state = stateWith('full', 'failure');
  state.latest = { ...attempt('full'), runId: '124' };
  const result = decide({ now: FULL_NOW, state, catalog: catalog() });
  assert.equal(result.status, 'healthy'); assert.equal(result.mayDispatch, false);
  assert.equal(result.runId, '124');
});

test('completed recovery persists after a later date publication overwrites latest', () => {
  const state = stateWith('full', 'failure');
  state.completed = { [`full:${DATE}`]: { ...attempt('full'), runId: '124' } };
  state.latest = { ...attempt('dates'), runId: '125' };
  const result = decide({ now: FULL_NOW, state, catalog: catalog() });
  assert.equal(result.status, 'healthy'); assert.equal(result.runId, '124');
  assert.equal(result.mayDispatch, false);
});

test('verified full publication satisfies dates, but collection-only success does not', () => {
  const state = stateWith('full');
  assert.equal(decide({ now: DATE_NOW, state, catalog: catalog() }).reason, 'full_publication_satisfies_dates');
  state.scheduled[`full:${DATE}`].stages.live = 'failure';
  const result = decide({ now: FULL_NOW, state, catalog: catalog() });
  assert.equal(result.status, 'failed'); assert.equal(result.mayDispatch, false);
});

test('empty or stale calendar never reports a prior successful attempt as healthy', () => {
  for (const data of [catalog(DATE, 0), catalog('2026-11-10')]) {
    const result = decide({ now: FULL_NOW, state: stateWith('full'), catalog: data });
    assert.equal(result.status, 'failed'); assert.equal(result.mayDispatch, false);
  }
});

test('malformed receipts and claims fail closed', () => {
  for (const state of [null, { schemaVersion: 2, scheduled: {} }, { schemaVersion: 1, scheduled: [] },
    { schemaVersion: 1, scheduled: { [`full:${DATE}`]: null } },
    { schemaVersion: 1, scheduled: { 'full:2026-02-31': attempt('full', 'started', '2026-02-31') } },
    { ...blank(), completed: [] }, { ...blank(), completed: { [`full:${DATE}`]: attempt('full', 'started') } },
    { ...blank(), latest: {} }]) assert.throws(() => validateReceipt(state));
});

test('dispatch uses only fixed repository/workflow/main and required guard inputs', async () => {
  const h = setup(); const result = await runCheck(h.env, h.deps);
  assert.equal(result.status, 'dispatch_requested');
  const post = h.calls.filter(x => x.method === 'POST'); assert.equal(post.length, 1);
  assert.equal(post[0].url, 'https://api.github.com/repos/84lorinw-a11y/kingdom-circuit/actions/workflows/update-and-deploy.yml/dispatches');
  assert.deepEqual(JSON.parse(post[0].body), { ref: 'main', inputs: { refresh_mode: 'full', automatic_fallback: 'true', expected_day: DATE } });
  assert.equal(JSON.stringify(result).includes(h.env.GITHUB_TOKEN), false);
  assert.equal(h.logs.join('').includes(h.env.GITHUB_TOKEN), false);
  const receipt = h.calls.find(x => x.url.includes('raw.githubusercontent.com'));
  assert(receipt.url.includes('watchdog='));
  assert.equal(receipt.headers.Authorization, undefined);
  assert.equal(h.calls.some(x => x.url.includes('/contents/')), false);
  for (const call of h.calls) {
    assert.equal(call.redirect, 'manual');
    assert.equal(call.signal instanceof AbortSignal, true);
  }
});

test('public receipt and catalog redirects fail closed without requesting their destinations', async () => {
  for (const [redirectAt, reason] of [['raw.githubusercontent.com', 'github_receipt_http_302'],
    ['fan-show-catalog', 'live_catalog_http_302']]) {
    const h = setup({ redirectAt }); const result = await runCheck(h.env, h.deps);
    assert.equal(result.status, 'error'); assert.equal(result.reason, reason);
    assert.equal(h.calls.some(x => x.url.includes('untrusted-redirect')), false);
    assert.equal(h.calls.some(x => x.method === 'POST'), false);
    assert.equal(h.calls.at(-1).redirect, 'manual');
  }
});

test('authenticated Actions GET redirects fail closed without forwarding credentials', async () => {
  const h = setup({ redirectAt: '/runs?', redirectStatus: 307 });
  const result = await runCheck(h.env, h.deps);
  assert.equal(result.reason, 'github_runs_http_307');
  assert.equal(h.calls.filter(x => x.url.includes('/runs?')).length, 1);
  assert.equal(h.calls.some(x => x.url.includes('untrusted-redirect')), false);
  assert.equal(h.calls.some(x => x.method === 'POST'), false);
  assert.equal(h.calls.at(-1).redirect, 'manual');
});

test('dispatch redirects are rejected once without forwarding credentials or retrying', async () => {
  const h = setup({ redirectAt: '/dispatches', redirectStatus: 307 });
  const result = await runCheck(h.env, h.deps);
  assert.equal(result.status, 'failed'); assert.equal(result.reason, 'dispatch_http_307');
  assert.equal(h.calls.some(x => x.url.includes('untrusted-redirect')), false);
  await runCheck(h.env, h.deps);
  assert.equal(h.calls.filter(x => x.method === 'POST').length, 1);
  assert.equal(h.calls.find(x => x.method === 'POST').redirect, 'manual');
});

test('accepted dispatch is not retried before GitHub receipt appears', async () => {
  const h = setup(); await runCheck(h.env, h.deps);
  const result = await runCheck(h.env, h.deps);
  assert.equal(result.reason, 'dispatch_already_attempted_no_daily_receipt');
  assert.equal(h.calls.filter(x => x.method === 'POST').length, 1);
});

test('unknown POST outcome is saved and never duplicated', async () => {
  const h = setup({ postThrows: true }); const first = await runCheck(h.env, h.deps);
  assert.equal(first.status, 'dispatch_unknown');
  await runCheck(h.env, h.deps);
  assert.equal(h.calls.filter(x => x.method === 'POST').length, 1);
  assert.equal(h.logs.join('').includes(h.env.GITHUB_TOKEN), false);
});

test('rejected POST is not automatically retried', async () => {
  const h = setup({ postStatus: 403 }); assert.equal((await runCheck(h.env, h.deps)).reason, 'dispatch_http_403');
  await runCheck(h.env, h.deps); assert.equal(h.calls.filter(x => x.method === 'POST').length, 1);
});

test('API errors, malformed API state, incomplete runs, and absent token prevent dispatch', async () => {
  for (const options of [{ apiFails: true }, { state: null }, { state: { schemaVersion: 1 } },
    { totalCount: 101 }, { env: { GITHUB_TOKEN: '' } }]) {
    if (options.state === null) options.state = [];
    const h = setup(options); const result = await runCheck(h.env, h.deps);
    assert.equal(result.status, 'error'); assert.equal(h.calls.some(x => x.method === 'POST'), false);
  }
});

test('disabled worker performs no external requests', async () => {
  const h = setup({ env: { ENABLED: 'false' } });
  assert.equal((await runCheck(h.env, h.deps)).status, 'disabled'); assert.equal(h.calls.length, 0);
});

test('state storage failure prevents dispatch and reports only safe reason', async () => {
  const h = setup(); h.kv.put = async () => { throw new Error('private failure'); };
  assert.equal((await runCheck(h.env, h.deps)).reason, 'state_write_failed');
  assert.equal(h.calls.some(x => x.method === 'POST'), false);
});

test('HTTP health endpoint only reads stored result and never dispatches', async () => {
  const h = setup(); await h.kv.put('latest', JSON.stringify({ status: 'healthy', checkedAt: FULL_NOW.toISOString() }));
  const health = await healthResponse(new Request('https://watchdog.example/health'), h.env, FULL_NOW);
  assert.equal((await health.json()).status, 'healthy');
  const post = await worker.fetch(new Request('https://watchdog.example/health', { method: 'POST' }), h.env);
  assert.equal(post.status, 405);
  const bad = await worker.fetch(new Request('https://watchdog.example/run'), h.env);
  assert.equal(bad.status, 404); assert.equal(h.calls.length, 0);
});

test('health marks an old check stale without modifying stored state or making requests', async () => {
  const h = setup(); const saved = { status: 'healthy', checkedAt: FULL_NOW.toISOString() };
  await h.kv.put('latest', JSON.stringify(saved));
  const result = await healthResponse(new Request('https://watchdog.example/health'), h.env,
    new Date(FULL_NOW.getTime() + 46 * 60000));
  assert.equal(result.status, 503);
  assert.deepEqual(await result.json(), { ...saved, status: 'stale', lastStatus: 'healthy', reason: 'last_check_stale', ageMinutes: 46 });
  assert.deepEqual(JSON.parse(await h.kv.get('latest')), saved); assert.equal(h.calls.length, 0);
});

test('health returns unavailable when no check or invalid/future check timestamp exists', async () => {
  for (const value of [null, { status: 'healthy' }, { status: 'healthy', checkedAt: 'not-a-date' },
    { status: 'healthy', checkedAt: '2027-01-01T00:00:00Z' }]) {
    const h = setup(); if (value) await h.kv.put('latest', JSON.stringify(value));
    const result = await healthResponse(new Request('https://watchdog.example/health'), h.env, FULL_NOW);
    assert.equal(result.status, 503); assert.equal(h.calls.length, 0);
  }
});
