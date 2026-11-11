// Independent missing-schedule backup. GitHub remains the only publisher.
// This module intentionally has no HTTP endpoint that can trigger a workflow.
export const REPOSITORY = '84lorinw-a11y/kingdom-circuit';
export const WORKFLOW = 'update-and-deploy.yml';
const API = `https://api.github.com/repos/${REPOSITORY}`;
const RECEIPT = `https://raw.githubusercontent.com/${REPOSITORY}/main/daily-publication-status.json`;
const CATALOG = 'https://kingdomcircuit.com/assets/fan-show-catalog.json';
const ACTIVE = ['queued', 'in_progress', 'waiting', 'pending', 'requested'];
const MODES = ['dates', 'full'];
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const RUN = /^\d+$/;
const TTL = 14 * 86400;

class CheckError extends Error {
  constructor(code) { super(code); this.code = code; }
}

export function localClock(now, timeZone) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(now).map(x => [x.type, x.value]));
  return { day: `${parts.year}-${parts.month}-${parts.day}`,
    minutes: Number(parts.hour) * 60 + Number(parts.minute) };
}

function validDay(day) {
  return typeof day === 'string' && DAY.test(day)
    && !Number.isNaN(Date.parse(day)) && new Date(day).toISOString().slice(0, 10) === day;
}

function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }

function validAttempt(value, mode, day) {
  return object(value) && RUN.test(String(value.runId || ''))
    && value.mode === mode && value.day === day
    && typeof value.conclusion === 'string' && value.conclusion.length > 0;
}

export function validateReceipt(state) {
  if (!object(state) || state.schemaVersion !== 1 || !object(state.scheduled))
    throw new CheckError('invalid_publication_receipt');
  if (state.completed !== undefined && !object(state.completed))
    throw new CheckError('invalid_completed_receipts');
  for (const [collection, values] of [['scheduled', state.scheduled], ['completed', state.completed || {}]]) {
    for (const [key, value] of Object.entries(values)) {
      const [mode, day, extra] = key.split(':');
      if (extra || !MODES.includes(mode) || !validDay(day) || !validAttempt(value, mode, day)
          || (collection === 'completed' && value.conclusion === 'started'))
        throw new CheckError(collection === 'scheduled' ? 'invalid_daily_claim' : 'invalid_completed_receipt');
    }
  }
  if (state.latest !== undefined && (!object(state.latest) || !MODES.includes(state.latest.mode)
      || !validDay(state.latest.day) || !validAttempt(state.latest, state.latest.mode, state.latest.day)))
    throw new CheckError('invalid_latest_receipt');
  return state;
}

function attemptFor(state, mode, day) {
  const claim = state.scheduled[`${mode}:${day}`];
  const latest = state.latest?.mode === mode && state.latest?.day === day ? state.latest : null;
  const completed = state.completed?.[`${mode}:${day}`];
  // An explicitly reviewed manual recovery may succeed after the first durable
  // attempt failed. Keep the claim as a retry guard, but report newer evidence.
  return [claim, completed, latest].filter(Boolean).reduce((chosen, item) =>
    !chosen || BigInt(item.runId) >= BigInt(chosen.runId) ? item : chosen, null);
}

function published(attempt, day) {
  return attempt?.conclusion === 'success' && attempt.catalogDay === day
    && ['source_save', 'build', 'deployment', 'live', 'freshness'].every(x => attempt.stages?.[x] === 'success')
    && (attempt.mode !== 'full' || attempt.stages?.collection === 'success');
}

export function decide({ now, state, catalog, activeRuns = [] }) {
  validateReceipt(state);
  if (!object(catalog) || !validDay(catalog.asOf) || !Array.isArray(catalog.shows))
    throw new CheckError('invalid_live_catalog');
  const pacific = localClock(now, 'America/Los_Angeles');
  const central = localClock(now, 'America/Chicago');
  const datesWindow = pacific.minutes >= 45 && pacific.minutes <= 135;
  const fullWindow = central.minutes >= 315 && central.minutes <= 435;
  const mode = fullWindow || central.minutes > 435 ? 'full' : 'dates';
  const day = mode === 'full' ? central.day : pacific.day;
  const liveHealthy = catalog.asOf === pacific.day && catalog.shows.length > 0;
  const base = { mode, day, pacificDay: pacific.day, liveAsOf: catalog.asOf,
    upcomingCount: catalog.shows.length, liveHealthy, mayDispatch: false };
  if (activeRuns.length) return { ...base, status: 'active', reason: 'publication_run_active',
    runIds: activeRuns.map(x => String(x.id)) };
  const full = attemptFor(state, 'full', central.day);
  if (mode === 'dates' && published(full, pacific.day) && liveHealthy)
    return { ...base, status: 'healthy', reason: 'full_publication_satisfies_dates', runId: String(full.runId) };
  const prior = attemptFor(state, mode, day);
  if (prior) {
    if (published(prior, pacific.day) && liveHealthy)
      return { ...base, status: 'healthy', reason: 'publication_verified', runId: String(prior.runId) };
    return { ...base, status: 'failed', reason: prior.conclusion === 'started' ? 'unfinished_daily_claim' :
      published(prior, pacific.day) ? 'published_calendar_unhealthy' : 'daily_attempt_not_verified',
      runId: String(prior.runId), conclusion: prior.conclusion };
  }
  if (mode === 'dates' && liveHealthy)
    return { ...base, status: 'healthy', reason: 'live_date_already_current' };
  if (!datesWindow && !fullWindow)
    return { ...base, status: central.minutes > 435 || !liveHealthy ? 'missing' : 'healthy',
      reason: 'outside_recovery_window' };
  return { ...base, status: 'missing', reason: 'no_daily_attempt', mayDispatch: true };
}

function headers(token) {
  return { Authorization: `Bearer ${token}`, 'User-Agent': 'Kingdom-Circuit-Publication-Watchdog',
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28', 'Cache-Control': 'no-cache' };
}

async function getJSON(fetcher, url, options, code) {
  let response;
  // Workers rejects redirect:'error' before sending. Manual returns 3xx to
  // the failure check below and never forwards credentials to another host.
  try { response = await fetcher(url, { ...options, redirect: 'manual', signal: AbortSignal.timeout(15000) }); }
  catch { throw new CheckError(`${code}_unavailable`); }
  if (!response.ok) throw new CheckError(`${code}_http_${response.status}`);
  try { return await response.json(); } catch { throw new CheckError(`${code}_invalid_json`); }
}

async function getActive(fetcher, token) {
  const active = [];
  for (const status of ACTIVE) {
    const data = await getJSON(fetcher,
      `${API}/actions/workflows/${WORKFLOW}/runs?branch=main&status=${status}&per_page=100`,
      { headers: headers(token) }, 'github_runs');
    if (!object(data) || !Array.isArray(data.workflow_runs) || !Number.isInteger(data.total_count)
        || data.total_count < 0 || data.total_count > 100 || data.workflow_runs.length !== data.total_count)
      throw new CheckError('incomplete_active_run_listing');
    for (const run of data.workflow_runs) {
      if (!object(run) || !RUN.test(String(run.id || '')) || run.head_branch !== 'main' || !ACTIVE.includes(run.status))
        throw new CheckError('invalid_active_run');
      active.push(run);
    }
  }
  return [...new Map(active.map(x => [x.id, x])).values()];
}

async function kvGet(kv, key) {
  let raw;
  try { raw = await kv.get(key); } catch { throw new CheckError('state_read_failed'); }
  if (raw === null) return null;
  try { return JSON.parse(raw); } catch { throw new CheckError('invalid_watchdog_state'); }
}

async function kvPut(kv, key, value) {
  try { await kv.put(key, JSON.stringify(value), { expirationTtl: TTL }); }
  catch { throw new CheckError('state_write_failed'); }
}

export async function runCheck(env, deps = {}) {
  const now = deps.now || new Date();
  const fetcher = deps.fetch || fetch;
  const checkedAt = now.toISOString();
  let result = { checkedAt, status: 'disabled', reason: 'not_enabled', mayDispatch: false };
  try {
    if (!env.WATCHDOG_STATE?.get || !env.WATCHDOG_STATE?.put)
      throw new CheckError('missing_state_binding');
    if (env.ENABLED !== 'true') return await finish(env, result, deps);
    if (!env.GITHUB_TOKEN || typeof env.GITHUB_TOKEN !== 'string') throw new CheckError('missing_github_token');
    // Public raw source needs no Contents permission and receives no token.
    const state = await getJSON(fetcher, `${RECEIPT}?watchdog=${now.getTime()}`,
      { headers: { 'Cache-Control': 'no-cache' } }, 'github_receipt');
    validateReceipt(state);
    const catalog = await getJSON(fetcher, `${CATALOG}?watchdog=${now.getTime()}`,
      { headers: { 'Cache-Control': 'no-cache' } }, 'live_catalog');
    const activeRuns = await getActive(fetcher, env.GITHUB_TOKEN);
    result = { checkedAt, ...decide({ now, state, catalog, activeRuns }) };
    if (!result.mayDispatch) return await finish(env, result, deps);
    const key = `dispatch:${result.mode}:${result.day}`;
    const previous = await kvGet(env.WATCHDOG_STATE, key);
    if (previous !== null) {
      if (!object(previous) || previous.day !== result.day || previous.mode !== result.mode ||
          typeof previous.requestedAt !== 'string') throw new CheckError('invalid_dispatch_claim');
      result = { ...result, status: 'failed', reason: 'dispatch_already_attempted_no_daily_receipt',
        mayDispatch: false, requestedAt: previous.requestedAt };
      return await finish(env, result, deps);
    }
    // Save before the network write. An ambiguous POST must never be retried
    // automatically; the GitHub daily claim is the final serialization guard.
    const intent = { mode: result.mode, day: result.day, requestedAt: checkedAt, phase: 'requesting' };
    await kvPut(env.WATCHDOG_STATE, key, intent);
    let response;
    try {
      response = await fetcher(`${API}/actions/workflows/${WORKFLOW}/dispatches`, {
        // As with GET, reject redirects without following or forwarding auth.
        method: 'POST', redirect: 'manual', signal: AbortSignal.timeout(15000),
        headers: { ...headers(env.GITHUB_TOKEN), 'Content-Type': 'application/json' },
        body: JSON.stringify({ ref: 'main', inputs: { refresh_mode: result.mode,
          automatic_fallback: 'true', expected_day: result.day } }),
      });
    } catch {
      result = { ...result, status: 'dispatch_unknown', reason: 'dispatch_outcome_unknown', mayDispatch: false };
      await kvPut(env.WATCHDOG_STATE, key, { ...intent, phase: 'unknown' });
      return await finish(env, result, deps);
    }
    const accepted = response.status === 204 || response.status === 200;
    await kvPut(env.WATCHDOG_STATE, key, { ...intent, phase: accepted ? 'accepted' : 'rejected', httpStatus: response.status });
    result = { ...result, status: accepted ? 'dispatch_requested' : 'failed', mayDispatch: false,
      reason: accepted ? 'github_accepted_dispatch' : `dispatch_http_${response.status}` };
  } catch (error) {
    result = { ...result, status: 'error', reason: error instanceof CheckError ? error.code : 'unexpected_check_error', mayDispatch: false };
  }
  return finish(env, result, deps);
}

async function finish(env, result, deps) {
  try { await kvPut(env.WATCHDOG_STATE, 'latest', result); }
  catch { result = { ...result, status: 'error', reason: 'state_write_failed', mayDispatch: false }; }
  (deps.log || console.log)(JSON.stringify(result));
  return result;
}

export default {
  async scheduled(controller, env) { await runCheck(env); },
  async fetch(request, env) { return healthResponse(request, env); },
};

export async function healthResponse(request, env, now = new Date()) {
  const url = new URL(request.url);
  if (url.pathname !== '/health') return new Response('Not found', { status: 404 });
  if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
  let result, httpStatus = 200;
  try { result = await kvGet(env.WATCHDOG_STATE, 'latest'); }
  catch { result = { status: 'error', reason: 'state_read_failed' }; httpStatus = 503; }
  if (result === null) {
    result = { status: 'unknown', reason: 'no_check_recorded' }; httpStatus = 503;
  } else if (httpStatus === 200) {
    const checked = object(result) && typeof result.checkedAt === 'string' ? Date.parse(result.checkedAt) : NaN;
    if (!Number.isFinite(checked) || checked > now.getTime() + 60000) {
      result = { status: 'error', reason: 'invalid_health_timestamp' }; httpStatus = 503;
    } else if (now.getTime() - checked > 45 * 60000) {
      result = { ...result, lastStatus: result.status, status: 'stale', reason: 'last_check_stale',
        ageMinutes: Math.floor((now.getTime() - checked) / 60000) };
      httpStatus = 503;
    }
  }
  return new Response(request.method === 'HEAD' ? null : JSON.stringify(result), {
    status: httpStatus, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' },
  });
}
