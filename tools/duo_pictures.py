"""Both versions of the bag in one colour, side by side (2026-10-23, Amir: the closing section's cards show
each colour with its one-zipper and two-zipper bag together). Made from the colour pictures
(tools/color_photos.py, tools/phantom_photos.py), the two-zipper bag on the left, a little wider, as it is
(28 cm against the Alpha's 25), both standing on the same line, on a transparent background.

    python tools/duo_pictures.py   (writes frontend/public/images/colors/duo-<black|brown>.webp)
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
COLORS = ROOT / 'frontend' / 'public' / 'images' / 'colors'
PAIRS = {'black': ('black.webp', 'phantom-black.webp'), 'brown': ('brown.webp', 'phantom-brown.webp')}
ALPHA_W = 620  # the Alpha bag's width in the picture, px; the two-zipper bag 28/25 of it
MARGIN = 0.05  # each colour picture's margin on either side, as a share of its bag's width (color_photos.picture)
GAP = 24


def scaled(path, bag_width):
    im = Image.open(path).convert('RGBA')
    width = round(bag_width * (1 + 2 * MARGIN))
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def main():
    for name, (alpha, phantom) in PAIRS.items():
        a = scaled(COLORS / alpha, ALPHA_W)
        p = scaled(COLORS / phantom, round(ALPHA_W * 28 / 25))
        h = max(a.height, p.height)
        out = Image.new('RGBA', (p.width + GAP + a.width, h), (0, 0, 0, 0))
        out.alpha_composite(p, (0, h - p.height))  # bottoms level: both shadows end on the same line
        out.alpha_composite(a, (p.width + GAP, h - a.height))
        out.save(COLORS / f'duo-{name}.webp', quality=88, method=6)
        print(name, out.size)


if __name__ == '__main__':
    main()
