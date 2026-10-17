// Pro terminal layout (1920 x 1080): one frame at time t. Pure function of
// (t, market, position, assets, icons), so every frame is reproducible.

import { centsToString, formatPct, formatPctBp, formatPrice, formatUsdCents } from '../format.js';
import { roundRect } from '../ui.js';
import { SLOTS } from './market.js';

const UI = 'Inter, system-ui, sans-serif';
const NUM = '"Inter Tnum", Inter, system-ui, sans-serif';

export const C = {
  bg: '#05080F',
  nav: '#070B15',
  panel: '#0A0F1C',
  field: '#0E1426',
  border: '#18213A',
  divider: 'rgba(120, 140, 200, 0.10)',
  grid: 'rgba(120, 140, 200, 0.07)',
  text: '#E6EAF5',
  text2: '#8A97BF',
  text3: '#5C688B',
  up: '#36E0B5',
  down: '#F0475F',
  upBg: 'rgba(54, 224, 181, 0.12)',
  downBg: 'rgba(240, 71, 95, 0.12)',
  violet: '#8777E0',
  blue: '#5B7BFB',
  activeBg: 'rgba(91, 123, 251, 0.16)',
  activeText: '#AFC0FF',
  shadow: 'rgba(0, 0, 0, 0.35)',
};

// ---- layout ---------------------------------------------------------------
const NAV_H = 56;
const TOKEN = { x: 12, y: 64, w: 1896, h: 72 };
const CHART = { x: 12, y: 144, w: 1440, h: 892 };
const SIDE_X = 1464;
const SIDE_W = 444;
const STATUS_Y = 1044;
const TB_H = 46; // chart toolbar
const TOOLS_W = 46; // drawing tools column
export const PLOT = { x: CHART.x + TOOLS_W, y: CHART.y + TB_H, w: 1288, h: 762 };
const AXIS_X = PLOT.x + PLOT.w; // price axis 1356 .. 1452
const PRICE_TOP = PLOT.y + 70;
const PRICE_BOT = PLOT.y + PLOT.h - 150;
const VOL_BOT = PLOT.y + PLOT.h - 6;
const VOL_H = 112;
const SLOT_X0 = PLOT.x + 10;
export const PITCH = (PLOT.w - 18) / SLOTS; // 10 px
const BODY_W = 7;
export const slotX = (i) => SLOT_X0 + (i + 0.5) * PITCH;

// ---- small helpers ----------------------------------------------------------
function compactUsd(v) {
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}
function compactNum(v) {
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(0);
}
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
  ctx.shadowColor = 'rgba(0, 0, 0, 0.45)';
  ctx.shadowBlur = 18;
  ctx.shadowOffsetY = 6;
  roundRect(ctx, r.x, r.y, r.w, r.h, radius);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.restore();
  const g = ctx.createLinearGradient(0, r.y, 0, r.y + 40);
  g.addColorStop(0, 'rgba(150, 170, 255, 0.035)');
  g.addColorStop(1, 'rgba(150, 170, 255, 0)');
  roundRect(ctx, r.x, r.y, r.w, Math.min(r.h, 40), radius);
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
// Log-scale axis labels: 'nice' prices at least MIN_GAP px apart.
const MANT = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8];
const labelOf = (v) => v.toFixed(Math.max(6, Math.ceil(-Math.log10(v)) + 1));
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

// ---- top navigation -------------------------------------------------------------
function drawNav(ctx, assets, icons) {
  ctx.fillStyle = C.nav;
  ctx.fillRect(0, 0, 1920, NAV_H);
  hline(ctx, 0, 1920, NAV_H - 1, C.border);
  const lh = 36;
  const lw = (assets.logo.width / assets.logo.height) * lh;
  ctx.drawImage(assets.logo, 18, (NAV_H - lh) / 2, lw, lh);
  let x = 22 + lw + 40;
  ['Terminal', 'Discover', 'Trackers', 'Portfolio'].forEach((s, i) => {
    const w = text(ctx, s, x, NAV_H / 2, { font: `${i === 0 ? 600 : 500} 16px ${UI}`, color: i === 0 ? C.text : C.text2 });
    if (i === 0) {
      const g = ctx.createLinearGradient(x, 0, x + w, 0);
      g.addColorStop(0, C.blue);
      g.addColorStop(1, C.violet);
      ctx.fillStyle = g;
      ctx.fillRect(x, NAV_H - 3, w, 2);
    }
    x += w + 32;
  });
  // search
  const sx = 1040;
  pill(ctx, sx, 10, 420, 36, { fill: C.field, stroke: C.border, r: 10 });
  icon(ctx, icons, 'search', sx + 22, 28, 18);
  text(ctx, 'Search token or contract address', sx + 42, 28.5, { font: `400 15px ${UI}`, color: C.text3 });
  pill(ctx, sx + 420 - 34, 18, 22, 20, { fill: '#141B31', stroke: C.border, r: 5 });
  text(ctx, '/', sx + 420 - 23, 28.5, { font: `500 13px ${UI}`, color: C.text2, align: 'center' });
  // right cluster
  icon(ctx, icons, 'circle-user', 1880, 28, 26, 'muted');
  icon(ctx, icons, 'settings', 1832, 28, 20, 'muted');
  icon(ctx, icons, 'bell', 1792, 28, 20, 'muted');
  const solW = 78;
  pill(ctx, 1692, 12, solW, 32, { fill: C.field, stroke: C.border, r: 8 });
  text(ctx, 'SOL', 1708, 28.5, { font: `600 14px ${UI}`, color: C.text });
  icon(ctx, icons, 'chevron-down', 1750, 28, 16);
}

// ---- token bar ----------------------------------------------------------------------
function drawTokenBar(ctx, s, assets, icons) {
  panel(ctx, TOKEN);
  const cy = TOKEN.y + TOKEN.h / 2;
  // avatar
  ctx.save();
  ctx.beginPath();
  ctx.arc(TOKEN.x + 36, cy, 22, 0, Math.PI * 2);
  ctx.clip();
  const im = assets.token;
  const inset = im.width * 0.012;
  ctx.drawImage(im, inset, inset, im.width - 2 * inset, im.height - 2 * inset, TOKEN.x + 14, cy - 22, 44, 44);
  ctx.restore();
  const nx = TOKEN.x + 72;
  const nw = text(ctx, '$USELESS', nx, cy - 11, { font: `700 21px ${UI}` });
  icon(ctx, icons, 'star', nx + nw + 16, cy - 11, 16, 'dim');
  const sw = text(ctx, 'USELESS COIN', nx, cy + 14, { font: `500 13px ${UI}`, color: C.text2 });
  icon(ctx, icons, 'copy', nx + sw + 14, cy + 14, 13, 'dim');
  icon(ctx, icons, 'globe', nx + sw + 34, cy + 14, 13, 'dim');

  // stats
  let x = 300;
  const lab = (s2, xx) => text(ctx, s2, xx, cy - 13, { font: `500 13px ${UI}`, color: C.text3 });
  vline(ctx, x - 26, TOKEN.y + 16, TOKEN.y + TOKEN.h - 16, C.divider);
  lab('Price', x);
  const up = s.pct >= 0;
  let w = text(ctx, formatPrice(s.price), x, cy + 13, { font: `700 20px ${NUM}`, color: up ? C.up : C.down });
  const chip = formatPct(s.pct);
  const cw = measure(ctx, chip, `600 13px ${NUM}`) + 16;
  pill(ctx, x + w + 10, cy + 2, cw, 22, { fill: up ? C.upBg : C.downBg, r: 6 });
  text(ctx, chip, x + w + 10 + cw / 2, cy + 13.5, { font: `600 13px ${NUM}`, color: up ? C.up : C.down, align: 'center' });
  x += w + cw + 54;
  const stat = (label, value, color = C.text) => {
    lab(label, x);
    const ww = text(ctx, value, x, cy + 13, { font: `600 17px ${NUM}`, color });
    x += Math.max(ww, measure(ctx, label, `500 13px ${UI}`)) + 44;
  };
  stat('Market Cap', compactUsd(s.mcap));
  stat('Liquidity', compactUsd(s.liquidity));
  stat('Volume 1m', compactUsd(s.stats.vol));
  lab('Txns 1m', x);
  w = text(ctx, String(s.stats.buys), x, cy + 13, { font: `600 17px ${NUM}`, color: C.up });
  w += text(ctx, ' / ', x + w, cy + 13, { font: `500 17px ${NUM}`, color: C.text3 });
  w += text(ctx, String(s.stats.sells), x + w, cy + 13, { font: `600 17px ${NUM}`, color: C.down });
  x += w + 44;
  stat('Supply', '1B');
  // right actions
  const ry = cy;
  icon(ctx, icons, 'share-2', 1876, ry, 18);
  icon(ctx, icons, 'bell', 1838, ry, 18);
  icon(ctx, icons, 'external-link', 1800, ry, 18);
}

// ---- chart panel --------------------------------------------------------------------
function drawToolbar(ctx, icons) {
  const cy = CHART.y + TB_H / 2;
  let x = CHART.x + 16;
  // timeframe segmented control
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
  x += text(ctx, 'Indicators', x + 24, cy + 0.5, { font: `500 14px ${UI}`, color: C.text2 }) + 40;
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
  // right side
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
    const y = PLOT.y + 24 + i * 44;
    if (i === 0) pill(ctx, cx - 15, y - 15, 30, 30, { fill: C.activeBg, r: 7 });
    icon(ctx, icons, n, cx, y, 18, i === 0 ? 'active' : 'muted');
    if (i === 6 || i === 9) hline(ctx, cx - 12, cx + 12, y + 22);
  });
  vline(ctx, CHART.x + TOOLS_W, CHART.y + TB_H, CHART.y + CHART.h - 46, C.border);
}

function priceTag(ctx, y, label, fill, color = '#05110D') {
  const h = 24;
  pill(ctx, AXIS_X + 4, y - h / 2, CHART.x + CHART.w - AXIS_X - 10, h, { fill, r: 5 });
  text(ctx, label, AXIS_X + 12, y + 0.5, { font: `600 14px ${NUM}`, color });
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

export function buyTagBox(ctx, entrySlot, yOf, candle) {
  const label = 'BUY $500';
  const w = measure(ctx, label, `700 13px ${UI}`, '0.6px') + 44;
  const h = 26;
  const top = yOf(candle.h);
  return { x: slotX(entrySlot) - BODY_W / 2 - 8 - w, y: top - 16 - h, w, h, label };
}

function drawChart(ctx, s, position, pos, icons, t) {
  panel(ctx, CHART);
  drawToolbar(ctx, icons);
  drawTools(ctx, icons);
  const yOf = (p) => PRICE_BOT - ((Math.log(p) - s.logMin) / (s.logMax - s.logMin)) * (PRICE_BOT - PRICE_TOP);
  const plotR = PLOT.x + PLOT.w;

  ctx.save();
  ctx.beginPath();
  ctx.rect(PLOT.x, PLOT.y, PLOT.w + (CHART.x + CHART.w - AXIS_X), PLOT.h);
  ctx.clip();

  // grid + price axis labels
  const pLo = Math.exp(s.logMin - ((PRICE_BOT + 40 - PRICE_BOT) / (PRICE_BOT - PRICE_TOP)) * (s.logMax - s.logMin));
  const pHi = Math.exp(s.logMax + ((PRICE_TOP - PLOT.y - 14) / (PRICE_BOT - PRICE_TOP)) * (s.logMax - s.logMin));
  const levels = logLevels(pLo, pHi, yOf, 46);
  for (const [, y] of levels) hline(ctx, PLOT.x, plotR, y, C.grid);
  for (let i = 0; i < SLOTS; i += 10) vline(ctx, slotX(i), PLOT.y, PLOT.y + PLOT.h, C.grid);
  vline(ctx, AXIS_X, PLOT.y, PLOT.y + PLOT.h, C.border);
  const tagYs = [yOf(s.price)];
  if (pos?.open) tagYs.push(yOf(position.entryValue));
  for (const [v, y] of levels) {
    if (tagYs.some((ty) => Math.abs(ty - y) < 20)) continue;
    text(ctx, labelOf(v), AXIS_X + 12, y, { font: `500 13px ${NUM}`, color: C.text2 });
  }

  // volume
  const volRects = [];
  s.candles.forEach((k, i) => {
    const h = Math.max(2, (k.usd / s.vMax) * VOL_H);
    const x = Math.round(slotX(i) - BODY_W / 2);
    ctx.fillStyle = k.c >= k.o ? 'rgba(54, 224, 181, 0.42)' : 'rgba(240, 71, 95, 0.42)';
    ctx.fillRect(x, VOL_BOT - h, BODY_W, h);
    volRects.push({ x, y: VOL_BOT - h, w: BODY_W, h });
  });

  // candles' rectangles (also used to keep the entry line off them)
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

  // entry line (violet) behind the candles
  let entryY = null;
  if (pos?.open) {
    entryY = yOf(position.entryValue);
    const x0 = Math.round(slotX(position.entrySlot) + BODY_W / 2) + 2;
    const { y, pieces } = entryLinePieces(x0, plotR, entryY, [...marks, ...volRects]);
    ctx.strokeStyle = 'rgba(135, 119, 224, 0.85)';
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    for (const [a, b] of pieces) {
      ctx.moveTo(a, y);
      ctx.lineTo(b, y);
    }
    ctx.stroke();
  }

  // candles
  s.candles.forEach((k, i) => {
    const m = marks[i];
    const up = k.c >= k.o;
    ctx.fillStyle = up ? C.up : C.down;
    const wx = m.x + Math.floor(BODY_W / 2);
    ctx.fillRect(wx, yOf(k.h), 1, Math.max(1, yOf(k.l) - yOf(k.h)));
    ctx.fillRect(m.x, m.top, BODY_W, Math.max(1, m.bh));
  });

  // current price line + tag
  const last = s.candles[s.candles.length - 1];
  const lastUp = last.c >= last.o;
  const cy = yOf(s.price);
  ctx.strokeStyle = lastUp ? 'rgba(54, 224, 181, 0.7)' : 'rgba(240, 71, 95, 0.7)';
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 3]);
  ctx.beginPath();
  ctx.moveTo(PLOT.x, Math.round(cy) + 0.5);
  ctx.lineTo(plotR, Math.round(cy) + 0.5);
  ctx.stroke();
  ctx.setLineDash([]);
  const priceLabel = formatPrice(s.price).slice(1);
  let entryTagY = entryY;
  if (entryY !== null && Math.abs(entryY - cy) < 26) entryTagY = cy + (entryY >= cy ? 26 : -26);
  priceTag(ctx, cy, priceLabel, lastUp ? C.up : C.down, lastUp ? '#03140F' : '#FFFFFF');
  if (entryY !== null) priceTag(ctx, entryTagY, position.entryValue.toFixed(8), C.violet, '#FFFFFF');

  // BUY marker: tag above-left of the entry candle, leader to its top
  if (pos?.open) {
    const candle = s.candles[position.entrySlot];
    const b = buyTagBox(ctx, position.entrySlot, yOf, candle);
    const tx = slotX(position.entrySlot);
    ctx.strokeStyle = 'rgba(54, 224, 181, 0.75)';
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.moveTo(b.x + b.w - 6, b.y + b.h);
    ctx.lineTo(tx - 1, yOf(candle.h) - 4);
    ctx.stroke();
    ctx.save();
    ctx.shadowColor = C.shadow;
    ctx.shadowBlur = 8;
    pill(ctx, b.x, b.y, b.w, b.h, { fill: '#08201C', stroke: 'rgba(54, 224, 181, 0.55)', r: 13 });
    ctx.restore();
    ctx.beginPath();
    ctx.arc(b.x + 13, b.y + b.h / 2, 9, 0, Math.PI * 2);
    ctx.fillStyle = C.up;
    ctx.fill();
    text(ctx, 'B', b.x + 13, b.y + b.h / 2 + 0.5, { font: `800 11px ${UI}`, color: '#03140F', align: 'center' });
    text(ctx, b.label, b.x + 28, b.y + b.h / 2 + 0.5, { font: `700 13px ${UI}`, color: C.up, spacing: '0.6px' });
  }
  ctx.restore();

  // legend (OHLC of the forming candle)
  const lx = PLOT.x + 16;
  const ly = PLOT.y + 22;
  let x = lx;
  x += text(ctx, '$USELESS / USD', x, ly, { font: `600 15px ${UI}` });
  x += text(ctx, '  ·  1s  ·  SOL Sniper', x, ly, { font: `500 15px ${UI}`, color: C.text2 }) + 20;
  const col = lastUp ? C.up : C.down;
  for (const [k, v] of [['O', last.o], ['H', last.h], ['L', last.l], ['C', last.c]]) {
    x += text(ctx, k, x, ly, { font: `500 14px ${UI}`, color: C.text3 }) + 4;
    x += text(ctx, formatPrice(v).slice(1), x, ly, { font: `500 14px ${NUM}`, color: col }) + 14;
  }
  const ch = last.c / last.o - 1;
  text(ctx, `${ch >= 0 ? '+' : '−'}${Math.abs(ch * 100).toFixed(2)}%`, x, ly, { font: `600 14px ${NUM}`, color: col });
  x = lx;
  x += text(ctx, 'Volume', x, ly + 24, { font: `500 14px ${UI}`, color: C.text3 }) + 6;
  text(ctx, compactUsd(last.usd), x, ly + 24, { font: `500 14px ${NUM}`, color: col });

  // time axis
  const ty = PLOT.y + PLOT.h + 16;
  hline(ctx, PLOT.x, CHART.x + CHART.w, PLOT.y + PLOT.h, C.border);
  for (let i = 0; i < SLOTS; i += 10) text(ctx, s.clockOf(i), slotX(i), ty, { font: `500 13px ${NUM}`, color: C.text3, align: 'center' });

  // range row
  const ry = CHART.y + CHART.h - 23;
  hline(ctx, CHART.x, CHART.x + CHART.w, CHART.y + CHART.h - 46, C.border);
  let rx = CHART.x + 20;
  ['5y', '1y', '6m', '3m', '1m', '5d', '1d'].forEach((r) => {
    rx += text(ctx, r, rx, ry, { font: `500 14px ${UI}`, color: C.text2 }) + 18;
  });
  vline(ctx, rx, ry - 10, ry + 10);
  icon(ctx, icons, 'calendar', rx + 22, ry, 16);
  let rr = CHART.x + CHART.w - 20;
  rr -= text(ctx, 'auto', rr, ry, { font: `600 14px ${UI}`, color: C.activeText, align: 'right' }) + 16;
  rr -= text(ctx, 'log', rr, ry, { font: `600 14px ${UI}`, color: C.activeText, align: 'right' }) + 16;
  rr -= text(ctx, '%', rr, ry, { font: `500 14px ${UI}`, color: C.text2, align: 'right' }) + 18;
  vline(ctx, rr, ry - 10, ry + 10);
  text(ctx, `${s.clock} (UTC)`, rr - 18, ry, { font: `500 14px ${NUM}`, color: C.text2, align: 'right' });
}

// ---- sidebar ------------------------------------------------------------------------------
function drawActivity(ctx, s) {
  const r = { x: SIDE_X, y: CHART.y, w: SIDE_W, h: 96 };
  panel(ctx, r);
  const cols = [
    ['Volume 1m', compactUsd(s.stats.vol), C.text],
    [`Buys · ${s.stats.buys}`, compactUsd(s.stats.buyUsd), C.up],
    [`Sells · ${s.stats.sells}`, compactUsd(s.stats.sellUsd), C.down],
    ['Net Vol', `${s.stats.buyUsd >= s.stats.sellUsd ? '+' : '−'}${compactUsd(Math.abs(s.stats.buyUsd - s.stats.sellUsd))}`, s.stats.buyUsd >= s.stats.sellUsd ? C.up : C.down],
  ];
  const cw = (SIDE_W - 40) / 4;
  cols.forEach(([l, v, c], i) => {
    const x = r.x + 20 + i * cw;
    text(ctx, l, x, r.y + 26, { font: `500 13px ${UI}`, color: C.text3 });
    text(ctx, v, x, r.y + 50, { font: `600 16px ${NUM}`, color: c });
  });
  const bx = r.x + 20;
  const bw = SIDE_W - 40;
  const share = s.stats.buyUsd / Math.max(1, s.stats.buyUsd + s.stats.sellUsd);
  pill(ctx, bx, r.y + 72, bw, 4, { fill: C.down, r: 2 });
  pill(ctx, bx, r.y + 72, Math.max(4, bw * share - 2), 4, { fill: C.up, r: 2 });
}

function chip(ctx, label, right, cy, { fill, color, stroke = null }) {
  const w = measure(ctx, label, `700 12px ${UI}`, '0.8px') + 18;
  pill(ctx, right - w, cy - 11, w, 22, { fill, stroke, r: 6 });
  text(ctx, label, right - w / 2 + 0.4, cy + 0.5, { font: `700 12px ${UI}`, color, align: 'center', spacing: '0.8px' });
  return w;
}

function drawPosition(ctx, position, pos) {
  const r = { x: SIDE_X, y: CHART.y + 108, w: SIDE_W, h: 292 };
  panel(ctx, r);
  const L = r.x + 20;
  const R = r.x + r.w - 20;
  text(ctx, 'Position', L, r.y + 26, { font: `600 16px ${UI}` });
  const w1 = chip(ctx, pos.open ? 'OPEN' : 'NO POSITION', R, r.y + 26, pos.open ? { fill: C.activeBg, color: C.activeText, stroke: 'rgba(91, 123, 251, 0.45)' } : { fill: 'rgba(138, 151, 191, 0.10)', color: C.text2 });
  chip(ctx, 'SIMULATED', R - w1 - 8, r.y + 26, { fill: 'rgba(135, 119, 224, 0.12)', color: '#B7ADF5' });
  hline(ctx, r.x, r.x + r.w, r.y + 50);

  // PNL
  const dash = '—';
  text(ctx, 'Unrealized PNL', L, r.y + 74, { font: `500 13px ${UI}`, color: C.text3 });
  text(ctx, 'excl. fees & slippage', R, r.y + 74, { font: `500 12px ${UI}`, color: C.text3, align: 'right' });
  const sign = pos.open ? (pos.pnlCents > 0n ? 1 : pos.pnlCents < 0n ? -1 : 0) : 0;
  const tone = sign > 0 ? C.up : sign < 0 ? C.down : C.text;
  text(ctx, pos.open ? formatUsdCents(pos.pnlCents, { signed: true }) : dash, L, r.y + 106, { font: `700 30px ${NUM}`, color: pos.open ? tone : C.text3 });
  if (pos.open) {
    const roi = formatPctBp(pos.roiBp);
    const rw = measure(ctx, roi, `700 16px ${NUM}`) + 20;
    pill(ctx, R - rw, r.y + 92, rw, 28, { fill: sign >= 0 ? C.upBg : C.downBg, r: 7 });
    text(ctx, roi, R - rw / 2, r.y + 106.5, { font: `700 16px ${NUM}`, color: sign === 0 ? C.text : tone, align: 'center' });
  }
  hline(ctx, r.x + 20, r.x + r.w - 20, r.y + 132);

  // 2 x 2 grid
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
    text(ctx, value, x, y + 24, { font: `600 17px ${NUM}`, color: value === dash ? C.text3 : C.text });
  };
  const mid = r.x + r.w / 2 + 6;
  cell('Invested', pos.open ? formatUsdCents(position.sizeCents) : dash, L, r.y + 156);
  cell('Current Value', pos.open ? formatUsdCents(pos.valueCents) : dash, mid, r.y + 156);
  cell('Entry Price', pos.open ? position.entry.text : dash, L, r.y + 212, pos.open ? C.violet : C.text3);
  cell('Current Price', pos.price.text, mid, r.y + 212);
  hline(ctx, r.x + 20, r.x + r.w - 20, r.y + 252);
  text(ctx, 'Tokens Held', L, r.y + 272, { font: `500 13px ${UI}`, color: C.text3 });
  text(ctx, pos.open ? centsToString(position.tokensHundredths) : dash, R, r.y + 272, { font: `600 15px ${NUM}`, color: pos.open ? C.text : C.text3, align: 'right' });
}

function drawTrades(ctx, s, t) {
  const r = { x: SIDE_X, y: CHART.y + 412, w: SIDE_W, h: CHART.h - 412 };
  panel(ctx, r);
  const L = r.x + 20;
  const R = r.x + r.w - 20;
  let x = L;
  ['Trades', 'Holders', 'Top Traders'].forEach((tab, i) => {
    const w = text(ctx, tab, x, r.y + 24, { font: `${i === 0 ? 600 : 500} 15px ${UI}`, color: i === 0 ? C.text : C.text2 });
    if (i === 0) {
      ctx.fillStyle = C.violet;
      ctx.fillRect(x, r.y + 46, w, 2);
    }
    x += w + 26;
  });
  text(ctx, 'simulated tape', R, r.y + 24, { font: `500 12px ${UI}`, color: C.text3, align: 'right' });
  hline(ctx, r.x, r.x + r.w, r.y + 48);
  const cols = { age: L, type: L + 48, mc: L + 112, amount: L + 300, value: R };
  const hy = r.y + 66;
  text(ctx, 'Age', cols.age, hy, { font: `500 13px ${UI}`, color: C.text3 });
  text(ctx, 'Type', cols.type, hy, { font: `500 13px ${UI}`, color: C.text3 });
  text(ctx, 'MC', cols.mc, hy, { font: `500 13px ${UI}`, color: C.text3 });
  text(ctx, 'Amount', cols.amount, hy, { font: `500 13px ${UI}`, color: C.text3, align: 'right' });
  text(ctx, 'Value', cols.value, hy, { font: `500 13px ${UI}`, color: C.text3, align: 'right' });
  hline(ctx, r.x + 12, r.x + r.w - 12, r.y + 82);
  const rowH = 28;
  const rows = Math.floor((r.h - 92) / rowH);
  const shown = s.tape.slice(0, rows);
  const maxUsd = Math.max(...shown.map((x2) => x2.usd), 1);
  shown.forEach((tr, i) => {
    const y = r.y + 86 + i * rowH + rowH / 2;
    const buy = tr.side === 'buy';
    const col = buy ? C.up : C.down;
    const bw = 8 + (tr.usd / maxUsd) * 120;
    pill(ctx, R + 8 - bw, y - 11, bw, 22, { fill: buy ? 'rgba(54, 224, 181, 0.08)' : 'rgba(240, 71, 95, 0.08)', r: 4 });
    text(ctx, `${tr.age}s`, cols.age, y, { font: `500 14px ${NUM}`, color: C.text3 });
    text(ctx, buy ? 'Buy' : 'Sell', cols.type, y, { font: `600 14px ${UI}`, color: col });
    text(ctx, compactUsd(tr.price * 1e9), cols.mc, y, { font: `500 14px ${NUM}`, color: C.text });
    text(ctx, compactNum(tr.tokens), cols.amount, y, { font: `500 14px ${NUM}`, color: C.text2, align: 'right' });
    text(ctx, `$${tr.usd.toFixed(2)}`, cols.value, y, { font: `600 14px ${NUM}`, color: col, align: 'right' });
  });
}

// ---- status bar --------------------------------------------------------------------------
function drawStatus(ctx, s, t) {
  ctx.fillStyle = C.nav;
  ctx.fillRect(0, STATUS_Y, 1920, 1080 - STATUS_Y);
  hline(ctx, 0, 1920, STATUS_Y, C.border);
  const cy = STATUS_Y + 18;
  const label = 'Simulation Running';
  const w = measure(ctx, label, `500 13px ${UI}`) + 40;
  pill(ctx, 14, cy - 12, w, 24, { fill: 'rgba(54, 224, 181, 0.07)', stroke: 'rgba(54, 224, 181, 0.28)' });
  const ph = (t % 2) / 2;
  ctx.beginPath();
  ctx.arc(30, cy, 4 + 6 * (1 - (1 - ph) * (1 - ph)), 0, Math.PI * 2);
  ctx.fillStyle = `rgba(54, 224, 181, ${(0.3 * (1 - ph)).toFixed(3)})`;
  ctx.fill();
  ctx.beginPath();
  ctx.arc(30, cy, 4, 0, Math.PI * 2);
  ctx.fillStyle = C.up;
  ctx.fill();
  text(ctx, label, 42, cy + 0.5, { font: `500 13px ${UI}`, color: '#C9D1E6' });
  text(ctx, 'Simulated data · not financial results', 14 + w + 16, cy + 0.5, { font: `500 13px ${UI}`, color: C.text3 });
  text(ctx, `${s.clock} UTC`, 1904, cy + 0.5, { font: `500 13px ${NUM}`, color: C.text2, align: 'right' });
}

export function drawProFrame(ctx, t, market, position, assets, icons) {
  const s = { ...market.stateAt(t), clockOf: market.clockOf };
  const pos = position ? position.at(t) : null;
  ctx.save();
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, 1920, 1080);
  drawNav(ctx, assets, icons);
  drawTokenBar(ctx, s, assets, icons);
  drawChart(ctx, s, position, pos, icons, t);
  drawActivity(ctx, s);
  if (pos) drawPosition(ctx, position, pos);
  drawTrades(ctx, s, t);
  drawStatus(ctx, s, t);
  ctx.restore();
}
