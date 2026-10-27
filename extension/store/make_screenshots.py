"""Turn screenshots into Chrome Web Store screenshots: 1280x800 JPEGs with no transparency.

Each whole image is scaled to fit inside 1280x800, and any space left over is filled with dark
grey, so nothing (like the signer box at the edge of the player) is cut off. Screenshots close to
16:10 fill the frame best.

Usage (from the repository root, with the project's virtualenv, which has Pillow):
    python extension/store/make_screenshots.py ~/Desktop/shot1.png ~/Desktop/shot2.png ...

Writes extension/store/screenshot-1.jpg, screenshot-2.jpg, ...
"""

import sys
from pathlib import Path

from PIL import Image

WIDTH, HEIGHT = 1280, 800


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out_dir = Path(__file__).resolve().parent
    for n, path in enumerate(sys.argv[1:6], start=1):
        image = Image.open(path).convert("RGB")
        # Fit the whole image inside the frame, centred on a dark background.
        scale = min(WIDTH / image.width, HEIGHT / image.height)
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
        frame = Image.new("RGB", (WIDTH, HEIGHT), (24, 24, 24))
        frame.paste(image, ((WIDTH - image.width) // 2, (HEIGHT - image.height) // 2))
        out = out_dir / f"screenshot-{n}.jpg"
        frame.save(out, quality=92)
        print(f"{path} -> {out}")


if __name__ == "__main__":
    main()
