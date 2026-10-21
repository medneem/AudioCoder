"""TkDND file payloads are Tcl lists, not space-delimited paths."""
from pathlib import Path
import tempfile
import tkinter
import unittest

from audiocoder.drag_drop import AUDIO_EXTENSIONS, dropped_audio_path


class DragDropTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tcl = tkinter.Tcl()

    def test_unicode_and_spaces(self):
        path = self.root / "Песня с пробелами.FLAC"
        path.write_bytes(b"audio")
        self.assertEqual(dropped_audio_path("{" + str(path) + "}",
                                            self.tcl.splitlist), path)

    def test_supported_suffixes(self):
        for suffix in sorted(AUDIO_EXTENSIONS):
            path = self.root / ("Файл" + suffix)
            path.write_bytes(b"music")
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    dropped_audio_path("{" + str(path) + "}",
                                       self.tcl.splitlist), path)

    def test_reject_multiple_files(self):
        p1, p2 = self.root / "one.mp3", self.root / "two.flac"
        p1.touch()
        p2.touch()
        with self.assertRaisesRegex(ValueError, "один аудиофайл"):
            dropped_audio_path("{" + str(p1) + "} {" + str(p2) + "}",
                               self.tcl.splitlist)

    def test_reject_directory_and_unknown_type(self):
        for text in (str(self.root / "missing.mp3"),
                     str(self.root / "text.txt"),
                     str(self.root)):
            with self.subTest(path=text), self.assertRaises(ValueError):
                dropped_audio_path("{" + text + "}", self.tcl.splitlist)

    def test_empty_drop(self):
        with self.assertRaises(ValueError):
            dropped_audio_path("", self.tcl.splitlist)


if __name__ == "__main__":
    unittest.main()
