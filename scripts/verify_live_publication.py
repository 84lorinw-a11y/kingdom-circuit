#!/usr/bin/env python3
"""Read-only verification of an entire published, content-addressed manifest.

With --manifest, require the exact local release before and after the crawl.
Without it, verify a stable live snapshot; this proves live self-consistency,
not that an independently expected deployment reached production.
Only unauthenticated GET requests to the supplied origin are made.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid


MANIFEST_PATH = '/publication-manifest.json'
MANIFEST_LIMIT = 8 * 1024 * 1024


def validate_path(path):
    if not isinstance(path, str):
        raise ValueError('Manifest path must be a string')
    parsed = urlsplit(path)
    decoded = unquote(path)
    if (not path.startswith('/') or path.startswith('//') or parsed.scheme or parsed.netloc
            or parsed.query or parsed.fragment or '?' in path or '#' in path
            or '\\' in decoded or decoded.startswith('//')
            or any(part in {'.', '..'} for part in decoded.split('/'))
            or any(ord(character) < 32 or ord(character) == 127 for character in decoded)):
        raise ValueError(f'Invalid local manifest path: {path!r}')


def validate_manifest(value):
    if (not isinstance(value, dict) or type(value.get('schemaVersion')) is not int
            or value['schemaVersion'] != 1):
        raise ValueError('Manifest schemaVersion must be 1')
    if not isinstance(value.get('releaseId'), str) or not value['releaseId'].strip():
        raise ValueError('Manifest releaseId must be a nonempty string')
    if not isinstance(value.get('asOf'), str) or not value['asOf'].strip():
        raise ValueError('Manifest asOf must be a nonempty date or timestamp')
    try:
        datetime.fromisoformat(value['asOf'].replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Manifest asOf must be an ISO date or timestamp') from exc
    files = value.get('files')
    if not isinstance(files, dict) or not files or len(files) > 20000:
        raise ValueError('Manifest files must contain between 1 and 20000 entries')
    for path, entry in files.items():
        validate_path(path)
        if path == MANIFEST_PATH:
            raise ValueError('Manifest must not include its own path')
        if not isinstance(entry, dict) or not re.fullmatch(r'[0-9a-f]{64}', str(entry.get('sha256', ''))):
            raise ValueError(f'Manifest sha256 is invalid for path {path}')
        if type(entry.get('size')) is not int or entry['size'] < 0:
            raise ValueError(f'Manifest size is invalid for path {path}')
        if type(entry.get('status', 200)) is not int or entry.get('status', 200) not in {200, 404}:
            raise ValueError(f'Manifest status must be 200 or 404 for path {path}')
    return value


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'Duplicate manifest key: {key}')
        value[key] = item
    return value


def parse_manifest(body):
    return validate_manifest(json.loads(body, object_pairs_hook=unique_object))


def fingerprint(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True).encode()).hexdigest()


def origin(url):
    parts = urlsplit(url)
    return parts.scheme.lower(), parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80)


def validate_base_url(url):
    parts = urlsplit(url)
    if (parts.scheme not in {'https', 'http'} or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment or parts.path not in {'', '/'}):
        raise ValueError('Base URL must be an unauthenticated HTTP(S) origin without a path or query')
    if parts.scheme != 'https' and parts.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise ValueError('Public audit base URL must use HTTPS (HTTP is only allowed for loopback tests)')
    origin(url)  # Validate the port before starting workers.
    return url.rstrip('/')


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        target = urlsplit(newurl)
        if origin(request.full_url) != origin(newurl) or target.username or target.password:
            raise ValueError(f'Refused redirect outside the audit origin: {newurl}')
        return super().redirect_request(request, response, code, message, headers, newurl)


def fetch(url, timeout, byte_limit, capture_body=False):
    """Hash an identity response with limits on elapsed time and consumed bytes."""
    started = time.monotonic()
    result = {'requestUrl': url, 'status': None, 'finalUrl': url, 'bytes': 0}
    digest = hashlib.sha256()
    chunks = []
    try:
        request = Request(url, method='GET', headers={
            'User-Agent': 'KingdomCircuit-Publication-Audit/1.0',
            'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache',
        })
        # This opener has no cookie jar or HTTP authentication handler.
        try:
            response = build_opener(SameOriginRedirect()).open(request, timeout=timeout)
        except HTTPError as exc:
            response = exc  # A deliberate 404 must still have its body verified.
        with response:
            result.update(status=response.status, finalUrl=response.geturl())
            if response.headers.get('Content-Encoding', 'identity').lower() not in {'', 'identity'}:
                raise ValueError('Response ignored Accept-Encoding: identity')
            length = response.headers.get('Content-Length')
            if length and int(length) > byte_limit:
                raise ValueError(f'Response exceeds byte limit {byte_limit}: Content-Length {length}')
            read = getattr(response, 'read1', response.read)
            while True:
                if time.monotonic() - started >= timeout:
                    raise TimeoutError('GET exceeded its elapsed-time limit')
                chunk = read(min(65536, byte_limit + 1 - result['bytes']))
                if not chunk:
                    break
                result['bytes'] += len(chunk)
                if result['bytes'] > byte_limit:
                    raise ValueError(f'Response exceeds byte limit {byte_limit}')
                digest.update(chunk)
                if capture_body:
                    chunks.append(chunk)
            if time.monotonic() - started >= timeout:
                raise TimeoutError('GET exceeded its elapsed-time limit')
            result['sha256'] = digest.hexdigest()
            if capture_body:
                result['_body'] = b''.join(chunks)
    except (OSError, URLError, ValueError, http.client.HTTPException) as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    result['elapsedSeconds'] = round(time.monotonic() - started, 3)
    return result


class Auditor:
    def __init__(self, args):
        self.args = args
        self.started = time.monotonic()
        self.deadline = self.started + args.max_duration
        self.nonce = uuid.uuid4().hex
        self.base = validate_base_url(args.base_url)
        self.report = {
            'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
            'baseUrl': self.base, 'manifestUrl': self.base + MANIFEST_PATH,
            'mode': 'expected-release' if args.manifest else 'current-live-release',
            'status': 'fail', 'releaseId': None, 'restartCount': 0,
            'manifestChecks': [], 'rounds': [], 'errors': [],
        }

    def check(self, path, expected=None, manifest_expected=None, manifest_check=False):
        url = self.base + quote(path, safe="/%:@!$&'()*+,;=-._~")
        attempts = []
        found = None
        count = self.args.release_attempts if manifest_expected is not None else self.args.attempts
        delay = self.args.release_delay if manifest_expected is not None else self.args.retry_delay
        for number in range(1, count + 1):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                break
            request_url = f'{url}?publication-audit={self.nonce}-{uuid.uuid4().hex[:8]}-{number}'
            limit = MANIFEST_LIMIT if manifest_check else self.args.max_response_bytes
            attempt = fetch(request_url, min(self.args.timeout, remaining), limit, manifest_check)
            body = attempt.pop('_body', None)
            attempt['attempt'] = number
            if not attempt.get('error'):
                status = 200 if manifest_check else expected.get('status', 200)
                if attempt['status'] != status:
                    attempt['error'] = f'HTTP {attempt["status"]}; expected {status}'
                elif manifest_check:
                    try:
                        found = parse_manifest(body)
                        attempt['releaseId'] = found['releaseId']
                        attempt['manifestFingerprint'] = fingerprint(found)
                        if manifest_expected is not None and fingerprint(found) != fingerprint(manifest_expected):
                            attempt['error'] = (f'Live release manifest does not match expected release '
                                                f'{manifest_expected["releaseId"]!r}; observed {found["releaseId"]!r}')
                    except (ValueError, TypeError, UnicodeError) as exc:
                        attempt['error'] = f'Invalid live manifest: {exc}'
                else:
                    differences = []
                    if attempt['sha256'] != expected['sha256']:
                        differences.append(f'sha256 {attempt["sha256"]}; expected {expected["sha256"]}')
                    if attempt['bytes'] != expected['size']:
                        differences.append(f'size {attempt["bytes"]}; expected {expected["size"]}')
                    if differences:
                        attempt['error'] = '; '.join(differences)
            attempts.append(attempt)
            if not attempt.get('error'):
                break
            if number < count:
                time.sleep(max(0, min(delay, self.deadline - time.monotonic())))
        success = bool(attempts) and not attempts[-1].get('error')
        deadline_hit = time.monotonic() >= self.deadline
        if deadline_hit:
            success = False
        result = {
            'path': path, 'url': url, 'status': 'pass' if success else 'fail',
            'attempts': attempts, 'retries': max(0, len(attempts) - 1),
        }
        if expected is not None:
            result['expected'] = expected
        if not success:
            result['error'] = ('Audit deadline reached' if deadline_hit else
                               attempts[-1].get('error', 'Audit deadline reached') if attempts else 'Audit deadline reached')
        return result, found if success else None

    def live_manifest(self, expected=None):
        result, manifest = self.check(MANIFEST_PATH, manifest_expected=expected, manifest_check=True)
        self.report['manifestChecks'].append(result)
        if manifest is None:
            self.report['errors'].append(f'{result["url"]}: {result["error"]}')
        return manifest

    def run(self):
        expected = None
        if self.args.manifest:
            data = self.args.manifest.read_bytes()
            if len(data) > MANIFEST_LIMIT:
                raise ValueError(f'Local manifest exceeds byte limit {MANIFEST_LIMIT}')
            expected = parse_manifest(data)
            self.report['releaseId'] = expected['releaseId']
        current = self.live_manifest(expected)
        if current is None:
            self.report['filesExpected'] = len(expected['files']) if expected else 0
            return self.finish()
        for round_number in range(2):
            self.report['releaseId'] = current['releaseId']
            self.report['manifestFingerprint'] = fingerprint(current)
            self.report['asOf'] = current['asOf']
            self.report['filesExpected'] = len(current['files'])
            items = sorted(current['files'].items())
            with ThreadPoolExecutor(max_workers=self.args.workers) as pool:
                results = list(pool.map(lambda item: self.check(item[0], item[1])[0], items))
            self.report['rounds'].append({'releaseId': current['releaseId'],
                                          'manifestFingerprint': fingerprint(current), 'results': results})
            if time.monotonic() >= self.deadline:
                self.report['errors'].append('Audit deadline reached; all remaining URLs are reported as failures')
                return self.finish()
            after = self.live_manifest(expected)
            if after is None:
                return self.finish()
            if fingerprint(after) != fingerprint(current):
                if expected is not None:
                    self.report['errors'].append('Expected release changed during verification')
                    return self.finish()
                if round_number:
                    self.report['errors'].append('Live release manifest changed twice during verification; no stable snapshot')
                    return self.finish()
                self.report['restartCount'] += 1
                current = after
                continue
            self.report['status'] = 'pass' if all(row['status'] == 'pass' for row in results) else 'fail'
            return self.finish()
        return self.finish()

    def finish(self):
        latest = self.report['rounds'][-1]['results'] if self.report['rounds'] else []
        all_checks = list(self.report['manifestChecks'])
        for audit_round in self.report['rounds']:
            all_checks.extend(audit_round['results'])
        self.report['summary'] = {
            'filesExpected': self.report.get('filesExpected', 0),
            'filesChecked': sum(bool(row['attempts']) for row in latest),
            'passed': sum(row['status'] == 'pass' for row in latest),
            'failed': sum(row['status'] == 'fail' for row in latest),
            'requests': sum(len(row['attempts']) for row in all_checks),
            'retries': sum(row['retries'] for row in all_checks),
            'bytesRead': sum(attempt['bytes'] for row in all_checks for attempt in row['attempts']),
            'elapsedSeconds': round(time.monotonic() - self.started, 3),
        }
        return self.report


def summary_markdown(report):
    counts = report['summary']
    lines = [f'## Publication verification: {report["status"].upper()}', '',
             f'- Mode: `{report["mode"]}`',
             f'- Release: `{report.get("releaseId") or "unknown"}`',
             f'- Site: {report["baseUrl"]}',
             f'- Files checked: {counts["filesChecked"]}/{counts["filesExpected"]}; '
             f'passed: {counts["passed"]}; failed: {counts["failed"]}',
             f'- GET requests: {counts["requests"]}; retries: {counts["retries"]}; '
             f'restarts: {report["restartCount"]}; elapsed: {counts["elapsedSeconds"]} seconds', '',
             'This result verifies published content. It does not change or roll back a deployment.', '']
    if report['mode'] == 'current-live-release':
        lines += ['Manual mode verifies a stable live manifest and its files; it does not prove that a specific workflow run deployed.', '']
    failures = list(report['errors'])
    if report['rounds']:
        failures += [f'{row["url"]}: {row["error"]}' for row in report['rounds'][-1]['results']
                     if row['status'] == 'fail']
    if failures:
        lines += ['Failures (full attempt, status, and hash evidence is in the JSON report):', '']
        lines += ['- ' + message.replace('\n', ' ') for message in failures[:100]]
        if len(failures) > 100:
            lines += [f'- {len(failures) - 100} additional failures in the JSON report.']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='https://kingdomcircuit.com')
    parser.add_argument('--manifest', type=Path, help='Expected local manifest; omit to audit the current live release')
    parser.add_argument('--report', type=Path, default=Path('live-publication-audit.json'))
    parser.add_argument('--summary', type=Path, default=Path('live-publication-audit.md'))
    parser.add_argument('--attempts', type=int, default=4)
    parser.add_argument('--retry-delay', type=float, default=5)
    parser.add_argument('--timeout', type=float, default=20)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--release-attempts', type=int, default=12)
    parser.add_argument('--release-delay', type=float, default=10)
    parser.add_argument('--max-response-bytes', type=int, default=32 * 1024 * 1024)
    parser.add_argument('--max-duration', type=float, default=1800)
    args = parser.parse_args(argv)
    auditor = None
    try:
        if not 1 <= args.workers <= 4:
            raise ValueError('workers must be between 1 and 4')
        if not 1 <= args.attempts <= 12 or not 1 <= args.release_attempts <= 30:
            raise ValueError('attempts must be between 1 and 12; release-attempts between 1 and 30')
        for name in ('timeout', 'max_duration', 'max_response_bytes'):
            if not math.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
                raise ValueError(f'{name} must be finite and positive')
        for name in ('retry_delay', 'release_delay'):
            if not math.isfinite(getattr(args, name)) or getattr(args, name) < 0:
                raise ValueError(f'{name} must be finite and nonnegative')
        auditor = Auditor(args)
        report = auditor.run()
    except (ValueError, OSError, TypeError) as exc:
        if auditor:
            auditor.report['errors'].append(f'{type(exc).__name__}: {exc}')
            report = auditor.finish()
        else:
            report = {'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
                      'baseUrl': args.base_url, 'mode': 'expected-release' if args.manifest else 'current-live-release',
                      'status': 'fail', 'releaseId': None, 'restartCount': 0, 'manifestChecks': [],
                      'rounds': [], 'errors': [f'{type(exc).__name__}: {exc}'],
                      'summary': {key: 0 for key in ('filesExpected', 'filesChecked', 'passed', 'failed',
                                                    'requests', 'retries', 'bytesRead', 'elapsedSeconds')}}
    for path in (args.report, args.summary):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    args.summary.write_text(summary_markdown(report), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('status', 'mode', 'releaseId', 'summary', 'errors')}, indent=2))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
