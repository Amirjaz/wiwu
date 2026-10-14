"""Where the phone was for each source photo, relative to the 3D shape: media/3d/cameras.json.

    python tools/fit_cameras.py   (numpy, scipy, opencv-python-headless, trimesh, fast-simplification)

For each photo: a few features marked by hand on both the photo and the shape (snap, pocket pull,
logo plate corners, lock module, ...) give a first pose with solvePnP; then the pose and focal length
are refined so the shape's outline matches the photo's bag mask (media/3d/photos, tools/photo_masks.py)
while the marked features stay close. Overlays for checking go to media/3d/fit/.
Shape coordinates are the AI source's (media/3d/ai/hunyuan2mv-shape-3view-denoised.glb): width ~1.97,
front +z, lock end -x. Photo pixels are in the 960 x 1280 originals.
"""
import json
from pathlib import Path

import cv2
import fast_simplification
import numpy as np
import trimesh
from PIL import Image
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent
SHAPE = ROOT / 'media' / '3d' / 'ai' / 'hunyuan2mv-shape-3view-denoised.glb'
PHOTOS = ROOT / 'media' / '3d' / 'photos'
OUT = ROOT / 'media' / '3d'
W, H = 960, 1280

# (shape point, photo pixel). A shape point is found by casting a ray at the surface:
# ('back', x, y) along +z from behind, ('front', x, y) along -z, ('end', y, z) along +x from the lock end.
KEYPOINTS = {
    'back': [
        (('back', -0.641, -0.331), (719, 730)),  # strap snap
        (('back', -0.725, 0.281), (744, 466)),  # pocket zip pull, top
        (('back', 0.619, 0.2775), (147, 507)),  # pocket, top left corner
        (('back', 0.689, -0.25), (162, 760)),  # strap, top left corner
        (('back', -0.694, -0.331), (788, 718)),  # strap, right end
    ],
    'front': [
        (('front', 0.446, -0.252), (761, 829)),  # logo plate corners
        (('front', 0.596, -0.234), (818, 820)),
        (('front', 0.635, -0.381), (826, 872)),
        (('front', 0.476, -0.399), (770, 882)),
    ],
    'side': [
        (('end', -0.31, -0.0105), (407, 841)),  # fingerprint sensor centre
        (('end', -0.05, -0.0105), (405, 712)),  # lock module, top
        (('end', -0.41, -0.0105), (405, 890)),  # lock module, bottom
        (('end', -0.30, -0.0875), (343, 830)),  # lock module, back edge
        (('end', -0.30, 0.0665), (468, 830)),  # lock module, front edge
    ],
}
# Rough start: the camera's position as (azimuth from +z toward +x, elevation) in degrees.
START = {'back': (200, 30), 'front': (8, 12), 'side': (-80, 6)}


def load_shape(faces=30_000):
    scene = trimesh.load(SHAPE)
    mesh = trimesh.util.concatenate(list(scene.dump())) if isinstance(scene, trimesh.Scene) else scene
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.merge_vertices()
    v, f = fast_simplification.simplify(mesh.vertices.astype(np.float32), mesh.faces.astype(np.int32),
                                        1 - faces / len(mesh.faces))
    return trimesh.Trimesh(v, f, process=True)


def raycast(mesh, origin, direction):
    """First hit of a ray (Möller–Trumbore over all faces)."""
    tri = mesh.triangles
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    p = np.cross(direction, e2)
    det = (e1 * p).sum(1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = origin - tri[:, 0]
    u = (s * p).sum(1) * inv
    q = np.cross(s, e1)
    v = (q * direction).sum(1) * inv
    t = (q * e2).sum(1) * inv
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
    if not hit.any():
        raise ValueError(f'no hit from {origin}')
    return origin + direction * t[hit].min()


def shape_point(mesh, spec):
    kind, a, b = spec
    if kind == 'back':
        return raycast(mesh, np.array([a, b, -5.0]), np.array([0, 0, 1.0]))
    if kind == 'front':
        return raycast(mesh, np.array([a, b, 5.0]), np.array([0, 0, -1.0]))
    return raycast(mesh, np.array([-5.0, a, b]), np.array([1.0, 0, 0]))


def look_at_pose(centre, az, el, dist):
    """OpenCV rvec/tvec for a camera at (az, el, dist) around centre, looking at it, y up."""
    a, e = np.radians(az), np.radians(el)
    eye = centre + dist * np.array([np.cos(e) * np.sin(a), np.sin(e), np.cos(e) * np.cos(a)])
    forward = (centre - eye) / np.linalg.norm(centre - eye)
    right = np.cross(forward, [0, 1, 0])
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    R = np.stack([right, down, forward])  # rows: camera x (right), y (down), z (forward)
    rvec, _ = cv2.Rodrigues(R)
    return rvec.ravel(), -R @ eye


def project(points, rvec, tvec, f):
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]])
    px, _ = cv2.projectPoints(points.astype(np.float64), rvec, tvec, K, None)
    return px.reshape(-1, 2)


def silhouette(mesh, rvec, tvec, f, scale=0.5):
    px = project(mesh.vertices, rvec, tvec, f) * scale
    img = np.zeros((int(H * scale), int(W * scale)), np.uint8)
    tris = np.round(px[mesh.faces] * 16).astype(np.int32)
    for t in tris:
        cv2.fillConvexPoly(img, t, 1, lineType=cv2.LINE_8, shift=4)
    return img.astype(bool)


def fit_view(mesh, name, mask_small):
    pts3 = np.array([shape_point(mesh, spec) for spec, _ in KEYPOINTS[name]])
    pts2 = np.array([px for _, px in KEYPOINTS[name]], float)
    centre = mesh.bounds.mean(0)

    best = None
    for f in np.arange(700, 2600, 50):
        K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]])
        for dist in (2.5, 4.0, 6.0):
            r0, t0 = look_at_pose(centre, *START[name], dist * f / 1000)
            ok, r, t = cv2.solvePnP(pts3, pts2, K, None, r0.copy(), t0.copy(), useExtrinsicGuess=True,
                                    flags=cv2.SOLVEPNP_ITERATIVE)
            if not ok or (cv2.Rodrigues(r)[0] @ centre + t.ravel())[2] <= 0:
                continue
            err = np.abs(project(pts3, r.ravel(), t.ravel(), f) - pts2).mean()
            sil = silhouette(mesh, r.ravel(), t.ravel(), f)
            iou = (sil & mask_small).sum() / max(1, (sil | mask_small).sum())
            score = (1 - iou) + 0.004 * err
            if best is None or score < best[0]:
                best = (score, f, r.ravel(), t.ravel(), iou, err)
    _, f, r, t, iou, err = best
    print(f'  {name}: start f={f:.0f} iou={iou:.3f} kp={err:.1f}px')

    def loss(p):
        rv, tv, ff = p[:3], p[3:6], np.exp(p[6])
        sil = silhouette(mesh, rv, tv, ff)
        iou = (sil & mask_small).sum() / max(1, (sil | mask_small).sum())
        e = np.abs(project(pts3, rv, tv, ff) - pts2).mean()
        return (1 - iou) + 0.002 * e

    p0 = np.concatenate([r, t, [np.log(f)]])
    steps = np.diag([0.04, 0.04, 0.04, 0.05, 0.05, 0.2, 0.05])  # rotation (rad), shift, distance, log focal
    res = minimize(loss, p0, method='Nelder-Mead',
                   options={'maxiter': 900, 'xatol': 1e-4, 'fatol': 1e-5, 'initial_simplex': np.vstack([p0, p0 + steps])})
    r, t, f = res.x[:3], res.x[3:6], float(np.exp(res.x[6]))
    sil = silhouette(mesh, r, t, f)
    iou = (sil & mask_small).sum() / max(1, (sil | mask_small).sum())
    err = np.abs(project(pts3, r, t, f) - pts2).mean()
    print(f'  {name}: fitted f={f:.0f} iou={iou:.3f} kp={err:.1f}px ({res.nfev} renders)')
    return {'f': f, 'rvec': r.tolist(), 'tvec': t.tolist(), 'iou': iou, 'kp_px': err,
            'keypoints3d': pts3.tolist(), 'keypoints2d': pts2.tolist()}


def overlay(mesh, name, cam):
    photo = Image.open(PHOTOS / f'{name}.png').convert('RGB')
    img = np.array(photo)
    sil = silhouette(mesh, np.array(cam['rvec']), np.array(cam['tvec']), cam['f'], scale=1.0).astype(np.uint8)
    contours, _ = cv2.findContours(sil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(img, contours, -1, (0, 255, 255), 2)
    mask = np.array(Image.open(PHOTOS / f'{name}.png'))[:, :, 3] > 128
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(img, contours, -1, (255, 0, 255), 2)
    for p3, p2 in zip(project(np.array(cam['keypoints3d']), np.array(cam['rvec']), np.array(cam['tvec']), cam['f']),
                      cam['keypoints2d']):
        cv2.circle(img, tuple(int(v) for v in p2), 7, (255, 60, 60), 2)
        cv2.circle(img, tuple(int(v) for v in p3), 4, (60, 255, 60), -1)
    (OUT / 'fit').mkdir(exist_ok=True)
    Image.fromarray(img).save(OUT / 'fit' / f'{name}.jpg', quality=88)


def main():
    mesh = load_shape()
    cams = {}
    for name in ('back', 'front', 'side'):
        mask = np.array(Image.open(PHOTOS / f'{name}.png'))[:, :, 3] > 128
        mask_small = np.array(Image.fromarray(mask.astype(np.uint8) * 255).resize((W // 2, H // 2))) > 128
        cams[name] = fit_view(mesh, name, mask_small)
        overlay(mesh, name, cams[name])
    (OUT / 'cameras.json').write_text(json.dumps({'width': W, 'height': H, 'shape': SHAPE.name, 'cameras': cams},
                                                 indent=1))


if __name__ == '__main__':
    main()
