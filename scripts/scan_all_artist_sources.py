#!/usr/bin/env python3
"""Compatibility entrypoint for the expanded all-artist discovery scan.

The implementation remains importable from scan_all_artist_sources_legacy while
command-line execution now routes through run_full_discovery_scan so Bandsintown
uses the structured REST collector instead of robot-blocked public HTML.
"""
from scan_all_artist_sources_legacy import *  # noqa: F401,F403


if __name__ == "__main__":
    from run_full_discovery_scan import main as run_full_discovery

    raise SystemExit(run_full_discovery())
