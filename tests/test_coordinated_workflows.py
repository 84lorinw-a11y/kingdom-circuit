"""Check the production trigger graph and the lock shared by manual writers.

Read the actual workflow files without a YAML dependency. Only the block-style
trigger/concurrency syntax used here is supported; unfamiliar syntax fails the
contract rather than being treated as an absent trigger or permission.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github/workflows'
PUBLISHER = 'update-and-deploy.yml'
LOCK = {'group': 'kingdom-circuit-pages', 'cancel-in-progress': 'false', 'queue': 'max'}
MANUAL_SOURCE_TOOLS = {
    'archive-event-history.yml', 'artist-website-refresh.yml', 'bandsintown-daily.yml',
    'catalog-curation.yml', 'ensure-verified-fall-shows.yml', 'eventbrite-artist-scan.yml',
    'fix-hvo-event-link.yml', 'guard-deonte-hall-submission.yml',
    'guard-echo-nights-official.yml', 'merge-verified-artist-seeds.yml',
    'remove-tru-serva-las-cruces-false-match.yml', 'sep11-catalog-audit-guard.yml',
}


def section(text, key):
    """Return one root mapping block, refusing duplicate or inline definitions."""
    matches = list(re.finditer(r'^' + re.escape(key) + r':([^\n]*)\n', text, re.M))
    if len(matches) != 1 or matches[0][1].strip():
        raise AssertionError(f'Expected one block-style {key} definition')
    start = matches[0].end()
    end = re.search(r'^\S[^\n]*:', text[start:], re.M)
    return text[start:start + end.start()] if end else text[start:]


def mapping_fields(block):
    values = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'  ([\w-]+):(?:\s+(.*))?', line)
        if not match or match[1] in values:
            raise AssertionError('Unsupported or duplicate mapping field: ' + line)
        values[match[1]] = (match[2] or '').strip().strip('"\'')
    return values


def triggers(text):
    block = section(text, 'on')
    values = []
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line.startswith('    '):
            continue
        match = re.fullmatch(r'  ([\w-]+):\s*', line)
        if not match or match[1] in values:
            raise AssertionError('Unsupported or duplicate trigger: ' + line)
        values.append(match[1])
    if not values:
        raise AssertionError('Workflow has no recognized trigger')
    return set(values)


def schedules(text):
    block = section(text, 'on')
    match = re.search(r'^  schedule:\n(.*?)(?=^  \w|\Z)', block, re.M | re.S)
    if not match:
        return []
    entries = []
    for line in match[1].splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        cron = re.fullmatch(r'    - cron: ["\']([^"\']+)["\']', line)
        timezone = re.fullmatch(r'      timezone: ["\']([^"\']+)["\']', line)
        if cron:
            entries.append({'cron': cron[1]})
        elif timezone and entries and 'timezone' not in entries[-1]:
            entries[-1]['timezone'] = timezone[1]
        else:
            raise AssertionError('Unsupported schedule entry: ' + line)
    return entries


def can_write_or_dispatch(text):
    # Permission is sufficient: a newly added write-capable action must not
    # escape the trigger/lock checks merely because its command is unfamiliar.
    capability = re.search(r'^ +(?:contents|actions|pages): write\s*$', text, re.M)
    direct_write = re.search(r'git\s+(?:push|commit)\b|publish_automation_changes\.py|'
                             r'publish_url_state\.py|gh\s+workflow\s+run|/dispatches', text)
    return bool(capability or direct_write)


def named_step(text, name):
    match = re.search(r'^      - name: ' + re.escape(name) +
                      r'\n(.*?)(?=^      - |^  [\w-]+:|\Z)', text, re.M | re.S)
    if not match:
        raise AssertionError('Missing workflow step: ' + name)
    return match[1]


class CoordinatedWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflows = {p.name: p.read_text() for p in WORKFLOWS.iterdir()
                         if p.suffix in {'.yml', '.yaml'}}

    def test_only_publisher_has_automatic_write_or_dispatch_capability(self):
        writers = {name: text for name, text in self.workflows.items()
                   if can_write_or_dispatch(text)}
        self.assertIn(PUBLISHER, writers)
        self.assertTrue(MANUAL_SOURCE_TOOLS <= writers.keys())
        for name, text in writers.items():
            if name == PUBLISHER:
                continue
            with self.subTest(workflow=name):
                self.assertEqual(triggers(text), {'workflow_dispatch'})

    def test_every_manual_writer_queues_behind_the_full_publication_run(self):
        for name, text in self.workflows.items():
            if not can_write_or_dispatch(text):
                continue
            with self.subTest(workflow=name):
                self.assertEqual(mapping_fields(section(text, 'concurrency')), LOCK)
                # A job-level override must not introduce another lock or an
                # interruption policy hidden beneath the shared root lock.
                self.assertFalse(re.search(r'^ +concurrency:', text, re.M))

    def test_one_workflow_owns_date_primary_and_missing_start_schedules(self):
        owners = {name for name, text in self.workflows.items() if 'schedule' in triggers(text)}
        self.assertEqual(owners, {PUBLISHER})
        self.assertEqual(schedules(self.workflows[PUBLISHER]), [
            {'cron': '15 0 * * *', 'timezone': 'America/Los_Angeles'},
            {'cron': '17 4 * * *', 'timezone': 'America/Chicago'},
            {'cron': '47 4 * * *', 'timezone': 'America/Chicago'},
        ])

    def test_collector_completion_cannot_start_another_publication(self):
        self.assertNotIn('workflow_run', triggers(self.workflows[PUBLISHER]))
        for name in MANUAL_SOURCE_TOOLS:
            self.assertEqual(triggers(self.workflows[name]), {'workflow_dispatch'}, name)

    def test_old_dispatcher_is_manual_and_tru_serva_no_longer_redispatches(self):
        wrapper = self.workflows['daily-full-show-scan-5am.yml']
        self.assertEqual(triggers(wrapper), {'workflow_dispatch'})
        repair = self.workflows['remove-tru-serva-las-cruces-false-match.yml']
        self.assertNotRegex(repair, r'gh\s+workflow\s+run|/dispatches|actions: write')
        self.assertIn('python scripts/remove_false_tru_serva.py', repair)

    def test_receipt_compatibility_workflow_cannot_write_or_launch_work(self):
        receipt = self.workflows['capture-live-deploy-status.yml']
        self.assertEqual(triggers(receipt), {'workflow_dispatch'})
        self.assertEqual(mapping_fields(section(receipt, 'permissions')), {'contents': 'read'})
        self.assertFalse(can_write_or_dispatch(receipt))
        self.assertNotRegex(receipt, r'git\s+(?:push|commit)|publish_automation_changes|gh\s+workflow')

    def test_manual_guard_commands_are_retained(self):
        required = {
            'ensure-verified-fall-shows.yml': ['ensure_verified_fall_2026_shows.py', 'apply_miles_cj_fall_2026_repairs.py'],
            'guard-echo-nights-official.yml': ['apply_echo_nights_official.py'],
            'fix-hvo-event-link.yml': ['preserve_hvo_link.py'],
            'guard-deonte-hall-submission.yml': ['apply_deonte_hall_submission.py --submission-only'],
            'sep11-catalog-audit-guard.yml': ['enforce_sep11_catalog_audit.py', 'sync_verified_artist_registry.py', 'replay_source_update.py normalize'],
        }
        for name, commands in required.items():
            for command in commands:
                self.assertIn('python scripts/' + command, self.workflows[name], name)

    def test_independent_dispatch_is_opt_in_and_passes_expected_day_to_plan(self):
        text = self.workflows[PUBLISHER]
        inputs = section(text, 'on')
        self.assertRegex(inputs, r'automatic_fallback:\n[^\n]+\n        type: boolean\n        default: false')
        self.assertRegex(inputs, r'expected_day:\n[^\n]+\n        type: string')
        claim = named_step(text, 'Claim the daily sequence before collecting anything')
        for env, value in [('KC_AUTOMATIC_FALLBACK', 'inputs.automatic_fallback'),
                           ('KC_EXPECTED_DAY', 'inputs.expected_day'),
                           ('KC_REQUESTED_MODE', 'inputs.refresh_mode')]:
            self.assertIn(env + ': ${{ ' + value + ' }}', claim)
        self.assertIn('claim_required: ${{ steps.plan.outputs.claim_required }}', text)

    def test_both_automatic_entrypoints_persist_and_verify_the_same_pinned_claim(self):
        text = self.workflows[PUBLISHER]
        for name in ('Persist the daily claim before starting work',
                     'Verify this run owns the saved daily claim'):
            with self.subTest(step=name):
                step = named_step(text, name)
                self.assertIn("if: steps.plan.outputs.claim_required == 'true' && steps.plan.outputs.run == 'true'", step)
                self.assertNotIn("github.event_name == 'schedule'", step)
                self.assertIn('KC_MODE: ${{ steps.plan.outputs.mode }}', step)
                self.assertIn('KC_DAY: ${{ steps.plan.outputs.day }}', step)
        persist = named_step(text, 'Persist the daily claim before starting work')
        self.assertIn('--reuse-validated-output', persist)
        self.assertIn('--replay "python scripts/coordinated_schedule.py verify-claim"', persist)
        self.assertNotIn('--replay "python scripts/coordinated_schedule.py claim"', persist)
        self.assertIn('git show origin/main:daily-publication-status.json',
                      named_step(text, 'Verify this run owns the saved daily claim'))

    def test_failed_job_rerun_verifies_attempt_before_any_source_work(self):
        text = self.workflows[PUBLISHER]
        guard_name = 'Verify the daily claim again before source work'
        guard = named_step(text, guard_name)
        self.assertIn("if: needs.plan.outputs.claim_required == 'true'", guard)
        self.assertIn('KC_MODE: ${{ needs.plan.outputs.mode }}', guard)
        self.assertIn('KC_DAY: ${{ needs.plan.outputs.day }}', guard)
        self.assertIn('python scripts/coordinated_schedule.py verify-claim', guard)
        for step in ('Install pinned image verification backend',
                     'Archive existing bookings before any source replacement',
                     'Collect upcoming shows'):
            self.assertLess(text.index('- name: ' + guard_name), text.index('- name: ' + step))

    def test_skipped_automatic_attempt_never_replaces_the_publication_receipt(self):
        text = self.workflows[PUBLISHER]
        record = re.search(r'^  record-result:\n(.*)', text, re.M | re.S)[1]
        self.assertIn("if: ${{ always() && needs.plan.result == 'success' && needs.plan.outputs.run == 'true' }}", record)
        self.assertIn('KC_MODE: ${{ needs.plan.outputs.mode }}', record)
        self.assertIn('KC_DAY: ${{ needs.plan.outputs.day }}', record)


if __name__ == '__main__':
    unittest.main()
