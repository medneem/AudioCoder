"""Central palette shared by CustomTkinter widgets and Pillow canvases.

Each pair is (Light, Dark). Keep subdued slate-blue accents and neutral cards
consistent across conversion controls, waveform and help diagrams.
"""
from pathlib import Path

WINDOW = ("#F3F5F6", "#1E262C")
EDITOR = ("#E8ECEF", "#252F35")
CARD = ("#FBFCFD", "#2B363D")
CARD_BORDER = ("#D5DFE4", "#42515A")
FADE_CARD = ("#EEF2F0", "#29383B")
FADE_BORDER = ("#D3DEDA", "#455B59")
FADE_DIVIDER = ("#D9E3DF", "#435854")
ZOOM_ROW = ("#F2F5F6", "#2A373E")
ACCENT = ("#506C78", "#56737F")
ACCENT_HOVER = ("#3D5965", "#455F6A")
WAVE_BACKGROUND = ("#F1F4F5", "#26343B")
WAVE_SELECTION = ("#DEE9ED", "#34434B")
WAVE_INACTIVE = ("#9AABB3", "#8198A1")
WAVE_ACTIVE = ("#537483", "#A5C6CE")
PLAYHEAD = ("#A16857", "#D0A085")
FADE_GUIDE = ("#AE826B", "#C69B82")
FADE_CHART_BACKGROUND = ("#FBFCFD", "#27353A")
FADE_CHART_LINE = ("#577480", "#A9C4CC")
FADE_CHART_TEXT = ("#33454E", "#E6EDF0")
FADE_CHART_GRID = ("#DDE4E7", "#45535A")
FADE_CHART_AXIS = ("#697C85", "#A8B6BE")
DND_BORDER = ("#5E7F8A", "#8DA8B2")
CANCEL_BG = ("#68767D", "#46555F")
CANCEL_HOVER = ("#526168", "#52636E")


def theme_path() -> Path:
    """Use the asset beside this module in both source and PyInstaller builds."""
    return Path(__file__).resolve().parent / "themes" / "quiet_slate.json"


def theme_color(colors: tuple[str, str], *, dark: bool) -> str:
    return colors[int(dark)]


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio for HEX colours, used to enforce readable controls."""
    def luminance(hex_color: str) -> float:
        value = hex_color.lstrip("#")
        if len(value) != 6:
            raise ValueError("Expected a six-digit HEX colour")
        channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
                  for c in channels]
        return sum(c * weight for c, weight in
                   zip(linear, (.2126, .7152, .0722)))
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + .05) / (low + .05)
