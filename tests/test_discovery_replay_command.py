"""The real workflow must recheck collection coverage after a publication race."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import textwrap
import unittest


class DiscoveryReplayCommandTests(unittest.TestCase):
    def test_full_replay_rechecks_current_roster_but_date_replay_does_not(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/update-and-deploy.yml').read_text()
        step = workflow.split('- name: Save refreshed event data', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('KC_DISCOVERY_MODE: ${{ steps.refresh-mode.outputs.discovery }}', step)
        shell = textwrap.dedent(step.split('run: |\n', 1)[1])
        with tempfile.TemporaryDirectory(prefix='kc replay ') as directory:
            root = Path(directory)
            # Capture the real shell argument vector without collecting or publishing.
            (root / 'python').write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$KC_CAPTURE_ARGS"\n')
            (root / 'python').chmod(0o755)
            for mode in ('true', 'false'):
                with self.subTest(mode=mode):
                    target = root / ('arguments-' + mode)
                    env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                               KC_DISCOVERY_MODE=mode, RUNNER_TEMP=directory,
                               KC_CAPTURE_ARGS=str(target))
                    subprocess.run(['bash', '-euo', 'pipefail', '-c', shell], env=env, check=True)
                    args = target.read_bytes().decode().rstrip('\0').split('\0')
                    self.assertEqual('scripts/publish_automation_changes.py', args[0])
                    replays = [args[index + 1] for index, arg in enumerate(args) if arg == '--replay']
                    self.assertEqual(3 if mode == 'true' else 2, len(replays))
                    self.assertFalse(any('replay_source_update.py full' in command for command in replays))
                    if mode == 'true':
                        self.assertEqual(['python', 'scripts/verify_discovery_receipt.py', '--source', '.',
                                          '--report', str(root / 'discovery-receipt.json')],
                                         shlex.split(replays[-1]))
                    else:
                        self.assertFalse(any('verify_discovery_receipt.py' in command for command in replays))


if __name__ == '__main__':
    unittest.main()
