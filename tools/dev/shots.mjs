// Screenshots of the 3D bag in the parts section (#parts): each tab's view, and each part tapped, as a
// visitor sees them. For checking the framing after changing the model or the stage: the bag and its
// shadow must stay inside the stage, and the pins on their parts.
//
//   node tools/dev/shots.mjs [width] [height] [out-dir] [url]
//
// Defaults: 1440 x 900, media/3d/compare/shots, http://127.0.0.1:8030/ (dev servers running). Below
// 768 px wide the page opens as a phone (2x, touch). Writes <out-dir>/<width>-<tab>[-<part>].jpg.
// Headless Edge through patchright, as in tools/compare.mjs.
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
const browser = await chromium.launch({ headless: true, channel: 'msedge', args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests'] });
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
// The model starts loading once the section is near.
await page.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, document.getElementById('parts').offsetTop - 64); });
for (let i = 0; i < 60 && !(await page.locator('[data-bag-stage][data-3d], [data-bag-stage][data-photos]').count()); i++) await page.waitForTimeout(500);
console.log('3D canvas:', await page.evaluate(() => !!document.querySelector('[data-bag-stage][data-3d] canvas')));
await page.waitForTimeout(1500);
for (const tab of ['front', 'side', 'back']) {
  await page.locator(`#parts-tab-${tab}`).click();
  await page.waitForTimeout(2200); // the camera's glide to the side
  await shot(tab);
  const parts = await page.locator(`#parts-${tab} button[data-part]`).count();
  for (let part = 1; part <= parts; part++) {
    await page.locator(`#parts-${tab} button[data-part="${part}"]`).click();
    await page.waitForTimeout(2200);
    await shot(`${tab}-${part}`);
  }
}
console.log('wrote', out);
await browser.close();
