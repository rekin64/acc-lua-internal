// Theme colours and 1920x1080 layout shared by the chart and its overlays.
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
export const PANEL = { x: 10, y: 10, w: W - 20, h: H - 20, r: 26 };
export const X0 = 36; // first slot left edge
export const SEP_X = 1690; // separator between plot and price axis
export const PITCH = (SEP_X - 2 - X0) / SLOTS;
export const BODY_W = Math.round(PITCH * 0.58);
export const WICK_W = 3;
export const VOL_W = Math.round(PITCH * 0.82);
export const PRICE_TOP = 196;
export const PRICE_BOT = 948;
export const VOL_BOT = 1008;
export const VOL_H = 175;
export const AXIS_X = 1712;
export const RIGHT = 1872;
export const HEADER_CY = 103;
export const PILL_Y = 182;
export const PILL_H = 58;
export const PILLS = ['1s', '1m', '5m', '15m', '1h'];
export const PILL_ON = 1;
export const FONT = 'Inter, "Inter Display", system-ui, sans-serif';
export const FIRST_MINUTE = 13 * 60 + 52; // time label of the first historical candle

export const slotX = (i) => X0 + (i + 0.5) * PITCH;

export function roundRect(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}
