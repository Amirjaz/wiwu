// The bag in 3D: a studio scene, drag to turn it, hotspots, and a camera that moves to each stop of
// the scroll tour. Loaded only when the device can take it (see islands/hero.ts).
import {
  AdditiveBlending, CanvasTexture, Color, DirectionalLight, Mesh, MeshBasicMaterial,
  MeshPhysicalMaterial, MeshStandardMaterial, NeutralToneMapping, PCFSoftShadowMap, PerspectiveCamera, PlaneGeometry,
  PMREMGenerator, Scene, ShadowMaterial, SRGBColorSpace, Vector2, Vector3, WebGLRenderer, type Material, type Texture,
} from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { pebbleNormalMap } from './textures';
import { buildFarEnd, buildLock, buildZipper, type Details } from './details';

/** What tools/build_model.py writes next to each model. */
interface ModelInfo {
  grainRepeat: number;
  details?: Details;
  hotspots?: Record<string, { at: [number, number, number]; normal: [number, number, number] }>;
}

/** A camera position around a target: azimuth from the front (+z) toward the far end (+x), in degrees.
 *  `frame` is how much (in metres, across) must fit: on narrow screens the camera backs off to fit it. */
export interface Stop {
  az: number;
  el: number;
  dist: number;
  frame: number;
  target: [number, number, number];
}

export interface Hotspot {
  id: string;
  at: [number, number, number];
  normal: [number, number, number];
}

const DEG = Math.PI / 180;

// The bag is 25 x 15.5 x 6.5 cm, resting on y = 0, front facing +z, the lock end at -x.
export const STOPS: Stop[] = [
  { az: -50, el: 14, dist: 0.3, frame: 0.27, target: [0, 0.072, 0] }, // the hero: front and the lock end
  { az: -80, el: 8, dist: 0.3, frame: 0.15, target: [-0.1, 0.06, 0] }, // the lock
  { az: 194, el: 12, dist: 0.3, frame: 0.36, target: [0.012, 0.075, 0] }, // the back pocket, with room for its shadow
  { az: 160, el: 22, dist: 0.3, frame: 0.26, target: [-0.01, 0.05, -0.02] }, // the wrist strap
  // The leather is shown on the back: its photo has the pebbled grain sharply (the front's is soft). The
  // whole back stays in frame: closer, the bag ran past the stage's edges (no edge fade since 2026-10-18).
  { az: 208, el: 24, dist: 0.36, frame: 0.34, target: [-0.008, 0.08, -0.01] }, // the leather, in raking light
];

export const HOTSPOTS: Hotspot[] = [
  { id: 'lock', at: [-0.129, 0.05, 0], normal: [-1, 0, 0] },
  { id: 'leather', at: [-0.03, 0.085, 0.034], normal: [0, 0, 1] },
  { id: 'pocket', at: [0.02, 0.118, -0.034], normal: [0, 0, -1] },
];

export class HeroScene {
  private renderer: WebGLRenderer;
  private key!: DirectionalLight;
  private light: MeshStandardMaterial | null = null;
  private halo: MeshBasicMaterial | null = null;
  private scene = new Scene();
  private camera = new PerspectiveCamera(28, 1, 0.01, 10);
  private controls: OrbitControls;
  private stop = 0;
  private stops: Stop[] = STOPS.map((s) => ({ ...s, target: [...s.target] }));
  private hotspots: Hotspot[] = HOTSPOTS;
  private current: Stop = { ...STOPS[0], target: [...STOPS[0].target] };
  private settled = false; // at the hero stop and handed over to the user's drag
  private running = false;
  private visible = true;
  private frame = 0;
  private onHotspots: (positions: Map<string, Vector2 | null>) => void;
  private resizeObserver: ResizeObserver;

  constructor(
    private container: HTMLElement,
    private options: { reducedMotion: boolean; small: boolean; onHotspots: HeroScene['onHotspots'] },
  ) {
    this.onHotspots = options.onHotspots;
    this.renderer = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, options.small ? 1.5 : 2));
    this.renderer.outputColorSpace = SRGBColorSpace;
    // Neutral, not filmic: the bag's colours come from the photos and should stay as photographed.
    this.renderer.toneMapping = NeutralToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFSoftShadowMap;
    const canvas = this.renderer.domElement;
    canvas.className = 'absolute inset-0 size-full opacity-0 transition-opacity duration-700';
    canvas.setAttribute('aria-hidden', 'true');
    // No mask at the edges: an elliptical fade read as a white ring around the bag (removed 2026-10-18).
    container.appendChild(canvas);

    const pmrem = new PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environmentIntensity = 0.75;
    pmrem.dispose();

    const key = (this.key = new DirectionalLight(0xffffff, 2.6));
    key.castShadow = true;
    key.shadow.mapSize.set(options.small ? 512 : 1024, options.small ? 512 : 1024);
    Object.assign(key.shadow.camera, { left: -0.3, right: 0.3, top: 0.3, bottom: -0.3, near: 0.1, far: 3 });
    key.shadow.radius = 8;
    key.shadow.bias = -0.0005;
    this.scene.add(key);
    const rim = new DirectionalLight(0xdfe6ff, 1.2);
    rim.position.set(0.6, 0.5, -0.7);
    this.scene.add(rim);

    const floor = new Mesh(new PlaneGeometry(3, 3), new ShadowMaterial({ color: new Color('#17181b'), opacity: 0.16 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    this.scene.add(floor);

    this.controls = new OrbitControls(this.camera, canvas);
    Object.assign(this.controls, {
      enableDamping: true, dampingFactor: 0.08, enablePan: false, rotateSpeed: 0.7,
      minDistance: 0.28, maxDistance: 0.85, minPolarAngle: 20 * DEG, maxPolarAngle: 88 * DEG,
      autoRotate: !options.reducedMotion, autoRotateSpeed: -0.6,
    });
    // Vertical swipes keep scrolling the page; sideways ones turn the bag. No zoom anywhere: the mouse
    // wheel over the bag scrolls the page like everywhere else (zooming in had pushed the bag past the
    // stage's edges).
    canvas.style.touchAction = 'pan-y';
    this.controls.enableZoom = false;
    this.controls.enabled = false;
    this.controls.addEventListener('start', () => (this.controls.autoRotate = false));

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
    this.place(this.current);
  }

  /** url: the .glb; its .json sidecar sits next to it. */
  async load(url: string, onProgress?: (fraction: number | null) => void): Promise<void> {
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    const [gltf, info] = await Promise.all([
      loader.loadAsync(url, (event) => onProgress?.(event.lengthComputable ? event.loaded / event.total : null)),
      fetch(url.replace(/[.]glb$/, '.json'))
        .then((r) => (r.ok ? (r.json() as Promise<ModelInfo>) : null))
        .catch(() => null),
    ]);
    // The colour is the photos', baked into one texture all parts share. The parts only differ in how
    // they take the studio light; a faint grain makes highlights break up like on real pebbled PU.
    let photo: Texture | null = null;
    gltf.scene.traverse((node) => {
      if (!photo && node instanceof Mesh) photo = (node.material as MeshStandardMaterial).map;
    });
    const grain = pebbleNormalMap(this.options.small ? 256 : 512);
    const repeat = info?.grainRepeat ?? 10;
    grain.repeat.set(repeat, repeat);
    const materials: Record<string, Material> = {
      leather: new MeshPhysicalMaterial({
        map: photo, roughness: 0.62, normalMap: grain, normalScale: new Vector2(0.16, 0.16),
        clearcoat: 0.12, clearcoatRoughness: 0.6,
      }),
      front: new MeshStandardMaterial({ map: photo, roughness: 0.82 }), // smooth matte panel
      tape: new MeshStandardMaterial({ map: photo, roughness: 0.85 }),
      teeth: new MeshStandardMaterial({ map: photo, metalness: 0.2, roughness: 0.45 }),
      metal: new MeshStandardMaterial({ map: photo, metalness: 0.2, roughness: 0.36 }),
    };
    gltf.scene.traverse((node) => {
      if (node instanceof Mesh) {
        const part = materials[node.name] ? node.name : node.parent?.name ?? '';
        node.material = materials[part] ?? materials.leather;
        node.castShadow = true;
        node.receiveShadow = true;
      }
    });
    this.scene.add(gltf.scene);
    if (info?.details) this.addDetails(info.details);
    if (info?.hotspots) {
      this.hotspots = Object.entries(info.hotspots).map(([id, h]) => ({ id, at: h.at, normal: h.normal }));
    }
    this.renderer.render(this.scene, this.camera);
    this.renderer.domElement.classList.remove('opacity-0');
    this.start();
  }

  /** The lock module, the zipper and the far end's hardware, modelled from the photos' measurements. */
  private addDetails(details: Details) {
    // The lock stop looks squarely at the module, a little from the front and above.
    const [nx, ny, nz] = details.module.n;
    const [ox, oy, oz] = details.module.origin;
    this.stops[1] = {
      ...this.stops[1],
      az: (Math.atan2(nx, nz) * 180) / Math.PI + 12,
      el: Math.max(4, (Math.asin(ny) * 180) / Math.PI - 4),
      target: [ox + nx * 0.004, oy, oz + nz * 0.004],
    };
    const lock = buildLock(details.module);
    this.light = lock.light;
    // A soft glow over the status light's window when it's lit.
    const [e0, e1, e2, e3] = details.module.led;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 64;
    const ctx = canvas.getContext('2d')!;
    const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, 'rgba(60,240,160,0.85)');
    g.addColorStop(1, 'rgba(60,240,160,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 64, 64);
    this.halo = new MeshBasicMaterial({
      map: new CanvasTexture(canvas), transparent: true, opacity: 0, blending: AdditiveBlending, depthWrite: false,
    });
    const glow = new Mesh(new PlaneGeometry((e2 - e0) * 2.6, (e3 - e1) * 5), this.halo);
    glow.position.set((e0 + e2) / 2, (e1 + e3) / 2, 0.0008);
    lock.group.add(glow);
    this.scene.add(lock.group);

    const tape = new MeshStandardMaterial({ color: '#141518', roughness: 0.95 });
    this.scene.add(buildZipper(details.zipper, tape));
    this.scene.add(buildFarEnd(details.farEnd));
  }

  /** Move to a tour stop (0 = the hero, where the user can drag). */
  goTo(index: number) {
    if (index === this.stop) return;
    if (this.stop === 0 && this.settled) this.readCamera();
    this.stop = index;
    this.settled = false;
    this.controls.enabled = false;
    if (this.options.reducedMotion) this.current = { ...this.stops[index], target: [...this.stops[index].target] };
    this.start();
  }

  /** Development only (tools/compare.mjs): one frame from a source photo's camera, as a JPEG data URL,
   *  so the model can be laid next to the photo. Stops the animation. */
  debugRender(eye: [number, number, number], quaternion: [number, number, number, number], fov: number,
    width: number, height: number): string {
    this.running = false;
    cancelAnimationFrame(this.frame);
    const camera = this.camera.clone();
    camera.position.set(...eye);
    camera.quaternion.set(...quaternion);
    camera.fov = fov;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    this.aimLight((Math.atan2(eye[0], eye[2]) * 180) / Math.PI);
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(width, height, false);
    this.renderer.render(this.scene, camera);
    return this.renderer.domElement.toDataURL('image/jpeg', 0.92);
  }

  /** Development only: one frame from an orbit position (degrees, metres), the status light on or off. */
  debugOrbit(az: number, el: number, dist: number, target: [number, number, number], width: number,
    height: number, light = false): string {
    if (this.light && this.halo) {
      this.halo.opacity = light ? 1 : 0;
      this.light.emissiveIntensity = light ? 2.4 : 0;
    }
    const a = az * DEG;
    const e = el * DEG;
    const eye: [number, number, number] = [
      target[0] + dist * Math.cos(e) * Math.sin(a),
      target[1] + dist * Math.sin(e),
      target[2] + dist * Math.cos(e) * Math.cos(a),
    ];
    const camera = new PerspectiveCamera(30, width / height, 0.01, 10);
    camera.position.set(...eye);
    camera.lookAt(...target);
    const q = camera.quaternion;
    return this.debugRender(eye, [q.x, q.y, q.z, q.w], 30, width, height);
  }

  setVisible(visible: boolean) {
    this.visible = visible;
    if (visible) this.start();
  }

  dispose() {
    this.running = false;
    cancelAnimationFrame(this.frame);
    this.resizeObserver.disconnect();
    this.controls.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  private start() {
    if (this.running || !this.visible || document.hidden) return;
    this.running = true;
    const tick = () => {
      if (!this.visible || document.hidden) {
        this.running = false;
        return;
      }
      this.update();
      this.renderer.render(this.scene, this.camera);
      this.reportHotspots();
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  private update() {
    // The status light: green at the lock stop, like the real lock when a finger opens it.
    if (this.light && this.halo) {
      const on = this.stop === 1 ? 1 : 0;
      this.halo.opacity += (on - this.halo.opacity) * 0.08;
      this.light.emissiveIntensity = this.halo.opacity * 2.4;
    }
    if (this.settled) {
      this.controls.update();
      const offset = this.camera.position.clone().sub(this.controls.target);
      this.aimLight(Math.atan2(offset.x, offset.z) / DEG);
      return;
    }
    const goal = this.stops[this.stop];
    const k = 0.075; // fraction of the way per frame: about half a second to arrive
    let az = goal.az - this.current.az;
    az = ((az + 540) % 360) - 180; // the short way round
    this.current.az += az * k;
    this.current.el += (goal.el - this.current.el) * k;
    this.current.dist += (goal.dist - this.current.dist) * k;
    this.current.frame += (goal.frame - this.current.frame) * k;
    this.current.target = this.current.target.map((t, i) => t + (goal.target[i] - t) * k) as Stop['target'];
    this.place(this.current);
    const arrived = Math.abs(az) < 0.3 && Math.abs(goal.dist - this.current.dist) < 0.002;
    if (arrived && this.stop === 0) {
      this.settled = true;
      this.controls.target.set(...goal.target);
      this.controls.enabled = true;
    }
  }

  private place(stop: Stop) {
    const [tx, ty, tz] = stop.target;
    const az = stop.az * DEG;
    const el = stop.el * DEG;
    const dist = Math.max(stop.dist, this.fitDistance(stop.frame));
    this.camera.position.set(
      tx + dist * Math.cos(el) * Math.sin(az),
      ty + dist * Math.sin(el),
      tz + dist * Math.cos(el) * Math.cos(az),
    );
    this.camera.lookAt(tx, ty, tz);
    this.aimLight(stop.az);
  }

  /** The distance at which `width` metres fill 90% of the view across. */
  private fitDistance(width: number) {
    const halfV = (this.camera.fov * DEG) / 2;
    const halfH = Math.atan(Math.tan(halfV) * this.camera.aspect);
    return width / 0.9 / (2 * Math.tan(halfH));
  }

  /** The key light stays in front of the camera and to its side, so the side we see is lit. */
  private aimLight(azimuth: number) {
    const a = (azimuth - 40) * DEG;
    this.key.position.set(0.7 * Math.sin(a), 0.85, 0.7 * Math.cos(a));
  }

  /** Where the user left the camera, so leaving the hero starts from there. */
  private readCamera() {
    const t = this.controls.target;
    const offset = this.camera.position.clone().sub(t);
    const dist = offset.length();
    this.current = {
      az: Math.atan2(offset.x, offset.z) / DEG,
      el: Math.asin(offset.y / dist) / DEG,
      dist,
      frame: 0, // the distance already is what the user chose
      target: [t.x, t.y, t.z],
    };
  }

  private reportHotspots() {
    const positions = new Map<string, Vector2 | null>();
    const rect = this.container.getBoundingClientRect();
    const toCamera = new Vector3();
    for (const spot of this.hotspots) {
      const at = new Vector3(...spot.at);
      toCamera.copy(this.camera.position).sub(at).normalize();
      const facing = toCamera.dot(new Vector3(...spot.normal)) > 0.25;
      if (this.stop !== 0 || !facing) {
        positions.set(spot.id, null);
        continue;
      }
      const p = at.project(this.camera);
      positions.set(spot.id, new Vector2(((p.x + 1) / 2) * rect.width, ((1 - p.y) / 2) * rect.height));
    }
    this.onHotspots(positions);
  }

  private resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    // Keep the whole bag in frame on narrow screens.
    this.camera.fov = w / h < 0.9 ? 38 : 28;
    this.camera.updateProjectionMatrix();
    this.controls.maxDistance = Math.max(0.85, this.fitDistance(this.stops[0].frame) * 1.15);
    if (!this.settled) this.place(this.current);
  }
}
