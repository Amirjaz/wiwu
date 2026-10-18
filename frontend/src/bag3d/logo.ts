// The brand plate's face, drawn in the browser: WiWU's emblem (a tall hexagon round an i) and name, traced
// from the maker's logo on wiwu.com and laid out as on the plate in their front photo
// (media/source-photos/wiwu/black-front.jpg): the emblem above, WIWU below, both raised from the plate.
// The glyphs' coordinates are the logo file's pixels (1200 px square).
import { CanvasTexture, LinearFilter, LinearMipmapLinearFilter, NoColorSpace, type Texture } from 'three';
import { toNormalMap } from './textures';

type Pt = [number, number];
type Box = [number, number, number, number]; // x, y, width, height

// The emblem: the hexagon's centre line, the i's dot and stem.
const HEXAGON: Pt[] = [[600, 313.5], [676.5, 365], [676.5, 526], [600, 577.5], [523.5, 526], [523.5, 365]];
const HEX_LINE = 11; // the logo file's line is 8 px; raised on the plate it reads bolder
const I_DOT: Box = [589, 368, 22, 20];
const I_STEM: Box = [589, 404, 22, 125];
// The name. The plate has a capital I where the logo has its red-dotted i.
const W: Pt[] = [[155, 676], [183, 676], [232, 848], [282, 676], [310, 676], [359, 848], [409, 676], [437, 676],
  [376, 890], [345, 890], [296, 729], [247, 890], [217, 890]];
const SECOND_W = 416; // how far right the second W is
const I_CAP: Box = [492, 676, 33, 214];
const CAPS = { top: 676, bottom: 890, left: 155, right: 1044.5 };

// Where they sit, as fractions of the plate's side (the maker's photo): the hexagon's outer edge, the capitals.
const EMBLEM = { top: 0.146, height: 0.488 };
const NAME = { top: 0.728, height: 0.162 };

function letterU(ctx: CanvasRenderingContext2D) {
  ctx.moveTo(883, 676);
  ctx.lineTo(883, 813);
  ctx.ellipse(963.75, 813, 80.75, 76.5, 0, Math.PI, 0, true);
  ctx.lineTo(1044.5, 676);
  ctx.lineTo(1016, 676);
  ctx.lineTo(1016, 822);
  ctx.ellipse(964, 822, 52, 45, 0, 0, Math.PI, false);
  ctx.lineTo(912, 676);
  ctx.closePath();
}

/** The emblem and the name in white on black, filling a square canvas as they fill the plate. */
function drawLogo(ctx: CanvasRenderingContext2D, size: number) {
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, size, size);
  ctx.fillStyle = ctx.strokeStyle = '#fff';

  const ys = HEXAGON.map(([, y]) => y);
  const top = Math.min(...ys) - HEX_LINE / 2;
  const k = (EMBLEM.height * size) / (Math.max(...ys) + HEX_LINE / 2 - top);
  ctx.setTransform(k, 0, 0, k, size / 2 - 600 * k, EMBLEM.top * size - top * k);
  ctx.lineWidth = HEX_LINE;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  HEXAGON.forEach(([x, y]) => ctx.lineTo(x, y));
  ctx.closePath();
  ctx.stroke();
  ctx.fillRect(...I_DOT);
  ctx.fillRect(...I_STEM);

  const kn = (NAME.height * size) / (CAPS.bottom - CAPS.top);
  ctx.setTransform(kn, 0, 0, kn, size / 2 - ((CAPS.left + CAPS.right) / 2) * kn, NAME.top * size - CAPS.top * kn);
  ctx.beginPath();
  for (const dx of [0, SECOND_W]) {
    W.forEach(([x, y], i) => (i ? ctx.lineTo(x + dx, y) : ctx.moveTo(x + dx, y)));
    ctx.closePath();
  }
  ctx.rect(...I_CAP);
  letterU(ctx);
  ctx.fill();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
}

/** Two passes of a separable box blur (close to a Gaussian), clamped at the edges. */
function blur(src: Float32Array, size: number, r: number): Float32Array {
  let a = Float32Array.from(src);
  let b = new Float32Array(src.length);
  const norm = 1 / (2 * r + 1);
  for (let pass = 0; pass < 4; pass++) {
    const step = pass % 2 === 0 ? 1 : size; // along the rows, then down the columns
    const across = pass % 2 === 0 ? size : 1;
    for (let line = 0; line < size; line++) {
      const base = line * across;
      let sum = 0;
      for (let i = -r; i <= r; i++) sum += a[base + Math.min(size - 1, Math.max(0, i)) * step];
      for (let i = 0; i < size; i++) {
        b[base + i * step] = sum * norm;
        sum += a[base + Math.min(size - 1, i + r + 1) * step] - a[base + Math.max(0, i - r) * step];
      }
    }
    [a, b] = [b, a];
  }
  return a;
}

function hash(x: number, y: number): number {
  let h = (x * 374761393 + y * 668265263) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

/** A grey canvas, one value (0..1) per pixel. */
function greyCanvas(size: number, value: (i: number) => number) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const image = ctx.createImageData(size, size);
  for (let i = 0; i < size * size; i++) {
    const v = value(i) * 255;
    image.data[i * 4] = image.data[i * 4 + 1] = image.data[i * 4 + 2] = v;
    image.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
  return canvas;
}

/** A canvas halved down to one pixel: [the canvas, its half, its quarter, ...]. */
function halvings(canvas: HTMLCanvasElement): HTMLCanvasElement[] {
  const chain = [canvas];
  for (let s = canvas.width / 2; s >= 1; s /= 2) {
    const half = document.createElement('canvas');
    half.width = half.height = s;
    const ctx = half.getContext('2d')!;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(chain[chain.length - 1], 0, 0, s, s);
    chain.push(half);
  }
  return chain;
}

function texture(canvas: HTMLCanvasElement, anisotropy: number) {
  const t = new CanvasTexture(canvas);
  t.colorSpace = NoColorSpace; // the values are linear light (the colour) and roughness
  t.minFilter = LinearMipmapLinearFilter;
  t.magFilter = LinearFilter;
  t.anisotropy = anisotropy;
  return t;
}

// From this size down the plate is a few dozen pixels across on screen (the parts section's front view,
// phones): the colour's smaller copies are drawn by hand from a version whose logo is brighter, bolder and
// has no dark crease, which would otherwise average out its light, so the emblem and name still read as
// light marks on the plate, as in the maker's small photos.
const FAR_MIP = 128;

/** The plate face's textures, `size` pixels square (a power of two): the colour (brushed satin, the raised
 *  logo a little brighter with a dark crease round its foot), the relief as a normal map, and the
 *  roughness (the raised logo polished). */
export function plateFace(size: number, anisotropy = 1): { map: Texture; normalMap: Texture; roughnessMap: Texture } {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
  drawLogo(ctx, size);
  const pixels = ctx.getImageData(0, 0, size, size).data;
  const mask = new Float32Array(size * size);
  for (let i = 0; i < mask.length; i++) mask[i] = pixels[i * 4] / 255;

  const height = blur(mask, size, Math.max(1, Math.round(size / 300))); // the raised parts' rounded edges
  const wide = blur(mask, size, Math.max(2, Math.round(size / 110)));
  // Brushed across: a streak per row, and a finer grain.
  const streak = (i: number) => (hash(0, Math.floor(i / size)) - 0.5) * 0.035 + (hash(i % size, Math.floor(i / size)) - 0.5) * 0.02;
  const near = halvings(greyCanvas(size, (i) => {
    const crease = Math.max(0, wide[i] - height[i]);
    return Math.min(1, Math.max(0, 0.74 + 0.3 * height[i] - 0.8 * crease + streak(i) * (1 - height[i])));
  }));
  const far = halvings(greyCanvas(size, (i) => Math.min(1, 0.7 + 0.6 * Math.max(height[i], wide[i]))));
  const map = texture(near[0], anisotropy);
  map.mipmaps = near.map((level, i) => (level.width <= FAR_MIP ? far[i] : level));
  map.generateMipmaps = false;
  const roughnessMap = texture(greyCanvas(size, (i) => 0.5 - 0.2 * height[i] + streak(i) * 0.8), anisotropy);
  const normalMap = toNormalMap(height, size, size / 200);
  normalMap.anisotropy = anisotropy;
  return { map, normalMap, roughnessMap };
}
