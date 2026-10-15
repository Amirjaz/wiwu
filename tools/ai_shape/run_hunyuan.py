"""AI shape from photos: a Hunyuan3D Space on Hugging Face through gradio_client (free ZeroGPU quota,
queues when busy; one run took about 50 minutes on 2026-10-14).

    python tools/ai_shape/run_hunyuan.py SPACE NAME STEPS OCTREE [image=PATH] [front=PATH] [back=PATH] [left=PATH] [right=PATH]

Writes media/3d/ai/NAME.glb, a shape with no texture (the textured generators were unusable). The hero's
shape is hunyuan2mv-shape-3view-denoised.glb: SPACE tencent/Hunyuan3D-2mv, from front-norm-dn-sq.png,
back-norm-sq.png and side-lock-norm-dn-sq.png (preprocess.py, then denoise.py). That run's exact
arguments (steps, octree resolution, which side slot the lock-end photo went in) weren't recorded. A new
shape must come out the way tools/fit_cameras.py expects (front +z, lock end -x, about 2 wide), and its
KEYPOINTS there must be checked again before the cameras, details and model are rebuilt on it.
"""
import json
import shutil
import sys
import time
from pathlib import Path

from gradio_client import Client, handle_file

OUT = Path(__file__).resolve().parents[2] / 'media' / '3d' / 'ai'
space, name, steps, octree = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
kv = dict(a.split('=', 1) for a in sys.argv[5:])
f = lambda k: handle_file(kv[k]) if k in kv else None  # noqa: E731

t0 = time.time()
c = Client(space, verbose=False)
# image, front, back, left, right, steps, guidance, seed, octree resolution, remove background,
# number of chunks, randomize seed
args = [f('image'), f('front'), f('back'), f('left'), f('right'),
        steps, 5.0, 1234, octree, False, 200000, False]
if '2mv' in space or space.endswith('Hunyuan3D-2'):
    args = [None] + args  # these Spaces take a caption first
r = c.predict(*args, api_name='/shape_generation')
print(f'done {time.time() - t0:.0f}s')
file_out, html, stats, seed = r
print(json.dumps(stats, indent=1)[:1500])
src = file_out if isinstance(file_out, str) else file_out.get('path') or file_out.get('value')
dst = OUT / f'{name}.glb'
shutil.copy(src, dst)
print('saved', dst, dst.stat().st_size)
