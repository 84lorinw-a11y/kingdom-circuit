# Automatic publication audits

Every normal publication runs two required checks in `Update and deploy show calendar`:

1. **Audit final publication artifact** runs after the final page changes and before `Upload Pages artifact`. It checks the completed `_site` and writes `_site/publication-manifest.json` only when the artifact passes. The release ID combines the actual build checkout's Git commit, Actions run ID, and run attempt.
2. **Verify exact published release** runs immediately after Pages deployment. It compares the live site against that build's local manifest. A live check failure makes the workflow fail even if Pages accepted the upload.

These checks run for the nightly date update, the 5AM Central full discovery scan, manual runs, pushes, and successful collector follow-ups. Discovery behavior and scheduling are unchanged. The shared deployment queue continues to serialize publications; a delayed scheduled start is still allowed to run.

If Pages deploys successfully, publication URL history is saved even when the live check fails. This preserves the record of what was deployed without treating a failed live audit as successful verification.

If the first Pages deployment attempt fails, the workflow retries exactly once using the same accepted and uploaded artifact. It does not rerun collection, rebuild the site, or replace the artifact. The retry requires both a passing final audit and successful artifact upload; cancellation prevents a retry. A separate publication gate requires one deployment attempt to succeed before live verification can run. Failure of both attempts, or a later live audit failure, leaves the workflow failed.

## Evidence and failure handling

Open the deployment run in GitHub Actions. Its job summary records the build audit, both Pages attempt outcomes, the publication gate, and the live audit. The `publication-audit-<run>-<attempt>` artifact retains available JSON reports, readable summaries, and the expected manifest for 14 days, including when a required check fails. Existing calendar freshness evidence remains available separately.

A failed build audit stops upload and deployment. A failed live audit means the deployment needs investigation: inspect its report to distinguish propagation delays, the wrong release, and content failures. Do not rerun a deployment just to dismiss a failed audit; inspect the reported evidence and correct the cause. The existing deployment-result workflow captures the overall outcome and links to the run. These workflows do not send messages or change notification preferences.

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

GitHub schedules may be delayed or dropped under service load. The dispatcher starting successfully does not prove that publication finished. Existing schedules remain 5AM America/Chicago for full discovery and 00:15 America/Los_Angeles for date maintenance. The publication gates validate runs that execute; they cannot guarantee that GitHub starts every scheduled run. See [GitHub's schedule limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
