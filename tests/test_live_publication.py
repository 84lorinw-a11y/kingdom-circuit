"""Exercise the auditor against a public HTTP transport, without production writes."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'verify_live_publication.py'
MANIFEST_PATH = '/publication-manifest.json'


def manifest(files, release='release-one'):
    return {
        'schemaVersion': 1, 'releaseId': release, 'asOf': '2026-11-09',
        'files': {path: {'sha256': hashlib.sha256(body).hexdigest(),
                         'size': len(body), 'status': status,
                         'kind': 'html' if path.endswith('/') else 'asset'}
                  for path, (status, body) in files.items()},
    }


@contextmanager
def server(routes):
    """Each route has a response or a bounded sequence of responses."""
    lock = threading.Lock()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            with lock:
                requests.append({'path': path, 'url': self.path,
                                 'headers': dict(self.headers)})
                response = routes.get(path, (404, b'Unexpected request'))
                if isinstance(response, list):
                    response = response.pop(0) if len(response) > 1 else response[0]
            status, body, *extra = response
            settings = extra[0] if extra else {}
            if settings.get('delay'):
                time.sleep(settings['delay'])
            try:
                self.send_response(status)
                self.send_header('Content-Length', str(len(body)))
                for key, value in settings.get('headers', {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=httpd.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    worker.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}', requests
    finally:
        httpd.shutdown()
        httpd.server_close()
        worker.join()


def manifest_response(value):
    return 200, json.dumps(value).encode()


class LivePublicationTests(unittest.TestCase):
    def run_audit(self, base, expected=None, options=()):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            command = [sys.executable, str(SCRIPT), '--base-url', base,
                       '--report', str(output / 'report.json'),
                       '--summary', str(output / 'summary.md'),
                       '--attempts', '3', '--retry-delay', '0', '--timeout', '1',
                       '--release-attempts', '3', '--release-delay', '0', *options]
            if expected is not None:
                path = output / 'manifest.json'
                path.write_text(json.dumps(expected))
                command += ['--manifest', str(path)]
            process = subprocess.run(command, text=True, capture_output=True, timeout=20)
            self.assertTrue((output / 'report.json').is_file(),
                            'Auditor must write its report: ' + process.stdout + process.stderr)
            self.assertTrue((output / 'summary.md').is_file(), 'Auditor must write a readable summary')
            return process.returncode, json.loads((output / 'report.json').read_text()), (output / 'summary.md').read_text()

    def test_audits_every_manifest_file_and_accepts_exact_custom_404(self):
        files = {'/': (200, b'Home'), '/artists/one/': (200, b'Artist'),
                 '/robots.txt': (200, b'Allow: /'), '/assets/art.webp': (200, b'Art'),
                 '/__publication-audit-not-found__/': (404, b'Custom missing page')}
        expected = manifest(files)
        with server({**files, MANIFEST_PATH: manifest_response(expected)}) as (base, requests):
            code, report, summary = self.run_audit(base, expected)
        self.assertEqual(0, code, report)
        self.assertEqual('pass', report['status'])
        self.assertEqual(5, report['summary']['filesChecked'])
        self.assertEqual(5, report['summary']['passed'])
        self.assertEqual(set(files), {row['path'] for row in report['rounds'][0]['results']})
        self.assertIn('release-one', summary)
        self.assertTrue(all(item['headers'].get('Accept-Encoding') == 'identity' for item in requests))
        self.assertFalse(any('Authorization' in item['headers'] or 'Cookie' in item['headers'] for item in requests))

    def test_temporary_503_timeout_and_stale_body_recover_with_evidence(self):
        files = {'/': (200, b'Current release')}
        expected = manifest(files)
        responses = [(503, b'Unavailable'), (200, b'Late', {'delay': .15}),
                     (200, b'Previous release'), files['/']]
        with server({'/': responses, MANIFEST_PATH: manifest_response(expected)}) as (base, _):
            code, report, _ = self.run_audit(base, expected,
                                            ['--attempts', '4', '--timeout', '.05'])
        self.assertEqual(0, code, report)
        result = report['rounds'][0]['results'][0]
        self.assertEqual(3, result['retries'])
        self.assertEqual(503, result['attempts'][0]['status'])
        self.assertIn('timeout', result['attempts'][1]['error'].lower())
        self.assertIn('sha256', result['attempts'][2]['error'])
        self.assertEqual(hashlib.sha256(b'Current release').hexdigest(), result['attempts'][3]['sha256'])
        self.assertTrue(all(row['requestUrl'].startswith(base + '/?') for row in result['attempts']))

    def test_http_200_with_wrong_release_bytes_fails_after_bounded_retries(self):
        expected = manifest({'/': (200, b'Expected')})
        with server({'/': (200, b'Wrong!!!'), MANIFEST_PATH: manifest_response(expected)}) as (base, _):
            code, report, summary = self.run_audit(base, expected)
        self.assertEqual(1, code)
        self.assertEqual('fail', report['status'])
        result = report['rounds'][0]['results'][0]
        self.assertEqual(3, len(result['attempts']))
        self.assertIn('sha256', result['error'])
        self.assertIn(base + '/', summary)
        self.assertEqual(1, report['summary']['failed'])

    def test_unavailable_page_is_reported_and_never_skipped(self):
        expected = manifest({'/': (200, b'Home'), '/artists/gone/': (200, b'Artist')})
        with server({'/': (200, b'Home'), '/artists/gone/': (503, b'Offline'),
                     MANIFEST_PATH: manifest_response(expected)}) as (base, _):
            code, report, _ = self.run_audit(base, expected)
        self.assertEqual(1, code)
        self.assertEqual(2, report['summary']['filesChecked'])
        self.assertEqual(1, report['summary']['passed'])
        self.assertEqual(1, report['summary']['failed'])
        self.assertEqual(base + '/artists/gone/', report['rounds'][0]['results'][1]['url'])

    def test_missing_route_must_return_404_even_when_body_matches(self):
        expected = manifest({'/': (200, b'Home'), '/missing/': (404, b'Missing')})
        with server({'/': (200, b'Home'), '/missing/': (200, b'Missing'),
                     MANIFEST_PATH: manifest_response(expected)}) as (base, _):
            code, report, _ = self.run_audit(base, expected)
        self.assertEqual(1, code)
        self.assertIn('HTTP 200; expected 404', report['rounds'][0]['results'][1]['error'])

    def test_post_deploy_waits_for_the_exact_expected_manifest(self):
        expected = manifest({'/': (200, b'New')}, 'new')
        previous = manifest({'/': (200, b'Old')}, 'old')
        with server({'/': (200, b'New'), MANIFEST_PATH: [manifest_response(previous),
                     manifest_response(expected)]}) as (base, _):
            code, report, _ = self.run_audit(base, expected)
        self.assertEqual(0, code, report)
        self.assertEqual('new', report['releaseId'])
        self.assertEqual(1, report['manifestChecks'][0]['retries'])
        self.assertIn('release', report['manifestChecks'][0]['attempts'][0]['error'])

    def test_post_deploy_never_passes_a_stable_old_manifest(self):
        expected = manifest({'/': (200, b'New')}, 'new')
        previous = manifest({'/': (200, b'Old')}, 'old')
        with server({'/': (200, b'Old'), MANIFEST_PATH: manifest_response(previous)}) as (base, requests):
            code, report, _ = self.run_audit(base, expected)
        self.assertEqual(1, code)
        self.assertEqual(0, report['summary']['filesChecked'])
        self.assertEqual(3, len(report['manifestChecks'][0]['attempts']))
        self.assertFalse(any(row['path'] == '/' for row in requests))

    def test_post_deploy_compares_files_even_when_release_id_is_reused(self):
        expected = manifest({'/': (200, b'New')})
        stale = manifest({'/': (200, b'Old')})
        with server({MANIFEST_PATH: manifest_response(stale)}) as (base, _):
            code, report, _ = self.run_audit(base, expected)
        self.assertEqual(1, code)
        self.assertIn('manifest', report['manifestChecks'][0]['error'])

    def test_manual_audit_restarts_once_when_release_changes_mid_crawl(self):
        old = manifest({'/': (200, b'Old')}, 'old')
        new = manifest({'/': (200, b'New'), '/new/': (200, b'Added')}, 'new')
        with server({'/': (200, b'New'), '/new/': (200, b'Added'),
                     MANIFEST_PATH: [manifest_response(old), manifest_response(new)]}) as (base, _):
            code, report, _ = self.run_audit(base)
        self.assertEqual(0, code, report)
        self.assertEqual(1, report['restartCount'])
        self.assertEqual('new', report['releaseId'])
        self.assertEqual(2, len(report['rounds']))
        self.assertEqual(2, report['summary']['passed'])
        self.assertEqual('fail', report['rounds'][0]['results'][0]['status'])

    def test_manual_audit_fails_if_release_changes_twice(self):
        first = manifest({'/': (200, b'One')}, 'one')
        second = manifest({'/': (200, b'Two')}, 'two')
        third = manifest({'/': (200, b'Two')}, 'three')
        with server({'/': (200, b'Two'), MANIFEST_PATH: [manifest_response(first),
                     manifest_response(second), manifest_response(third)]}) as (base, _):
            code, report, summary = self.run_audit(base)
        self.assertEqual(1, code)
        self.assertEqual(1, report['restartCount'])
        self.assertIn('changed twice', ' '.join(report['errors']))
        self.assertIn('changed twice', summary)

    def test_manifest_disappearance_at_end_of_audit_cannot_pass(self):
        expected = manifest({'/': (200, b'Home')})
        with server({'/': (200, b'Home'), MANIFEST_PATH: [manifest_response(expected),
                     (503, b'Offline')]}) as (base, _):
            code, report, _ = self.run_audit(base)
        self.assertEqual(1, code)
        self.assertEqual('fail', report['manifestChecks'][-1]['status'])

    def test_response_size_limit_fails_explicitly(self):
        expected = manifest({'/': (200, b'Home')})
        with server({'/': (200, b'X' * 5000), MANIFEST_PATH: manifest_response(expected)}) as (base, _):
            code, report, _ = self.run_audit(base, expected, ['--max-response-bytes', '1024'])
        self.assertEqual(1, code)
        self.assertIn('limit', report['rounds'][0]['results'][0]['error'])

    def test_redirect_to_another_origin_is_not_followed(self):
        expected = manifest({'/': (200, b'Home')})
        with server({'/': (200, b'Home')}) as (foreign, foreign_requests):
            with server({'/': (302, b'', {'headers': {'Location': foreign + '/'}}),
                         MANIFEST_PATH: manifest_response(expected)}) as (base, _):
                code, report, _ = self.run_audit(base, expected)
        self.assertEqual(1, code)
        self.assertEqual([], foreign_requests)
        self.assertIn('redirect', report['rounds'][0]['results'][0]['error'].lower())

    def test_invalid_manifest_paths_fail_before_any_outside_request(self):
        for bad in ['https://outside.invalid/', '//outside.invalid/', '/a/../b', '/a?token=secret',
                    '/a#fragment', '/%2e%2e/b', '/a\\b']:
            with self.subTest(path=bad):
                expected = manifest({'/': (200, b'Home'), bad: (200, b'Bad')})
                with server({MANIFEST_PATH: manifest_response(expected)}) as (base, requests):
                    code, report, _ = self.run_audit(base, expected)
                self.assertEqual(1, code)
                self.assertEqual([], requests)
                self.assertIn('path', ' '.join(report['errors']).lower())

    def test_invalid_manifest_shape_produces_failure_json(self):
        for invalid in [{}, {'schemaVersion': 1, 'releaseId': 'a', 'asOf': '2026-11-09', 'files': {}},
                        manifest({'/': (200, b'')}) | {'releaseId': ''}]:
            with self.subTest(manifest=invalid):
                with server({}) as (base, _):
                    code, report, summary = self.run_audit(base, invalid)
                self.assertEqual(1, code)
                self.assertEqual('fail', report['status'])
                self.assertIn('FAIL', summary)

    def test_boolean_schema_version_is_not_accepted_as_version_one(self):
        expected = manifest({'/': (200, b'Home')})
        expected['schemaVersion'] = True
        with server({'/': (200, b'Home'), MANIFEST_PATH: manifest_response(expected)}) as (base, requests):
            code, report, _ = self.run_audit(base, expected)
        self.assertEqual(1, code)
        self.assertEqual([], requests)
        self.assertIn('schemaVersion', ' '.join(report['errors']))

    def test_deadline_reports_unchecked_urls_as_failures(self):
        expected = manifest({'/': (200, b'Home'), '/slow/': (200, b'Slow')})
        with server({'/': (200, b'Home'), '/slow/': (200, b'Slow'),
                     MANIFEST_PATH: (200, json.dumps(expected).encode(), {'delay': .1})}) as (base, _):
            code, report, _ = self.run_audit(base, expected, ['--max-duration', '.01'])
        self.assertEqual(1, code)
        self.assertIn('deadline', ' '.join(report['errors']).lower())


if __name__ == '__main__':
    unittest.main()
