"""Smooth, zoomable waveform. Ctrl-free wheel zoom and right-drag panning.

Draw waveform pixels to one cached PhotoImage, not hundreds of Canvas items
on each handle movement. The playhead remains a lightweight Canvas line.
"""
import tkinter as tk
import math
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from .waveform_navigation import WaveformViewport, clamp


class WaveformView(tk.Canvas):
    def __init__(self, master, *, height=118, on_edit=None, on_view_change=None, **kwargs):
        super().__init__(master, height=height, borderwidth=0,
                         highlightthickness=0, relief="flat", **kwargs)
        self.peaks: tuple[float, ...] = ()
        self.selection: tuple[float, float] = (0.0, 1.0)
        self.playhead: float | None = None
        self.fade_enabled = False
        self.fade_fraction = 0.0
        self.viewport = WaveformViewport()
        self.on_edit = on_edit
        self.on_view_change = on_view_change
        self._dragging = None
        self._pan_last_x = None
        self._pending = False
        self._image = None
        self._image_item = self.create_image(0, 0, anchor="nw")
        self._playhead_item = self.create_line(0, 0, 0, height, state="hidden", width=2)
        self.bind("<Configure>", lambda event: self.redraw())
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda e: self._wheel(e, 1))
        self.bind("<Button-5>", lambda e: self._wheel(e, -1))
        self.bind("<ButtonPress-3>", self._pan_start)
        self.bind("<B3-Motion>", self._pan_move)
        self.bind("<ButtonRelease-3>", self._pan_end)
        self.bind("<ButtonPress-1>", self._edit_start)
        self.bind("<B1-Motion>", self._edit_move)
        self.bind("<ButtonRelease-1>", self._edit_end)
        self.redraw()

    def reset_view(self):
        self.viewport.reset()
        self._view_changed()

    def set_peaks(self, peaks):
        self.peaks = tuple(clamp(float(p), 0.0, 1.0) for p in peaks)
        self.redraw()

    def set_selection(self, start: float, end: float, duration: float):
        new = ((clamp(start / duration, 0.0, 1.0),
                clamp(end / duration, 0.0, 1.0)) if duration > 0 else (0.0, 1.0))
        if new != self.selection:
            self.selection = new
            self.redraw()

    def set_fade(self, enabled: bool, seconds: float, duration: float):
        self.fade_enabled = bool(enabled)
        self.fade_fraction = max(0.0, seconds / duration) if duration > 0 else 0.0
        self.redraw()

    def set_playhead(self, position: float | None, duration: float = 1.0):
        self.playhead = (None if position is None or duration <= 0 else
                         clamp(position / duration, 0.0, 1.0))
        self._draw_playhead()

    def _draw_playhead(self):
        w, h = max(self.winfo_width(), 1), max(self.winfo_height(), 1)
        if self.playhead is None or not (self.viewport.start <= self.playhead <= self.viewport.end):
            self.itemconfigure(self._playhead_item, state="hidden")
            return
        x = self.viewport.x_at(self.playhead, w)
        dark = ctk.get_appearance_mode() == "Dark"
        self.coords(self._playhead_item, x, 0, x, h)
        self.itemconfigure(self._playhead_item, state="normal",
                           fill="#E95757" if dark else "#CF2535")
        self.tag_raise(self._playhead_item)

    def _view_changed(self):
        self.redraw()
        if self.on_view_change:
            self.on_view_change(self.viewport.zoom_level)

    def _wheel(self, event, direction=None):
        if direction is None:
            direction = 1 if event.delta > 0 else -1
            if event.delta == 0:
                return "break"
        self.viewport.zoom(1.4 if direction > 0 else 1.0 / 1.4,
                           clamp(event.x / max(1, self.winfo_width()), 0.0, 1.0))
        self._view_changed()
        return "break"

    def _pan_start(self, event):
        self._pan_last_x = event.x
        return "break"

    def _pan_move(self, event):
        if self._pan_last_x is not None:
            self.viewport.pan(event.x - self._pan_last_x, self.winfo_width())
            self._pan_last_x = event.x
            self._view_changed()
        return "break"

    def _pan_end(self, event):
        self._pan_last_x = None
        return "break"

    def _edit_start(self, event):
        location = self.viewport.position_at(event.x, self.winfo_width())
        self._dragging = ("left" if abs(location - self.selection[0]) <=
                          abs(location - self.selection[1]) else "right")
        self._edit_move(event)
        return "break"

    def _edit_move(self, event):
        if self._dragging is not None and self.on_edit:
            location = self.viewport.position_at(event.x, self.winfo_width())
            self.on_edit(self._dragging, location, False)
        return "break"

    def _edit_end(self, event):
        if self._dragging is not None and self.on_edit:
            location = self.viewport.position_at(event.x, self.winfo_width())
            self.on_edit(self._dragging, location, True)
        self._dragging = None
        return "break"

    def redraw(self):
        if not self._pending:
            self._pending = True
            self.after_idle(self._paint)

    def _paint(self):
        self._pending = False
        w, h = max(1, self.winfo_width()), max(1, self.winfo_height())
        dark = ctk.get_appearance_mode() == "Dark"
        background = "#202938" if dark else "#F1F5F9"
        selected_bg = "#243B55" if dark else "#DCEBFB"
        inactive = "#7A889A" if dark else "#A7B4C4"
        active = "#53B5FF" if dark else "#1874C9"
        self.configure(background=background)
        image = Image.new("RGB", (w, h), background)
        draw = ImageDraw.Draw(image)
        x1 = int(self.viewport.x_at(self.selection[0], w))
        x2 = int(self.viewport.x_at(self.selection[1], w))
        draw.rectangle((max(x1, 0), 0, min(x2, w), h), fill=selected_bg) if x2 >= 0 and x1 <= w else None
        middle = h / 2
        if not self.peaks:
            draw.text((12, middle - 7), "Waveform", fill=inactive)
        else:
            n = len(self.peaks)
            for x in range(w):
                start = int((self.viewport.start + x / w * self.viewport.span) * n)
                end = int((self.viewport.start + (x + 1) / w * self.viewport.span) * n)
                start = min(max(start, 0), n - 1)
                end = min(max(end, start + 1), n)
                peak = max(self.peaks[start:end])
                half = max(0.5, peak * (middle - 5))
                draw.line((x, int(middle - half), x, int(middle + half)),
                          fill=active if x1 <= x <= x2 else inactive)
        for x in (x1, x2):
            if 0 <= x < w:
                draw.line((x, 0, x, h), fill=active, width=1)
        if self.fade_enabled and self.fade_fraction > 0:
            # Red logarithmic envelope guides like the user's reference sketch.
            # They are visual only; the same afade curve is applied at export.
            length = max(0.0, self.selection[1] - self.selection[0])
            fade_frac = min(self.fade_fraction, length / 2)
            if fade_frac > 0:
                top, bottom = 9, h - 9
                fade_colour = "#E04444" if dark else "#D92D2D"
                for begin, end, direction in (
                    (self.selection[0], self.selection[0] + fade_frac, "in"),
                    (self.selection[1] - fade_frac, self.selection[1], "out"),
                ):
                    points = []
                    for x in range(w):
                        position = self.viewport.position_at(x, w)
                        if not begin <= position <= end:
                            continue
                        progress = (position - begin) / fade_frac
                        if direction == "out":
                            progress = 1 - progress
                        gain = math.log1p(9 * progress) / math.log(10)
                        points.append((x, int(bottom - gain * (bottom - top))))
                    if len(points) >= 2:
                        draw.line(points, fill=fade_colour, width=2)
        self._image = ImageTk.PhotoImage(image, master=self)
        self.itemconfigure(self._image_item, image=self._image)
        self._draw_playhead()
