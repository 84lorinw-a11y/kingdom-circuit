# Automatic publication audits

Every normal publication runs two required checks in `Update and deploy show calendar`:

1. **Audit final publication artifact** runs after the final page changes and before `Upload Pages artifact`. It checks the completed `_site` and writes `_site/publication-manifest.json` only when the artifact passes. The release ID combines the saved, validated source commit, Actions run ID, and run attempt. A missing or malformed source commit stops publication.
2. **Verify exact published release** runs immediately after Pages deployment. It compares the live site against that build's local manifest. A live check failure makes the workflow fail even if Pages accepted the upload.

These checks run through one workflow for the nightly date update, morning full discovery, manual runs, and human pushes. Collection, archival, source saving, publication, and the final receipt share the `kingdom-circuit-pages` lock. Independent collector completion triggers and automatic legacy writers are retired. Legacy manual tools share the lock and cannot cancel a publication.

## Daily sequence and timing

| Local time | GitHub work |
| --- | --- |
| 00:15 America/Los_Angeles (normally 02:15 Central) | Archive before pruning, refresh dates from accepted data, validate, publish, verify. No source scan. |
| 04:17 America/Chicago | Archive the previous source; collect base sources, structured Bandsintown and expanded artist sources, official websites and seeds, then Eventbrite research; validate; save; build; publish; verify. |
| 04:47 America/Chicago | Same morning entrypoint, only when no morning attempt claimed this local day. An existing running, completed, failed, or interrupted attempt suppresses this fallback. |
| 06:00 America/Chicago | Existing Codex read-only monitor checks the workflow receipts and live site. Publication does not depend on Codex or the laptop. |

IANA timezone schedules follow daylight saving time. The main morning entry is off the busy hour and allows 103 minutes before the monitor, but that is headroom, not a completion guarantee. A delayed midnight refresh becomes a no-op if the morning full sequence already verified the current Pacific catalog date.

The planning job durably saves the daily claim in `daily-publication-status.json` before starting collectors. The final result job runs inside the same workflow lock, including on failure, and records stage outcomes plus the saved source SHA. The legacy `live-deploy-status.json` monitor contract remains available. A claim without a final receipt is interrupted/unfinished, not permission for another automatic scan. Explicit reviewed manual recovery remains possible; select `dates` to rebuild saved data without another source scan.

Official website omissions retain only previously accepted exact event identities. They are reported for review; omission alone is not cancellation. Eventbrite results remain a research queue, not unreviewed automatic event promotion. Collection receipts must be current and account for the current roster; blocked provider surfaces remain visible as limitations, not a claim that every website was readable.

Validated source saves use `--reuse-validated-output`. If main advanced, unchanged output paths preserve owner edits and unrelated changes survive; different edits to the same file stop publication for reconciliation. Offline normalization/tests may run, but a Git save race no longer triggers another network scan. No force-push or automatic conflict-side selection is used.

If Pages deploys successfully, publication URL history is saved even when the live check fails. This preserves the record of what was deployed without treating a failed live audit as successful verification.

If the first Pages deployment attempt fails, the workflow retries exactly once using the same accepted and uploaded artifact. It does not rerun collection, rebuild the site, or replace the artifact. The retry requires both a passing final audit and successful artifact upload; cancellation prevents a retry. A separate publication gate requires one deployment attempt to succeed before live verification can run. Failure of both attempts, or a later live audit failure, leaves the workflow failed.

## Evidence and failure handling

Open the deployment run in GitHub Actions. Its job summary records the build audit, both Pages attempt outcomes, the publication gate, and the live audit. The `publication-audit-<run>-<attempt>` artifact retains available JSON reports, readable summaries, and the expected manifest for 14 days, including when a required check fails. Existing calendar freshness evidence remains available separately.

Failures before source saving also retain a limited `source-failure-<run>-<attempt>` diagnostic. It contains only allowed public event identity fields from the three source feeds, excludes private and held records, and never copies URLs, addresses, configuration, raw errors, provider status files, or credentials. Earlier source/build/upload failures skip the Pages acceptance gate, so they are not mislabeled as failed deployment attempts.

A failed build audit stops upload and deployment. A failed live audit means the deployment needs investigation: inspect its report to distinguish propagation delays, the wrong release, and content failures. Do not rerun a deployment just to dismiss a failed audit; inspect the reported evidence and correct the cause. The final result job captures the overall outcome and links to the run. These workflows do not send messages or change notification preferences.

`Live SEO Audit` is now a manual, read-only check using the same live verifier. It fetches the currently published manifest and checks that release's listed files. This is useful for investigating the current site, but it does not independently prove that a particular Actions build deployed. Each normal deployment supplies its own expected manifest for that proof. The manual workflow retains its reports as Actions artifacts and does not write or force-push an audit branch.

## Local commands

After completing the production build and all page transformations:

```sh
python scripts/publication_audit.py --site _site \
  --release-id "$(git rev-parse HEAD)-local" \
  --report publication-audit.json --summary publication-audit.md

python scripts/verify_live_publication.py \
  --base-url https://kingdomcircuit.com \
  --manifest _site/publication-manifest.json \
  --report live-publication-audit.json --summary live-publication-audit.md
```

The second command is meaningful after that artifact has been deployed. For a read-only audit of the currently published release, omit `--manifest`. The build audit also accepts `--day YYYY-MM-DD` for controlled fixture checks; recurring publication uses its current date.

## Recovery and scheduling limits

`Recover verified November 7 Pages release` is retired. Its first step fails with a clear explanation and its Pages write permissions have been removed. The frozen November 7 manifest and offline recovery verifier remain historical evidence; they are not updated to claim that later checks ran on the old artifact. Use the current audited deployment workflow for a new release.

GitHub schedules may be delayed or dropped under service load. A saved claim proves a sequence started, not that publication finished. The 04:47 catch-up can recover a missing primary trigger, but both triggers use GitHub and cannot guarantee service availability. A normally queued or running job is not a failure. After two failed same-artifact Pages attempts, the workflow stops and retains evidence; it does not launch an unlimited retry, rescan, or separate recovery controller. See [GitHub's schedule limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
