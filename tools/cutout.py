"""Cut the purse out of each photo: transparent PNG, cropped to the purse, plus a preview on grey.

Usage: python cutout.py <src_dir> <out_dir> <model> [<model> ...]
Keeps only the largest connected blob, so stray fingers and table props at the edges are dropped.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from rembg import new_session, remove


def largest_blob(alpha: np.ndarray) -> np.ndarray:
    """Zero every pixel not in the largest 8-connected region of alpha > 32."""
    mask = alpha > 32
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    sizes = [0]
    label = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not labels[y, x]:
                label += 1
                stack = [(y, x)]
                labels[y, x] = label
                n = 0
                while stack:
                    cy, cx = stack.pop()
                    n += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                                labels[ny, nx] = label
                                stack.append((ny, nx))
                sizes.append(n)
    if label == 0:
        return alpha
    keep = int(np.argmax(sizes))
    out = alpha.copy()
    out[labels != keep] = 0
    return out


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for model in sys.argv[3:]:
        session = new_session(model)
        for path in sorted(src.glob("*.jpg")):
            img = Image.open(path).convert("RGB")
            cut = np.array(remove(img, session=session, post_process_mask=True))
            # Blob search on a quarter-size mask (fast), then scaled back up as a keep-mask.
            small = Image.fromarray(cut[:, :, 3]).resize((img.width // 4, img.height // 4))
            kept = largest_blob(np.array(small))
            keep = np.array(Image.fromarray((kept > 0).astype(np.uint8) * 255).resize(img.size)) > 0
            # Grow the keep-mask a little so soft edges next to the blob survive the downscale.
            keep_img = Image.fromarray(keep.astype(np.uint8) * 255).filter(
                __import__("PIL.ImageFilter", fromlist=["MaxFilter"]).MaxFilter(9))
            cut[:, :, 3] = np.where(np.array(keep_img) > 0, cut[:, :, 3], 0)

            rgba = Image.fromarray(cut)
            bbox = rgba.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
            pad = int(0.04 * max(img.size))
            box = (max(bbox[0] - pad, 0), max(bbox[1] - pad, 0),
                   min(bbox[2] + pad, img.width), min(bbox[3] + pad, img.height))
            rgba = rgba.crop(box)
            stem = f"{path.stem}-{model}"
            rgba.save(out / f"{stem}.png")
            grey = Image.new("RGBA", rgba.size, (205, 205, 205, 255))
            grey.alpha_composite(rgba)
            grey.convert("RGB").save(out / f"{stem}-preview.jpg", quality=90)
            print(model, path.name, "->", rgba.size)


if __name__ == "__main__":
    main()
