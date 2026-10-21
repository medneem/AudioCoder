"""High-DPI anti-aliased fade diagrams inspired by the user's reference charts.

These are *shape previews* on a 1-second illustrative timeline, with fades
over 0..0.2 and 0.8..1.0. Actual export durations are specified separately.
"""
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk

from .fade import FADE_CURVES, fade_gain
from .palette import (FADE_CHART_BACKGROUND, FADE_CHART_TEXT, FADE_CHART_GRID,
                      FADE_CHART_AXIS, FADE_CHART_LINE, theme_color)


def _font(size: int):
    for name in ("segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_fade_diagrams(curve_in: str, curve_out: str,
                       width: int = 740, height: int = 170,
                       dark: bool = False) -> Image.Image:
    """Draw two independent envelopes with readable axes and fine grids."""
    if curve_in not in FADE_CURVES or curve_out not in FADE_CURVES:
        raise ValueError("Unknown fade curve")
    width, height = max(width, 320), max(height, 100)
    # Supersampling ensures smooth bezier-like plots even on narrow screens.
    scale = 3
    W, H = width * scale, height * scale
    bg = theme_color(FADE_CHART_BACKGROUND, dark=dark)
    text = theme_color(FADE_CHART_TEXT, dark=dark)
    grid = theme_color(FADE_CHART_GRID, dark=dark)
    axis = theme_color(FADE_CHART_AXIS, dark=dark)
    line = theme_color(FADE_CHART_LINE, dark=dark)
    image = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(image)
    font = _font(11 * scale)
    titlefont = _font(13 * scale)
    gap = 14 * scale
    outer = 8 * scale
    half = (W - 2 * outer - gap) // 2

    for column, (code, direction) in enumerate(((curve_in, "in"), (curve_out, "out"))):
        base = outer + column * (half + gap)
        # Reserve space for labels and ticks.
        left = base + 44 * scale
        top = 32 * scale
        right = base + half - 14 * scale
        bottom = H - 29 * scale
        d.text((base + 3 * scale, 8 * scale),
               ("1. Появление" if direction == "in" else "2. Затухание")
               + " · " + FADE_CURVES[code], font=titlefont, fill=text)
        for fraction in (0.0, 0.5, 1.0):
            y = int(bottom - fraction * (bottom - top))
            d.line((left, y, right, y), fill=grid, width=scale)
            d.text((base + 3 * scale, y - 6 * scale),
                   f"{round(fraction * 100)}%", font=font, fill=axis)
        for fraction in (0.0, 0.2, 0.5, 0.8, 1.0):
            x = int(left + fraction * (right - left))
            d.line((x, top, x, bottom), fill=grid, width=max(1, scale // 2))
        d.line((left, top, left, bottom, right, bottom), fill=axis, width=scale)
        for fraction, caption in ((0.0, "0"), (0.2, "0.2"), (0.5, "0.5"), (0.8, "0.8"), (1.0, "1 c")):
            x = int(left + fraction * (right - left))
            d.text((x - 8 * scale, bottom + 5 * scale), caption, font=font, fill=axis)
        steps = max(300, (right - left) // 2)
        points = []
        for k in range(steps + 1):
            t = k / steps
            if direction == "in":
                gain = fade_gain(code, t / .2) if t < .2 else 1.0
            else:
                gain = 1.0 if t < .8 else fade_gain(code, (1.0 - t) / .2)
            points.append((int(left + t * (right - left)),
                           int(bottom - gain * (bottom - top))))
        d.line(points, fill=line, width=3 * scale, joint="curve")
    return image.resize((width, height), Image.Resampling.LANCZOS)


class FadePreview(tk.Canvas):
    def __init__(self, master, *, width=740, height=170, **kwargs):
        super().__init__(master, height=height, borderwidth=0,
                         highlightthickness=0, **kwargs)
        self._curves = ("log", "log")
        self._image = None
        self._item = self.create_image(0, 0, anchor="nw")
        self.bind("<Configure>", lambda event: self.redraw())
        self.redraw()

    def set_curves(self, fade_in: str, fade_out: str):
        if (fade_in, fade_out) != self._curves:
            self._curves = (fade_in, fade_out)
            self.redraw()

    def redraw(self):
        width, height = max(self.winfo_width(), 320), max(self.winfo_height(), 100)
        dark = ctk.get_appearance_mode() == "Dark"
        image = draw_fade_diagrams(*self._curves, width=width, height=height, dark=dark)
        self._image = ImageTk.PhotoImage(image, master=self)
        self.itemconfigure(self._item, image=self._image)
        self.configure(bg=theme_color(FADE_CHART_BACKGROUND, dark=dark))
