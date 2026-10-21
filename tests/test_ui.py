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

    def test_help_contains_every_fade_type_and_not_on_main_window(self):
        from audiocoder.fade import FADE_CURVES
        from audiocoder.fade_help import FADE_DESCRIPTIONS
        self.assertFalse(hasattr(self.window, "fade_preview"))
        self.assertEqual(set(FADE_DESCRIPTIONS), set(FADE_CURVES))
        self.assertEqual(self.window.help_button.cget("text"), "❔ Справка")
        self.window.open_help()
        help_window = self.window._help_window
        self.assertTrue(help_window.winfo_exists())
        self.assertEqual(len(help_window._diagrams), len(FADE_CURVES))
        self.assertEqual(
            [diagram._curves for diagram in help_window._diagrams],
            [(code, code) for code in FADE_CURVES])
        self.window.open_help()
        self.assertIs(self.window._help_window, help_window)
        with patch.object(help_window, "refresh_theme") as refresh:
            with patch("audiocoder.ui.save_settings"):
                self.window.on_appearance("Тёмная")
            refresh.assert_called_once()
        with patch("audiocoder.ui.save_settings"):
            self.window.on_appearance("Светлая")
        help_window.destroy()
        self.window._help_window = None

    def test_compact_window_can_scroll_without_hiding_playback_controls(self):
        # Reproduce the problematic 810 x 650 window size. The central editor
        # must scroll while the footer stays visible even at limited height.
        import customtkinter as ctk
        self.assertIsInstance(self.window.editor_panel, ctk.CTkScrollableFrame)
        self.assertEqual(self.window.footer.winfo_manager(), "grid")
        self.window.deiconify()
        try:
            self.window.geometry("810x650")
            self.window.update_idletasks()
            scroll_canvas = self.window.editor_panel._parent_canvas
            top, bottom = scroll_canvas.yview()
            self.assertLess(bottom, 1.0, "All editor controls unexpectedly fit; test did not exercise overflow")
            self.assertAlmostEqual(top, 0.0)
            self.assertLessEqual(
                self.window.footer.winfo_rooty() + self.window.footer.winfo_height(),
                self.window.winfo_rooty() + self.window.winfo_height() + 4,
                "Playback and conversion footer is outside the window",
            )
            scroll_canvas.yview_moveto(1.0)
            self.window.update_idletasks()
            self.assertGreater(scroll_canvas.yview()[0], top)
            self.assertEqual(self.window.run_button.winfo_manager(), "pack")
        finally:
            self.window.geometry("920x710")
            self.window.editor_panel._parent_canvas.yview_moveto(0.0)
            self.window.withdraw()

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
                self.assertEqual(play.call_args.args[1], PlaybackWindow(20, 25))
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

    def test_vbr_mode_and_fade_curve_controls_persist(self):
        from audiocoder.settings import load_settings, save_settings
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch("audiocoder.ui.save_settings",
                       side_effect=lambda settings: save_settings(settings, folder)):
                self.window.on_format("MP3")
                self.window.vbr_var.set(True)
                self.window.on_vbr_changed()
                self.window.on_vbr_quality("0")
                self.window.fade_var.set(True)
                self.window.on_fade_changed()
                self.window.on_fade_curve("fade_in_curve", "Четверть синусоиды")
                self.window.on_fade_curve("fade_out_curve", "Кубический")
            restored = load_settings(folder)
            self.assertTrue(restored["vbr_enabled"])
            self.assertEqual(restored["vbr_quality"], 0)
            self.assertEqual(restored["fade_in_curve"], "qsin")
            self.assertEqual(restored["fade_out_curve"], "cub")
            self.assertEqual(self.window.bitrate_menu.cget("state"), "disabled")
            self.assertEqual(self.window.vbr_quality_menu.cget("state"), "normal")

    def test_range_and_view_persist_for_same_source(self):
        from audiocoder.settings import load_settings, save_settings
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "Песня.flac"
            path.touch()
            with patch("audiocoder.ui.save_settings",
                       side_effect=lambda settings: save_settings(settings, folder)), \
                 patch.object(self.window, "_start_waveform"):
                self.window._loaded(AudioInfo(path, 120.0, "flac", 44100, 2))
                self.window.slider.set([12.5, 75])
                self.window.on_range(self.window.slider.get())
                self.window.waveform.viewport.zoom(4, .5)
                self.window.waveform._view_changed()
                self.window._save()
                saved = load_settings(folder)
                self.assertAlmostEqual(saved["clip_start"], 12.5)
                self.assertAlmostEqual(saved["clip_end"], 75)
                self.assertAlmostEqual(saved["waveform_zoom"], 4)
                # Simulate closing/reopening the source with restored JSON.
                self.window.settings = saved
                self.window._loaded(AudioInfo(path, 120.0, "flac", 44100, 2))
                self.assertAlmostEqual(self.window.slider.get()[0], 12.5)
                self.assertAlmostEqual(self.window.slider.get()[1], 75)
                self.assertAlmostEqual(self.window.waveform.viewport.zoom_level, 4)

    def test_mp3_bitrate_selector(self):
        self.window.settings["target_format"] = "FLAC"
        self.window.settings["vbr_enabled"] = False
        self.window.vbr_var.set(False)
        self.window._refresh()
        self.assertEqual(self.window.bitrate_menu.cget("state"), "disabled")
        with patch("audiocoder.ui.save_settings"):
            self.window.on_format("MP3")
        self.assertEqual(self.window.bitrate_menu.cget("state"), "normal")


if __name__ == "__main__":
    unittest.main()
