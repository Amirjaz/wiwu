"""Photo 2: drop the sofa pillow that sits on top of the zipper.

For each column, find where the dark bag body starts; the zipper teeth sit just above it.
Bright, grey pixels above that line are pillow, so their alpha goes to zero.
Usage: python fix2.py <in.png> <out.png> <zoom.jpg>
"""
import sys

import numpy as np
from PIL import Image

src, dst, zoom = sys.argv[1:4]
im = Image.open(src).convert("RGBA")
a = np.array(im).astype(np.int32)
h, w = a.shape[:2]
rgb, alpha = a[:, :, :3], a[:, :, 3]
lum = rgb @ np.array([299, 587, 114]) // 1000
chroma = rgb.max(axis=2) - rgb.min(axis=2)

TEETH = 15  # zipper teeth height in px at this size, plus a little margin
dark_top = np.full(w, -1)
for x in range(w):
    col = (lum[:, x] < 45) & (alpha[:, x] > 128)
    run = np.convolve(col.astype(int), np.ones(4, int), "valid") == 4  # 4 dark px in a row
    idx = np.nonzero(run)[0]
    if len(idx):
        dark_top[x] = idx[0]

# Smooth the line (the zipper is a gentle curve) and fill gaps.
xs = np.nonzero(dark_top >= 0)[0]
line = np.interp(np.arange(w), xs, dark_top[xs])
k = 31
line = np.array([np.median(line[max(0, x - k): x + k]) for x in range(w)])

out = a.copy()
removed = 0
for x in range(w):
    cut = int(line[x]) - TEETH
    for y in range(max(cut + 6, 0)):
        pillow = lum[y, x] > 105 and chroma[y, x] < 45
        if y < cut or pillow:
            if out[y, x, 3]:
                removed += 1
            out[y, x, 3] = 0 if (y < cut - 1 or pillow) else out[y, x, 3] // 2
print("removed px:", removed)

res = Image.fromarray(out.astype(np.uint8))
bbox = res.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
pad = 30
res = res.crop((max(bbox[0] - pad, 0), max(bbox[1] - pad, 0), min(bbox[2] + pad, w), min(bbox[3] + pad, h)))
res.save(dst)
z = res.crop((0, 0, res.width, 140)).resize((res.width * 2, 280))
bg = Image.new("RGBA", z.size, (255, 0, 255, 255))
bg.alpha_composite(z)
bg.convert("RGB").save(zoom, quality=90)
