"""Canonical AudioCoder icon artwork shared by the GUI and Windows build."""
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
