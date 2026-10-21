"""The CustomTkinter presentation layer; no FFmpeg work on the UI thread."""

from pathlib import Path
from tkinter import filedialog, messagebox
import queue
import threading

import customtkinter as ctk
from tkinterdnd2 import COPY, DND_FILES, REFUSE_DROP, TkinterDnD
from vendor.CTkRangeSlider import CTkRangeSlider

from version import APP_VERSION
from .converter import (BITRATES, FORMATS, ConversionCancelled,
                        ConversionJob, ConversionRunner, output_path)
from .media import probe_audio
from .player import AudioPlayer, listening_window
from .waveform import extract_waveform
from .waveform_view import WaveformView
from .fade import FADE_CURVES
from .fade_help import FadeHelpWindow
from .drag_drop import dropped_audio_path
from .ui_style import FONT_FAMILY, TITLE_SIZE, apply_body_font
from .selection import ClipRange, clock
from .settings import DEFAULTS, load_settings, save_settings


ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


class AudioCoderApp(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title(f"AudioCoder {APP_VERSION}")
        self.geometry("920x690")
        self.minsize(810, 620)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.events = queue.Queue()
        self.info = None
        self.runner = None
        self.busy = False
        self.probing = False
        self.closing = False
        self.source_sequence = 0
        self.player = AudioPlayer()
        self._preview_timer = None
        self._detail_timer = None
        self._detail_generation = 0
        self._last_drag_side = None
        self._playing = False
        self._save_timer = None
        self._loading_source = False
        self._help_window = None
        try:
            self.settings = load_settings()
        except (ValueError, OSError) as exc:
            self.settings = DEFAULTS.copy()
            self.after(50, lambda error=str(exc): messagebox.showwarning("Настройки", error))
        ctk.set_appearance_mode(self.settings["appearance"])

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(9, 3))
        self.main_heading = ctk.CTkLabel(header, text="AudioCoder",
                                         font=ctk.CTkFont(family=FONT_FAMILY, size=TITLE_SIZE, weight="bold"))
        self.main_heading.pack(side="left")
        self.appearance_menu = ctk.CTkOptionMenu(
            header, values=["Светлая", "Тёмная", "Системная"], width=125,
            command=self.on_appearance)
        self.appearance_menu.set({
            "Light": "Светлая", "Dark": "Тёмная", "System": "Системная",
        }[self.settings["appearance"]])
        self.appearance_menu.pack(side="right")
        self.help_button = ctk.CTkButton(
            header, text="❔ Справка", width=110, command=self.open_help)
        self.help_button.pack(side="right", padx=(0, 12))

        # The entire editor is a regular frame: no nested vertical scrolling.
        # Keep height compact, and enforce its requested size after layout so
        # Windows DPI scaling cannot silently clip settings below the waveform.
        self.editor_panel = ctk.CTkFrame(self, corner_radius=14)
        frame = self.editor_panel
        frame.grid(row=1, column=0, sticky="nsew", padx=17, pady=3)
        frame.grid_columnconfigure(0, weight=1)
        source_header = ctk.CTkFrame(frame, fg_color="transparent")
        source_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(5, 0))
        ctk.CTkLabel(source_header, text="🎵 Исходный аудиофайл · перетащите файл на волну").pack(
            side="left")
        self.open_button = ctk.CTkButton(
            source_header, text="Выбрать файл", width=130, height=28,
            command=self.choose_file)
        self.open_button.pack(side="right")
        self.path_label = ctk.CTkLabel(frame, text="Файл не выбран", anchor="w")
        self.path_label.grid(row=1, column=0, sticky="ew", padx=16)
        self.metadata = ctk.CTkLabel(frame, text="Длительность: —    Кодек: —", anchor="w")
        self.metadata.grid(row=3, column=0, sticky="ew", padx=16)

        times = ctk.CTkFrame(frame, fg_color="transparent")
        times.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 1))
        times.grid_columnconfigure(1, weight=1)
        self.left_time = ctk.CTkLabel(times, text="00:00:00.000")
        self.left_time.grid(row=0, column=0, sticky="w")
        self.length_time = ctk.CTkLabel(times, text="Выделенный фрагмент: —")
        self.length_time.grid(row=0, column=1)
        self.right_time = ctk.CTkLabel(times, text="00:00:00.000")
        self.right_time.grid(row=0, column=2, sticky="e")
        self.waveform = WaveformView(
            frame, height=120, on_edit=self._waveform_edit,
            on_view_change=self._on_waveform_view)
        self.waveform.grid(row=5, column=0, sticky="ew", padx=18, pady=(1, 2))
        self.waveform.drop_target_register(DND_FILES)
        self.waveform.dnd_bind("<<DropEnter>>", self._drop_enter)
        self.waveform.dnd_bind("<<DropLeave>>", self._drop_leave)
        self.waveform.dnd_bind("<<Drop>>", self._on_wave_drop)
        self.slider = CTkRangeSlider(
            frame, from_=0, to=1, height=20, state="disabled",
            command=(self._left_moved, self._right_moved))
        self.slider.grid(row=6, column=0, sticky="ew", padx=18, pady=(2, 6))
        # The vendored range slider handles mouse events on its inner Canvas.
        # Keep its internal drag handlers; add only a release notification.
        self.slider._canvas.bind("<ButtonRelease-1>", self._slider_released, add="+")
        # Approved mockup variant 3: compact quality rows, highlighted fade
        # card, and a distinct folder strip, without an internal scrollbar.
        zoom_row = ctk.CTkFrame(frame, fg_color=("#F7F9FD", "#293544"),
                                corner_radius=12)
        zoom_row.grid(row=7, column=0, sticky="ew", padx=16, pady=(1, 5))
        zoom_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            zoom_row, text="◈  Колесо — масштаб · Правая кнопка — сдвиг · Левая — границы",
            anchor="w").grid(row=0, column=0, sticky="ew", padx=(12, 5), pady=3)
        self.zoom_label = ctk.CTkLabel(zoom_row, text="×1.0", width=54)
        self.zoom_label.grid(row=0, column=1, padx=8)
        ctk.CTkButton(
            zoom_row, text="↻ Сброс", width=86, height=28,
            command=self.waveform.reset_view
        ).grid(row=0, column=2, padx=(2, 10), pady=3)

        self.codec_card = ctk.CTkFrame(
            frame, fg_color=("#FFFFFF", "#273341"), corner_radius=14,
            border_width=1, border_color=("#E3E8F0", "#405065"))
        self.codec_card.grid(row=8, column=0, sticky="ew", padx=16, pady=(0, 5))
        codec_row = ctk.CTkFrame(self.codec_card, fg_color="transparent")
        codec_row.pack(fill="x", padx=12, pady=(7, 4))
        ctk.CTkLabel(codec_row, text="♫", width=28).pack(side="left")
        ctk.CTkLabel(codec_row, text="Формат").pack(side="left", padx=(4, 8))
        self.format_menu = ctk.CTkOptionMenu(
            codec_row, values=list(FORMATS), width=112, command=self.on_format)
        self.format_menu.set(self.settings["target_format"])
        self.format_menu.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(codec_row, text="Битрейт").pack(side="left", padx=(0, 8))
        self.bitrate_menu = ctk.CTkOptionMenu(
            codec_row, values=list(BITRATES), width=105, command=self.on_bitrate)
        self.bitrate_menu.set(self.settings["bitrate"])
        self.bitrate_menu.pack(side="left", padx=(0, 19))
        self.vbr_var = ctk.BooleanVar(value=self.settings["vbr_enabled"])
        self.vbr_checkbox = ctk.CTkCheckBox(
            codec_row, text="VBR", variable=self.vbr_var, width=75,
            command=self.on_vbr_changed)
        self.vbr_checkbox.pack(side="left")

        quality_row = ctk.CTkFrame(self.codec_card, fg_color="transparent")
        quality_row.pack(fill="x", padx=12, pady=(0, 7))
        ctk.CTkLabel(quality_row, text="▥", width=28).pack(side="left")
        ctk.CTkLabel(
            quality_row, text="Качество MP3 VBR (0 — лучшее)"
        ).pack(side="left", padx=(4, 10))
        self.vbr_quality_menu = ctk.CTkOptionMenu(
            quality_row, values=[str(n) for n in range(10)], width=72,
            command=self.on_vbr_quality)
        self.vbr_quality_menu.set(str(self.settings["vbr_quality"]))
        self.vbr_quality_menu.pack(side="left")
        self._update_audio_options()

        self.fade_card = ctk.CTkFrame(
            frame, fg_color=("#EEF4FF", "#26364F"), corner_radius=14,
            border_width=1, border_color=("#DAE7FA", "#455D7D"))
        self.fade_card.grid(row=9, column=0, sticky="ew", padx=16, pady=(0, 5))
        fades = ctk.CTkFrame(self.fade_card, fg_color="transparent")
        fades.pack(fill="x", padx=12, pady=(7, 5))
        self.fade_var = ctk.BooleanVar(value=self.settings["fade_enabled"])
        self.fade_checkbox = ctk.CTkCheckBox(
            fades, text="Плавное появление и затухание",
            variable=self.fade_var, command=self.on_fade_changed)
        self.fade_checkbox.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(fades, text="Длительность, с").pack(side="left", padx=(0, 8))
        self.fade_menu = ctk.CTkOptionMenu(
            fades, values=["0.5", "1.0", "2.0", "3.0", "5.0"], width=85,
            command=self.on_fade_seconds)
        self.fade_menu.set(str(self.settings["fade_seconds"]))
        self.fade_menu.pack(side="left")
        ctk.CTkFrame(
            self.fade_card, height=1, corner_radius=0,
            fg_color=("#D7E5F7", "#445D80")
        ).pack(fill="x", padx=17)
        curves = ctk.CTkFrame(self.fade_card, fg_color="transparent")
        curves.pack(fill="x", padx=12, pady=(5, 7))
        curve_names = list(FADE_CURVES.values())
        ctk.CTkLabel(curves, text="⌁", width=28).pack(side="left")
        ctk.CTkLabel(curves, text="Появление").pack(side="left", padx=(4, 8))
        self.fade_in_menu = ctk.CTkOptionMenu(
            curves, values=curve_names, width=175,
            command=lambda label: self.on_fade_curve("fade_in_curve", label))
        self.fade_in_menu.set(FADE_CURVES[self.settings["fade_in_curve"]])
        self.fade_in_menu.pack(side="left", padx=(0, 18))
        ctk.CTkLabel(curves, text="⌁", width=28).pack(side="left")
        ctk.CTkLabel(curves, text="Затухание").pack(side="left", padx=(4, 8))
        self.fade_out_menu = ctk.CTkOptionMenu(
            curves, values=curve_names, width=175,
            command=lambda label: self.on_fade_curve("fade_out_curve", label))
        self.fade_out_menu.set(FADE_CURVES[self.settings["fade_out_curve"]])
        self.fade_out_menu.pack(side="left")
        self._update_fade_state()
        self._sync_fade_overlay()

        self.folder_card = ctk.CTkFrame(
            frame, fg_color=("#FFFFFF", "#273341"), corner_radius=14,
            border_width=1, border_color=("#E3E8F0", "#405065"))
        self.folder_card.grid(row=10, column=0, sticky="ew", padx=16, pady=(0, 5))
        self.folder_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.folder_card, text="📁", width=38).grid(
            row=0, column=0, padx=(12, 0), pady=6)
        self.folder_label = ctk.CTkLabel(
            self.folder_card, text="Папка: рядом с оригиналом", anchor="w")
        self.folder_label.grid(row=0, column=1, sticky="ew", padx=(6, 10), pady=6)
        self.folder_button = ctk.CTkButton(
            self.folder_card, text="📁 Изменить", width=136, height=30,
            command=self.choose_folder)
        self.folder_button.grid(row=0, column=2, padx=(0, 12), pady=6)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer = footer
        footer.grid(row=2, column=0, sticky="ew", padx=17, pady=(2, 8))
        footer.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(footer, text="Готов к работе", anchor="w")
        self.status.grid(row=0, column=0, sticky="ew")
        self.progress = ctk.CTkProgressBar(footer)
        self.progress.grid(row=1, column=0, sticky="ew", pady=3)
        self.progress.set(0)
        buttons = ctk.CTkFrame(footer, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="e")
        self.play_button = ctk.CTkButton(
            buttons, text="▶ Воспроизвести", width=155,
            state="disabled", command=self.toggle_play)
        self.play_button.pack(side="left", padx=(0, 10))
        self.cancel_button = ctk.CTkButton(buttons, text="Отмена", width=100, state="disabled",
                                            fg_color="gray40", command=self.cancel)
        self.cancel_button.pack(side="left", padx=(0, 10))
        self.run_button = ctk.CTkButton(buttons, text="Конвертировать", width=170,
                                         state="disabled", command=self.convert)
        self.run_button.pack(side="left")
        self._refresh()
        self.body_font = apply_body_font(self, excluded=(self.main_heading,))
        self._fit_editor_to_window()
        self.after(100, self._poll)

    def _fit_editor_to_window(self):
        """Make the entire fixed editor visible rather than hiding its bottom.

        Grid's requested height reflects CustomTkinter DPI/font scaling, so
        enforce it instead of relying on one magic minimum for every monitor.
        """
        self.update_idletasks()
        minimum = max(620, self.winfo_reqheight())
        self.minsize(810, minimum)
        # Match the natural content height: no artificial grey space below
        # the output folder card when the redundant result row is absent.
        self.geometry(f"920x{minimum}")

    def _save(self):
        if self._save_timer is not None:
            self.after_cancel(self._save_timer)
            self._save_timer = None
        try:
            save_settings(self.settings)
        except OSError as exc:
            messagebox.showwarning("Настройки", str(exc))

    def _schedule_save(self):
        # Never rewrite config.json on every mouse move / scroll event.
        if self._loading_source or self.closing:
            return
        if self._save_timer is not None:
            self.after_cancel(self._save_timer)
        self._save_timer = self.after(600, self._save)

    def _record_view(self):
        if self.info is None:
            return
        self.settings["waveform_zoom"] = self.waveform.viewport.zoom_level
        self.settings["waveform_start"] = self.waveform.viewport.start
        self._schedule_save()

    def on_appearance(self, value):
        theme = {"Светлая": "Light", "Тёмная": "Dark", "Системная": "System"}[value]
        self.settings["appearance"] = theme
        ctk.set_appearance_mode(theme)
        self.waveform.redraw()
        if self._help_window is not None and self._help_window.winfo_exists():
            self._help_window.refresh_theme()
        self._save()

    def open_help(self):
        """Show one reusable reference window with every supported fade curve."""
        if self._help_window is not None and self._help_window.winfo_exists():
            self._help_window.lift()
            self._help_window.focus()
            return
        self._help_window = FadeHelpWindow(self)
        self._help_window.focus()

    def _drop_enter(self, event):
        if self.busy or self.probing:
            return REFUSE_DROP
        self.waveform.configure(highlightthickness=2, highlightbackground="#2F87DC")
        return COPY

    def _drop_leave(self, event=None):
        self.waveform.configure(highlightthickness=0)
        return COPY

    def _on_wave_drop(self, event):
        """Windows Explorer CF_HDROP delivered as a Tcl file list."""
        self._drop_leave()
        if self.busy or self.probing:
            return REFUSE_DROP
        try:
            path = dropped_audio_path(event.data, self.tk.splitlist)
        except ValueError as exc:
            messagebox.showwarning("Аудиофайл", str(exc), parent=self)
            return REFUSE_DROP
        self.open_file(path)
        return COPY

    def choose_file(self):
        folder = self.settings["last_source_dir"]
        if not folder or not Path(folder).is_dir():
            folder = str(Path.home())
        name = filedialog.askopenfilename(
            parent=self, title="Выбрать аудиофайл", initialdir=folder,
            filetypes=[("Аудиофайлы", "*.flac *.mp3 *.wav *.ape *.m4a *.aac *.ogg *.opus *.wma"),
                       ("Все файлы", "*.*")])
        if name:
            self.open_file(Path(name))

    def open_file(self, path: Path):
        if self.busy or self.probing:
            return
        self._stop_playback()
        self._cancel_detail_waveform()
        self._save()
        self.info = None
        self.source_sequence += 1
        self.waveform.set_peaks(())
        self.waveform.reset_view()
        self.probing = True
        self.path_label.configure(text=str(path))
        self.status.configure(text="Анализ аудиофайла…")
        self.progress.set(0)
        self._refresh()
        def worker():
            try:
                self.events.put(("loaded", probe_audio(path)))
            except (OSError, ValueError) as exc:
                self.events.put(("open_error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _loaded(self, info):
        self.probing = False
        self.info = info
        self._loading_source = True
        same_source = self.settings["last_source_path"] == str(info.path)
        saved_start = self.settings["clip_start"]
        saved_end = self.settings["clip_end"]
        saved_zoom = self.settings["waveform_zoom"]
        saved_view_start = self.settings["waveform_start"]
        self.settings["last_source_dir"] = str(info.path.parent)
        self.settings["last_source_path"] = str(info.path)
        self.metadata.configure(text=f"Длительность: {clock(info.duration)}    "
                                     f"Кодек: {info.codec.upper()}    "
                                     f"{info.sample_rate} Гц    {info.channels} кан.")
        self.slider.configure(to=info.duration, state="normal")
        if same_source and 0 <= saved_start < saved_end <= info.duration:
            left, right = saved_start, saved_end
        else:
            left, right = 0.0, info.duration
        self.slider.set([left, right])
        self.on_range((left, right))
        if same_source:
            self.waveform.viewport.span = 1 / saved_zoom
            self.waveform.viewport.start = max(0.0, min(
                saved_view_start, 1 - self.waveform.viewport.span))
            self.waveform._view_changed()
        self._sync_fade_overlay()
        self._loading_source = False
        self._save()
        self.status.configure(text="Построение звуковой волны…")
        self._preview()
        self._start_waveform(info)

    def _start_waveform(self, info):
        sequence = self.source_sequence
        def worker():
            try:
                peaks = extract_waveform(info.path)
                self.events.put(("waveform", (sequence, peaks)))
            except (OSError, ValueError) as exc:
                self.events.put(("waveform_error", (sequence, str(exc))))
        threading.Thread(target=worker, daemon=True).start()

    def _cancel_detail_waveform(self):
        self._detail_generation += 1
        if self._detail_timer is not None:
            self.after_cancel(self._detail_timer)
            self._detail_timer = None

    def _schedule_detail_waveform(self):
        """Coalesce wheel/drag events so zooming never blocks the Tk UI."""
        self._cancel_detail_waveform()
        if (self.info is None or not self.waveform.peaks
                or self.waveform.viewport.zoom_level < 1.10):
            return
        self._detail_timer = self.after(280, self._start_detail_waveform)

    def _start_detail_waveform(self):
        self._detail_timer = None
        if self.closing or self.info is None or not self.waveform.peaks:
            return
        info = self.info
        viewport = self.waveform.viewport
        start, end = viewport.start, viewport.end
        duration = (end - start) * info.duration
        if duration <= 0.05:
            return
        sequence = self.source_sequence
        generation = self._detail_generation
        width = max(1024, min(4096, self.waveform.winfo_width() * 2))

        def worker():
            try:
                peaks = extract_waveform(
                    info.path, width=width, height=120, timeout=90,
                    start=start * info.duration, duration=duration)
                self.events.put((
                    "waveform_detail", (sequence, generation, start, end, peaks)))
            except (OSError, ValueError):
                # Keep rendering the full-track overview when detail decoding
                # cannot be performed; do not interrupt editing or playback.
                pass
        threading.Thread(target=worker, daemon=True).start()

    def on_range(self, values):
        if self.info is None:
            return
        start, end = (float(v) for v in values)
        self.left_time.configure(text=clock(max(start, 0)))
        self.right_time.configure(text=clock(max(end, 0)))
        self.length_time.configure(text="Выделено: " + (clock(end - start) if end >= start else "—"))
        self.waveform.set_selection(start, end, self.info.duration)
        self.settings["clip_start"] = start
        self.settings["clip_end"] = end
        self._schedule_save()
        # Do not call _refresh() here: it reconfigures the range slider and
        # previously slowed down every mouse-move during dragging.

    def _on_waveform_view(self, zoom):
        self.zoom_label.configure(text=f"×{zoom:.1f}")
        self._record_view()
        self._schedule_detail_waveform()

    def _waveform_edit(self, side, position, finished):
        if self.info is None or self.probing or self.busy:
            return
        left, right = (float(x) for x in self.slider.get())
        value = position * self.info.duration
        min_gap = min(0.05, self.info.duration / 2)
        if side == "left":
            left = max(0.0, min(value, right - min_gap))
        else:
            right = min(self.info.duration, max(value, left + min_gap))
        self.slider.set([left, right])
        self._slider_moved(side)
        if finished:
            self._slider_released()

    def on_fade_changed(self):
        self.settings["fade_enabled"] = bool(self.fade_var.get())
        self._update_fade_state()
        self._sync_fade_overlay()
        self._save()

    def on_fade_seconds(self, seconds):
        self.settings["fade_seconds"] = float(seconds)
        self._sync_fade_overlay()
        self._save()

    def on_fade_curve(self, parameter, label):
        if parameter not in ("fade_in_curve", "fade_out_curve"):
            raise ValueError("Unknown fade parameter")
        self.settings[parameter] = next(
            key for key, name in FADE_CURVES.items() if name == label)
        self._sync_fade_overlay()
        self._save()

    def _sync_fade_overlay(self):
        duration = self.info.duration if self.info else 0.0
        self.waveform.set_fade(
            self.settings["fade_enabled"], self.settings["fade_seconds"], duration,
            self.settings["fade_in_curve"], self.settings["fade_out_curve"])

    def _update_fade_state(self):
        enabled = self.fade_var.get() and not self.busy
        state = "normal" if enabled else "disabled"
        self.fade_menu.configure(state=state)
        self.fade_in_menu.configure(state=state)
        self.fade_out_menu.configure(state=state)

    def _update_audio_options(self):
        fmt = self.settings["target_format"]
        vbr = self.settings["vbr_enabled"]
        self.vbr_checkbox.configure(
            state="normal" if fmt in ("MP3", "Opus") and not self.busy else "disabled")
        self.bitrate_menu.configure(
            state="normal" if fmt in ("MP3", "Opus") and not self.busy
            and not (fmt == "MP3" and vbr) else "disabled")
        self.vbr_quality_menu.configure(
            state="normal" if fmt == "MP3" and vbr and not self.busy else "disabled")

    def on_vbr_changed(self):
        self.settings["vbr_enabled"] = bool(self.vbr_var.get())
        self._update_audio_options()
        self._save()

    def on_vbr_quality(self, quality):
        self.settings["vbr_quality"] = int(quality)
        self._save()

    def _cancel_preview(self):
        if self._preview_timer is not None:
            self.after_cancel(self._preview_timer)
            self._preview_timer = None

    def _stop_playback(self):
        self._cancel_preview()
        self._last_drag_side = None
        self.player.stop()
        self._playing = False
        self.waveform.set_playhead(None)
        self.play_button.configure(text="▶ Воспроизвести")

    def _left_moved(self, value):
        self._slider_moved("left")

    def _right_moved(self, value):
        self._slider_moved("right")

    def _slider_moved(self, side):
        self.on_range(self.slider.get())
        if self.info is None or self.busy or self.probing:
            return
        self._cancel_preview()
        if self._playing:
            self.player.stop()
            self._playing = False
            self.waveform.set_playhead(None)
            self.play_button.configure(text="▶ Воспроизвести")
        self._last_drag_side = side
        # Don't restart FFplay for every pixel; play when the thumb rests.
        self._preview_timer = self.after(250, lambda: self._start_preview(side))

    def _start_preview(self, side):
        self._preview_timer = None
        self._play_segment(side)

    def _slider_released(self, event=None):
        if self._last_drag_side is None:
            return
        side = self._last_drag_side
        self._last_drag_side = None
        pending = self._preview_timer is not None
        self._cancel_preview()
        if pending:
            self._play_segment(side)

    def _play_segment(self, mode):
        if self.info is None or self.busy or self.probing:
            return
        try:
            left, right = self.slider.get()
            clip = ClipRange(float(left), float(right), self.info.duration)
            window = listening_window(mode, clip.start, clip.end)
        except ValueError:
            return
        self.player.play(
            self.info.path, window,
            lambda generation, message: self.events.put(
                ("play_error", (generation, message))))
        self._playing = True
        self.waveform.set_playhead(window.start, self.info.duration)
        self.play_button.configure(text="■ Остановить")
        self.status.configure(text="Прослушивание…")

    def toggle_play(self):
        if self._playing or self._preview_timer is not None:
            self._stop_playback()
            self.status.configure(text="Воспроизведение остановлено")
        else:
            self._cancel_preview()
            self._last_drag_side = None
            self._play_segment("selection")

    def on_format(self, value):
        self.settings["target_format"] = value
        self._update_audio_options()
        self._save()
        self._preview()

    def on_bitrate(self, value):
        self.settings["bitrate"] = value
        self._save()

    def choose_folder(self):
        if self.busy:
            return
        folder = self.settings["output_dir"] or (str(self.info.path.parent) if self.info else str(Path.home()))
        if not Path(folder).is_dir():
            folder = str(Path.home())
        chosen = filedialog.askdirectory(parent=self, initialdir=folder, title="Выбрать папку")
        if chosen:
            self.settings["output_dir"] = chosen
            self._save()
            self._preview()

    def _destination(self):
        assert self.info is not None
        folder = Path(self.settings["output_dir"]) if self.settings["output_dir"] else self.info.path.parent
        return output_path(self.info.path, folder, self.settings["target_format"])

    def _preview(self):
        if self.info:
            try:
                path = self._destination()
                self.folder_label.configure(text=f"Папка: {path.parent}")
            except ValueError as exc:
                self.status.configure(text=f"Ошибка параметров: {exc}")
        self._refresh()

    def _refresh(self):
        enabled = self.info is not None and not self.busy and not self.probing
        if enabled:
            try:
                start, end = self.slider.get()
                ClipRange(float(start), float(end), self.info.duration)
                self._destination()
            except ValueError:
                enabled = False
        self.run_button.configure(state="normal" if enabled else "disabled")
        self.play_button.configure(state="normal" if enabled else "disabled")
        self.open_button.configure(state="disabled" if self.busy or self.probing else "normal")
        self.folder_button.configure(state="disabled" if self.busy else "normal")
        self.format_menu.configure(state="disabled" if self.busy else "normal")
        self._update_audio_options()
        self.fade_checkbox.configure(state="disabled" if self.busy else "normal")
        self._update_fade_state()
        self.slider.configure(state="normal" if self.info is not None and not self.busy and not self.probing else "disabled")

    def convert(self):
        if self.info is None or self.busy or self.probing:
            return
        try:
            start, end = self.slider.get()
            clip = ClipRange(float(start), float(end), self.info.duration)
            destination = self._destination()
            job = ConversionJob(
                self.info, destination, self.settings["target_format"],
                clip, self.settings["bitrate"],
                fade_enabled=self.settings["fade_enabled"],
                fade_seconds=self.settings["fade_seconds"],
                fade_in_curve=self.settings["fade_in_curve"],
                fade_out_curve=self.settings["fade_out_curve"],
                vbr_enabled=self.settings["vbr_enabled"],
                vbr_quality=self.settings["vbr_quality"])
        except (ValueError, OSError) as exc:
            messagebox.showwarning("Параметры", str(exc))
            return
        self._stop_playback()
        self.runner = ConversionRunner()
        self.busy = True
        self.progress.set(0)
        self.status.configure(text="Конвертация…")
        self.cancel_button.configure(state="normal")
        self._refresh()
        def worker():
            try:
                result = self.runner.run(job, lambda value: self.events.put(("progress", value)))
                self.events.put(("finished", result))
            except ConversionCancelled:
                self.events.put(("cancelled", None))
            except (OSError, RuntimeError, ValueError) as exc:
                self.events.put(("convert_error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def cancel(self):
        if self.runner:
            self.cancel_button.configure(state="disabled")
            self.status.configure(text="Отмена…")
            self.runner.cancel()

    def _end(self):
        self.runner = None
        self.busy = False
        self.cancel_button.configure(state="disabled")
        self._refresh()

    def _poll(self):
        if self.closing:
            return
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "loaded":
                    self._loaded(data)
                elif kind == "open_error":
                    self.probing = False
                    self.status.configure(text="Ошибка открытия файла")
                    self._refresh()
                    messagebox.showerror("Аудиофайл", data)
                elif kind == "waveform":
                    sequence, peaks = data
                    if sequence == self.source_sequence and self.info is not None:
                        self.waveform.set_peaks(peaks)
                        self._schedule_detail_waveform()
                        if not self.busy:
                            self.status.configure(text="Аудиофайл загружен")
                elif kind == "waveform_detail":
                    sequence, generation, start, end, peaks = data
                    if (sequence == self.source_sequence
                            and generation == self._detail_generation
                            and self.info is not None):
                        self.waveform.set_detail_peaks(start, end, peaks)
                elif kind == "waveform_error":
                    sequence, error = data
                    if sequence == self.source_sequence and not self.busy:
                        self.status.configure(text="Waveform недоступен: " + error[:160])
                elif kind == "play_error":
                    generation, message = data
                    if generation == self.player.generation:
                        self._stop_playback()
                        self.status.configure(text="Ошибка воспроизведения")
                        messagebox.showerror("Воспроизведение", message)
                elif kind == "progress":
                    self.progress.set(data)
                    self.status.configure(text=f"Конвертация: {data * 100:.1f}%")
                elif kind == "finished":
                    self._end()
                    self.progress.set(1)
                    self.status.configure(text=f"Готово: {data.name}")
                elif kind == "cancelled":
                    self._end()
                    self.progress.set(0)
                    self.status.configure(text="Отменено")
                elif kind == "convert_error":
                    self._end()
                    self.status.configure(text="Ошибка конвертации")
                    messagebox.showerror("Конвертация", data)
        except queue.Empty:
            pass
        if self._playing:
            position = self.player.position()
            if position is None:
                self._playing = False
                self.waveform.set_playhead(None)
                self.play_button.configure(text="▶ Воспроизвести")
            elif self.info is not None:
                self.waveform.set_playhead(position, self.info.duration)
        self.after(100, self._poll)

    def _close(self):
        self.closing = True
        self._cancel_detail_waveform()
        self._stop_playback()
        if self.runner:
            self.runner.cancel()
        self._save()
        if self._help_window is not None and self._help_window.winfo_exists():
            self._help_window.destroy()
        self.destroy()
