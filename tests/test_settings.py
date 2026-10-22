import json
from pathlib import Path
import tempfile
import unittest

from audiocoder.settings import DEFAULTS, load_settings, save_settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_defaults_and_unicode(self):
        self.assertEqual(load_settings(self.root), DEFAULTS)
        settings = {**DEFAULTS, "last_source_dir": "D:/Музыка", "output_dir": "D:/Готово"}
        save_settings(settings, self.root)
        self.assertEqual(load_settings(self.root), settings)
        self.assertIn("Музыка", (self.root / "config.json").read_text(encoding="utf-8"))

    def test_broken_config_preserved(self):
        broken = '{"target_format":"BAD"}'
        (self.root / "config.json").write_text(broken, encoding="utf-8")
        with self.assertRaises(ValueError):
            load_settings(self.root)
        self.assertEqual((self.root / "config.json").read_text(encoding="utf-8"), broken)

    def test_theme_setting_is_saved_and_validated(self):
        config = {**DEFAULTS, "appearance": "System"}
        save_settings(config, self.root)
        self.assertEqual(load_settings(self.root)["appearance"], "System")
        (self.root / "config.json").write_text('{"appearance": "NotATheme"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_settings(self.root)

    def test_invalid_fade_settings_are_rejected(self):
        for invalid in ("yes", None, 0):
            values = {**DEFAULTS, "fade_enabled": invalid}
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                save_settings(values, self.root)
        for invalid in (-1, 0, "one", 200, True):
            values = {**DEFAULTS, "fade_seconds": invalid}
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                save_settings(values, self.root)

    def test_none_curve_ids_roundtrip_config_and_legacy_curves_survive(self):
        for fade_in, fade_out in (("none", "none"),
                                 ("none", "log"), ("qsin", "none")):
            values = {**DEFAULTS, "fade_enabled": True,
                      "fade_in_curve": fade_in, "fade_out_curve": fade_out}
            with self.subTest(curves=(fade_in, fade_out)):
                save_settings(values, self.root)
                self.assertEqual(load_settings(self.root), values)

    def test_new_options_survive_restart(self):
        values = {**DEFAULTS,
                  "target_format": "MP3", "bitrate": "320k",
                  "vbr_enabled": True, "vbr_quality": 0,
                  "fade_enabled": True, "fade_seconds": 3.0,
                  "fade_in_curve": "qsin", "fade_out_curve": "cub",
                  "last_source_path": "D:/Music/Song.flac",
                  "clip_start": 1.25, "clip_end": 51.7,
                  "waveform_zoom": 8.0, "waveform_start": .625}
        save_settings(values, self.root)
        self.assertEqual(load_settings(self.root), values)

    def test_legacy_settings_get_new_defaults(self):
        (self.root / "config.json").write_text(
            '{"target_format":"WAV","fade_enabled":true}',
            encoding="utf-8")
        values = load_settings(self.root)
        self.assertEqual(values["target_format"], "WAV")
        self.assertTrue(values["fade_enabled"])
        self.assertEqual(values["bitrate"], DEFAULTS["bitrate"])
        self.assertEqual(values["fade_in_curve"], "log")
        self.assertEqual(values["vbr_enabled"], False)
        self.assertEqual(values["waveform_zoom"], 1)

    def test_invalid_persisted_options(self):
        for name, value in (
            ("vbr_enabled", "yes"), ("vbr_quality", 12),
            ("fade_in_curve", "fake"), ("fade_out_curve", ""),
            ("waveform_zoom", 17), ("waveform_start", -0.1),
            ("clip_start", -1), ("clip_end", -2),
        ):
            with self.subTest(setting=name), self.assertRaises(ValueError):
                save_settings({**DEFAULTS, name: value}, self.root)

    def test_default_save(self):
        save_settings(DEFAULTS, self.root)
        self.assertEqual(json.loads((self.root / "config.json").read_text(encoding="utf-8")), DEFAULTS)


    def test_selection_repeat_defaults_roundtrip_and_validation(self):
        self.assertIs(DEFAULTS["loop_selection"], False)
        saved = {**DEFAULTS, "loop_selection": True}
        save_settings(saved, self.root)
        self.assertTrue(load_settings(self.root)["loop_selection"])
        for value in (None, 1, "true"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                save_settings({**DEFAULTS, "loop_selection": value}, self.root)


if __name__ == "__main__":
    unittest.main()
