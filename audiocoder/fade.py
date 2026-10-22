"""Audio fade curves matching FFmpeg afade's gain expressions.

Based on libavfilter/af_afade.c (FFmpeg). The presentation previews and
filter parameters use the same stable curve IDs, not approximated log curves.
"""
import math

FADE_CURVES = {
    "log": "Логарифмический",
    "tri": "Линейный",
    "qsin": "Четверть синусоиды",
    "hsin": "Половина синусоиды",
    "exp": "Экспоненциальный",
    "qua": "Квадратичный",
    "cub": "Кубический",
    "ipar": "Обратная парабола",
}

# Keep real FFmpeg curve IDs separate from the UI-only "no effect" option.
# The help gallery covers only actual mathematical curves.
FADE_OPTIONS = {"none": "Нет", **FADE_CURVES}


def fade_filtergraph(duration: float, seconds: float, curve_in: str,
                     curve_out: str, *, mode: str = "selection") -> str | None:
    """Build the same FFmpeg afade chain for export and FFplay previews.

    Full selection: symmetrical, non-overlapping fades. Left/right marker
    snippets: only the corresponding edge is processed; the short preview
    uses its own duration, since it starts a fresh FFplay timeline.
    """
    if mode not in ("selection", "left", "right"):
        raise ValueError("Неизвестный режим предпрослушивания.")
    if (not math.isfinite(duration) or duration <= 0
            or not math.isfinite(seconds) or seconds <= 0):
        raise ValueError("Некорректная длительность появления или затухания.")
    if curve_in not in FADE_OPTIONS or curve_out not in FADE_OPTIONS:
        raise ValueError("Неподдерживаемый алгоритм появления или затухания.")
    effective = min(seconds, duration / 2 if mode == "selection" else duration)
    filters = []
    if mode != "right" and curve_in != "none":
        filters.append(f"afade=t=in:st=0:d={effective:.6f}:curve={curve_in}")
    if mode != "left" and curve_out != "none":
        start = max(0.0, duration - effective)
        filters.append(
            f"afade=t=out:st={start:.6f}:d={effective:.6f}:curve={curve_out}")
    return ",".join(filters) if filters else None


def fade_gain(curve: str, progress: float) -> float:
    """Gain from silence (0) to unity (1); right fade reverses progress."""
    if curve not in FADE_CURVES:
        raise ValueError("Неподдерживаемый алгоритм появления или затухания.")
    if not math.isfinite(progress):
        raise ValueError("Некорректная позиция fade.")
    x = max(0.0, min(1.0, progress))
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    if curve == "log":
        return max(0.0, min(1.0, 1.0 + 0.2 * math.log10(x)))
    if curve == "tri":
        return x
    if curve == "qsin":
        return math.sin(x * math.pi / 2)
    if curve == "hsin":
        return (1 - math.cos(x * math.pi)) / 2
    if curve == "exp":
        return math.exp(-11.512925464970227 * (1 - x))
    if curve == "qua":
        return x * x
    if curve == "cub":
        return x * x * x
    if curve == "ipar":
        return 1 - (1 - x) ** 2
    raise AssertionError("Every supported FFmpeg curve has a preview implementation")


def fade_envelope(curve_in: str, curve_out: str, time_fraction: float,
                  fade_fraction: float = 0.2) -> float:
    """An illustrative 1-second graph: fades over 0..0.2 and 0.8..1."""
    if not 0 < fade_fraction <= 0.5:
        raise ValueError("Invalid fade fraction")
    t = max(0.0, min(1.0, time_fraction))
    return (fade_gain(curve_in, t / fade_fraction)
            if t < fade_fraction else
            fade_gain(curve_out, (1 - t) / fade_fraction)
            if t > 1 - fade_fraction else 1.0)
