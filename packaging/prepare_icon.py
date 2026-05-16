"""Convert assets/logomark.svg → assets/icon.ico (multi-resolution).

Run once on the dev box; commit assets/icon.ico.
Re-run only when logomark.svg changes.

Usage: .venv/bin/python packaging/prepare_icon.py
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SVG = REPO / "assets" / "logomark.svg"
ICO = REPO / "assets" / "icon.ico"
SIZES = [16, 32, 48, 64, 128, 256]


def main() -> None:
    try:
        import cairosvg
    except ImportError:
        raise SystemExit(
            "cairosvg not installed. Run: pip install cairosvg Pillow"
        )

    from PIL.Image import SAVE_ALL

    images = []
    for size in SIZES:
        png_bytes = cairosvg.svg2png(
            url=str(SVG), output_width=size, output_height=size
        )
        images.append(Image.open(io.BytesIO(png_bytes)).convert("RGBA"))

    # Use the largest image as base to avoid Pillow's size-filtering logic
    # (it skips sizes larger than the base image)
    from PIL import IcoImagePlugin

    SAVE_ALL["ICO"] = IcoImagePlugin._save
    base_img = images[-1]
    other_imgs = images[:-1]

    base_img.save(
        ICO,
        format="ICO",
        save_all=True,
        append_images=other_imgs,
        sizes=[(im.width, im.height) for im in images],
    )
    print(f"Wrote {ICO}")


if __name__ == "__main__":
    main()
