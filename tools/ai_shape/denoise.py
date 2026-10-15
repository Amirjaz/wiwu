"""Denoised copies of the front and side inputs (the phone photos are grainy in the black leather).
The shape the hero is built from, media/3d/ai/hunyuan2mv-shape-3view-denoised.glb, was made from these.

    python tools/ai_shape/denoise.py        (after preprocess.py)

Writes media/3d/ai/inputs/<name>-norm-dn-sq.png and _dn_check.jpg (before | after, front then side).
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

INPUTS = Path(__file__).resolve().parents[2] / 'media' / '3d' / 'ai' / 'inputs'

for n in ['front', 'side-lock']:
    a = np.array(Image.open(INPUTS / f'{n}-norm-sq.png').convert('RGBA'))
    rgb = cv2.cvtColor(a[..., :3], cv2.COLOR_RGB2BGR)
    d = cv2.fastNlMeansDenoisingColored(rgb, None, 9, 9, 7, 21)
    a[..., :3] = cv2.cvtColor(d, cv2.COLOR_BGR2RGB)
    Image.fromarray(a).save(INPUTS / f'{n}-norm-dn-sq.png')

ims = [Image.open(INPUTS / f'{n}.png').convert('RGBA')
       for n in ['front-norm-sq', 'front-norm-dn-sq', 'side-lock-norm-sq', 'side-lock-norm-dn-sq']]
sheet = Image.new('RGBA', (2048, 512), 'white')
for i, im in enumerate(ims):
    sheet.alpha_composite(im.resize((512, 512)), (i * 512, 0))
sheet.convert('RGB').save(INPUTS / '_dn_check.jpg')
print('wrote', INPUTS)
