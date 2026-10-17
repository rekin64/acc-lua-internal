// Pro terminal layout (1920 x 1080): one frame at time t. Pure function of
// (t, market, position, assets, icons), so every frame is reproducible.

import { centsToString, formatPctBp, formatUsdCents, priceDecimals } from '../format.js';
import { roundRect } from '../ui.js';
import { PLAYBACK_SPEED, SLOTS } from './market.js';

const UI = 'Inter, system-ui, sans-serif';
const NUM = '"Inter Tnum", Inter, system-ui, sans-serif';

// Indigo / navy theme. Violet is reserved for the position (entry line, entry
// tag, entry price dot); blue marks selected UI controls.
export const C = {
  bg: '#05060F',
  nav: '#080A18',
  panel: '#0D1024',
  field: '#121632',
  border: '#1E2444',
  divider: 'rgba(130, 140, 210, 0.11)',
  grid: 'rgba(130, 140, 210, 0.06)',
  text: '#E8EBF7',
  text2: '#9AA3C7',
  text3: '#7581A8',
  up: '#36E0B5',
  down: '#F0475F',
  upBg: 'rgba(54, 224, 181, 0.12)',
  downBg: 'rgba(240, 71, 95, 0.12)',
  violet: '#8B7BF0',
  blue: '#5B7BFB',
  activeBg: 'rgba(91, 123, 251, 0.16)',
  activeText: '#B4C3FF',
};

// ---- layout ---------------------------------------------------------------------
const NAV_H = 60;
const TOKEN = { x: 10, y: 70, w: 1900, h: 76 };
const CHART = { x: 10, y: 156, w: 1440, h: 878 };
const SIDE_X = 1460;
const SIDE_W = 450;
const ACTIVITY = { x: SIDE_X, y: CHART.y, w: SIDE_W, h: 96 };
const POSITION = { x: SIDE_X, y: ACTIVITY.y + ACTIVITY.h + 12, w: SIDE_W, h: 322 };
const TRADES = { x: SIDE_X, y: POSITION.y + POSITION.h + 12, w: SIDE_W, h: CHART.y + CHART.h - (POSITION.y + POSITION.h + 12) };
const STATUS_Y = 1044;
const TB_H = 46; // chart toolbar
const TOOLS_W = 46; // drawing tools column
const RANGE_H = 46; // range / scale row
export const PLOT = { x: CHART.x + TOOLS_W, y: CHART.y + TB_H, w: 1284, h: 754 };
const AXIS_X = PLOT.x + PLOT.w; // price axis 1340 .. 1450
const AXIS_R = CHART.x + CHART.w;
const AXIS_CX = (AXIS_X + 6 + AXIS_R - 8) / 2;
const PRICE_TOP = PLOT.y + 52;
const PRICE_BOT = PLOT.y + PLOT.h - 104;
const VOL_BOT = PLOT.y + PLOT.h - 6;
const VOL_H = 118;
const SLOT_X0 = PLOT.x + 10;
export const PITCH = (PLOT.w - 18) / SLOTS; // 12.66 px
const BODY_W = 9;
export const slotX = (i) => SLOT_X0 + (i + 0.5) * PITCH;

// ---- small helpers ----------------------------------------------------------------
// Half-up rounding ($80,550 -> $80.6K).
function compactUsd(v) {
  if (v >= 1e6) return `$${(Math.round(v / 1e4) / 100).toFixed(2)}M`;
  if (v >= 1e3) return `$${(Math.round(v / 100) / 10).toFixed(1)}K`;
  return `$${Math.round(v)}`;
}
// Market cap as shown: from the 4-significant-digit price on screen, so the
// two always agree ($0.00008055 -> $80.6K).
const mcOf = (p) => Math.round(Number(p.toFixed(priceDecimals(p))) * 1e9);
function compactNum(v) {
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(0);
}
const group = (n) => n.toLocaleString('en-US');
const easeOut = (k) => 1 - Math.pow(1 - Math.min(1, Math.max(0, k)), 3);
const usd2 = (v) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function text(ctx, s, x, y, { font = `500 15px ${UI}`, color = C.text, align = 'left', base = 'middle', spacing = '0px' } = {}) {
  ctx.font = font;
  ctx.fillStyle = color;
  ctx.textAlign = align;
  ctx.textBaseline = base;
  ctx.letterSpacing = spacing;
  ctx.fillText(s, x, y);
  const w = ctx.measureText(s).width;
  ctx.letterSpacing = '0px';
  return w;
}
function measure(ctx, s, font, spacing = '0px') {
  ctx.font = font;
  ctx.letterSpacing = spacing;
  const w = ctx.measureText(s).width;
  ctx.letterSpacing = '0px';
  return w;
}
function icon(ctx, icons, name, x, y, size, color = 'muted') {
  ctx.drawImage(icons[name][color], x - size / 2, y - size / 2, size, size);
}
function panel(ctx, r, { radius = 12, fill = C.panel } = {}) {
  ctx.save();
  ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
  ctx.shadowBlur = 18;
  ctx.shadowOffsetY = 6;
  roundRect(ctx, r.x, r.y, r.w, r.h, radius);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.restore();
  const g = ctx.createLinearGradient(0, r.y, 0, r.y + 44);
  g.addColorStop(0, 'rgba(150, 165, 255, 0.04)');
  g.addColorStop(1, 'rgba(150, 165, 255, 0)');
  roundRect(ctx, r.x, r.y, r.w, Math.min(r.h, 44), radius);
  ctx.fillStyle = g;
  ctx.fill();
  roundRect(ctx, r.x + 0.5, r.y + 0.5, r.w - 1, r.h - 1, radius);
  ctx.strokeStyle = C.border;
  ctx.lineWidth = 1;
  ctx.stroke();
}
function hline(ctx, x0, x1, y, color = C.divider) {
  ctx.fillStyle = color;
  ctx.fillRect(x0, Math.round(y), x1 - x0, 1);
}
function vline(ctx, x, y0, y1, color = C.divider) {
  ctx.fillStyle = color;
  ctx.fillRect(Math.round(x), y0, 1, y1 - y0);
}
function pill(ctx, x, y, w, h, { fill, stroke = null, r = h / 2 } = {}) {
  roundRect(ctx, x, y, w, h, r);
  ctx.fillStyle = fill;
  ctx.fill();
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}
function chip(ctx, label, right, cy, { fill, color, stroke = null }) {
  const w = measure(ctx, label, `700 12px ${UI}`, '0.8px') + 18;
  pill(ctx, right - w, cy - 11, w, 22, { fill, stroke, r: 6 });
  text(ctx, label, right - w / 2 + 0.4, cy + 0.5, { font: `700 12px ${UI}`, color, align: 'center', spacing: '0.8px' });
  return w;
}

// "0.0₄1567": the zeros after the decimal point collapse into a subscript count
// (DEX terminal notation). Same 4 significant digits as the position panel.
export function priceParts(p) {
  const s = p.toFixed(priceDecimals(p));
  const m = /^0\.(0{3,})(\d+)$/.exec(s);
  return m ? { head: '0.0', zeros: String(m[1].length), tail: m[2] } : { head: s, zeros: '', tail: '' };
}
function priceText(ctx, p, x, y, { size = 15, weight = 500, color = C.text, align = 'left', prefix = '' } = {}) {
  const { head, zeros, tail } = priceParts(p);
  const main = `${weight} ${size}px ${NUM}`;
  const sub = `${weight} ${Math.round(size * 0.68)}px ${NUM}`;
  const w1 = measure(ctx, prefix + head, main);
  const w2 = zeros ? measure(ctx, zeros, sub) + 1 : 0;
  const w3 = tail ? measure(ctx, tail, main) : 0;
  const w = w1 + w2 + w3;
  const x0 = align === 'center' ? x - w / 2 : align === 'right' ? x - w : x;
  const base = y + size * 0.3635; // Inter: 'middle' sits 0.3635 em above the baseline
  ctx.fillStyle = color;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  ctx.font = main;
  ctx.fillText(prefix + head, x0, base);
  if (zeros) {
    ctx.font = sub;
    ctx.fillText(zeros, x0 + w1 + 0.5, base + size * 0.2);
  }
  if (tail) {
    ctx.font = main;
    ctx.fillText(tail, x0 + w1 + w2, base);
  }
  return w;
}

// Log-scale axis levels: 'nice' prices at least minGap px apart.
const MANT = [1, 1.2, 1.4, 1.6, 1.8, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7, 8, 9];
function logLevels(lo, hi, yOf, minGap) {
  const out = [];
  for (let e = Math.floor(Math.log10(lo)) - 1; e <= Math.ceil(Math.log10(hi)); e++) {
    for (const m of MANT) {
      const v = m * Math.pow(10, e);
      if (v < lo || v > hi) continue;
      const y = yOf(v);
      if (!out.length || out[out.length - 1][1] - y >= minGap) out.push([v, y]);
    }
  }
  return out;
}

// ---- top navigation ---------------------------------------------------------------
function drawNav(ctx, assets, icons) {
  ctx.fillStyle = C.nav;
  ctx.fillRect(0, 0, 1920, NAV_H);
  hline(ctx, 0, 1920, NAV_H - 1, C.border);
  const lh = 40;
  const lw = (assets.logo.width / assets.logo.height) * lh;
  ctx.drawImage(assets.logo, 20, (NAV_H - lh) / 2, lw, lh);
  let x = 20 + lw + 46;
  ['Terminal', 'Discover', 'Trackers', 'Portfolio'].forEach((s, i) => {
    const w = text(ctx, s, x, NAV_H / 2, { font: `${i === 0 ? 600 : 500} 16px ${UI}`, color: i === 0 ? C.text : C.text2 });
    if (i === 0) pill(ctx, x, NAV_H - 3, w, 3, { fill: C.blue, r: 1.5 });
    x += w + 34;
  });
  // search
  const sx = 1030;
  pill(ctx, sx, 11, 440, 38, { fill: C.field, stroke: C.border, r: 10 });
  icon(ctx, icons, 'search', sx + 22, 30, 18);
  text(ctx, 'Search token or contract address', sx + 42, 30.5, { font: `400 15px ${UI}`, color: C.text3 });
  pill(ctx, sx + 440 - 34, 20, 22, 20, { fill: '#161B3A', stroke: C.border, r: 5 });
  text(ctx, '/', sx + 440 - 23, 30.5, { font: `500 13px ${UI}`, color: C.text2, align: 'center' });
  // right cluster
  icon(ctx, icons, 'circle-user', 1882, 30, 26);
  icon(ctx, icons, 'settings', 1836, 30, 20);
  icon(ctx, icons, 'bell', 1796, 30, 20);
  drawWallet(ctx, assets, icons, 1772);
}

// Wallet chip: official SOL logo, balance and wallet name (fictitious balance).
function drawWallet(ctx, assets, icons, right) {
  const BAL = `600 15px ${NUM}`;
  const UNIT = `500 15px ${UI}`;
  const NAME = `500 14px ${UI}`;
  const bw = measure(ctx, '154.5', BAL) + 5 + measure(ctx, 'SOL', UNIT);
  const nw = measure(ctx, 'Wallet 01', NAME);
  const w = 10 + 24 + 10 + bw + 13 + 1 + 13 + nw + 6 + 14 + 10;
  const x = right - w;
  const y = 11;
  const h = 38;
  const cy = y + h / 2;
  pill(ctx, x, y, w, h, { fill: C.field, stroke: C.border, r: 10 });
  const g = ctx.createLinearGradient(0, y, 0, y + h);
  g.addColorStop(0, 'rgba(150, 165, 255, 0.05)');
  g.addColorStop(1, 'rgba(150, 165, 255, 0)');
  pill(ctx, x + 1, y + 1, w - 2, h - 2, { fill: g, r: 9 });
  ctx.save();
  ctx.beginPath();
  ctx.arc(x + 10 + 12, cy, 12, 0, Math.PI * 2);
  ctx.clip();
  ctx.drawImage(assets.sol, x + 10, cy - 12, 24, 24);
  ctx.restore();
  let tx = x + 10 + 24 + 10;
  tx += text(ctx, '154.5', tx, cy + 0.5, { font: BAL }) + 5;
  tx += text(ctx, 'SOL', tx, cy + 0.5, { font: UNIT, color: C.text2 }) + 13;
  vline(ctx, tx, cy - 10, cy + 10, C.border);
  tx += 1 + 13;
  tx += text(ctx, 'Wallet 01', tx, cy + 0.5, { font: NAME, color: C.text2 }) + 6;
  icon(ctx, icons, 'chevron-down', tx + 7, cy, 14);
}

// ---- token bar: fixed anchors so values never shift while they tick -------------------
function drawTokenBar(ctx, s, assets, icons) {
  panel(ctx, TOKEN);
  const cy = TOKEN.y + TOKEN.h / 2;
  ctx.save();
  ctx.beginPath();
  ctx.arc(TOKEN.x + 38, cy, 24, 0, Math.PI * 2);
  ctx.clip();
  const im = assets.token;
  const inset = im.width * 0.012;
  ctx.drawImage(im, inset, inset, im.width - 2 * inset, im.height - 2 * inset, TOKEN.x + 14, cy - 24, 48, 48);
  ctx.restore();
  const nx = TOKEN.x + 76;
  const nw = text(ctx, '$USELESS', nx, cy - 11, { font: `700 22px ${UI}` });
  icon(ctx, icons, 'star', nx + nw + 16, cy - 11, 16, 'dim');
  const sw = text(ctx, 'USELESS COIN', nx, cy + 15, { font: `500 13px ${UI}`, color: C.text2 });
  icon(ctx, icons, 'copy', nx + sw + 14, cy + 15, 13, 'dim');
  icon(ctx, icons, 'globe', nx + sw + 34, cy + 15, 13, 'dim');
  vline(ctx, 280, TOKEN.y + 16, TOKEN.y + TOKEN.h - 16);

  const LY = cy - 14;
  const VY = cy + 12;
  const lab = (l, x) => text(ctx, l, x, LY, { font: `500 14px ${UI}`, color: C.text3 });
  // price + 5m change
  lab('Price', 306);
  const up = s.pct5m >= 0;
  const pw = priceText(ctx, s.price, 306, VY + 1, { size: 26, weight: 700, color: up ? C.up : C.down, prefix: '$' });
  const ch = `${up ? '+' : '−'}${group(Math.round(Math.abs(s.pct5m)))}%`;
  const cw = measure(ctx, ch, `600 14px ${NUM}`) + measure(ctx, '5m', `500 12px ${UI}`) + 24;
  const cx = 306 + pw + 12;
  pill(ctx, cx, VY - 11, cw, 24, { fill: up ? C.upBg : C.downBg, r: 6 });
  const lw = text(ctx, '5m', cx + 8, VY + 1, { font: `500 12px ${UI}`, color: up ? 'rgba(54, 224, 181, 0.75)' : 'rgba(240, 71, 95, 0.75)' });
  text(ctx, ch, cx + 8 + lw + 6, VY + 1, { font: `600 14px ${NUM}`, color: up ? C.up : C.down });

  const val = (v, x, color = C.text) => text(ctx, v, x, VY, { font: `600 19px ${NUM}`, color });
  lab('Market Cap', 590);
  val(compactUsd(mcOf(s.price)), 590);
  lab('Liquidity', 750);
  val(compactUsd(s.liquidity), 750);
  lab('Volume 5m', 910);
  val(compactUsd(s.stats5m.vol), 910);
  lab('Txns 5m', 1070);
  let w = val(group(s.stats5m.buys), 1070, C.up);
  w += text(ctx, ' / ', 1070 + w, VY, { font: `500 19px ${NUM}`, color: C.text3 });
  val(group(s.stats5m.sells), 1070 + w, C.down);
  lab('ATH', 1230);
  val(compactUsd(s.ath * 1e9), 1230);
  lab('Holders', 1410);
  val(group(s.holders), 1410);
  lab('Supply', 1560);
  val('1B', 1560);
  icon(ctx, icons, 'external-link', 1806, cy, 18);
  icon(ctx, icons, 'bell', 1844, cy, 18);
  icon(ctx, icons, 'share-2', 1882, cy, 18);
}

// ---- chart panel ---------------------------------------------------------------------
function drawToolbar(ctx, icons) {
  const cy = CHART.y + TB_H / 2;
  let x = CHART.x + 14;
  const tfs = ['1s', '15s', '1m', '5m', '1h'];
  const tw = tfs.map((s) => measure(ctx, s, `600 14px ${UI}`) + 22);
  const total = tw.reduce((a, b) => a + b, 0) + 8;
  pill(ctx, x, cy - 15, total, 30, { fill: C.field, r: 8 });
  let tx = x + 4;
  tfs.forEach((s, i) => {
    if (i === 0) pill(ctx, tx, cy - 11, tw[i], 22, { fill: C.activeBg, r: 6 });
    text(ctx, s, tx + tw[i] / 2, cy + 0.5, { font: `600 14px ${UI}`, color: i === 0 ? C.activeText : C.text2, align: 'center' });
    tx += tw[i];
  });
  x += total + 16;
  vline(ctx, x, cy - 12, cy + 12);
  x += 18;
  icon(ctx, icons, 'chart-candlestick', x + 9, cy, 18);
  x += 34;
  vline(ctx, x, cy - 12, cy + 12);
  x += 16;
  icon(ctx, icons, 'square-function', x + 9, cy, 18);
  x += text(ctx, 'Indicators', x + 25, cy + 0.5, { font: `500 14px ${UI}`, color: C.text2 }) + 42;
  icon(ctx, icons, 'layout-grid', x + 9, cy, 17);
  x += 34;
  vline(ctx, x, cy - 12, cy + 12);
  x += 16;
  const pair = (a, b) => {
    x += text(ctx, a, x, cy + 0.5, { font: `600 14px ${UI}`, color: C.activeText });
    x += text(ctx, ' / ', x, cy + 0.5, { font: `500 14px ${UI}`, color: C.text3 });
    x += text(ctx, b, x, cy + 0.5, { font: `500 14px ${UI}`, color: C.text2 }) + 26;
  };
  pair('USD', 'SOL');
  pair('Price', 'MCap');
  const r = CHART.x + CHART.w - 22;
  icon(ctx, icons, 'camera', r, cy, 18);
  icon(ctx, icons, 'maximize', r - 36, cy, 17);
  icon(ctx, icons, 'settings', r - 72, cy, 18);
  icon(ctx, icons, 'redo-2', r - 116, cy, 17, 'dim');
  icon(ctx, icons, 'undo-2', r - 148, cy, 17, 'dim');
  hline(ctx, CHART.x, CHART.x + CHART.w, CHART.y + TB_H, C.border);
}

function drawTools(ctx, icons) {
  const cx = CHART.x + TOOLS_W / 2;
  const names = ['crosshair', 'pen-line', 'rows-3', 'pencil', 'spline', 'type', 'smile', 'ruler', 'zoom-in', 'magnet', 'lock', 'eye', 'trash-2'];
  names.forEach((n, i) => {
    const y = PLOT.y + 26 + i * 46;
    if (i === 0) pill(ctx, cx - 15, y - 15, 30, 30, { fill: C.activeBg, r: 7 });
    icon(ctx, icons, n, cx, y, 18, i === 0 ? 'active' : 'muted');
    if (i === 6 || i === 9) hline(ctx, cx - 12, cx + 12, y + 23);
  });
  vline(ctx, CHART.x + TOOLS_W, CHART.y + TB_H, CHART.y + CHART.h - RANGE_H, C.border);
}

// Axis tag centred in the price axis, with a notch pointing at its level.
function priceTag(ctx, y, p, fill, color) {
  const h = 24;
  const x0 = AXIS_X + 6;
  roundRect(ctx, x0, y - h / 2, AXIS_R - 8 - x0, h, 5);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(x0 + 1, y - 6);
  ctx.lineTo(AXIS_X + 1, y);
  ctx.lineTo(x0 + 1, y + 6);
  ctx.closePath();
  ctx.fill();
  priceText(ctx, p, AXIS_CX, y + 0.5, { size: 14, weight: 600, color, align: 'center' });
}

const DASH_ON = 6;
const DASH_OFF = 5;
// Dash pieces of the entry line; every dash stops 1 px short of any candle or
// volume bar crossing it, so the line never paints over the chart's own marks.
export function entryLinePieces(x0, x1, y, marks) {
  const row = Math.floor(y);
  const blocked = marks.filter((r) => r.y < row + 3 && r.y + r.h > row - 2).map((r) => [Math.floor(r.x) - 1, Math.ceil(r.x + r.w) + 1]);
  const pieces = [];
  for (let a = x0; a < x1; a += DASH_ON + DASH_OFF) {
    let segs = [[a, Math.min(a + DASH_ON, x1)]];
    for (const [ba, bb] of blocked) {
      segs = segs.flatMap(([sa, sb]) => (bb <= sa || ba >= sb ? [[sa, sb]] : [[sa, Math.min(sb, ba)], [Math.max(sa, bb), sb]]));
    }
    for (const [sa, sb] of segs) if (sb - sa >= 3) pieces.push([sa, sb]);
  }
  return { y: row + 0.5, pieces };
}

// BUY marker: pill above-left of the entry, leader down to an anchor dot that
// sits on the entry price, in the gap just before the entry candle.
const BUY_FONT = `700 15px ${UI}`;
export function buyMarker(ctx, position, yOf) {
  const label = 'BUY $500';
  const w = 8 + 22 + 8 + measure(ctx, label, BUY_FONT, '0.4px') + 14;
  const h = 30;
  const ax = slotX(position.entrySlot) - PITCH / 2;
  const ay = yOf(position.entryValue);
  const right = ax - 24;
  return { x: right - w, y: ay - 26 - h, w, h, label, ax, ay };
}

function drawChart(ctx, s, position, pos, icons) {
  panel(ctx, CHART);
  drawToolbar(ctx, icons);
  drawTools(ctx, icons);
  const yOf = (p) => PRICE_BOT - ((Math.log(p) - s.logMin) / (s.logMax - s.logMin)) * (PRICE_BOT - PRICE_TOP);
  const pOf = (y) => Math.exp(s.logMin + ((PRICE_BOT - y) / (PRICE_BOT - PRICE_TOP)) * (s.logMax - s.logMin));
  const plotR = PLOT.x + PLOT.w;
  const plotB = PLOT.y + PLOT.h;

  ctx.save();
  ctx.beginPath();
  ctx.rect(PLOT.x, PLOT.y, AXIS_R - PLOT.x, PLOT.h);
  ctx.clip();

  // grid
  const levels = logLevels(pOf(plotB - 12), pOf(PLOT.y + 12), yOf, 56);
  for (const [, y] of levels) hline(ctx, PLOT.x, plotR, y, C.grid);
  const timeSlots = [];
  for (let i = 0; i < SLOTS; i++) if (s.isTen(i)) timeSlots.push(i);
  for (const i of timeSlots) vline(ctx, slotX(i), PLOT.y, plotB, C.grid);
  vline(ctx, AXIS_X, PLOT.y, plotB, C.border);

  // volume (overlay at the bottom of the pane)
  const volRects = [];
  s.candles.forEach((k, i) => {
    const h = Math.max(2, (k.usd / s.vMax) * VOL_H);
    const x = Math.round(slotX(i) - BODY_W / 2);
    ctx.fillStyle = k.c >= k.o ? 'rgba(54, 224, 181, 0.42)' : 'rgba(240, 71, 95, 0.62)';
    ctx.fillRect(x, VOL_BOT - h, BODY_W, h);
    volRects.push({ x, y: VOL_BOT - h, w: BODY_W, h });
  });

  // candle rectangles (also used to keep the entry line off them)
  const marks = s.candles.map((k, i) => {
    let top = Math.min(yOf(k.o), yOf(k.c));
    let bh = Math.abs(yOf(k.c) - yOf(k.o));
    if (bh < 1) {
      top -= (1 - bh) / 2;
      bh = 1;
    }
    const y0 = Math.min(yOf(k.h), top);
    const y1 = Math.max(yOf(k.l), top + bh);
    return { x: Math.round(slotX(i) - BODY_W / 2), y: y0, w: BODY_W, h: y1 - y0, top, bh };
  });

  const buy = pos?.open ? buyMarker(ctx, position, yOf) : null;

  // entry line (violet), from the anchor to the axis, behind the candles
  let entryY = null;
  if (buy) {
    entryY = buy.ay;
    const { y, pieces } = entryLinePieces(Math.round(buy.ax) + 6, plotR, entryY, [...marks, ...volRects]);
    ctx.strokeStyle = 'rgba(139, 123, 240, 0.85)';
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    for (const [a, b] of pieces) {
      ctx.moveTo(a, y);
      ctx.lineTo(b, y);
    }
    ctx.stroke();
  }

  // current price line, left open where it would cross the BUY pill
  const last = s.candles[s.candles.length - 1];
  const lastUp = last.c >= last.o;
  const cy = yOf(s.price);
  const ly = Math.round(cy) + 0.5;
  ctx.strokeStyle = lastUp ? 'rgba(54, 224, 181, 0.65)' : 'rgba(240, 71, 95, 0.65)';
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 3]);
  ctx.beginPath();
  if (buy && ly > buy.y - 3 && ly < buy.y + buy.h + 3) {
    ctx.moveTo(PLOT.x, ly);
    ctx.lineTo(buy.x - 6, ly);
    ctx.moveTo(buy.x + buy.w + 6, ly);
  } else {
    ctx.moveTo(PLOT.x, ly);
  }
  ctx.lineTo(plotR, ly);
  ctx.stroke();
  ctx.setLineDash([]);

  // candles
  s.candles.forEach((k, i) => {
    const m = marks[i];
    ctx.fillStyle = k.c >= k.o ? C.up : C.down;
    ctx.fillRect(m.x + Math.floor(BODY_W / 2), yOf(k.h), 1, Math.max(1, yOf(k.l) - yOf(k.h)));
    ctx.fillRect(m.x, m.top, BODY_W, Math.max(1, m.bh));
  });

  // BUY marker
  if (buy) {
    ctx.strokeStyle = 'rgba(54, 224, 181, 0.7)';
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.moveTo(buy.x + buy.w - 12, buy.y + buy.h);
    ctx.lineTo(buy.ax - 3, buy.ay - 3);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(buy.ax, buy.ay, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = C.panel;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(buy.ax, buy.ay, 3, 0, Math.PI * 2);
    ctx.fillStyle = C.up;
    ctx.fill();
    pill(ctx, buy.x, buy.y, buy.w, buy.h, { fill: '#0A2223', stroke: 'rgba(54, 224, 181, 0.5)', r: 8 });
    const bcx = buy.x + 8 + 11;
    const bcy = buy.y + buy.h / 2;
    ctx.beginPath();
    ctx.arc(bcx, bcy, 11, 0, Math.PI * 2);
    ctx.fillStyle = C.up;
    ctx.fill();
    text(ctx, 'B', bcx + 0.3, bcy + 0.5, { font: `800 13px ${UI}`, color: '#03140F', align: 'center' });
    text(ctx, buy.label, bcx + 11 + 8, bcy + 0.5, { font: BUY_FONT, color: C.up, spacing: '0.4px' });
  }

  // axis labels (kept clear of the tags), then the tags
  const tagYs = [cy];
  let entryTagY = entryY;
  if (entryY !== null) {
    if (Math.abs(entryY - cy) < 26) entryTagY = cy + (entryY >= cy ? 26 : -26);
    tagYs.push(entryTagY);
  }
  for (const [v, y] of levels) {
    if (tagYs.some((ty) => Math.abs(ty - y) < 28)) continue;
    priceText(ctx, v, AXIS_CX, y, { size: 13, weight: 500, color: C.text2, align: 'center' });
  }
  if (entryY !== null) priceTag(ctx, entryTagY, position.entryValue, C.violet, '#FFFFFF');
  priceTag(ctx, cy, s.price, lastUp ? C.up : C.down, lastUp ? '#03140F' : '#FFFFFF');
  ctx.restore();

  // legend (OHLC of the forming candle)
  const lx = PLOT.x + 16;
  const lgy = PLOT.y + 22;
  let x = lx;
  x += text(ctx, '$USELESS / USD', x, lgy, { font: `600 15px ${UI}` });
  x += text(ctx, '  ·  1s  ·  SOL Sniper', x, lgy, { font: `500 15px ${UI}`, color: C.text2 }) + 22;
  const col = lastUp ? C.up : C.down;
  for (const [k, v] of [['O', last.o], ['H', last.h], ['L', last.l], ['C', last.c]]) {
    x += text(ctx, k, x, lgy, { font: `500 14px ${UI}`, color: C.text3 }) + 5;
    x += priceText(ctx, v, x, lgy, { size: 14, color: col }) + 14;
  }
  const chg = last.c / last.o - 1;
  text(ctx, `${chg >= 0 ? '+' : '−'}${Math.abs(chg * 100).toFixed(2)}%`, x, lgy, { font: `600 14px ${NUM}`, color: col });
  x = lx;
  x += text(ctx, 'Volume', x, lgy + 25, { font: `500 14px ${UI}`, color: C.text3 }) + 7;
  text(ctx, compactUsd(last.usd), x, lgy + 25, { font: `500 14px ${NUM}`, color: col });

  // time axis: every 10 s, minutes in bold
  const ty = plotB + 16;
  hline(ctx, PLOT.x, AXIS_R, plotB, C.border);
  for (const i of timeSlots) {
    const minute = s.isMinute(i);
    const label = minute ? s.clockOf(i).slice(0, 5) : s.clockOf(i);
    const font = `${minute ? 600 : 500} 13px ${NUM}`;
    const lw = measure(ctx, label, font);
    if (slotX(i) - lw / 2 < PLOT.x + 6 || slotX(i) + lw / 2 > AXIS_X - 4) continue;
    text(ctx, label, slotX(i), ty, { font, color: minute ? C.text2 : C.text3, align: 'center' });
  }

  // range / scale row
  const ry = CHART.y + CHART.h - RANGE_H / 2;
  hline(ctx, CHART.x, CHART.x + CHART.w, CHART.y + CHART.h - RANGE_H, C.border);
  let rx = CHART.x + 20;
  ['3m', '1m', '5d', '1d'].forEach((r) => {
    rx += text(ctx, r, rx, ry, { font: `500 14px ${UI}`, color: C.text2 }) + 20;
  });
  vline(ctx, rx, ry - 10, ry + 10);
  icon(ctx, icons, 'calendar', rx + 22, ry, 16);
  let rr = CHART.x + CHART.w - 20;
  rr -= text(ctx, 'auto', rr, ry, { font: `600 14px ${UI}`, color: C.activeText, align: 'right' }) + 16;
  rr -= text(ctx, 'log', rr, ry, { font: `600 14px ${UI}`, color: C.activeText, align: 'right' }) + 16;
  rr -= text(ctx, '%', rr, ry, { font: `500 14px ${UI}`, color: C.text2, align: 'right' }) + 18;
  vline(ctx, rr, ry - 10, ry + 10);
  rr -= 18;
  rr -= text(ctx, `${s.clock} (UTC)`, rr, ry, { font: `500 14px ${NUM}`, color: C.text2, align: 'right' }) + 14;
  // 1 s candles play at 2x: 2 chart seconds per video second
  const speed = `${PLAYBACK_SPEED}×`;
  const rw = 10 + 12 + 6 + measure(ctx, 'Speed', `500 14px ${UI}`) + 5 + measure(ctx, speed, `600 14px ${NUM}`) + 10;
  pill(ctx, rr - rw, ry - 12, rw, 24, { fill: C.field, stroke: C.border, r: 6 });
  icon(ctx, icons, 'play', rr - rw + 10 + 6, ry, 12, 'active');
  let px = rr - rw + 10 + 12 + 6;
  px += text(ctx, 'Speed', px, ry + 0.5, { font: `500 14px ${UI}`, color: C.text2 }) + 5;
  text(ctx, speed, px, ry + 0.5, { font: `600 14px ${NUM}`, color: C.text });
}

// ---- sidebar -------------------------------------------------------------------------
function drawActivity(ctx, s) {
  const r = ACTIVITY;
  panel(ctx, r);
  const st = s.stats1m;
  const net = st.buyUsd - st.sellUsd;
  const cols = [
    ['1m Vol', compactUsd(st.vol), C.text],
    [`Buys · ${st.buys}`, compactUsd(st.buyUsd), C.up],
    [`Sells · ${st.sells}`, compactUsd(st.sellUsd), C.down],
    ['Net Vol', `${net >= 0 ? '+' : '−'}${compactUsd(Math.abs(net))}`, net >= 0 ? C.up : C.down],
  ];
  const cw = (r.w - 40) / 4;
  cols.forEach(([l, v, c], i) => {
    const x = r.x + 20 + i * cw;
    text(ctx, l, x, r.y + 26, { font: `500 13px ${UI}`, color: C.text3 });
    text(ctx, v, x, r.y + 51, { font: `600 17px ${NUM}`, color: c });
  });
  const bx = r.x + 20;
  const bw = r.w - 40;
  const share = st.buyUsd / Math.max(1, st.vol);
  pill(ctx, bx, r.y + 74, bw, 4, { fill: 'rgba(240, 71, 95, 0.85)', r: 2 });
  pill(ctx, bx, r.y + 74, Math.max(4, bw * share - 2), 4, { fill: C.up, r: 2 });
}

function drawPosition(ctx, position, pos) {
  const r = POSITION;
  panel(ctx, r);
  const L = r.x + 20;
  const R = r.x + r.w - 20;
  text(ctx, 'Position', L, r.y + 27, { font: `600 16px ${UI}` });
  chip(ctx, pos.open ? 'OPEN' : 'NO POSITION', R, r.y + 27, pos.open ? { fill: C.activeBg, color: C.activeText, stroke: 'rgba(91, 123, 251, 0.45)' } : { fill: 'rgba(154, 163, 199, 0.10)', color: C.text2 });
  hline(ctx, r.x, r.x + r.w, r.y + 53);

  const dash = '—';
  text(ctx, 'Unrealized PNL', L, r.y + 78, { font: `500 13px ${UI}`, color: C.text3 });
  text(ctx, 'excl. fees & slippage', R, r.y + 78, { font: `500 12px ${UI}`, color: C.text3, align: 'right' });
  const sign = pos.open ? (pos.pnlCents > 0n ? 1 : pos.pnlCents < 0n ? -1 : 0) : 0;
  const tone = sign > 0 ? C.up : sign < 0 ? C.down : C.text;
  text(ctx, pos.open ? formatUsdCents(pos.pnlCents, { signed: true }) : dash, L - 1, r.y + 115, { font: `700 40px ${NUM}`, color: pos.open ? tone : C.text3 });
  if (pos.open) {
    const roi = formatPctBp(pos.roiBp);
    const rw = measure(ctx, roi, `700 20px ${NUM}`) + 22;
    pill(ctx, R - rw, r.y + 99, rw, 32, { fill: sign >= 0 ? C.upBg : C.downBg, r: 8 });
    text(ctx, roi, R - rw / 2, r.y + 115.5, { font: `700 20px ${NUM}`, color: sign === 0 ? C.text : tone, align: 'center' });
  }
  hline(ctx, L, R, r.y + 148);

  const cell = (label, value, x, y, dot = null) => {
    let lx = x;
    if (dot) {
      ctx.beginPath();
      ctx.arc(lx + 4, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = dot;
      ctx.fill();
      lx += 14;
    }
    text(ctx, label, lx, y, { font: `500 13px ${UI}`, color: C.text3 });
    text(ctx, value, x, y + 25, { font: `600 18px ${NUM}`, color: value === dash ? C.text3 : C.text });
  };
  const mid = r.x + r.w / 2 + 8;
  cell('Invested', pos.open ? formatUsdCents(position.sizeCents) : dash, L, r.y + 172);
  cell('Current Value', pos.open ? formatUsdCents(pos.valueCents) : dash, mid, r.y + 172);
  cell('Entry Price', pos.open ? position.entry.text : dash, L, r.y + 232, pos.open ? C.violet : C.text3);
  cell('Current Price', pos.price.text, mid, r.y + 232);
  hline(ctx, L, R, r.y + 282);
  text(ctx, 'Tokens Held', L, r.y + 302, { font: `500 13px ${UI}`, color: C.text3 });
  text(ctx, pos.open ? centsToString(position.tokensHundredths) : dash, R, r.y + 302, { font: `600 16px ${NUM}`, color: pos.open ? C.text : C.text3, align: 'right' });
}

// Trades tape, newest first. Like a live terminal, a new trade is inserted
// at the top at once (the top row is always the last trade), fades in over
// 120 ms and its row flashes briefly.
const ROW_H = 30;
const FADE_S = 0.12;
const FLASH_S = 0.5;
function drawTrades(ctx, s, t) {
  const r = TRADES;
  panel(ctx, r);
  const L = r.x + 20;
  const R = r.x + r.w - 20;
  let x = L;
  ['Trades', 'Holders', 'Top Traders'].forEach((tab, i) => {
    const w = text(ctx, tab, x, r.y + 25, { font: `${i === 0 ? 600 : 500} 15px ${UI}`, color: i === 0 ? C.text : C.text2 });
    if (i === 0) pill(ctx, x, r.y + 47, w, 2, { fill: C.blue, r: 1 });
    x += w + 26;
  });
  hline(ctx, r.x, r.x + r.w, r.y + 49);
  const cols = { age: L, type: L + 50, mc: L + 118, amount: L + 296, value: R };
  const hy = r.y + 68;
  const hf = { font: `500 13px ${UI}`, color: C.text3 };
  text(ctx, 'Age', cols.age, hy, hf);
  text(ctx, 'Type', cols.type, hy, hf);
  text(ctx, 'MC', cols.mc, hy, hf);
  text(ctx, 'Amount', cols.amount, hy, { ...hf, align: 'right' });
  text(ctx, 'Value', cols.value, hy, { ...hf, align: 'right' });
  hline(ctx, r.x + 12, r.x + r.w - 12, r.y + 85);

  const top = r.y + 88;
  ctx.save();
  ctx.beginPath();
  ctx.rect(r.x + 1, top, r.w - 2, r.y + r.h - 8 - top);
  ctx.clip();
  s.tape.forEach((tr, i) => {
    const y = top + i * ROW_H + ROW_H / 2;
    if (y - ROW_H / 2 > r.y + r.h) return;
    const buy = tr.side === 'buy';
    const c = buy ? C.up : C.down;
    const fk = (t - tr.tv) / FLASH_S;
    if (fk >= 0 && fk < 1) {
      ctx.fillStyle = buy ? `rgba(54, 224, 181, ${(0.12 * (1 - fk)).toFixed(3)})` : `rgba(240, 71, 95, ${(0.12 * (1 - fk)).toFixed(3)})`;
      ctx.fillRect(r.x + 1, y - ROW_H / 2, r.w - 2, ROW_H);
    }
    ctx.globalAlpha = 0.35 + 0.65 * easeOut((t - tr.tv) / FADE_S);
    const bw = Math.min(100, Math.max(16, 16 + (Math.log10(Math.max(1, tr.usd)) / Math.log10(3000)) * 84));
    pill(ctx, R + 6 - bw, y - 11, bw, 22, { fill: buy ? 'rgba(54, 224, 181, 0.09)' : 'rgba(240, 71, 95, 0.10)', r: 4 });
    text(ctx, `${tr.age}s`, cols.age, y, { font: `500 15px ${NUM}`, color: C.text3 });
    text(ctx, buy ? 'Buy' : 'Sell', cols.type, y, { font: `600 15px ${UI}`, color: c });
    text(ctx, compactUsd(mcOf(tr.price)), cols.mc, y, { font: `500 15px ${NUM}`, color: C.text });
    text(ctx, compactNum(tr.tokens), cols.amount, y, { font: `500 15px ${NUM}`, color: C.text2, align: 'right' });
    text(ctx, usd2(tr.usd), cols.value, y, { font: `600 15px ${NUM}`, color: c, align: 'right' });
    ctx.globalAlpha = 1;
  });
  // older rows fade out at the bottom edge of the list
  const fb = r.y + r.h - 8;
  const g = ctx.createLinearGradient(0, fb - 34, 0, fb);
  g.addColorStop(0, 'rgba(13, 16, 36, 0)');
  g.addColorStop(1, 'rgba(13, 16, 36, 1)');
  ctx.fillStyle = g;
  ctx.fillRect(r.x + 1, fb - 34, r.w - 2, 34);
  ctx.restore();
}

// ---- footer: the one notice that the data is fictitious ----------------------------------
function drawStatus(ctx, icons) {
  ctx.fillStyle = C.nav;
  ctx.fillRect(0, STATUS_Y, 1920, 1080 - STATUS_Y);
  hline(ctx, 0, 1920, STATUS_Y, C.border);
  const cy = STATUS_Y + 18;
  icon(ctx, icons, 'info', 24, cy, 15);
  text(ctx, 'Simulated data · prices, trades, wallet balance and PNL are fictitious', 40, cy + 0.5, { font: `500 14px ${UI}`, color: C.text2 });
}

export function drawProFrame(ctx, t, market, position, assets, icons) {
  const s = { ...market.stateAt(t), clockOf: market.clockOf, isMinute: market.isMinute, isTen: market.isTen };
  const pos = position ? position.at(t) : null;
  ctx.save();
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, 1920, 1080);
  drawNav(ctx, assets, icons);
  drawTokenBar(ctx, s, assets, icons);
  drawChart(ctx, s, position, pos, icons);
  drawActivity(ctx, s);
  if (pos) drawPosition(ctx, position, pos);
  drawTrades(ctx, s, t);
  drawStatus(ctx, icons);
  ctx.restore();
}
