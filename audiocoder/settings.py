"""Portable JSON settings stored next to the EXE, like FlacSplitter."""

import json
from pathlib import Path
import sys

from .converter import FORMATS, BITRATES


DEFAULTS = {
    "last_source_dir": "",
    "output_dir": "",
    "target_format": "FLAC",
    "bitrate": "192k",
}


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def validate(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("config.json должен содержать JSON-объект.")
    settings = {**DEFAULTS, **config}
    if any(not isinstance(settings[key], str) for key in DEFAULTS):
        raise ValueError("Параметры config.json должны быть строками.")
    if settings["target_format"] not in FORMATS or settings["bitrate"] not in BITRATES:
        raise ValueError("Некорректный формат или битрейт в config.json.")
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
