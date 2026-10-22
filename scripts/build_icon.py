"""Generate PNG and multi-resolution Windows ICO from the GUI icon artwork."""
from pathlib import Path
import sys

# Also allow direct invocation with `python scripts/build_icon.py`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audiocoder.app_icon import create_icon_image


def main():
    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(exist_ok=True)
    image = create_icon_image()
    image.save(assets / "app.png")
    image.save(assets / "app.ico", sizes=[
        (16, 16), (24, 24), (32, 32), (48, 48),
        (64, 64), (128, 128), (256, 256)])
    print("Created app.png and app.ico")


if __name__ == "__main__":
    main()
