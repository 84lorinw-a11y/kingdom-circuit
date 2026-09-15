from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_public_audit_repairs as audit_repairs  # noqa: E402
import apply_public_ux_repairs as ux_repairs  # noqa: E402
import finalize_public_experience as public_pipeline  # noqa: E402
import finalize_seo_indexing as seo_finalizer  # noqa: E402
import verify_public_performance as performance_verifier  # noqa: E402
import verify_public_ux as ux_verifier  # noqa: E402


class PublicExperiencePipelineTests(unittest.TestCase):
    def test_public_ux_preserves_full_artist_directory_controls(self):
        sample = '''<html><head><script src="/assets/artist-filter-fix.js?v=5" defer></script></head>
        <body><main><section data-artist-directory><div class="directory-toolbar">
        <select data-directory-artist-filter></select><select data-directory-state-filter></select>
        <select data-directory-month-filter></select><input data-has-shows-filter checked>
        <button data-directory-reset-filters>Clear filters</button><p data-artist-count>2 artists</p></div>
        <div data-artist-grid><article data-artist-card data-has-shows="true"></article>
        <article data-artist-card data-has-shows="false"></article></div>
        <div data-artist-empty hidden></div></section></main></body></html>'''
        with self.subTest("filter script and complete grid survive finalization"):
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                page = root / "artists" / "index.html"
                page.parent.mkdir(parents=True)
                page.write_text(sample, encoding="utf-8")
                changed, stats = ux_repairs.patch_html(page, root)
                output = page.read_text(encoding="utf-8")
                self.assertTrue(changed)
                self.assertIn("artist-filter-fix.js", output)
                self.assertIn("data-directory-month-filter", output)
                self.assertNotIn("data-kc-inactive-artists", output)
                self.assertEqual(2, output.count("data-artist-card"))
                self.assertEqual({"activeArtists": 1, "totalArtists": 2}, stats)

        self.assertIn(
            "grid-template-columns: repeat(2, minmax(0, 1fr)) !important;",
            ux_repairs.OVERLAY_CSS,
        )
        self.assertIn("grid-auto-rows: 1fr !important;", ux_repairs.OVERLAY_CSS)
        self.assertIn("aspect-ratio: 1 / 1 !important;", ux_repairs.OVERLAY_CSS)
        self.assertIn("margin-top: auto !important;", ux_repairs.OVERLAY_CSS)
        self.assertIn("overflow-wrap: anywhere !important;", ux_repairs.OVERLAY_CSS)
        self.assertIn(
            "body [data-artist-directory] .artist-card-links,\n"
            "  body [data-artist-directory] .seo-card-socials {\n"
            "    display: flex !important;\n"
            "    flex-wrap: nowrap !important;",
            ux_repairs.OVERLAY_CSS,
        )
        self.assertIn("flex: 1 1 36px !important;", ux_repairs.OVERLAY_CSS)
        self.assertIn("max-width: 36px !important;", ux_repairs.OVERLAY_CSS)
        self.assertIn("width: min(22px, 100%) !important;", ux_repairs.OVERLAY_CSS)
        self.assertIn("margin: auto 0 4px !important;", ux_repairs.OVERLAY_CSS)
        self.assertIn(
            "body [data-artist-directory] .artist-card-footer {\n"
            "    margin-top: 8px !important;",
            ux_repairs.OVERLAY_CSS,
        )
        self.assertNotIn("grid-template-columns: repeat(2, 44px) !important;", ux_repairs.OVERLAY_CSS)
        self.assertIn("body .seo-artist-hero .seo-social-links", ux_repairs.OVERLAY_CSS)
        self.assertIn("width: auto !important;", ux_repairs.OVERLAY_CSS)
        self.assertNotIn(
            ".artist-platform-link,\n  .seo-social-link,\n  .seo-social-link-compact,",
            ux_repairs.OVERLAY_CSS,
        )

        simplified = '''<html><head><script src="/assets/artist-filter-fix.js?v=5"></script></head>
        <body><main><section data-artist-directory><div class="directory-toolbar">
        <label><input data-artist-search></label><input data-has-shows-filter>
        <p data-artist-count>2 artists</p></div><div data-artist-grid>
        <article data-artist-card data-has-shows="true"></article>
        <article data-artist-card data-has-shows="false"></article></div>
        <div data-artist-empty hidden></div></section></main></body></html>'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / "artists" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(simplified, encoding="utf-8")
            ux_repairs.patch_html(page, root)
            output = page.read_text(encoding="utf-8")
            self.assertIn("data-directory-artist-filter", output)
            self.assertIn("data-directory-state-filter", output)
            self.assertIn("data-directory-month-filter", output)
            self.assertIn("data-directory-reset-filters", output)
            self.assertIn("data-has-shows-filter type=\"checkbox\" checked", output)
            self.assertIn(">2 artists</p>", output)

    def test_public_ux_refreshes_cached_overlay_assets(self):
        sample = '''<html><head>
        <link rel="stylesheet" href="/assets/site-ux-repairs.css?v=1" data-kc-public-ux-overlay>
        </head><body><main></main>
        <script src="/assets/site-ux-repairs.js?v=1" defer data-kc-public-ux-overlay></script>
        </body></html>'''
        refreshed = ux_repairs.ensure_page_shell(sample)
        self.assertIn(ux_repairs.CSS_HREF, refreshed)
        self.assertIn(ux_repairs.JS_SRC, refreshed)
        self.assertNotIn("site-ux-repairs.css?v=1", refreshed)
        self.assertNotIn("site-ux-repairs.js?v=1", refreshed)
        self.assertEqual(ux_repairs.CSS_HREF, ux_verifier.CSS_HREF)
        self.assertEqual(ux_repairs.JS_SRC, ux_verifier.JS_SRC)

    def test_pipeline_uses_only_the_production_identity(self):
        self.assertEqual("https://kingdomcircuit.com", public_pipeline.PUBLIC_ORIGIN)
        self.assertEqual("/", public_pipeline.PUBLIC_BASE)
        self.assertEqual(public_pipeline.PUBLIC_ORIGIN, audit_repairs.PUBLIC_ORIGIN)
        self.assertEqual(public_pipeline.PUBLIC_BASE, audit_repairs.PUBLIC_BASE)
        self.assertEqual(public_pipeline.PUBLIC_BASE, ux_repairs.PUBLIC_BASE)
        self.assertEqual(public_pipeline.PUBLIC_BASE, ux_verifier.PUBLIC_BASE)
        self.assertEqual(public_pipeline.PUBLIC_ORIGIN, performance_verifier.DEFAULT_ORIGIN)
        self.assertEqual(public_pipeline.PUBLIC_BASE, performance_verifier.DEFAULT_BASE)
        self.assertEqual("Pillow==12.3.0", public_pipeline.PINNED_PILLOW)

    def test_production_security_policy_preserves_analytics(self):
        self.assertIn("https://www.googletagmanager.com", audit_repairs.CSP)
        self.assertIn("https://*.google-analytics.com", audit_repairs.CSP)
        self.assertIn("https://*.analytics.google.com", audit_repairs.CSP)
        self.assertIn("object-src 'none'", audit_repairs.CSP)
        self.assertIn("upgrade-insecure-requests", audit_repairs.CSP)

    def test_mobile_listing_cleanup_preserves_analytics(self):
        sample = '''<html><head>
        <script src="/assets/image-fix.js"></script>
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-N2KK9XF4TJ"></script>
        <script>window.dataLayer=window.dataLayer||[];gtag('config','G-N2KK9XF4TJ');</script>
        </head><body></body></html>'''
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / "index.html"
            page.write_text(sample, encoding="utf-8")
            result = seo_finalizer.apply_p0_mobile_listing_safety(root)
            output = page.read_text(encoding="utf-8")
            self.assertNotIn("/assets/image-fix.js", output)
            self.assertIn("https://www.googletagmanager.com/gtag/js?id=G-N2KK9XF4TJ", output)
            self.assertIn("gtag('config','G-N2KK9XF4TJ')", output)
            self.assertEqual(1, result["pages_cleaned"])

    def test_release_stage_is_limited_to_the_pages_workflow_or_explicit_opt_in(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(public_pipeline.should_finalize_public_experience())
        with patch.dict(
            "os.environ",
            {"GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/update-and-deploy.yml@refs/heads/main"},
            clear=True,
        ):
            self.assertTrue(public_pipeline.should_finalize_public_experience())
        with patch.dict("os.environ", {"KC_FINALIZE_PUBLIC_EXPERIENCE": "1"}, clear=True):
            self.assertTrue(public_pipeline.should_finalize_public_experience())

    def test_pipeline_is_the_last_indexing_stage(self):
        source = (ROOT / "scripts" / "finalize_seo_indexing.py").read_text(encoding="utf-8")
        self.assertIn("from finalize_public_experience import (", source)
        self.assertIn("finalize_public_experience,", source)
        self.assertIn("should_finalize_public_experience,", source)
        self.assertLess(
            source.index("inject_menu_accessibility_sync(root)"),
            source.index("finalize_public_experience(root)"),
        )


if __name__ == "__main__":
    unittest.main()
