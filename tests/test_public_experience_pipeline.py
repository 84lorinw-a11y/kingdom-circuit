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
import verify_public_performance as performance_verifier  # noqa: E402
import verify_public_ux as ux_verifier  # noqa: E402


class PublicExperiencePipelineTests(unittest.TestCase):
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
