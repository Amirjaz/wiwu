// The phone: first screen, swiping the hero's photos, the parts tabs with the 3D bag (or its photos),
// then each section below. Prints the state at each step and saves screenshots.
//   node tools/dev/phone.mjs <out-dir> [base] [width] [height]
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const out = process.argv[2];
const base = process.argv[3] ?? 'http://127.0.0.1:8030';
const width = Number(process.argv[4] ?? 390);
const height = Number(process.argv[5] ?? 844);
fs.mkdirSync(out, { recursive: true });
const ext = fs.readdirSync(path.join(os.homedir(), '.vscode', 'extensions')).filter((d) => d.startsWith('danielsanmedium.dscodegpt-')).sort().pop();
const { chromium } = createRequire(path.join(os.homedir(), '.vscode', 'extensions', ext, 'standalone', 'index.js'))('patchright');
const browser = await chromium.launch({ headless: true, channel: 'msedge', args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests'] });
const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) console.log('[page]', m.type(), m.text().slice(0, 200)); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
const cdp = await ctx.newCDPSession(page);
const shot = async (name) => {
  const r = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 78 });
  fs.writeFileSync(path.join(out, `${width}-${name}.jpg`), Buffer.from(r.data, 'base64'));
};
const state = () => page.evaluate(() => ({
  photo: [...document.querySelectorAll('[data-slide]')].findIndex((slide) => slide.hasAttribute('data-on')) + 1,
  tab: document.querySelector('[role="tab"][aria-selected="true"]')?.textContent?.trim(),
  stage: [...document.querySelector('[data-bag-stage]').attributes].map((a) => a.name).filter((n) => ['data-pending', 'data-3d', 'data-photos'].includes(n)).join(' '),
  scrollY: Math.round(scrollY),
  overflow: document.documentElement.scrollWidth - innerWidth,
}));
// A sideways swipe across the hero's photo (right to left page: a swipe to the right brings the next).
const swipe = async (x0, x1, y = 300) => {
  const touch = (type, x) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y }] });
  await touch('touchStart', x0);
  for (let i = 1; i <= 8; i++) await touch('touchMove', x0 + ((x1 - x0) * i) / 8);
  await touch('touchEnd');
  await page.waitForTimeout(1200);
};

await page.goto(base + '/', { waitUntil: 'load' });
await page.waitForTimeout(2500);
console.log('first screen', JSON.stringify(await state()));
await shot('m-0-first');
await swipe(80, 300);
console.log('swiped to the next photo', JSON.stringify(await state()));
await shot('m-0-photo2');
const to = async (selector, offset = 64) => {
  await page.evaluate(([s, o]) => {
    document.documentElement.style.scrollBehavior = 'auto';
    const el = document.querySelector(s);
    window.scrollTo(0, el.getBoundingClientRect().top + scrollY - o);
  }, [selector, offset]);
  await page.waitForTimeout(900);
};
await to('#parts');
for (let i = 0; i < 40 && !(await page.locator('[data-bag-stage][data-3d], [data-bag-stage][data-photos]').count()); i++) await page.waitForTimeout(500);
await page.waitForTimeout(1500);
console.log('parts', JSON.stringify(await state()));
await shot('m-1-parts-front');
for (const tab of ['side', 'back']) {
  await page.locator(`#parts-tab-${tab}`).click();
  await page.waitForTimeout(2200);
  await shot(`m-1-parts-${tab}`);
}
for (const [name, sel] of [['try', '#try'], ['specs', '#specs'], ['specs-cells', '#specs dl'], ['buy', '#buy'], ['receipt', '#buy aside'], ['faq', '#faq'], ['closing', 'section.bg-signal']]) {
  await to(sel, name === 'specs-cells' || name === 'receipt' ? 160 : 64);
  await shot(`m-2-${name}`);
}
console.log('end', JSON.stringify(await state()));
await browser.close();
