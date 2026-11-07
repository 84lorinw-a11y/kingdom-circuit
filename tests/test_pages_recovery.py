"""Portable recovery provenance regressions using actual reviewed run identities/gates."""
import copy
from datetime import date, datetime
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import zipfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/verify_pages_recovery.py'
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    import verify_pages_recovery as recovery
except ModuleNotFoundError:
    recovery = None

GATES = [
    "Install pinned image verification backend",
    "Choose independent date maintenance or full discovery",
    "Snapshot Canadian bookings before automated changes",
    "Sync verified artist registry",
    "Apply confirmed private admission before validation",
    "Run all automated tests",
    "Apply curated catalog policy and coverage audit",
    "Apply durable September 12 audit repairs",
    "Remember permanent state pages before date rollover",
    "Remove completed shows from source data",
    "Normalize Sevin schedule from HOG MOB",
    "Apply verified live artist overrides",
    "Restore Deonte Hall artist-submitted show",
    "Apply durable September 13 content repairs",
    "Apply verified Miles Minnick and CJ Emulous fall 2026 repairs",
    "Restore promoter-submitted TRNSCND VA 2026 show",
    "Preserve official Rock the Pines 2027 announcement",
    "Preserve verified EGR and Bizzle event details and artwork",
    "Preserve submitted Man Of FAITH, Southside Joz and Bobby Real Montgomery shows",
    "Preserve verified September 26 concert source corrections",
    "Preserve October 2 verified artist intake concerts",
    "Preserve October 3 concert corrections and artist identity",
    "Restore reviewed missing show information",
    "Validate refreshed source before publication",
    "Reconcile durable event identities before page generation",
    "Prepare verified multi-page production site",
    "Build production SEO architecture",
    "Apply approved SEO experience",
    "Apply verified live artist artifact cleanup",
    "Remove completed shows from deployment artifact",
    "Verify production SEO architecture",
    "Verify complete deployment artifact",
    "Finalize and audit live event images",
    "Apply final SEO indexing policy",
    "Apply approved mobile-first live redesign",
    "Preserve permanent state navigation and complete archives",
    "Refresh final production indexing after redesign",
    "Restore approved artist schedule details after redesign",
    "Apply approved live artist submission form",
    "Verify approved live redesign and production identity",
    "Verify artist details in the final production artifact",
    "Verify permanent state pages in the final production artifact",
    "Label private bookings on all show cards",
    "Apply approved fan-first discovery layout",
    "Verify promoted production discovery",
    "Display verified sold-out artwork notices",
    "Apply and verify approved artist discovery and Google events",
    "Publish and verify approved show information",
    "Verify approved game behavior",
    "Publish isolated CHH Show Night game",
    "Verify current dates counts and all artist next shows",
    "Verify private bookings remain listed with admission labels",
    "Verify Canadian bookings survived the complete build",
    "Preserve published URLs and record real page changes"
]
SHA = '32c3e50439a977c6f5846af540812a28395f80a6'
ZIP_SHA = '6689f50ed36d02811dcd7cc4270209a086640f46b4d2b501f97dbc8d0b34bf5e'


class PagesRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(recovery, 'Missing exact-artifact recovery verifier')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tar = Path(self.temp.name) / 'artifact.tar'
        self.write_tar()
        self.manifest = {
            'repository': '84lorinw-a11y/kingdom-circuit', 'datePacific': '2026-11-07',
            'runId': 42410736914, 'jobId': 128518099918, 'sourceSha': SHA, 'runAttempt': 1,
            'artifactId': 13589113167, 'artifactName': 'github-pages-42410736914-1',
            'tarSha256': self.digest(), 'artifactDigest': 'sha256:' + ZIP_SHA,
            'requiredGateNames': GATES.copy(),
        }
        self.run = {'id': 42410736914, 'head_sha': SHA, 'head_branch': 'main',
                    'run_attempt': 1, 'status': 'completed', 'conclusion': 'failure',
                    'repository': {'full_name': '84lorinw-a11y/kingdom-circuit'}}
        steps = [{'name': name, 'status': 'completed', 'conclusion': 'success', 'number': n}
                 for n, name in enumerate(GATES + ['Upload Pages artifact'], 1)]
        steps += [{'name': 'Deploy to GitHub Pages', 'status': 'completed', 'conclusion': 'failure', 'number': 56},
                  {'name': 'Save successful publication URL history', 'status': 'completed', 'conclusion': 'skipped', 'number': 57},
                  {'name': 'Keep calendar freshness verification results', 'status': 'completed', 'conclusion': 'success', 'number': 58}]
        self.job = {'id': 128518099918, 'run_id': 42410736914, 'run_attempt': 1,
                    'head_sha': SHA, 'status': 'completed', 'conclusion': 'failure', 'steps': steps}
        self.jobs = {'total_count': 1, 'jobs': [self.job]}
        self.artifact = {'id': 13589113167, 'name': 'github-pages-42410736914-1',
                         'expired': False, 'digest': 'sha256:' + ZIP_SHA, 'size_in_bytes': 572395421,
                         'workflow_run': {'id': 42410736914, 'head_sha': SHA, 'head_branch': 'main'}}

    def write_tar(self, extra=None):
        with tarfile.open(self.tar, 'w') as out:
            for name, data in [('index.html', b'<h1>Reviewed artifact</h1>'), ('CNAME', b'kingdomcircuit.com\n'), ('.nojekyll', b'')]:
                item = tarfile.TarInfo(name); item.size = len(data); item.mode = 0o644
                out.addfile(item, io.BytesIO(data))
            if extra is not None:
                out.addfile(extra, io.BytesIO(b'x' * extra.size) if extra.isfile() else None)

    def digest(self):
        return hashlib.sha256(self.tar.read_bytes()).hexdigest()

    def result(self, today=date(2026, 11, 7)):
        return recovery.verify(self.manifest, self.run, self.jobs, self.artifact, self.tar, today=today)

    def reject(self, phrase):
        result = self.result()
        self.assertFalse(result['passed'])
        self.assertTrue(any(phrase in x['check'] for x in result['results'] if not x['passed']), result)

    def test_reviewed_actual_run_identifiers_and_all54_gates_with_safe_tar_pass(self):
        result = self.result()
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['requiredGatesPassed'], 54)
        self.assertEqual(result['tarSha256'], self.digest())
        self.assertFalse(result['livePublicationVerified'])

    def test_run_or_job_wrong_source_sha_is_rejected(self):
        for row in [self.run, self.job]:
            with self.subTest(row='run' if row is self.run else 'job'):
                old = row['head_sha']; row['head_sha'] = '0' * 40
                self.reject('source'); row['head_sha'] = old

    def test_original_run_and_job_identity_cannot_be_substituted(self):
        for row, key in [(self.run, 'id'), (self.job, 'id'), (self.job, 'run_id')]:
            with self.subTest(key=key, row=row.get('id')):
                old = row[key]; row[key] += 1; self.reject('identity'); row[key] = old

    def test_other_attempt_or_repository_or_branch_is_rejected(self):
        self.run['run_attempt'] = 2; self.reject('identity'); self.run['run_attempt'] = 1
        self.job['run_attempt'] = 2; self.reject('identity'); self.job['run_attempt'] = 1
        self.run['repository']['full_name'] = 'other/repository'; self.reject('identity')

    def test_original_run_must_be_completed_failure(self):
        self.run['status'] = 'in_progress'; self.reject('completed'); self.run['status'] = 'completed'
        self.run['conclusion'] = 'success'; self.reject('completed')

    def test_failed_or_skipped_required_gate_is_rejected(self):
        for state in ['failure', 'skipped']:
            self.job['steps'][0]['conclusion'] = state; self.reject('required_gates')

    def test_missing_or_duplicate_required_gate_is_rejected(self):
        old = self.job['steps'].pop(0); self.reject('required_gates')
        self.job['steps'].insert(0, old); self.job['steps'].insert(0, dict(old)); self.reject('required_gates')

    def test_manifest_cannot_reduce_the54_required_gates(self):
        self.manifest['requiredGateNames'].pop(); self.reject('manifest')

    def test_upload_must_succeed_after_required_gates(self):
        upload = next(s for s in self.job['steps'] if s['name'] == 'Upload Pages artifact')
        upload['conclusion'] = 'failure'; self.reject('upload')
        upload['conclusion'] = 'success'; upload['number'] = 1; self.reject('ordering')

    def test_deploy_pages_must_be_the_only_failed_step(self):
        self.job['steps'].append({'name': 'Unrelated check', 'status': 'completed', 'conclusion': 'failure', 'number': 59})
        self.reject('only_pages')

    def test_failed_pages_step_cannot_be_missing_or_successful(self):
        deploy = next(s for s in self.job['steps'] if s['name'] == 'Deploy to GitHub Pages')
        deploy['conclusion'] = 'success'; self.reject('only_pages')

    def test_wrong_artifact_id_name_digest_or_source_run_is_rejected(self):
        for key, bad in [('id', 12), ('name', 'other-artifact'), ('digest', 'sha256:' + '0' * 64)]:
            with self.subTest(key=key):
                old = self.artifact[key]; self.artifact[key] = bad; self.reject('artifact'); self.artifact[key] = old
        self.artifact['workflow_run']['id'] = 12; self.reject('artifact')

    def test_expired_artifact_is_rejected(self):
        self.artifact['expired'] = True; self.reject('artifact')

    def test_changed_tar_bytes_are_rejected_even_if_tar_parser_accepts_them(self):
        with self.tar.open('ab') as out: out.write(b'changed')
        self.reject('tar_sha256')

    def test_native_zip_tar_member_can_be_verified_without_disk_extraction(self):
        wrapper = Path(self.temp.name) / 'download.zip'
        with zipfile.ZipFile(wrapper, 'w') as out:
            out.write(self.tar, 'artifact.tar')
        self.manifest['artifactDigest'] = self.artifact['digest'] = 'sha256:' + hashlib.sha256(wrapper.read_bytes()).hexdigest()
        result = recovery.verify(self.manifest, self.run, self.jobs, self.artifact, wrapper, today=date(2026, 11, 7))
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['tarSha256'], self.digest())

    def test_wrong_day_and_changed_manifest_day_are_rejected(self):
        self.assertFalse(self.result(today=date(2026, 11, 8))['passed'])
        self.manifest['datePacific'] = '2026-11-08'
        self.assertFalse(self.result(today=date(2026, 11, 8))['passed'])

    def test_safe_hash_does_not_allow_tar_traversal_or_absolute_paths(self):
        for name in ['../outside', '/absolute', 'bad\\path']:
            with self.subTest(name=name):
                item = tarfile.TarInfo(name); item.size = 1; item.mode = 0o644
                self.write_tar(item); self.manifest['tarSha256'] = self.digest(); self.reject('tar_safety')

    def test_safe_hash_does_not_allow_links_duplicate_names_or_unreadable_files(self):
        link = tarfile.TarInfo('link'); link.type = tarfile.SYMTYPE; link.linkname = '/etc/passwd'
        duplicate = tarfile.TarInfo('index.html'); duplicate.mode = 0o644
        private = tarfile.TarInfo('private'); private.mode = 0o600
        for item in [link, duplicate, private]:
            with self.subTest(name=item.name):
                self.write_tar(item); self.manifest['tarSha256'] = self.digest(); self.reject('tar_safety')

    def test_cli_writes_safe_receipt_for_the_real_file_boundary(self):
        import subprocess
        paths = {}
        for name, value in [('manifest', self.manifest), ('run', self.run), ('jobs', self.jobs), ('artifact', self.artifact)]:
            paths[name] = Path(self.temp.name) / (name + '.json'); paths[name].write_text(json.dumps(value))
        output = Path(self.temp.name) / 'receipt.json'
        command = [sys.executable, str(SCRIPT), '--manifest', str(paths['manifest']), '--run-json', str(paths['run']),
                   '--jobs-json', str(paths['jobs']), '--artifact-json', str(paths['artifact']), '--tar', str(self.tar), '--output', str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        allowed_today = datetime.now(ZoneInfo('America/Los_Angeles')).date() == date(2026, 11, 7)
        self.assertEqual(result.returncode, 0 if allowed_today else 1, result.stdout + result.stderr)
        receipt = json.loads(output.read_text()); self.assertEqual(receipt['passed'], allowed_today); self.assertFalse(receipt['livePublicationVerified'])
        result = subprocess.run(command + ['--today', '2026-11-07'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
