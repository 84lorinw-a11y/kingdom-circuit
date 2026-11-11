# Independent publication watchdog

Cloudflare checks every 15 minutes; GitHub remains the sole collector, validator,
and publisher. This Worker never edits shows, archives, artist verification,
repository source, or production assets.

## Recovery policy

- Date fallback: 00:45–02:15 America/Los_Angeles, inclusive.
- Full discovery fallback: 05:15–07:15 America/Chicago, inclusive.
- Outside those windows: health observation only. UTC cron plus IANA local-time
  checks automatically handles daylight saving changes.
- Any active publication run is left alone. Every recorded same-day/mode
  attempt blocks another automatic attempt, even after failure or interruption.
- A verified full publication can satisfy date refresh. A current catalog alone
  cannot prove today's discovery completed.
- Missing/malformed receipts, incomplete run lists, API failures, or unavailable
  state storage fail closed. The Worker records a dispatch intent before POST;
  an ambiguous response is never blindly retried. The GitHub workflow's durable
  claim and existing publication concurrency provide the final race guard.
- Failed checks are recorded for the existing 6 AM monitor to report. No email,
  Slack, or third-party notification recipients are added.

## Deployment

Use the dedicated `kingdom-circuit-publication-watchdog` Worker, independent of
Apollo and the Kingdom Circuit site. Upload `worker.mjs` as an ES module.

Production was activated on November 11, 2026. The dedicated KV binding,
15-minute Cron Trigger, `GITHUB_TOKEN` secret, and `ENABLED=true` setting are
configured. The committed Wrangler configuration preserves this active state
on future deployments. A newly created environment must follow the setup
checks below before enabling recovery.

1. Create/bind a dedicated KV namespace as `WATCHDOG_STATE`.
2. Add `GITHUB_TOKEN` as a secret: fine-grained token restricted to
   `84lorinw-a11y/kingdom-circuit`, Actions write (plus implicit metadata read).
   A suitably restricted GitHub App installation token is also supported.
   Public receipt/catalog reads are unauthenticated and do not require Contents
   permission. The token is only transmitted to GitHub's Actions API.
3. Keep `ENABLED=false` until the guarded GitHub dispatch inputs are live and
   the secret, storage binding, and tests are verified.
4. Add Cron Trigger `*/15 * * * *` (UTC); enable Workers logs.
5. Set `ENABLED=true` only when ready. Inspect the next actual cron result and
   `/health`; a newly registered trigger can take 15 minutes to propagate.

`wrangler.jsonc` contains the active production setting and the dedicated
account and KV namespace IDs returned by Cloudflare. Never commit tokens.
Keep an intentional pause explicit: set `ENABLED=false` in the deployed
environment and the deployment configuration together.

The repository-scoped GitHub credential expires on November 11, 2027. Its
nonsecret expiry and activation evidence belong in
`Kingdom Circuit Audits/2026-11-11/independent-publication-watchdog/setup-status.json`.
The daily monitor should warn during the final 30 days so the secret can be
renewed before expiry. Update that receipt after renewal; never include the
credential value in source, receipts, or logs.

`GET /health` returns the last stored result; it makes no external requests.
All other HTTP paths return 404 and non-read methods on health return 405.
Check `checkedAt`: old status is not proof the scheduler is still running.
The endpoint reports HTTP 503 with `status: stale` and the stored `lastStatus`
if the last check is more than 45 minutes old; missing or invalid state also
returns HTTP 503. These HTTP checks never write state or dispatch anything.
The public health record contains operational timestamps, count and reason
codes, never credentials or source response bodies.

## Local tests

```sh
node --test ops/publication-watchdog/worker.test.mjs
```

Tests use injected fetch/time/storage and never contact GitHub or Cloudflare.
They cover DST/windows, failed and unfinished claims, queued jobs, malformed
receipts, rejected/unknown POST outcomes, missing credentials, storage failures,
once-only dispatch intent, and the read-only HTTP endpoint.
