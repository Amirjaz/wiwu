"""The hero's bag-only slides (2026-10-20): WiWU's studio renders, cut out of their white and set on a dark
studio sweep in the bag's tone, with a floor reflection, a contact shadow and a little film grain.

    python tools/hero_slides.py media/source-photos/wiwu/brown-render-front.jpg out.png brown
    python tools/hero_slides.py media/source-photos/wiwu/brown-render-back.jpg out.png brown
    python tools/hero_slides.py media/source-photos/wiwu/white-three-quarter.png out.png silver

Writes a 1600 x 2400 PNG; media/source-photos/look/bag-*.jpg are those, and the hero's 1200/600 px files
and its 160 px thumbnails (cropped closer on the bag) are made from them (frontend/public/images/look/).

The hero shows 2:3 photos with object-fit: cover. On wide screens only a band shows (views.LOOK puts it
round the bag) and the headline sits on the right; on phones the full height shows, the sides cropped, the
text over the lower half. So the bag sits left of centre (x 31%), high (y 30%), a third of the frame wide.
"""
import sys

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

W, H = 1600, 2400
CX, CY = 0.31, 0.30

PALETTES = {
    # top of the wall, wall at the floor line, floor near, light colour
    'brown': ((21, 19, 18), (68, 60, 54), (11, 10, 9), (255, 230, 204)),  # taupe, so the brown stands out
    'silver': ((16, 19, 24), (44, 50, 58), (8, 9, 11), (205, 222, 255)),
}


def cut_out(path):
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


def backdrop(palette, horizon):
    """A seamless studio sweep: the wall brightening down to where it curves into the floor (horizon,
    behind the bag's base), the floor darkening towards the camera."""
    top, wall, floor, light = (np.array(c, np.float32) for c in PALETTES[palette])
    y = np.linspace(0, 1, H)[:, None, None]
    x = np.linspace(0, 1, W)[None, :, None]
    wall_part = top + (wall - top) * np.clip(y / horizon, 0, 1) ** 1.4
    floor_part = wall + (floor - wall) * np.clip((y - horizon) / (1 - horizon), 0, 1) ** 0.55
    t = np.clip((y - horizon + 0.03) / 0.06, 0, 1)
    t = t * t * (3 - 2 * t)  # the curve of the sweep
    img = (wall_part * (1 - t) + floor_part * t) * np.ones((1, W, 1), np.float32)
    # A broad key light from the upper left, washing over the wall and the floor around the bag.
    d = np.sqrt(((x - CX + 0.02) / 0.7) ** 2 + ((y - CY + 0.03) / 0.42) ** 2)
    img += light * 0.12 * np.exp(-d ** 2 * 1.6)
    # Vignette.
    v = np.sqrt(((x - 0.4) / 0.9) ** 2 + ((y - 0.45) / 0.8) ** 2)
    img *= np.clip(1.08 - 0.55 * v ** 2, 0.35, 1)
    return img


def place(img, rgb, alpha, width_frac):
    bw = int(W * width_frac)
    bh = int(rgb.shape[0] * bw / rgb.shape[1])
    bag = cv2.resize(rgb, (bw, bh), interpolation=cv2.INTER_AREA)
    a = cv2.resize(alpha, (bw, bh), interpolation=cv2.INTER_AREA)[..., None]
    # Settle it into the scene: a touch darker, with the light falling off to the lower right.
    yy, xx = np.mgrid[0:bh, 0:bw]
    fall = 1.0 - 0.10 * (yy / bh) - 0.06 * (xx / bw)
    bag = bag * 0.93 * fall[..., None]
    x0 = int(W * CX - bw / 2)
    y0 = int(H * CY - bh / 2)
    base = y0 + bh  # where it stands
    # Contact shadow and a soft drop shadow under it.
    shadow = np.zeros((H, W), np.float32)
    cv2.ellipse(shadow, (x0 + bw // 2, base - int(bh * 0.02)), (int(bw * 0.47), int(bh * 0.05)), 0, 0, 360, 1.0, -1)
    shadow = cv2.GaussianBlur(shadow, (0, 0), bh * 0.035)
    img *= (1 - 0.75 * shadow)[..., None]
    wide = np.zeros((H, W), np.float32)
    cv2.ellipse(wide, (x0 + bw // 2, base + int(bh * 0.04)), (int(bw * 0.58), int(bh * 0.14)), 0, 0, 360, 1.0, -1)
    wide = cv2.GaussianBlur(wide, (0, 0), bh * 0.12)
    img *= (1 - 0.45 * wide)[..., None]
    # Reflection on the glossy floor: the bag upside down, fading out.
    refl = bag[::-1]
    ra = a[::-1] * np.linspace(0.16, 0, bh)[:, None, None] ** 1.0
    ry0 = base + 2
    rh = min(bh, H - ry0)
    region = img[ry0:ry0 + rh, x0:x0 + bw]
    img[ry0:ry0 + rh, x0:x0 + bw] = region * (1 - ra[:rh]) + refl[:rh] * ra[:rh]
    region = img[y0:y0 + bh, x0:x0 + bw]
    img[y0:y0 + bh, x0:x0 + bw] = region * (1 - a) + bag * a
    return img


def grain(img, seed=7):
    rng = np.random.default_rng(seed)
    noise = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.7)
    return img + noise[..., None] * 3.2


def main():
    src, out, palette = sys.argv[1], sys.argv[2], sys.argv[3]
    width = float(sys.argv[4]) if len(sys.argv) > 4 else 0.34
    rgb, alpha = cut_out(src)
    bh = W * width * rgb.shape[0] / rgb.shape[1]
    base = (H * CY + bh / 2) / H
    img = backdrop(palette, horizon=base - 0.35 * bh / H)  # the floor line well behind the bag
    img = place(img, rgb, alpha, width)
    img = grain(img)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(out)
    print(out, 'bag', rgb.shape[1], 'x', rgb.shape[0])


if __name__ == '__main__':
    main()
