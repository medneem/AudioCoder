"""Portable JSON settings stored next to the EXE, like FlacSplitter."""

import json
import math
from pathlib import Path
import sys

from .converter import FORMATS, BITRATES
from .fade import FADE_CURVES


DEFAULTS = {
    "last_source_dir": "",
    "output_dir": "",
    "target_format": "FLAC",
    "bitrate": "192k",
    "appearance": "Light",
    "fade_enabled": False,
    "fade_seconds": 1.0,
    "fade_in_curve": "log",
    "fade_out_curve": "log",
    "vbr_enabled": False,
    "vbr_quality": 2,
    "last_source_path": "",
    "clip_start": 0.0,
    "clip_end": 0.0,
    "waveform_zoom": 1.0,
    "waveform_start": 0.0,
}


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def validate(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("config.json должен содержать JSON-объект.")
    settings = {**DEFAULTS, **config}
    if any(not isinstance(settings[key], str) for key in ("last_source_dir", "output_dir", "target_format", "bitrate", "appearance", "last_source_path")):
        raise ValueError("Параметры config.json должны быть строками.")
    if settings["target_format"] not in FORMATS or settings["bitrate"] not in BITRATES:
        raise ValueError("Некорректный формат или битрейт в config.json.")
    if settings["appearance"] not in ("Light", "Dark", "System"):
        raise ValueError("Некорректная тема в config.json.")
    if type(settings["fade_enabled"]) is not bool:
        raise ValueError("fade_enabled должен быть логическим значением.")
    if type(settings["fade_seconds"]) not in (int, float) or not (0.1 <= settings["fade_seconds"] <= 20):
        raise ValueError("fade_seconds должен быть числом от 0.1 до 20.")
    if settings["fade_in_curve"] not in FADE_CURVES or settings["fade_out_curve"] not in FADE_CURVES:
        raise ValueError("Неизвестный алгоритм fade в config.json.")
    if type(settings["vbr_enabled"]) is not bool:
        raise ValueError("vbr_enabled должен быть true/false.")
    if type(settings["vbr_quality"]) is not int or not 0 <= settings["vbr_quality"] <= 9:
        raise ValueError("vbr_quality должен быть от 0 до 9.")
    for name in ("clip_start", "clip_end", "waveform_zoom", "waveform_start", "fade_seconds"):
        value = settings[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{name} должен быть конечным числом.")
    if settings["clip_start"] < 0 or settings["clip_end"] < 0:
        raise ValueError("Отрицательные границы фрагмента.")
    if not 1 <= settings["waveform_zoom"] <= 16:
        raise ValueError("waveform_zoom должен быть от 1 до 16.")
    if not 0 <= settings["waveform_start"] <= 1:
        raise ValueError("waveform_start должен быть от 0 до 1.")
    return {key: settings[key] for key in DEFAULTS}


def load_settings(directory: Path | None = None) -> dict:
    root = directory if directory is not None else application_directory()
    path = root / "config.json"
    if not path.exists():
        save_settings(DEFAULTS, root)
        return DEFAULTS.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return validate(data)
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"Ошибка config.json: {exc}") from exc


def save_settings(settings: dict, directory: Path | None = None) -> None:
    root = directory if directory is not None else application_directory()
    values = validate(settings)
    path = root / "config.json"
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
