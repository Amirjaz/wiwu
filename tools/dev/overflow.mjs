// Phone layout check: does anything make the home page wider than the screen (sideways scrolling)?
//
//   node tools/dev/overflow.mjs [width] [url]
//
// Defaults: 390, http://127.0.0.1:8030/. Prints the page's scroll width against the screen's and the first
// elements reaching past either edge (some are fine: a clipping parent hides them). Headless Edge through
// patchright, as in tools/compare.mjs.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const width = Number(process.argv[2] ?? 390);
const url = process.argv[3] ?? 'http://127.0.0.1:8030/';

const ext = fs.readdirSync(path.join(os.homedir(), '.vscode', 'extensions')).filter((d) => d.startsWith('danielsanmedium.dscodegpt-')).sort().pop();
const { chromium } = createRequire(path.join(os.homedir(), '.vscode', 'extensions', ext, 'standalone', 'index.js'))('patchright');
const browser = await chromium.launch({ headless: true, channel: 'msedge', args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader'] });
const ctx = await browser.newContext({ viewport: { width, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
await page.goto(url, { waitUntil: 'load' });
await page.waitForTimeout(6000);
const result = await page.evaluate(() => {
  const w = document.documentElement.clientWidth;
  const wide = [...document.querySelectorAll('body *')]
    .filter((e) => { const b = e.getBoundingClientRect(); return b.width && (b.left < -1 || b.right > w + 1); })
    .slice(0, 12)
    .map((e) => {
      const b = e.getBoundingClientRect();
      return `${e.tagName}.${String(e.className.baseVal ?? e.className).slice(0, 80)} ${Math.round(b.left)}..${Math.round(b.right)}`;
    });
  return { scrollWidth: document.documentElement.scrollWidth, clientWidth: w, wide };
});
console.log(JSON.stringify(result, null, 1));
console.log(result.scrollWidth > result.clientWidth ? 'OVERFLOW: the page scrolls sideways' : 'ok: no sideways scrolling');
await browser.close();
