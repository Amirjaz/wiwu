// The bag in 3D: a studio scene, a camera that moves to each side the parts section asks for (and to a
// single part), numbered pins that move with the bag, and dragging to turn it. Loaded only when the
// device can take it (see islands/bag3d.ts).
import {
  AdditiveBlending, CanvasTexture, Color, DirectionalLight, Mesh, MeshBasicMaterial,
  MeshPhysicalMaterial, MeshStandardMaterial, NeutralToneMapping, PCFSoftShadowMap, PerspectiveCamera, PlaneGeometry,
  PMREMGenerator, Raycaster, Scene, ShadowMaterial, SRGBColorSpace, Vector2, Vector3, WebGLRenderer, type Material,
  type Texture,
} from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { pebbleNormalMap } from './textures';
import { buildFarEnd, buildLock, buildPlate, buildZipper, type Details } from './details';

/** What tools/build_model.py writes next to each model. */
interface ModelInfo {
  grainRepeat: number;
  details?: Details;
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

/** A numbered pin on the bag: the point, and the way its surface faces (the pin hides when that turns
 *  away from the camera). */
export interface Pin {
  at: [number, number, number];
  normal: [number, number, number];
}

const DEG = Math.PI / 180;

// The bag is 25 x 14 x 7.7 cm, resting on y = 0, front facing +z, the lock end at -x. A view per tab of
// the parts section; the side's is aimed squarely at the lock module once the model is in (addDetails).
export const VIEWS: Record<string, Stop> = {
  front: { az: -30, el: 16, dist: 0.3, frame: 0.28, target: [0, 0.068, 0] }, // the front and the lock end
  side: { az: -80, el: 8, dist: 0.3, frame: 0.17, target: [-0.1, 0.07, 0] }, // the lock
  back: { az: 194, el: 14, dist: 0.3, frame: 0.34, target: [0.01, 0.072, 0] }, // with room for its shadow
};

const copy = (stop: Stop): Stop => ({ ...stop, target: [...stop.target] });

const BLACK_LEATHER = new Color('#2b2c2f');
const GUNMETAL = new Color('#4a4d52');
// The zipper and far-end hardware on the coloured bags, where the photo's own metal doesn't show through.
const SILVER = new Color('#8d9095');

/** The texture's typical brightness (linear light): the median of a small copy, the empty atlas left out. */
function medianLuminance(texture: Texture) {
  const image = texture.image as CanvasImageSource | undefined;
  if (!image) return 0.01;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return 0.01;
  ctx.drawImage(image, 0, 0, 64, 64);
  const data = ctx.getImageData(0, 0, 64, 64).data;
  const linear = (v: number) => ((v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  const lums: number[] = [];
  for (let i = 0; i < data.length; i += 4) {
    const l = 0.2126 * linear(data[i]) + 0.7152 * linear(data[i + 1]) + 0.0722 * linear(data[i + 2]);
    if (data[i + 3] > 0 && l > 0.0004) lums.push(l);
  }
  lums.sort((a, b) => a - b);
  return lums.length ? Math.max(lums[lums.length >> 1], 0.002) : 0.01;
}

export class BagScene {
  private renderer: WebGLRenderer;
  private key!: DirectionalLight;
  private light: MeshStandardMaterial | null = null;
  private halo: MeshBasicMaterial | null = null;
  private scene = new Scene();
  private camera = new PerspectiveCamera(28, 1, 0.01, 10);
  private controls: OrbitControls;
  private views: Record<string, Stop> = Object.fromEntries(Object.entries(VIEWS).map(([k, v]) => [k, copy(v)]));
  private view = 'front';
  private goal: Stop = copy(VIEWS.front);
  private current: Stop = copy(VIEWS.front);
  private pins: Pin[] = [];
  private settled = false; // arrived, and handed over to the user's drag
  private running = false;
  private visible = true;
  private frame = 0;
  private onPins: (positions: (Vector2 | null)[]) => void;
  private resizeObserver: ResizeObserver;
  // The colour: the model's own textured parts, and the shader's switch from the photo's colours to a tint
  // (with the photo's typical brightness, so a tint keeps the photo's light and dark around it).
  private parts: Record<string, MeshStandardMaterial> = {};
  private tint = { value: 0 };
  private photoLum = { value: 0.01 };
  private swatch = '#17181b';
  private zipperTape: MeshStandardMaterial | null = null;

  constructor(
    private container: HTMLElement,
    private options: { reducedMotion: boolean; small: boolean; onPins: BagScene['onPins'] },
  ) {
    this.onPins = options.onPins;
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

    // No zoom and no auto-turn: the pins should stay where people can read them. The distance limits only
    // keep a drag from changing how close a view is.
    this.controls = new OrbitControls(this.camera, canvas);
    Object.assign(this.controls, {
      enableDamping: true, dampingFactor: 0.08, enablePan: false, enableZoom: false, rotateSpeed: 0.7,
      minDistance: 0.05, maxDistance: 3, minPolarAngle: 20 * DEG, maxPolarAngle: 88 * DEG,
    });
    // Vertical swipes keep scrolling the page; sideways ones turn the bag. The mouse wheel over the bag
    // scrolls the page like everywhere else.
    canvas.style.touchAction = 'pan-y';
    this.controls.enabled = false;

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
    this.place(this.current);
  }

  /** url: the .glb (its address may carry a ?v= version); its .json sidecar sits next to it. */
  async load(url: string, onProgress?: (fraction: number | null) => void): Promise<void> {
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    const [gltf, info] = await Promise.all([
      loader.loadAsync(url, (event) => onProgress?.(event.lengthComputable ? event.loaded / event.total : null)),
      fetch(url.replace(/[.]glb(?=$|[?])/, '.json'))
        .then((r) => (r.ok ? (r.json() as Promise<ModelInfo>) : null))
        .catch(() => null),
    ]);
    // The colour is the photos' (of the black bag), baked into one texture all parts share. The parts only
    // differ in how they take the studio light; a faint grain makes highlights break up like on real
    // pebbled PU. Another colour tints the texture (setColor).
    let photo: Texture | null = null;
    gltf.scene.traverse((node) => {
      if (!photo && node instanceof Mesh) photo = (node.material as MeshStandardMaterial).map;
    });
    if (photo) this.photoLum.value = medianLuminance(photo);
    const grain = pebbleNormalMap(this.options.small ? 256 : 512);
    const repeat = info?.grainRepeat ?? 10;
    grain.repeat.set(repeat, repeat);
    const leather = this.tinted(new MeshPhysicalMaterial({
      map: photo, roughness: 0.62, normalMap: grain, normalScale: new Vector2(0.16, 0.16),
      clearcoat: 0.12, clearcoatRoughness: 0.6,
    }));
    const materials: Record<string, MeshStandardMaterial> = {
      leather,
      // The front is the same pebbled PU as the rest (the maker's photos; the client's front photo was
      // too soft to show the grain, so it used to be a smooth panel).
      front: leather,
      tape: this.tinted(new MeshStandardMaterial({ map: photo, roughness: 0.85 })),
      teeth: this.tinted(new MeshStandardMaterial({ map: photo, metalness: 0.2, roughness: 0.45 })),
      metal: this.tinted(new MeshStandardMaterial({ map: photo, metalness: 0.2, roughness: 0.36 })),
    };
    this.parts = materials;
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
    this.setColor(this.swatch);
    this.renderer.render(this.scene, this.camera);
    this.renderer.domElement.classList.remove('opacity-0');
    this.start();
  }

  /** The lock module, the zipper, the far end's hardware and the brand plate, modelled from the photos'
   *  measurements. */
  private addDetails(details: Details) {
    // The side view looks squarely at the module, a little from the front, from just above its middle
    // (so the zipper running up from it stays in the picture).
    const [nx, ny, nz] = details.module.n;
    const [ox, oy, oz] = details.module.origin;
    this.views.side = {
      ...this.views.side,
      az: (Math.atan2(nx, nz) * 180) / Math.PI + 12,
      el: Math.max(6, (Math.asin(ny) * 180) / Math.PI),
      target: [ox + nx * 0.004, oy + 0.022, oz + nz * 0.004],
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

    const tape = (this.zipperTape = new MeshStandardMaterial({ color: '#141518', roughness: 0.95 }));
    this.scene.add(buildZipper(details.zipper, tape));
    this.scene.add(buildFarEnd(details.farEnd));
    if (details.plate) {
      const anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
      this.scene.add(buildPlate(details.plate, this.options.small ? 256 : 512, anisotropy));
    }
  }

  /** The bag in a colour (its swatch from the panel, #rrggbb). The photos are of the black bag: black
   *  keeps them as they are. Any other colour tints the leather by the photo's own light and dark (its
   *  grain, seams and shading stay), the zipper tape a darker shade of it, and the hardware silver, as on
   *  the maker's photos of the brown and silver-white bags. */
  setColor(swatch: string) {
    this.swatch = swatch;
    const color = new Color(swatch);
    const black = color.r * 0.2126 + color.g * 0.7152 + color.b * 0.0722 < 0.03; // linear light
    this.tint.value = 1;
    const { leather, tape, teeth, metal } = this.parts;
    if (!leather) return; // set again once the model is in (load)
    leather.color.copy(black ? BLACK_LEATHER : color);
    tape.color.copy(black ? new Color('#16171a') : color.clone().multiplyScalar(0.18));
    teeth.color.copy(black ? GUNMETAL : SILVER);
    metal.color.copy(black ? GUNMETAL : SILVER);
    // The modelled parts (lock, zipper, far end) carry their two looks (details.ts).
    this.scene.traverse((node) => {
      if (!(node instanceof Mesh)) return;
      for (const material of [node.material as Material | Material[]].flat()) {
        const finish = material.userData.finish as { black: string; light: string } | undefined;
        if (finish) (material as MeshStandardMaterial).color.set(black ? finish.black : finish.light);
      }
    });
    if (this.zipperTape) this.zipperTape.color.copy(black ? new Color('#141518') : color.clone().multiplyScalar(0.18));
  }

  /** A material whose texture can be swapped for a tint of it: the photo's brightness relative to its
   *  usual, times the material's colour (setColor). With the tint off it's the material as three.js has it. */
  private tinted<T extends MeshStandardMaterial>(material: T): T {
    material.onBeforeCompile = (shader) => {
      shader.uniforms.uTint = this.tint;
      shader.uniforms.uPhotoLum = this.photoLum;
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', '#include <common>\nuniform float uTint;\nuniform float uPhotoLum;')
        .replace('#include <map_fragment>', `#ifdef USE_MAP
  vec4 sampledDiffuseColor = texture2D( map, vMapUv );
  float ratio = dot( sampledDiffuseColor.rgb, vec3( 0.2126, 0.7152, 0.0722 ) ) / uPhotoLum;
  // Softened: the photo's lighting reads much stronger on a light leather than on the black it was taken on.
  vec3 tinted = diffuseColor.rgb * clamp( pow( ratio, 0.55 ), 0.72, 1.2 );
  // Far brighter than the leather in the photo: the metal (the pulls, the snap), which keeps the
  // photo's own colour on every bag.
  vec3 metal = sampledDiffuseColor.rgb * 1.3;
  vec3 recoloured = mix( tinted, metal, smoothstep( 3.0, 6.0, ratio ) );
  diffuseColor.rgb = mix( diffuseColor.rgb * sampledDiffuseColor.rgb, recoloured, uTint );
  diffuseColor.a *= sampledDiffuseColor.a;
#endif`);
    };
    material.customProgramCacheKey = () => 'bag-tinted';
    return material;
  }

  /** Turn to a side (a key of VIEWS) and show its pins. `instant`: be there at once (the first view). */
  show(view: string, pins: Pin[], instant = false) {
    this.view = view;
    this.pins = pins;
    this.moveTo(this.views[view] ?? this.views.front, instant);
  }

  /** Turn the bag toward a pin's part: to face it, keeping up to 15° of the side's own angle so the bag
   *  doesn't go flat, and aimed a little toward it. The whole bag stays in the picture (a closer look
   *  cut it off at the stage's edges). */
  focus(pin: Pin) {
    const [nx, ny, nz] = pin.normal;
    const view = this.views[this.view] ?? this.views.front;
    const facing = Math.atan2(nx, nz) / DEG;
    const turn = ((view.az - facing + 540) % 360) - 180;
    this.moveTo({
      ...view,
      // A part facing up (the zipper on top) is looked at from higher, from where the bag is seen now.
      az: Math.hypot(nx, nz) > 0.5 ? facing + Math.max(-15, Math.min(15, turn)) : this.goal.az,
      el: ny > 0.7 ? 34 : view.el,
      target: view.target.map((c, i) => c + (pin.at[i] - c) * 0.2) as Stop['target'],
    });
  }

  private moveTo(stop: Stop, instant = false) {
    if (this.settled) this.readCamera();
    this.goal = copy(stop);
    this.settled = false;
    this.controls.enabled = false;
    if (instant || this.options.reducedMotion) this.current = copy(stop);
    this.start();
  }

  /** Development only: the surface under a rough pin, found from outside along its normal, for
   *  views.PARTS. Returns the hit and the face's normal, or null if the ray misses. */
  debugSnap(at: [number, number, number], normal: [number, number, number]) {
    const dir = new Vector3(...normal).normalize();
    const ray = new Raycaster(new Vector3(...at).addScaledVector(dir, 0.15), dir.clone().negate(), 0, 0.3);
    const hit = ray.intersectObject(this.scene, true).find((h) => h.object instanceof Mesh && h.face);
    if (!hit?.face) return null;
    const n = hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
    const round = (v: Vector3, k: number) => v.toArray().map((x) => Number(x.toFixed(k)));
    return { at: round(hit.point, 4), normal: round(n, 2) };
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
      this.reportPins();
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  private update() {
    // The status light: green on the lock's side, like the real lock when a finger opens it.
    if (this.light && this.halo) {
      const on = this.view === 'side' ? 1 : 0;
      this.halo.opacity += (on - this.halo.opacity) * 0.08;
      this.light.emissiveIntensity = this.halo.opacity * 2.4;
    }
    if (this.settled) {
      this.controls.update();
      const offset = this.camera.position.clone().sub(this.controls.target);
      this.aimLight(Math.atan2(offset.x, offset.z) / DEG);
      return;
    }
    const goal = this.goal;
    const k = 0.075; // fraction of the way per frame: about half a second to arrive
    let az = goal.az - this.current.az;
    az = ((az + 540) % 360) - 180; // the short way round
    this.current.az += az * k;
    this.current.el += (goal.el - this.current.el) * k;
    this.current.dist += (goal.dist - this.current.dist) * k;
    this.current.frame += (goal.frame - this.current.frame) * k;
    this.current.target = this.current.target.map((t, i) => t + (goal.target[i] - t) * k) as Stop['target'];
    this.place(this.current);
    const near = (a: number, b: number, d: number) => Math.abs(a - b) < d;
    if (near(az, 0, 0.3) && near(goal.el, this.current.el, 0.3) && near(goal.dist, this.current.dist, 0.002) &&
      near(goal.frame, this.current.frame, 0.002) && goal.target.every((t, i) => near(t, this.current.target[i], 0.0005))) {
      this.settled = true;
      this.controls.target.set(...this.current.target);
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

  /** Where the user left the camera, so the next move starts from there. */
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

  /** Where each pin is on the stage, in pixels, or null where its side faces away (or it's off the
   *  stage, which would put it over the page around). */
  private reportPins() {
    const { clientWidth: w, clientHeight: h } = this.container;
    const toCamera = new Vector3();
    const at = new Vector3();
    this.onPins(this.pins.map((pin) => {
      at.set(...pin.at);
      toCamera.copy(this.camera.position).sub(at).normalize();
      if (toCamera.dot(new Vector3(...pin.normal)) < 0.2) return null;
      const p = at.project(this.camera);
      const x = ((p.x + 1) / 2) * w;
      const y = ((1 - p.y) / 2) * h;
      return x < 12 || x > w - 12 || y < 12 || y > h - 12 ? null : new Vector2(x, y);
    }));
  }

  private resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    // Keep the whole bag in frame on narrow screens.
    this.camera.fov = w / h < 0.9 ? 38 : 28;
    this.camera.updateProjectionMatrix();
    if (!this.settled) this.place(this.current);
  }
}
