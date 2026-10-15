"""Polishes the three photo cameras for the shape's fitted proportions, starting both from the current
cameras and from a second set (e.g. an earlier fit, which may sit in a better basin), keeping the best.

    python tools/refine_cameras.py [other-cameras.json]

Front and back weigh the outline and the marked features; the side only its outline (its features sit
on the AI's own lock module, which is lower and smaller than the real one, now modelled from the photo).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.optimize import minimize

import fit_cameras as fc

ROOT = Path(__file__).resolve().parent.parent
FEATURE_WEIGHT = {'back': 0.002, 'front': 0.002, 'side': 0.0}


def main():
    path = ROOT / 'media' / '3d' / 'cameras.json'
    data = json.loads(path.read_text())
    others = json.loads(Path(sys.argv[1]).read_text())['cameras'] if len(sys.argv) > 1 else {}
    mesh = fc.load_shape()
    for name, cam in data['cameras'].items():
        mask = np.array(Image.open(fc.PHOTOS / f'{name}.png'))[:, :, 3] > 128
        small = np.array(Image.fromarray(mask.astype(np.uint8) * 255).resize((fc.W // 2, fc.H // 2))) > 128
        pts3 = np.array([fc.shape_point(mesh, spec) for spec, _ in fc.KEYPOINTS[name]])
        pts2 = np.array([px for _, px in fc.KEYPOINTS[name]], float)

        def stats(p):
            sil = fc.silhouette(mesh, p[:3], p[3:6], np.exp(p[6]))
            iou = (sil & small).sum() / max(1, (sil | small).sum())
            err = np.abs(fc.project(pts3, p[:3], p[3:6], np.exp(p[6])) - pts2).mean()
            return iou, err

        def loss(p):
            iou, err = stats(p)
            return (1 - iou) + FEATURE_WEIGHT[name] * err

        best = None
        starts = [cam] + ([others[name]] if name in others else [])
        for start in starts:
            p0 = np.concatenate([start['rvec'], start['tvec'], [np.log(start['f'])]])
            steps = np.diag([0.02, 0.02, 0.02, 0.03, 0.03, 0.1, 0.03])
            res = minimize(loss, p0, method='Nelder-Mead',
                           options={'maxiter': 600, 'xatol': 1e-5, 'fatol': 1e-6,
                                    'initial_simplex': np.vstack([p0, p0 + steps])})
            iou, err = stats(res.x)
            print(f'  {name}: from f={start["f"]:.0f} -> iou {iou:.3f}, features {err:.1f} px', flush=True)
            if best is None or res.fun < best[0]:
                best = (res.fun, res.x, iou, err)
        _, x, iou, err = best
        cam.update({'rvec': x[:3].tolist(), 'tvec': x[3:6].tolist(), 'f': float(np.exp(x[6])), 'iou': iou,
                    'kp_px': err, 'keypoints3d': pts3.tolist(), 'keypoints2d': pts2.tolist()})
        cam.pop('note', None)
        fc.overlay(mesh, name, cam)
    path.write_text(json.dumps(data, indent=1), newline='\n')


if __name__ == '__main__':
    main()
