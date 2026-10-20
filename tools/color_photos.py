"""Each colour's picture (2026-10-20): the bag cut out of WiWU's studio render, all three turned the same way,
on a transparent background with a soft shadow under it. Shown at checkout for the picked colour, beside
the parts list where the 3D bag can't run, and in the home page's closing section.

    python tools/color_photos.py   (writes frontend/public/images/colors/<black|brown|white>.webp)

The black is WiWU's brown render made black (tools/black_render.py: their black render is from another
angle); the silver is their silver photo, which is small (its lock differs, so it can't come from the brown
render), so it's drawn a little bigger with Lanczos and sharpened.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hero_slides  # noqa: E402  (tools/hero_slides.py)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'media' / 'source-photos' / 'wiwu'
OUT = ROOT / 'frontend' / 'public' / 'images' / 'colors'
PHOTOS = {  # colour file: (render, the bag's width in pixels)
    'black': ('black-render-front.jpg', 1000),
    'brown': ('brown-render-front.jpg', 1000),
    'white': ('white-three-quarter.png', 700),
}


def picture(src, width):
    rgb, alpha = hero_slides.cut_out(src)
    bh = int(rgb.shape[0] * width / rgb.shape[1])
    if width <= rgb.shape[1]:
        bag = cv2.resize(rgb, (width, bh), interpolation=cv2.INTER_AREA)
        a = cv2.resize(alpha, (width, bh), interpolation=cv2.INTER_AREA)
    else:
        bag = cv2.resize(rgb, (width, bh), interpolation=cv2.INTER_LANCZOS4)
        bag = np.clip(bag + 0.6 * (bag - cv2.GaussianBlur(bag, (0, 0), 1.2)), 0, 255)
        a = np.clip(cv2.resize(alpha, (width, bh), interpolation=cv2.INTER_LINEAR), 0, 1)
    side, below = int(width * 0.05), int(bh * 0.16)
    w, h = width + 2 * side, bh + below
    # A soft shadow under it, in the alpha (black, partly see-through), then the bag over it.
    shadow = np.zeros((h, w), np.float32)
    cv2.ellipse(shadow, (w // 2, bh - int(bh * 0.01)), (int(width * 0.47), int(bh * 0.06)), 0, 0, 360, 1.0, -1)
    shadow = cv2.GaussianBlur(shadow, (0, 0), bh * 0.04) * 0.42
    out_a = shadow.copy()
    out_rgb = np.zeros((h, w, 3), np.float32)
    out_a[:bh, side:side + width] = a + shadow[:bh, side:side + width] * (1 - a)
    region = out_rgb[:bh, side:side + width]
    out_rgb[:bh, side:side + width] = bag * (a / np.maximum(out_a[:bh, side:side + width], 1e-4))[..., None] + region
    rgba = np.dstack([np.clip(out_rgb, 0, 255), np.clip(out_a * 255, 0, 255)]).astype(np.uint8)
    return Image.fromarray(rgba, 'RGBA')


def main():
    for name, (src, width) in PHOTOS.items():
        im = picture(SRC / src, width)
        im.save(OUT / f'{name}.webp', quality=88, method=6)
        print(name, im.size)


if __name__ == '__main__':
    main()
