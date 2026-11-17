"""Build resources/ico.ico from resources/icon.png.

Every frame (16…256 px) is a downscale of the same source picture, so the
taskbar, Explorer «Таблица» view and window title show the real icon, not a
simplified glyph. Small frames get a light unsharp mask to stay crisp.

    py tools/make_ico.py
"""
import os
import sys

from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "resources", "icon.png")
DST = os.path.join(ROOT, "resources", "ico.ico")
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def build(src: str = SRC, dst: str = DST) -> None:
    base = Image.open(src).convert("RGBA")
    frames = []
    for size in SIZES:
        frame = base.resize((size, size), Image.Resampling.LANCZOS)
        if size <= 48:
            frame = frame.filter(ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=1))
        frames.append(frame)
    # Pillow writes one frame per entry of `sizes`, taking the matching image
    # from append_images when its size fits exactly.
    frames[-1].save(dst, format="ICO", sizes=[(s, s) for s in SIZES],
                    append_images=frames[:-1])


if __name__ == "__main__":
    build(*sys.argv[1:3])
