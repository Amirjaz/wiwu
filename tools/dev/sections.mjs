// Screenshots of every home section and the other pages at one size, as visitors see them (scroll
// animations play out first). Headless Edge through patchright, as in tools/compare.mjs.
//   node tools/dev/sections.mjs <width> <height> <out-dir>          (BASE=https://shop.nisatech.org for staging)
// Below 768 px wide the page opens as a phone (2x, touch) and the phone menu is shot open too.
// The --disable-features flags let the page (port 8030) load Vite's modules (port 5180) in development.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const width = Number(process.argv[2] ?? 1440);
const height = Number(process.argv[3] ?? 900);
const out = process.argv[4];
fs.mkdirSync(out, { recursive: true });
const base = process.env.BASE ?? 'http://127.0.0.1:8030';

const ext = fs.readdirSync(path.join(os.homedir(), '.vscode', 'extensions')).filter((d) => d.startsWith('danielsanmedium.dscodegpt-')).sort().pop();
const { chromium } = createRequire(path.join(os.homedir(), '.vscode', 'extensions', ext, 'standalone', 'index.js'))('patchright');
const browser = await chromium.launch({ headless: true, channel: 'msedge', args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests'] });
const phone = width < 768;
const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: phone ? 2 : 1, isMobile: phone, hasTouch: phone });
const page = await ctx.newPage();
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) console.log('[page]', m.type(), m.text().slice(0, 200)); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
const cdp = await ctx.newCDPSession(page);
const shot = async (name) => {
  const r = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 78 });
  fs.writeFileSync(path.join(out, `${width}-${name}.jpg`), Buffer.from(r.data, 'base64'));
};
const to = async (selector, offset = 64) => {
  await page.evaluate(([s, o]) => {
    const el = document.querySelector(s);
    document.documentElement.style.scrollBehavior = 'auto';
    window.scrollTo(0, el.getBoundingClientRect().top + scrollY - o);
  }, [selector, offset]);
  await page.waitForTimeout(900);
};

await page.goto(base + '/', { waitUntil: 'load' });
await page.waitForTimeout(6000);
console.log('overflow', await page.evaluate(() => document.documentElement.scrollWidth - innerWidth));
await shot('home-0-hero');
if (phone) {
  await page.locator('[data-menu-toggle]').click();
  await page.waitForTimeout(400);
  await shot('menu-open');
  await page.locator('[data-menu-toggle]').click();
  await page.waitForTimeout(300);
}
await to('[data-stop="1"]', phone ? height * 0.5 : 120);
await page.waitForTimeout(1500);
await shot('home-1-lock');
await to('#try');
await shot('home-2-try');
// Hold the sensor for 0.7 s.
const box = await page.locator('[data-sensor]').boundingBox();
await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
await page.mouse.down();
await page.waitForTimeout(250);
await shot('home-2-try-reading');
await page.waitForTimeout(500);
await page.mouse.up();
await shot('home-2-try-open');
await to('#parts');
await page.locator('#parts-back li[data-part="1"]').hover();
await page.waitForTimeout(300);
await shot('home-3-parts-back');
await page.locator('#parts-tab-side').click();
await page.waitForTimeout(500);
await shot('home-3-parts-side');
await page.locator('#parts-tab-front').click();
await page.waitForTimeout(500);
await shot('home-3-parts-front');
await to('#specs');
await page.waitForTimeout(600);
await shot('home-4-specs');
await to('#specs dl', phone ? 120 : 300);
await shot('home-4-specs-cells');
await to('#buy');
await page.waitForTimeout(600);
await shot('home-5-buy');
await to('#buy aside', 200);
await page.waitForTimeout(600);
await shot('home-5-buy-receipt');
await to('#faq');
await shot('home-6-faq');
await to('section.bg-signal');
await shot('home-7-closing');
await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await page.waitForTimeout(900);
await shot('home-8-footer');

for (const [name, url] of [['checkout', '/checkout/'], ['lookup', '/orders/'], ['policy', '/p/returns/'], ['order-shipped', '/o/csKJLJCp1zwvkaOs/'], ['panel', '/panel/']]) {
  await page.goto(base + url, { waitUntil: 'load' });
  await page.waitForTimeout(1800);
  await shot(name);
}
console.log('wrote', out);
await browser.close();
