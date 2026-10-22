"""The muted theme stays legible and is applied consistently everywhere."""
import json
import unittest
from pathlib import Path

from audiocoder.palette import (
    ACCENT, CARD, CARD_BORDER, FADE_CARD, FADE_BORDER, WINDOW, EDITOR,
    BUTTON_SECONDARY, BUTTON_PRIMARY, BUTTON_SECONDARY_TEXT,
    BUTTON_PRIMARY_TEXT, MENU_BG, MENU_TEXT, MENU_ARROW, BUTTON_BORDER,
    CANCEL_BG, CANCEL_TEXT,
    ZOOM_ROW, WAVE_BACKGROUND, WAVE_SELECTION, WAVE_ACTIVE,
    FADE_CHART_BACKGROUND, FADE_CHART_LINE, theme_path,
    theme_color, contrast_ratio,
)


class MutedPaletteTests(unittest.TestCase):
    def test_theme_is_bundled_as_local_json(self):
        path = theme_path()
        self.assertTrue(path.is_file(), f"Missing CustomTkinter theme file {path}")
        theme = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(tuple(theme["CTk"]["fg_color"]), WINDOW)
        self.assertEqual(tuple(theme["CTkButton"]["fg_color"]), BUTTON_SECONDARY)
        self.assertEqual(tuple(theme["CTkButton"]["text_color"]), BUTTON_SECONDARY_TEXT)
        self.assertEqual(tuple(theme["CTkButton"]["border_color"]), BUTTON_BORDER)
        self.assertEqual(tuple(theme["CTkCheckBox"]["fg_color"]), ACCENT)
        self.assertEqual(tuple(theme["CTkOptionMenu"]["fg_color"]), MENU_BG)
        self.assertEqual(tuple(theme["CTkOptionMenu"]["button_color"]), MENU_ARROW)
        self.assertEqual(tuple(theme["CTkOptionMenu"]["text_color"]), MENU_TEXT)
        self.assertEqual(tuple(theme["CTkProgressBar"]["progress_color"]), ACCENT)
        self.assertEqual(tuple(theme["CTkSlider"]["button_color"]), ACCENT)
        self.assertEqual(tuple(theme["CTkFrame"]["fg_color"]), EDITOR)

    def test_control_hierarchy_uses_light_secondary_surfaces(self):
        theme = json.loads(theme_path().read_text(encoding="utf-8"))
        self.assertEqual(theme["CTkButton"]["border_width"], 2)
        self.assertEqual(theme["CTkButton"]["corner_radius"], 6)
        # Previous theme made *every* control a dark blue block. Secondary
        # controls must instead have light surfaces and dark, legible labels.
        for surface in (BUTTON_SECONDARY[0], MENU_BG[0], CANCEL_BG[0]):
            self.assertLess(contrast_ratio(surface, "#FFFFFF"), 1.65)
        self.assertGreater(contrast_ratio(BUTTON_PRIMARY[0], "#FFFFFF"),
                           contrast_ratio(BUTTON_SECONDARY[0], "#FFFFFF"))
        for index in (0, 1):
            with self.subTest(mode=index):
                self.assertGreaterEqual(
                    contrast_ratio(BUTTON_SECONDARY_TEXT[index],
                                   BUTTON_SECONDARY[index]), 4.5)
                self.assertGreaterEqual(
                    contrast_ratio(BUTTON_PRIMARY_TEXT[index],
                                   BUTTON_PRIMARY[index]), 4.5)
                self.assertGreaterEqual(
                    contrast_ratio(MENU_TEXT[index], MENU_BG[index]), 4.5)
                self.assertGreaterEqual(
                    contrast_ratio(CANCEL_TEXT[index], CANCEL_BG[index]), 4.5)
        # Preserve a visible active control without making all buttons dark.
        self.assertNotEqual(BUTTON_SECONDARY, BUTTON_PRIMARY)
        self.assertNotEqual(MENU_BG, ACCENT)

    def test_all_editor_setting_surfaces_share_identical_colors(self):
        self.assertEqual(CARD, FADE_CARD)
        self.assertEqual(CARD, ZOOM_ROW)
        self.assertEqual(CARD_BORDER, FADE_BORDER)
        self.assertEqual(CARD[0], "#FBFCFD")
        self.assertEqual(CARD_BORDER[0], theme_color(CARD_BORDER, dark=False))

    def test_light_and_dark_components_have_distinct_quiet_palette(self):
        for colors in (WINDOW, EDITOR, CARD, FADE_CARD, ZOOM_ROW,
                       WAVE_BACKGROUND, WAVE_SELECTION, WAVE_ACTIVE,
                       FADE_CHART_BACKGROUND, FADE_CHART_LINE):
            self.assertEqual(len(colors), 2)
            self.assertNotEqual(colors[0], colors[1])
        self.assertNotIn("#3B8ED0", ACCENT)
        self.assertNotIn("#1874C9", WAVE_ACTIVE)
        self.assertNotIn("#096CDD", FADE_CHART_LINE)

    def test_primary_button_text_is_legible_on_both_themes(self):
        theme = json.loads(theme_path().read_text(encoding="utf-8"))
        for index in (0, 1):
            with self.subTest(mode=index):
                self.assertGreaterEqual(
                    contrast_ratio(theme["CTkButton"]["text_color"][index],
                                   theme["CTkButton"]["fg_color"][index]), 4.5)
                self.assertGreaterEqual(
                    contrast_ratio(theme["CTkOptionMenu"]["text_color"][index],
                                   theme["CTkOptionMenu"]["fg_color"][index]), 4.5)

    def test_wave_and_fade_surfaces_are_harmonized_with_cards(self):
        for i in (0, 1):
            with self.subTest(mode=i):
                self.assertGreaterEqual(
                    contrast_ratio(WAVE_ACTIVE[i], WAVE_SELECTION[i]), 3.0)
                self.assertGreaterEqual(
                    contrast_ratio(FADE_CHART_LINE[i], FADE_CHART_BACKGROUND[i]), 3.0)
                self.assertGreaterEqual(
                    contrast_ratio(CARD_BORDER[i], CARD[i]), 1.10)
                self.assertGreaterEqual(
                    contrast_ratio(FADE_BORDER[i], FADE_CARD[i]), 1.10)

    def test_theme_color_resolves_light_and_dark(self):
        self.assertEqual(theme_color(ACCENT, dark=False), ACCENT[0])
        self.assertEqual(theme_color(ACCENT, dark=True), ACCENT[1])
        self.assertEqual(theme_color(CARD, dark=False), CARD[0])
        self.assertEqual(theme_color(CARD, dark=True), CARD[1])


if __name__ == "__main__":
    unittest.main()
