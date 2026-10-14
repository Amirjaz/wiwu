"""The product photos the site shows (frontend/public/images/*.webp), from media/cutouts.

    python tools/web_images.py   (needs Pillow + numpy)

- Front photo: removes the last sliver of the sofa pillow above the zipper (bright, nearly grey pixels;
  the zipper teeth are darker and warmer) and anything left floating above it in that column.
- All three: a mild lift so the leather grain reads on a light page (the photos are underexposed), and
  the front shot's blue cast pulled toward neutral (it's the same black bag; PLAN.md §2).
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CUTOUTS = ROOT / 'media' / 'cutouts'
OUT = ROOT / 'frontend' / 'public' / 'images'


def remove_pillow_sliver(a):
    rgb = a[:, :, :3].astype(int)
    lum = (rgb * [299, 587, 114]).sum(2) // 1000
    chroma = rgb.max(2) - rgb.min(2)
    pillow = (a[:, :, 3] > 20) & (lum > 155) & (chroma < 25)
    pillow[60:] = False  # only the band above the zipper
    for x in np.nonzero(pillow.any(0))[0]:
        lowest = np.nonzero(pillow[:, x])[0].max()
        a[: lowest + 1, x, 3] = 0
    return a


def export(name, source, fix=None):
    a = np.array(Image.open(CUTOUTS / source).convert('RGBA'))
    if fix:
        a = fix(a)
    rgb = a[:, :, :3].astype(np.float32) / 255
    rgb = np.clip(rgb ** 0.8, 0, 1)
    grey = rgb.mean(2, keepdims=True)
    rgb = grey + (rgb - grey) * 0.55
    a[:, :, :3] = (rgb * 255).astype(np.uint8)
    image = Image.fromarray(a)
    image.save(OUT / f'{name}.webp', 'WEBP', quality=88, method=6)
    print(name, image.size)


if __name__ == '__main__':
    export('front', 'purse-front.png', remove_pillow_sliver)
    export('back', 'purse-back.png')
    export('side', 'purse-side-lock.png')
