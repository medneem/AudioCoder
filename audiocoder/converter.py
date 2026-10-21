"""FFmpeg transcoding runner; GUI independent and non-destructive."""

from dataclasses import dataclass, field
import os
import math
from pathlib import Path
import subprocess
import tempfile
import threading
from typing import Callable

from .media import AudioInfo, find_binary
from .selection import ClipRange
from .fade import FADE_CURVES


FORMATS = ("FLAC", "MP3", "WAV", "Opus")
BITRATES = ("128k", "192k", "256k", "320k")


class ConversionError(RuntimeError):
    pass


class ConversionCancelled(ConversionError):
    pass


def output_path(source: Path, directory: Path, target_format: str) -> Path:
    if target_format not in FORMATS:
        raise ValueError("Неподдерживаемый формат.")
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise ValueError("Папка для сохранения не существует.")
    suffix = target_format.lower() if target_format != "Opus" else "opus"
    return directory / f"{source.stem}_converted.{suffix}"


@dataclass(frozen=True)
class ConversionJob:
    source: AudioInfo
    destination: Path
    target_format: str
    clip: ClipRange
    bitrate: str = "192k"
    fade_enabled: bool = False
    fade_seconds: float = 1.0
    fade_in_curve: str = "log"
    fade_out_curve: str = "log"
    vbr_enabled: bool = False
    vbr_quality: int = 2

    def __post_init__(self):
        if self.target_format not in FORMATS:
            raise ValueError("Неподдерживаемый формат.")
        if self.bitrate not in BITRATES:
            raise ValueError("Неподдерживаемый битрейт.")
        if type(self.fade_enabled) is not bool:
            raise ValueError("Некорректный переключатель затухания.")
        if type(self.fade_seconds) not in (int, float) or not math.isfinite(self.fade_seconds) or not 0.1 <= self.fade_seconds <= 20:
            raise ValueError("Длительность затухания должна быть от 0,1 до 20 секунд.")
        if self.fade_in_curve not in FADE_CURVES or self.fade_out_curve not in FADE_CURVES:
            raise ValueError("Неподдерживаемый алгоритм появления или затухания.")
        if type(self.vbr_enabled) is not bool:
            raise ValueError("VBR должен быть логическим значением.")
        if type(self.vbr_quality) is not int or not (0 <= self.vbr_quality <= 9):
            raise ValueError("Качество MP3 VBR должно быть в диапазоне 0–9.")
        if self.clip.duration != self.source.duration:
            raise ValueError("Диапазон не соответствует длительности файла.")
        if self.destination.suffix.lower() != "." + self.target_format.lower():
            raise ValueError("Расширение результата не соответствует формату.")
        if self.destination.resolve() == self.source.path.resolve():
            raise ValueError("Нельзя перезаписывать исходный файл.")


def ffmpeg_command(job: ConversionJob, destination: Path, ffmpeg: Path) -> list[str]:
    cmd = [
        str(ffmpeg), "-hide_banner", "-nostdin", "-nostats", "-loglevel", "error",
        "-progress", "pipe:1",
        "-ss", f"{job.clip.start:.6f}", "-i", str(job.source.path),
        "-t", f"{job.clip.length:.6f}",
        "-map", "0:a:0", "-vn", "-sn", "-dn", "-map_metadata", "0",
    ]
    codecs = {
        "FLAC": ["-c:a", "flac", "-compression_level", "12"],
        "MP3": (["-c:a", "libmp3lame", "-q:a", str(job.vbr_quality),
                 "-compression_level", "0", "-id3v2_version", "3"]
                if job.vbr_enabled else
                ["-c:a", "libmp3lame", "-b:a", job.bitrate,
                 "-compression_level", "0", "-id3v2_version", "3"]),
        "WAV": ["-c:a", "pcm_s24le"],
        "Opus": ["-c:a", "libopus", "-b:a", job.bitrate, "-vbr", "on" if job.vbr_enabled else "off", "-compression_level", "10"],
    }
    if job.fade_enabled:
        # Use logarithmic fades on the trimmed output timeline.
        # Short excerpts use symmetrical, non-overlapping fades.
        length = job.clip.length
        fade = min(job.fade_seconds, length / 2)
        start_out = max(0.0, length - fade)
        filters = (
            f"afade=t=in:st=0:d={fade:.6f}:curve={job.fade_in_curve},"
            f"afade=t=out:st={start_out:.6f}:d={fade:.6f}:curve={job.fade_out_curve}"
        )
        cmd.extend(["-af", filters])
    return cmd + codecs[job.target_format] + ["-n", str(destination)]


@dataclass
class ConversionRunner:
    """One operation per runner. Progress is reported in [0, 1]."""

    cancel_event: threading.Event = field(default_factory=threading.Event)
    _process: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def cancel(self):
        self.cancel_event.set()
        with self._lock:
            process = self._process
        if process is not None and process.poll() is None:
            process.kill()

    def run(self, job: ConversionJob, progress: Callable[[float], None] | None = None,
            ffmpeg: Path | None = None) -> Path:
        destination = job.destination.absolute()
        if destination.resolve() == job.source.path.resolve():
            raise ConversionError("Нельзя перезаписывать исходный аудиофайл.")
        if not destination.parent.is_dir():
            raise ConversionError("Папка для сохранения не существует.")
        if self.cancel_event.is_set():
            raise ConversionCancelled("Операция отменена.")

        # Keep the temporary output in the destination folder (same filesystem).
        fd, tmp_name = tempfile.mkstemp(prefix=".audiocoder-", suffix=destination.suffix, dir=destination.parent)
        os.close(fd)
        temporary = Path(tmp_name)
        temporary.unlink()  # FFmpeg -n refuses to write an existing file.
        try:
            cmd = ffmpeg_command(job, temporary, ffmpeg or find_binary("ffmpeg"))
            lines: list[str] = []
            with self._lock:
                if self.cancel_event.is_set():
                    raise ConversionCancelled("Операция отменена.")
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                    errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            assert self._process.stdout is not None
            for line in self._process.stdout:
                line = line.strip()
                if line.startswith(("out_time_us=", "out_time_ms=")):
                    try:
                        micros = int(line.split("=", 1)[1])
                        if progress:
                            progress(max(0.0, min(1.0, micros / 1_000_000 / job.clip.length)))
                    except ValueError:
                        pass
                elif line and not line.startswith(("progress=", "bitrate=", "speed=", "total_size=", "out_time=")):
                    lines.append(line)
                    lines = lines[-15:]
            result = self._process.wait()
            if self.cancel_event.is_set():
                raise ConversionCancelled("Операция отменена.")
            if result != 0:
                raise ConversionError("FFmpeg: " + ("\n".join(lines[-5:]) or f"код {result}"))
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise ConversionError("FFmpeg не создал выходной файл.")
            # Atomic replacement on the same filesystem. Failed/cancelled encoding
            # keeps an existing output intact; the source file is never replaced.
            os.replace(temporary, destination)
            if progress:
                progress(1.0)
            return destination
        finally:
            with self._lock:
                process = self._process
                self._process = None
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            temporary.unlink(missing_ok=True)
