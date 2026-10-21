"""The hero's bag-only posters (2026-10-20): WiWU's studio renders, cut out of their white and set on a dark
studio sweep, with a floor reflection, contact shadows and a little film grain.

    python tools/hero_slides.py [--wide] <out.png> <palette> <render>[@x,y,width] ...

Two of each poster: tall (1600 x 2400, for phones: the full height shows, the sides cropped, the text over
the lower half, so the bags stand left of centre and high) and --wide (2560 x 1400, for laptops: the
headline sits on the right, so the bags stand in the left half, a little above the middle). One render
stands where its frame puts a lone bag. Several: each at x, y (its centre, as fractions of the frame) and
width (of the frame), drawn in the order given, so the last is in front; ",mirror" after the width flips
that bag left to right:

    W=media/source-photos/wiwu
    python tools/hero_slides.py bag-black.png steel $W/black-render-front.jpg   (from tools/black_render.py)
    python tools/hero_slides.py bag-brown.png brown $W/brown-render-front.jpg
    python tools/hero_slides.py bag-colors.png graphite $W/black-render-front.jpg@0.19,0.30,0.29 \\
        $W/brown-render-front.jpg@0.50,0.30,0.29,mirror   (side by side as mirror images: Amir, 2026-10-21)
    python tools/hero_slides.py --wide bag-black-wide.png steel $W/black-render-front.jpg
    python tools/hero_slides.py --wide bag-brown-wide.png brown $W/brown-render-front.jpg
    python tools/hero_slides.py --wide bag-colors-wide.png graphite $W/black-render-front.jpg@0.13,0.47,0.175 \\
        $W/brown-render-front.jpg@0.325,0.47,0.175,mirror

The silver poster (palette 'silver', from WiWU's small silver photo, $W/white-three-quarter.png, drawn no
bigger than its 658 px) was dropped on 2026-10-21: the client doesn't have the silver bag, and the colours
poster shows black and brown only. media/source-photos/look/bag-*.jpg are the tall posters and
bag-*-wide.jpg the wide ones; the hero's files come from them (frontend/public/images/look/).
"""
import sys

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

W, H = 1600, 2400
SWEEP = 0.06  # how tall the curve from wall to floor is (the wide frame's is softer: its floor line spans more)
SINGLE = (0.31, 0.30, 0.34)  # x, y, width of a lone bag
WIDE = (2560, 1400), (0.25, 0.47, 0.30), 0.18

PALETTES = {
    # top of the wall, the wall where it meets the floor, the floor near the camera, the light's colour
    'brown': ((21, 19, 18), (68, 60, 54), (11, 10, 9), (255, 230, 204)),  # taupe, so the brown stands out
    'silver': ((16, 19, 24), (44, 50, 58), (8, 9, 11), (205, 222, 255)),
    'steel': ((30, 32, 36), (118, 121, 127), (13, 14, 16), (240, 244, 255)),  # light enough for black
    'graphite': ((24, 26, 29), (92, 95, 100), (11, 12, 13), (245, 245, 250)),  # the colours together
}


def cut_out(path):
    """The bag (colour, alpha), cropped to it, from a render on white."""
    img = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    near_white = img.min(axis=2) > 246
    labels, _ = ndimage.label(near_white)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, border[border > 0])
    fg = ndimage.binary_fill_holes(~background)
    fg = ndimage.binary_opening(fg, iterations=2)
    # The render's contact shadow: a thin grey line under the bag, whose light outer part would show as a
    # pale strip on a dark floor. Light, colourless pixels along the bottom edge go.
    rows = np.arange(fg.shape[0])[:, None]
    bottom = np.where(fg.any(axis=0), (fg * rows).max(axis=0), -1)[None, :]
    height = np.ptp(np.nonzero(fg.any(axis=1))[0])
    band = rows > bottom - max(2, int(height * 0.012))
    neutral = (img.max(axis=2) - img.min(axis=2) < 14) & (img.min(axis=2) > 110)
    fg &= ~(band & neutral)
    fg = ndimage.binary_opening(fg, iterations=1)
    # The edge pixels are half white: shave them off, then give everything outside the shaved bag the
    # colour of the nearest pixel inside it, so no white fringe survives the soft edge.
    shave = max(1, round(img.shape[1] / 1200))
    inner = ndimage.binary_erosion(fg, iterations=shave)
    _, (iy, ix) = ndimage.distance_transform_edt(~inner, return_indices=True)
    rgb = img[iy, ix]
    alpha = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), max(0.7, shave * 0.8))
    ys, xs = np.nonzero(alpha > 0.02)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    return rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]


def backdrop(palette, horizon, light_at):
    """A seamless studio sweep: the wall brightening down to where it curves into the floor (horizon,
    behind the bags), the floor darkening towards the camera, a broad key light from the upper left."""
    top, wall, floor, light = (np.array(c, np.float32) for c in PALETTES[palette])
    y = np.linspace(0, 1, H)[:, None, None]
    x = np.linspace(0, 1, W)[None, :, None]
    wall_part = top + (wall - top) * np.clip(y / horizon, 0, 1) ** 1.4
    floor_part = wall + (floor - wall) * np.clip((y - horizon) / (1 - horizon), 0, 1) ** 0.55
    t = np.clip((y - horizon + SWEEP / 2) / SWEEP, 0, 1)
    t = t * t * (3 - 2 * t)  # the curve of the sweep
    img = (wall_part * (1 - t) + floor_part * t) * np.ones((1, W, 1), np.float32)
    lx, ly = light_at
    d = np.sqrt(((x - lx + 0.02) / 0.7) ** 2 + ((y - ly + 0.03) / 0.42) ** 2)
    img += light * 0.12 * np.exp(-d ** 2 * 1.6)
    v = np.sqrt(((x - 0.4) / 0.9) ** 2 + ((y - 0.45) / 0.8) ** 2)
    img *= np.clip(1.08 - 0.55 * v ** 2, 0.35, 1)
    return img


def place(img, rgb, alpha, cx, cy, width):
    """One bag standing on the floor with its centre at (cx, cy): shadows and reflection, then the bag."""
    bw = int(W * width)
    bh = int(rgb.shape[0] * bw / rgb.shape[1])
    if bw <= rgb.shape[1]:
        bag = cv2.resize(rgb, (bw, bh), interpolation=cv2.INTER_AREA)
        a = cv2.resize(alpha, (bw, bh), interpolation=cv2.INTER_AREA)[..., None]
    else:  # a small source (the silver photo): Lanczos, and the softness that adds sharpened back a little
        bag = cv2.resize(rgb, (bw, bh), interpolation=cv2.INTER_LANCZOS4)
        bag = np.clip(bag + 0.6 * (bag - cv2.GaussianBlur(bag, (0, 0), 1.2)), 0, 255)
        a = np.clip(cv2.resize(alpha, (bw, bh), interpolation=cv2.INTER_LINEAR), 0, 1)[..., None]
    # Settle it into the scene: a touch darker, with the light falling off to the lower right.
    yy, xx = np.mgrid[0:bh, 0:bw]
    bag = bag * 0.93 * (1.0 - 0.10 * (yy / bh) - 0.06 * (xx / bw))[..., None]
    x0 = int(W * cx - bw / 2)
    y0 = int(H * cy - bh / 2)
    base = y0 + bh  # where it stands
    for (ry, rx, ryy), strength, blur in (((-0.02, 0.47, 0.05), 0.75, 0.035), ((0.04, 0.58, 0.14), 0.45, 0.12)):
        shadow = np.zeros((H, W), np.float32)
        cv2.ellipse(shadow, (x0 + bw // 2, base + int(bh * ry)), (int(bw * rx), int(bh * ryy)), 0, 0, 360, 1.0, -1)
        img *= (1 - strength * cv2.GaussianBlur(shadow, (0, 0), bh * blur))[..., None]
    # Reflection on the glossy floor: the bag upside down, fading out.
    ra = a[::-1] * np.linspace(0.16, 0, bh)[:, None, None]
    rh = min(bh, H - base - 2)
    region = img[base + 2:base + 2 + rh, x0:x0 + bw]
    img[base + 2:base + 2 + rh, x0:x0 + bw] = region * (1 - ra[:rh]) + bag[::-1][:rh] * ra[:rh]
    region = img[y0:y0 + bh, x0:x0 + bw]
    img[y0:y0 + bh, x0:x0 + bw] = region * (1 - a) + bag * a


def grain(img, seed=7):
    rng = np.random.default_rng(seed)
    noise = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.7)
    return img + noise[..., None] * 3.2


def main():
    global W, H, SINGLE, SWEEP
    args = sys.argv[1:]
    if args[0] == '--wide':
        (W, H), SINGLE, SWEEP = WIDE
        args = args[1:]
    out, palette, *specs = args
    bags = []
    for spec in specs:
        path, _, where = spec.partition('@')
        fields = where.split(',') if where else []
        mirror = fields[-1:] == ['mirror']
        fields = fields[:3]
        cx, cy, width = (float(v) for v in fields) if fields else SINGLE
        rgb, alpha = cut_out(path)
        if mirror:  # flipped left to right, so two bags can face each other
            rgb, alpha = np.ascontiguousarray(rgb[:, ::-1]), np.ascontiguousarray(alpha[:, ::-1])
        bags.append((rgb, alpha, cx, cy, width, W * width * rgb.shape[0] / rgb.shape[1]))
    # The floor line well behind the furthest bag.
    horizon = min((H * cy + bh / 2 - 0.35 * bh) / H for _, _, _, cy, _, bh in bags)
    light_x = sum(b[2] for b in bags) / len(bags)
    light_y = sum(b[3] for b in bags) / len(bags)
    img = backdrop(palette, horizon, (light_x, light_y))
    for rgb, alpha, cx, cy, width, _ in bags:
        place(img, rgb, alpha, cx, cy, width)
    Image.fromarray(np.clip(grain(img), 0, 255).astype(np.uint8)).save(out)
    print(out)


if __name__ == '__main__':
    main()
