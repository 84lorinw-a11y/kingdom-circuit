"""Regression contracts for the recurring jobs and their shared publication path."""
from pathlib import Path
import unittest
from scripts.replay_source_update import SOURCE_REPAIRS

ROOT = Path(__file__).resolve().parents[1]


class AutomationWorkflowTests(unittest.TestCase):
    def workflow(self, name):
        return (ROOT / '.github/workflows' / (name + '.yml')).read_text()

    def test_delayed_daily_scan_is_not_skipped_by_runner_clock(self):
        text = self.workflow('daily-full-show-scan-5am')
        self.assertIn('timezone: "America/Chicago"', text)
        self.assertIn('cron: "0 5 * * *"', text)
        self.assertNotIn('date +%H', text)
        self.assertIn('"schedule"', text)

    def test_source_refresh_replay_has_full_outputs_and_credentials(self):
        main = self.workflow('update-and-deploy')
        save = main.split('- name: Save refreshed event data')[1].split('- name: Check out pinned')[0]
        self.assertIn('event-history.json', save)
        self.assertIn('config/permanent-state-pages.json', save)
        self.assertIn('TICKETMASTER_API_KEY:', save)
        self.assertIn('--sync-checkout', save)
        website = self.workflow('artist-website-refresh').split('- name: Save discovered shows')[1]
        self.assertIn('TICKETMASTER_API_KEY:', website)
        # Replays must apply the same ordered source repairs as the original run.
        positions = [main.index('python scripts/' + script) for script in SOURCE_REPAIRS]
        self.assertEqual(positions, sorted(positions))

    def test_collector_completions_deploy_without_recursive_full_scan(self):
        main = self.workflow('update-and-deploy')
        self.assertIn('"Daily Bandsintown discovery"', main)
        self.assertIn('"Refresh official artist website shows"', main)
        self.assertIn('"Merge verified artist seed events"', main)
        self.assertIn('cancel-in-progress: false', main)
        for name in ('Add priority artist fallback calendars', 'Collect upcoming shows', 'Run expanded all-artist source scan', 'Save refreshed event data'):
            condition = main.split('- name: ' + name)[1].split('\n')[1]
            self.assertIn("github.event_name == 'schedule'", condition)
            self.assertIn("github.event_name == 'workflow_dispatch'", condition)
            self.assertNotIn("!= 'push'", condition)
        website = self.workflow('artist-website-refresh')
        self.assertIn("github.event.workflow_run.event == 'schedule'", website)
        self.assertIn("github.event.workflow_run.event == 'workflow_dispatch'", website)

    def test_all_active_source_writers_replay_instead_of_rebasing_generated_json(self):
        names = ('archive-event-history', 'artist-website-refresh', 'bandsintown-daily',
                 'capture-live-deploy-status', 'catalog-curation', 'ensure-verified-fall-shows',
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

    def test_browser_audit_matches_current_navigation_and_retains_failure_evidence(self):
        text = self.workflow('live-browser-retest')
        script = (ROOT / 'scripts/live_browser_retest.py').read_text()
        self.assertIn('if: always()', text)
        self.assertIn('actions/upload-artifact@v4', text)
        self.assertIn('Primary navigation', script)
        self.assertNotIn('menu-toggle', script)
        self.assertNotIn('menu-drawer', script)


if __name__ == '__main__':
    unittest.main()
