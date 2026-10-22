"""Smooth, zoomable waveform. Ctrl-free wheel zoom and right-drag panning.

Draw waveform pixels to one cached PhotoImage, not hundreds of Canvas items
on each handle movement. The playhead remains a lightweight Canvas line.
"""
import tkinter as tk
from functools import lru_cache
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from .waveform_navigation import WaveformViewport, clamp
from .fade import fade_gain
from .palette import (FADE_GUIDE, PLAYHEAD, WAVE_ACTIVE, WAVE_BACKGROUND,
                      WAVE_INACTIVE, WAVE_SELECTION, theme_color)



@lru_cache(maxsize=12)
def _rounded_mask(width: int, height: int, radius: int) -> Image.Image:
    """Cache an antialiased clipping mask while dragging markers."""
    radius = max(0, min(radius, width // 2, height // 2))
    scale = 3
    mask = Image.new("L", (width * scale, height * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, width * scale - 1, height * scale - 1),
        radius=radius * scale, fill=255)
    return mask.resize((width, height), Image.Resampling.LANCZOS)


def tk_background_rgb(widget: tk.Misc, color: str) -> tuple[int, int, int]:
    """Convert Tk's platform color names (e.g. gray86) for Pillow.

    CustomTkinter defaults on Windows can be named Tk colors rather than HEX.
    Tk accepts 'gray86', but PIL.Image.new raises ValueError for that name.
    Always resolve through the running Tk interpreter before compositing.
    """
    return tuple(round(channel / 257) for channel in widget.winfo_rgb(color))


def round_waveform_image(image: Image.Image, surrounding_color: str | tuple[int, int, int],
                         radius: int = 14) -> Image.Image:
    """Make real rounded bitmap corners, matching the surrounding CTk card."""
    outer = Image.new("RGB", image.size, surrounding_color)
    outer.paste(image, (0, 0), _rounded_mask(*image.size, radius))
    return outer


def visible_waveform_columns(
    overview: tuple[float, ...], viewport: WaveformViewport, width: int,
    *, detail: tuple[float, float, tuple[float, ...]] | None = None,
) -> tuple[float, ...]:
    """Project amplitudes onto the *entire* currently visible canvas width.

    Exact-viewport detail overrides the compressed whole-track overview.
    Panning/zooming away automatically falls back to overview until the next
    high-resolution worker finishes; no audio decoding occurs in Tk's thread.
    """
    if width <= 0 or not overview:
        return ()
    start, span, peaks = 0.0, 1.0, overview
    if detail is not None:
        begin, end, samples = detail
        if (samples and abs(begin - viewport.start) < 1e-8
                and abs(end - viewport.end) < 1e-8):
            start, span, peaks = begin, end - begin, samples
    if span <= 0:
        return (0.0,) * width
    size = len(peaks)
    values = []
    for x in range(width):
        absolute_start = viewport.start + viewport.span * x / width
        absolute_end = viewport.start + viewport.span * (x + 1) / width
        p1 = max(0, min(size - 1, int((absolute_start - start) / span * size)))
        p2 = max(p1 + 1, min(size, int((absolute_end - start) / span * size)))
        values.append(max(peaks[p1:p2]))
    return tuple(values)


def level_waveform_columns(columns: tuple[float, ...]) -> tuple[float, ...]:
    """Fit quiet visible audio into the canvas height without touching sound.

    Waveform peaks are linear PCM amplitudes, often around 0.1–0.2 even in
    properly mastered audio. Viewing at ×16 should reveal their *shape* rather
    than a tiny line in the middle of an otherwise empty canvas.
    """
    if not columns:
        return ()
    ordered = sorted(columns)
    reference = ordered[min(len(ordered) - 1, int((len(ordered) - 1) * .99))]
    if reference < .015:
        return columns  # Do not magnify near-silent background noise.
    gain = min(12.0, max(1.0, .90 / reference))
    return tuple(min(1.0, max(0.0, peak * gain)) for peak in columns)


class WaveformView(tk.Canvas):
    def __init__(self, master, *, height=118, on_edit=None, on_view_change=None, **kwargs):
        super().__init__(master, height=height, borderwidth=0,
                         highlightthickness=0, relief="flat", **kwargs)
        self.peaks: tuple[float, ...] = ()
        self.detail_peaks: tuple[float, float, tuple[float, ...]] | None = None
        self.selection: tuple[float, float] = (0.0, 1.0)
        self.playhead: float | None = None
        self.corner_radius = 14
        self.fade_enabled = False
        self.fade_fraction = 0.0
        self.fade_in_curve = "log"
        self.fade_out_curve = "log"
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
        self.detail_peaks = None
        self.redraw()

    def set_detail_peaks(self, start: float, end: float, peaks):
        """Retain a zoomed segment without changing marker coordinates."""
        self.detail_peaks = (
            start, end, tuple(clamp(float(p), 0.0, 1.0) for p in peaks))
        self.redraw()

    def clear_detail(self):
        self.detail_peaks = None
        self.redraw()

    def set_selection(self, start: float, end: float, duration: float):
        new = ((clamp(start / duration, 0.0, 1.0),
                clamp(end / duration, 0.0, 1.0)) if duration > 0 else (0.0, 1.0))
        if new != self.selection:
            self.selection = new
            self.redraw()

    def set_fade(self, enabled: bool, seconds: float, duration: float,
                 curve_in: str = "log", curve_out: str = "log"):
        self.fade_enabled = bool(enabled)
        self.fade_fraction = max(0.0, seconds / duration) if duration > 0 else 0.0
        self.fade_in_curve = curve_in
        self.fade_out_curve = curve_out
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
        # An overlay line should not cut through the rounded image corners.
        edge = self.corner_radius if x < self.corner_radius or x > w - self.corner_radius else 0
        self.coords(self._playhead_item, x, edge, x, h - edge)
        self.itemconfigure(self._playhead_item, state="normal",
                           fill=theme_color(PLAYHEAD, dark=dark))
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
        background = theme_color(WAVE_BACKGROUND, dark=dark)
        selected_bg = theme_color(WAVE_SELECTION, dark=dark)
        inactive = theme_color(WAVE_INACTIVE, dark=dark)
        active = theme_color(WAVE_ACTIVE, dark=dark)
        # The raw Tk canvas stays rectangular. Blend the four outer corners
        # into the CTkFrame behind it, while retaining normal TkDND bindings.
        surrounding = self.master._apply_appearance_mode(
            self.master.cget("fg_color"))
        self.configure(background=surrounding)
        image = Image.new("RGB", (w, h), background)
        draw = ImageDraw.Draw(image)
        x1 = int(self.viewport.x_at(self.selection[0], w))
        x2 = int(self.viewport.x_at(self.selection[1], w))
        draw.rectangle((max(x1, 0), 0, min(x2, w), h), fill=selected_bg) if x2 >= 0 and x1 <= w else None
        middle = h / 2
        columns = level_waveform_columns(visible_waveform_columns(
            self.peaks, self.viewport, w, detail=self.detail_peaks))
        if not columns:
            draw.text((12, middle - 7), "Waveform", fill=inactive)
        else:
            for x, peak in enumerate(columns):
                half = max(0.5, peak * (middle - 5))
                draw.line((x, int(middle - half), x, int(middle + half)),
                          fill=active if x1 <= x <= x2 else inactive)
        for x in (x1, x2):
            if 0 <= x < w:
                draw.line((x, 0, x, h), fill=active, width=1)
        if self.fade_enabled and self.fade_fraction > 0:
            # Subtle warm waveform guides distinguish fades from the audio.
            # They are visual only; the same afade curve is applied at export.
            length = max(0.0, self.selection[1] - self.selection[0])
            fade_frac = min(self.fade_fraction, length / 2)
            if fade_frac > 0:
                top, bottom = 9, h - 9
                fade_colour = theme_color(FADE_GUIDE, dark=dark)
                for begin, end, direction, curve in (
                    (self.selection[0], self.selection[0] + fade_frac,
                     "in", self.fade_in_curve),
                    (self.selection[1] - fade_frac, self.selection[1],
                     "out", self.fade_out_curve),
                ):
                    if curve == "none":
                        continue
                    points = []
                    for x in range(w):
                        position = self.viewport.position_at(x, w)
                        if not begin <= position <= end:
                            continue
                        progress = (position - begin) / fade_frac
                        if direction == "out":
                            progress = 1 - progress
                        gain = fade_gain(curve, progress)
                        points.append((x, int(bottom - gain * (bottom - top))))
                    if len(points) >= 2:
                        draw.line(points, fill=fade_colour, width=2)
        image = round_waveform_image(
            image, tk_background_rgb(self, surrounding), self.corner_radius)
        self._image = ImageTk.PhotoImage(image, master=self)
        self.itemconfigure(self._image_item, image=self._image)
        self._draw_playhead()
