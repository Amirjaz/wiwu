// The phone tour: first screen, swiping the stop cards (which view tab lights up, whether the 3D loaded),
// tapping a tab, then each section below. Prints the state at each step and saves screenshots.
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
  tab: document.querySelector('[data-view][aria-current="true"]')?.textContent?.trim(),
  scrollY: Math.round(scrollY),
  overflow: document.documentElement.scrollWidth - innerWidth,
  canvas: !!document.querySelector('[data-hero-stage] canvas'),
}));

await page.goto(base + '/', { waitUntil: 'load' });
await page.waitForTimeout(6500);
console.log('first screen', JSON.stringify(await state()));
await shot('m-0-first');
for (const i of [1, 2, 4]) {
  await page.evaluate((i) => document.querySelector(`[data-stop="${i}"]`).scrollIntoView({ inline: 'center', block: 'nearest' }), i);
  await page.waitForTimeout(2200);
  console.log(`card ${i}`, JSON.stringify(await state()));
  await shot(`m-1-card${i}`);
}
await page.locator('[data-view="1"]').click();
await page.waitForTimeout(1800);
console.log('tap tab 1', JSON.stringify(await state()));
const to = async (selector, offset = 64) => {
  await page.evaluate(([s, o]) => {
    document.documentElement.style.scrollBehavior = 'auto';
    const el = document.querySelector(s);
    window.scrollTo(0, el.getBoundingClientRect().top + scrollY - o);
  }, [selector, offset]);
  await page.waitForTimeout(900);
};
for (const [name, sel] of [['try', '#try'], ['parts', '#parts'], ['specs', '#specs'], ['specs-cells', '#specs dl'], ['buy', '#buy'], ['receipt', '#buy aside'], ['faq', '#faq'], ['closing', 'section.bg-signal']]) {
  await to(sel, name === 'specs-cells' || name === 'receipt' ? 160 : 64);
  await shot(`m-2-${name}`);
}
console.log('end', JSON.stringify(await state()));
await browser.close();
