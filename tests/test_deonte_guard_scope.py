import unittest
from unittest.mock import patch
from scripts import apply_deonte_hall_submission as repair


class DeonteGuardScopeTests(unittest.TestCase):
    def exercise(self, args):
        names = ('patch_verified_updates', 'patch_artists', 'patch_submitted_event',
                 'verify', 'run_verified_show_repairs', 'run_verified_event_overrides')
        with patch.multiple(repair, **{name: unittest.mock.DEFAULT for name in names}) as mocks:
            self.assertEqual(0, repair.main(args))
            for name in names[:4]:
                mocks[name].assert_called_once_with()
            return {name: mocks[name].call_count for name in names[4:]}

    def test_standalone_guard_cannot_reapply_unrelated_catalog_repairs(self):
        self.assertEqual({'run_verified_show_repairs': 0, 'run_verified_event_overrides': 0},
                         self.exercise(['--submission-only']))

    def test_full_build_keeps_its_existing_verified_repair_sequence(self):
        self.assertEqual({'run_verified_show_repairs': 1, 'run_verified_event_overrides': 1},
                         self.exercise([]))


if __name__ == '__main__':
    unittest.main()
