// Checks, frame by frame, that the PNL panel (with its drop shadow), the ENTRY
// tag, the entry dot and the dashed entry line never cover a candle (wick and
// glow included for the panel and tag), a volume bar or another UI element,
// and that the tag stays inside the plot.
// Usage: node scripts/check-layout.js   (exit code 1 on any overlap)

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
  const { loadTnumFonts } = await import('/src/fonts.js');
  const ui = await import('/src/ui.js');
  const { PNL_BOX, entryTagBox, entryPoint, entryDotBox, entryLinePieces } = await import('/src/overlay.js');
  await loadTnumFonts((f) => `/public/fonts/${f}`);
  const ctx = document.createElement('canvas').getContext('2d');
  const market = buildMarket();
  const position = buildPosition(market);
  // visible glow margin: shadowBlur 18 (up) / 10 (down) in render.js
  const GLOW_UP = 12;
  const GLOW_DOWN = 8;
  const gapOf = (a, b) => {
    const dx = Math.max(b.x - (a.x + a.w), a.x - (b.x + b.w), 0);
    const dy = Math.max(b.y - (a.y + a.h), a.y - (b.y + b.h), 0);
    return dx === 0 && dy === 0 ? -1 : Math.hypot(dx, dy);
  };
  const fixed = [
    { name: 'pills', x: 52, y: ui.PILL_Y, w: 520, h: ui.PILL_H },
    { name: 'price axis', x: ui.SEP_X, y: ui.PRICE_TOP - 24, w: 1920 - ui.SEP_X, h: ui.VOL_BOT - ui.PRICE_TOP + 24 },
    { name: 'header', x: 0, y: 0, w: 1920, h: 160 },
  ];
  const worst = { panel: { gap: Infinity }, tag: { gap: Infinity }, dot: { gap: Infinity }, line: { gap: Infinity } };
  const overlaps = [];
  if (PNL_BOX.y - (ui.PILL_Y + ui.PILL_H) <= 0) overlaps.push({ frame: -1, box: 'panel', with: 'pills' });
  // panel plus its drop shadow: blur 28 (sigma 14, ~3 sigma = 42 px), offset y 10
  const panelShadow = { x: PNL_BOX.x - 42, y: PNL_BOX.y - 32, w: PNL_BOX.w + 84, h: PNL_BOX.h + 84 };
  // pixel footprint of a mark: fractional edges rounded outwards (anti-aliasing)
  const px = (r) => ({ x: Math.floor(r.x), y: Math.floor(r.y), w: Math.ceil(r.x + r.w) - Math.floor(r.x), h: Math.ceil(r.y + r.h) - Math.floor(r.y) });
  let tagChecked = 0;
  for (let f = 0; f < FPS * DURATION; f++) {
    const t = f / FPS;
    const s = market.stateAt(t);
    const yOf = (p) => ui.PRICE_BOT - ((p - s.yMin) / (s.yMax - s.yMin)) * (ui.PRICE_BOT - ui.PRICE_TOP);
    const things = [...fixed];
    const bodies = [];
    const marks = []; // exactly the rectangles render.js passes to drawEntryLine
    s.candles.forEach((k, i) => {
      const cx = ui.slotX(i);
      const glow = k.c >= k.o ? GLOW_UP : GLOW_DOWN;
      // body exactly as render.js draws it (3 px minimum, centred on open/close)
      let bTop = Math.min(yOf(k.o), yOf(k.c));
      let bh = Math.abs(yOf(k.c) - yOf(k.o));
      if (bh < 3) {
        bTop -= (3 - bh) / 2;
        bh = 3;
      }
      const top = Math.min(yOf(k.h), bTop);
      const bottom = Math.max(yOf(k.l), bTop + bh);
      const bx = Math.round(cx - ui.BODY_W / 2);
      bodies.push({ name: `candle ${i} (no glow)`, x: bx, y: top, w: ui.BODY_W, h: bottom - top });
      marks.push({ name: `candle ${i}`, x: bx, y: top, w: ui.BODY_W, h: bottom - top });
      things.push({ name: `candle ${i}`, x: bx - glow, y: top - glow, w: ui.BODY_W + 2 * glow, h: bottom - top + 2 * glow });
      const vh = Math.max(3, (k.v / s.vMax) * ui.VOL_H);
      things.push({ name: `volume ${i}`, x: cx - ui.VOL_W / 2, y: ui.VOL_BOT - vh, w: ui.VOL_W, h: vh });
      marks.push({ name: `volume ${i}`, x: cx - ui.VOL_W / 2, y: ui.VOL_BOT - vh, w: ui.VOL_W, h: vh });
    });
    const boxes = [['panel', panelShadow]];
    if (position.at(t).open) {
      const tag = entryTagBox(ctx, position, yOf);
      boxes.push(['tag', tag]);
      tagChecked++;
      if (tag.x < ui.X0 || tag.x + tag.w > ui.SEP_X || tag.y < ui.PRICE_TOP - 24 || tag.y + tag.h > ui.VOL_BOT) {
        overlaps.push({ frame: f, box: 'tag', with: 'plot bounds' });
      }
      // the dot must not touch any candle body/wick (glow allowed) nor a volume bar
      const dot = entryDotBox(position, yOf);
      for (const th of [...bodies, ...things.filter((x) => x.name.startsWith('volume'))]) {
        const g = gapOf(dot, th);
        if (g < 0) overlaps.push({ frame: f, box: 'dot', with: th.name });
        if (g < worst.dot.gap) worst.dot = { gap: Math.round(g * 10) / 10, frame: f, with: th.name };
      }
      // every dash piece (rows painted incl. anti-aliasing) vs every mark's pixel footprint
      const { y: ly, pieces } = entryLinePieces(position, yOf, marks);
      for (const [a, b] of pieces) {
        const seg = { x: Math.floor(a), y: Math.floor(ly) - 1, w: Math.ceil(b) - Math.floor(a), h: 3 };
        for (const m of marks) {
          const g = gapOf(seg, px(m));
          if (g < 0) overlaps.push({ frame: f, box: 'line', with: m.name });
          if (g < worst.line.gap) worst.line = { gap: Math.round(g * 10) / 10, frame: f, with: m.name };
        }
      }
    }
    for (const [name, box] of boxes) {
      for (const th of things) {
        if (name === 'panel' && th.name === 'pills') continue; // checked below as a gap
        const g = gapOf(box, th);
        if (g < 0) overlaps.push({ frame: f, box: name, with: th.name });
        if (g < worst[name].gap) worst[name] = { gap: Math.round(g * 10) / 10, frame: f, with: th.name };
      }
      if (name === 'tag') {
        const pb = PNL_BOX;
        const g = gapOf(box, pb);
        if (g < 0) overlaps.push({ frame: f, box: 'tag', with: 'panel' });
      }
    }
  }
  const p = entryPoint(position, (v) => v);
  return {
    frames: FPS * DURATION,
    tagFramesChecked: tagChecked,
    panel: PNL_BOX,
    panelToPillsGap: PNL_BOX.y - (ui.PILL_Y + ui.PILL_H),
    entrySlot: position.entrySlot,
    entryX: p.x,
    worstClearance: worst,
    overlapCount: overlaps.length,
    overlapsByElement: overlaps.reduce((acc, o) => {
      const k = `${o.box} x ${o.with}`;
      acc[k] = acc[k] ? { ...acc[k], last: o.frame, n: acc[k].n + 1 } : { first: o.frame, last: o.frame, n: 1 };
      return acc;
    }, {}),
    firstOverlaps: overlaps.slice(0, 5),
  };
});
await browser.close();
server.close();
console.log(JSON.stringify(report, null, 1));
process.exit(report.overlapCount ? 1 : 0);
