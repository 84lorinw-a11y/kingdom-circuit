from __future__ import annotations

import datetime as dt
import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import prune_past_events as pruning


class PrunePastEventsTests(unittest.TestCase):
    def test_default_cutoff_keeps_yesterday_for_one_day(self) -> None:
        class FrozenDateTime(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 9, 21, 12, 0, tzinfo=tz)

        with mock.patch.object(pruning, "datetime", FrozenDateTime):
            self.assertEqual("2026-09-20", pruning.today_cutoff())

        self.assertFalse(
            pruning.is_past_event({"startDate": "2026-09-20"}, "2026-09-20")
        )
        self.assertTrue(
            pruning.is_past_event({"startDate": "2026-09-19"}, "2026-09-20")
        )


if __name__ == "__main__":
    unittest.main()
