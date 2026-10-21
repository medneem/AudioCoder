"""FFplay preview transport. Popen is launched off the Tkinter thread."""
from dataclasses import dataclass, field
import math
from pathlib import Path
import subprocess
import threading
import time
from typing import Callable

from .media import find_binary


@dataclass(frozen=True)
class PlaybackWindow:
    start: float
    end: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.start, self.end)):
            raise ValueError("Некорректные границы воспроизведения.")
        if self.start < 0 or self.end - self.start < 0.05:
            raise ValueError("Слишком короткий фрагмент для прослушивания.")

    @property
    def duration(self) -> float:
        return self.end - self.start


def listening_window(mode: str, left: float, right: float) -> PlaybackWindow:
    if mode not in {"selection", "left", "right"}:
        raise ValueError("Неизвестный режим воспроизведения.")
    if not all(math.isfinite(v) for v in (left, right)) or left < 0 or right <= left:
        raise ValueError("Некорректный диапазон.")
    if mode == "right":
        return PlaybackWindow(max(left, right - 1.0), right)
    if mode == "left":
        return PlaybackWindow(left, min(left + 5.0, right))
    return PlaybackWindow(left, right)


def ffplay_command(source: Path, window: PlaybackWindow, binary: Path) -> list[str]:
    return [
        str(binary), "-hide_banner", "-loglevel", "error", "-nostats",
        "-nodisp", "-autoexit", "-vn", "-sn",
        "-ss", f"{window.start:.6f}", "-t", f"{window.duration:.6f}",
        str(source),
    ]


@dataclass
class AudioPlayer:
    """Serialised process launches; only the latest request can start playback."""
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _generation: int = field(default=0, init=False)
    _process: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _window: PlaybackWindow | None = field(default=None, init=False)
    _started_at: float | None = field(default=None, init=False, repr=False)
    _pending: bool = field(default=False, init=False)

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def stop(self) -> None:
        with self._lock:
            self._generation += 1
            process = self._process
            self._process = None
            self._window = None
            self._pending = False
            self._started_at = None
            if process is not None and process.poll() is None:
                process.kill()

    def play(self, source: Path, window: PlaybackWindow,
             on_error: Callable[[int, str], None] | None = None) -> int:
        with self._lock:
            self._generation += 1
            generation = self._generation
            previous = self._process
            if previous is not None and previous.poll() is None:
                previous.kill()
            self._process = None
            self._window = window
            self._pending = True
            self._started_at = None
        threading.Thread(
            target=self._launch, args=(generation, Path(source), window, on_error),
            daemon=True,
        ).start()
        return generation

    def _launch(self, generation, source, window, on_error):
        try:
            binary = find_binary("ffplay")
            command = ffplay_command(source, window, binary)
            with self._lock:
                if generation != self._generation:
                    return
                self._process = subprocess.Popen(
                    command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self._started_at = time.monotonic()
                self._pending = False
        except OSError as exc:
            with self._lock:
                valid = generation == self._generation
                if valid:
                    self._window = None
                    self._process = None
                    self._pending = False
                    self._started_at = None
            if valid and on_error:
                on_error(generation, str(exc))

    def position(self) -> float | None:
        """Approximate playhead position while loading/playing, otherwise None."""
        with self._lock:
            if self._window is None:
                return None
            if self._pending:
                return self._window.start
            if self._process is None or self._process.poll() is not None:
                self._window = None
                self._process = None
                self._started_at = None
                return None
            assert self._started_at is not None
            elapsed = max(0.0, time.monotonic() - self._started_at)
            return min(self._window.end, self._window.start + elapsed)
