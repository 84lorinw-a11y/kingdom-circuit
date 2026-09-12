from __future__ import annotations

import pathlib
import sys

from add_past_show_archives import apply_past_show_archives
from finalize_seo_indexing_core import main as finalize_main
from fix_seo_audit import apply_seo_audit_fixes
from harden_public_artifact import harden


def main() -> None:
    try:
        index = sys.argv.index("--site")
        root = pathlib.Path(sys.argv[index + 1]).resolve()
    except (ValueError, IndexError):
        raise SystemExit("--site is required")

    report = apply_past_show_archives(root)
    print("Past show archive:", report)
    seo_report = apply_seo_audit_fixes(root)
    print("SEO audit fixes:", seo_report)
    finalize_main()
    public_report = harden(root)
    print("Public artifact prepared:", public_report)


if __name__ == "__main__":
    main()
