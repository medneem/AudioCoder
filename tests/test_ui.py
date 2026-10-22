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

    def test_button_hierarchy_on_actual_widgets(self):
        import customtkinter as ctk
        from audiocoder.palette import (
            BUTTON_SECONDARY, BUTTON_SECONDARY_TEXT, BUTTON_PRIMARY,
            BUTTON_PRIMARY_TEXT, CARD, CARD_BORDER, FADE_CARD, FADE_BORDER,
            MENU_BG, MENU_TEXT, ZOOM_ROW, CANCEL_BG, CANCEL_TEXT, ACCENT)
        self.assertEqual(
            tuple(ctk.ThemeManager.theme["CTkButton"]["fg_color"]),
            BUTTON_SECONDARY)
        for button in (self.window.help_button, self.window.open_button,
                       self.window.folder_button, self.window.play_button):
            self.assertEqual(tuple(button.cget("fg_color")), BUTTON_SECONDARY)
            self.assertEqual(tuple(button.cget("text_color")), BUTTON_SECONDARY_TEXT)
        self.assertEqual(tuple(self.window.run_button.cget("fg_color")), BUTTON_PRIMARY)
        self.assertEqual(tuple(self.window.run_button.cget("text_color")), BUTTON_PRIMARY_TEXT)
        self.assertEqual(tuple(self.window.cancel_button.cget("fg_color")), CANCEL_BG)
        self.assertEqual(tuple(self.window.cancel_button.cget("text_color")), CANCEL_TEXT)
        self.assertEqual(tuple(self.window.codec_card.cget("fg_color")), CARD)
        self.assertEqual(tuple(self.window.codec_card.cget("border_color")), CARD_BORDER)
        self.assertEqual(tuple(self.window.fade_card.cget("fg_color")), FADE_CARD)
        self.assertEqual(tuple(self.window.fade_card.cget("border_color")), FADE_BORDER)
        for menu in (self.window.format_menu, self.window.bitrate_menu,
                     self.window.fade_in_menu, self.window.fade_out_menu,
                     self.window.fade_menu, self.window.appearance_menu):
            self.assertEqual(tuple(menu.cget("fg_color")), MENU_BG)
            self.assertEqual(tuple(menu.cget("text_color")), MENU_TEXT)
        self.assertEqual(tuple(self.window.progress.cget("progress_color")), ACCENT)
        self.assertEqual(tuple(self.window.slider.cget("button_color")), ACCENT)
        self.assertEqual(
            tuple(self.window.zoom_label.master.cget("fg_color")), ZOOM_ROW)

    def test_approved_settings_cards_and_unified_typography(self):
        import customtkinter as ctk
        from audiocoder.ui_style import FONT_FAMILY, BODY_SIZE, TITLE_SIZE
        for card in (self.window.codec_card, self.window.fade_card,
                     self.window.folder_card):
            self.assertIsInstance(card, ctk.CTkFrame)
            self.assertEqual(card.winfo_manager(), "grid")
        self.assertEqual(self.window.codec_card.cget("corner_radius"), 14)
        self.assertEqual(self.window.fade_card.cget("fg_color"),
                         self.window.codec_card.cget("fg_color"))
        for widget in (
            self.window.format_menu, self.window.bitrate_menu,
            self.window.vbr_checkbox, self.window.fade_checkbox,
            self.window.fade_menu, self.window.fade_in_menu,
            self.window.fade_out_menu, self.window.folder_button,
            self.window.help_button, self.window.open_button,
        ):
            font = widget.cget("font")
            self.assertEqual(font.cget("family"), FONT_FAMILY)
            self.assertEqual(font.cget("size"), BODY_SIZE)
        self.assertEqual(self.window.main_heading.cget("font").cget("size"),
                         TITLE_SIZE)

    def test_editor_has_no_gray_outer_container(self):
        from audiocoder.palette import WINDOW
        self.assertEqual(tuple(self.window.editor_panel.cget("fg_color")), WINDOW)
        self.assertEqual(self.window.editor_panel.cget("corner_radius"), 0)
        self.assertEqual(self.window.editor_panel.cget("border_width"), 0)
        self.assertEqual(int(self.window.editor_panel.grid_info()["padx"]), 0)
        # The actual root/window background is the same as the editor surface.
        self.assertEqual(tuple(self.window.cget("fg_color")), WINDOW)

    def test_uniform_white_cards_and_unbroken_thicker_borders(self):
        from audiocoder.palette import CARD, CARD_BORDER
        cards = (self.window.codec_card, self.window.fade_card,
                 self.window.folder_card, self.window.zoom_label.master)
        for card in cards:
            with self.subTest(widget=card):
                self.assertEqual(tuple(card.cget("fg_color")), CARD)
                self.assertEqual(tuple(card.cget("border_color")), CARD_BORDER)
                self.assertEqual(card.cget("border_width"), 2)
                self.assertEqual(card.cget("corner_radius"), 12)
        buttons = (self.window.help_button, self.window.open_button,
                   self.window.folder_button, self.window.play_button,
                   self.window.cancel_button, self.window.run_button)
        for button in buttons:
            with self.subTest(widget=button):
                self.assertEqual(button.cget("border_width"), 2)
                self.assertEqual(button.cget("corner_radius"), 6)

    def test_switching_themes_keeps_cards_uniform(self):
        for appearance in ("Тёмная", "Светлая"):
            with self.subTest(appearance=appearance), patch("audiocoder.ui.save_settings"):
                self.window.on_appearance(appearance)
                cards = (self.window.codec_card, self.window.fade_card,
                         self.window.folder_card, self.window.zoom_label.master)
                self.assertEqual(len({c._apply_appearance_mode(c.cget("fg_color"))
                                      for c in cards}), 1)

    def test_large_progress_backlog_does_not_block_gui_event_loop(self):
        import queue
        pending = queue.Queue()
        for i in range(450):
            pending.put(("progress", i / 450))
        previous = self.window.events
        try:
            self.window.events = pending
            self.window._poll()
            self.assertGreater(pending.qsize(), 0,
                               "One Tk callback consumed an unbounded event backlog")
            self.assertLess(pending.qsize(), 450)
        finally:
            self.window.events = previous

    def test_waveform_accepts_explorer_audio_drop(self):
        from types import SimpleNamespace
        from tkinterdnd2 import COPY, REFUSE_DROP
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Песня с пробелами.flac"
            path.touch()
            self.window.busy = False
            self.window.probing = False
            self.assertTrue(hasattr(self.window.waveform, "drop_target_register"))
            with patch.object(self.window, "open_file") as open_file:
                self.assertEqual(self.window._drop_enter(None), COPY)
                self.assertEqual(self.window._on_wave_drop(
                    SimpleNamespace(data="{" + str(path) + "}")), COPY)
                open_file.assert_called_once_with(path)
            with patch("audiocoder.ui.messagebox.showwarning") as warning:
                self.assertEqual(self.window._on_wave_drop(
                    SimpleNamespace(data="{other.txt}")), REFUSE_DROP)
                warning.assert_called_once()
            self.window.busy = True
            try:
                with patch.object(self.window, "open_file") as open_file:
                    self.assertEqual(self.window._on_wave_drop(
                        SimpleNamespace(data="{" + str(path) + "}")), REFUSE_DROP)
                    open_file.assert_not_called()
            finally:
                self.window.busy = False

    def test_compact_editor_has_no_internal_scroll_and_no_clipped_footer(self):
        import customtkinter as ctk
        self.assertIsInstance(self.window.editor_panel, ctk.CTkFrame)
        self.assertNotIsInstance(self.window.editor_panel, ctk.CTkScrollableFrame)
        self.assertFalse(hasattr(self.window.editor_panel, "_parent_canvas"))
        self.assertFalse(hasattr(self.window, "target_label"))
        self.window.deiconify()
        try:
            self.window.update()
            self.assertEqual(int(self.window.waveform.cget("height")), 120)
            self.assertLessEqual(self.window.winfo_reqheight(),
                                 self.window.winfo_height())
            self.assertEqual(self.window.footer.winfo_manager(), "grid")
            # All 3 approved settings cards must appear above the pinned footer.
            for widget in (self.window.codec_card, self.window.fade_card,
                           self.window.folder_card):
                self.assertEqual(widget.winfo_manager(), "grid")
                bottom = widget.winfo_rooty() + widget.winfo_height()
                footer_top = self.window.footer.winfo_rooty()
                self.assertLessEqual(bottom, footer_top)
            self.assertLessEqual(
                self.window.footer.winfo_rooty() + self.window.footer.winfo_height(),
                self.window.winfo_rooty() + self.window.winfo_height() + 4)
        finally:
            self.window.withdraw()

    def test_window_rejects_height_too_small_to_show_all_controls(self):
        self.window.deiconify()
        try:
            self.window.update()
            # CustomTkinter 5.2.x does not implement a getter for minsize();
            # use the native window-manager query instead.
            minimum = int(self.window.tk.call("wm", "minsize", self.window._w)[1])
            self.assertGreaterEqual(minimum, self.window.winfo_reqheight())
            self.window.geometry("920x500")
            self.window.update()
            self.assertGreaterEqual(self.window.winfo_height(), minimum)
            self.assertLessEqual(
                self.window.footer.winfo_rooty() + self.window.footer.winfo_height(),
                self.window.winfo_rooty() + self.window.winfo_height() + 4)
        finally:
            self.window.geometry("920x710")
            self.window.withdraw()

    def test_header_version_removed_and_controls_aligned_right(self):
        from version import APP_VERSION
        import customtkinter as ctk
        header = self.window.main_heading.master
        labels = [widget.cget("text") for widget in header.winfo_children()
                  if isinstance(widget, ctk.CTkLabel)]
        self.assertNotIn(f"v{APP_VERSION}", labels)
        self.assertEqual(self.window.appearance_menu.pack_info()["side"], "right")
        self.assertEqual(self.window.help_button.pack_info()["side"], "right")
        self.assertEqual(self.window.title(), f"AudioCoder {APP_VERSION}")

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
            self.assertFalse(hasattr(self.window, "target_label"))
            self.assertIn(str(destination.parent), self.window.folder_label.cget("text"))
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

    def test_real_canvas_paints_with_tk_named_gray86_background(self):
        """Regression: Windows CTkFrame theme returns 'gray86', invalid for PIL."""
        previous_view = (self.window.waveform.viewport.start,
                         self.window.waveform.viewport.span)
        self.window.deiconify()
        try:
            self.window.update_idletasks()
            self.window.waveform.set_peaks((0.3,) * 4096)
            self.window.waveform.viewport.reset()
            self.window.waveform.viewport.zoom(3.8, .5)
            self.window.waveform.set_selection(0, 143.901, 143.901)
            from audiocoder.waveform_view import tk_background_rgb
            for color, expected in (("gray86", (219, 219, 219)),
                                    ("gray13", (33, 33, 33)),
                                    ("#DBDBDB", (219, 219, 219))):
                with self.subTest(color=color):
                    self.assertEqual(
                        tk_background_rgb(self.window.waveform, color), expected)
                    with patch.object(self.window.editor_panel, "_apply_appearance_mode",
                                      return_value=color):
                        self.window.waveform._paint()
                    self.assertIsNotNone(self.window.waveform._image)
                    self.assertTrue(self.window.waveform.itemcget(
                        self.window.waveform._image_item, "image"))
        finally:
            (self.window.waveform.viewport.start,
             self.window.waveform.viewport.span) = previous_view
            self.window.withdraw()

    def test_canvas_idle_callback_does_not_fail_silently(self):
        """Tkinter callback exceptions used to be printed but not fail CI."""
        errors = []
        previous_view = (self.window.waveform.viewport.start,
                         self.window.waveform.viewport.span)
        self.window.deiconify()
        try:
            self.window.waveform.set_peaks((.35,) * 4096)
            self.window.waveform.viewport.reset()
            self.window.waveform.viewport.zoom(3.8, .5)
            with patch.object(self.window, "report_callback_exception",
                              side_effect=lambda typ, err, tb: errors.append(str(err))):
                self.window.waveform.redraw()
                self.window.update()
            self.assertEqual(errors, [], "Canvas callback failed: " + repr(errors))
            self.assertIsNotNone(self.window.waveform._image)
        finally:
            (self.window.waveform.viewport.start,
             self.window.waveform.viewport.span) = previous_view
            self.window.withdraw()

    def test_zoom_detail_updates_width_and_ignores_stale_results(self):
        from audiocoder.waveform_view import visible_waveform_columns
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "detail.flac"
            file.touch()
            with patch("audiocoder.ui.save_settings"), patch.object(self.window, "_start_waveform"):
                self.window._loaded(AudioInfo(file, 120.0, "flac", 44100, 2))
            self.window.waveform.set_peaks((0.0,) * 4096)
            self.window.waveform.viewport.zoom(4, 0.5)
            self.window._on_waveform_view(4.0)
            self.assertIsNotNone(self.window._detail_timer)
            old_generation = self.window._detail_generation
            start = self.window.waveform.viewport.start
            end = self.window.waveform.viewport.end
            detail = (0.7,) * 2000
            self.window.events.put(("waveform_detail", (
                self.window.source_sequence, old_generation, start, end, detail)))
            self.window._poll()
            self.assertEqual(self.window.waveform.detail_peaks, (start, end, detail))
            columns = visible_waveform_columns(
                self.window.waveform.peaks, self.window.waveform.viewport, 200,
                detail=self.window.waveform.detail_peaks)
            self.assertEqual(columns, (0.7,) * 200)

            self.window.waveform.viewport.pan(-50, 600)
            self.window._on_waveform_view(4.0)
            self.assertGreater(self.window._detail_generation, old_generation)
            # Old FFmpeg worker cannot overwrite a new viewport.
            self.window.events.put(("waveform_detail", (
                self.window.source_sequence, old_generation,
                start, end, (0.9,) * 2000)))
            self.window._poll()
            self.assertEqual(self.window.waveform.detail_peaks, (start, end, detail))
            columns = visible_waveform_columns(
                self.window.waveform.peaks, self.window.waveform.viewport, 200,
                detail=self.window.waveform.detail_peaks)
            self.assertEqual(columns, (0.0,) * 200)
            self.window._cancel_detail_waveform()

    def test_zoom_decode_uses_visible_range(self):
        from threading import Event
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "detail.flac"
            file.touch()
            with patch("audiocoder.ui.save_settings"), patch.object(self.window, "_start_waveform"):
                self.window._loaded(AudioInfo(file, 120.0, "flac", 44100, 2))
            self.window.waveform.set_peaks((0.2,) * 4096)
            self.window.waveform.reset_view()
            self.window.waveform.viewport.zoom(4, .5)
            self.window._on_waveform_view(4.0)
            captured = []
            completed = Event()
            def mocked_extract(path, **kwargs):
                captured.append((path, kwargs))
                completed.set()
                return (0.3,) * kwargs["width"]
            with patch("audiocoder.ui.extract_waveform", side_effect=mocked_extract):
                self.window._start_detail_waveform()
                self.assertTrue(completed.wait(2), "worker did not start")
            self.assertEqual(captured[0][0], file)
            self.assertAlmostEqual(captured[0][1]["start"], 45.0)
            self.assertAlmostEqual(captured[0][1]["duration"], 30.0)
            self.assertGreaterEqual(captured[0][1]["width"], 1024)
            self.window._cancel_detail_waveform()

    def test_wheel_zoom_displays_actual_visible_time_range(self):
        from types import SimpleNamespace
        previous_info = self.window.info
        previous_view = (self.window.waveform.viewport.start,
                         self.window.waveform.viewport.span)
        try:
            self.window.info = AudioInfo(
                Path("song.flac"), 285.327, "flac", 44100, 2)
            self.window.waveform.viewport.reset()
            with patch.object(self.window, "_record_view"), \
                 patch.object(self.window, "_schedule_detail_waveform"):
                self.window._on_waveform_view(1)
                self.assertIn("×1.0", self.window.zoom_label.cget("text"))
                self.assertIn("00:00", self.window.zoom_label.cget("text"))
                self.assertIn("04:45", self.window.zoom_label.cget("text"))
                self.window.waveform._wheel(
                    SimpleNamespace(delta=120, x=400))
                self.assertLess(self.window.waveform.viewport.span, 1)
                self.assertIn("×1.4", self.window.zoom_label.cget("text"))
                self.window.waveform.viewport.zoom(50, .5)
                self.window._on_waveform_view(
                    self.window.waveform.viewport.zoom_level)
                text = self.window.zoom_label.cget("text")
                self.assertIn("×16.0", text)
                self.assertNotIn("00:00–04:45", text)
                # Window is only 285.327 / 16 seconds long.
                self.assertAlmostEqual(
                    (self.window.waveform.viewport.end -
                     self.window.waveform.viewport.start) * self.window.info.duration,
                    285.327 / 16, places=4)
        finally:
            self.window.info = previous_info
            self.window.waveform.viewport.start = previous_view[0]
            self.window.waveform.viewport.span = previous_view[1]

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
