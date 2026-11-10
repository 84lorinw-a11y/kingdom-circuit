import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from scripts.publish_automation_changes import git, publish


class AutomationPublicationTests(unittest.TestCase):
    def test_refreshed_source_is_validated_before_it_is_saved(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/update-and-deploy.yml').read_text()
        correction = workflow.index('- name: Preserve October 3 concert corrections and artist identity')
        validation = workflow.index('- name: Validate refreshed source before publication')
        publication = workflow.index('- name: Save refreshed event data')
        self.assertLess(correction, validation)
        self.assertLess(validation, publication)
        self.assertIn("python -m unittest discover -s tests -p 'test_*.py' -q", workflow[validation:publication])

    def test_manual_full_replay_restores_curated_artist_seeds_before_final_validation(self):
        from scripts import replay_source_update as replay
        from scripts.apply_verified_show_artwork import patch_event, BY_ID
        event = {}
        calls = []

        def source_step(script):
            calls.append(script)
            if script == 'merge_artist_website_events.py':
                event.update(id='manual:808-beezy-bandsintown-108856031',
                             startDate='2026-11-02', image='old-artist-portrait.webp',
                             firstSeen='2026-09-02T14:46:37Z')
            if script == 'apply_sep26_source_corrections.py':
                patch_event(event)

        with patch.object(sys, 'argv', ['replay_source_update.py', 'full']), \
             patch.object(replay, 'run', side_effect=source_step), \
             patch.object(replay, 'Path'), patch.object(replay.subprocess, 'run'):
            replay.main()

        self.assertEqual(BY_ID['808-beezy-bandsintown-108856031']['image'], event['image'])
        self.assertEqual('2026-09-02T14:46:37Z', event['firstSeen'])
        self.assertLess(calls.index('scan_all_artist_sources.py'), calls.index('merge_artist_website_events.py'))
        self.assertTrue(all(calls.index('merge_artist_website_events.py') < len(calls) - 1 - calls[::-1].index(step)
                            for step in replay.SOURCE_REPAIRS))

    def test_full_workflow_restores_seeds_before_approved_corrections(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/update-and-deploy.yml').read_text()
        merge = workflow.index('python scripts/merge_artist_website_events.py')
        self.assertLess(workflow.index('python scripts/scan_all_artist_sources.py'), merge)
        normalize = workflow.index('python scripts/replay_source_update.py normalize', merge)
        self.assertLess(merge, normalize)
        self.assertLess(normalize, workflow.index('- name: Validate refreshed source before publication'))
        # Reconcile duplicate provider identities before the seed merger, which
        # deliberately rejects losing a curated seed to a conflicting identity.
        self.assertLess(workflow.index('python scripts/apply_sep26_source_corrections.py'), merge)
        # A repository race reuses the validated source result and runs local
        # corrections/tests; it must not start another full network collection.
        save = workflow.split('- name: Save refreshed event data', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('--reuse-validated-output', save)
        self.assertIn('--replay "python scripts/replay_source_update.py normalize"', save)
        self.assertNotIn('replay_source_update.py full', save)

    def setup_repo(self, directory):
        base = Path(directory)
        remote, owner, bot = [base / n for n in ('remote.git', 'owner', 'bot')]
        subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(remote)], check=True, capture_output=True)
        subprocess.run(['git', 'clone', str(remote), str(owner)], check=True, capture_output=True)
        for key,value in [('user.name','Test owner'),('user.email','test@example.test')]: git(owner,'config',key,value)
        (owner / 'events.json').write_text('{"owner": "original", "bot": 0}\n')
        (owner / 'repair.py').write_text("import json\nfrom pathlib import Path\np=Path('events.json')\nv=json.loads(p.read_text()); v['bot']=1\np.write_text(json.dumps(v)+'\\n')\n")
        git(owner,'add','.'); git(owner,'commit','-m','fixture'); git(owner,'push','origin','main')
        subprocess.run(['git', 'clone', str(remote), str(bot)], check=True, capture_output=True)
        return remote, owner, bot

    def test_race_recomputes_same_json_without_losing_owner_changes_or_resetting_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, owner, bot = self.setup_repo(directory)
            subprocess.run([sys.executable,'repair.py'],cwd=bot,check=True)
            before = git(bot,'rev-parse','HEAD').stdout
            def competing_push(attempt, work):
                if attempt == 0:
                    (owner / 'events.json').write_text('{"owner": "new confirmed show", "bot": 0}\n')
                    git(owner,'add','.'); git(owner,'commit','-m','owner update'); git(owner,'push','origin','main')
            with patch('scripts.publish_automation_changes.time.sleep'):
                sha = publish(bot,['events.json'],[f'{sys.executable} repair.py'],'Bot update',before_push=competing_push)
            result = json.loads(git(remote,'show',sha+':events.json').stdout)
            self.assertEqual({'owner':'new confirmed show','bot':1},result)
            self.assertEqual(before,git(bot,'rev-parse','HEAD').stdout)
            self.assertEqual({'owner':'original','bot':1},json.loads((bot/'events.json').read_text()))
            self.assertEqual(1,git(bot,'worktree','list','--porcelain').stdout.count('worktree '))

    def test_unlisted_change_and_local_sync_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            _,_,bot=self.setup_repo(directory)
            (bot/'repair.py').write_text('changed unexpectedly')
            with self.assertRaisesRegex(RuntimeError,'Unlisted tracked changes'):
                publish(bot,['events.json'],['python repair.py'],'Do not publish')
            with patch.dict(os.environ,{},clear=True), self.assertRaisesRegex(RuntimeError,'disposable'):
                publish(bot,['events.json'],['python repair.py'],'Do not publish',sync=True)

    def test_no_change_does_not_create_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            remote,_,bot=self.setup_repo(directory)
            before=git(remote,'rev-parse','main').stdout.strip()
            self.assertEqual(before,publish(bot,['events.json'],['python repair.py'],'No change'))

    def setup_coverage_repo(self, directory, report=None):
        remote, owner, bot = self.setup_repo(directory)
        report = report if report is not None else {
            'policyVersion': 7, 'generatedAt': '2026-11-06T23:34:10Z',
            'highRiskArtists': [{'artist': 'Example', 'failed': True}],
            'mediumRiskArtists': [], 'summary': {'count': 1},
        }
        original = json.dumps(report, indent=2) + '\n'
        (owner/'coverage-gaps.json').write_text(original)
        git(owner, 'add', 'coverage-gaps.json'); git(owner, 'commit', '-m', 'Coverage baseline')
        git(owner, 'push', 'origin', 'main'); git(bot, 'pull', '--ff-only')
        return remote, owner, bot, report, original

    def test_timestamp_only_coverage_does_not_commit_or_change_user_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, _, bot, report, original = self.setup_coverage_repo(directory)
            report['generatedAt'] = '2026-11-07T14:15:00Z'
            generated = json.dumps(report, indent=2) + '\n'
            (bot/'coverage-gaps.json').write_text(generated)
            before = git(remote, 'rev-parse', 'main').stdout.strip()
            sha = publish(bot, ['coverage-gaps.json'], [f'{sys.executable} repair.py'], 'Coverage refresh')
            self.assertEqual(before, sha)
            self.assertEqual(before, git(remote, 'rev-parse', 'main').stdout.strip())
            self.assertEqual(original, git(remote, 'show', sha + ':coverage-gaps.json').stdout)
            self.assertEqual(generated, (bot/'coverage-gaps.json').read_text())
            self.assertEqual(1, git(bot, 'worktree', 'list', '--porcelain').stdout.count('worktree '))

    def test_meaningful_coverage_changes_keep_new_timestamp_and_exact_output(self):
        variants = [
            {'highRiskArtists': [{'artist': 'New confirmed risk', 'failed': True}]},
            {'summary': {'count': 2}},
            {'summary': {'count': True}},  # Python equality must not hide a JSON type change.
            {'policyVersion': 8},
            {'newField': 'review required'},
        ]
        for change in variants:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                remote, _, bot, report, _ = self.setup_coverage_repo(directory)
                report.update(change, generatedAt='2026-11-07T14:15:00Z')
                generated = json.dumps(report, indent=2) + '\n'
                (bot/'coverage-gaps.json').write_text(generated)
                sha = publish(bot, ['coverage-gaps.json'], [f'{sys.executable} repair.py'], 'Changed coverage')
                self.assertEqual(generated, git(remote, 'show', sha + ':coverage-gaps.json').stdout)

    def test_timestamp_suppression_does_not_suppress_other_allowlisted_output(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, _, bot, report, original = self.setup_coverage_repo(directory)
            report['generatedAt'] = '2026-11-07T14:15:00Z'
            (bot/'coverage-gaps.json').write_text(json.dumps(report) + '\n')
            changed_events = '{"owner":"original","bot":1}\n'
            (bot/'events.json').write_text(changed_events)
            sha = publish(bot, ['coverage-gaps.json', 'events.json'], [f'{sys.executable} repair.py'], 'Actual source update')
            self.assertEqual(original, git(remote, 'show', sha + ':coverage-gaps.json').stdout)
            self.assertEqual(changed_events, git(remote, 'show', sha + ':events.json').stdout)
            self.assertEqual('events.json', git(remote, 'diff-tree', '--no-commit-id', '--name-only', '-r', sha).stdout.strip())

    def test_invalid_or_non_report_coverage_is_never_silently_normalized(self):
        values = ['{broken JSON', '[]\n', '{"generatedAt":"not a timestamp","summary":1}\n',
                  '{"generatedAt":"2026-11-07T14:15:00Z","generatedAt":"2026-11-07T15:00:00Z"}\n']
        for generated in values:
            with self.subTest(generated=generated), tempfile.TemporaryDirectory() as directory:
                remote, _, bot, _, _ = self.setup_coverage_repo(directory)
                (bot/'coverage-gaps.json').write_text(generated)
                sha = publish(bot, ['coverage-gaps.json'], [f'{sys.executable} repair.py'], 'Caller-validated coverage')
                self.assertEqual(generated, git(remote, 'show', sha + ':coverage-gaps.json').stdout)

    def test_first_coverage_report_and_missing_baseline_timestamp_are_preserved(self):
        for has_baseline in (False, True):
            with self.subTest(has_baseline=has_baseline), tempfile.TemporaryDirectory() as directory:
                if has_baseline:
                    remote, _, bot, _, _ = self.setup_coverage_repo(directory, report={'summary': {'count': 1}})
                else:
                    remote, _, bot = self.setup_repo(directory)
                generated = '{"summary":{"count":1},"generatedAt":"2026-11-07T14:15:00Z"}\n'
                (bot/'coverage-gaps.json').write_text(generated)
                sha = publish(bot, ['coverage-gaps.json'], [f'{sys.executable} repair.py'], 'First coverage timestamp')
                self.assertEqual(generated, git(remote, 'show', sha + ':coverage-gaps.json').stdout)

    def test_unlisted_timestamp_only_report_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, _, bot, report, _ = self.setup_coverage_repo(directory)
            before = git(remote, 'rev-parse', 'main').stdout
            report['generatedAt'] = '2026-11-07T14:15:00Z'
            (bot/'coverage-gaps.json').write_text(json.dumps(report) + '\n')
            with self.assertRaisesRegex(RuntimeError, 'Unlisted tracked changes'):
                publish(bot, ['events.json'], [f'{sys.executable} repair.py'], 'Unlisted report')
            self.assertEqual(before, git(remote, 'rev-parse', 'main').stdout)

    def test_concurrent_main_change_still_replays_and_preserves_owner_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, owner, bot, report, _ = self.setup_coverage_repo(directory)
            replay = """import json
from pathlib import Path
p=Path('coverage-gaps.json')
v=json.loads(p.read_text()); v['generatedAt']='2026-11-07T14:15:00Z'
p.write_text(json.dumps(v)+'\\n')
p=Path('events.json'); v=json.loads(p.read_text()); v['bot']=1
p.write_text(json.dumps(v)+'\\n')
"""
            (owner/'coverage-replay.py').write_text(replay)
            git(owner, 'add', 'coverage-replay.py'); git(owner, 'commit', '-m', 'Verified replay')
            git(owner, 'push', 'origin', 'main'); git(bot, 'pull', '--ff-only')
            subprocess.run([sys.executable, 'coverage-replay.py'], cwd=bot, check=True)
            local_report = (bot/'coverage-gaps.json').read_text()
            before_checkout = git(bot, 'rev-parse', 'HEAD').stdout
            def competing_push(attempt, work):
                if attempt == 0:
                    report['highRiskArtists'].append({'artist': 'Owner confirmed risk', 'failed': True})
                    report['generatedAt'] = '2026-11-07T14:16:00Z'
                    (owner/'coverage-gaps.json').write_text(json.dumps(report, indent=2) + '\n')
                    (owner/'events.json').write_text('{"owner":"new confirmed show","bot":0}\n')
                    git(owner, 'add', '.'); git(owner, 'commit', '-m', 'Meaningful owner change'); git(owner, 'push', 'origin', 'main')
            with patch('scripts.publish_automation_changes.time.sleep'):
                sha = publish(bot, ['coverage-gaps.json', 'events.json'], [f'{sys.executable} coverage-replay.py'],
                              'Refreshed source', before_push=competing_push)
            self.assertEqual(report, json.loads(git(remote, 'show', sha + ':coverage-gaps.json').stdout))
            self.assertEqual({'owner': 'new confirmed show', 'bot': 1}, json.loads(git(remote, 'show', sha + ':events.json').stdout))
            self.assertEqual(local_report, (bot/'coverage-gaps.json').read_text())
            self.assertEqual(before_checkout, git(bot, 'rev-parse', 'HEAD').stdout)


if __name__ == '__main__': unittest.main()
