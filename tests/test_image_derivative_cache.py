"""Exercise reusable image bytes without bypassing the public image floor."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import optimize_public_images as optimizer
import verify_public_performance as performance


class ImageDerivativeCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / "cache"
        self.build_number = 0

    def image(self, color, size=(80, 60)):
        from PIL import Image
        output = io.BytesIO()
        Image.new("RGB", size, color).save(output, "PNG")
        return output.getvalue()

    def build(self, images=None, cache=True, extra=(), identity=None, fail_render=False):
        self.build_number += 1
        site = self.root / f"site{self.build_number}"
        site.mkdir()
        images = images or {"one.png": self.image("red")}
        for name, data in images.items():
            (site / name).write_bytes(data)
        (site / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
        (site / "index.html").write_text("".join(
            f'<img class="artist-photo" src="/{name}">' for name in [*images, "logo.svg"]))
        (site / "events.json").write_text(json.dumps([{"image": "/" + next(iter(images))}]))
        backend = optimizer.PillowBackend()
        argv = [str(site), "--offline", "--widths", "16,32,64", *extra]
        if cache:
            argv.extend(["--cache-dir", str(self.cache)])
        stream = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(optimizer, "choose_backend", return_value=backend))
            render = stack.enter_context(patch.object(
                backend, "render", side_effect=optimizer.OptimizationFailure("test-failure")
                if fail_render else backend.render))
            if identity is not None:
                stack.enter_context(patch.object(optimizer, "derivative_cache_identity", return_value=identity))
            stack.enter_context(contextlib.redirect_stdout(stream))
            self.assertEqual(0, optimizer.main(argv))
        for name, data in images.items():
            self.assertEqual(data, (site / name).read_bytes())
        summary = json.loads(stream.getvalue())
        files = {path.relative_to(site).as_posix(): path.read_bytes()
                 for path in site.rglob("*") if path.is_file()}
        return site, summary, files, render.call_count

    def floor_errors(self, site):
        errors, _, _ = performance.verify(site, "/", optimizer.DEFAULT_ORIGIN,
                                          False, 0, None, 5 * 1024 * 1024, 192 * 1024 * 1024)
        return [error for error in errors if "every local source must be optimized" in error]

    def test_cold_warm_and_disabled_builds_have_identical_public_bytes(self):
        images = {"one.png": self.image("red"), "alias.png": self.image("red"), "two.png": self.image("blue")}
        cold, cold_summary, cold_files, cold_calls = self.build(images)
        warm, warm_summary, warm_files, warm_calls = self.build(images)
        _, plain_summary, plain_files, plain_calls = self.build(images, cache=False)
        self.assertEqual((2, 0, 2), (cold_calls, warm_calls, plain_calls))
        self.assertEqual(cold_files, warm_files)
        self.assertEqual(cold_files, plain_files)
        self.assertEqual(2, warm_summary["derivativeCache"]["hits"])
        self.assertEqual(2, cold_summary["derivativeCache"]["misses"])
        self.assertFalse(plain_summary["derivativeCache"]["enabled"])
        report = json.loads((self.root / "image-cache-report.json").read_text())
        self.assertEqual(warm_summary["derivativeCache"], report["derivativeCache"])
        self.assertEqual(3, report["localSources"])
        self.assertGreaterEqual(report["durationSeconds"], 0)
        self.assertNotIn("image-cache-report.json", warm_files)
        for summary in (cold_summary, warm_summary, plain_summary):
            self.assertEqual(3, summary["optimizedLocalSources"])
            self.assertEqual(1, summary["preservedVectorSources"])
            self.assertEqual(sum(map(len, images.values())), summary["bytesRead"])
        self.assertEqual([], self.floor_errors(cold))
        self.assertEqual([], self.floor_errors(warm))

    def test_only_changed_source_is_rendered_and_obsolete_entries_are_pruned(self):
        self.build({"one.png": self.image("red"), "two.png": self.image("blue")})
        ignored = self.cache / "keep-owner-file.txt"
        ignored.write_text("keep")
        _, summary, _, calls = self.build({"one.png": self.image("green"), "two.png": self.image("blue")})
        self.assertEqual(1, calls)
        self.assertEqual(1, summary["derivativeCache"]["hits"])
        self.assertEqual(1, summary["derivativeCache"]["prunedEntries"])
        self.assertEqual(2, len(list(self.cache.glob("*.zip"))))
        self.assertEqual("keep", ignored.read_text())

    def test_recipe_and_version_changes_invalidate_but_public_base_does_not(self):
        identity = {"optimizer": "v1", "encoder": "pillow1", "framing": "crop1"}
        self.build(identity=identity)
        for extra, changed in [
            (("--quality", "82"), identity),
            (("--widths", "16,48,64"), identity),
            ((), {**identity, "optimizer": "v2"}),
            ((), {**identity, "encoder": "pillow2"}),
            ((), {**identity, "framing": "crop2"}),
        ]:
            with self.subTest(extra=extra, identity=changed):
                _, summary, _, calls = self.build(extra=extra, identity=changed)
                self.assertEqual(1, calls)
                self.assertEqual(0, summary["derivativeCache"]["hits"])
        _, summary, files, calls = self.build(extra=("--base", "/new/"), identity=changed)
        self.assertEqual(0, calls)
        self.assertEqual(1, summary["derivativeCache"]["hits"])
        self.assertIn(b'/new/assets/optimized/', files["index.html"])

    def test_identity_covers_implementation_framing_and_encoder_codecs(self):
        identity = optimizer.derivative_cache_identity(optimizer.PillowBackend())
        self.assertEqual(hashlib.sha256(Path(optimizer.__file__).read_bytes()).hexdigest(), identity["optimizerSha256"])
        self.assertEqual(hashlib.sha256(optimizer.PORTRAIT_FRAMING_PATH.read_bytes()).hexdigest(), identity["portraitFramingSha256"])
        self.assertTrue(identity["pillow"])
        self.assertTrue(identity["codecs"]["webp"])
        self.assertEqual({"PIL._imaging", "PIL._webp"}, set(identity["binaries"]))

    def corrupt(self, mode):
        entry = next(self.cache.glob("*.zip"))
        if mode == "truncated":
            entry.write_bytes(entry.read_bytes()[:40])
            return
        with zipfile.ZipFile(entry) as archive:
            payloads = {name: archive.read(name) for name in archive.namelist()}
        metadata = json.loads(payloads["entry.json"])
        image_name = next(name for name in payloads if name != "entry.json")
        if mode == "hash":
            from PIL import Image
            replacement = io.BytesIO()
            Image.new("RGB", tuple(metadata["variants"][image_name]["dimensions"]), "green").save(replacement, "WEBP")
            payloads[image_name] = replacement.getvalue()
            metadata["variants"][image_name]["bytes"] = len(payloads[image_name])
        elif mode == "incomplete":
            del payloads[image_name]
        elif mode == "dimensions":
            metadata["variants"][image_name]["dimensions"][1] += 1
        elif mode == "decode":
            payloads[image_name] = payloads[image_name][:30]
            metadata["variants"][image_name]["bytes"] = len(payloads[image_name])
            metadata["variants"][image_name]["sha256"] = hashlib.sha256(payloads[image_name]).hexdigest()
        elif mode == "traversal":
            payloads["../outside.txt"] = b"must not extract"
        elif mode == "recipe":
            metadata["recipe"]["quality"] += 1
        payloads["entry.json"] = json.dumps(metadata).encode()
        if mode == "deep_json":
            payloads["entry.json"] = b"[" * 20000 + b"]" * 20000
        with zipfile.ZipFile(entry, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in payloads.items():
                if mode == "member_symlink" and name == image_name:
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, data)
                else:
                    archive.writestr(name, data)

    def test_corrupt_or_incomplete_archives_regenerate_the_whole_set(self):
        for mode in ("truncated", "hash", "incomplete", "dimensions", "decode", "traversal", "recipe", "member_symlink", "deep_json"):
            with self.subTest(mode=mode):
                self.cache = self.root / ("cache_" + mode)
                _, _, expected, _ = self.build()
                self.corrupt(mode)
                site, summary, actual, calls = self.build()
                self.assertEqual(1, calls)
                self.assertEqual(1, summary["derivativeCache"]["invalidEntries"])
                self.assertEqual(expected, actual)
                self.assertEqual([], self.floor_errors(site))
                self.assertFalse((self.root / "outside.txt").exists())
                _, summary, _, calls = self.build()
                self.assertEqual((1, 0), (summary["derivativeCache"]["hits"], calls))

    def test_archive_symlink_does_not_read_or_replace_its_target(self):
        _, _, expected, _ = self.build()
        entry = next(self.cache.glob("*.zip"))
        external = self.root / "external.zip"
        entry.rename(external)
        original = external.read_bytes()
        entry.symlink_to(external)
        _, summary, actual, calls = self.build()
        self.assertEqual(1, calls)
        self.assertEqual(1, summary["derivativeCache"]["invalidEntries"])
        self.assertEqual(original, external.read_bytes())
        self.assertFalse(entry.is_symlink())
        self.assertEqual(expected, actual)

    def test_unavailable_cache_keeps_rendering_and_public_cache_path_is_refused(self):
        self.cache.write_text("not a directory")
        site, summary, _, calls = self.build()
        self.assertEqual(1, calls)
        self.assertFalse(summary["derivativeCache"]["enabled"])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, optimizer.main([str(site), "--cache-dir", str(site / "cache")]))
            outside_alias = self.root / "public_alias"
            outside_alias.symlink_to(site, target_is_directory=True)
            self.assertEqual(2, optimizer.main([str(site), "--cache-dir", str(outside_alias)]))
        self.cache = self.root / "cache_alias"
        target = self.root / "external_cache"
        target.mkdir()
        self.cache.symlink_to(target, target_is_directory=True)
        _, summary, _, calls = self.build()
        self.assertEqual(1, calls)
        self.assertFalse(summary["derivativeCache"]["enabled"])
        self.assertEqual([], list(target.iterdir()))

    def test_cache_capacity_is_bounded_and_failed_run_does_not_prune(self):
        with patch.object(optimizer, "MAX_CACHE_BYTES", 1):
            site, summary, _, calls = self.build()
        self.assertEqual(1, calls)
        self.assertEqual(1, summary["derivativeCache"]["capacitySkips"])
        self.assertEqual([], list(self.cache.iterdir()))
        self.assertEqual([], self.floor_errors(site))
        self.build()
        existing = {path.name: path.read_bytes() for path in self.cache.iterdir()}
        site, summary, _, _ = self.build({"changed.png": self.image("blue")}, fail_render=True)
        self.assertEqual(1, summary["failures"])
        self.assertTrue(self.floor_errors(site))
        self.assertEqual(existing, {path.name: path.read_bytes() for path in self.cache.iterdir()})

    def test_cache_write_failure_does_not_turn_rendered_sources_into_failures(self):
        real_replace = optimizer.os.replace

        def replace(source, destination):
            if Path(destination).suffix == ".zip":
                raise PermissionError("Cache became read only")
            return real_replace(source, destination)

        with patch.object(optimizer.os, "replace", side_effect=replace):
            site, summary, _, calls = self.build()
        self.assertEqual(1, calls)
        self.assertEqual(0, summary["failures"])
        self.assertEqual(1, summary["derivativeCache"]["writeFailures"])
        self.assertEqual([], list(self.cache.iterdir()))
        self.assertEqual([], self.floor_errors(site))

    def test_disabled_cache_does_not_write_external_report(self):
        self.build(cache=False)
        self.assertFalse((self.root / "image-cache-report.json").exists())

    def test_warm_cache_does_not_bypass_current_source_byte_limit(self):
        images = {"one.png": self.image("red") + bytes(70 * 1024)}
        self.build(images)
        site, summary, _, calls = self.build(images, extra=("--max-image-bytes", str(64 * 1024)))
        self.assertEqual(0, calls)
        self.assertEqual(0, summary["derivativeCache"]["hits"])
        self.assertEqual(1, summary["failures"])
        self.assertTrue(self.floor_errors(site))


if __name__ == "__main__":
    unittest.main()
