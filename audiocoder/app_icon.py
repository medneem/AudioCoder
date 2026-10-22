"""Canonical AudioCoder icon artwork shared by the GUI and Windows build."""
from pathlib import Path
import sys

from PIL import Image, ImageDraw


def create_icon_image(size: int = 512) -> Image.Image:
    """Render the waveform logo at the requested pixel size."""
    if not isinstance(size, int) or isinstance(size, bool) or size < 16:
        raise ValueError("Icon size must be an integer of at least 16 px")
    image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    painter = ImageDraw.Draw(image)
    painter.rounded_rectangle((18, 18, 494, 494), radius=112, fill="#19385C")
    painter.rounded_rectangle((40, 40, 472, 472), radius=94, fill="#234568")
    for x, top, bottom in ((93, 171, 339), (165, 125, 386), (235, 77, 435),
                           (305, 131, 380), (375, 184, 327)):
        painter.rounded_rectangle((x, top, x + 44, bottom),
                                  radius=20, fill="#5BCEEB")
    if size != 512:
        image = image.resize((size, size), Image.Resampling.LANCZOS)
    return image


# Keep in sync with scripts/build_icon.py and the multi-resolution EXE icon.
ICO_SIZES = ((16, 16), (24, 24), (32, 32), (48, 48),
             (64, 64), (128, 128), (256, 256))


def icon_file_path(*, application_root: Path | None = None) -> Path:
    """Resolve a real .ico file for Tk/Windows wm_iconbitmap.

    PyInstaller onefile extracts the bundled icon to sys._MEIPASS. Development
    checkouts generate the same ICO on demand when assets/app.ico is absent.
    """
    if getattr(sys, "frozen", False):
        path = Path(sys._MEIPASS) / "assets" / "app.ico"
        if not path.is_file():
            raise FileNotFoundError(f"Не найдена иконка приложения: {path}")
        return path
    root = Path(application_root) if application_root is not None else Path(__file__).resolve().parent.parent
    path = root / "assets" / "app.ico"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        create_icon_image().save(path, format="ICO", sizes=ICO_SIZES)
    return path
