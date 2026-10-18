"""The product images the site shows (frontend/public/images/), from WiWU's own studio photos.

    .venv-3d/Scripts/python tools/studio_images.py   (Pillow, numpy, scipy)

The photos (media/source-photos/wiwu/, found on resellers' pages on 2026-10-19, Amir agreed to use them)
are on plain white. The bag is cut out by flooding the white in from the photo's edges, so bright parts
inside the bag (the brand plate, the lock) stay. Writes:
- front.webp, back.webp, side.webp: the black bag straight on (the 3D section's backup photos with their
  numbers in views.PARTS, the size drawing, link previews);
- colors/<black|brown|white>.webp: each colour at three-quarters (checkout, search data).
They replace the client's own phone photos (tools/web_images.py), which were softer.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'media' / 'source-photos' / 'wiwu'
OUT = ROOT / 'frontend' / 'public' / 'images'

# name in the site, source photo, the brightness from which a pixel can be background, longest side
IMAGES = [
    ('front', 'black-front.jpg', 200, 960),
    ('back', 'black-back.jpg', 200, 960),
    ('side', 'black-lock-end.webp', 200, 760),
    ('colors/black', 'black-three-quarter.jpg', 200, 900),
    ('colors/brown', 'brown-three-quarter.jpg', 205, 900),
    ('colors/white', 'white-three-quarter.png', 222, 900),
]


def cutout(image, threshold):
    rgb = np.asarray(image.convert('RGB')).astype(np.int32)
    lum = (rgb * [299, 587, 114]).sum(2) // 1000
    chroma = rgb.max(2) - rgb.min(2)
    light = (lum >= threshold) & (chroma < 24)
    labels, _ = ndimage.label(light)
    edge = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, edge[edge > 0])
    bag = ~background
    # The bag only: its largest piece, holes inside it filled, the edge softened by a pixel.
    pieces, n = ndimage.label(bag)
    if n > 1:
        sizes = ndimage.sum(bag, pieces, range(1, n + 1))
        bag = pieces == 1 + int(np.argmax(sizes))
    bag = ndimage.binary_fill_holes(bag)
    alpha = Image.fromarray((bag * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    out = image.convert('RGB')
    out.putalpha(alpha)
    ys, xs = np.nonzero(bag)
    pad = 4
    return out.crop((max(xs.min() - pad, 0), max(ys.min() - pad, 0),
                     min(xs.max() + pad + 1, out.width), min(ys.max() + pad + 1, out.height)))


def main():
    (OUT / 'colors').mkdir(parents=True, exist_ok=True)
    for name, source, threshold, longest in IMAGES:
        image = cutout(Image.open(SOURCE / source), threshold)
        scale = min(1, longest / max(image.size))
        if scale < 1:
            image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
        path = OUT / f'{name}.webp'
        image.save(path, 'WEBP', quality=86, method=6)
        print(f'{path.relative_to(ROOT)}: {image.width} x {image.height}, {path.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
