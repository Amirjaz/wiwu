"""The black bag at the brown and silver renders' angle (2026-10-20). WiWU's black render
(media/source-photos/wiwu/black-three-quarter.jpg) is from another angle, so the hero's posters would show
it turned differently from the other two. This takes the brown render and makes its leather black, as on
the black render: neutral, the same brightness, the grain a little stronger. The lock, the zipper and the
logo plate are the same on both bags and stay as they are.

    python tools/black_render.py   (writes media/source-photos/wiwu/black-render-front.jpg)
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'media' / 'source-photos' / 'wiwu' / 'brown-render-front.jpg'
OUT = ROOT / 'media' / 'source-photos' / 'wiwu' / 'black-render-front.jpg'
# The leather's brightness (luma of the sRGB values, 0..1) on the middle of the front, measured on both renders.
BROWN_MEAN, BLACK_MEAN = 0.255, 0.239
GRAIN = 1.3  # the black render's grain shows a little more


def main():
    rgb = np.asarray(Image.open(SRC).convert('RGB')).astype(np.float32) / 255
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    # The leather: brown (not the lock's grey metal, the zipper's grey tape or the sensor's gold frame).
    leather = ((h > 8) & (h < 34) & (s > 0.15) & (v < 0.55)).astype(np.float32)
    leather = cv2.GaussianBlur(leather, (0, 0), 1.5)[..., None]
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    black = np.clip(BLACK_MEAN + (luma - BROWN_MEAN) * GRAIN, 0, 1)[..., None] * np.ones(3, np.float32)
    out = rgb * (1 - leather) + black * leather
    Image.fromarray((np.clip(out, 0, 1) * 255).round().astype(np.uint8)).save(OUT, quality=95)
    print(OUT)


if __name__ == '__main__':
    main()
