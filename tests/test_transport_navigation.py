"""Focused navigation and selection-zoom regression tests."""
import unittest

from audiocoder.waveform_navigation import WaveformViewport


class NavigationViewportTests(unittest.TestCase):
    def test_fit_range_shows_entire_selected_clip_with_padding(self):
        viewport = WaveformViewport()
        viewport.fit_range(.25, .40)
        self.assertLess(viewport.start, .25)
        self.assertGreater(viewport.end, .40)
        self.assertLess(viewport.span, .20)

    def test_fit_range_clamps_at_beginning_end_and_zoom_limit(self):
        viewport = WaveformViewport()
        viewport.fit_range(0.0, .025)
        self.assertEqual(viewport.start, 0.0)
        self.assertAlmostEqual(viewport.span, 1 / 16)
        viewport.fit_range(.98, 1.0)
        self.assertAlmostEqual(viewport.end, 1.0)
        viewport.fit_range(0.0, 1.0)
        self.assertEqual((viewport.start, viewport.span), (0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
