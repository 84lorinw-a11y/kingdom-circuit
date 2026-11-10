#!/usr/bin/env python3
"""Publish validated bot output without rebasing conflicting generated JSON.

On a push race, replay the named operation in an isolated worktree of latest
main. Never force-push, choose one side of a conflict, or reset a user's checkout.
The caller supplies the complete reviewed output allowlist and replay commands.
Validated-output reuse is an opt-in alternative: carry only the already checked
file delta onto latest main, reject competing edits to the same file, and use
the supplied replay commands for offline normalization and validation only.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
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


def committed_file(root, revision, name):
    """Read original bytes, distinguishing an absent path from a Git failure."""
    entry = git(root, 'ls-tree', revision, '--', name).stdout
    if not entry:
        return None
    mode, kind, object_and_path = entry.split(' ', 2)
    if mode not in {'100644', '100755'} or kind != 'blob':
        raise RuntimeError(f'Validated publication requires a regular file: {name}')
    object_id = object_and_path.split('\t', 1)[0]
    return subprocess.run(['git', '-C', str(root), 'cat-file', 'blob', object_id],
                          check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def working_file(root, name):
    path = root / name
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeError(f'Validated publication requires a regular file: {name}')
    return path.read_bytes() if path.exists() else None


def reuse_validated_files(work, original, output):
    """Apply a conservative file-level three-way delta without merging facts."""
    updates = {}
    conflicts = []
    for name, content in output.items():
        if content == original[name]:
            continue  # An unchanged collection output must not undo newer main.
        current = working_file(work, name)
        if current == content:
            continue  # Independently accepted identical output has converged.
        if current != original[name]:
            conflicts.append(name)
        else:
            updates[name] = content
    if conflicts:
        raise RuntimeError(f'Validated output conflicts with newer main changes: {sorted(conflicts)}')
    for name, content in updates.items():
        target = work / name
        if content is None:
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


def validated_changed_paths(work):
    # Offline checks must not smuggle in staged changes or new unlisted files.
    tracked = git(work, 'diff', 'HEAD', '--name-only').stdout.splitlines()
    added = git(work, 'ls-files', '--others', '--exclude-standard').stdout.splitlines()
    return set([*tracked, *added])


def preserve_unchanged_coverage_report(work, baseline):
    """Suppress only a new timestamp on an otherwise identical JSON report.

    Called only in the isolated publication worktree after the allowlist and
    retention checks. Restoring the baseline bytes also avoids formatting churn;
    every non-timestamp JSON value must be unchanged, including its type.
    Invalid, absent, or newly created reports are left to the caller's validators.
    """
    target = work / 'coverage-gaps.json'
    if baseline is None or not target.is_file() or target.is_symlink():
        return False

    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate coverage report key')
            value[key] = item
        return value

    try:
        before, after = [json.loads(raw, object_pairs_hook=unique_object)
                         for raw in (baseline, target.read_bytes())]
        if not all(isinstance(report, dict) for report in (before, after)):
            return False
        for report in (before, after):
            stamp = report.get('generatedAt')
            if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace('Z', '+00:00')).tzinfo is None:
                return False
        if before['generatedAt'] == after['generatedAt']:
            return False
        content = [json.dumps({key: value for key, value in report.items() if key != 'generatedAt'},
                              sort_keys=True, ensure_ascii=False, allow_nan=False)
                   for report in (before, after)]
        if content[0] != content[1]:
            return False
    except (ValueError, TypeError, UnicodeDecodeError):
        return False
    target.write_bytes(baseline)
    return True


def publish(root, paths, commands, message, *, attempts=4, sync=False, before_push=None,
            reuse_validated_output=False):
    root = Path(root).resolve()
    if sync and os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Checkout synchronization is restricted to disposable GitHub Actions runners')
    if not commands:
        raise ValueError('A verified replay operation is required')
    allowed = set(paths)
    changed = (validated_changed_paths(root) if reuse_validated_output else
               set(git(root, 'diff', 'HEAD', '--name-only').stdout.splitlines()))
    if changed - allowed:
        raise RuntimeError(f'Unlisted tracked changes; refusing partial publication: {sorted(changed - allowed)}')
    snapshots = {p: (working_file(root, p) if reuse_validated_output else
                     (root / p).read_bytes() if (root / p).is_file() else None) for p in paths}
    original = git(root, 'rev-parse', 'HEAD').stdout.strip()
    original_files = ({p: committed_file(root, original, p) for p in paths}
                      if reuse_validated_output else {})
    for attempt in range(attempts):
        git(root, 'fetch', 'origin', 'main')
        latest = git(root, 'rev-parse', 'origin/main').stdout.strip()
        with tempfile.TemporaryDirectory(prefix='kc-bot-publish-') as tmp:
            work = Path(tmp) / 'work'
            git(root, 'worktree', 'add', '--detach', str(work), latest)
            try:
                canadian_baseline = read_events(work)
                coverage = work / 'coverage-gaps.json'
                coverage_baseline = (coverage.read_bytes() if 'coverage-gaps.json' in allowed
                                     and coverage.is_file() and not coverage.is_symlink() else None)
                if reuse_validated_output:
                    reuse_validated_files(work, original_files, snapshots)
                    if latest != original or attempt:
                        print(f'Main changed; reusing validated output on {latest[:12]} '
                              f'with offline checks (attempt {attempt + 1}/{attempts})', flush=True)
                        for command in commands:
                            subprocess.run(shlex.split(command), cwd=work, check=True)
                elif latest == original and attempt == 0:
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
                touched = (validated_changed_paths(work) if reuse_validated_output else
                           set(git(work, 'diff', '--name-only').stdout.splitlines()))
                if touched - allowed:
                    raise RuntimeError(f'Replay changed unlisted files: {sorted(touched - allowed)}')
                lost = retention_errors(canadian_baseline, read_events(work), today_cutoff())
                if lost:
                    raise RuntimeError('Canadian event preservation blocked publication:\n' + '\n'.join(lost))
                if 'coverage-gaps.json' in allowed and preserve_unchanged_coverage_report(work, coverage_baseline):
                    print('Coverage report content unchanged; preserving its prior generatedAt.', flush=True)
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
    parser.add_argument('--reuse-validated-output', action='store_true', help=(
        'Reuse the validated original-to-output file delta after a push race; '
        'reject same-file conflicts. In this mode --replay must contain only '
        'offline normalization/validation, never network collection.'))
    parser.add_argument('--sync-checkout', action='store_true')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    sha = publish(Path.cwd(), args.paths, args.replay, args.message, sync=args.sync_checkout,
                  reuse_validated_output=args.reuse_validated_output)
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
            output.write(f'validated_source_sha={sha}\n')


if __name__ == '__main__':
    main()
