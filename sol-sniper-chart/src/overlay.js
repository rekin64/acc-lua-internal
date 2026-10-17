// Position overlay drawn on top of the chart: the PNL panel and the entry
// marker. The position is simulated, so no order, transaction or signature is
// shown, and the panel is labelled "Simulated position".

import { centsToString, formatPctBp, formatUsdCents } from './format.js';
import { BODY_W, PITCH, SEP_X, THEME, roundRect, slotX } from './ui.js';

const TNUM = '"Inter Tnum", Inter, system-ui, sans-serif';

const C = {
  bg: 'rgba(8, 15, 36, 0.72)',
  shadow: 'rgba(0, 0, 0, 0.45)',
  borderA: 'rgba(59, 102, 240, 0.55)', // blue
  borderB: 'rgba(135, 119, 224, 0.55)', // violet
  sep: 'rgba(130, 150, 210, 0.14)',
  label: '#8A97BF',
  value: '#F4F5F8',
  muted: '#56638B',
  footnote: '#7280A8', // 4.9:1 on the panel, legible yet discreet
  brand: '#5B7BFB', // SOL Sniper wordmark blue (solsniper.com)
  violet: '#8777E0',
  blueText: '#AFC0FF',
  blueBg: 'rgba(59, 102, 240, 0.16)',
  blueBorder: 'rgba(59, 102, 240, 0.60)',
  idleBg: 'rgba(138, 151, 191, 0.10)',
  idleBorder: 'rgba(138, 151, 191, 0.30)',
  line: 'rgba(135, 119, 224, 0.80)',
  buy: THEME.up, // turquoise of the up candles
  buyBg: 'rgba(7, 26, 32, 0.92)',
  buyBorder: 'rgba(110, 240, 204, 0.55)',
  statusText: '#C9D1E6',
  statusBg: 'rgba(110, 240, 204, 0.07)',
  statusBorder: 'rgba(110, 240, 204, 0.28)',
};

const ARROW_W = 9;
const ARROW_H = 12;

// ---- panel geometry -----------------------------------------------------
const PAD = 24;
const HEAD_H = 60;
const ROW_H = 38;
const PNL_ROW_H = 48;
const GAP = 8; // breathing room around the separators
const FOOT_H = 44;
const X = 52;
const Y = 268;
const W_ = 500;
const H_ = HEAD_H + 4 * ROW_H + 2 * GAP + ROW_H + PNL_ROW_H + ROW_H + GAP + FOOT_H;
export const PNL_BOX = { x: X, y: Y, w: W_, h: H_, r: 18 };

const tone = (sign) => (sign > 0n ? THEME.up : sign < 0n ? THEME.down : C.value);

function separator(ctx, y) {
  ctx.fillStyle = C.sep;
  ctx.fillRect(X + PAD, Math.round(y), W_ - 2 * PAD, 1);
}

const DASH = '—';

function row(ctx, top, h, label, value, { valueFont = `600 22px ${TNUM}`, color = C.value, dot = null } = {}) {
  const cy = top + h / 2;
  let lx = X + PAD;
  if (dot) {
    ctx.beginPath();
    ctx.arc(lx + 5, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = dot;
    ctx.fill();
    lx += 18;
  }
  ctx.textBaseline = 'middle';
  ctx.font = `500 20px ${TNUM}`;
  ctx.fillStyle = C.label;
  ctx.textAlign = 'left';
  ctx.fillText(label, lx, cy + 1);
  // empty values all use the same muted dash
  ctx.font = value === DASH ? `600 22px ${TNUM}` : valueFont;
  ctx.fillStyle = value === DASH ? C.muted : color;
  ctx.textAlign = 'right';
  ctx.fillText(value, X + W_ - PAD, cy + 1);
}

function chip(ctx, text, right, cy, open) {
  ctx.font = `600 14px ${TNUM}`;
  ctx.letterSpacing = '1.2px';
  const w = ctx.measureText(text).width + 22;
  const h = 26;
  roundRect(ctx, right - w, cy - h / 2, w, h, 13);
  ctx.fillStyle = open ? C.blueBg : C.idleBg;
  ctx.fill();
  ctx.lineWidth = 1;
  ctx.strokeStyle = open ? C.blueBorder : C.idleBorder;
  ctx.stroke();
  ctx.fillStyle = open ? C.blueText : C.label;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, right - w / 2 + 0.6, cy + 1);
  ctx.letterSpacing = '0px';
}

export function drawPositionPanel(ctx, position, pos, assets) {
  ctx.save();

  // soft drop shadow, outside the panel only (the panel itself is see-through)
  ctx.save();
  const outside = new Path2D();
  outside.rect(0, 0, ctx.canvas.width, ctx.canvas.height);
  outside.roundRect(X, Y, W_, H_, PNL_BOX.r);
  ctx.clip(outside, 'evenodd');
  ctx.shadowColor = C.shadow;
  ctx.shadowBlur = 28;
  ctx.shadowOffsetY = 10;
  roundRect(ctx, X, Y, W_, H_, PNL_BOX.r);
  ctx.fillStyle = '#000';
  ctx.fill();
  ctx.restore();

  roundRect(ctx, X, Y, W_, H_, PNL_BOX.r);
  ctx.fillStyle = C.bg;
  ctx.fill();
  const g = ctx.createLinearGradient(X, Y, X + W_, Y + H_);
  g.addColorStop(0, C.borderA);
  g.addColorStop(1, C.borderB);
  roundRect(ctx, X + 0.75, Y + 0.75, W_ - 1.5, H_ - 1.5, PNL_BOX.r);
  ctx.strokeStyle = g;
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // header: SOL Sniper — $USELESS, status
  const hcy = Y + HEAD_H / 2;
  const icon = assets.icon;
  const ih = 28;
  const iw = (icon.width / icon.height) * ih;
  ctx.drawImage(icon, X + PAD, hcy - ih / 2, iw, ih);
  ctx.font = `600 21px ${TNUM}`;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  let tx = X + PAD + iw + 12;
  ctx.fillStyle = C.brand;
  ctx.fillText('SOL Sniper', tx, hcy + 1);
  tx += ctx.measureText('SOL Sniper').width;
  ctx.fillStyle = C.label;
  ctx.fillText('  —  ', tx, hcy + 1);
  tx += ctx.measureText('  —  ').width;
  ctx.fillStyle = C.value;
  ctx.fillText('$USELESS', tx, hcy + 1);
  chip(ctx, pos.open ? 'OPEN' : 'NO POSITION', X + W_ - PAD, hcy, pos.open);
  separator(ctx, Y + HEAD_H);

  // position details
  const dash = DASH;
  let y = Y + HEAD_H;
  row(ctx, y, ROW_H, 'Invested', pos.open ? formatUsdCents(position.sizeCents) : dash);
  y += ROW_H;
  row(ctx, y, ROW_H, 'Entry Price', pos.open ? position.entry.text : dash, { dot: pos.open ? C.violet : C.muted });
  y += ROW_H;
  row(ctx, y, ROW_H, 'Tokens Held', pos.open ? centsToString(position.tokensHundredths) : dash);
  y += ROW_H;
  row(ctx, y, ROW_H, 'Current Price', pos.price.text);
  y += ROW_H + GAP;
  separator(ctx, y);
  y += GAP;

  // marked-to-market values
  row(ctx, y, ROW_H, 'Current Value', pos.open ? formatUsdCents(pos.valueCents) : dash);
  y += ROW_H;
  row(ctx, y, PNL_ROW_H, 'Unrealized PNL', pos.open ? formatUsdCents(pos.pnlCents, { signed: true }) : dash, {
    valueFont: `700 30px ${TNUM}`,
    color: pos.open ? tone(pos.pnlCents) : C.muted,
  });
  y += PNL_ROW_H;
  row(ctx, y, ROW_H, 'ROI', pos.open ? formatPctBp(pos.roiBp) : dash, {
    valueFont: `700 24px ${TNUM}`,
    color: pos.open ? tone(pos.roiBp) : C.muted,
  });
  y += ROW_H + GAP;
  separator(ctx, y);

  ctx.font = `500 16px ${TNUM}`;
  ctx.fillStyle = C.footnote;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText('Simulated position · Excl. fees & slippage', X + PAD, y + FOOT_H / 2 + 1);

  ctx.restore();
}

// ---- BUY marker ---------------------------------------------------------
const TAG_TEXT = 'BUY $500';
const TAG_H = 26;

// The arrow sits in the gap just left of the entry candle and points at it at
// the entry price, so the candle itself stays fully visible; the dashed line
// runs from the arrow tip through the entry candle to the price axis.
export function entryPoint(position, yOf) {
  return { x: slotX(position.entrySlot) - PITCH / 2, y: yOf(position.entryValue) };
}

// Right-pointing arrowhead, tip 3 px short of the entry candle body.
export function entryArrowBox(position, yOf) {
  const p = entryPoint(position, yOf);
  const tip = slotX(position.entrySlot) - BODY_W / 2 - 3;
  return { x: tip - ARROW_W, y: p.y - ARROW_H / 2, w: ARROW_W, h: ARROW_H };
}

export function entryTagBox(ctx, position, yOf) {
  const p = entryPoint(position, yOf);
  ctx.save();
  ctx.font = `700 15px ${TNUM}`;
  ctx.letterSpacing = '1px';
  const w = ctx.measureText(TAG_TEXT).width + 22;
  ctx.restore();
  return { x: p.x - 10 - w, y: p.y - 16 - TAG_H, w, h: TAG_H };
}

const DASH_ON = 7;
const DASH_OFF = 6;
const MIN_PIECE = 3; // drop dash fragments shorter than this (px)

// Dash pieces of the entry line at the entry price, from the dot to the price
// axis. `marks` holds the frame's candle and volume-bar rectangles: every
// dash is cut 1 px short of any mark crossing the line, so the line never
// touches a chart pixel, and fragments under MIN_PIECE px are dropped.
export function entryLinePieces(position, yOf, marks = []) {
  const p = entryPoint(position, yOf);
  const row = Math.floor(p.y);
  const x0 = slotX(position.entrySlot) - BODY_W / 2 - 1;
  const x1 = SEP_X - 6;
  // rows painted by a 1.5 px stroke centred on row + 0.5 (anti-aliasing included)
  const top = row - 1;
  const bottom = row + 2;
  const blocked = marks
    .filter((r) => r.y < bottom + 1 && r.y + r.h > top - 1)
    .map((r) => [Math.floor(r.x) - 1, Math.ceil(r.x + r.w) + 1]);
  const pieces = [];
  for (let a = x0; a < x1; a += DASH_ON + DASH_OFF) {
    let segs = [[a, Math.min(a + DASH_ON, x1)]];
    for (const [ba, bb] of blocked) {
      segs = segs.flatMap(([sa, sb]) => (bb <= sa || ba >= sb ? [[sa, sb]] : [[sa, Math.min(sb, ba)], [Math.max(sa, bb), sb]]));
    }
    for (const [sa, sb] of segs) if (sb - sa >= MIN_PIECE) pieces.push([sa, sb]);
  }
  return { y: row + 0.5, pieces };
}

export function drawEntryLine(ctx, position, yOf, marks = []) {
  const { y, pieces } = entryLinePieces(position, yOf, marks);
  ctx.save();
  ctx.strokeStyle = C.line;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (const [a, b] of pieces) {
    ctx.moveTo(a, y);
    ctx.lineTo(b, y);
  }
  ctx.stroke();
  ctx.restore();
}

// BUY arrow and "BUY $500" tag, above the candles.
export function drawEntryTag(ctx, position, yOf) {
  const p = entryPoint(position, yOf);
  const a = entryArrowBox(position, yOf);
  const b = entryTagBox(ctx, position, yOf);
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(a.x + a.w, p.y);
  ctx.lineTo(a.x, a.y);
  ctx.lineTo(a.x, a.y + a.h);
  ctx.closePath();
  ctx.fillStyle = C.buy;
  ctx.fill();

  // short leader from the tag to the arrow, so they read as one marker
  ctx.beginPath();
  ctx.moveTo(b.x + b.w - 10, b.y + b.h);
  ctx.lineTo(a.x - 1, a.y + 1);
  ctx.strokeStyle = 'rgba(110, 240, 204, 0.7)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  roundRect(ctx, b.x, b.y, b.w, b.h, 7);
  ctx.fillStyle = C.buyBg;
  ctx.fill();
  ctx.lineWidth = 1;
  ctx.strokeStyle = C.buyBorder;
  ctx.stroke();
  ctx.font = `700 15px ${TNUM}`;
  ctx.letterSpacing = '1px';
  ctx.fillStyle = C.buy;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(TAG_TEXT, b.x + b.w / 2 + 0.5, b.y + b.h / 2 + 1);
  ctx.restore();
}

// ---- "Simulation Running" status badge (top bar) -------------------------
const STATUS_TEXT = 'Simulation Running';
const STATUS_H = 36;
const PULSE_S = 2; // one slow halo every 2 s

export function statusBox(ctx, x, cy) {
  ctx.save();
  ctx.font = `500 19px ${TNUM}`;
  const w = 14 + 10 + 12 + ctx.measureText(STATUS_TEXT).width + 16;
  ctx.restore();
  return { x, y: cy - STATUS_H / 2, w, h: STATUS_H };
}

export function drawSimStatus(ctx, t, x, cy) {
  const b = statusBox(ctx, x, cy);
  ctx.save();
  roundRect(ctx, b.x, b.y, b.w, b.h, STATUS_H / 2);
  ctx.fillStyle = C.statusBg;
  ctx.fill();
  ctx.lineWidth = 1;
  ctx.strokeStyle = C.statusBorder;
  ctx.stroke();
  // dot with a soft halo that slowly grows and fades (no blinking)
  const dx = b.x + 14 + 5;
  const ph = (t % PULSE_S) / PULSE_S;
  const ease = 1 - (1 - ph) * (1 - ph);
  ctx.beginPath();
  ctx.arc(dx, cy, 5 + 7 * ease, 0, Math.PI * 2);
  ctx.fillStyle = `rgba(110, 240, 204, ${(0.32 * (1 - ph)).toFixed(3)})`;
  ctx.fill();
  ctx.beginPath();
  ctx.arc(dx, cy, 5, 0, Math.PI * 2);
  ctx.fillStyle = C.buy;
  ctx.fill();
  ctx.font = `500 19px ${TNUM}`;
  ctx.fillStyle = C.statusText;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(STATUS_TEXT, dx + 5 + 12, cy + 1);
  ctx.restore();
}
