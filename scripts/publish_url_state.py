"""Save one successful deployment's URL state without publishing feed edits."""
from pathlib import Path
import shlex
import sys
import tempfile

from publish_automation_changes import git, publish


def main():
    root = Path.cwd()
    incoming = (root / '_url-continuity-state.json').resolve()
    if not incoming.is_file():
        raise RuntimeError('Successful build URL state is missing')
    git(root, 'fetch', 'origin', 'main')
    with tempfile.TemporaryDirectory(prefix='kc-url-state-') as directory:
        checkout = Path(directory) / 'work'
        git(root, 'worktree', 'add', '--detach', str(checkout), 'origin/main')
        try:
            # The successful deployment's generated state is immutable input.
            from url_continuity import persist
            persist(checkout, incoming)
            publish(checkout, ['config/url-continuity.json'],
                    [shlex.join([sys.executable, 'scripts/url_continuity.py', '--persist', str(incoming)])],
                    'Preserve published URLs and page change history [skip ci]')
        finally:
            git(root, 'worktree', 'remove', '--force', str(checkout))


if __name__ == '__main__': main()
