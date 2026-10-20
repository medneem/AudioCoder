"""The same version-number rules used by FlacSplitter."""

import unittest

from scripts.stamp_version import make_version, windows_version_info


class VersionTests(unittest.TestCase):
    def test_run_number_becomes_patch(self):
        self.assertEqual(make_version("0.1", "39"), "0.1.39")
        self.assertIn("(0, 1, 39, 0)", windows_version_info("0.1.39"))

    def test_invalid_runs(self):
        for run in ("0", "abc", "-1", "65536"):
            with self.subTest(run=run), self.assertRaises(ValueError):
                make_version("0.1", run)


if __name__ == "__main__":
    unittest.main()
