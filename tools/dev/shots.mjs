// Screenshots of the home page's scroll tour: the hero, then each of the four stops scrolled to the
// middle of the screen, as a visitor sees them.
//
//   node tools/dev/shots.mjs [width] [height] [out-dir] [url]
//
// Defaults: 1440 x 900, media/3d/compare/shots, http://127.0.0.1:8030/ (dev servers running). Below
// 768 px wide the page opens as a phone (2x, touch). Writes <out-dir>/<width>-<stop>.jpg. Headless
// Edge through patchright, as in tools/compare.mjs.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const width = Number(process.argv[2] ?? 1440);
const height = Number(process.argv[3] ?? 900);
const out = process.argv[4] ?? path.join(root, 'media', '3d', 'compare', 'shots');
const url = process.argv[5] ?? 'http://127.0.0.1:8030/';
fs.mkdirSync(out, { recursive: true });

const ext = fs.readdirSync(path.join(os.homedir(), '.vscode', 'extensions')).filter((d) => d.startsWith('danielsanmedium.dscodegpt-')).sort().pop();
const { chromium } = createRequire(path.join(os.homedir(), '.vscode', 'extensions', ext, 'standalone', 'index.js'))('patchright');
const browser = await chromium.launch({ headless: true, channel: 'msedge', args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const phone = width < 768;
const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: phone ? 2 : 1, isMobile: phone, hasTouch: phone });
const page = await ctx.newPage();
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) console.log('[page]', m.type(), m.text().slice(0, 300)); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto(url, { waitUntil: 'load' });
const cdp = await ctx.newCDPSession(page);
const shot = async (name) => {
  const r = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 80 });
  fs.writeFileSync(path.join(out, `${width}-${name}.jpg`), Buffer.from(r.data, 'base64'));
};
await page.waitForTimeout(7000); // the 3D bag loads after the page
console.log('3D canvas:', await page.evaluate(() => !!document.querySelector('[data-hero-stage] canvas')));
await shot('0');
for (const i of [1, 2, 3, 4]) {
  await page.evaluate((i) => {
    const el = document.querySelector(`[data-stop="${i}"]`);
    window.scrollTo(0, el.getBoundingClientRect().top + scrollY - innerHeight / 2 + el.offsetHeight / 2);
  }, i);
  await page.waitForTimeout(2200); // the camera's glide to the stop
  await shot(String(i));
}
console.log('wrote', out);
await browser.close();
