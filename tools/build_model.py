"""The hero's 3D model (frontend/public/models/alpha*.glb + .json) from the AI shape and the three photos.

    python tools/build_model.py   (numpy, scipy, opencv-python-headless, trimesh, fast-simplification, xatlas)
    Before it: tools/photo_masks.py, tools/fit_proportions.py, tools/fit_cameras.py (see README).

1. The shape: media/3d/ai/hunyuan2mv-shape-3view-denoised.glb, made by Hunyuan3D-2mv from the front,
   back and side photos (2026-10-14). Zero-area triangles (about half) dropped, the rest welded,
   decimated for the web (desktop and phone versions), lightly smoothed, and given the proportions the
   photos agree with best (tools/fit_proportions.py).
2. The detailed parts are measured from the photos (tools/details.py) and modelled by the page: the lock
   module, the zipper, the far end's ring and pull tab. Under them the AI's blurry versions are pressed
   flat, so the modelled parts sit cleanly (and the AI's invented far-end bracket is smoothed away).
3. The surface is unwrapped into a texture atlas (xatlas) and the three photos are projected onto it
   (tools/bake.py): the front, back, top and lock end look like the photos. The bottom and the far end,
   which no photo shows, get the leather's colour.
4. Faces are sorted into parts the page lights differently (leather, zipper tape, zipper teeth, metal).
5. One uniform scale makes it 25 cm wide (the photos give the proportions, not the retailers' listings,
   which disagree); it rests on y = 0, front +z, lock end -x. Compressed: meshopt, JPEG texture.
The .json beside each model holds the measurements of step 2, the hotspots' anchors and the leather
grain's repeat. Coordinates below are the unscaled AI shape's (width about 1.97).
"""
import json
import subprocess
import sys
from pathlib import Path

import fast_simplification
import numpy as np
import trimesh
import xatlas
from PIL import Image
from scipy import sparse
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bake  # noqa: E402  (tools/bake.py)
import details  # noqa: E402  (tools/details.py)
import fit_cameras as fc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'media' / '3d' / 'ai' / 'hunyuan2mv-shape-3view-denoised.glb'
OUT = ROOT / 'frontend' / 'public' / 'models'
WIDTH_M = 0.25  # the body's width (pulls stick out)
BODY_X = (-0.98, 0.94)  # the body's width in shape units, without the zipper pull tab
GRAIN_TILE_M = 0.04  # one tile of the page's leather grain covers 4 cm
TAPE_HALF_M = 0.0105  # the zipper tape's half width; frontend/src/hero/details.ts uses the same
TAPE_LIFT_M = 0.0006


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
    """Material name per face, from face centres and normals (unscaled shape units)."""
    c, n = centres, normals
    x, y, z = c[:, 0], c[:, 1], c[:, 2]
    part = np.full(len(c), 'leather', dtype=object)

    on_top = (y > 0.42) & (np.abs(n[:, 2]) < 0.75)
    lock_end_band = (x < -0.9) & (y > -0.06) & (np.abs(n[:, 2]) < 0.75)
    far_end_band = (x > 0.88) & (y > 0.4) & (np.abs(n[:, 2]) < 0.75)
    zipper = on_top | lock_end_band | far_end_band
    part[zipper & (np.abs(z) < 0.1)] = 'tape'
    part[zipper & (np.abs(z) < 0.032)] = 'teeth'

    # The front panel: smooth and matte in the photo, unlike the pebbled back.
    zc = (c[:, 2].min() + c[:, 2].max()) / 2
    part[(part == 'leather') & (n[:, 2] > 0.45) & (z > zc + 0.1) & (np.abs(x) < 0.9)] = 'front'

    metal = np.zeros(len(c), bool)
    plate = [(0.446, -0.252), (0.596, -0.234), (0.635, -0.381), (0.476, -0.399)]  # the logo plate
    metal |= (z > 0.12) & (n[:, 2] > 0.3) & in_quad(c[:, :2], plate)
    metal |= (x < -0.88) & (z < -0.14) & (y > 0.07) & (y < 0.24)  # main zipper's pull on the lock end
    metal |= (z < -0.2) & (x > -0.775) & (x < -0.675) & (y > 0.06) & (y < 0.29)  # back pocket's pull
    metal |= (z < -0.25) & (np.hypot(x + 0.641, y + 0.331) < 0.035)  # the strap's snap
    part[metal] = 'metal'
    return part


def polygon_inside_distance(points, polygon):
    """Signed distance of 2D points to a closed polygon: positive inside."""
    poly = np.asarray(polygon)
    a, b = poly, np.roll(poly, -1, axis=0)
    ab = b - a
    t = np.clip(((points[:, None, :] - a) * ab).sum(2) / (ab * ab).sum(1), 0, 1)
    nearest = a + t[:, :, None] * ab
    dist = np.linalg.norm(points[:, None, :] - nearest, axis=2).min(1)
    x, y = points[:, 0:1], points[:, 1:2]
    crosses = ((a[:, 1] > y) != (b[:, 1] > y)) & (x < (b[:, 0] - a[:, 0]) * (y - a[:, 1]) / (ab[:, 1] + 1e-12) + a[:, 0])
    inside = crosses.sum(1) % 2 == 1
    return np.where(inside, dist, -dist)


def diffuse(mesh, mask, rounds):
    """A soft 0..1 weight from a vertex mask, spread over the mesh's edges."""
    edges = mesh.edges_unique
    n = len(mesh.vertices)
    adj = sparse.coo_matrix((np.ones(len(edges) * 2), (np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]])),
                            shape=(n, n)).tocsr()
    adj = sparse.diags(1 / np.maximum(adj.sum(1).A1, 1)) @ adj
    w = mask.astype(float)
    for _ in range(rounds):
        w = 0.5 * w + 0.5 * (adj @ w)
    return np.clip(w * 2, 0, 1)


def press_under_details(mesh, d, units_per_m, far_end_region):
    """Push the AI's own versions of the modelled parts under them."""
    v = mesh.vertices
    # 1. The lock module's footprint: down to just behind the plate's back.
    m = d['module']
    o, u, vv, n = (np.array(m[k]) for k in ('origin', 'u', 'v', 'n'))
    rel = v - o
    a, b, h = rel @ u, rel @ vv, rel @ n
    inside = polygon_inside_distance(np.stack([a, b], 1), m['outline'])
    margin = 0.002 * units_per_m
    weight = np.clip((inside + margin) / margin + 1, 0, 1)  # 1 inside and 2 mm around, fading to 0 by 4 mm
    near = (h > -m['thickness'] - 0.06) & (h < 0.04) & (weight > 0)
    target = -m['thickness'] - 0.0008 * units_per_m
    new_h = h + weight * (np.minimum(h, target) - h)
    v[near] += n * (new_h - h)[near, None]

    # 2. Under the zipper tape: below the tape's surface.
    P = np.array(d['zipper']['points'])
    N = np.array(d['zipper']['normals'])
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    tree = cKDTree(P)
    dist, idx = tree.query(v)
    p, nn, tt = P[idx], N[idx], T[idx]
    across = np.cross(nn, tt)
    across /= np.linalg.norm(across, axis=1, keepdims=True)
    rel = v - p
    lat, h, along = (rel * across).sum(1), (rel * nn).sum(1), (rel * tt).sum(1)
    half = TAPE_HALF_M * units_per_m
    inner = (idx > 0) & (idx < len(P) - 1)
    band = inner & (np.abs(lat) < half + 0.001 * units_per_m) & (np.abs(along) < 0.006 * units_per_m) & (h > -0.03)
    tape_h = (TAPE_LIFT_M - 0.0012 * np.clip(lat / half, -1, 1) ** 2 - 0.0009) * units_per_m
    v[band] += nn[band] * (np.minimum(h, tape_h) - h)[band, None]

    # 3. The far end: smooth away the AI's bracket and tab (the modelled ring and tab replace them).
    weight = diffuse(mesh, far_end_region, 6)
    smooth = mesh.copy()
    trimesh.smoothing.filter_laplacian(smooth, lamb=0.6, iterations=40)
    mesh.vertices = v * (1 - weight[:, None]) + smooth.vertices * weight[:, None]


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


def surface_point(mesh, origin, direction):
    p, n = details.surface(mesh, np.asarray(origin, float), np.asarray(direction, float))
    return p, n


def to_real(d, centre, s):
    """Measurements from shape units to the model's metres."""
    pt = lambda p: ((np.array(p) - centre) * s).round(5).tolist()  # noqa: E731
    m = d['module']
    module = {
        'origin': pt(m['origin']), 'u': m['u'], 'v': m['v'], 'n': m['n'],
        'thickness': round(m['thickness'] * s, 5),
        'outline': (np.array(m['outline']) * s).round(5).tolist(),
        'capBottom': round(m['capBottom'] * s, 5), 'capSides': (np.array(m['capSides']) * s).round(5).tolist(),
    }
    for key in ('slot', 'latch', 'led', 'frame', 'glass'):
        module[key] = (np.array(m[key]) * s).round(5).tolist()
    return {
        'module': module,
        'zipper': {'points': [pt(p) for p in d['zipper']['points']],
                   'normals': np.array(d['zipper']['normals']).round(4).tolist()},
        'farEnd': {k: pt(p) for k, p in d['farEnd'].items()},
    }


def build(name, faces, texture, d):
    print(f'{name}: {faces} faces, {texture}px texture')
    mesh = decimate(load(), faces)
    labels = parts(mesh.triangles_center, mesh.face_normals)
    x, y, z = mesh.vertices.T
    zc = (mesh.bounds[0][2] + mesh.bounds[1][2]) / 2
    far_end = ((x > 0.86) & (np.abs(z - zc) < 0.15) & (y > 0.0)) | (x > 0.95)
    # The front panel is smooth in the photo; the AI shape has dents in it (not around the logo plate).
    plate = [(0.40, -0.21), (0.64, -0.19), (0.68, -0.42), (0.43, -0.44)]
    front = (mesh.vertex_normals[:, 2] > 0.55) & (z > zc + 0.12) & (np.abs(x) < 0.86) & \
        ~in_quad(mesh.vertices[:, :2], plate)
    fc.apply_shape_transform(mesh)  # the photos' proportions (the cameras' frame)
    s = WIDTH_M / (BODY_X[1] - BODY_X[0])
    press_under_details(mesh, d, 1 / s, far_end)
    weight = diffuse(mesh, front, 3)
    smooth = mesh.copy()
    trimesh.smoothing.filter_taubin(smooth, lamb=0.5, nu=-0.53, iterations=30)
    mesh.vertices = mesh.vertices * (1 - weight[:, None]) + smooth.vertices * weight[:, None]

    normals = mesh.vertex_normals.copy()
    vmapping, ufaces, uvs = unwrap(mesh, texture)
    verts = mesh.vertices[vmapping]
    vnorm = normals[vmapping]
    # xatlas keeps the triangle order, so the parts computed on the welded mesh still apply.
    assert len(ufaces) == len(mesh.faces) and np.allclose(verts[ufaces].mean(1), mesh.triangles_center, atol=1e-5)

    print('  baking the photos')
    rgb, coverage = bake.bake(verts, vnorm, ufaces, uvs, texture)
    tex_path = OUT / f'{name}-texture.jpg'
    Image.fromarray(rgb).save(tex_path, quality=90, optimize=True, progressive=False)
    texture_image = Image.open(tex_path)  # trimesh keeps a JPEG a JPEG when embedding it
    texture_image.load()

    lo, hi = mesh.bounds
    centre = np.array([(BODY_X[0] + BODY_X[1]) / 2, lo[1], (lo[2] + hi[2]) / 2])
    real = (verts - centre) * s

    scene = trimesh.Scene()
    for part in ('leather', 'front', 'tape', 'teeth', 'metal'):
        idx = np.nonzero(labels == part)[0]
        used, inverse = np.unique(ufaces[idx].ravel(), return_inverse=True)
        sub = trimesh.Trimesh(real[used], inverse.reshape(-1, 3), vertex_normals=vnorm[used], process=False)
        material = trimesh.visual.material.PBRMaterial(name=part, baseColorTexture=texture_image,
                                                      metallicFactor=0.0, roughnessFactor=0.6)
        sub.visual = trimesh.visual.TextureVisuals(uv=uvs[used], material=material)
        scene.add_geometry(sub, node_name=part, geom_name=part)
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

    # Sidecar. The grain's repeat: metres per UV unit, from comparing edge lengths.
    edges = ufaces[:, [0, 1]]
    world = np.linalg.norm(real[edges[:, 0]] - real[edges[:, 1]], axis=1)
    uvlen = np.linalg.norm(uvs[edges[:, 0]] - uvs[edges[:, 1]], axis=1)
    metres_per_uv = float(np.median(world[uvlen > 1e-6] / uvlen[uvlen > 1e-6]))
    m = d['module']
    lock_at = np.array(m['origin']) + np.array(m['n']) * 0.02
    front, front_n = surface_point(mesh, [-0.2, (lo[1] + hi[1]) / 2, hi[2] + 1], [0, 0, -1])
    pocket, pocket_n = surface_point(mesh, [0.0, lo[1] + 0.78 * (hi[1] - lo[1]), lo[2] - 1], [0, 0, 1])
    hotspots = {
        'lock': {'at': ((lock_at - centre) * s).round(5).tolist(), 'normal': m['n']},
        'leather': {'at': ((front - centre) * s).round(5).tolist(), 'normal': front_n.round(4).tolist()},
        'pocket': {'at': ((pocket - centre) * s).round(5).tolist(), 'normal': pocket_n.round(4).tolist()},
    }
    side = {'grainRepeat': round(metres_per_uv / GRAIN_TILE_M, 2), 'size': ((hi - lo) * s).round(4).tolist(),
            'hotspots': hotspots, 'details': to_real(d, centre, s),
            # model = (shape - centre) * scale: lets tools/compare.mjs use the photo cameras.
            'frame': {'centre': centre.tolist(), 'scale': s}}
    (OUT / f'{name}.json').write_text(json.dumps(side), newline='\n')
    print(f'  {final.name}: {final.stat().st_size / 1024:.0f} KB, size {side["size"]} m, '
          f'photos cover {np.mean(coverage[coverage > 0] > 0.5):.0%}')


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    _, measured = details.measure()
    build('alpha', 90_000, 2048, measured)
    if 'desktop' not in sys.argv[1:]:  # `build_model.py desktop`: just the desktop model, while iterating
        build('alpha-mobile', 36_000, 1024, measured)
