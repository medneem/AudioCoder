"""Windows titlebar icon must be an ICO file available in dev and frozen builds."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from audiocoder.app_icon import icon_file_path


class AppIconTests(unittest.TestCase):
    def test_development_build_materializes_correct_ico(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            icon = icon_file_path(application_root=root)
            self.assertEqual(icon, root / "assets" / "app.ico")
            self.assertTrue(icon.is_file())
            with Image.open(icon) as image:
                self.assertEqual(image.format, "ICO")
                self.assertEqual(image.size, (256, 256))
                self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertEqual(icon_file_path(application_root=root), icon)

    def test_frozen_application_uses_embedded_icon_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            embedded = Path(tmp) / "assets" / "app.ico"
            embedded.parent.mkdir()
            embedded.write_bytes(b"provided by PyInstaller")
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "_MEIPASS", str(tmp), create=True):
                self.assertEqual(icon_file_path(), embedded)
            self.assertEqual(embedded.read_bytes(), b"provided by PyInstaller")

    def test_frozen_application_fails_clearly_if_icon_resource_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "_MEIPASS", str(tmp), create=True):
                with self.assertRaises(FileNotFoundError):
                    icon_file_path()


if __name__ == "__main__":
    unittest.main()
