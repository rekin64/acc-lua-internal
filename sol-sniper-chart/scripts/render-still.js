// Renders a single frame of the chart to PNG.
// Usage: node scripts/render-still.js [seconds=8] [out=out/preview_t8.png]
// OVERLAY=0 renders the chart without the position overlay; PAGE=pro renders
// the pro terminal layout (preview/pro.html).

import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  ({ chromium } = require(join(execSync('npm root -g').toString().trim(), 'playwright')));
}

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const t = process.argv[2] ?? '8';
const out = resolve(root, process.argv[3] ?? `out/preview_t${t}.png`);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.png': 'image/png', '.otf': 'font/otf', '.svg': 'image/svg+xml' };

const server = createServer(async (req, res) => {
  const path = normalize(join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname)));
  if (!path.startsWith(root)) return res.writeHead(403).end();
  try {
    const body = await readFile(path);
    res.writeHead(200, { 'Content-Type': types[extname(path)] ?? 'application/octet-stream' }).end(body);
  } catch {
    res.writeHead(404).end();
  }
}).listen(0, '127.0.0.1');
await new Promise((r) => server.once('listening', r));
const { port } = server.address();

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.error('page error:', e.message));
const hs = process.env.HIST_SEED ? `&hs=${process.env.HIST_SEED}` : '';
const ov = process.env.OVERLAY === '0' ? '&overlay=0' : '';
const pageName = process.env.PAGE ?? 'index';
await page.goto(`http://127.0.0.1:${port}/preview/${pageName}.html?t=${t}${hs}${ov}`);
await page.waitForFunction(() => window.__ready === true, null, { timeout: 30000 });
await page.locator('#c').screenshot({ path: out });
await browser.close();
server.close();
console.log('wrote', out);
