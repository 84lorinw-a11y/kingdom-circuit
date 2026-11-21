"""Exercise artifact identity, upload propagation grace and bounded failures."""
import io
import json
from pathlib import Path
import sys
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from wait_for_pages_artifact import (ArtifactReadinessError, ExpectedArtifact,
                                     fetch_metadata, wait_for_artifact)


class Clock:
    def __init__(self):
        self.now = 0
        self.sleeps = []

    def read(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class PagesArtifactReadinessTests(unittest.TestCase):
    def setUp(self):
        self.expected = ExpectedArtifact('84lorinw-a11y/kingdom-circuit', 42, 2, 99, 'a' * 40)
        self.clock = Clock()

    def metadata(self):
        return {'id': 99, 'name': 'github-pages-42-2', 'expired': False,
                'size_in_bytes': 689529545, 'created_at': '2020-01-01T00:00:00Z',
                'digest': 'sha256:' + 'b' * 64,
                'workflow_run': {'id': 42, 'head_sha': 'a' * 40}}

    def wait(self, fetch):
        return wait_for_artifact(self.expected, fetch, clock=self.clock.read, sleep=self.clock.sleep)

    def test_visible_metadata_still_waits_thirty_seconds_after_upload(self):
        result = self.wait(self.metadata)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['elapsedSeconds'], 30)
        self.assertEqual(self.clock.sleeps, [10, 10, 10])
        self.assertEqual(result['attempts'], 4)
        self.assertFalse(result['internalDeployBackendVerified'])

    def test_missing_then_visible_polls_until_identity_and_grace_both_pass(self):
        responses = iter([None, None, None, None, self.metadata()])
        result = self.wait(lambda: next(responses))
        self.assertEqual(result['elapsedSeconds'], 40)
        self.assertEqual(result['artifact']['id'], 99)

    def test_artifact_created_at_does_not_shortcut_upload_grace(self):
        for created in ('2020-01-01T00:00:00Z', '2099-01-01T00:00:00Z', None):
            with self.subTest(created=created):
                self.clock = Clock()
                data = dict(self.metadata(), created_at=created)
                self.assertEqual(self.wait(lambda: data)['elapsedSeconds'], 30)

    def test_wrong_identity_expiry_or_size_fails_immediately(self):
        cases = [('id', 100, 'artifact_id_mismatch'),
                 ('name', 'github-pages-42-1', 'artifact_name_mismatch'),
                 ('expired', True, 'artifact_expired'),
                 ('size_in_bytes', 0, 'artifact_size_invalid'),
                 ('size_in_bytes', True, 'artifact_size_invalid')]
        for field, value, code in cases:
            with self.subTest(field=field, value=value):
                data = dict(self.metadata(), **{field: value})
                with self.assertRaises(ArtifactReadinessError) as caught:
                    self.wait(lambda: data)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.receipt['attempts'], 1)
                self.assertEqual(self.clock.sleeps, [])

    def test_wrong_workflow_run_or_head_fails_immediately(self):
        for field, value, code in [('id', 43, 'run_id_mismatch'), ('head_sha', 'c' * 40, 'head_sha_mismatch')]:
            with self.subTest(field=field):
                data = self.metadata()
                data['workflow_run'][field] = value
                with self.assertRaises(ArtifactReadinessError) as caught:
                    self.wait(lambda: data)
                self.assertEqual(caught.exception.code, code)
                self.assertFalse(self.clock.sleeps)

    def test_missing_metadata_stops_at_one_hundred_eighty_seconds(self):
        with self.assertRaises(ArtifactReadinessError) as caught:
            self.wait(lambda: None)
        self.assertEqual(caught.exception.code, 'readiness_timeout')
        self.assertEqual(caught.exception.receipt['elapsedSeconds'], 180)
        self.assertEqual(caught.exception.receipt['attempts'], 18)
        self.assertEqual(self.clock.sleeps, [10] * 18)

    def test_fetch_that_finishes_after_deadline_cannot_pass(self):
        def slow_fetch():
            self.clock.now += 181
            return self.metadata()
        with self.assertRaises(ArtifactReadinessError) as caught:
            self.wait(slow_fetch)
        self.assertEqual(caught.exception.code, 'readiness_timeout')
        self.assertEqual(self.clock.sleeps, [])

    def test_authentication_errors_fail_fast_and_do_not_disclose_token(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.clock = Clock()
                def opener(request, timeout):
                    raise urllib.error.HTTPError(request.full_url, status, 'secret-token', {},
                                                 io.BytesIO(b'secret-token'))
                with self.assertRaises(ArtifactReadinessError) as caught:
                    self.wait(lambda: fetch_metadata(self.expected, 'secret-token', opener=opener))
                self.assertEqual(caught.exception.code, 'authentication_failed')
                self.assertNotIn('secret-token', str(caught.exception))
                self.assertNotIn('secret-token', json.dumps(caught.exception.receipt))
                self.assertEqual(self.clock.sleeps, [])

    def test_temporary_http_errors_are_retryable_not_authentication_success(self):
        for status in (404, 429, 500, 502, 503):
            with self.subTest(status=status):
                def opener(request, timeout):
                    raise urllib.error.HTTPError(request.full_url, status, 'temporary', {}, io.BytesIO())
                self.assertIsNone(fetch_metadata(self.expected, 'not-logged', opener=opener))

    def test_only_exact_repository_scoped_get_is_sent(self):
        def opener(request, timeout):
            self.assertEqual(request.method, 'GET')
            self.assertEqual(request.full_url,
                             'https://api.github.com/repos/84lorinw-a11y/kingdom-circuit/actions/artifacts/99')
            self.assertEqual(request.unredirected_hdrs['Authorization'], 'Bearer not-logged')
            self.assertNotIn('Authorization', request.headers)
            self.assertEqual(timeout, 20)
            return io.BytesIO(json.dumps(self.metadata()).encode())
        self.assertEqual(fetch_metadata(self.expected, 'not-logged', opener=opener)['id'], 99)

    def test_environment_uses_current_attempt_and_rejects_invalid_identifiers(self):
        env = {'GITHUB_REPOSITORY': '84lorinw-a11y/kingdom-circuit', 'GITHUB_RUN_ID': '42',
               'GITHUB_RUN_ATTEMPT': '2', 'PAGES_ARTIFACT_ID': '99', 'GITHUB_SHA': 'a' * 40}
        self.assertEqual(ExpectedArtifact.from_environment(env), self.expected)
        for key, value in [('GITHUB_REPOSITORY', 'https://other.example/owner/repo'),
                           ('GITHUB_RUN_ID', '0'), ('GITHUB_RUN_ATTEMPT', '1/2'),
                           ('PAGES_ARTIFACT_ID', ''), ('GITHUB_SHA', 'main')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    ExpectedArtifact.from_environment(dict(env, **{key: value}))


if __name__ == '__main__':
    unittest.main()
