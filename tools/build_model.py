"""The hero's 3D model (frontend/public/models/alpha*.glb) from the AI-generated shape.

    python tools/build_model.py            (needs numpy, trimesh, fast-simplification)
    cd frontend && npx gltf-transform meshopt ...   (run by this script; compresses the result)

Source: media/3d/ai/hunyuan2mv-shape-3view-denoised.glb, made by Hunyuan3D-2mv from the front, back
and side photos (2026-10-14). It is a good shape with no texture, so this script:
1. drops the zero-area triangles (about half of them) and welds the rest;
2. decimates it for the web (desktop and phone versions);
3. puts it at real size and proportion (25 x 15.5 x 6.5 cm; the AI made it a little short and thick),
   resting on y = 0, front facing +z, the lock end at -x;
4. splits it into the parts the browser gives different materials, by where they are on the bag
   (read off orthographic views of the source): black PU leather, zipper tape, zipper teeth and
   gunmetal hardware (lock module, logo plate, zipper slider and pulls, the strap's snap);
5. gives every part box-projected UVs (1 unit = 4 cm) for the leather grain normal map, which the
   page draws itself (frontend/src/hero/leather.ts).
Coordinates below are in the source's units (width about 1.97).
"""
import subprocess
import sys
from pathlib import Path

import fast_simplification
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'media' / '3d' / 'ai' / 'hunyuan2mv-shape-3view-denoised.glb'
OUT = ROOT / 'frontend' / 'public' / 'models'
SIZE_M = np.array([0.25, 0.155, 0.065])  # width, height, depth of the body (pulls stick out)
BODY_X = (-0.98, 0.94)  # the body's width in source units, without the zipper pull tab
UV_TILE_M = 0.04


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


def parts(mesh):
    """Material name per face, from face centres and normals (source units)."""
    c, n = mesh.triangles_center, mesh.face_normals
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


def to_real_size(mesh):
    lo, hi = mesh.bounds
    sx = SIZE_M[0] / (BODY_X[1] - BODY_X[0])
    sy = SIZE_M[1] / (hi[1] - lo[1])
    sz = SIZE_M[2] / (hi[2] - lo[2])
    centre = np.array([(BODY_X[0] + BODY_X[1]) / 2, lo[1], (lo[2] + hi[2]) / 2])
    mesh.vertices = (mesh.vertices - centre) * [sx, sy, sz]


def with_box_uvs(mesh):
    """Duplicate vertices where the projection axis changes, then project each face on its axis."""
    axis = np.abs(mesh.face_normals).argmax(1)
    keys = mesh.faces * 3 + axis[:, None]
    unique, inverse = np.unique(keys.ravel(), return_inverse=True)
    vertex = unique // 3
    vaxis = unique % 3
    verts = mesh.vertices[vertex]
    normals = mesh.vertex_normals[vertex]
    uv = np.where(vaxis[:, None] == 0, verts[:, [2, 1]], np.where(vaxis[:, None] == 1, verts[:, [0, 2]], verts[:, [0, 1]]))
    out = trimesh.Trimesh(verts, inverse.reshape(-1, 3), vertex_normals=normals, process=False)
    out.visual = trimesh.visual.TextureVisuals(uv=uv / UV_TILE_M)
    return out


def build(name, faces):
    mesh = decimate(load(), faces)
    labels = parts(mesh)
    to_real_size(mesh)
    scene = trimesh.Scene()
    for part in ('leather', 'tape', 'teeth', 'metal'):
        sub = mesh.submesh([np.nonzero(labels == part)[0]], append=True)
        sub = with_box_uvs(sub)
        sub.visual.material = trimesh.visual.material.PBRMaterial(name=part)
        scene.add_geometry(sub, node_name=part, geom_name=part)
        print(f'  {part}: {len(sub.faces)} faces')
    raw = OUT / f'{name}.raw.glb'
    scene.export(raw)
    final = OUT / f'{name}.glb'
    subprocess.run(['npx', '--no-install', 'gltf-transform', 'meshopt', str(raw), str(final)],
                   cwd=ROOT / 'frontend', check=True, shell=sys.platform == 'win32')
    raw.unlink()
    print(f'{final.name}: {final.stat().st_size / 1024:.0f} KB, bounds {np.round(mesh.bounds, 4).tolist()}')


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    build('alpha', 90_000)
    build('alpha-mobile', 36_000)
