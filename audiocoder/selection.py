"""Validated media timeline ranges independent of the GUI."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ClipRange:
    start: float
    end: float
    duration: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.start, self.end, self.duration)):
            raise ValueError("Временные границы должны быть конечными числами.")
        if self.duration <= 0 or self.start < 0 or self.end > self.duration + 0.001:
            raise ValueError("Временные границы выходят за пределы файла.")
        if self.end - self.start < 0.05:
            raise ValueError("Выберите фрагмент длительностью хотя бы 0,05 секунды.")

    @property
    def length(self) -> float:
        return self.end - self.start


def clock(seconds: float) -> str:
    """HH:MM:SS.mmm, including for files longer than 24 hours."""
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Invalid timestamp")
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"
