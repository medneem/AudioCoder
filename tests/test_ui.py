"""Windows GUI smoke tests without displaying the window or playing audio."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audiocoder.media import AudioInfo
from audiocoder.settings import DEFAULTS
from audiocoder.ui import AudioCoderApp


class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # CTk schedules delayed DPI/icon callbacks. Recreating/destroying
        # multiple Tk roots in a single Tcl interpreter emits noisy errors.
        with patch("audiocoder.ui.load_settings", return_value=DEFAULTS.copy()):
            cls.window = AudioCoderApp()
        cls.window.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.window._close()

    def test_slider_controls_and_time_labels(self):
        self.assertEqual(self.window.run_button.cget("state"), "disabled")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Альбом.flac"
            path.touch()
            with patch("audiocoder.ui.save_settings"), patch.object(self.window, "_start_waveform") as start_waveform:
                self.window._loaded(AudioInfo(path, 120.0, "flac", 44100, 2))
            start_waveform.assert_called_once()
            self.window.waveform.set_peaks((0.1, 0.9, 0.6, 0.2))
            self.assertEqual(tuple(self.window.slider.get()), (0.0, 120.0))
            self.assertEqual(self.window.run_button.cget("state"), "normal")
            self.window.slider.set([10.0, 30.0])
            self.window.on_range(self.window.slider.get())
            self.assertEqual(self.window.left_time.cget("text"), "00:00:10.000")
            self.assertEqual(self.window.length_time.cget("text"), "Выделено: 00:00:20.000")
            self.assertEqual(self.window.waveform.selection, (10 / 120, 30 / 120))
            self.assertEqual(len(self.window.waveform.peaks), 4)

    def test_theme_selection(self):
        import customtkinter as ctk
        with patch("audiocoder.ui.save_settings"):
            self.window.on_appearance("Тёмная")
            self.assertEqual(ctk.get_appearance_mode(), "Dark")
            self.window.on_appearance("Светлая")
            self.assertEqual(ctk.get_appearance_mode(), "Light")
        self.assertEqual(self.window.settings["appearance"], "Light")

    def test_existing_destination_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Альбом.flac"
            path.touch()
            with patch("audiocoder.ui.save_settings"), patch.object(self.window, "_start_waveform"):
                self.window._loaded(AudioInfo(path, 120.0, "flac", 44100, 2))
            destination = self.window._destination()
            destination.write_bytes(b"existing")
            self.window._preview()
            self.assertIn("будет заменён", self.window.target_label.cget("text"))
            self.assertEqual(self.window.run_button.cget("state"), "normal")

    def test_mp3_bitrate_selector(self):
        self.assertEqual(self.window.bitrate_menu.cget("state"), "disabled")
        with patch("audiocoder.ui.save_settings"):
            self.window.on_format("MP3")
        self.assertEqual(self.window.bitrate_menu.cget("state"), "normal")


if __name__ == "__main__":
    unittest.main()
