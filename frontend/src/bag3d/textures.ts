// The leather grain's normal map, drawn in the browser instead of downloaded. It tiles seamlessly;
// the model's .json says how often it repeats across the texture atlas (one tile = 4 cm).
import { CanvasTexture, LinearFilter, LinearMipmapLinearFilter, NoColorSpace, RepeatWrapping, type Texture } from 'three';

function hash(x: number, y: number, seed: number): number {
  let h = (x * 374761393 + y * 668265263 + seed * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

/** Height field → tangent-space normal map (wrapping at the edges, so it tiles). */
export function toNormalMap(height: Float32Array, size: number, strength: number): Texture {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const image = ctx.createImageData(size, size);
  const at = (x: number, y: number) => height[((y + size) % size) * size + ((x + size) % size)];
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = (at(x + 1, y) - at(x - 1, y)) * strength;
      const dy = (at(x, y + 1) - at(x, y - 1)) * strength;
      const len = Math.hypot(dx, dy, 1);
      const i = (y * size + x) * 4;
      image.data[i] = ((-dx / len) * 0.5 + 0.5) * 255;
      image.data[i + 1] = ((dy / len) * 0.5 + 0.5) * 255;
      image.data[i + 2] = ((1 / len) * 0.5 + 0.5) * 255;
      image.data[i + 3] = 255;
    }
  }
  ctx.putImageData(image, 0, 0);
  const texture = new CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = RepeatWrapping;
  texture.colorSpace = NoColorSpace;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.magFilter = LinearFilter;
  return texture;
}

/** Pebbled leather: rounded cells (Worley F2 - F1), about 1.5 mm across at 4 cm per tile. */
export function pebbleNormalMap(size = 512, cells = 26): Texture {
  const height = new Float32Array(size * size);
  const cell = size / cells;
  const points: [number, number][] = [];
  for (let cy = 0; cy < cells; cy++) {
    for (let cx = 0; cx < cells; cx++) {
      points.push([(cx + 0.15 + hash(cx, cy, 1) * 0.7) * cell, (cy + 0.15 + hash(cx, cy, 2) * 0.7) * cell]);
    }
  }
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const gx = Math.floor(x / cell);
      const gy = Math.floor(y / cell);
      let f1 = Infinity;
      let f2 = Infinity;
      for (let oy = -1; oy <= 1; oy++) {
        for (let ox = -1; ox <= 1; ox++) {
          const nx = (gx + ox + cells) % cells;
          const ny = (gy + oy + cells) % cells;
          const [px, py] = points[ny * cells + nx];
          // The neighbour's point, moved across the edge when the cell wrapped.
          const wx = px + (gx + ox - nx) * cell;
          const wy = py + (gy + oy - ny) * cell;
          const d = Math.hypot(x - wx, y - wy);
          if (d < f1) {
            f2 = f1;
            f1 = d;
          } else if (d < f2) f2 = d;
        }
      }
      // Domed pebbles with soft creases between them.
      height[y * size + x] = Math.min(1, (f2 - f1) / (cell * 0.55)) ** 0.6;
    }
  }
  return toNormalMap(height, size, 2.2);
}
