"""The bag's true proportions, from the photos: how much to stretch the AI shape's height and depth
(relative to its width) so that all three photo cameras see the outline best.

    python tools/fit_proportions.py   (then tools/fit_cameras.py uses the result)

For each candidate (height, depth) scale, the shape is scaled about its centre and the three cameras
(from media/3d/cameras.json) are re-fitted briefly; the mean outline overlap decides. Writes
"shape_scale" into media/3d/cameras.json. The retailers' dimensions disagree (24x14x6, 25x15.5x6.5,
26x17x7 cm), so the photos are the better witness.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.optimize import minimize

import fit_cameras as fc

ROOT = Path(__file__).resolve().parent.parent


def refit(mesh, name, cam, mask_small, iters=70):
    pts3 = np.array([fc.shape_point(mesh, spec) for spec, _ in fc.KEYPOINTS[name]])
    pts2 = np.array([px for _, px in fc.KEYPOINTS[name]], float)

    def loss(p):
        sil = fc.silhouette(mesh, p[:3], p[3:6], np.exp(p[6]))
        iou = (sil & mask_small).sum() / max(1, (sil | mask_small).sum())
        err = np.abs(fc.project(pts3, p[:3], p[3:6], np.exp(p[6])) - pts2).mean()
        return (1 - iou) + 0.002 * err

    p0 = np.concatenate([cam['rvec'], cam['tvec'], [np.log(cam['f'])]])
    steps = np.diag([0.02, 0.02, 0.02, 0.03, 0.03, 0.1, 0.03])
    res = minimize(loss, p0, method='Nelder-Mead',
                   options={'maxiter': iters, 'initial_simplex': np.vstack([p0, p0 + steps])})
    sil = fc.silhouette(mesh, res.x[:3], res.x[3:6], np.exp(res.x[6]))
    return (sil & mask_small).sum() / max(1, (sil | mask_small).sum())


def main():
    base = fc.load_shape(10_000, scaled=False)
    centre = fc.load_shape(scaled=False).bounds.mean(0)  # the 30k-face shape's, as everywhere else
    data = json.loads((ROOT / 'media' / '3d' / 'cameras.json').read_text())
    masks = {}
    for name in data['cameras']:
        mask = np.array(Image.open(fc.PHOTOS / f'{name}.png'))[:, :, 3] > 128
        masks[name] = np.array(Image.fromarray(mask.astype(np.uint8) * 255).resize((fc.W // 2, fc.H // 2))) > 128

    def score(sy, sz):
        mesh = base.copy()
        mesh.vertices = (mesh.vertices - centre) * [1, sy, sz] + centre
        ious = [refit(mesh, n, data['cameras'][n], masks[n]) for n in ('back', 'front', 'side')]
        print(f'height x{sy:.2f} depth x{sz:.2f}: ' + ' '.join(f'{i:.3f}' for i in ious) + f'  mean {np.mean(ious):.4f}',
              flush=True)
        return float(np.mean(ious))

    # Depth first (the side photo pins it), then height at the best depth.
    depth = max((score(1.0, sz), sz) for sz in (0.90, 0.96, 1.0, 1.04, 1.08))[1]
    best = max((score(sy, depth), sy) for sy in (0.96, 1.0, 1.04, 1.08))
    print('best height', best[1], 'depth', depth, 'mean iou', best[0])
    data['shape_scale'] = [1.0, best[1], depth]
    data['shape_centre'] = centre.tolist()
    (ROOT / 'media' / '3d' / 'cameras.json').write_text(json.dumps(data, indent=1), newline='\n')


if __name__ == '__main__':
    main()
