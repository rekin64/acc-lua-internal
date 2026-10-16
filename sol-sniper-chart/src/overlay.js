// Position overlay drawn on top of the chart: the PNL panel and the entry
// marker. The position is simulated, so no order, transaction or signature is
// shown, and the panel is labelled "Simulated position".

import { centsToString, formatPctBp, formatUsdCents } from './format.js';
import { PITCH, SEP_X, THEME, roundRect, slotX } from './ui.js';

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
  violetText: '#C9C2FF',
  blueText: '#AFC0FF',
  blueBg: 'rgba(59, 102, 240, 0.16)',
  blueBorder: 'rgba(59, 102, 240, 0.60)',
  idleBg: 'rgba(138, 151, 191, 0.10)',
  idleBorder: 'rgba(138, 151, 191, 0.30)',
  line: 'rgba(135, 119, 224, 0.80)',
  tagBg: 'rgba(9, 13, 38, 0.90)',
  tagBorder: 'rgba(135, 119, 224, 0.60)',
};

const DOT_R = 4;

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
  row(ctx, y, ROW_H, 'Position Size', pos.open ? formatUsdCents(position.sizeCents) : dash);
  y += ROW_H;
  row(ctx, y, ROW_H, 'Entry Price', pos.open ? position.entry.text : dash, { dot: pos.open ? C.violet : C.muted });
  y += ROW_H;
  row(ctx, y, ROW_H, 'Tokens', pos.open ? centsToString(position.tokensHundredths) : dash);
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

// ---- entry marker -------------------------------------------------------
const TAG_TEXT = 'ENTRY — $500';
const TAG_H = 26;

// The dot sits in the gap just left of the entry candle, so the candle itself
// stays fully visible; the dashed line runs from it through the entry candle.
export function entryPoint(position, yOf) {
  return { x: slotX(position.entrySlot) - PITCH / 2, y: yOf(position.entryValue) };
}

export function entryDotBox(position, yOf) {
  const p = entryPoint(position, yOf);
  return { x: p.x - DOT_R, y: p.y - DOT_R, w: 2 * DOT_R, h: 2 * DOT_R };
}

export function entryTagBox(ctx, position, yOf) {
  const p = entryPoint(position, yOf);
  ctx.save();
  ctx.font = `600 15px ${TNUM}`;
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
  const x0 = p.x + DOT_R + 2;
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

// Entry dot and "ENTRY — $500" tag, above the candles.
export function drawEntryTag(ctx, position, yOf) {
  const p = entryPoint(position, yOf);
  const b = entryTagBox(ctx, position, yOf);
  ctx.save();
  ctx.beginPath();
  ctx.arc(p.x, p.y, DOT_R, 0, Math.PI * 2);
  ctx.fillStyle = C.violet;
  ctx.fill();

  roundRect(ctx, b.x, b.y, b.w, b.h, 7);
  ctx.fillStyle = C.tagBg;
  ctx.fill();
  ctx.lineWidth = 1;
  ctx.strokeStyle = C.tagBorder;
  ctx.stroke();
  ctx.font = `600 15px ${TNUM}`;
  ctx.letterSpacing = '1px';
  ctx.fillStyle = C.violetText;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(TAG_TEXT, b.x + b.w / 2 + 0.5, b.y + b.h / 2 + 1);
  ctx.restore();
}
