"""The CustomTkinter presentation layer; no FFmpeg work on the UI thread."""

from pathlib import Path
from tkinter import filedialog, messagebox
import queue
import threading

import customtkinter as ctk
from vendor.CTkRangeSlider import CTkRangeSlider

from version import APP_VERSION
from .converter import (BITRATES, FORMATS, ConversionCancelled,
                        ConversionJob, ConversionRunner, output_path)
from .media import probe_audio
from .player import AudioPlayer, listening_window
from .waveform import extract_waveform
from .waveform_view import WaveformView
from .selection import ClipRange, clock
from .settings import DEFAULTS, load_settings, save_settings


ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


class AudioCoderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"AudioCoder {APP_VERSION}")
        self.geometry("800x730")
        self.minsize(700, 680)
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
        self._last_drag_side = None
        self._playing = False
        try:
            self.settings = load_settings()
        except (ValueError, OSError) as exc:
            self.settings = DEFAULTS.copy()
            self.after(50, lambda error=str(exc): messagebox.showwarning("Настройки", error))
        ctk.set_appearance_mode(self.settings["appearance"])

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text="AudioCoder", font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text=f"v{APP_VERSION}", text_color="gray").pack(side="right")
        self.appearance_menu = ctk.CTkOptionMenu(
            header, values=["Светлая", "Тёмная", "Системная"], width=125,
            command=self.on_appearance)
        self.appearance_menu.set({
            "Light": "Светлая", "Dark": "Тёмная", "System": "Системная",
        }[self.settings["appearance"]])
        self.appearance_menu.pack(side="right", padx=(0, 16))

        frame = ctk.CTkFrame(self, corner_radius=14)
        frame.grid(row=1, column=0, sticky="nsew", padx=22, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text="Исходный аудиофайл", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 5))
        self.path_label = ctk.CTkLabel(frame, text="Файл не выбран", anchor="w")
        self.path_label.grid(row=1, column=0, sticky="ew", padx=18)
        self.open_button = ctk.CTkButton(frame, text="Выбрать файл", command=self.choose_file)
        self.open_button.grid(row=2, column=0, sticky="w", padx=18, pady=(8, 12))
        self.metadata = ctk.CTkLabel(frame, text="Длительность: —    Кодек: —", anchor="w")
        self.metadata.grid(row=3, column=0, sticky="ew", padx=18)

        times = ctk.CTkFrame(frame, fg_color="transparent")
        times.grid(row=4, column=0, sticky="ew", padx=18, pady=(18, 4))
        times.grid_columnconfigure(1, weight=1)
        self.left_time = ctk.CTkLabel(times, text="00:00:00.000")
        self.left_time.grid(row=0, column=0, sticky="w")
        self.length_time = ctk.CTkLabel(times, text="Выделенный фрагмент: —")
        self.length_time.grid(row=0, column=1)
        self.right_time = ctk.CTkLabel(times, text="00:00:00.000")
        self.right_time.grid(row=0, column=2, sticky="e")
        self.waveform = WaveformView(
            frame, height=140, on_edit=self._waveform_edit,
            on_view_change=self._on_waveform_view)
        self.waveform.grid(row=5, column=0, sticky="ew", padx=24, pady=(5, 4))
        self.slider = CTkRangeSlider(
            frame, from_=0, to=1, height=20, state="disabled",
            command=(self._left_moved, self._right_moved))
        self.slider.grid(row=6, column=0, sticky="ew", padx=24, pady=(5, 17))
        # The vendored range slider handles mouse events on its inner Canvas.
        # Keep its internal drag handlers; add only a release notification.
        self.slider._canvas.bind("<ButtonRelease-1>", self._slider_released, add="+")
        zoom_row = ctk.CTkFrame(frame, fg_color="transparent")
        zoom_row.grid(row=7, column=0, sticky="ew", padx=24, pady=(0, 5))
        zoom_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            zoom_row, text="Колесо — масштаб • Правая кнопка — сдвиг • Левая — границы",
            font=ctk.CTkFont(size=11)
        ).grid(row=0, column=0, sticky="w")
        self.zoom_label = ctk.CTkLabel(zoom_row, text="×1.0", width=50)
        self.zoom_label.grid(row=0, column=1, padx=(5, 8))
        ctk.CTkButton(zoom_row, text="Сброс", width=65,
                      command=self.waveform.reset_view).grid(row=0, column=2)

        options = ctk.CTkFrame(frame, fg_color="transparent")
        options.grid(row=8, column=0, sticky="w", padx=18, pady=6)
        ctk.CTkLabel(options, text="Формат").pack(side="left", padx=(0, 8))
        self.format_menu = ctk.CTkOptionMenu(
            options, values=list(FORMATS), width=115, command=self.on_format)
        self.format_menu.set(self.settings["target_format"])
        self.format_menu.pack(side="left", padx=(0, 24))
        ctk.CTkLabel(options, text="MP3 битрейт").pack(side="left", padx=(0, 8))
        self.bitrate_menu = ctk.CTkOptionMenu(
            options, values=list(BITRATES), width=110, command=self.on_bitrate)
        self.bitrate_menu.set(self.settings["bitrate"])
        self.bitrate_menu.pack(side="left")

        fades = ctk.CTkFrame(frame, fg_color="transparent")
        fades.grid(row=9, column=0, sticky="w", padx=18, pady=(5, 7))
        self.fade_var = ctk.BooleanVar(value=self.settings["fade_enabled"])
        self.fade_checkbox = ctk.CTkCheckBox(
            fades, text="Плавное логарифмическое появление и затухание",
            variable=self.fade_var, command=self.on_fade_changed)
        self.fade_checkbox.pack(side="left", padx=(0, 15))
        ctk.CTkLabel(fades, text="Длительность, с").pack(side="left", padx=(0, 6))
        self.fade_menu = ctk.CTkOptionMenu(
            fades, values=["0.5", "1.0", "2.0", "3.0", "5.0"], width=82,
            command=self.on_fade_seconds)
        self.fade_menu.set(str(self.settings["fade_seconds"]))
        self.fade_menu.pack(side="left")
        self._update_fade_state()
        self._sync_fade_overlay()

        destination = ctk.CTkFrame(frame, fg_color="transparent")
        destination.grid(row=10, column=0, sticky="ew", padx=18, pady=8)
        destination.grid_columnconfigure(0, weight=1)
        self.folder_label = ctk.CTkLabel(destination, text="Сохранение: рядом с оригиналом", anchor="w")
        self.folder_label.grid(row=0, column=0, sticky="ew")
        self.folder_button = ctk.CTkButton(destination, text="Изменить", width=100, command=self.choose_folder)
        self.folder_button.grid(row=0, column=1)
        self.target_label = ctk.CTkLabel(frame, text="Результат: —", anchor="w")
        self.target_label.grid(row=11, column=0, sticky="ew", padx=18, pady=(2, 8))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=22, pady=(4, 20))
        footer.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(footer, text="Готов к работе", anchor="w")
        self.status.grid(row=0, column=0, sticky="ew")
        self.progress = ctk.CTkProgressBar(footer)
        self.progress.grid(row=1, column=0, sticky="ew", pady=7)
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
        self.after(100, self._poll)

    def _save(self):
        try:
            save_settings(self.settings)
        except OSError as exc:
            messagebox.showwarning("Настройки", str(exc))

    def on_appearance(self, value):
        theme = {"Светлая": "Light", "Тёмная": "Dark", "Системная": "System"}[value]
        self.settings["appearance"] = theme
        ctk.set_appearance_mode(theme)
        self.waveform.redraw()
        self._save()

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
        self.settings["last_source_dir"] = str(info.path.parent)
        self._save()
        self.metadata.configure(text=f"Длительность: {clock(info.duration)}    "
                                     f"Кодек: {info.codec.upper()}    "
                                     f"{info.sample_rate} Гц    {info.channels} кан.")
        self.slider.configure(to=info.duration, state="normal")
        self.slider.set([0.0, info.duration])
        self.on_range((0.0, info.duration))
        self._sync_fade_overlay()
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

    def on_range(self, values):
        if self.info is None:
            return
        start, end = (float(v) for v in values)
        self.left_time.configure(text=clock(max(start, 0)))
        self.right_time.configure(text=clock(max(end, 0)))
        self.length_time.configure(text="Выделено: " + (clock(end - start) if end >= start else "—"))
        self.waveform.set_selection(start, end, self.info.duration)
        # Do not call _refresh() here: it reconfigures the range slider and
        # previously slowed down every mouse-move during dragging.

    def _on_waveform_view(self, zoom):
        self.zoom_label.configure(text=f"×{zoom:.1f}")

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

    def _sync_fade_overlay(self):
        duration = self.info.duration if self.info else 0.0
        self.waveform.set_fade(self.settings["fade_enabled"], self.settings["fade_seconds"], duration)

    def _update_fade_state(self):
        self.fade_menu.configure(state="normal" if self.fade_var.get() else "disabled")

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
                action = " (будет заменён)" if path.exists() else ""
                self.target_label.configure(text=f"Результат: {path.name}{action}")
            except ValueError as exc:
                self.target_label.configure(text=f"Ошибка: {exc}")
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
        self.bitrate_menu.configure(
            state="normal" if not self.busy and self.settings["target_format"] == "MP3" else "disabled")
        self.fade_checkbox.configure(state="disabled" if self.busy else "normal")
        self.fade_menu.configure(
            state="normal" if not self.busy and self.fade_var.get() else "disabled")
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
                fade_seconds=self.settings["fade_seconds"])
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
                        if not self.busy:
                            self.status.configure(text="Аудиофайл загружен")
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
        self._stop_playback()
        if self.runner:
            self.runner.cancel()
        self.destroy()
