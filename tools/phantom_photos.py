"""The two-zipper bag's pictures (WiWU Phantom Pro, 2026-10-21): black and deep brown, the colours the client
has. The only clean studio render found is of its tan bag (media/source-photos/wiwu/phantom-tan.png, from a
reseller's page, elryan.com; the other stores' photos carry their watermark), so this makes its leather each
colour, as tools/black_render.py did for the Alpha: the deep brown of Amir's screenshot of the bag, and a
neutral black. The zippers, piping, handle, lock and logo plate are the same on every colour and stay as
they are (the sensor's gold frame is kept out by hand). Then each is cut out like the Alpha's colour
pictures (tools/color_photos.py).

    python tools/phantom_photos.py   (writes media/source-photos/wiwu/phantom-<black|brown>.jpg and
                                       frontend/public/images/colors/phantom-<black|brown>.webp)
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import color_photos  # noqa: E402  (tools/color_photos.py)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'media' / 'source-photos' / 'wiwu' / 'phantom-tan.png'
OUT = ROOT / 'frontend' / 'public' / 'images' / 'colors'
TAN_MEAN = 0.578  # the tan leather's brightness (luma, 0..1) on the middle of the front
COLOURS = {  # name: the leather's mean colour (sRGB 0..1), and how much of the tan's grain to keep
    'brown': (np.array([66, 46, 35], np.float32) / 255, 1.6),  # Amir's screenshot of the bag
    'black': (np.array([36, 37, 39], np.float32) / 255, 1.9),
}
SENSOR = (36, 645, 76, 712)  # x0, y0, x1, y1: the fingerprint sensor's gold frame, not leather


def recolour(rgb, colour, grain):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    leather = ((h > 8) & (h < 34) & (s > 0.18) & (v > 0.15)).astype(np.float32)  # edges blended with the lock too
    x0, y0, x1, y1 = SENSOR
    leather[y0:y1, x0:x1] = 0
    leather = cv2.GaussianBlur(leather, (0, 0), 1.5)[..., None]
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    shade = np.clip(1 + (luma / TAN_MEAN - 1) * grain, 0, 3)[..., None]
    return rgb * (1 - leather) + np.clip(colour * shade, 0, 1) * leather


def main():
    rgba = np.asarray(Image.open(SRC).convert('RGBA')).astype(np.float32) / 255
    rgb = rgba[..., :3] * rgba[..., 3:] + (1 - rgba[..., 3:])  # on white, as the renders are
    for name, (colour, grain) in COLOURS.items():
        out = recolour(rgb, colour, grain)
        jpg = SRC.with_name(f'phantom-{name}.jpg')
        Image.fromarray((np.clip(out, 0, 1) * 255).round().astype(np.uint8)).save(jpg, quality=95)
        im = color_photos.picture(jpg, 900)
        im.save(OUT / f'phantom-{name}.webp', quality=88, method=6)
        print(name, im.size)


if __name__ == '__main__':
    main()
