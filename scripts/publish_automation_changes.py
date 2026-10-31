#!/usr/bin/env python3
"""Publish validated bot output without rebasing conflicting generated JSON.

On a push race, replay the named operation in an isolated worktree of latest
main. Never force-push, choose one side of a conflict, or reset a user's checkout.
The caller supplies the complete reviewed output allowlist and replay commands.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
try:
    from .canadian_event_guard import read_events, retention_errors, today_cutoff
except ImportError:
    from canadian_event_guard import read_events, retention_errors, today_cutoff


def git(root, *args, check=True):
    return subprocess.run(['git', '-C', str(root), *args], check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def publish(root, paths, commands, message, *, attempts=4, sync=False, before_push=None):
    root = Path(root).resolve()
    if sync and os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Checkout synchronization is restricted to disposable GitHub Actions runners')
    if not commands:
        raise ValueError('A verified replay operation is required')
    allowed = set(paths)
    changed = set(git(root, 'diff', 'HEAD', '--name-only').stdout.splitlines())
    if changed - allowed:
        raise RuntimeError(f'Unlisted tracked changes; refusing partial publication: {sorted(changed - allowed)}')
    snapshots = {p: (root / p).read_bytes() if (root / p).is_file() else None for p in paths}
    original = git(root, 'rev-parse', 'HEAD').stdout.strip()
    for attempt in range(attempts):
        git(root, 'fetch', 'origin', 'main')
        latest = git(root, 'rev-parse', 'origin/main').stdout.strip()
        with tempfile.TemporaryDirectory(prefix='kc-bot-publish-') as tmp:
            work = Path(tmp) / 'work'
            git(root, 'worktree', 'add', '--detach', str(work), latest)
            try:
                canadian_baseline = read_events(work)
                if latest == original and attempt == 0:
                    for name, content in snapshots.items():
                        target = work / name
                        if content is None:
                            if target.exists(): target.unlink()
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(content)
                else:
                    print(f'Main changed; recomputing on {latest[:12]} (attempt {attempt + 1}/{attempts})', flush=True)
                    for command in commands:
                        subprocess.run(shlex.split(command), cwd=work, check=True)
                touched = set(git(work, 'diff', '--name-only').stdout.splitlines())
                if touched - allowed:
                    raise RuntimeError(f'Replay changed unlisted files: {sorted(touched - allowed)}')
                lost = retention_errors(canadian_baseline, read_events(work), today_cutoff())
                if lost:
                    raise RuntimeError('Canadian event preservation blocked publication:\n' + '\n'.join(lost))
                existing = [p for p in paths if (work / p).exists() or git(work, 'ls-files', '--', p).stdout.strip()]
                git(work, 'add', '--', *existing)
                if git(work, 'diff', '--cached', '--quiet', check=False).returncode == 0:
                    sha = latest
                else:
                    git(work, '-c', 'user.name=kingdom-circuit-bot', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'commit', '-m', message)
                    sha = git(work, 'rev-parse', 'HEAD').stdout.strip()
                    if before_push: before_push(attempt, work)
                    result = git(work, 'push', 'origin', 'HEAD:main', check=False)
                    if result.returncode:
                        print(result.stderr, flush=True)
                        git(root, 'fetch', 'origin', 'main')
                        if git(root, 'rev-parse', 'origin/main').stdout.strip() == latest:
                            raise RuntimeError('Push failed without a competing commit; check access/network')
                        if attempt + 1 == attempts: raise RuntimeError('Main kept changing; validated output was not published')
                        time.sleep(min(attempt + 1, 3))
                        continue
                if sync:
                    # CI only: build exactly the successfully saved source, including
                    # concurrent owner changes. The caller's original edits are not
                    # discarded locally; this flag cannot run on a user's checkout.
                    git(root, 'restore', '--source', sha, '--staged', '--worktree', '--', '.')
                print(f'Validated automation source: {sha}', flush=True)
                return sha
            finally:
                # Worktree contains only this tool's temporary generated output.
                git(root, 'worktree', 'remove', '--force', str(work))
    raise RuntimeError('Publication did not complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--message', required=True)
    parser.add_argument('--replay', action='append', required=True)
    parser.add_argument('--sync-checkout', action='store_true')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    publish(Path.cwd(), args.paths, args.replay, args.message, sync=args.sync_checkout)


if __name__ == '__main__':
    main()
