// Close-ups of the 3D bag from fixed orbit positions: the views its details are judged by (the lock,
// the zipper from above, the far end) and a few wider ones.
//
//   node tools/dev/orbits.mjs [out-dir] [url]
//
// Defaults: media/3d/compare/orbits, http://127.0.0.1:8030/. Needs the dev servers running (the page has
// window.__bag.debugOrbit in development only) and headless Edge through patchright (tools/compare.mjs).
// Writes <out-dir>/<view>.jpg, 900 x 900; the lock views have the sensor's light on.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const out = process.argv[2] ?? path.join(root, 'media', '3d', 'compare', 'orbits');
const url = process.argv[3] ?? 'http://127.0.0.1:8030/';
fs.mkdirSync(out, { recursive: true });

const model = JSON.parse(fs.readFileSync(path.join(root, 'frontend', 'public', 'models', 'alpha.json'), 'utf8'));
const top = model.size[1];
const mod = model.details.module;
// name: [azimuth°, elevation°, distance m, target, light]; azimuth 0 looks at the front, the lock end is at -x.
const views = {
  lock: [(Math.atan2(mod.n[0], mod.n[2]) * 180) / Math.PI + 10, 8, 0.16, mod.origin, true],
  lockwide: [-80, 10, 0.32, [-0.11, 0.065, 0], true],
  top: [-20, 72, 0.3, [0, top, 0], false],
  topzip: [0, 88, 0.16, [-0.05, top, 0], false],
  farend: [90, 10, 0.28, [0.11, 0.07, 0], false],
  farend34: [120, 18, 0.3, [0.1, 0.07, 0], false],
  hero: [-50, 14, 0.5, [0, 0.07, 0], false],
  back: [200, 22, 0.52, [0, 0.07, 0], false],
};

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
for (const [name, [az, el, dist, target, light]] of Object.entries(views)) {
  const dataUrl = await js(`window.__bag.debugOrbit(${az}, ${el}, ${dist}, ${JSON.stringify(target)}, 900, 900, ${light})`);
  fs.writeFileSync(path.join(out, `${name}.jpg`), Buffer.from(dataUrl.split(',')[1], 'base64'));
}
console.log('wrote', Object.keys(views).join(' '), 'to', out);
await browser.close();
