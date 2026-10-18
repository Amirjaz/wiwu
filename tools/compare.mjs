// Renders the site's 3D bag from each source photo's camera and puts it next to the photo, to check
// the model against reality detail by detail.
//
//   node tools/compare.mjs [http://127.0.0.1:8030/] [out-dir]
//
// Needs the dev servers running (the page exposes window.__bag in development) and headless Microsoft
// Edge through patchright (on this machine it comes with the CodeGPT VS Code extension). Writes
// <out-dir>/<photo>-render.jpg, the same size as the photo, to lay over it.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const url = process.argv[2] ?? 'http://127.0.0.1:8030/';
const out = process.argv[3] ?? path.join(root, 'media', '3d', 'compare');
fs.mkdirSync(out, { recursive: true });

const cams = JSON.parse(fs.readFileSync(path.join(root, 'media', '3d', 'cameras.json'), 'utf8'));
const model = JSON.parse(fs.readFileSync(path.join(root, 'frontend', 'public', 'models', 'alpha.json'), 'utf8'));
const { centre, scale } = model.frame;

function rodrigues([x, y, z]) {
  const th = Math.hypot(x, y, z);
  if (th < 1e-12) return [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  const [kx, ky, kz] = [x / th, y / th, z / th];
  const c = Math.cos(th), s = Math.sin(th), v = 1 - c;
  return [
    [kx * kx * v + c, kx * ky * v - kz * s, kx * kz * v + ky * s],
    [ky * kx * v + kz * s, ky * ky * v + c, ky * kz * v - kx * s],
    [kz * kx * v - ky * s, kz * ky * v + kx * s, kz * kz * v + c],
  ];
}

function quaternionFromColumns(xa, ya, za) {
  const m = [[xa[0], ya[0], za[0]], [xa[1], ya[1], za[1]], [xa[2], ya[2], za[2]]];
  const tr = m[0][0] + m[1][1] + m[2][2];
  let q;
  if (tr > 0) {
    const s = Math.sqrt(tr + 1) * 2;
    q = [(m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, s / 4];
  } else if (m[0][0] > m[1][1] && m[0][0] > m[2][2]) {
    const s = Math.sqrt(1 + m[0][0] - m[1][1] - m[2][2]) * 2;
    q = [s / 4, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s];
  } else if (m[1][1] > m[2][2]) {
    const s = Math.sqrt(1 + m[1][1] - m[0][0] - m[2][2]) * 2;
    q = [(m[0][1] + m[1][0]) / s, s / 4, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s];
  } else {
    const s = Math.sqrt(1 + m[2][2] - m[0][0] - m[1][1]) * 2;
    q = [(m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, s / 4, (m[1][0] - m[0][1]) / s];
  }
  return q;
}

/** OpenCV camera (shape frame) → three.js camera (model frame): eye, quaternion, vertical fov. */
function threeCamera(cam) {
  const R = rodrigues(cam.rvec);
  const t = cam.tvec;
  const eyeShape = [0, 1, 2].map((i) => -(R[0][i] * t[0] + R[1][i] * t[1] + R[2][i] * t[2]));
  const eye = eyeShape.map((v, i) => (v - centre[i]) * scale);
  const right = R[0], down = R[1], forward = R[2];
  const q = quaternionFromColumns(right, down.map((v) => -v), forward.map((v) => -v));
  const fov = (2 * Math.atan(cams.height / 2 / cam.f) * 180) / Math.PI;
  return { eye, q, fov };
}

const ext = fs.readdirSync(path.join(os.homedir(), '.vscode', 'extensions')).filter((d) => d.startsWith('danielsanmedium.dscodegpt-')).sort().pop();
const { chromium } = createRequire(path.join(os.homedir(), '.vscode', 'extensions', ext, 'standalone', 'index.js'))('patchright');
const browser = await chromium.launch({ headless: true, channel: 'msedge', args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto(url, { waitUntil: 'load' });
// The page's own world (patchright evaluates in an isolated one): the DevTools protocol.
const cdp = await ctx.newCDPSession(page);
const js = async (expression) => {
  const r = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400));
  return r.result.value;
};
// The model loads once the parts section is near.
await js(`document.getElementById('parts').scrollIntoView()`);
for (let i = 0; i < 120 && !(await js('!!window.__bag')); i++) await new Promise((r) => setTimeout(r, 500));
await new Promise((r) => setTimeout(r, 800));
for (const [name, cam] of Object.entries(cams.cameras)) {
  const { eye, q, fov } = threeCamera(cam);
  const args = JSON.stringify([eye, q, fov, cams.width, cams.height]);
  const dataUrl = await js(`window.__bag.debugRender(...${args})`);
  fs.writeFileSync(path.join(out, `${name}-render.jpg`), Buffer.from(dataUrl.split(',')[1], 'base64'));
  console.log('rendered', name);
}
await browser.close();
