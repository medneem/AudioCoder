"""Generate a compact visual audio waveform using FFmpeg's showwavespic filter.

Only one monochrome video frame (width * height bytes) is transferred to Python,
not a decoded copy of the entire audio file.
"""
from pathlib import Path
import math
import subprocess

from .media import find_binary


def waveform_command(path: Path, ffmpeg: Path, width: int, height: int,
                     *, start: float = 0.0, duration: float | None = None) -> list[str]:
    if not (32 <= width <= 4096 and 32 <= height <= 512):
        raise ValueError("Неподдерживаемые размеры waveform.")
    if not math.isfinite(start) or start < 0:
        raise ValueError("Некорректная начальная позиция waveform.")
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("Некорректная длительность waveform.")
    filtergraph = (f"[0:a:0]aformat=channel_layouts=mono,"
                   f"showwavespic=s={width}x{height}:colors=white:scale=lin:draw=full[v]")
    command = [str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error"]
    if start:
        command += ["-ss", f"{start:.6f}"]
    command += ["-i", str(path)]
    if duration is not None:
        command += ["-t", f"{duration:.6f}"]
    return command + [
        "-filter_complex", filtergraph,
        "-map", "[v]", "-frames:v", "1", "-f", "rawvideo",
        "-pix_fmt", "gray", "pipe:1",
    ]


def peak_columns(raw: bytes, width: int, height: int) -> tuple[float, ...]:
    """Extract normalised amplitude per column from FFmpeg's raw gray waveform."""
    if len(raw) != width * height:
        raise ValueError("FFmpeg вернул неполную звуковую волну.")
    middle = height / 2
    result = []
    for x in range(width):
        extent = 0.0
        for y in range(height):
            if raw[y * width + x] > 127:
                extent = max(extent, abs((y + 0.5) - middle))
        result.append(max(0.0, min(1.0, extent / middle)))
    return tuple(result)


def extract_waveform(path: Path, ffmpeg: Path | None = None,
                     *, width: int = 4096, height: int = 120,
                     timeout: int = 180, start: float = 0.0,
                     duration: float | None = None) -> tuple[float, ...]:
    """Decode the first audio stream into one waveform preview in a worker thread."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Не найден аудиофайл: {path}")
    cmd = waveform_command(path, ffmpeg or find_binary("ffmpeg"), width, height,
                           start=start, duration=duration)
    try:
        completed = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Построение звуковой волны превысило лимит времени.") from exc
    if completed.returncode:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError("Ошибка построения waveform: " + (message or str(completed.returncode)))
    return peak_columns(completed.stdout, width, height)
