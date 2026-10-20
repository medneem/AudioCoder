"""FFprobe discovery and audio metadata extraction."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class AudioInfo:
    path: Path
    duration: float
    codec: str
    sample_rate: int
    channels: int


def find_binary(name: str) -> Path:
    """Prefer the portable tools beside the executable over PATH."""
    exe = name + (".exe" if sys.platform == "win32" else "")
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    local = base / exe
    if local.is_file():
        return local
    external = shutil.which(name)
    if external:
        return Path(external)
    raise FileNotFoundError(f"Не найден {exe}. Установите FFmpeg или положите {exe} рядом с программой.")


def probe_audio(path: Path, ffprobe: Path | None = None) -> AudioInfo:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Не найден аудиофайл: {path}")
    cmd = [
        str(ffprobe or find_binary("ffprobe")), "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "format=duration:stream=codec_name,sample_rate,channels,duration",
        "-of", "json", str(path),
    ]
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=30, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("FFprobe не ответил за 30 секунд.") from exc
    if process.returncode:
        raise ValueError("FFprobe: " + (process.stderr.strip() or "невозможно прочитать аудиофайл"))
    try:
        data = json.loads(process.stdout)
        streams = data.get("streams") or []
        if not streams:
            raise ValueError("В файле не найдена аудиодорожка.")
        stream = streams[0]
        duration_text = (data.get("format") or {}).get("duration") or stream.get("duration")
        duration = float(duration_text)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Неизвестная длительность аудиофайла.")
        sample_rate = int(stream.get("sample_rate") or 0)
        channels = int(stream.get("channels") or 0)
        return AudioInfo(path, duration, str(stream.get("codec_name") or "unknown"), sample_rate, channels)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Не удалось определить параметры аудиофайла: {exc}") from exc
