"""Waveform corner compositing must preserve the waveform and theme."""
import unittest

from PIL import Image

from audiocoder.waveform_view import round_waveform_image, _rounded_mask


class RoundedWaveformTests(unittest.TestCase):
    def test_corners_take_parent_color_and_center_remains_waveform(self):
        source = Image.new("RGB", (160, 90), "#1974C9")
        result = round_waveform_image(source, "#DBDBDB", radius=14)
        self.assertEqual(result.size, source.size)
        self.assertEqual(result.getpixel((0, 0)), (219, 219, 219))
        self.assertEqual(result.getpixel((159, 0)), (219, 219, 219))
        self.assertEqual(result.getpixel((0, 89)), (219, 219, 219))
        self.assertEqual(result.getpixel((159, 89)), (219, 219, 219))
        self.assertEqual(result.getpixel((80, 45)), (25, 116, 201))
        self.assertEqual(result.getpixel((80, 0)), (25, 116, 201))

    def test_theme_changes_outer_corners_only(self):
        wave = Image.new("RGB", (160, 90), "#1974C9")
        light = round_waveform_image(wave, "#DBDBDB")
        dark = round_waveform_image(wave, "#2B2B2B")
        self.assertNotEqual(light.getpixel((0, 0)), dark.getpixel((0, 0)))
        self.assertEqual(light.getpixel((80, 45)), dark.getpixel((80, 45)))

    def test_mask_cache_and_rounded_edge_are_antialiased(self):
        mask = _rounded_mask(160, 90, 14)
        self.assertIs(mask, _rounded_mask(160, 90, 14))
        self.assertEqual(mask.getpixel((0, 0)), 0)
        self.assertEqual(mask.getpixel((80, 0)), 255)
        self.assertTrue(any(0 < v < 255 for v in mask.crop((0, 0, 14, 14)).getdata()))


if __name__ == "__main__":
    unittest.main()
