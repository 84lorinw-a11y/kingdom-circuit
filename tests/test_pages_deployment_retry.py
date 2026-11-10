"""Execute the publication gate and evaluate the workflow's deployment decisions."""
import ast
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/update-and-deploy.yml'


def workflow_steps():
    text = WORKFLOW.read_text()
    matches = list(re.finditer(r'^      - name: (.+)$', text, re.M))
    return {match[1]: text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
            for index, match in enumerate(matches)}


def field(block, name):
    match = re.search(r'^        ' + re.escape(name) + r': (.+)$', block, re.M)
    return match[1] if match else None


def shell(block):
    lines = block.splitlines()
    start = lines.index('        run: |') + 1
    result = []
    for line in lines[start:]:
        if line and not line.startswith('          '):
            break
        result.append(line[10:] if line else '')
    return '\n'.join(result)


def condition(block, states, *, cancelled=False, failed=False):
    """Evaluate the limited Actions expression grammar used by these steps.

    Step conditions come directly from the production workflow. Refuse unknown
    syntax rather than silently accepting a workflow change the test cannot model.
    """
    expression = field(block, 'if')
    if expression is None:
        return not failed and not cancelled
    expression = expression.removeprefix('${{').removesuffix('}}').strip()
    has_status_function = bool(re.search(r'\b(?:always|cancelled|success|failure)\(\)', expression))
    expression = re.sub(r'steps\.([\w-]+)\.(outcome|conclusion)',
                        lambda match: repr(states.get(match[1], {}).get(match[2], '')),
                        expression)
    for name, value in [('cancelled', cancelled), ('failure', failed),
                        ('success', not failed and not cancelled), ('always', True)]:
        expression = expression.replace(name + '()', repr(value))
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'!(?!=)', ' not ', expression).strip()
    tree = ast.parse(expression, mode='eval')
    supported = (ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Constant,
                 ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq)
    if any(not isinstance(node, supported) for node in ast.walk(tree)):
        raise AssertionError('Unsupported deployment condition: ' + expression)
    result = bool(eval(compile(tree, '<workflow condition>', 'eval'), {'__builtins__': {}}))
    return result and (has_status_function or (not failed and not cancelled))


class PagesDeploymentRetryTests(unittest.TestCase):
    def setUp(self):
        self.steps = workflow_steps()

    def simulate(self, *, first='success', retry='success', live='success', source='success', cancelled=False):
        """Model actual conditions and continue-on-error; run the actual shell gate."""
        states = {'publication-audit': {'outcome': source, 'conclusion': source},
                  'pages-artifact': {'outcome': 'success' if source == 'success' else 'skipped',
                                     'conclusion': 'success' if source == 'success' else 'skipped'}}
        failed = source != 'success'
        visited = []
        plan = [('Deploy to GitHub Pages', first),
                ('Retry accepted Pages artifact once', retry),
                ('Require successful Pages publication', None),
                ('Verify exact published release', live),
                ('Save successful publication URL history', 'success')]
        for name, requested_result in plan:
            block = self.steps[name]
            identifier = field(block, 'id') or name
            if not condition(block, states, cancelled=cancelled, failed=failed):
                states[identifier] = {'outcome': 'skipped', 'conclusion': 'skipped'}
                continue
            visited.append(name)
            if requested_result is None:
                result = subprocess.run(
                    ['bash', '-e', '-o', 'pipefail', '-c', shell(block)], capture_output=True, text=True,
                    env=os.environ | {
                        'FIRST_DEPLOYMENT_OUTCOME': states['deployment']['outcome'],
                        'RETRY_DEPLOYMENT_OUTCOME': states['deployment-retry']['outcome'],
                    })
                outcome = 'success' if result.returncode == 0 else 'failure'
            else:
                outcome = requested_result
            conclusion = 'success' if outcome == 'failure' and field(block, 'continue-on-error') == 'true' else outcome
            states[identifier] = {'outcome': outcome, 'conclusion': conclusion}
            failed = failed or conclusion == 'failure'
        return states, visited, not failed and not cancelled

    def test_first_success_skips_retry_and_requires_live_verification(self):
        states, visited, success = self.simulate()
        self.assertTrue(success)
        self.assertEqual(states['deployment-retry']['outcome'], 'skipped')
        self.assertIn('Verify exact published release', visited)
        self.assertIn('Save successful publication URL history', visited)

    def test_first_failure_retries_once_and_live_success_allows_success(self):
        states, visited, success = self.simulate(first='failure')
        self.assertTrue(success)
        self.assertEqual(states['deployment']['outcome'], 'failure')
        self.assertEqual(states['deployment']['conclusion'], 'success')
        self.assertEqual(visited.count('Retry accepted Pages artifact once'), 1)
        self.assertEqual(states['pages-publication']['outcome'], 'success')
        self.assertEqual(states['live-publication-audit']['outcome'], 'success')

    def test_live_failure_remains_failure_after_either_deployment_success(self):
        for first in ('success', 'failure'):
            with self.subTest(first=first):
                states, visited, success = self.simulate(first=first, live='failure')
                self.assertFalse(success)
                self.assertEqual(states['live-publication-audit']['conclusion'], 'failure')
                self.assertIn('Save successful publication URL history', visited)

    def test_both_attempts_fail_and_neither_live_nor_history_runs(self):
        states, visited, success = self.simulate(first='failure', retry='failure')
        self.assertFalse(success)
        self.assertEqual(states['deployment-retry']['conclusion'], 'failure')
        self.assertEqual(states['pages-publication']['outcome'], 'failure')
        self.assertNotIn('Verify exact published release', visited)
        self.assertNotIn('Save successful publication URL history', visited)

    def test_cancelled_workflow_cannot_retry_or_publish(self):
        states, visited, success = self.simulate(first='failure', cancelled=True)
        self.assertFalse(success)
        self.assertEqual(visited, [])
        # Also exercise cancellation arriving after the first failed deployment.
        after_first = {'deployment': {'outcome': 'failure', 'conclusion': 'success'},
                       'publication-audit': {'outcome': 'success'}, 'pages-artifact': {'outcome': 'success'}}
        self.assertFalse(condition(self.steps['Retry accepted Pages artifact once'], after_first, cancelled=True))

    def test_retry_requires_both_audit_and_artifact_upload_success(self):
        for audit, upload in [('failure', 'success'), ('success', 'failure'), ('skipped', 'skipped')]:
            with self.subTest(audit=audit, upload=upload):
                states = {'deployment': {'outcome': 'failure', 'conclusion': 'success'},
                          'publication-audit': {'outcome': audit}, 'pages-artifact': {'outcome': upload}}
                self.assertFalse(condition(self.steps['Retry accepted Pages artifact once'], states))

    def test_build_cannot_upload_without_a_nonempty_public_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = root / 'bin'
            commands.mkdir()
            for name, content in [('git', '#!/bin/sh\nprintf "fixture-commit\\n"\n'), ('python', '#!/bin/sh\nexit 0\n')]:
                path = commands / name
                path.write_text(content)
                path.chmod(0o755)
            env = os.environ | {'PATH': str(commands) + os.pathsep + os.environ['PATH'],
                                'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1'}
            command = ['bash', '-e', '-o', 'pipefail', '-c', shell(self.steps['Audit final publication artifact'])]
            self.assertNotEqual(subprocess.run(command, cwd=root, env=env, capture_output=True).returncode, 0)
            (root / '_site').mkdir()
            (root / '_site/publication-manifest.json').write_text('{}\n')
            self.assertEqual(subprocess.run(command, cwd=root, env=env, capture_output=True).returncode, 0)

    def test_source_audit_failure_cannot_become_success_or_reach_deployment(self):
        states, visited, success = self.simulate(source='failure')
        self.assertFalse(success)
        self.assertEqual(states['deployment']['outcome'], 'skipped')
        self.assertEqual(states['deployment-retry']['outcome'], 'skipped')
        self.assertEqual(states['pages-publication']['outcome'], 'failure')
        self.assertNotIn('Verify exact published release', visited)

    def test_acceptance_shell_rejects_missing_skipped_or_failed_deployment(self):
        block = self.steps['Require successful Pages publication']
        for first, retry in [('', ''), ('skipped', 'skipped'), ('failure', 'skipped'), ('failure', 'failure')]:
            with self.subTest(first=first, retry=retry):
                result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', shell(block)], capture_output=True,
                                        env=os.environ | {'FIRST_DEPLOYMENT_OUTCOME': first, 'RETRY_DEPLOYMENT_OUTCOME': retry})
                self.assertNotEqual(result.returncode, 0)

    def test_retry_reuses_exact_accepted_artifact_without_rebuilding(self):
        names = list(self.steps)
        audit = names.index('Audit final publication artifact')
        upload = names.index('Upload Pages artifact')
        first = names.index('Deploy to GitHub Pages')
        retry = names.index('Retry accepted Pages artifact once')
        accept = names.index('Require successful Pages publication')
        self.assertEqual([audit + 1, upload + 1, first + 1, retry + 1], [upload, first, retry, accept])
        blocks = [self.steps[names[first]], self.steps[names[retry]]]
        self.assertEqual([field(block, 'uses') for block in blocks], ['actions/deploy-pages@v5'] * 2)
        artifact_names = [re.search(r'^          artifact_name: (.+)$', block, re.M)[1] for block in blocks]
        self.assertEqual(artifact_names[0], artifact_names[1])
        self.assertIn('${{ github.run_id }}-${{ github.run_attempt }}', artifact_names[0])
        self.assertEqual(sum(field(block, 'uses') == 'actions/deploy-pages@v5' for block in self.steps.values()), 2)


if __name__ == '__main__':
    unittest.main()
