"""Full-frame bag masks for the three source photos, used to fit cameras and project the photos onto
the 3D model (tools/texture_model.py). Writes media/3d/photos/<name>.png: the photo with the mask as alpha.

    python tools/photo_masks.py   (in the venv that has rembg; see tools/cutout.py)
"""
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from rembg import new_session, remove

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {'side': '1-side-lock.jpg', 'front': '2-front.jpg', 'back': '3-back.jpg'}
OUT = ROOT / 'media' / '3d' / 'photos'


def largest_blob(mask):
    """Keep the largest 8-connected region (drops fingers and props at the edges)."""
    from scipy import ndimage

    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n <= 1:
        return mask
    sizes = ndimage.sum(mask, labels, range(1, n + 1))
    return labels == (1 + int(np.argmax(sizes)))


def cut_pillow(rgba):
    """Front photo: a sofa pillow touches the top zipper. Per column, find where the dark bag body
    starts; the teeth sit just above it; bright greyish pixels above that are pillow."""
    a = rgba.astype(np.int32)
    lum = (a[:, :, :3] * [299, 587, 114]).sum(2) // 1000
    chroma = a[:, :, :3].max(2) - a[:, :, :3].min(2)
    alpha = a[:, :, 3]
    h, w = alpha.shape
    tops = np.full(w, -1)
    for x in range(w):
        col = (lum[:, x] < 45) & (alpha[:, x] > 128)
        run = np.convolve(col.astype(int), np.ones(4, int), 'valid') == 4
        idx = np.nonzero(run)[0]
        if len(idx):
            tops[x] = idx[0]
    xs = np.nonzero(tops >= 0)[0]
    line = np.interp(np.arange(w), xs, tops[xs])
    line = np.array([np.median(line[max(0, x - 30): x + 30]) for x in range(w)])
    teeth = 18  # px at this size
    for x in range(w):
        cut = int(line[x]) - teeth
        for y in range(max(cut + 6, 0)):
            if y < cut or (lum[y, x] > 105 and chroma[y, x] < 45):
                rgba[y, x, 3] = 0
    # The last sliver: bright, nearly neutral pixels in the band right above the zipper.
    sliver = (rgba[:, :, 3] > 20) & (lum > 155) & (chroma < 25)
    band = np.zeros_like(sliver)
    for x in range(w):
        top = int(line[x])
        band[max(0, top - 40): top - 4, x] = True
    for x in np.nonzero((sliver & band).any(0))[0]:
        rgba[: np.nonzero(sliver[:, x] & band[:, x])[0].max() + 1, x, 3] = 0
    return rgba


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = new_session('birefnet-general-lite')
    for name, file in SOURCES.items():
        image = Image.open(ROOT / 'media' / 'source-photos' / file).convert('RGB')
        rgba = np.array(remove(image, session=session, post_process_mask=True))
        keep = largest_blob(rgba[:, :, 3] > 32)
        keep = np.array(Image.fromarray(keep.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
        rgba[:, :, 3] = np.where(keep, rgba[:, :, 3], 0)
        if name == 'front':
            rgba = cut_pillow(rgba)
        Image.fromarray(rgba).save(OUT / f'{name}.png')
        print(name, image.size, 'bag px:', int((rgba[:, :, 3] > 128).sum()))


if __name__ == '__main__':
    os.environ.setdefault('U2NET_HOME', str(Path(os.environ.get('TEMP', '.')) / 'u2net'))
    main()
