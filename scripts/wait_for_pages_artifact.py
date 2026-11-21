"""Wait for the exact successful Pages upload to propagate before deployment.

Run immediately after a successful upload. The propagation grace starts at this
helper's entry, which is later than upload completion, never at created_at (that
timestamp can precede the upload). REST readiness does not prove readiness of the
internal artifact backend used by deploy-pages. The elapsed grace and the separate
delayed deployment retry cover that distinction without changing publication gates.

Only repository scoped GET requests are sent. Authentication stays in memory.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

GRACE_SECONDS = 30
POLL_SECONDS = 10
TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class ExpectedArtifact:
    repository: str
    run_id: int
    run_attempt: int
    artifact_id: int
    head_sha: str

    @property
    def name(self):
        return f'github-pages-{self.run_id}-{self.run_attempt}'

    def safe_metadata(self):
        return {'repository': self.repository, 'runId': self.run_id,
                'runAttempt': self.run_attempt, 'artifactId': self.artifact_id,
                'name': self.name, 'headSha': self.head_sha}

    @classmethod
    def from_environment(cls, env):
        repository = env.get('GITHUB_REPOSITORY', '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Missing or invalid GITHUB_REPOSITORY')
        numbers = []
        for field in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'PAGES_ARTIFACT_ID'):
            value = env.get(field, '')
            if not re.fullmatch(r'[1-9][0-9]*', value):
                raise ValueError('Missing or invalid ' + field)
            numbers.append(int(value))
        head = env.get('GITHUB_SHA', '')
        if not re.fullmatch(r'[0-9a-f]{40}', head):
            raise ValueError('Missing or invalid GITHUB_SHA')
        return cls(repository, *numbers, head)


class ArtifactReadinessError(RuntimeError):
    def __init__(self, code, message, receipt=None):
        super().__init__(message)
        self.code = code
        self.receipt = receipt


def validate_metadata(metadata, expected):
    """Reject identity mismatches rather than waiting for a different upload."""
    if not isinstance(metadata, dict):
        raise ArtifactReadinessError('invalid_metadata', 'Artifact metadata is not an object')
    workflow = metadata.get('workflow_run')
    if not isinstance(workflow, dict):
        raise ArtifactReadinessError('invalid_metadata', 'Artifact workflow identity is missing')
    checks = (
        ('artifact_id_mismatch', metadata.get('id') == expected.artifact_id),
        ('artifact_name_mismatch', metadata.get('name') == expected.name),
        ('run_id_mismatch', workflow.get('id') == expected.run_id),
        ('head_sha_mismatch', workflow.get('head_sha') == expected.head_sha),
        ('artifact_expired', metadata.get('expired') is False),
        ('artifact_size_invalid', type(metadata.get('size_in_bytes')) is int
         and metadata['size_in_bytes'] > 0),
    )
    for code, passed in checks:
        if not passed:
            raise ArtifactReadinessError(code, 'Uploaded Pages artifact failed validation: ' + code)
    return {'id': metadata['id'], 'name': metadata['name'],
            'runId': workflow['id'], 'headSha': workflow['head_sha'],
            'sizeBytes': metadata['size_in_bytes'], 'expired': False,
            'digest': metadata.get('digest'), 'createdAt': metadata.get('created_at')}


def fetch_metadata(expected, token, *, opener=urllib.request.urlopen):
    """404 and temporary transport errors remain bounded by the caller's clock."""
    url = (f'https://api.github.com/repos/{expected.repository}/actions/artifacts/'
           f'{expected.artifact_id}')
    request = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'Kingdom-Circuit-Pages-Artifact-Readiness/1.0',
    }, method='GET')
    request.add_unredirected_header('Authorization', 'Bearer ' + token)
    try:
        with opener(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ArtifactReadinessError('authentication_failed',
                                        f'GitHub artifact authentication failed (HTTP {exc.code})') from None
        if exc.code in (404, 429) or 500 <= exc.code <= 599:
            return None
        raise ArtifactReadinessError('unexpected_http_status',
                                    f'Artifact metadata request failed (HTTP {exc.code})') from None
    except (urllib.error.URLError, TimeoutError):
        return None
    except (ValueError, UnicodeError):
        raise ArtifactReadinessError('invalid_json', 'Artifact metadata response was not valid JSON') from None


def wait_for_artifact(expected, fetch, *, clock=time.monotonic, sleep=time.sleep,
                      grace_seconds=GRACE_SECONDS, poll_seconds=POLL_SECONDS,
                      timeout_seconds=TIMEOUT_SECONDS):
    """Use elapsed time measured after upload, with injectable I/O for tests."""
    if grace_seconds < 0 or poll_seconds <= 0 or timeout_seconds <= grace_seconds:
        raise ValueError('Invalid artifact readiness timing')
    started = clock()
    attempts = 0
    last_metadata = None

    def receipt(status, code=None):
        result = {'schemaVersion': 1, 'status': status, 'expected': expected.safe_metadata(),
                  'attempts': attempts, 'elapsedSeconds': round(clock() - started, 3),
                  'graceSeconds': grace_seconds, 'timeoutSeconds': timeout_seconds,
                  'graceOrigin': 'helper entry after successful upload',
                  'artifact': last_metadata, 'internalDeployBackendVerified': False}
        if code:
            result['errorCode'] = code
        return result

    while clock() - started < timeout_seconds:
        attempts += 1
        try:
            metadata = fetch()
            if metadata is not None:
                last_metadata = validate_metadata(metadata, expected)
                elapsed = clock() - started
                if grace_seconds <= elapsed < timeout_seconds:
                    return receipt('ready')
        except ArtifactReadinessError as exc:
            exc.receipt = receipt('failed', exc.code)
            raise
        remaining = timeout_seconds - (clock() - started)
        if remaining > 0:
            sleep(min(poll_seconds, remaining))
    raise ArtifactReadinessError('readiness_timeout',
                                'Pages artifact readiness timed out without changing production',
                                receipt('failed', 'readiness_timeout'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=Path('pages-artifact-readiness.json'))
    args = parser.parse_args()
    try:
        expected = ExpectedArtifact.from_environment(os.environ)
        token = os.environ.get('GITHUB_TOKEN', '')
        if not token:
            raise ValueError('Missing GITHUB_TOKEN')
        result = wait_for_artifact(expected, lambda: fetch_metadata(expected, token))
        code = 0
    except ArtifactReadinessError as exc:
        result = exc.receipt or {'schemaVersion': 1, 'status': 'failed', 'errorCode': exc.code}
        code = 1
    except ValueError as exc:
        result = {'schemaVersion': 1, 'status': 'failed', 'errorCode': 'invalid_configuration',
                  'message': str(exc)}
        code = 1
    result['checkedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
