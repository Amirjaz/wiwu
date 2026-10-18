"""Measurements of the bag's detailed parts, taken from the photos, so the page can model them crisply
instead of relying on the AI shape (which blurs them) and the photos' pixels (too few up close).

    python tools/details.py   (after fit_cameras.py; build_model.py runs it and stores the result)

- The lock module (side photo): its outline and features (cap with the pull's slot and latch, the
  groove, the status light's slit, the sensor's copper frame and glass), traced in photo pixels and
  projected through the fitted camera onto the module's face plane. The plane is the leather around
  the module, moved out by the module's thickness.
- The zipper: its centre line along the shape's seam, from the lock module's cap, over the top, down
  the far end to the pull tab; resampled every millimetre with the surface normal.
- The far end's ring and pull tab (front and back photos both show them): triangulated.
- The brand plate (front photo): its corners projected through the fitted camera onto the leather
  around it, moved out by the plate's thickness. build_model.py measures it on the finished front
  (logo_plate), since pulling the front taut moves the leather under it.
All results are in the shape's coordinates (fitted proportions); build_model.py converts them.
"""
import json
from pathlib import Path

import cv2
import numpy as np

import fit_cameras as fc

ROOT = Path(__file__).resolve().parent.parent
MODULE_THICKNESS = 0.035  # shape units (~4.5 mm): how far the lock module stands out of the leather

# Side photo, traced at 4x zoom (pixels in the 960 x 1280 original).
MODULE = {
    # The module's outline, clockwise from the top of the cap.
    'outline': [(405, 707), (430, 709), (450, 715), (461, 726), (464, 742), (469, 752), (470, 790), (469, 840),
                (467, 872), (460, 886), (447, 893), (405, 895), (363, 893), (350, 886), (344, 872), (342, 840),
                (342, 790), (343, 752), (348, 742), (351, 726), (361, 715), (380, 709)],
    'cap_bottom': 771,  # the groove under the cap
    'cap_sides': (351, 462),
    'slot': (381, 724, 426, 745),  # x0, y0, x1, y1
    'latch': (381, 745, 428, 757),
    'led': (386, 793, 420, 801),
    'frame': (380, 817, 432, 864),
    'glass': (388, 824, 425, 857),
}
# Far end: the same physical points in the front and the back photo. Only points that stick out past
# the bag in both photos are the same point in both (where the tab meets each photo's outline isn't).
FAR_END = {
    'ring': ((905, 538), (50, 467)),
    'tab_mid': ((937, 636), (25, 581)),
    'tab_tip': ((953, 634), (12, 580)),
}
FAR_FACE_X = 0.925  # where the tab enters the far end (shape units)
# The brand plate's corners in the front photo, clockwise from the top left, traced at 6x zoom.
PLATE = [(762.5, 827.5), (818.5, 819.5), (826, 873), (770, 882.5)]
PLATE_THICKNESS = 0.007  # shape units (~0.9 mm)


def cameras():
    data = json.loads((ROOT / 'media' / '3d' / 'cameras.json').read_text())
    out = {}
    for name, cam in data['cameras'].items():
        R, _ = cv2.Rodrigues(np.array(cam['rvec']))
        t, f = np.array(cam['tvec']), cam['f']
        K = np.array([[f, 0, data['width'] / 2], [0, f, data['height'] / 2], [0, 0, 1.0]])
        out[name] = {'K': K, 'R': R, 't': t, 'eye': -R.T @ t}
    return out


def ray(cam, px):
    d = cam['R'].T @ np.linalg.solve(cam['K'], np.array([px[0], px[1], 1.0]))
    return cam['eye'], d / np.linalg.norm(d)


def hit_plane(origin, direction, point, normal):
    return origin + direction * ((point - origin) @ normal) / (direction @ normal)


def triangulate(cam_a, px_a, cam_b, px_b):
    Pa = cam_a['K'] @ np.hstack([cam_a['R'], cam_a['t'][:, None]])
    Pb = cam_b['K'] @ np.hstack([cam_b['R'], cam_b['t'][:, None]])
    X = cv2.triangulatePoints(Pa, Pb, np.array(px_a, float).reshape(2, 1), np.array(px_b, float).reshape(2, 1))
    return (X[:3] / X[3]).ravel()


def lock_module(mesh, cam):
    """The module's face plane and its features in plane coordinates (u toward the front, v up)."""
    centre_px = (405, 800)
    o, d = ray(cam, centre_px)
    on_module = fc.raycast(mesh, o, d)
    # The leather around the module: vertices on the lock end near the module but outside its outline
    # (as the side camera sees them).
    v = mesh.vertices
    cam_v = v @ cam['R'].T + cam['t']
    px = (cam_v @ cam['K'].T)[:, :2] / cam_v[:, 2:3]
    outline = np.array(MODULE['outline'], np.float32)
    dist = np.array([cv2.pointPolygonTest(outline, (float(x), float(y)), True) for x, y in px])
    near = (np.linalg.norm(v - on_module, axis=1) < 0.25) & (dist < -6) & (dist > -40)
    near &= (v - on_module) @ (cam['eye'] - on_module) > -0.05  # the side facing the camera
    ring = v[near]
    centroid = ring.mean(0)
    _, _, vt = np.linalg.svd(ring - centroid)
    normal = vt[2]
    if normal @ (cam['eye'] - centroid) < 0:
        normal = -normal
    face_point = centroid + normal * MODULE_THICKNESS
    up = np.array([0, 1.0, 0]) - normal * normal[1]
    up /= np.linalg.norm(up)
    across = np.cross(up, normal)  # right-handed u, v, n; on the lock end u points to the front (+z)
    assert across[2] > 0, 'unexpected module orientation'

    def to_plane(p):
        o, d = ray(cam, p)
        q = hit_plane(o, d, face_point, normal)
        return [(q - face_point) @ across, (q - face_point) @ up]

    shape_centre = np.array(to_plane(centre_px))
    origin = face_point + across * shape_centre[0] + up * shape_centre[1]

    def plane(p):
        q = np.array(to_plane(p)) - shape_centre
        return q.round(5).tolist()

    def rect(box):
        x0, y0, x1, y1 = box
        a, b = plane((x0, y1)), plane((x1, y0))  # bottom-left, top-right
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]

    return {
        'origin': origin.tolist(), 'u': across.tolist(), 'v': up.tolist(), 'n': normal.tolist(),
        'thickness': MODULE_THICKNESS,
        'outline': [plane(p) for p in MODULE['outline']],
        'capBottom': plane((405, MODULE['cap_bottom']))[1],
        'capSides': [plane((MODULE['cap_sides'][0], 740))[0], plane((MODULE['cap_sides'][1], 740))[0]],
        'slot': rect(MODULE['slot']), 'latch': rect(MODULE['latch']), 'led': rect(MODULE['led']),
        'frame': rect(MODULE['frame']), 'glass': rect(MODULE['glass']),
    }


def logo_plate(mesh, cam):
    """The brand plate's face: its centre, plane (u along the bag, v up, n out) and size. The plane is
    fitted to the leather under and just around the plate; the plate is taken square to the bag (the
    photo's slight tilt is the camera fit's, not the plate's)."""
    corners = np.array(PLATE, np.float32)
    o, d = ray(cam, corners.mean(0))
    on_plate = fc.raycast(mesh, o, d)
    v = mesh.vertices
    close = np.nonzero((np.linalg.norm(v - on_plate, axis=1) < 0.2) & ((v - on_plate) @ (cam['eye'] - on_plate) > -0.05))[0]
    cam_v = v[close] @ cam['R'].T + cam['t']
    px = (cam_v @ cam['K'].T)[:, :2] / cam_v[:, 2:3]
    dist = np.array([cv2.pointPolygonTest(corners, (float(x), float(y)), True) for x, y in px])
    ring = v[close[dist > -12]]  # the footprint and about 3 mm around it
    centroid = ring.mean(0)
    _, _, vt = np.linalg.svd(ring - centroid)
    normal = vt[2] if vt[2] @ (cam['eye'] - centroid) > 0 else -vt[2]
    face_point = centroid + normal * PLATE_THICKNESS
    across = np.array([1.0, 0, 0]) - normal * normal[0]
    across /= np.linalg.norm(across)
    up = np.cross(normal, across)

    def to_plane(p):
        o, d = ray(cam, p)
        q = hit_plane(o, d, face_point, normal)
        return np.array([(q - face_point) @ across, (q - face_point) @ up])

    tl, tr, br, bl = (to_plane(p) for p in PLATE)
    centre = (tl + tr + br + bl) / 4
    width = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    height = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    tilt = np.degrees(np.arctan2(*(tr - tl)[::-1]))
    return {
        'origin': (face_point + across * centre[0] + up * centre[1]).tolist(),
        'u': across.tolist(), 'v': up.tolist(), 'n': normal.tolist(),
        'size': [float(width), float(height)], 'thickness': PLATE_THICKNESS, 'tilt': float(tilt),
    }


def surface(mesh, origin, direction):
    """Hit point and face normal. A ray exactly along an edge can slip between two triangles; then it's
    retried a hair to the side."""
    tri = mesh.triangles
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    p = np.cross(direction, e2)
    det = (e1 * p).sum(1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    q_base = np.cross(origin - tri[:, 0], e1)
    for jitter in (0.0, 1e-4, -1e-4, 3e-4):
        o = origin + np.cross(direction, [0.577, 0.577, 0.577]) * jitter
        s = o - tri[:, 0]
        u = (s * p).sum(1) * inv
        q = np.cross(s, e1) if jitter else q_base
        v = (q * direction).sum(1) * inv
        t = (q * e2).sum(1) * inv
        hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 0)
        if hit.any():
            i = np.nonzero(hit)[0][np.argmin(t[hit])]
            return o + direction * t[i], mesh.face_normals[i]
    raise ValueError(f'ray from {origin} misses the shape')


def zipper_path(mesh, cap_top, tab_root, step=0.008, top_end=0.80):
    """Seam centre line: up the lock end from the module's cap, over the top, round the far corner and
    down to the pull tab. The AI's far end has a recess (for a bracket it invented) where rays find no
    surface, so past top_end the path is a smooth curve to the tab, whose position the photos give."""
    lo, hi = mesh.bounds
    z_seam = (lo[2] + hi[2]) / 2
    pts = []

    def cast(origin, direction):
        try:
            pts.append(surface(mesh, np.array(origin, float), np.array(direction, float)))
        except ValueError:
            pass

    for y in np.arange(cap_top[1], hi[1] - 0.06, step):  # lock end, upward
        cast([lo[0] - 1, y, z_seam], [1.0, 0, 0])
    for x in np.arange(lo[0] + 0.05, top_end, step):  # over the top
        cast([x, hi[1] + 1, z_seam], [0, -1.0, 0])
    a, c = pts[-1][0], np.array(tab_root)
    control = np.array([c[0], a[1], (a[2] + c[2]) / 2])
    n = max(4, int(np.linalg.norm(c - a) / step) * 2)
    for t in np.linspace(0, 1, n)[1:]:
        point = (1 - t) ** 2 * a + 2 * (1 - t) * t * control + t ** 2 * c
        normal = (1 - t) * np.array([0, 1.0, 0]) + t * np.array([1.0, 0, 0])
        pts.append((point, normal / np.linalg.norm(normal)))
    P = np.array([p for p, _ in pts])
    N = np.array([n for _, n in pts])
    # Corners: the end rays and the top rays overlap near each corner; keep the path monotonic by
    # ordering along the walk and dropping points that step backwards.
    keep = [0]
    for i in range(1, len(P)):
        if np.linalg.norm(P[i] - P[keep[-1]]) > step * 0.5:
            keep.append(i)
    P, N = P[keep], N[keep]
    # Smooth (the AI seam is lumpy) and resample evenly.
    for _ in range(6):
        P[1:-1] = (P[:-2] + 2 * P[1:-1] + P[2:]) / 4
        N[1:-1] = (N[:-2] + 2 * N[1:-1] + N[2:]) / 4
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return P, N


def measure():
    """Everything, in the shape's coordinates (fitted proportions)."""
    mesh = fc.load_shape(60_000)
    cams = cameras()
    module = lock_module(mesh, cams['side'])
    far = {k: triangulate(cams['front'], a, cams['back'], b) for k, (a, b) in FAR_END.items()}
    along = far['tab_tip'] - far['tab_mid']
    along /= np.linalg.norm(along)
    far['tab_root'] = far['tab_tip'] + along * (FAR_FACE_X - far['tab_tip'][0]) / along[0]
    del far['tab_mid']
    o = np.array(module['origin'])
    cap_top = o + np.array(module['v']) * max(p[1] for p in module['outline'])
    path, normals = zipper_path(mesh, cap_top, far['tab_root'])
    return mesh, {
        'module': module,
        'farEnd': {k: v.tolist() for k, v in far.items()},
        'zipper': {'points': path.tolist(), 'normals': normals.tolist()},
    }


def main():
    mesh, out = measure()
    module, far = out['module'], {k: np.array(v) for k, v in out['farEnd'].items()}
    path = np.array(out['zipper']['points'])
    (ROOT / 'media' / '3d' / 'details.json').write_text(json.dumps(out), newline='\n')
    lo, hi = mesh.bounds
    print('shape bounds', lo.round(3), hi.round(3))
    print('module origin', np.round(module['origin'], 3), 'normal', np.round(module['n'], 3))
    print('module size', np.round(np.ptp(np.array(module['outline']), 0), 4))
    print('far end', {k: v.round(3) for k, v in far.items()})
    print('zipper', len(path), 'points, from', path[0].round(3), 'to', path[-1].round(3))


if __name__ == '__main__':
    main()
