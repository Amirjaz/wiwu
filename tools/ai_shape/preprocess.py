"""Inputs for the AI shape (run_hunyuan.py): square-padded, colour-normalised copies of the purse cutouts.

    python tools/ai_shape/preprocess.py

Reads media/cutouts/purse-*-lifted.png, writes media/3d/ai/inputs/ (not in git): <name>-lifted-sq.png,
<name>-norm-sq.png (colour cast removed, brightness matched to the back photo) and a white-background copy.
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'media' / 'cutouts'
OUT = ROOT / 'media' / '3d' / 'ai' / 'inputs'
OUT.mkdir(parents=True, exist_ok=True)

ref = np.array(Image.open(SRC / 'purse-back-lifted.png').convert('RGBA')).astype(np.float32)
rm = ref[..., 3] > 128
ref_mean = ref[rm][:, :3].mean(0)
ref_lum = ref_mean.mean()


def normalise(a):
    """Remove colour cast and match mean brightness to the back-lifted shot."""
    m = a[..., 3] > 128
    mean = a[m][:, :3].mean(0)
    gain = ref_lum / mean  # per-channel gain -> neutral grey mean at ref brightness
    out = a.copy()
    out[..., :3] = np.clip(a[..., :3] * gain, 0, 255)
    # slight desaturation to kill residual blue
    rgb = out[..., :3]
    g = rgb.mean(-1, keepdims=True)
    out[..., :3] = g + (rgb - g) * 0.15
    return out


def square(a, size=1024, margin=0.12):
    im = Image.fromarray(a.astype(np.uint8), 'RGBA')
    im = im.crop(im.getbbox())
    w, h = im.size
    s = (1 - 2 * margin) * size / max(w, h)
    im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    return canvas


for name in ['back', 'front', 'side-lock']:
    a = np.array(Image.open(SRC / f'purse-{name}-lifted.png').convert('RGBA')).astype(np.float32)
    sq = square(a)
    sq.save(OUT / f'{name}-lifted-sq.png')
    n = square(normalise(a)) if name != 'back' else sq
    n.save(OUT / f'{name}-norm-sq.png')
    white = Image.new('RGBA', n.size, (255, 255, 255, 255))
    white.alpha_composite(n)
    white.convert('RGB').save(OUT / f'{name}-norm-sq-white.png')
    print(name, 'done', sq.size)
