import unittest
from audiocoder.waveform_navigation import WaveformViewport


class ViewportTests(unittest.TestCase):
    def test_zoom_anchored_at_mouse_cursor(self):
        view = WaveformViewport()
        focal_before = view.position_at(150, 600)
        view.zoom(2.0, .25)
        self.assertAlmostEqual(view.position_at(150, 600), focal_before)
        self.assertEqual(view.zoom_level, 2.0)

    def test_zoom_limits_and_reset(self):
        view = WaveformViewport()
        view.zoom(1000)
        self.assertEqual(view.zoom_level, 16.0)
        view.zoom(.00001)
        self.assertEqual(view.zoom_level, 1.0)
        self.assertEqual(view.start, 0.0)
        view.zoom(4)
        view.reset()
        self.assertEqual((view.start, view.end), (0.0, 1.0))

    def test_right_drag_pans_both_directions(self):
        view = WaveformViewport()
        view.zoom(4, .5)
        start = view.start
        view.pan(-100, 400)
        self.assertAlmostEqual(view.start, start + 100 / 400 * .25)
        view.pan(100, 400)
        self.assertAlmostEqual(view.start, start)

    def test_pan_clamps_at_file_boundaries(self):
        view = WaveformViewport()
        view.zoom(16, .5)
        view.pan(10000, 600)
        self.assertEqual(view.start, 0)
        view.pan(-10000, 600)
        self.assertAlmostEqual(view.end, 1)

    def test_screen_coordinate_is_full_audio_fraction(self):
        view = WaveformViewport()
        view.zoom(4, .5)
        midpoint = view.position_at(320, 640)
        self.assertAlmostEqual(midpoint, .5)
        self.assertAlmostEqual(view.x_at(.5, 640), 320)
        self.assertEqual(view.position_at(-100, 640), view.start)
        self.assertEqual(view.position_at(10000, 640), view.end)

    def test_invalid_zoom(self):
        with self.assertRaises(ValueError):
            WaveformViewport().zoom(0)


if __name__ == "__main__":
    unittest.main()
