"""Curve preview math and quality diagrams match FFmpeg options."""
import io
import math
import unittest

from audiocoder.fade import FADE_CURVES, fade_envelope, fade_gain
from audiocoder.fade_preview import draw_fade_diagrams


class FadeCurvesTests(unittest.TestCase):
    def test_all_curves_finite_monotonic_and_endpoint_consistent(self):
        for curve in FADE_CURVES:
            with self.subTest(curve=curve):
                values = [fade_gain(curve, i / 1000) for i in range(1001)]
                self.assertEqual(values[0], 0)
                self.assertEqual(values[-1], 1)
                self.assertTrue(all(0 <= v <= 1 and math.isfinite(v) for v in values))
                self.assertTrue(all(a <= b + 1e-12 for a, b in zip(values, values[1:])))

    def test_ffmpeg_exact_log_formula(self):
        self.assertAlmostEqual(fade_gain("log", .01), .6)
        self.assertAlmostEqual(fade_gain("log", .1), .8)
        self.assertAlmostEqual(fade_gain("log", 1e-5), 0)

    def test_other_source_formulas(self):
        self.assertAlmostEqual(fade_gain("tri", .5), .5)
        self.assertAlmostEqual(fade_gain("qua", .5), .25)
        self.assertAlmostEqual(fade_gain("cub", .5), .125)
        self.assertAlmostEqual(fade_gain("hsin", .5), .5)
        self.assertAlmostEqual(fade_gain("qsin", .5), math.sqrt(.5))
        self.assertAlmostEqual(fade_gain("ipar", .5), .75)

    def test_different_independent_curves(self):
        self.assertAlmostEqual(fade_envelope("log", "qua", .01),
                               fade_gain("log", .05))
        self.assertAlmostEqual(fade_envelope("log", "qua", .9),
                               fade_gain("qua", .5))
        self.assertEqual(fade_envelope("log", "qua", .5), 1.0)

    def test_reject_bad_curve(self):
        with self.assertRaises(ValueError):
            fade_gain("wrong", .3)

    def test_fade_charts_use_same_muted_palette_as_editor(self):
        from PIL import ImageColor
        from audiocoder.palette import (FADE_CHART_BACKGROUND,
                                         FADE_CHART_LINE, FADE_CHART_TEXT)
        for dark in (False, True):
            with self.subTest(dark=dark):
                img = draw_fade_diagrams("log", "cub",
                                         width=600, height=170, dark=dark)
                self.assertEqual(
                    img.getpixel((0, 0)),
                    ImageColor.getrgb(FADE_CHART_BACKGROUND[int(dark)]))
                self.assertNotEqual(
                    FADE_CHART_LINE[int(dark)],
                    FADE_CHART_BACKGROUND[int(dark)])
                self.assertNotEqual(
                    FADE_CHART_TEXT[int(dark)],
                    FADE_CHART_BACKGROUND[int(dark)])

    def test_graph_preview_has_real_axes_and_antialias(self):
        img = draw_fade_diagrams("log", "cub", width=800, height=180)
        self.assertEqual(img.size, (800, 180))
        self.assertEqual(img.mode, "RGB")
        target = io.BytesIO()
        img.save(target, format="PNG")
        self.assertGreater(len(target.getvalue()), 10000)
        self.assertNotEqual(img.getpixel((10, 10)), img.getpixel((200, 90)))


if __name__ == "__main__":
    unittest.main()
