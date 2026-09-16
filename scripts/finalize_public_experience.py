#!/usr/bin/env python3
"""Apply and verify the final production-only public artifact safeguards."""

from __future__ import annotations

import json
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import apply_echo_nights_official
import apply_public_audit_repairs
import apply_public_ux_repairs
import optimize_public_images
import verify_public_audit
import verify_public_performance
import verify_public_ux


PUBLIC_ORIGIN = "https://kingdomcircuit.com"
PUBLIC_BASE = "/"
PINNED_PILLOW = "Pillow==12.3.0"
TRUTHY = {"1", "true", "yes", "on"}


def env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in TRUTHY


def is_production_workflow() -> bool:
    workflow_ref = os.environ.get("GITHUB_WORKFLOW_REF", "")
    workflow_name = os.environ.get("GITHUB_WORKFLOW", "")
    return (
        "/.github/workflows/update-and-deploy.yml@" in workflow_ref
        or workflow_name == "Update and deploy show calendar"
    )


def should_finalize_public_experience() -> bool:
    """Run only for the Pages release job or an explicit local release build."""
    return env_enabled("KC_FINALIZE_PUBLIC_EXPERIENCE") or is_production_workflow()


def ensure_image_backend() -> str:
    """Guarantee a reproducible WebP encoder on the ephemeral Pages runner."""
    if is_production_workflow():
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--only-binary=:all:",
                PINNED_PILLOW,
            ],
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("Unable to install the pinned production image encoder")
        from PIL import features

        version = importlib.metadata.version("Pillow")
        if version != PINNED_PILLOW.split("==", 1)[1] or not features.check("webp"):
            raise RuntimeError("The pinned Pillow install does not provide WebP support")
        return f"pillow-{version}"

    backend = optimize_public_images.choose_backend()
    return backend.name


def verify_javascript(site: Path) -> list[str]:
    node = os.environ.get("KC_NODE_BINARY") or shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for the production JavaScript syntax gate")

    checked: list[str] = []
    for relative in (Path("app.js"), Path("assets/site-ux-repairs.js")):
        target = site / relative
        if not target.is_file():
            raise RuntimeError(f"Required production JavaScript is missing: {relative}")
        result = subprocess.run(
            [node, "--check", str(target)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            details = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"JavaScript syntax failed for {relative}: {details}")
        checked.append(relative.as_posix())
    return checked


def verify_release_identity(site: Path) -> None:
    expected_files = (
        "index.html",
        "404.html",
        ".nojekyll",
        "CNAME",
        "robots.txt",
        "sitemap.xml",
        "events.json",
        "supplemental-events.json",
        "config/artists.json",
    )
    missing = [relative for relative in expected_files if not (site / relative).is_file()]
    if missing:
        raise RuntimeError("Production artifact is incomplete: " + ", ".join(missing))
    if (site / "CNAME").read_text(encoding="utf-8").strip() != "kingdomcircuit.com":
        raise RuntimeError("Production CNAME does not target kingdomcircuit.com")


def finalize_public_experience(site: Path) -> dict[str, Any]:
    site = site.resolve()
    apply_public_audit_repairs.validate_target(site)
    (site / ".nojekyll").write_text("", encoding="utf-8")
    verify_release_identity(site)

    audit_repairs = apply_public_audit_repairs.apply_repairs(site)

    # This is the final authoritative event-artwork write before responsive
    # image generation. Any earlier generic repair can run, but the optimizer
    # must receive the verified ATK poster as the ECHO Nights source image.
    echo_nights = apply_echo_nights_official.apply(site)

    image_backend = ensure_image_backend()
    remote_images = is_production_workflow() or env_enabled("KC_PUBLIC_IMAGE_REMOTE")
    if env_enabled("KC_PUBLIC_IMAGE_OFFLINE"):
        remote_images = False
    optimizer_args = [
        str(site),
        "--base", PUBLIC_BASE,
        "--origin", PUBLIC_ORIGIN,
        "--workers", "8",
        "--timeout", "12",
        "--wall-time", "360" if remote_images else "180",
    ]
    if not remote_images:
        optimizer_args.append("--offline")
    optimizer_status = optimize_public_images.main(optimizer_args)
    if optimizer_status:
        raise RuntimeError(f"Production image optimization failed with status {optimizer_status}")

    ux_repairs = apply_public_ux_repairs.apply(site)

    audit = verify_public_audit.verify_site(site)
    if audit.failures:
        sample = "; ".join(audit.failures[:20])
        raise RuntimeError(
            f"Production audit failed ({len(audit.failures)} failures across "
            f"{audit.checks} checks): {sample}"
        )

    ux_failures, ux_totals = verify_public_ux.verify(site)
    if ux_failures:
        raise RuntimeError(
            f"Production UX verification failed ({len(ux_failures)} failures): "
            + "; ".join(ux_failures[:20])
        )

    performance_status = verify_public_performance.main(
        [str(site), "--base", PUBLIC_BASE, "--origin", PUBLIC_ORIGIN]
    )
    if performance_status:
        raise RuntimeError(
            f"Production performance verification failed with status {performance_status}"
        )

    javascript = verify_javascript(site)
    verify_release_identity(site)
    return {
        "productionPublicExperience": "verified",
        "imageMode": "remote-and-local" if remote_images else "local-only",
        "imageBackendReady": image_backend,
        "auditChecks": audit.checks,
        "auditRepairs": audit_repairs.get("repairs", {}),
        "echoNightsOfficialPin": echo_nights,
        "ux": ux_repairs,
        "uxVerification": ux_totals,
        "javascriptChecked": javascript,
    }


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise SystemExit("usage: finalize_public_experience.py SITE_OUTPUT")
    report = finalize_public_experience(Path(arguments[0]))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
