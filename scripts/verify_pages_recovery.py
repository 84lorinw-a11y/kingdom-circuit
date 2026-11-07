"""Fail closed before a one-day recovery of the exact reviewed Pages artifact.

Inputs are saved GitHub API responses and a local, unmodified artifact.tar
or the native downloaded ZIP containing only that TAR.
This verifier performs no network requests, extraction or publication.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
from zoneinfo import ZoneInfo
import zipfile

RECOVERY_DAY = date(2026, 11, 7)
UPLOAD = 'Upload Pages artifact'
DEPLOY = 'Deploy to GitHub Pages'


def digest(value):
    value = str(value or '').removeprefix('sha256:')
    return value if re.fullmatch(r'[0-9a-f]{64}', value) else None


def file_sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


@contextmanager
def tar_stream(path):
    """Read native wrapper bytes directly when local disk cannot hold a copy."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].filename != 'artifact.tar' or members[0].is_dir():
                raise ValueError('Native wrapper must contain exactly artifact.tar')
            with archive.open(members[0]) as source:
                yield source, members[0].file_size
    else:
        with Path(path).open('rb') as source:
            yield source, Path(path).stat().st_size


def tar_sha256(path):
    result = hashlib.sha256()
    with tar_stream(path) as (source, _):
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def tar_safety(path):
    """Inspect member metadata only; never extract or follow a link."""
    problems, files, directories, names = [], set(), set(), Counter()
    total = 0
    with tar_stream(path) as (source, tar_bytes), tarfile.open(fileobj=source, mode='r|') as archive:
        for member in archive:
            raw = member.name
            name = str(PurePosixPath(raw)).rstrip('/')
            if (raw.startswith('/') or '..' in PurePosixPath(raw).parts or '\\' in raw
                    or any(ord(c) < 32 or ord(c) == 127 for c in raw)):
                problems.append('unsafe path')
            names[name] += 1
            if member.isfile():
                files.add(name)
                total += member.size
                if member.mode & (stat.S_IRUSR | stat.S_IROTH) != stat.S_IRUSR | stat.S_IROTH:
                    problems.append('unreadable file')
            elif member.isdir():
                directories.add(name)
                required = stat.S_IRUSR | stat.S_IXUSR | stat.S_IROTH | stat.S_IXOTH
                if member.mode & required != required:
                    problems.append('unreadable directory')
            else:
                problems.append('link or special file')
    if any(count != 1 for count in names.values()):
        problems.append('duplicate normalized member')
    if any(name in directories or any(str(parent) in files for parent in PurePosixPath(name).parents)
           for name in files):
        problems.append('file/directory conflict')
    if not files or total > 1024 ** 3 or tar_bytes >= 10 * 1024 ** 3:
        problems.append('empty or oversized archive')
    return {'passed': not problems, 'files': len(files), 'regularBytes': total,
            'problems': sorted(set(problems))}


def verify(manifest, run, jobs, artifact, tar_path, *, today=None):
    """Return a receipt; tests may inject a date, but the CLI has no override."""
    today = today if today is not None else datetime.now(ZoneInfo('America/Los_Angeles')).date()
    results = []

    def check(name, condition, details=None):
        row = {'check': name, 'passed': bool(condition)}
        if details is not None:
            row['details'] = details
        results.append(row)

    gates = manifest.get('requiredGateNames', [])
    manifest_ok = (isinstance(gates, list) and len(gates) == 54 and len(set(gates)) == 54
                   and all(isinstance(x, str) and x.strip() for x in gates)
                   and UPLOAD not in gates and DEPLOY not in gates
                   and manifest.get('runAttempt') == 1
                   and re.fullmatch(r'[0-9a-f]{40}', str(manifest.get('sourceSha', '')))
                   and digest(manifest.get('tarSha256')) is not None
                   and digest(manifest.get('artifactDigest')) is not None
                   and all(type(manifest.get(key)) is int and manifest[key] > 0
                           for key in ('runId', 'jobId', 'artifactId')))
    check('frozen_manifest_shape', manifest_ok)
    check('same_day_pacific_recovery_only', today == RECOVERY_DAY and manifest.get('datePacific') == RECOVERY_DAY.isoformat())
    check('original_run_identity_attempt_repository',
          run.get('id') == manifest.get('runId') and run.get('run_attempt') == 1
          and run.get('head_branch') == 'main'
          and (run.get('repository') or {}).get('full_name') == manifest.get('repository'))
    check('original_run_source_sha', run.get('head_sha') == manifest.get('sourceSha'))
    check('original_run_completed_failure', run.get('status') == 'completed' and run.get('conclusion') == 'failure')
    candidates = jobs.get('jobs', []) if isinstance(jobs, dict) else []
    matches = [job for job in candidates if job.get('id') == manifest.get('jobId')]
    job = matches[0] if len(matches) == 1 else {}
    check('original_job_identity_attempt_run',
          len(candidates) == 1 and len(matches) == 1 and jobs.get('total_count') == 1
          and job.get('run_id') == manifest.get('runId') and job.get('run_attempt') == 1)
    check('original_job_source_sha', job.get('head_sha') == manifest.get('sourceSha'))
    check('original_job_completed_failure', job.get('status') == 'completed' and job.get('conclusion') == 'failure')
    steps = job.get('steps', [])
    by_name = {}
    for step in steps:
        by_name.setdefault(step.get('name'), []).append(step)
    passed_gates = [name for name in gates if len(by_name.get(name, [])) == 1
                    and by_name[name][0].get('status') == 'completed'
                    and by_name[name][0].get('conclusion') == 'success']
    check('all54_required_gates_success_once', manifest_ok and len(passed_gates) == 54,
          {'passed': len(passed_gates), 'missingOrUnsuccessful': [name for name in gates if name not in passed_gates]})
    uploads, deploys = by_name.get(UPLOAD, []), by_name.get(DEPLOY, [])
    check('original_upload_success_once', len(uploads) == 1 and uploads[0].get('status') == 'completed'
          and uploads[0].get('conclusion') == 'success')
    numbers = [by_name[name][0].get('number') for name in passed_gates]
    ordering = (len(numbers) == 54 and all(type(x) is int and x > 0 for x in numbers)
                and len(set(numbers)) == 54 and len(uploads) == len(deploys) == 1
                and type(uploads[0].get('number')) is int and type(deploys[0].get('number')) is int)
    check('gate_upload_deployment_ordering', ordering and max(numbers, default=0) < uploads[0]['number'] < deploys[0]['number'])
    failed = [step for step in steps if step.get('conclusion') not in {'success', 'skipped'}]
    check('only_pages_deployment_failed', len(deploys) == 1 and len(failed) == 1
          and failed[0].get('name') == DEPLOY and failed[0].get('conclusion') == 'failure'
          and all(step.get('status') == 'completed' for step in steps))
    workflow_run = artifact.get('workflow_run') or {}
    check('exact_unexpired_source_artifact_identity_digest',
          artifact.get('id') == manifest.get('artifactId') and artifact.get('name') == manifest.get('artifactName')
          and artifact.get('expired') is False and type(artifact.get('size_in_bytes')) is int
          and artifact['size_in_bytes'] > 0
          and digest(artifact.get('digest')) is not None
          and digest(artifact.get('digest')) == digest(manifest.get('artifactDigest'))
          and workflow_run.get('id') == manifest.get('runId')
          and workflow_run.get('head_sha') == manifest.get('sourceSha') and workflow_run.get('head_branch') == 'main')
    actual_sha = None
    try:
        if zipfile.is_zipfile(tar_path):
            check('exact_local_zip_sha256', file_sha256(tar_path) == digest(manifest.get('artifactDigest')))
        actual_sha = tar_sha256(tar_path)
        check('exact_local_tar_sha256', actual_sha == digest(manifest.get('tarSha256')), actual_sha)
        safety = tar_safety(tar_path)
        check('local_tar_safety', safety['passed'], safety)
    except (OSError, tarfile.TarError, zipfile.BadZipFile, ValueError):
        check('local_tar_safety', False, 'Local TAR could not be safely inspected')
    return {
        'passed': all(row['passed'] for row in results), 'checks': len(results),
        'failures': sum(not row['passed'] for row in results), 'results': results,
        'datePacific': today.isoformat(), 'runId': manifest.get('runId'), 'jobId': manifest.get('jobId'),
        'sourceSha': manifest.get('sourceSha'), 'artifactId': manifest.get('artifactId'),
        'artifactName': manifest.get('artifactName'), 'tarSha256': actual_sha,
        'requiredGatesPassed': len(passed_gates), 'networkRequests': 0,
        'livePublicationVerified': False,
        'scope': 'Offline provenance and packaging verification only; does not deploy or prove live publication.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'run-json', 'jobs-json', 'artifact-json', 'tar', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        inputs = [json.loads(path.read_text()) for path in (args.manifest, args.run_json, args.jobs_json, args.artifact_json)]
        if not all(isinstance(value, dict) for value in inputs):
            raise ValueError('Each input must be one JSON object')
        result = verify(*inputs, args.tar)
    except (OSError, ValueError, TypeError, KeyError):
        result = {'passed': False, 'livePublicationVerified': False,
                  'error': 'Recovery input could not be validated; no publication authorized.'}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result.get(key) for key in ('passed', 'checks', 'failures', 'requiredGatesPassed', 'error')}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
