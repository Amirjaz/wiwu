"""The hero's 3D model (frontend/public/models/alpha*.glb + .json) from the AI shape and the three photos.

    python tools/build_model.py   (numpy, scipy, opencv-python-headless, trimesh, fast-simplification, xatlas)

Steps, all from files in media/:
1. The shape: media/3d/ai/hunyuan2mv-shape-3view-denoised.glb, made by Hunyuan3D-2mv from the front,
   back and side photos (2026-10-14). Its zero-area triangles (about half) are dropped, the rest welded,
   decimated for the web (desktop and phone versions) and lightly smoothed.
2. Its surface is unwrapped into a texture atlas (xatlas), and the three photos are projected onto it
   (tools/bake.py, with the cameras from tools/fit_cameras.py and the masks from tools/photo_masks.py):
   the front, back and lock end look exactly like the photos. The bottom and the far end, which no
   photo shows, get the leather's colour.
3. Faces are sorted into the parts the page gives different surface behaviour (by where they are on
   the bag, read off orthographic views of the source): PU leather, zipper tape, zipper teeth and the
   gunmetal hardware (lock module, logo plate, zipper slider and pulls, the strap's snap).
4. It is put at real size (25 x 15.5 x 6.5 cm; the AI made it a little short and thick), resting on
   y = 0, front facing +z, the lock end at -x, and compressed (meshopt, JPEG texture).
The .json next to each model holds what the page needs besides the mesh: where the fingerprint
sensor's status light is (from the side photo), and how often the leather grain repeats.
Coordinates below are in the source's units (width about 1.97).
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import fast_simplification
import numpy as np
import trimesh
import xatlas
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bake  # noqa: E402  (tools/bake.py)

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'media' / '3d' / 'ai' / 'hunyuan2mv-shape-3view-denoised.glb'
OUT = ROOT / 'frontend' / 'public' / 'models'
SIZE_M = np.array([0.25, 0.155, 0.065])  # width, height, depth of the body (pulls stick out)
BODY_X = (-0.98, 0.94)  # the body's width in source units, without the zipper pull tab
GRAIN_TILE_M = 0.04  # one tile of the page's leather grain covers 4 cm
LED_PIXEL = (402, 797)  # the sensor's status light in the side photo


def load():
    scene = trimesh.load(SOURCE)
    mesh = trimesh.util.concatenate(list(scene.dump())) if isinstance(scene, trimesh.Scene) else scene
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.merge_vertices()
    mesh.remove_unreferenced_vertices()
    return mesh


def decimate(mesh, faces):
    ratio = 1 - faces / len(mesh.faces)
    v, f = fast_simplification.simplify(mesh.vertices.astype(np.float32), mesh.faces.astype(np.int32), ratio)
    out = trimesh.Trimesh(v, f, process=True)
    trimesh.smoothing.filter_taubin(out, lamb=0.5, nu=-0.53, iterations=4)  # soften the front's dents
    return out


def in_quad(p, quad):
    """Points (n, 2) inside a convex quad given clockwise or counter-clockwise."""
    crosses = []
    for i in range(4):
        a, b = np.array(quad[i]), np.array(quad[(i + 1) % 4])
        crosses.append((b[0] - a[0]) * (p[:, 1] - a[1]) - (b[1] - a[1]) * (p[:, 0] - a[0]))
    crosses = np.array(crosses)
    return (crosses >= 0).all(0) | (crosses <= 0).all(0)


def parts(centres, normals):
    """Material name per face, from face centres and normals (source units)."""
    c, n = centres, normals
    x, y, z = c[:, 0], c[:, 1], c[:, 2]
    part = np.full(len(c), 'leather', dtype=object)

    on_top = (y > 0.42) & (np.abs(n[:, 2]) < 0.75)
    lock_end_band = (x < -0.9) & (y > -0.06) & (np.abs(n[:, 2]) < 0.75)
    far_end_band = (x > 0.88) & (y > 0.4) & (np.abs(n[:, 2]) < 0.75)
    zipper = on_top | lock_end_band | far_end_band
    part[zipper & (np.abs(z) < 0.1)] = 'tape'
    part[zipper & (np.abs(z) < 0.032)] = 'teeth'

    metal = np.zeros(len(c), bool)
    # Lock module on the -x end (with its upper hinge where the pull docks).
    metal |= (x < -0.9) & (n[:, 0] < -0.2) & (z > -0.095) & (z < 0.075) & (y > -0.415) & (y < -0.04)
    # Logo plate, front lower right (a slightly tilted square).
    plate = [(0.446, -0.252), (0.596, -0.234), (0.635, -0.381), (0.476, -0.399)]
    metal |= (z > 0.12) & (n[:, 2] > 0.3) & in_quad(c[:, :2], plate)
    # Zipper slider bracket and pull on the +x end, the pull tab beyond it.
    metal |= (x > 0.9) & (z > -0.1) & (z < 0.1) & (y > 0.11) & (y < 0.41)
    metal |= x > 0.95
    # The main zipper's pull hanging on the lock end.
    metal |= (x < -0.88) & (z < -0.14) & (y > 0.07) & (y < 0.24)
    # Back pocket's zip pull and the strap's snap.
    metal |= (z < -0.2) & (x > -0.775) & (x < -0.675) & (y > 0.06) & (y < 0.29)
    metal |= (z < -0.25) & (np.hypot(x + 0.641, y + 0.331) < 0.035)
    part[metal] = 'metal'
    return part


def real_size_transform(bounds):
    """(scale, centre): real = (source - centre) * scale."""
    lo, hi = bounds
    scale = np.array([SIZE_M[0] / (BODY_X[1] - BODY_X[0]), SIZE_M[1] / (hi[1] - lo[1]), SIZE_M[2] / (hi[2] - lo[2])])
    centre = np.array([(BODY_X[0] + BODY_X[1]) / 2, lo[1], (lo[2] + hi[2]) / 2])
    return scale, centre


def unwrap(mesh, size):
    atlas = xatlas.Atlas()
    atlas.add_mesh(mesh.vertices.astype(np.float32), mesh.faces.astype(np.uint32))
    pack = xatlas.PackOptions()
    pack.resolution = size
    pack.padding = 4
    pack.bilinear = True
    atlas.generate(xatlas.ChartOptions(), pack)
    vmapping, faces, uvs = atlas[0]
    return vmapping, faces.astype(np.int64), uvs.astype(np.float64)


def led_position(mesh):
    """Where the side photo's status light is on the shape: the camera ray through it, hitting the mesh."""
    cams, width, height = bake.load_cameras()
    cam = cams['side']
    R, _ = cv2.Rodrigues(np.array(cam['rvec']))
    t, f = np.array(cam['tvec']), cam['f']
    eye = -R.T @ t
    ray = R.T @ np.array([(LED_PIXEL[0] - width / 2) / f, (LED_PIXEL[1] - height / 2) / f, 1.0])
    ray /= np.linalg.norm(ray)
    tri = mesh.triangles
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    p = np.cross(ray, e2)
    det = (e1 * p).sum(1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = eye - tri[:, 0]
    u = (s * p).sum(1) * inv
    q = np.cross(s, e1)
    v = (q * ray).sum(1) * inv
    dist = (q * e2).sum(1) * inv
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (dist > 0)
    if not hit.any():
        return None, None
    i = np.nonzero(hit)[0][np.argmin(dist[hit])]
    return eye + ray * dist[i], mesh.face_normals[i]


def build(name, faces, texture):
    print(f'{name}: {faces} faces, {texture}px texture')
    mesh = decimate(load(), faces)
    normals = mesh.vertex_normals.copy()
    vmapping, ufaces, uvs = unwrap(mesh, texture)
    verts = mesh.vertices[vmapping]
    vnorm = normals[vmapping]
    # xatlas keeps the triangle order, so the parts computed on the welded mesh still apply.
    assert len(ufaces) == len(mesh.faces) and np.allclose(verts[ufaces].mean(1), mesh.triangles_center, atol=1e-5)
    labels = parts(mesh.triangles_center, mesh.face_normals)

    print('  baking the photos')
    rgb, coverage = bake.bake(verts, vnorm, ufaces, uvs, texture)
    tex_path = OUT / f'{name}-texture.jpg'
    Image.fromarray(rgb).save(tex_path, quality=88, optimize=True, progressive=False)
    texture_image = Image.open(tex_path)  # trimesh keeps a JPEG a JPEG when embedding it
    texture_image.load()
    print(f'  photos cover {np.mean(coverage[coverage > 0] > 0.5):.0%} of the surface')

    scale, centre = real_size_transform(mesh.bounds)
    real = (verts - centre) * scale
    real_normals = vnorm / scale
    real_normals /= np.linalg.norm(real_normals, axis=1, keepdims=True)

    scene = trimesh.Scene()
    for part in ('leather', 'tape', 'teeth', 'metal'):
        idx = np.nonzero(labels == part)[0]
        sub_faces = ufaces[idx]
        used, inverse = np.unique(sub_faces.ravel(), return_inverse=True)
        sub = trimesh.Trimesh(real[used], inverse.reshape(-1, 3), vertex_normals=real_normals[used], process=False)
        material = trimesh.visual.material.PBRMaterial(name=part, baseColorTexture=texture_image,
                                                      metallicFactor=0.0, roughnessFactor=0.6)
        sub.visual = trimesh.visual.TextureVisuals(uv=uvs[used], material=material)
        scene.add_geometry(sub, node_name=part, geom_name=part)
        print(f'  {part}: {len(sub.faces)} faces')
    raw = OUT / f'{name}.raw.glb'
    scene.export(raw)
    tmp = OUT / f'{name}.dedup.glb'
    final = OUT / f'{name}.glb'
    run = dict(cwd=ROOT / 'frontend', check=True, shell=sys.platform == 'win32')
    subprocess.run(['npx', '--no-install', 'gltf-transform', 'dedup', str(raw), str(tmp)], **run)
    subprocess.run(['npx', '--no-install', 'gltf-transform', 'meshopt', str(tmp), str(final)], **run)
    raw.unlink()
    tmp.unlink()
    tex_path.unlink()

    # Sidecar: the status light and the grain's repeat (UV units are the atlas's; meters per UV unit
    # come from comparing edge lengths).
    led, led_normal = led_position(mesh)
    edges = ufaces[:, [0, 1]]
    world = np.linalg.norm(real[edges[:, 0]] - real[edges[:, 1]], axis=1)
    uvlen = np.linalg.norm(uvs[edges[:, 0]] - uvs[edges[:, 1]], axis=1)
    metres_per_uv = float(np.median(world[uvlen > 1e-6] / uvlen[uvlen > 1e-6]))
    side = {
        'grainRepeat': round(metres_per_uv / GRAIN_TILE_M, 2),
        'led': None if led is None else {
            'position': ((led - centre) * scale).round(5).tolist(),
            'normal': (lambda n: (n / np.linalg.norm(n)).round(4).tolist())(led_normal / scale),
        },
    }
    (OUT / f'{name}.json').write_text(json.dumps(side), newline='
')
    print(f'{final.name}: {final.stat().st_size / 1024:.0f} KB; {side}')


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    build('alpha', 90_000, 2048)
    build('alpha-mobile', 36_000, 1024)
