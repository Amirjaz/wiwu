// The bag in 3D: a studio scene, drag to turn it, hotspots, and a camera that moves to each stop of
// the scroll tour. Loaded only when the device can take it (see islands/hero.ts).
import {
  ACESFilmicToneMapping, BoxGeometry, Color, DirectionalLight, Group, Mesh, MeshBasicMaterial, MeshPhysicalMaterial,
  MeshStandardMaterial, PCFSoftShadowMap, PerspectiveCamera, PlaneGeometry, PMREMGenerator, Raycaster, Scene,
  ShadowMaterial, SRGBColorSpace, Vector2, Vector3, WebGLRenderer, type Material, type Object3D,
} from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { pebbleNormalMap, teethNormalMap } from './textures';

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
  { az: -48, el: 14, dist: 0.5, frame: 0.33, target: [0, 0.072, 0] }, // the hero: front and the lock end
  { az: -80, el: 8, dist: 0.3, frame: 0.15, target: [-0.1, 0.06, 0] }, // the lock
  { az: 194, el: 12, dist: 0.5, frame: 0.33, target: [0, 0.08, 0] }, // the back pocket
  { az: 160, el: 22, dist: 0.42, frame: 0.29, target: [-0.01, 0.05, -0.02] }, // the wrist strap
  { az: 22, el: 30, dist: 0.32, frame: 0.2, target: [0.02, 0.085, 0.02] }, // the leather, in raking light
];

export const HOTSPOTS: Hotspot[] = [
  { id: 'lock', at: [-0.129, 0.05, 0], normal: [-1, 0, 0] },
  { id: 'leather', at: [-0.03, 0.085, 0.034], normal: [0, 0, 1] },
  { id: 'pocket', at: [0.02, 0.118, -0.034], normal: [0, 0, -1] },
];

export class HeroScene {
  private renderer: WebGLRenderer;
  private key!: DirectionalLight;
  private led: MeshBasicMaterial | null = null;
  private scene = new Scene();
  private camera = new PerspectiveCamera(28, 1, 0.01, 10);
  private controls: OrbitControls;
  private stop = 0;
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
    this.renderer.toneMapping = ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFSoftShadowMap;
    const canvas = this.renderer.domElement;
    canvas.className = 'absolute inset-0 size-full opacity-0 transition-opacity duration-700';
    canvas.setAttribute('aria-hidden', 'true');
    // Fade the canvas out at its edges: a close-up or a long shadow never ends in a hard line.
    const fade = 'radial-gradient(ellipse 72% 70% at 50% 50%, #000 62%, transparent 100%)';
    canvas.style.maskImage = fade;
    canvas.style.webkitMaskImage = fade;
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
      minDistance: 0.36, maxDistance: 0.85, minPolarAngle: 20 * DEG, maxPolarAngle: 88 * DEG,
      autoRotate: !options.reducedMotion, autoRotateSpeed: -0.6,
    });
    // Vertical swipes keep scrolling the page; sideways ones turn the bag. No pinch-zoom on phones.
    canvas.style.touchAction = 'pan-y';
    this.controls.enableZoom = !options.small;
    this.controls.enabled = false;
    this.controls.addEventListener('start', () => (this.controls.autoRotate = false));

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
    this.place(this.current);
  }

  async load(url: string): Promise<void> {
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    const gltf = await loader.loadAsync(url);
    const grain = pebbleNormalMap(this.options.small ? 256 : 512);
    const materials: Record<string, Material> = {
      leather: new MeshPhysicalMaterial({
        color: '#1b1c1f', roughness: 0.58, normalMap: grain, normalScale: new Vector2(0.45, 0.45),
        clearcoat: 0.22, clearcoatRoughness: 0.55, sheen: 0.35, sheenRoughness: 0.7, sheenColor: new Color('#6c7280'),
      }),
      tape: new MeshStandardMaterial({ color: '#121315', roughness: 0.92 }),
      teeth: new MeshStandardMaterial({ color: '#3d3e42', metalness: 0.8, roughness: 0.45, normalMap: teethNormalMap(), normalScale: new Vector2(0.45, 0.45) }),
      metal: new MeshStandardMaterial({ color: '#73757b', metalness: 0.9, roughness: 0.45 }),
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
    this.addSensor(gltf.scene);
    this.renderer.render(this.scene, this.camera);
    this.renderer.domElement.classList.remove('opacity-0');
    this.start();
  }

  /** The fingerprint sensor and its status light: too small and flat for the AI shape to have caught,
   *  so they're drawn here on the lock module's face (found by casting a ray at it). */
  private addSensor(model: Object3D) {
    const centre = new Vector3(-0.2, 0.039, 0);
    const hit = new Raycaster(centre, new Vector3(1, 0, 0)).intersectObject(model, true)[0];
    if (!hit) return;
    const face = hit.point.x - 0.0004;
    const sensor = new Group();
    const rim = new Mesh(new BoxGeometry(0.0006, 0.0135, 0.0135),
      new MeshStandardMaterial({ color: '#b07a5a', metalness: 1, roughness: 0.3 }));
    const glass = new Mesh(new BoxGeometry(0.0008, 0.011, 0.011),
      new MeshPhysicalMaterial({ color: '#0b0c0e', roughness: 0.15, clearcoat: 1, clearcoatRoughness: 0.1 }));
    glass.position.x = -0.0002;
    this.led = new MeshBasicMaterial({ color: '#2b2d31' });
    const led = new Mesh(new BoxGeometry(0.0006, 0.0016, 0.008), this.led);
    led.position.y = 0.0135;
    sensor.add(rim, glass, led);
    sensor.position.set(face, centre.y, centre.z);
    this.scene.add(sensor);
  }

  /** Move to a tour stop (0 = the hero, where the user can drag). */
  goTo(index: number) {
    if (index === this.stop) return;
    if (this.stop === 0 && this.settled) this.readCamera();
    this.stop = index;
    this.settled = false;
    this.controls.enabled = false;
    if (this.options.reducedMotion) this.current = { ...STOPS[index], target: [...STOPS[index].target] };
    this.start();
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
    if (this.led) {
      const goal = new Color(this.stop === 1 ? '#19c37d' : '#2b2d31');
      this.led.color.lerp(goal, 0.08);
    }
    if (this.settled) {
      this.controls.update();
      const offset = this.camera.position.clone().sub(this.controls.target);
      this.aimLight(Math.atan2(offset.x, offset.z) / DEG);
      return;
    }
    const goal = STOPS[this.stop];
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
    for (const spot of HOTSPOTS) {
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
    this.controls.maxDistance = Math.max(0.85, this.fitDistance(STOPS[0].frame) * 1.15);
    if (!this.settled) this.place(this.current);
  }
}
