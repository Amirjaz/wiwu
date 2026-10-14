"""Projecting the three source photos onto the 3D shape (used by tools/build_model.py).

Each texel of the model's texture atlas gets the colour of the photos that see its point on the surface:
facing the camera, not hidden behind another part (depth test), and away from the photo's mask edges
(where background or blur creeps in). The best-placed view dominates, so details stay sharp. Texels no
photo sees (the bottom, the far end) get the leather's colour and the page's leather grain. Cameras come
from tools/fit_cameras.py, in the AI shape's coordinates, which is why this runs before resizing.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / 'media' / '3d' / 'photos'


def load_cameras():
    data = json.loads((ROOT / 'media' / '3d' / 'cameras.json').read_text())
    return data['cameras'], data['width'], data['height']


def raster_uv(uv_px, faces, size):
    """Which triangle covers each texel, and where in it (barycentric)."""
    tri_of = np.full((size, size), -1, np.int32)
    bary = np.zeros((size, size, 3), np.float32)
    for i, f in enumerate(faces):
        a, b, c = uv_px[f]
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        w0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        w1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-3) & (w1 >= -1e-3) & (w2 >= -1e-3)
        if not inside.any():
            continue
        iy, ix = (ys[inside] - 0.5).astype(int), (xs[inside] - 0.5).astype(int)
        tri_of[iy, ix] = i
        bary[iy, ix] = np.stack([w0[inside], w1[inside], w2[inside]], 1)
    return tri_of, bary


def zbuffer(px, depth, faces, width, height):
    """Nearest depth per photo pixel."""
    z = np.full(height * width, np.inf, np.float32)
    for f in faces:
        a, b, c = px[f]
        if min(depth[f]) <= 0:
            continue
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, width - 1), min(y1, height - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        w0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        w1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not inside.any():
            continue
        d = w0 * depth[f[0]] + w1 * depth[f[1]] + w2 * depth[f[2]]
        idx = (ys[inside] - 0.5).astype(int) * width + (xs[inside] - 0.5).astype(int)
        np.minimum.at(z, idx, d[inside].astype(np.float32))
    return z.reshape(height, width)


def sample(rgb, x, y, width=2048):
    """Bilinear colours at pixel positions (any count: cv2.remap wants maps under 32k rows, so the
    points are laid out in rows of `width`)."""
    n = len(x)
    rows = -(-n // width)
    pad = rows * width - n
    mx = np.concatenate([x, np.zeros(pad)]).astype(np.float32).reshape(rows, width)
    my = np.concatenate([y, np.zeros(pad)]).astype(np.float32).reshape(rows, width)
    out = cv2.remap(rgb.astype(np.float32), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out.reshape(-1, 3)[:n]


def balanced_photo(name):
    """The photo made to match the others, so the three blend without visible seams. Returns (rgb, mask).
    - White balance from the bright metal (zipper, pulls, plate, lock), which is neutral gunmetal; the
      dark leather is a poor reference (the front photo turns it navy).
    - Colour noise smoothed (chroma only, so the leather grain stays sharp), and the dark leather pulled
      towards neutral black: brightening the dark front photo otherwise shows green and purple blotches.
    - Exposure matched to the back photo's leather, the best exposed of the three."""
    rgba = np.array(Image.open(PHOTOS / f'{name}.png').convert('RGBA')).astype(np.float32)
    rgb, alpha = rgba[:, :, :3] / 255, rgba[:, :, 3] / 255
    lum = rgb @ [0.299, 0.587, 0.114]
    inside = alpha > 0.9
    bright = inside & (lum > np.quantile(lum[inside], 0.97)) & (lum < 0.95)
    metal = rgb[bright].mean(0)
    rgb = rgb * np.clip(metal.mean() / metal, 0.75, 1.35)

    ycc = cv2.cvtColor(np.clip(rgb, 0, 1).astype(np.float32), cv2.COLOR_RGB2YCrCb)
    y, chroma = ycc[:, :, 0], ycc[:, :, 1:] - 0.5
    chroma = cv2.GaussianBlur(chroma, (0, 0), 2.2)
    keep = np.clip((y - 0.06) / 0.3, 0.12, 1.0)[:, :, None]  # dark leather: little colour left
    ycc[:, :, 1:] = chroma * keep + 0.5
    rgb = cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB)

    lum = rgb @ [0.299, 0.587, 0.114]
    leather = inside & (lum < np.quantile(lum[inside], 0.7))
    target = 0.115
    gain = np.clip(target / np.median(lum[leather]), 0.6, 2.2)
    return np.clip(rgb * gain, 0, 1), alpha


def bake(vertices, normals, faces, uv, size):
    """vertices/normals/faces/uv of the unwrapped mesh (AI shape coordinates). Returns (rgb uint8, coverage)."""
    cameras, width, height = load_cameras()
    uv_px = np.stack([uv[:, 0] * size, (1 - uv[:, 1]) * size], 1)  # image rows go down
    tri_of, bary = raster_uv(uv_px, faces, size)
    covered = tri_of >= 0
    tris = faces[tri_of[covered]]
    b = bary[covered]
    points = (vertices[tris] * b[:, :, None]).sum(1)
    norms = (normals[tris] * b[:, :, None]).sum(1)
    norms /= np.linalg.norm(norms, axis=1, keepdims=True) + 1e-9

    total = np.zeros((len(points), 3))
    weight = np.zeros(len(points))
    best = np.zeros(len(points))
    for name, cam in cameras.items():
        R, _ = cv2.Rodrigues(np.array(cam['rvec']))
        t, f = np.array(cam['tvec']), cam['f']
        K = np.array([[f, 0, width / 2], [0, f, height / 2], [0, 0, 1]])
        cam_v = vertices @ R.T + t
        px_v = (cam_v @ K.T)[:, :2] / cam_v[:, 2:3]
        zbuf = zbuffer(px_v, cam_v[:, 2], faces, width, height)

        cam_p = points @ R.T + t
        px = (cam_p @ K.T)[:, :2] / cam_p[:, 2:3]
        eye = -R.T @ t
        view = eye - points
        dist = np.linalg.norm(view, axis=1)
        cos = (norms * view).sum(1) / dist
        ix = np.clip(px[:, 0].astype(int), 0, width - 1)
        iy = np.clip(px[:, 1].astype(int), 0, height - 1)
        inside = (px[:, 0] >= 0) & (px[:, 0] < width) & (px[:, 1] >= 0) & (px[:, 1] < height)
        visible = inside & (cam_p[:, 2] <= zbuf[iy, ix] * 1.004 + 0.002)

        rgb, alpha = balanced_photo(name)
        mask = (alpha > 0.5).astype(np.uint8)
        edge = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        edge_w = np.clip((edge[iy, ix] - 3) / 14, 0, 1)
        w = np.where(visible, np.clip(cos, 0, 1) ** 3 * edge_w * (f / dist) ** 2, 0)
        w = np.where(cos > 0.12, w, 0)
        colour = sample(rgb, px[:, 0], px[:, 1])
        w2 = w ** 2  # sharpen towards the best view
        total += colour * w2[:, None]
        weight += w2
        best = np.maximum(best, w)
        print(f'    {name}: sees {np.count_nonzero(w > 0) / len(w):.0%} of the surface')

    # Normalise coverage so a well-seen texel is 1; fade to the leather fill where views get poor.
    seen = weight > 0
    colour = np.zeros_like(total)
    colour[seen] = total[seen] / weight[seen, None]
    ref = np.quantile(best[seen], 0.5) if seen.any() else 1
    cover = np.clip(best / (0.35 * ref), 0, 1)
    leather = np.array([0.105, 0.106, 0.112])
    colour = colour * cover[:, None] + leather * (1 - cover[:, None])

    image = np.zeros((size, size, 3), np.float32)
    image[covered] = colour
    coverage = np.zeros((size, size), np.float32)
    coverage[covered] = cover
    # Gutter: grow each chart outward a few texels so mipmaps don't bleed the empty atlas in.
    filled = covered.copy()
    for _ in range(8):
        grown = cv2.dilate(image, np.ones((3, 3), np.uint8))
        grown_mask = cv2.dilate(filled.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        new = grown_mask & ~filled
        image[new] = grown[new]
        filled |= new
    image[~filled] = leather
    return (np.clip(image, 0, 1) * 255).astype(np.uint8), coverage
