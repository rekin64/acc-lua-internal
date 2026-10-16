// Canvas 2D renderer: draws one frame of the chart at time t (seconds).
// Pure function of (t, market, assets) so every frame is reproducible.
// Colours and proportions are measured from the reference capture (IMAGE 1).

import { W, H, SLOTS } from './engine.js';

export const THEME = {
  outside: '#01040B',
  bg: '#030917',
  up: '#6EF0CC',
  upGlow: 'rgba(110, 240, 205, 0.45)',
  down: '#E94E67',
  downGlow: 'rgba(233, 78, 103, 0.30)',
  price: '#70F0C6',
  title: '#F4F5F8',
  link: '#3D71B8',
  pillIdleBg: '#071025',
  pillIdleText: '#8090B8',
  pillOnBg: '#3B66F0',
  pillOnText: '#FFFFFF',
  axis: '#8A97BF',
  faint: '#3E4868',
  grid: 'rgba(130, 150, 210, 0.10)',
  separator: '#1C2440',
  volUpTop: '#377E8C',
  volUpBot: '#28487A',
  volDownTop: '#6A30A8',
  volDownBot: '#3A1E76',
};

// ---- layout (1920 x 1080) ----------------------------------------------------
const PANEL = { x: 10, y: 10, w: W - 20, h: H - 20, r: 26 };
const X0 = 36; // first slot left edge
const SEP_X = 1690; // separator between plot and price axis
const PITCH = (SEP_X - 2 - X0) / SLOTS;
const BODY_W = Math.round(PITCH * 0.58);
const WICK_W = 3;
const VOL_W = Math.round(PITCH * 0.82);
const PRICE_TOP = 196;
const PRICE_BOT = 948;
const VOL_BOT = 1008;
const VOL_H = 175;
const AXIS_X = 1712;
const RIGHT = 1872;
const HEADER_CY = 103;
const PILL_Y = 182;
const PILL_H = 58;
const PILLS = ['1s', '1m', '5m', '15m', '1h'];
const PILL_ON = 1;
const FONT = 'Inter, "Inter Display", system-ui, sans-serif';
const FIRST_MINUTE = 13 * 60 + 52; // time label of the first historical candle

const slotX = (i) => X0 + (i + 0.5) * PITCH;

function roundRect(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

export function formatPrice(p) {
  const decimals = Math.max(2, 3 - Math.floor(Math.log10(p))); // 4 significant digits
  return '$' + p.toFixed(decimals);
}

export function formatPct(pct) {
  const r = Math.round(pct);
  return (r >= 0 ? '+' : '-') + Math.abs(r).toLocaleString('en-US') + '%';
}

function niceStep(range, target) {
  const rough = range / target;
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const f = rough / mag;
  const nice = f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10;
  return Math.max(1e-6, nice * mag);
}

function drawExternalLink(ctx, x, y, s, color) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = s * 0.11;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();
  ctx.moveTo(x + s * 0.45, y + s * 0.1);
  ctx.lineTo(x + s * 0.18, y + s * 0.1);
  ctx.quadraticCurveTo(x + s * 0.08, y + s * 0.1, x + s * 0.08, y + s * 0.2);
  ctx.lineTo(x + s * 0.08, y + s * 0.82);
  ctx.quadraticCurveTo(x + s * 0.08, y + s * 0.92, x + s * 0.18, y + s * 0.92);
  ctx.lineTo(x + s * 0.8, y + s * 0.92);
  ctx.quadraticCurveTo(x + s * 0.9, y + s * 0.92, x + s * 0.9, y + s * 0.82);
  ctx.lineTo(x + s * 0.9, y + s * 0.55);
  ctx.moveTo(x + s * 0.62, y + s * 0.08);
  ctx.lineTo(x + s * 0.94, y + s * 0.08);
  ctx.lineTo(x + s * 0.94, y + s * 0.4);
  ctx.moveTo(x + s * 0.92, y + s * 0.1);
  ctx.lineTo(x + s * 0.48, y + s * 0.54);
  ctx.stroke();
  ctx.restore();
}

export function drawFrame(ctx, t, market, assets, opts = {}) {
  const s = market.stateAt(t);
  const T = THEME;
  const yOf = (p) => PRICE_BOT - ((p - s.yMin) / (s.yMax - s.yMin)) * (PRICE_BOT - PRICE_TOP);
  const vOf = (v) => (v / s.vMax) * VOL_H;

  ctx.save();
  ctx.fillStyle = T.outside;
  ctx.fillRect(0, 0, W, H);

  // ---- panel + ambient light ---------------------------------------------
  roundRect(ctx, PANEL.x, PANEL.y, PANEL.w, PANEL.h, PANEL.r);
  ctx.fillStyle = T.bg;
  ctx.fill();
  ctx.save();
  roundRect(ctx, PANEL.x, PANEL.y, PANEL.w, PANEL.h, PANEL.r);
  ctx.clip();

  // purple glow rising from the bottom edge
  ctx.save();
  ctx.translate(W * 0.55, H + 40);
  ctx.scale(1, 0.3);
  let g = ctx.createRadialGradient(0, 0, 0, 0, 0, 1250);
  g.addColorStop(0, 'rgba(58, 40, 175, 0.42)');
  g.addColorStop(0.45, 'rgba(36, 24, 120, 0.16)');
  g.addColorStop(1, 'rgba(20, 14, 80, 0)');
  ctx.fillStyle = g;
  ctx.fillRect(-1400, -1400, 2800, 2800);
  ctx.restore();

  // faint teal light behind the most recent candles
  const lastK = s.candles[s.candles.length - 1];
  const gx = slotX(s.candles.length - 1);
  const gy = yOf(lastK.c);
  g = ctx.createRadialGradient(gx, gy, 0, gx, gy, 520);
  g.addColorStop(0, 'rgba(60, 220, 190, 0.075)');
  g.addColorStop(1, 'rgba(60, 220, 190, 0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);

  // ---- grid + axes -------------------------------------------------------
  ctx.lineWidth = 1;
  ctx.strokeStyle = T.grid;
  const step = niceStep(s.yMax - s.yMin, 5);
  const levels = [];
  for (let v = Math.ceil(s.yMin / step) * step; v <= s.yMax; v += step) {
    const y = yOf(v);
    if (y < PRICE_TOP + 18 || y > PRICE_BOT + 10) continue;
    levels.push([v, y]);
    ctx.beginPath();
    ctx.moveTo(PANEL.x, Math.round(y) + 0.5);
    ctx.lineTo(SEP_X, Math.round(y) + 0.5);
    ctx.stroke();
  }
  ctx.font = `500 22px ${FONT}`;
  ctx.fillStyle = T.faint;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  for (let i = 0; i < SLOTS; i++) {
    const minute = FIRST_MINUTE + i;
    if (minute % 5 !== 0) continue;
    const x = Math.round(slotX(i)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(x, PRICE_TOP - 24);
    ctx.lineTo(x, VOL_BOT);
    ctx.stroke();
    const hh = String(Math.floor(minute / 60) % 24).padStart(2, '0');
    const mm = String(minute % 60).padStart(2, '0');
    ctx.fillText(`${hh}:${mm}`, x, VOL_BOT + 36);
  }

  ctx.fillStyle = T.separator;
  ctx.fillRect(SEP_X, PRICE_TOP - 24, 2, VOL_BOT - PRICE_TOP + 24);

  ctx.font = `500 28px ${FONT}`;
  ctx.fillStyle = T.axis;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  for (const [v, y] of levels) ctx.fillText(v.toFixed(6), AXIS_X, y);

  // ---- volume ------------------------------------------------------------
  s.candles.forEach((k, i) => {
    const h = Math.max(3, vOf(k.v));
    const x = slotX(i) - VOL_W / 2;
    const up = k.c >= k.o;
    const vg = ctx.createLinearGradient(0, VOL_BOT - h, 0, VOL_BOT);
    vg.addColorStop(0, up ? T.volUpTop : T.volDownTop);
    vg.addColorStop(1, up ? T.volUpBot : T.volDownBot);
    ctx.fillStyle = vg;
    ctx.globalAlpha = 0.92;
    roundRect(ctx, x, VOL_BOT - h, VOL_W, h, 2);
    ctx.fill();
    ctx.globalAlpha = 1;
  });

  // ---- candles -----------------------------------------------------------
  s.candles.forEach((k, i) => {
    const up = k.c >= k.o;
    const cx = slotX(i);
    const color = up ? T.up : T.down;
    const yH = yOf(k.h);
    const yL = yOf(k.l);
    let yO = yOf(k.o);
    let yC = yOf(k.c);
    let top = Math.min(yO, yC);
    let bh = Math.abs(yC - yO);
    if (bh < 3) {
      top -= (3 - bh) / 2;
      bh = 3;
    }
    ctx.save();
    ctx.shadowColor = up ? T.upGlow : T.downGlow;
    ctx.shadowBlur = up ? 18 : 10;
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(cx - WICK_W / 2), yH, WICK_W, Math.max(1, yL - yH));
    roundRect(ctx, Math.round(cx - BODY_W / 2), top, BODY_W, bh, 3);
    ctx.fill();
    ctx.restore();
  });

  // ---- header ------------------------------------------------------------
  const logo = assets.logo;
  const logoH = 64;
  const logoW = (logo.width / logo.height) * logoH;
  ctx.drawImage(logo, 52, HEADER_CY - logoH / 2, logoW, logoH);

  const divX = Math.round(52 + logoW + 34);
  ctx.fillStyle = T.separator;
  ctx.fillRect(divX, HEADER_CY - 30, 2, 60);

  const avR = 45;
  const avX = divX + 34 + avR;
  ctx.save();
  ctx.beginPath();
  ctx.arc(avX, HEADER_CY, avR, 0, Math.PI * 2);
  ctx.clip();
  const icon = assets.token;
  const inset = icon.width * 0.012; // trim the anti-aliased white corner pixels
  ctx.drawImage(icon, inset, inset, icon.width - 2 * inset, icon.height - 2 * inset, avX - avR, HEADER_CY - avR, avR * 2, avR * 2);
  ctx.restore();

  ctx.font = `600 46px ${FONT}`;
  ctx.fillStyle = T.title;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  const titleX = avX + avR + 24;
  ctx.fillText('$USELESS', titleX, HEADER_CY + 17);
  const tw = ctx.measureText('$USELESS').width;
  drawExternalLink(ctx, titleX + tw + 22, HEADER_CY - 17, 32, T.link);

  ctx.fillStyle = T.price;
  ctx.font = `700 50px ${FONT}`;
  ctx.textAlign = 'right';
  ctx.fillText(formatPrice(s.price), RIGHT, HEADER_CY - 6);
  ctx.fillText(formatPct(s.pct), RIGHT, HEADER_CY + 50);

  // timeframe pills
  let px = 52;
  PILLS.forEach((label, i) => {
    const on = i === PILL_ON;
    ctx.font = `${on ? 700 : 500} 28px ${FONT}`;
    const w = Math.max(84, ctx.measureText(label).width + 52);
    roundRect(ctx, px, PILL_Y, w, PILL_H, 13);
    ctx.fillStyle = on ? T.pillOnBg : T.pillIdleBg;
    ctx.fill();
    ctx.fillStyle = on ? T.pillOnText : T.pillIdleText;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, px + w / 2, PILL_Y + PILL_H / 2 + 1);
    px += w + 12;
  });

  // honest labelling: this is a simulation, not a real result
  if (opts.disclaimer !== false) {
    ctx.font = `500 20px ${FONT}`;
    ctx.fillStyle = T.faint;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'alphabetic';
    ctx.fillText('Simulated data', RIGHT, VOL_BOT + 36);
  }

  ctx.restore(); // panel clip

  // panel border
  roundRect(ctx, PANEL.x + 1, PANEL.y + 1, PANEL.w - 2, PANEL.h - 2, PANEL.r);
  g = ctx.createLinearGradient(0, PANEL.y, 0, PANEL.y + PANEL.h);
  g.addColorStop(0, 'rgba(70, 80, 190, 0.30)');
  g.addColorStop(1, 'rgba(95, 65, 215, 0.60)');
  ctx.strokeStyle = g;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();
}
