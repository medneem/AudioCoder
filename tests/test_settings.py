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

    def test_legacy_config(self):
        (self.root / "config.json").write_text('{"target_format": "WAV"}', encoding="utf-8")
        self.assertEqual(load_settings(self.root)["bitrate"], DEFAULTS["bitrate"])
        self.assertEqual(load_settings(self.root)["target_format"], "WAV")

    def test_broken_config_preserved(self):
        broken = '{"target_format":"BAD"}'
        (self.root / "config.json").write_text(broken, encoding="utf-8")
        with self.assertRaises(ValueError):
            load_settings(self.root)
        self.assertEqual((self.root / "config.json").read_text(encoding="utf-8"), broken)

    def test_default_save(self):
        save_settings(DEFAULTS, self.root)
        self.assertEqual(json.loads((self.root / "config.json").read_text(encoding="utf-8")), DEFAULTS)


if __name__ == "__main__":
    unittest.main()
