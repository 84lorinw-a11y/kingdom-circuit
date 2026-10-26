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

    def test_full_replay_restores_curated_artist_seeds_before_final_validation(self):
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
        self.assertIn("replay_source_update.py full", workflow)

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


if __name__ == '__main__': unittest.main()
