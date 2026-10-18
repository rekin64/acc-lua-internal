// Lossless proof that the position overlay leaves the chart untouched: renders
// all 600 frames with and without the overlay and counts changed pixels
//   - inside any candle or volume bar (pixel footprint, anti-aliasing included)
//   - outside the overlay's own zones (panel + shadow, tag, dot, line pieces)
// Both counts must be 0. Usage: node scripts/check-pixels.js (exit 1 otherwise)

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
const types = { '.html': 'text/html', '.js': 'text/javascript', '.png': 'image/png', '.otf': 'font/otf' };
const server = createServer(async (req, res) => {
  const path = normalize(join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname)));
  if (!path.startsWith(root)) return res.writeHead(403).end();
  try {
    const body = await readFile(path);
    res.writeHead(200, { 'Content-Type': types[extname(path)] ?? 'text/html' }).end(body);
  } catch {
    res.writeHead(200, { 'Content-Type': 'text/html' }).end('<!doctype html><title>check</title>');
  }
}).listen(0, '127.0.0.1');
await new Promise((r) => server.once('listening', r));

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(`http://127.0.0.1:${server.address().port}/check.html`);
const report = await page.evaluate(async () => {
  const { buildMarket, FPS, DURATION } = await import('/src/engine.js');
  const { buildPosition } = await import('/src/position.js');
  const { drawFrame } = await import('/src/render.js');
  const { loadTnumFonts } = await import('/src/fonts.js');
  const ui = await import('/src/ui.js');
  const { PNL_BOX, entryTagBox, entryArrowBox, entryLinePieces, statusBox } = await import('/src/overlay.js');
  await Promise.all(['500 22px Inter', '500 28px Inter', '600 46px Inter', '700 50px Inter'].map((f) => document.fonts.load(f)));
  await loadTnumFonts((f) => `/public/fonts/${f}`);
  const load = (src) => new Promise((ok, ko) => Object.assign(new Image(), { onload() { ok(this); }, onerror: ko, src }));
  const assets = {
    logo: await load('/public/assets/solsniper-logo.png'),
    token: await load('/public/assets/useless.png'),
    icon: await load('/public/assets/solsniper-icon.png'),
  };
  const mk = () => {
    const c = document.createElement('canvas');
    c.width = 1920;
    c.height = 1080;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    ctx.imageSmoothingQuality = 'high';
    return ctx;
  };
  const a = mk();
  const b = mk();
  const market = buildMarket();
  const position = buildPosition(market);
  const W = 1920;
  const H = 1080;
  let markChanged = 0;
  let strayChanged = 0;
  const worstFrames = [];
  for (let f = 0; f < FPS * DURATION; f++) {
    const t = f / FPS;
    drawFrame(a, t, market, assets, null);
    drawFrame(b, t, market, assets, position);
    const da = a.getImageData(0, 0, W, H).data;
    const db = b.getImageData(0, 0, W, H).data;
    const s = market.stateAt(t);
    const yOf = (p) => ui.PRICE_BOT - ((p - s.yMin) / (s.yMax - s.yMin)) * (ui.PRICE_BOT - ui.PRICE_TOP);
    // overlay zones (allowed to change)
    const zone = new Uint8Array(W * H);
    const mark = (x0, y0, x1, y1, arr) => {
      for (let y = Math.max(0, Math.floor(y0)); y < Math.min(H, Math.ceil(y1)); y++) {
        for (let x = Math.max(0, Math.floor(x0)); x < Math.min(W, Math.ceil(x1)); x++) arr[y * W + x] = 1;
      }
    };
    // panel + drop shadow: blur 28 (sigma 14, ~3 sigma = 42 px), offset y 10
    mark(PNL_BOX.x - 42, PNL_BOX.y - 32, PNL_BOX.x + PNL_BOX.w + 42, PNL_BOX.y + PNL_BOX.h + 52, zone);
    {
      // status badge, placed exactly as render.js places it (after the link icon)
      const logoW = (assets.logo.width / assets.logo.height) * 64;
      const titleX = Math.round(52 + logoW + 34) + 34 + 45 + 45 + 24;
      a.font = '600 46px Inter';
      const sb = statusBox(a, Math.round(titleX + a.measureText('$USELESS').width + 22 + 32 + 36), ui.HEADER_CY);
      mark(sb.x - 2, sb.y - 2, sb.x + sb.w + 2, sb.y + sb.h + 2, zone);
    }
    // chart marks, exactly as render.js builds them
    const marksArr = new Uint8Array(W * H);
    const marks = [];
    s.candles.forEach((k, i) => {
      let top = Math.min(yOf(k.o), yOf(k.c));
      let bh = Math.abs(yOf(k.c) - yOf(k.o));
      if (bh < 3) {
        top -= (3 - bh) / 2;
        bh = 3;
      }
      const y0 = Math.min(yOf(k.h), top);
      const y1 = Math.max(yOf(k.l), top + bh);
      const x = Math.round(ui.slotX(i) - ui.BODY_W / 2);
      marks.push({ x, y: y0, w: ui.BODY_W, h: y1 - y0 });
      mark(x, y0, x + ui.BODY_W, y1, marksArr);
      const vh = Math.max(3, (k.v / s.vMax) * ui.VOL_H);
      const vx = ui.slotX(i) - ui.VOL_W / 2;
      marks.push({ x: vx, y: ui.VOL_BOT - vh, w: ui.VOL_W, h: vh });
      mark(vx, ui.VOL_BOT - vh, vx + ui.VOL_W, ui.VOL_BOT, marksArr);
    });
    if (position.at(t).open) {
      const tag = entryTagBox(a, position, yOf);
      mark(tag.x - 2, tag.y - 2, tag.x + tag.w + 2, tag.y + tag.h + 2, zone);
      const dot = entryArrowBox(position, yOf);
      mark(dot.x - 2, dot.y - 2, dot.x + dot.w + 2, dot.y + dot.h + 2, zone);
      mark(tag.x + tag.w - 12, tag.y + tag.h - 1, dot.x + 1, dot.y + 3, zone); // leader
      const { y, pieces } = entryLinePieces(position, yOf, marks);
      for (const [x0, x1] of pieces) mark(x0 - 1, y - 2, x1 + 1, y + 2, zone);
    }
    let mc = 0;
    let sc = 0;
    const where = [];
    for (let i = 0; i < W * H; i++) {
      const j = i * 4;
      if (da[j] === db[j] && da[j + 1] === db[j + 1] && da[j + 2] === db[j + 2]) continue;
      if (marksArr[i]) mc++; // the panel never sits on a mark (see check-layout), so any change here is real
      if (!zone[i]) {
        sc++;
        if (where.length < 4) where.push([i % W, Math.floor(i / W), Math.max(Math.abs(da[j] - db[j]), Math.abs(da[j + 1] - db[j + 1]), Math.abs(da[j + 2] - db[j + 2]))]);
      }
    }
    markChanged += mc;
    strayChanged += sc;
    if (mc || sc) worstFrames.push({ frame: f, markChanged: mc, strayChanged: sc, strayAt: where });
  }
  return { frames: FPS * DURATION, markChanged, strayChanged, worstFrames: worstFrames.slice(0, 10) };
});
await browser.close();
server.close();
console.log(JSON.stringify(report, null, 1));
process.exit(report.markChanged || report.strayChanged ? 1 : 0);
