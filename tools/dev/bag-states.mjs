// The 3D bag's stage (#parts) in three cases: the 3D loads; the model is blocked (the photos must take
// over); no WebGL2 at all (photos from the start). Scrolls to the section once the page has loaded (the
// model only starts loading then), prints what is visible right away and after 7 s, and saves the stage.
//   node tools/dev/bag-states.mjs <base> <out-dir> [ok,blocked,nowebgl]   (FIRST=ms to wait before the first look)
import { createRequire } from 'node:module'; import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
const ext = fs.readdirSync(path.join(os.homedir(), '.vscode', 'extensions')).filter((d) => d.startsWith('danielsanmedium.dscodegpt-')).sort().pop();
const { chromium } = createRequire(path.join(os.homedir(), '.vscode', 'extensions', ext, 'standalone', 'index.js'))('patchright');
const [base, out] = [process.argv[2], process.argv[3]]; fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true, channel: 'msedge', args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests'] });
const state = (page) => page.evaluate(() => {
  const stage = document.querySelector('[data-bag-stage]');
  const vis = (el) => el ? `${getComputedStyle(el).visibility}/${getComputedStyle(el).opacity}/${getComputedStyle(el).display}` : 'gone';
  return { attrs: [...stage.attributes].map(a => a.name).filter(n => ['data-pending', 'data-3d', 'data-photos'].includes(n)),
    photo: vis(stage.querySelector('[data-parts-photo]')), loading: vis(stage.querySelector('[data-bag-loading]')),
    pins: [...stage.querySelectorAll('[data-pins]:not([hidden]) [data-pin]')].filter((p) => !p.hidden && p.offsetParent).length,
    canvas: !!stage.querySelector('canvas') };
});
for (const mode of (process.argv[4] ?? 'ok,blocked,nowebgl').split(',')) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  if (mode === 'blocked') await page.route('**/*.glb', (route) => route.abort());
  if (mode === 'nowebgl') await page.addInitScript(() => { const get = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function (t, ...a) { return t === 'webgl2' ? null : get.call(this, t, ...a); }; });
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await page.goto(base, { waitUntil: 'load' });
  await page.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, document.getElementById('parts').offsetTop); });
  await page.waitForTimeout(Number(process.env.FIRST ?? 300));
  console.log(mode, 'first', JSON.stringify(await state(page)));
  const clip = async () => { const b = await page.locator('[data-bag-stage]').boundingBox(); return { x: b.x, y: b.y, width: b.width, height: b.height }; };
  await page.screenshot({ path: `${out}/${mode}-first.png`, clip: await clip() });
  await page.waitForTimeout(7000);
  console.log(mode, 'after 7s', JSON.stringify(await state(page)));
  await page.screenshot({ path: `${out}/${mode}-7s.png`, clip: await clip() });
  await ctx.close();
}
await browser.close();
