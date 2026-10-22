"""Pure navigation math shared by waveform drawing and unit tests."""
from dataclasses import dataclass

MAX_ZOOM = 16.0


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass
class WaveformViewport:
    """Normalised visible interval in the entire audio recording."""
    start: float = 0.0
    span: float = 1.0

    @property
    def end(self) -> float:
        return self.start + self.span

    @property
    def zoom_level(self) -> float:
        return 1.0 / self.span

    def reset(self) -> None:
        self.start = 0.0
        self.span = 1.0

    def zoom(self, factor: float, anchor: float = 0.5) -> None:
        if factor <= 0:
            raise ValueError("Zoom factor must be positive.")
        anchor = clamp(anchor, 0.0, 1.0)
        focal = self.start + self.span * anchor
        self.span = clamp(self.span / factor, 1.0 / MAX_ZOOM, 1.0)
        self.start = clamp(focal - self.span * anchor, 0.0, 1.0 - self.span)

    def fit_range(self, left: float, right: float) -> None:
        """Show a complete normalized selection, with padding where possible."""
        left = clamp(left, 0.0, 1.0)
        right = clamp(right, left, 1.0)
        span = clamp((right - left) * 1.12, 1.0 / MAX_ZOOM, 1.0)
        self.span = span
        self.start = clamp((left + right - span) / 2.0, 0.0, 1.0 - span)

    def pan(self, dx_pixels: float, width: int) -> None:
        if width <= 0:
            return
        self.start = clamp(
            self.start - (dx_pixels / width) * self.span,
            0.0, 1.0 - self.span,
        )

    def position_at(self, x_pixels: float, width: int) -> float:
        if width <= 0:
            return self.start
        return clamp(self.start + clamp(x_pixels / width, 0.0, 1.0) * self.span,
                     0.0, 1.0)

    def x_at(self, absolute_position: float, width: int) -> float:
        return (absolute_position - self.start) * width / self.span
