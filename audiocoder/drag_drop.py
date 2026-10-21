"""Validate Explorer file-drop payloads before opening any audio."""
from pathlib import Path

AUDIO_EXTENSIONS = frozenset({
    ".flac", ".mp3", ".wav", ".ape", ".m4a", ".aac",
    ".ogg", ".opus", ".wma",
})


def dropped_audio_path(data: str, splitlist) -> Path:
    """Decode TkDND Tcl-list paths, including braces, spaces and Unicode.

    Only one existing supported file is accepted, never multiple files,
    directories, URLs, or arbitrary payload text.
    """
    paths = splitlist(data)
    if len(paths) != 1:
        raise ValueError("Перетащите один аудиофайл.")
    path = Path(paths[0])
    if path.suffix.lower() not in AUDIO_EXTENSIONS:
        raise ValueError("Неподдерживаемый формат аудиофайла.")
    if not path.is_file():
        raise ValueError("Выбранный аудиофайл не найден.")
    return path
