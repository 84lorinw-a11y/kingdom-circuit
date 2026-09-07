from __future__ import annotations

import pathlib
import sys

from add_past_show_archives import apply_past_show_archives
from finalize_seo_indexing_core import main as finalize_main


def main() -> None:
    try:
        index = sys.argv.index("--site")
        root = pathlib.Path(sys.argv[index + 1]).resolve()
    except (ValueError, IndexError):
        raise SystemExit("--site is required")

    report = apply_past_show_archives(root)
    print("Past show archive:", report)
    finalize_main()


if __name__ == "__main__":
    main()
