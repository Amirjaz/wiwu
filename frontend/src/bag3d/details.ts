// The bag's detailed parts, modelled here from measurements of the photos (tools/details.py, stored in
// the model's .json): the fingerprint lock module, the zipper (tape and teeth), the far end's ring and
// pull tab, and the brand plate. The AI shape blurs these and the photos have too few pixels for them up
// close, so they are built as real geometry with real materials. All positions are in metres, in the
// model's frame.
import {
  BufferAttribute, BufferGeometry, CatmullRomCurve3, Color, DoubleSide, ExtrudeGeometry, Group, InstancedMesh, Matrix4, Mesh,
  MeshPhysicalMaterial, MeshStandardMaterial, Path, Quaternion, Shape, TorusGeometry, Vector2, Vector3,
  type Material,
} from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { plateFace } from './logo';

type V3 = [number, number, number];
type Rect = [number, number, number, number]; // u0, v0, u1, v1 in the module's plane

export interface Details {
  module: {
    origin: V3; u: V3; v: V3; n: V3; thickness: number; outline: [number, number][];
    capBottom: number; capSides: [number, number]; slot: Rect; latch: Rect; led: Rect; frame: Rect; glass: Rect;
  };
  zipper: { points: V3[]; normals: V3[] };
  farEnd: { ring: V3; tab_root: V3; tab_tip: V3 };
  /** The brand plate: its face's centre and plane (u along the bag, v up), width and height. */
  plate?: { origin: V3; u: V3; v: V3; n: V3; size: [number, number]; thickness: number };
}

/** A part's two looks (scene.ts setColor): satin gunmetal on the black bag, as on the maker's side photo
 *  (lighter than the client's dim one), and silver on the brown and silver-white bags. */
function finish<T extends MeshStandardMaterial>(material: T, black: string, light: string): T {
  material.color.set(black);
  material.userData.finish = { black, light };
  return material;
}

// Satin, not mirror-like: a mirror would reflect the bright studio.
const gunmetal = () => finish(new MeshPhysicalMaterial({ metalness: 0.8, roughness: 0.42 }), '#55585d', '#b4b7bc');

function roundedRect(shape: Shape | Path, x0: number, y0: number, x1: number, y1: number, r: number) {
  const rr = Math.min(r, (x1 - x0) / 2, (y1 - y0) / 2);
  shape.moveTo(x0 + rr, y0);
  shape.lineTo(x1 - rr, y0);
  shape.quadraticCurveTo(x1, y0, x1, y0 + rr);
  shape.lineTo(x1, y1 - rr);
  shape.quadraticCurveTo(x1, y1, x1 - rr, y1);
  shape.lineTo(x0 + rr, y1);
  shape.quadraticCurveTo(x0, y1, x0, y1 - rr);
  shape.lineTo(x0, y0 + rr);
  shape.quadraticCurveTo(x0, y0, x0 + rr, y0);
  return shape;
}

function slab(shape: Shape, depth: number, bevel: number) {
  return new ExtrudeGeometry(shape, {
    depth, bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 5, curveSegments: 14,
  });
}

/** The lock: outline plate, raised cap with the pull's slot and latch, light window, sensor. Returns the
 *  group and the light window's material (the page turns it green at the lock stop). */
export function buildLock(d: Details['module']) {
  const group = new Group();
  const basis = new Matrix4().makeBasis(new Vector3(...d.u), new Vector3(...d.v), new Vector3(...d.n));
  group.quaternion.setFromRotationMatrix(basis);
  group.position.set(...d.origin);
  const metal = gunmetal();

  // The plate: the module's whole outline, from the leather (z = -thickness) to its face (z = 0).
  // The traced outline as a smooth closed curve (straight segments between the traced points facet it).
  const traced = new CatmullRomCurve3(d.outline.map(([x, y]) => new Vector3(x, y, 0)), true, 'centripetal');
  const outline = new Shape(traced.getSpacedPoints(120).slice(0, -1).map((p) => new Vector2(p.x, p.y)));
  const plate = new Mesh(slab(outline, d.thickness - 0.0012, 0.0012), metal);
  plate.position.z = -d.thickness;
  group.add(plate);

  // The cap over the top: slightly proud of the plate, rounded at the top like the photo's.
  const top = Math.max(...d.outline.map(([, y]) => y));
  const [c0, c1] = d.capSides;
  const capShape = new Shape();
  const r = (c1 - c0) * 0.32;
  capShape.moveTo(c0, d.capBottom);
  capShape.lineTo(c1, d.capBottom);
  capShape.lineTo(c1, top - r);
  capShape.quadraticCurveTo(c1, top, c1 - r, top);
  capShape.lineTo(c0 + r, top);
  capShape.quadraticCurveTo(c0, top, c0, top - r);
  capShape.lineTo(c0, d.capBottom);
  const cap = new Mesh(slab(capShape, 0.0008, 0.0005),
    finish(new MeshPhysicalMaterial({ metalness: 0.8, roughness: 0.4 }), '#5c5f64', '#bcbfc4'));
  cap.position.z = 0.0001;
  group.add(cap);

  const dark = new MeshStandardMaterial({ color: '#0b0c0e', roughness: 0.6 });
  const faceZ = 0.0001 + 0.0008 + 0.0005; // the cap's face
  // The groove under the cap.
  const groove = new Mesh(new RoundedBoxGeometry(c1 - c0, 0.0009, 0.0004, 2, 0.0002), dark);
  groove.position.set((c0 + c1) / 2, d.capBottom - 0.0002, 0.0007);
  group.add(groove);
  // The slot the pull's tongue goes into, and the latch's ridges under it.
  const [s0, s1, s2, s3] = d.slot;
  const slot = new Mesh(new RoundedBoxGeometry(s2 - s0, s3 - s1, 0.0004, 2, 0.0003), dark);
  slot.position.set((s0 + s2) / 2, (s1 + s3) / 2, faceZ);
  group.add(slot);
  const [l0, l1, l2, l3] = d.latch;
  const ridges = 7;
  const ridgeMat = finish(new MeshStandardMaterial({ metalness: 0.7, roughness: 0.5 }), '#6e7177', '#c3c6ca');
  for (let i = 0; i < ridges; i++) {
    const w = (l2 - l0) / (ridges * 2);
    const ridge = new Mesh(new RoundedBoxGeometry(w, l3 - l1, 0.0005, 2, w / 3), ridgeMat);
    ridge.position.set(l0 + w * (2 * i + 1), (l1 + l3) / 2, faceZ);
    group.add(ridge);
  }

  // The status light's window: a frosted pill, green when lit.
  const [e0, e1, e2, e3] = d.led;
  const ledShape = roundedRect(new Shape(), e0, e1, e2, e3, (e3 - e1) / 2) as Shape;
  const light = new MeshStandardMaterial({
    color: '#64676c', roughness: 0.4, emissive: new Color('#2fe39a'), emissiveIntensity: 0,
  });
  const led = new Mesh(slab(ledShape, 0.0002, 0), light);
  led.position.z = 0.0001;
  group.add(led);

  // The sensor: dark glass in a rose-copper frame.
  const [f0, f1, f2, f3] = d.frame;
  const [g0, g1, g2, g3] = d.glass;
  const frameShape = roundedRect(new Shape(), f0, f1, f2, f3, (f2 - f0) * 0.12) as Shape;
  frameShape.holes.push(roundedRect(new Path(), g0, g1, g2, g3, (g2 - g0) * 0.08) as Path);
  const frame = new Mesh(slab(frameShape, 0.0004, 0.00025), new MeshPhysicalMaterial({
    color: '#94817a', metalness: 0.6, roughness: 0.5,
  }));
  frame.position.z = 0.0001;
  group.add(frame);
  const glass = new Mesh(slab(roundedRect(new Shape(), g0, g1, g2, g3, (g2 - g0) * 0.08) as Shape, 0.0002, 0),
    new MeshPhysicalMaterial({ color: '#07080a', roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.06 }));
  glass.position.z = -0.0001;
  group.add(glass);

  group.traverse((o) => {
    if (o instanceof Mesh) {
      o.castShadow = true;
      o.receiveShadow = true;
    }
  });
  return { group, light };
}

/** The brand plate on the front: a square of dark satin metal with WiWU's emblem and name raised on its
 *  face (logo.ts), and a bright chamfer round it. Dark on every colour, as on the maker's photos of all
 *  three. `resolution`: the face's texture size in pixels. */
export function buildPlate(d: NonNullable<Details['plate']>, resolution: number, anisotropy: number) {
  const group = new Group();
  const basis = new Matrix4().makeBasis(new Vector3(...d.u), new Vector3(...d.v), new Vector3(...d.n));
  group.quaternion.setFromRotationMatrix(basis);
  group.position.set(...d.origin);

  const [w, h] = d.size;
  const bevel = Math.min(0.0003, d.thickness / 3);
  const outline = roundedRect(new Shape(), -w / 2 + bevel, -h / 2 + bevel, w / 2 - bevel, h / 2 - bevel, 0.0004) as Shape;
  const { map, normalMap, roughnessMap } = plateFace(resolution, anisotropy);
  // The face's UVs are the outline's own coordinates (metres): the textures span the plate's whole square.
  for (const texture of [map, normalMap, roughnessMap]) {
    texture.repeat.set(1 / w, 1 / h);
    texture.offset.set(0.5, 0.5);
  }
  // Satin, half metallic: a mirror-like face goes black where it reflects the studio's dark side, and the
  // plate reads mid-grey from every side on the maker's photos.
  const face = new MeshPhysicalMaterial({ color: '#84878c', metalness: 0.5, roughness: 1, map, normalMap, roughnessMap });
  const edge = new MeshPhysicalMaterial({ color: '#979a9f', metalness: 0.7, roughness: 0.3 });
  const plate = new Mesh(slab(outline, d.thickness - bevel, bevel), [face, edge]); // the faces, the sides
  plate.position.z = -d.thickness;
  plate.castShadow = true;
  plate.receiveShadow = true;
  group.add(plate);
  return group;
}

/** Arc-length lookup along the zipper's centre line. */
function pathSampler(points: V3[], normals: V3[]) {
  const P = points.map((p) => new Vector3(...p));
  const N = normals.map((n) => new Vector3(...n).normalize());
  const s = [0];
  for (let i = 1; i < P.length; i++) s.push(s[i - 1] + P[i].distanceTo(P[i - 1]));
  const length = s[s.length - 1];
  const at = (t: number) => {
    let i = 1;
    while (i < s.length - 1 && s[i] < t) i++;
    const k = (t - s[i - 1]) / Math.max(1e-9, s[i] - s[i - 1]);
    const p = P[i - 1].clone().lerp(P[i], Math.min(Math.max(k, 0), 1));
    const n = N[i - 1].clone().lerp(N[i], Math.min(Math.max(k, 0), 1)).normalize();
    const tangent = P[i].clone().sub(P[i - 1]).normalize();
    const across = new Vector3().crossVectors(n, tangent).normalize();
    n.crossVectors(tangent, across).normalize();
    return { p, n, tangent, across };
  };
  return { length, at };
}

/** The zipper: black tape along the seam and interlocked metal teeth on it. */
export function buildZipper(z: Details['zipper'], tapeMaterial: Material) {
  const group = new Group();
  const path = pathSampler(z.points, z.normals);
  const halfTape = 0.0105;
  const lift = 0.0006;

  // Tape: a strip with a slight crown, its edges tucked into the leather.
  const across = [-1, -0.6, -0.2, 0.2, 0.6, 1];
  const steps = Math.max(2, Math.round(path.length / 0.002));
  const positions: number[] = [];
  const normals: number[] = [];
  const uvs: number[] = [];
  for (let i = 0; i <= steps; i++) {
    const { p, n, across: b } = path.at((i / steps) * path.length);
    for (const a of across) {
      const height = lift - 0.0012 * a * a; // crown
      const q = p.clone().addScaledVector(b, a * halfTape).addScaledVector(n, height);
      positions.push(q.x, q.y, q.z);
      const tilt = n.clone().addScaledVector(b, a * 0.25).normalize();
      normals.push(tilt.x, tilt.y, tilt.z);
      uvs.push((a + 1) / 2, (i / steps) * path.length * 40);
    }
  }
  const index: number[] = [];
  const w = across.length;
  for (let i = 0; i < steps; i++) {
    for (let j = 0; j < w - 1; j++) {
      const a = i * w + j;
      index.push(a, a + w, a + 1, a + 1, a + w, a + w + 1);
    }
  }
  const tape = new BufferGeometry();
  tape.setAttribute('position', new BufferAttribute(new Float32Array(positions), 3));
  tape.setAttribute('normal', new BufferAttribute(new Float32Array(normals), 3));
  tape.setAttribute('uv', new BufferAttribute(new Float32Array(uvs), 2));
  tape.setIndex(index);
  const tapeMesh = new Mesh(tape, tapeMaterial);
  tapeMesh.receiveShadow = true;
  group.add(tapeMesh);

  // Teeth: alternate sides every 2.4 mm; each reaches from its tape to the centre line, where the two
  // rows meet, as in the photos' interlocked chain.
  const pitch = 0.0024;
  const count = Math.floor(path.length / pitch) - 1;
  const toothLength = 0.0041;
  const tooth = new RoundedBoxGeometry(toothLength, 0.0016, 0.0018, 2, 0.00045);
  const teeth = new InstancedMesh(tooth,
    finish(new MeshStandardMaterial({ metalness: 0.85, roughness: 0.36 }), '#6a6d73', '#c0c3c8'), count);
  const m = new Matrix4();
  const q = new Quaternion();
  const scale = new Vector3(1, 1, 1);
  for (let k = 0; k < count; k++) {
    const { p, n, tangent, across: b } = path.at((k + 1) * pitch);
    const side = k % 2 === 0 ? -1 : 1;
    const pos = p.clone().addScaledVector(n, lift + 0.0008).addScaledVector(b, side * (toothLength / 2 + 0.00015));
    q.setFromRotationMatrix(new Matrix4().makeBasis(b, n, tangent));
    m.compose(pos, q, scale);
    teeth.setMatrixAt(k, m);
  }
  teeth.castShadow = true;
  group.add(teeth);
  return group;
}

/** The far end: the ring at the top corner and the pull tab sticking out (as the front and back photos show). */
export function buildFarEnd(f: Details['farEnd']) {
  const group = new Group();
  const metal = finish(new MeshStandardMaterial({ metalness: 1, roughness: 0.32, side: DoubleSide }), '#8a8c91', '#c8cbd0');

  const ring = new Mesh(new TorusGeometry(0.0042, 0.0008, 10, 28), metal);
  ring.position.set(...f.ring);
  group.add(ring); // its plane faces front and back, like an O in both photos

  const root = new Vector3(...f.tab_root);
  const tip = new Vector3(...f.tab_tip);
  const along = tip.clone().sub(root);
  const length = along.length() + 0.003;
  along.normalize();
  const width = 0.0058;
  const outer = roundedRect(new Shape(), 0, -width / 2, length, width / 2, width / 2) as Shape;
  outer.holes.push(roundedRect(new Path(), length * 0.42, -width * 0.16, length - 0.0018, width * 0.16, width * 0.16) as Path);
  const tab = new Mesh(new ExtrudeGeometry(outer, {
    depth: 0.0012, bevelEnabled: true, bevelThickness: 0.0003, bevelSize: 0.0003, bevelSegments: 2, curveSegments: 8,
  }), metal);
  // Long axis along root→tip, width vertical, thickness front-to-back.
  const up = new Vector3(0, 1, 0).sub(along.clone().multiplyScalar(along.y)).normalize();
  const thick = new Vector3().crossVectors(along, up);
  tab.quaternion.setFromRotationMatrix(new Matrix4().makeBasis(along, up, thick));
  tab.position.copy(root).addScaledVector(along, -0.0015).addScaledVector(thick, -0.0006);
  group.add(tab);

  // The slider the tab hangs from.
  const slider = new Mesh(new RoundedBoxGeometry(0.0075, 0.0055, 0.011, 3, 0.0015), metal);
  slider.position.copy(root).addScaledVector(along, -0.003);
  slider.quaternion.copy(tab.quaternion);
  group.add(slider);

  group.traverse((o) => {
    if (o instanceof Mesh) o.castShadow = true;
  });
  return group;
}
