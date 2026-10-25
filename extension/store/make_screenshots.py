"""Turn screenshots into Chrome Web Store screenshots: 1280x800 JPEGs with no transparency.

Each image is cropped around its centre to the store's 16:10 shape, then resized. Crop your
screenshots close to the video player first if you want the signer to be large.

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
        # Crop to 16:10 around the centre: as wide as possible, or as tall as possible.
        if image.width / image.height > WIDTH / HEIGHT:
            w = round(image.height * WIDTH / HEIGHT)
            image = image.crop(((image.width - w) // 2, 0, (image.width + w) // 2, image.height))
        else:
            h = round(image.width * HEIGHT / WIDTH)
            image = image.crop((0, (image.height - h) // 2, image.width, (image.height + h) // 2))
        out = out_dir / f"screenshot-{n}.jpg"
        image.resize((WIDTH, HEIGHT), Image.LANCZOS).save(out, quality=92)
        print(f"{path} -> {out}")


if __name__ == "__main__":
    main()
