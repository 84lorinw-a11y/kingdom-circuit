"""Reuse validated collection bytes across real Git races without recollecting."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.publish_automation_changes import git, publish
from scripts import publish_automation_changes as publication


class ValidatedSourcePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote, self.owner, self.bot = [self.root / name for name in ('remote.git', 'owner', 'bot')]
        subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(self.remote)], check=True, capture_output=True)
        subprocess.run(['git', 'clone', str(self.remote), str(self.owner)], check=True, capture_output=True)
        git(self.owner, 'config', 'user.name', 'Fixture owner')
        git(self.owner, 'config', 'user.email', 'fixture@example.test')
        self.rows = [{'id': 'show-one', 'title': 'Confirmed title', 'startDate': '2099-11-10',
                      'city': 'Austin', 'state': 'TX', 'country': 'US'}]
        self.put(self.owner, 'events.json', self.rows)
        self.put(self.owner, 'receipt.json', {'day': 'old', 'owner': 'original'})
        (self.owner / 'notes.txt').write_text('Original owner note\n')
        (self.owner / 'offline.py').write_text(
            "import json, sys\nfrom pathlib import Path\n"
            "result = {name: json.loads(Path(name).read_text()) for name in ['events.json', 'receipt.json']}\n"
            "with Path(sys.argv[1]).open('a') as output: output.write(json.dumps(result) + '\\n')\n")
        self.commit_owner('Initial source')
        subprocess.run(['git', 'clone', str(self.remote), str(self.bot)], check=True, capture_output=True)
        self.trace = self.root / 'offline-checks.jsonl'
        self.command = shlex.join([sys.executable, 'offline.py', str(self.trace)])
        self.paths = ['events.json', 'receipt.json']

    def put(self, root, name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + '\n')

    def commit_owner(self, message):
        git(self.owner, 'add', '.')
        git(self.owner, 'commit', '-m', message)
        git(self.owner, 'push', 'origin', 'main')
        return git(self.owner, 'rev-parse', 'HEAD').stdout.strip()

    def remote_json(self, path, revision='main'):
        return json.loads(git(self.remote, 'show', revision + ':' + path).stdout)

    def collected(self):
        rows = [dict(self.rows[0], title='New verified source title')]
        self.put(self.bot, 'events.json', rows)
        return rows

    def reuse(self, **kwargs):
        with patch('scripts.publish_automation_changes.time.sleep'):
            return publish(self.bot, self.paths, [self.command], 'Save validated collection',
                           reuse_validated_output=True, **kwargs)

    def test_initial_validated_output_is_saved_without_running_replay(self):
        expected = self.collected()
        self.reuse()
        self.assertEqual(expected, self.remote_json('events.json'))
        self.assertFalse(self.trace.exists(), 'The initial result has already been validated')

    def test_cli_exports_saved_source_sha_without_overwriting_other_step_outputs(self):
        output = self.root / 'github-output'
        output.write_text('prior=value\n')
        sha = 'a' * 40
        with patch.object(sys, 'argv', ['publish_automation_changes.py', '--message', 'Fixture',
                '--reuse-validated-output', '--replay', 'python offline.py', 'events.json']), \
             patch.dict(os.environ, {'GITHUB_OUTPUT': str(output)}), \
             patch.object(publication, 'publish', return_value=sha) as saved:
            publication.main()
        self.assertTrue(saved.call_args.kwargs['reuse_validated_output'])
        self.assertEqual('prior=value\nvalidated_source_sha=' + sha + '\n', output.read_text())

    def test_real_push_race_preserves_unrelated_owner_files_and_unchanged_receipt(self):
        expected = self.collected()
        original_head = git(self.bot, 'rev-parse', 'HEAD').stdout

        def competing_push(attempt, _work):
            if attempt == 0:
                self.put(self.owner, 'receipt.json', {'day': 'today', 'owner': 'new evidence'})
                (self.owner / 'notes.txt').write_text('New confirmed owner note\n')
                self.commit_owner('Owner evidence arrived during collection save')

        result = self.reuse(before_push=competing_push)
        self.assertEqual(expected, self.remote_json('events.json', result))
        self.assertEqual({'day': 'today', 'owner': 'new evidence'}, self.remote_json('receipt.json', result))
        self.assertEqual('New confirmed owner note\n', git(self.remote, 'show', result + ':notes.txt').stdout)
        checks = [json.loads(line) for line in self.trace.read_text().splitlines()]
        self.assertEqual(1, len(checks), 'Only offline validation runs on the new main')
        self.assertEqual(expected, checks[0]['events.json'])
        self.assertEqual('today', checks[0]['receipt.json']['day'])
        self.assertEqual(original_head, git(self.bot, 'rev-parse', 'HEAD').stdout)
        self.assertEqual(expected, json.loads((self.bot / 'events.json').read_text()))
        self.assertEqual(1, git(self.bot, 'worktree', 'list', '--porcelain').stdout.count('worktree '))

    def test_same_record_changes_reject_even_when_different_fields_could_text_merge(self):
        self.collected()
        owner_rows = [dict(self.rows[0], city='Owner-confirmed Dallas')]
        self.put(self.owner, 'events.json', owner_rows)
        owner_sha = self.commit_owner('Owner corrected the same source record')
        with self.assertRaisesRegex(RuntimeError, 'conflict.*events.json'):
            self.reuse()
        self.assertEqual(owner_sha, git(self.remote, 'rev-parse', 'main').stdout.strip())
        self.assertEqual(owner_rows, self.remote_json('events.json'))
        self.assertFalse(self.trace.exists())

    def test_converged_identical_owner_change_is_not_a_conflict(self):
        expected = self.collected()
        self.put(self.owner, 'events.json', expected)
        owner_sha = self.commit_owner('Same reviewed source change')
        self.assertEqual(owner_sha, self.reuse())
        self.assertEqual(1, len(self.trace.read_text().splitlines()))

    def test_validated_addition_and_deletion_survive_unrelated_main_change(self):
        self.paths += ['new-receipt.json', 'notes.txt']
        self.put(self.bot, 'new-receipt.json', {'collected': 'once'})
        (self.bot / 'notes.txt').unlink()
        self.put(self.owner, 'receipt.json', {'day': 'today'})
        self.commit_owner('New unrelated receipt')
        self.reuse()
        self.assertEqual({'collected': 'once'}, self.remote_json('new-receipt.json'))
        self.assertEqual({'day': 'today'}, self.remote_json('receipt.json'))
        self.assertNotEqual(0, git(self.remote, 'cat-file', '-e', 'main:notes.txt', check=False).returncode)

    def test_conflicting_addition_is_rejected(self):
        self.paths.append('new-receipt.json')
        self.put(self.bot, 'new-receipt.json', {'collected': 'once'})
        self.put(self.owner, 'new-receipt.json', {'owner': 'different evidence'})
        owner_sha = self.commit_owner('New owner receipt')
        with self.assertRaisesRegex(RuntimeError, 'conflict.*new-receipt.json'):
            self.reuse()
        self.assertEqual(owner_sha, git(self.remote, 'rev-parse', 'main').stdout.strip())

    def test_offline_validation_failure_cannot_publish(self):
        self.collected()
        (self.owner / 'notes.txt').write_text('Owner change\n')
        owner_sha = self.commit_owner('New owner note')
        self.command = shlex.join([sys.executable, '-c', 'raise SystemExit(7)'])
        with self.assertRaises(subprocess.CalledProcessError):
            self.reuse()
        self.assertEqual(owner_sha, git(self.remote, 'rev-parse', 'main').stdout.strip())

    def test_offline_validation_cannot_change_unlisted_tracked_or_new_files(self):
        self.collected()
        (self.owner / 'notes.txt').write_text('Owner change\n')
        owner_sha = self.commit_owner('New owner note')
        for filename, stage in [('notes.txt', False), ('unexpected.txt', False), ('notes.txt', True)]:
            with self.subTest(filename=filename, staged=stage):
                code = f"from pathlib import Path; Path({filename!r}).write_text('unexpected')"
                if stage:
                    code += f"; import subprocess; subprocess.run(['git', 'add', {filename!r}], check=True)"
                self.command = shlex.join([sys.executable, '-c', code])
                with self.assertRaisesRegex(RuntimeError, 'unlisted'):
                    self.reuse()
                self.assertEqual(owner_sha, git(self.remote, 'rev-parse', 'main').stdout.strip())

    def test_canadian_retention_still_blocks_loss_from_validated_output(self):
        canadian = dict(self.rows[0], id='canadian', city='Toronto', state='ON', country='CA')
        self.put(self.owner, 'events.json', [*self.rows, canadian])
        self.commit_owner('Confirmed Canadian show')
        git(self.bot, 'pull', '--ff-only', 'origin', 'main')
        self.put(self.bot, 'events.json', self.rows)
        with self.assertRaisesRegex(RuntimeError, 'Canadian event preservation'):
            self.reuse()
        self.assertIn(canadian, self.remote_json('events.json'))

    def test_new_canadian_owner_show_survives_when_collection_did_not_change_feed(self):
        self.put(self.bot, 'receipt.json', {'day': 'today', 'collected': 'once'})
        canadian = dict(self.rows[0], id='canadian', city='Toronto', state='ON', country='CA')
        self.put(self.owner, 'events.json', [*self.rows, canadian])
        self.commit_owner('Confirmed Canadian show')
        self.reuse()
        self.assertIn(canadian, self.remote_json('events.json'))
        self.assertEqual('once', self.remote_json('receipt.json')['collected'])

    def test_four_races_remain_bounded_without_network_collection_replay(self):
        expected = self.collected()
        attempts = []

        def competing_push(attempt, _work):
            attempts.append(attempt)
            (self.owner / 'notes.txt').write_text(f'Owner revision {attempt}\n')
            self.commit_owner(f'Competing owner edit {attempt}')

        with self.assertRaisesRegex(RuntimeError, 'Main kept changing'):
            self.reuse(before_push=competing_push)
        self.assertEqual([0, 1, 2, 3], attempts)
        checks = [json.loads(line) for line in self.trace.read_text().splitlines()]
        self.assertEqual(3, len(checks))
        self.assertTrue(all(check['events.json'] == expected for check in checks))
        self.assertEqual(self.rows, self.remote_json('events.json'))


if __name__ == '__main__':
    unittest.main()
