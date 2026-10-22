"""Verify automatic Explorer navigation is safe for unicode paths."""
from pathlib import Path
from unittest.mock import patch
import unittest

from audiocoder.explorer import reveal_output_file


class ExplorerTests(unittest.TestCase):
    @patch("audiocoder.explorer.subprocess.Popen")
    @patch("audiocoder.explorer.sys.platform", "win32")
    def test_reveals_new_file_in_folder_with_unicode_and_spaces(self, popen):
        path = Path("D:/Музыка/Новая папка/Песня converted.flac")
        reveal_output_file(path)
        argv = popen.call_args.args[0]
        self.assertEqual(argv[0:2], ["explorer.exe", "/select,"])
        self.assertEqual(Path(argv[2]).name, path.name)
        self.assertIn("Музыка", argv[2])
        self.assertEqual(
            popen.call_args.kwargs["creationflags"],
            getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0))

    @patch("audiocoder.explorer.subprocess.Popen")
    @patch("audiocoder.explorer.sys.platform", "linux")
    def test_non_windows_never_starts_explorer(self, popen):
        with self.assertRaises(OSError):
            reveal_output_file(Path("/tmp/result.flac"))
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
