"""Generate PNG and multi-resolution Windows ICO with Pillow (no Qt dependency)."""

from pathlib import Path
from PIL import Image, ImageDraw


def main():
    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(exist_ok=True)
    image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    painter = ImageDraw.Draw(image)
    painter.rounded_rectangle((18, 18, 494, 494), radius=112, fill="#19385C")
    painter.rounded_rectangle((40, 40, 472, 472), radius=94, fill="#234568")
    for x, top, bottom in ((93, 171, 339), (165, 125, 386), (235, 77, 435),
                           (305, 131, 380), (375, 184, 327)):
        painter.rounded_rectangle((x, top, x+44, bottom), radius=20, fill="#5BCEEB")
    image.save(assets / "app.png")
    image.save(assets / "app.ico", sizes=[
        (16,16), (24,24), (32,32), (48,48),
        (64,64), (128,128), (256,256)])
    print("Created app.png and app.ico")


if __name__ == "__main__":
    main()
