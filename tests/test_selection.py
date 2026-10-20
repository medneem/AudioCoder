import unittest

from audiocoder.selection import ClipRange, clock


class ClipTests(unittest.TestCase):
    def test_duration_and_boundaries(self):
        clip = ClipRange(1.5, 3.25, 5)
        self.assertAlmostEqual(clip.length, 1.75)
        self.assertEqual(ClipRange(0, 5, 5).length, 5)

    def test_invalid_ranges(self):
        for start, end, duration in [(2, 2, 5), (4, 2, 5), (-1, 2, 5), (0, 6, 5),
                                     (0, 0.01, 5), (0, 1, 0)]:
            with self.subTest(start=start, end=end, duration=duration):
                with self.assertRaises(ValueError):
                    ClipRange(start, end, duration)

    def test_nonfinite(self):
        with self.assertRaises(ValueError):
            ClipRange(0, float("nan"), 100)

    def test_clock(self):
        self.assertEqual(clock(3661.2345), "01:01:01.234")
        self.assertEqual(clock(0), "00:00:00.000")
        with self.assertRaises(ValueError):
            clock(-1)


if __name__ == "__main__":
    unittest.main()
