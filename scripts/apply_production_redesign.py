"""Run the approved redesign with production event identity matching."""

import importlib.util
import pathlib
import re
import sys


UNKNOWN_LOCATIONS = {"location not confirmed", "location to be announced"}


def configure_new_show_keys(redesign):
    """Match unknown-location cards to blank source cities without changing HTML."""
    original = redesign.card_source_key

    def card_source_key(card):
        key = original(card)
        opening = card[:card.find(">") + 1]
        empty_state = re.search(r'''\sdata-state=(?:""|'')(?=\s|>)''', opening)
        location = re.search(r'<dt>\s*Location\s*</dt>\s*<dd>(.*?)</dd>', card, re.I | re.S)
        if empty_state and location:
            text = redesign.normalized_key(redesign.clean_text(location.group(1)))
            if text in UNKNOWN_LOCATIONS and key[2] == text:
                return key[0], key[1], ""
        return key

    redesign.card_source_key = card_source_key


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit("Usage: apply_production_redesign.py APPROVED_SCRIPT SITE [redesign options]")
    path = pathlib.Path(args[0]).resolve()
    spec = importlib.util.spec_from_file_location("approved_production_redesign", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load approved redesign: {path}")
    redesign = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(redesign)
    missing = [
        name for name in ("main", "card_source_key", "clean_text", "normalized_key")
        if not callable(getattr(redesign, name, None))
    ]
    if missing:
        raise SystemExit("Approved redesign interface missing callable(s): " + ", ".join(missing))
    configure_new_show_keys(redesign)
    original_argv = sys.argv
    try:
        sys.argv = [str(path), *args[1:]]
        return redesign.main()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    raise SystemExit(main())
