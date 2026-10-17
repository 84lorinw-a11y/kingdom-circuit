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
