import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "apply_curated_catalog_policy",
    ROOT / "scripts" / "apply_curated_catalog_policy.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CuratedCatalogPolicyTests(unittest.TestCase):
    def test_silver_spring_fragments_are_recognized(self):
        for artist in ("Hulvey", "indie tribe.", "Kijan Boone"):
            event = {
                "startDate": "2026-09-08",
                "venue": "The Fillmore Silver Spring",
                "address": "8656 Colesville Rd",
                "artists": [artist],
            }
            self.assertTrue(MODULE.is_hulvey_silver_spring_fragment(event))

    def test_silver_spring_verified_lineup_is_complete(self):
        event = MODULE.HULVEY_SILVER_SPRING
        self.assertEqual("Hulvey", event["headliner"])
        self.assertEqual(
            {"Hulvey", "indie tribe.", "Kijan Boone"},
            set(event["artists"]),
        )
        self.assertEqual("Silver Spring", event["city"])
        self.assertEqual("MD", event["state"])


if __name__ == "__main__":
    unittest.main()
