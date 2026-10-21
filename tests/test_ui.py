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
        self.window.info = None
        self.window._refresh()
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

    def test_play_button_and_drag_previews(self):
        from audiocoder.player import PlaybackWindow
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Песня.flac"
            path.touch()
            with patch("audiocoder.ui.save_settings"), patch.object(self.window, "_start_waveform"):
                self.window._loaded(AudioInfo(path, 120.0, "flac", 44100, 2))
            self.window.slider.set([20, 80])
            self.window.on_range(self.window.slider.get())
            with patch.object(self.window.player, "play", return_value=1) as play, \
                 patch.object(self.window.player, "stop") as stop:
                self.window.toggle_play()
                self.assertEqual(play.call_args.args[1], PlaybackWindow(20, 80))
                self.window.toggle_play()
                stop.assert_called()
                self.window._left_moved(20)
                self.assertIsNotNone(self.window._preview_timer)
                self.window._slider_released()
                self.assertEqual(play.call_args.args[1], PlaybackWindow(20, 80))
                self.window._right_moved(80)
                self.window._slider_released()
                self.assertEqual(play.call_args.args[1], PlaybackWindow(79, 80))
            self.window._stop_playback()

    def test_format_and_bitrate_persist_to_config(self):
        from audiocoder.settings import load_settings, save_settings
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch("audiocoder.ui.save_settings", side_effect=lambda settings: save_settings(settings, folder)):
                self.window.on_format("MP3")
                self.window.on_bitrate("320k")
            loaded = load_settings(folder)
            self.assertEqual(loaded["target_format"], "MP3")
            self.assertEqual(loaded["bitrate"], "320k")

    def test_fade_option_and_output_configuration(self):
        self.window.fade_var.set(True)
        with patch("audiocoder.ui.save_settings"):
            self.window.on_fade_changed()
            self.window.on_fade_seconds("2.0")
        self.assertTrue(self.window.settings["fade_enabled"])
        self.assertEqual(self.window.settings["fade_seconds"], 2.0)
        self.assertEqual(self.window.fade_menu.cget("state"), "normal")
        self.assertTrue(self.window.waveform.fade_enabled)

    def test_zoomed_waveform_edit_moves_slider_boundary(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Песня.flac"
            path.touch()
            with patch("audiocoder.ui.save_settings"), patch.object(self.window, "_start_waveform"):
                self.window._loaded(AudioInfo(path, 120.0, "flac", 44100, 2))
            self.window.slider.set([10, 80])
            self.window.on_range(self.window.slider.get())
            self.window.waveform.viewport.zoom(4, .5)
            with patch.object(self.window, "_slider_moved") as moved:
                self.window._waveform_edit("left", .25, False)
            self.assertAlmostEqual(self.window.slider.get()[0], 30)
            moved.assert_called_once_with("left")
            self.assertEqual(self.window.waveform.selection, (10 / 120, 80 / 120))
            self.window.on_range(self.window.slider.get())
            self.assertAlmostEqual(self.window.waveform.selection[0], .25)

    def test_mp3_bitrate_selector(self):
        self.window.settings["target_format"] = "FLAC"
        self.window._refresh()
        self.assertEqual(self.window.bitrate_menu.cget("state"), "disabled")
        with patch("audiocoder.ui.save_settings"):
            self.window.on_format("MP3")
        self.assertEqual(self.window.bitrate_menu.cget("state"), "normal")


if __name__ == "__main__":
    unittest.main()
