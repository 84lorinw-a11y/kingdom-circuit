"""Regression contracts for the recurring jobs and their shared publication path."""
from pathlib import Path
import re
import shlex
import unittest
from scripts.replay_source_update import SOURCE_REPAIRS

ROOT = Path(__file__).resolve().parents[1]


def step(text, name):
    """Read one named step, stopping at the next step or job."""
    matches = list(re.finditer(r'^      - name: ' + re.escape(name) + r'$', text, re.M))
    if len(matches) != 1:
        raise AssertionError('Expected one workflow step: ' + name)
    body = text[matches[0].end():]
    end = re.search(r'^(?:      - |  [\w-]+:)', body, re.M)
    return body[:end.start()] if end else body


def field(block, name, indentation=8):
    match = re.search(r'^' + ' ' * indentation + re.escape(name) + r': (.+)$', block, re.M)
    return match[1] if match else None


def runs_in_mode(block, discovery, *, previous_failure=False):
    """Evaluate the source steps' actual limited condition, failing on new syntax."""
    expression = field(block, 'if')
    if expression is None:
        return not previous_failure
    if expression != "steps.refresh-mode.outputs.discovery == 'true'":
        raise AssertionError('Unsupported source-step condition: ' + expression)
    return discovery and not previous_failure


class AutomationWorkflowTests(unittest.TestCase):
    def workflow(self, name):
        return (ROOT / '.github/workflows' / (name + '.yml')).read_text()

    def test_scheduled_source_mode_uses_the_schedule_not_runner_clock(self):
        main = self.workflow('update-and-deploy')
        selection = step(main, 'Choose independent date maintenance or full discovery')
        claim = step(main, 'Claim the daily sequence before collecting anything')
        for block in (selection, claim):
            self.assertEqual(field(block, 'KC_SCHEDULE', 10), '${{ github.event.schedule }}')
            self.assertIsNone(field(block, 'if'))
            self.assertNotRegex(block, r'date\s+.*%H')
        self.assertIn('python scripts/calendar_maintenance.py --mode', selection)

    def test_source_refresh_replay_has_full_outputs_and_credentials(self):
        main = self.workflow('update-and-deploy')
        save = step(main, 'Save refreshed event data')
        outputs = shlex.split(save.split('        run: |', 1)[1].replace('\\\n', ' '))
        for path in ('event-history.json', 'config/permanent-state-pages.json',
                     'artist-website-events.json', 'artist-website-status.json',
                     'config/verified-artist-websites.json', 'config/verified-artist-registry-updates.json',
                     'config/artist-website-seed-events.json', 'eventbrite-scan-status.json',
                     'eventbrite-scan-candidates.json', 'data/verified-false-matches.json'):
            self.assertIn(path, outputs)
        # The expanded scan delegates to the REST collector, which also writes
        # these two reports even when it discovers no additional shows.
        self.assertIn('bandsintown-status.json', save)
        self.assertIn('bandsintown-candidates.json', save)
        self.assertIn('TICKETMASTER_API_KEY:', save)
        self.assertIn('--sync-checkout', save)
        self.assertIn('--reuse-validated-output', outputs)
        replays = [outputs[index + 1] for index, arg in enumerate(outputs) if arg == '--replay']
        self.assertEqual(replays, ['python scripts/replay_source_update.py normalize',
                                  'python -m unittest discover -s tests -p test_*.py -q'])
        website = self.workflow('artist-website-refresh').split('- name: Save discovered shows')[1]
        self.assertIn('TICKETMASTER_API_KEY:', website)
        self.assertIn('event-history.json', website)
        self.assertIn('config/permanent-state-pages.json', website)
        whole_website = self.workflow('artist-website-refresh')
        self.assertLess(whole_website.index('python scripts/merge_artist_website_events.py'), whole_website.index('python scripts/replay_source_update.py normalize'))
        self.assertLess(whole_website.index('python scripts/replay_source_update.py normalize'), whole_website.index('- name: Run production tests'))
        for name in ('catalog-curation', 'ensure-verified-fall-shows'):
            self.assertIn('event-history.json', self.workflow(name))
        # Replays must apply the same ordered source repairs as the original run.
        repairs = main.split('- name: Apply curated catalog policy and coverage audit')[1].split('- name: Validate refreshed source before publication')[0]
        actual = re.findall(r'^\s*(?:run: )?python scripts/(.+)$', repairs, re.M)
        # Compare the full sequence, including the deliberately repeated audit
        # around registry sync; first-index checks miss a reversed duplicate.
        self.assertEqual(actual[:len(SOURCE_REPAIRS)], SOURCE_REPAIRS)

    def test_reviewed_information_replays_before_initial_tests_and_after_repairs(self):
        main = self.workflow('update-and-deploy')
        command = 'python scripts/apply_verified_show_information.py'
        initial = main.split('- name: Apply confirmed private admission before validation')[1].split('- name: Run all automated tests')[0]
        self.assertIn(command, initial)
        self.assertLess(initial.index('python scripts/private_events.py'), initial.index(command))
        self.assertNotIn('if:', initial)
        later = main.split('- name: Preserve October 3 concert corrections and artist identity')[1].split('- name: Validate refreshed source before publication')[0]
        self.assertLess(later.index('python scripts/apply_oct3_concert_corrections.py'), later.index(command))
        replay = later.split('- name: Restore reviewed missing show information')[1].split('\n      - name:', 1)[0]
        self.assertIn(command, replay)
        self.assertNotIn('if:', replay)
        self.assertEqual(main.count(command), 2)

    def test_only_full_mode_collects_but_both_modes_archive_validate_and_save(self):
        main = self.workflow('update-and-deploy')
        discovery_steps = ('Add priority artist fallback calendars', 'Collect upcoming shows',
                           'Run expanded all-artist source scan',
                           'Collect official websites while preserving accepted missing bookings',
                           'Scan Eventbrite for every tracked artist as a review queue')
        daily_steps = ('Archive existing bookings before any source replacement',
                       'Restore verified artist website seeds after full discovery',
                       'Archive reconciled bookings and preserve reviewed corrections',
                       'Validate refreshed source before publication', 'Save refreshed event data')
        for name in discovery_steps + daily_steps:
            block = step(main, name)
            with self.subTest(step=name):
                self.assertTrue(runs_in_mode(block, True))
                self.assertEqual(runs_in_mode(block, False), name in daily_steps)
                self.assertFalse(runs_in_mode(block, True, previous_failure=True))
                self.assertFalse(runs_in_mode(block, False, previous_failure=True))
        self.assertLess(main.index('- name: ' + daily_steps[0]),
                        main.index('- name: Collect upcoming shows'))
        self.assertLess(main.index('- name: ' + daily_steps[2]),
                        main.index('- name: Validate refreshed source before publication'))

    def test_reusable_source_writers_replay_instead_of_rebasing_generated_json(self):
        names = ('archive-event-history', 'artist-website-refresh', 'bandsintown-daily',
                 'catalog-curation', 'ensure-verified-fall-shows',
                 'eventbrite-artist-scan', 'fix-hvo-event-link', 'guard-deonte-hall-submission',
                 'guard-echo-nights-official', 'merge-verified-artist-seeds',
                 'remove-tru-serva-las-cruces-false-match', 'sep11-catalog-audit-guard', 'update-and-deploy')
        for name in names:
            with self.subTest(workflow=name):
                text = self.workflow(name)
                self.assertIn('scripts/publish_automation_changes.py', text)
                self.assertIn('--replay ', text)
                self.assertNotIn('git pull --rebase', text)
                self.assertNotIn('git push --force', text)

    def test_pages_rerun_selects_only_its_own_uploaded_artifact(self):
        text = self.workflow('update-and-deploy')
        upload = text.split('- name: Upload Pages artifact')[1].split('- name:')[0]
        deploy = text.split('- name: Deploy to GitHub Pages')[1].split('- name:')[0]
        upload_name = next(line.strip().split(': ', 1)[1] for line in upload.splitlines()
                           if line.strip().startswith('name: '))
        deploy_name = next(line.strip().split(': ', 1)[1] for line in deploy.splitlines()
                           if line.strip().startswith('artifact_name: '))
        self.assertEqual(upload_name, deploy_name)
        self.assertIn('${{ github.run_id }}', upload_name)
        self.assertIn('${{ github.run_attempt }}', upload_name)
        first = upload_name.replace('${{ github.run_id }}', '123').replace('${{ github.run_attempt }}', '1')
        retry = deploy_name.replace('${{ github.run_id }}', '123').replace('${{ github.run_attempt }}', '2')
        self.assertNotEqual(first, retry)

    def test_browser_audit_matches_current_navigation_and_retains_failure_evidence(self):
        text = self.workflow('live-browser-retest')
        script = (ROOT / 'scripts/live_browser_retest.py').read_text()
        self.assertIn('if: always()', text)
        self.assertIn('actions/upload-artifact@v4', text)
        self.assertIn('Primary navigation', script)
        self.assertNotIn('menu-toggle', script)
        self.assertNotIn('menu-drawer', script)

    def test_skipped_browser_followups_cannot_cancel_active_checks(self):
        browser = self.workflow('live-browser-retest')
        group = next(line for line in browser.splitlines() if 'group:' in line)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", group)
        self.assertIn("if: github.event_name != 'workflow_run' || github.event.workflow_run.conclusion == 'success'", browser)

    def test_result_receipt_waits_for_publisher_and_records_failures_inside_its_lock(self):
        main = self.workflow('update-and-deploy')
        receipt = main.split('\n  record-result:\n', 1)[1]
        self.assertEqual(field(receipt, 'needs', 4), '[plan, update-and-deploy]')
        self.assertEqual(field(receipt, 'if', 4),
                         "${{ always() && needs.plan.result == 'success' && needs.plan.outputs.run == 'true' }}")
        self.assertNotRegex(receipt, re.compile(r'^ +concurrency:', re.M))
        save = step(main, 'Save the result while still holding the publication lock')
        self.assertEqual(field(save, 'KC_RESULT', 10), '${{ needs.update-and-deploy.result }}')
        for stage in ('collection', 'source_save', 'source_sha', 'build', 'deployment', 'live', 'freshness'):
            self.assertEqual(field(save, 'KC_' + stage.upper(), 10),
                             '${{ needs.update-and-deploy.outputs.' + stage + ' }}')
        self.assertIn('python scripts/coordinated_schedule.py record', save)
        self.assertIn('daily-publication-status.json live-deploy-status.json', save)


if __name__ == '__main__':
    unittest.main()
