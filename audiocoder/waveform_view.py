"""Responsive Tkinter Canvas waveform with selected-range highlighting.

The drawing represents the entire source file. The slider remains the
single source of truth for start/end positions.
"""
import tkinter as tk
import customtkinter as ctk


class WaveformView(tk.Canvas):
    def __init__(self, master, *, height=118, **kwargs):
        super().__init__(master, height=height, borderwidth=0, highlightthickness=0,
                         relief="flat", **kwargs)
        self.peaks: tuple[float, ...] = ()
        self.selection: tuple[float, float] = (0.0, 1.0)
        self._pending = False
        self.bind("<Configure>", lambda event: self.redraw())
        self.redraw()

    def set_peaks(self, peaks):
        self.peaks = tuple(max(0.0, min(1.0, float(p))) for p in peaks)
        self.redraw()

    def set_selection(self, start: float, end: float, duration: float):
        if duration <= 0:
            self.selection = (0.0, 1.0)
        else:
            self.selection = (max(0.0, min(1.0, start / duration)),
                              max(0.0, min(1.0, end / duration)))
        self.redraw()

    def redraw(self):
        # Coalesce many drag events into one frame.
        if not self._pending:
            self._pending = True
            self.after_idle(self._paint)

    def _paint(self):
        self._pending = False
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        dark = ctk.get_appearance_mode() == "Dark"
        background = "#202938" if dark else "#F1F5F9"
        active_background = "#243B55" if dark else "#DCEBFB"
        muted = "#7A889A" if dark else "#A7B4C4"
        active = "#53B5FF" if dark else "#1874C9"
        center = height / 2
        self.configure(bg=background)
        self.delete("all")
        x1 = round(self.selection[0] * width)
        x2 = round(self.selection[1] * width)
        self.create_rectangle(x1, 0, x2, height, fill=active_background, outline="", tags="selection")
        if not self.peaks:
            self.create_text(width / 2, center, text="Звуковая волна появится после загрузки",
                             fill=muted, font=("Segoe UI", 12))
            return
        n = len(self.peaks)
        for x in range(width):
            # Resample displayed bars on resize; raw waveform stays unchanged.
            peak = self.peaks[min(n - 1, int(x * n / width))]
            half_height = max(0.5, peak * (height / 2 - 5))
            self.create_line(x, center - half_height, x, center + half_height,
                             fill=active if x1 <= x <= x2 else muted, width=1)
        for pos in (x1, x2):
            self.create_line(pos, 0, pos, height, fill=active, width=1)
