"""Run at most one expensive waveform decoder and keep only the latest view.

The Tk thread submits work; callbacks are invoked by the background thread
and must only enqueue messages, never touch Tk widgets.
"""
from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Callable, Generic, TypeVar

Request = TypeVar("Request")
Result = TypeVar("Result")


@dataclass(frozen=True)
class WaveformDetailRequest:
    path: Path
    audio_duration: float
    start: float
    end: float
    width: int
    sequence: int
    generation: int


class LatestOnlyWorker(Generic[Request, Result]):
    """Serialize slow work, replacing queued requests during rapid edits."""

    def __init__(
        self,
        work: Callable[[Request], Result],
        on_result: Callable[[Request, Result], None],
        on_error: Callable[[Request, Exception], None] | None = None,
    ):
        self._work = work
        self._on_result = on_result
        self._on_error = on_error
        self._condition = threading.Condition()
        self._pending: tuple[Request, int] | None = None
        self._revision = 0
        self._active = False
        self._closed = False

    def submit(self, request: Request) -> None:
        with self._condition:
            if self._closed:
                return
            self._revision += 1
            self._pending = request, self._revision
            if self._active:
                return
            self._active = True
            threading.Thread(target=self._drain, daemon=True).start()

    def clear(self) -> None:
        """Discard queued requests and invalidate any in-flight result."""
        with self._condition:
            self._revision += 1
            self._pending = None

    def close(self) -> None:
        """Never publish results after closing; in-flight decode can finish."""
        with self._condition:
            self._closed = True
            self._revision += 1
            self._pending = None

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """For deterministic tests; the GUI must not call this method."""
        with self._condition:
            return self._condition.wait_for(lambda: not self._active, timeout=timeout)

    def _drain(self) -> None:
        while True:
            with self._condition:
                if self._closed or self._pending is None:
                    self._active = False
                    self._condition.notify_all()
                    return
                request, revision = self._pending
                self._pending = None
            try:
                result = self._work(request)
            except Exception as exc:
                with self._condition:
                    current = not self._closed and self._revision == revision
                if current and self._on_error is not None:
                    self._on_error(request, exc)
            else:
                with self._condition:
                    current = not self._closed and self._revision == revision
                if current:
                    self._on_result(request, result)
