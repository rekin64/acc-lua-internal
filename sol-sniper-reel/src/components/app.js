// SOL Sniper trading terminal: a light, desktop web app (1920×1080) used as the
// "screen recording" in the reel. Every visual is a pure function of the state
// passed to update(state); there are no timers, transitions or random calls.
//
// Contract (see SPEC.md): createApp() -> { el, rect(name), update(state) }.
// All trades shown are simulated (the top bar carries a "Demo mode" chip).
import { clamp, lerp, prog, ease, rng, noise1, css, text } from '../lib/engine.js';
import { createLogo } from './brand.js';

/* ------------------------------------------------------------------ layout */
const FEED = { x: 24, y: 96, w: 560, h: 960 };
const CHART = { x: 608, y: 96, w: 744, h: 960 };
const TRADE = { x: 1376, y: 96, w: 520, h: 584 };
const POS = { x: 1376, y: 704, w: 520, h: 352 };
const TOAST = { right: 40, top: 84, w: 392 };

const ROW_H = 88;          // feed row height
const LIST_TOP = 144;      // feed list top (panel coordinates)
const PLOT = { x: 24, y: 216, w: 696, h: 480 }; // chart plot (panel coordinates)
const AX_W = 72;           // right price axis
const CW = PLOT.w - AX_W;  // candle area width
const PY0 = 40, PY1 = 360; // price area (plot coordinates)
const VY0 = 380, VY1 = 448; // volume band
const SLOT = 12, BODY = 8, X0 = 6;
const TAPE_DT = 0.62;      // seconds between trades on the tape
const TAG_CLEAR = 24;      // min px between an axis tag and an axis label

/* ------------------------------------------------------------------ market data (fictional) */
const ENTRY_USD = 0.0000412;   // GLINT entry price (MC $41.2K at 1B supply)
const SUPPLY = 1e9;
const TOK_PER_SOL = 18.2e6;    // GLINT received per SOL at the entry price
const BALANCE = 24.8;          // wallet balance before the demo's two buys (SOL)
const FEE = 0.005;             // priority fee per buy (SOL)
const SNIPE_SOL = 1;           // size of the feed snipe (SOL)

const TOK = {
  GLINT: { name: 'Glint', mint: '8hJ2…pump', liq: 84.2, mc: 41.2, ai: 94, age: 6, g: ['#7086F4', '#A979EE'] },
  ZORP: { name: 'Zorp', mint: 'Zr4q…pump', liq: 66.4, mc: 31.7, ai: 87, age: 5, g: ['#7ED37A', '#2FA9B8'] },
  NOODL: { name: 'Noodle', mint: 'Nd8x…pump', liq: 92.6, mc: 47.9, ai: 90, age: 3, g: ['#F6BE5A', '#EE7C4C'] },
  BLIPZ: { name: 'Blipz', mint: 'Bz1m…pump', liq: 57.3, mc: 22.6, ai: 83, age: 5, g: ['#5EBAF4', '#5A6CEB'] },
  KOBI: { name: 'Kobi', mint: 'Kb6t…pump', liq: 104.8, mc: 63.1, ai: 93, age: 2, g: ['#F28C62', '#C8517E'] },
  TOFFE: { name: 'Toffee', mint: 'Tf3w…pump', liq: 62.0, mc: 29.3, ai: 85, age: 4, g: ['#E9B27C', '#B8745A'] },
  PLUMB: { name: 'Plumb', mint: 'Pl9c…pump', liq: 76.5, mc: 38.4, ai: 89, age: 3, g: ['#A57EF2', '#6656D6'] },
  DOZY: { name: 'Dozy', mint: 'Dz2k…pump', liq: 55.9, mc: 21.7, ai: 81, age: 5, g: ['#8BD3E6', '#7B9CF0'] },
  MUNCH: { name: 'Munch', mint: 'Mn7r…pump', liq: 118.3, mc: 74.6, ai: 91, age: 2, g: ['#F39A72', '#E46C8A'] },
  WAFFL: { name: 'Waffle Club', mint: 'Wf5n…pump', liq: 61.8, mc: 27.9, ai: 81, age: 14, g: ['#F1C66E', '#D8925B'] },
  PIPPA: { name: 'Pippa', mint: 'Pp2v…pump', liq: 112.4, mc: 88.6, ai: 91, age: 27, g: ['#E68BD8', '#9B7AF0'] },
  DUNKO: { name: 'Dunko', mint: 'Dk4h…pump', liq: 53.1, mc: 19.4, ai: 84, age: 41, g: ['#86A6CC', '#4F6B9E'] },
  MOCHI: { name: 'Mochi Cat', mint: 'Mc1s…pump', liq: 146.0, mc: 132.5, ai: 92, age: 58, g: ['#F5A6B9', '#EFC07E'] },
  FROGO: { name: 'Frogo', mint: 'Fg8e…pump', liq: 97.3, mc: 71.0, ai: 88, age: 76, g: ['#5ECB8E', '#2C9FA0'] },
  QUILL: { name: 'Quill', mint: 'Qu6a…pump', liq: 58.6, mc: 24.1, ai: 82, age: 95, g: ['#9BA8F6', '#62C0E6'] },
  SPUDZ: { name: 'Spudz', mint: 'Sp3d…pump', liq: 71.2, mc: 36.8, ai: 86, age: 128, g: ['#CDA67E', '#8F6F57'] },
  CRUMB: { name: 'Crumb', mint: 'Cr5b…pump', liq: 64.7, mc: 30.2, ai: 83, age: 151, g: ['#E7B98A', '#C98466'] },
  OLLIE: { name: 'Ollie', mint: 'Ol8p…pump', liq: 88.9, mc: 52.6, ai: 90, age: 176, g: ['#78C4F2', '#4F8BE0'] },
  PEBL: { name: 'Pebble', mint: 'Pb2y…pump', liq: 52.4, mc: 18.9, ai: 80, age: 204, g: ['#B3B8C9', '#7D849C'] },
};
const INCOMING = ['ZORP', 'GLINT', 'NOODL', 'BLIPZ', 'KOBI', 'TOFFE', 'PLUMB', 'DOZY', 'MUNCH'];
// 7 older rows per the contract, plus 3 further down so the list always fills the panel.
const OLDER = ['WAFFL', 'PIPPA', 'DUNKO', 'MOCHI', 'FROGO', 'QUILL', 'SPUDZ', 'CRUMB', 'OLLIE', 'PEBL'];
const AGE_BUMP = 2; // feed: extra seconds of age per row inserted above (ages also tick with t)

// GLINT's size is derived from the two buys in the state (feed snipe + trade panel).
const POSITIONS = [
  { tk: 'GLINT', size: 0, entry: 0.0000412 },
  { tk: 'MOCHI', size: 2.6, entry: 0.0001184 },
  { tk: 'ZORP', size: 0.8, entry: 0.0000329 },
  { tk: 'FROGO', size: 3.8, entry: 0.0000473 },
];

const PRESETS = [0.25, 0.5, 1, 2];

/* Candles: 48 × 1s, from the pair's launch. Closes are hand-shaped relative to
   the entry price (1.0): launch pop, then ~40s of chop with higher lows under
   the 1.0 range high, the snipe fills late in candle 41 as it breaks the range,
   then a fast climb with one pullback.
   The reel's timeline keys line up with this path: reveal 0.871 → fill,
   0.904 → +24%, 0.931–0.959 → +38%, 0.975–1.0 → +42% (glintPnl(reveal) gives
   the exact value). Opens, wicks and volume get seeded noise. */
const CLOSES = [
  0.872, 0.902, 0.948, 0.968, 0.931, 0.906, 0.893, 0.879, 0.902, 0.921,
  0.899, 0.884, 0.903, 0.926, 0.942, 0.929, 0.914, 0.931, 0.952, 0.941,
  0.924, 0.946, 0.961, 0.954, 0.972, 0.958, 0.941, 0.953, 0.969, 0.981,
  0.964, 0.951, 0.963, 0.976, 0.986, 0.972, 0.959, 0.968, 0.982, 0.975,
  0.968, 1.004, 1.198, 1.339, 1.393, 1.381, 1.428, 1.418,
];
const VOLS = [
  0.92, 0.74, 0.66, 0.58, 0.47, 0.36, 0.31, 0.34, 0.27, 0.3,
  0.24, 0.29, 0.22, 0.31, 0.34, 0.25, 0.21, 0.27, 0.33, 0.26,
  0.23, 0.29, 0.32, 0.24, 0.35, 0.27, 0.3, 0.24, 0.31, 0.37,
  0.26, 0.25, 0.28, 0.33, 0.38, 0.27, 0.24, 0.29, 0.35, 0.3,
  0.32, 0.56, 1.0, 0.86, 0.64, 0.5, 0.7, 0.46,
];
const WICK_UP = { 3: 0.012, 14: 0.005, 29: 0.004, 42: 0.024, 44: 0.03, 46: 0.02 };
const WICK_DN = { 7: 0.008, 26: 0.007, 43: 0.012, 45: 0.026 };
const ENTRY_IDX = 41;      // the snipe fills late in this candle
const ENTRY_AT = 41.78;    // candles revealed when the fill lands (B badge pops in)
const LAUNCH_OPEN = 0.842;
const T0_SEC = 14 * 3600 + 2 * 60 + 6; // wall clock of candle 0 (14:02:06)
const N = CLOSES.length;
const CANDLES = (() => {
  const R = rng(4127);
  const out = [];
  for (let i = 0; i < N; i++) {
    const c = CLOSES[i] * (1 + (R() - 0.5) * 0.003);
    const o = i === 0 ? LAUNCH_OPEN : out[i - 1].c * (1 + (R() - 0.5) * 0.0028);
    const body = Math.abs(c - o);
    const hi = Math.max(o, c) + 0.002 + R() * 0.007 + body * R() * 0.35 + (WICK_UP[i] || 0);
    const lo = Math.min(o, c) - 0.002 - R() * 0.006 - body * R() * 0.25 - (WICK_DN[i] || 0);
    out.push({ o, c, h: hi, l: lo, v: VOLS[i] * (0.86 + R() * 0.28) });
  }
  return out;
})();
const VMAX = Math.max(...CANDLES.map((c) => c.v));

/** GLINT price path (relative to entry, no live wiggle) at a given chart reveal. */
function pathAt(reveal) {
  const r = clamp(reveal) * N;
  const n = Math.min(Math.floor(r), N);
  if (n >= N) return CANDLES[N - 1].c;
  const f = r - n;
  if (f <= 0.0005) return n > 0 ? CANDLES[n - 1].c : CANDLES[0].o;
  return lerp(CANDLES[n].o, CANDLES[n].c, ease.inOutSine(f));
}
/** Unrealised PnL (%) of the sniped GLINT entry at a given chart reveal. Lets a
 *  timeline key chart.pnl / positions.pnl.GLINT to exactly what the chart draws. */
export function glintPnl(reveal) {
  return (pathAt(reveal) - 1) * 100;
}

/* ------------------------------------------------------------------ helpers */
const usd = (rel) => rel * ENTRY_USD;
const age = (s) => (s < 60 ? `${Math.floor(s)}s` : `${Math.floor(s / 60)}m`);
const kfmt = (v) => (v >= 1000 ? `$${(v / 1000).toFixed(1)}K` : `$${v.toFixed(0)}`);
/** 3 significant digits: 910K, 2.00M, 2.35M, 13.0M. */
const sig3 = (x) => (x >= 100 ? x.toFixed(0) : x >= 10 ? x.toFixed(1) : x.toFixed(2));
const mfmt = (v) => (v >= 999.5e3 ? `${sig3(v / 1e6)}M` : `${sig3(v / 1e3)}K`);
/** One price notation app-wide: "0.0₄5641" (zero count as a subscript) once a
 *  price has 4+ leading zeros, otherwise plain ("0.0001184"). */
function pxParts(v, digits = 4) {
  const m = /^0\.(0*)(\d+)/.exec(Math.abs(v).toFixed(14));
  const z = m ? m[1].length : 0;
  if (!m || z < 4) return { sub: false, s: v.toFixed(z + digits) };
  return { sub: true, z, d: m[2].slice(0, digits) };
}
function pxHTML(v, dollar = true, digits = 4) {
  const p = pxParts(v, digits), $ = dollar ? '$' : '';
  return p.sub ? `${$}0.0<sub>${p.z}</sub>${p.d}` : `${$}${p.s}`;
}
/** Same notation inside an SVG <text> (tspans). */
function pxSVG(node, v, digits = 4) {
  const p = pxParts(v, digits);
  const k = p.sub ? `${p.z}|${p.d}` : p.s;
  if (node.__px === k) return;
  node.__px = k;
  node.innerHTML = p.sub ? `0.0<tspan class="ap-sub" dy="2.6">${p.z}</tspan><tspan dy="-2.6">${p.d}</tspan>` : p.s;
}
/** HTML price into a node, cached on the formatted string. */
function setPx(node, v, dollar = true, digits = 4) {
  const html = pxHTML(v, dollar, digits);
  if (node.__px === html) return;
  node.__px = html;
  node.innerHTML = html;
}
const pct = (v, d = 1) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(d)}%`;
const hex = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
const mix = (a, b, t) => {
  const A = hex(a), B = hex(b);
  return `rgb(${A.map((v, i) => Math.round(lerp(v, B[i], clamp(t)))).join(',')})`;
};
function attr(el, name, value) {
  const cache = el.__attr || (el.__attr = {});
  const v = typeof value === 'number' ? +value.toFixed(2) : value;
  if (cache[name] === v) return;
  cache[name] = v;
  el.setAttribute(name, v);
}
function el(html) {
  const tpl = document.createElement('template');
  tpl.innerHTML = html.trim();
  return tpl.content.firstElementChild;
}

/* ------------------------------------------------------------------ icons (inline SVG, currentColor) */
const I = {
  bolt: (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M9.36 1.43 3.52 8.76c-.3.38-.03.94.45.94h3.2l-.9 4.38c-.1.5.53.79.85.39l5.86-7.4c.3-.38.03-.94-.45-.94H9.3l.93-4.32c.11-.5-.53-.8-.86-.38Z" fill="currentColor"/></svg>`,
  check: (s = 14, w = 2) => `<svg width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M3.5 8.4 6.6 11.4 12.6 4.8" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  spin: (s = 14) => `<svg class="ap-spin" width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-opacity=".28" stroke-width="2"/><path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
  up: (s = 10) => `<svg width="${s}" height="${s}" viewBox="0 0 10 10" fill="none" aria-hidden="true"><path d="M5 8.2V2M2.3 4.6 5 1.9l2.7 2.7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  down: (s = 10) => `<svg width="${s}" height="${s}" viewBox="0 0 10 10" fill="none" aria-hidden="true"><path d="M5 1.8V8M2.3 5.4 5 8.1l2.7-2.7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  arrowR: (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M2.5 8h10.4M9 4.2 12.9 8 9 11.8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  search: (s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="7.2" cy="7.2" r="4.7" stroke="currentColor" stroke-width="1.5"/><path d="m10.8 10.8 3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,
  bell: (s = 18) => `<svg width="${s}" height="${s}" viewBox="0 0 18 18" fill="none" aria-hidden="true"><path d="M4.5 12.8V8.1a4.5 4.5 0 0 1 9 0v4.7l1.2 1.4H3.3l1.2-1.4Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M7.4 15.6a1.8 1.8 0 0 0 3.2 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,
  chev: (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="m3.2 4.6 2.8 2.8 2.8-2.8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  pause: (s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><rect x="4.2" y="3.5" width="2.4" height="9" rx="1" fill="currentColor"/><rect x="9.4" y="3.5" width="2.4" height="9" rx="1" fill="currentColor"/></svg>`,
  sliders: (s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M2.5 5h6.3M12.2 5h1.3M2.5 11h1.3M7.2 11h6.3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="10.5" cy="5" r="1.7" stroke="currentColor" stroke-width="1.5"/><circle cx="5.5" cy="11" r="1.7" stroke="currentColor" stroke-width="1.5"/></svg>`,
  copy: (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" aria-hidden="true"><rect x="4" y="4" width="6.2" height="6.2" rx="1.4" stroke="currentColor" stroke-width="1.2"/><path d="M8 2.6V2.4c0-.6-.4-1-1-1H2.8c-.6 0-1 .4-1 1V7c0 .6.4 1 1 1H3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>`,
  ge: () => `<svg class="ap-ge" width="7" height="9" viewBox="0 0 7 9" fill="none" aria-hidden="true"><path d="M1 .9 6 3.3 1 5.7M1 8.1h5" stroke="currentColor" stroke-width="1.45" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  plus: (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 2.5v7M2.5 6h7" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`,
  sort: (s = 10) => `<svg width="${s}" height="${s}" viewBox="0 0 10 10" fill="none" aria-hidden="true"><path d="M5 2v6M2.6 5.8 5 8.2l2.4-2.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  x: (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="m3.2 3.2 5.6 5.6M8.8 3.2 3.2 8.8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`,
  candles: (s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M4.5 2v12M11.5 2.5v11" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><rect x="2.8" y="5" width="3.4" height="5.5" rx=".8" fill="currentColor"/><rect x="9.8" y="4.2" width="3.4" height="6.8" rx=".8" stroke="currentColor" stroke-width="1.3"/></svg>`,
  expand: (s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M9.5 2.8h3.7v3.7M6.5 13.2H2.8V9.5M13.2 2.8 9 7M2.8 13.2 7 9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  wallet: (s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M2.5 4.8c0-.9.7-1.6 1.6-1.6h7.4v1.6" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><rect x="2.5" y="4.8" width="11" height="8" rx="1.8" stroke="currentColor" stroke-width="1.4"/><circle cx="10.8" cy="8.8" r=".95" fill="currentColor"/></svg>`,
  shield: (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 1.3 2.3 2.7v3c0 2.3 1.6 4.2 3.7 4.9 2.1-.7 3.7-2.6 3.7-4.9v-3L6 1.3Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="m4.3 6 1.2 1.2 2.3-2.4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  spark: (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 .8c.4 2.9 1.6 4.4 4.6 5.2-3 .8-4.2 2.3-4.6 5.2-.4-2.9-1.6-4.4-4.6-5.2 3-.8 4.2-2.3 4.6-5.2Z" fill="currentColor"/></svg>`,
  info: (s = 13) => `<svg width="${s}" height="${s}" viewBox="0 0 14 14" fill="none" aria-hidden="true"><circle cx="7" cy="7" r="5.6" stroke="currentColor" stroke-width="1.2"/><path d="M7 6.3v3.3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><circle cx="7" cy="4.4" r=".8" fill="currentColor"/></svg>`,
};
/** SOL coin: dark disc with the three slanted Solana bars (outer bars lean one
 *  way, the middle bar the other), shaded teal → violet with solid fills. */
const solCoin = (s = 18) => `<svg width="${s}" height="${s}" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10" fill="#15161C"/><path d="M7.35 5.3h8.2l-2.2 2.25h-8.2z" fill="#B48CF6"/><path d="M5.15 8.88h8.2l2.2 2.25h-8.2z" fill="#8FA6F2"/><path d="M7.35 12.45h8.2l-2.2 2.25h-8.2z" fill="#5FD3BE"/></svg>`;

function avatar(tk, s) {
  const [a, b] = TOK[tk].g;
  return `<div class="ap-av" style="width:${s}px;height:${s}px;font-size:${Math.round(s * 0.4)}px;background:radial-gradient(120% 120% at 28% 18%, rgba(255,255,255,.32) 0%, rgba(255,255,255,0) 46%), linear-gradient(140deg, ${a} 0%, ${b} 100%)">${tk[0]}</div>`;
}
function aiPill(score) {
  const tier = score >= 90 ? 'g' : score >= 80 ? 'p' : 'n';
  return `<div class="ap-ai ap-ai--${tier}">${I.spark(12)}<span>${score}</span></div>`;
}

/* ------------------------------------------------------------------ build */
let instances = 0;

export function createApp() {
  const root = el(`<div class="app"></div>`);

  /* ---------- top bar ---------- */
  const top = el(`<div class="ap-top">
      <div class="ap-logo-slot"></div>
      <div class="ap-tabs">
        <div class="ap-tab ap-on">Terminal</div>
        <div class="ap-tab">Positions<span class="ap-cnt ap-tab-cnt">4</span></div>
        <div class="ap-tab">Wallet</div>
        <div class="ap-tab">Settings</div>
      </div>
      <div class="ap-search">${I.search(16)}<span>Search token or paste address</span><kbd>/</kbd></div>
      <div class="ap-right">
        <div class="ap-demo"><i></i><b>Demo mode</b><span>· simulated</span></div>
        <div class="ap-net"><i></i>Solana<span>38 ms</span></div>
        <div class="ap-bal">${solCoin(20)}<b class="ap-bal-v">24.80</b><span>SOL</span>${I.chev(12)}</div>
        <div class="ap-ibtn ap-bell">${I.bell(18)}<i></i></div>
        <div class="ap-me">AK</div>
      </div>
    </div>`);
  const logo = createLogo({ size: 20 });
  top.querySelector('.ap-logo-slot').appendChild(logo);
  root.appendChild(top);

  /* ---------- feed ---------- */
  const feed = el(`<div class="ap-panel ap-feed" style="left:${FEED.x}px;top:${FEED.y}px;width:${FEED.w}px;height:${FEED.h}px">
      <div class="ap-fhead">
        <div class="ap-live"><i class="ap-live-ring"></i><i class="ap-live-dot"></i></div>
        <div class="ap-h">New pairs</div>
        <div class="ap-fmeta">38 new / min</div>
        <div class="ap-fact"><div class="ap-ibtn ap-ibtn--b">${I.pause(15)}</div><div class="ap-ibtn ap-ibtn--b">${I.sliders(16)}</div></div>
      </div>
      <div class="ap-chips">
        <div class="ap-chip">AI score ${I.ge()} 80</div>
        <div class="ap-chip">Liq ${I.ge()} 50 SOL</div>
        <div class="ap-chip">${I.shield(12)}Mint revoked</div>
        <div class="ap-chip ap-chip--ghost">${I.plus(12)}Filter</div>
      </div>
      <div class="ap-cols ap-fgrid">
        <div>Token</div><div class="ap-r">Age${I.sort(10)}</div><div class="ap-r">Liq</div><div class="ap-r">MC</div><div class="ap-ctr">AI</div><div></div>
      </div>
      <div class="ap-list"></div>
    </div>`);
  root.appendChild(feed);
  const list = feed.querySelector('.ap-list');
  const liveRing = feed.querySelector('.ap-live-ring');
  const rows = {};
  for (const tk of [...INCOMING, ...OLDER]) {
    const d = TOK[tk];
    const r = el(`<div class="ap-frow">
        <div class="ap-frow-bg"></div><div class="ap-acc"></div>
        <div class="ap-frow-in ap-fgrid">
          <div class="ap-tk">${avatar(tk, 40)}<div class="ap-tk-t"><div class="ap-tk-s">$${tk}</div><div class="ap-tk-n">${d.name}</div></div></div>
          <div class="ap-r ap-age">0s</div>
          <div class="ap-r"><span class="ap-n">${d.liq.toFixed(1)}</span><span class="ap-u">SOL</span></div>
          <div class="ap-r ap-n">$${d.mc.toFixed(1)}K</div>
          <div class="ap-ctr">${aiPill(d.ai)}</div>
          <div class="ap-end"><div class="ap-snipe">
            <div class="ap-sn-soft"></div><div class="ap-sn-grad"></div><div class="ap-sn-ok"></div><div class="ap-sn-shade"></div>
            <div class="ap-sn-c ap-sn-idle">${I.bolt(13)}<span>Snipe</span></div>
            <div class="ap-sn-c ap-sn-pend">${I.spin(13)}<span>Sniping</span></div>
            <div class="ap-sn-c ap-sn-done">${I.check(13, 2.2)}<span>Bought</span></div>
          </div></div>
        </div>
      </div>`);
    list.appendChild(r);
    rows[tk] = {
      el: r,
      bg: r.querySelector('.ap-frow-bg'),
      acc: r.querySelector('.ap-acc'),
      inner: r.querySelector('.ap-frow-in'),
      age: r.querySelector('.ap-age'),
      ai: r.querySelector('.ap-ai'),
      snipe: r.querySelector('.ap-snipe'),
      snSoft: r.querySelector('.ap-sn-soft'),
      snGrad: r.querySelector('.ap-sn-grad'),
      snOk: r.querySelector('.ap-sn-ok'),
      snShade: r.querySelector('.ap-sn-shade'),
      snIdle: r.querySelector('.ap-sn-idle'),
      snPend: r.querySelector('.ap-sn-pend'),
      snDone: r.querySelector('.ap-sn-done'),
      spin: r.querySelector('.ap-spin'),
    };
  }

  /* ---------- chart ---------- */
  const chart = el(`<div class="ap-panel ap-chart" style="left:${CHART.x}px;top:${CHART.y}px;width:${CHART.w}px;height:${CHART.h}px">
      <div class="ap-chead">
        ${avatar('GLINT', 40)}
        <div class="ap-ct">
          <div class="ap-ct-s">$GLINT<span>/ SOL</span></div>
          <div class="ap-ct-n">Glint<i></i>8hJ2…pump${I.copy(12)}</div>
        </div>
        <div class="ap-tf"><div class="ap-on">1s</div><div>15s</div><div>1m</div><div>5m</div><div>1h</div></div>
        <div class="ap-ibtn ap-ibtn--b">${I.candles(16)}</div>
        <div class="ap-ibtn ap-ibtn--b">${I.expand(16)}</div>
      </div>
      <div class="ap-cprice">
        <div class="ap-bigp"></div>
        <div class="ap-chg"><span class="ap-chg-ic"></span><span class="ap-chg-v"></span></div>
        <div class="ap-chg-l">5m</div>
        <div class="ap-unit"><div class="ap-on">USD</div><div>SOL</div></div>
      </div>
      <div class="ap-stats">
        <div><span>Market cap</span><b class="ap-st-mc"></b></div>
        <div><span>Liquidity</span><b class="ap-st-liq"></b></div>
        <div><span>Holders</span><b class="ap-st-hold"></b></div>
        <div><span>Vol 5m</span><b class="ap-st-vol"></b></div>
      </div>
      <div class="ap-plot" style="left:${PLOT.x}px;top:${PLOT.y}px;width:${PLOT.w}px;height:${PLOT.h}px"></div>
      <div class="ap-tape">
        <div class="ap-tape-h"><div class="ap-h ap-h--s">Recent trades</div><div class="ap-ratio"><span class="ap-ratio-l"></span><div class="ap-ratio-b"><i></i></div></div></div>
        <div class="ap-tgrid ap-tcols"><div>Side</div><div class="ap-r">Total</div><div class="ap-r">Amount</div><div class="ap-r">Price</div><div class="ap-r">Maker</div><div class="ap-r">Age</div></div>
        <div class="ap-tlist"></div>
      </div>
    </div>`);
  root.appendChild(chart);
  const bigP = chart.querySelector('.ap-bigp');
  const chg = chart.querySelector('.ap-chg');
  const chgIc = chart.querySelector('.ap-chg-ic');
  const chgV = chart.querySelector('.ap-chg-v');
  const stMc = chart.querySelector('.ap-st-mc'), stLiq = chart.querySelector('.ap-st-liq');
  const stHold = chart.querySelector('.ap-st-hold'), stVol = chart.querySelector('.ap-st-vol');
  const plot = chart.querySelector('.ap-plot');
  const ratioL = chart.querySelector('.ap-ratio-l'), ratioB = chart.querySelector('.ap-ratio-b i');

  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('width', PLOT.w);
  svg.setAttribute('height', PLOT.h);
  svg.setAttribute('viewBox', `0 0 ${PLOT.w} ${PLOT.h}`);
  svg.setAttribute('class', 'ap-svg');
  plot.appendChild(svg);
  const mk = (tag, attrs = {}, parent = svg) => {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    parent.appendChild(n);
    return n;
  };
  // SVG ids must be unique per instance (the reel mounts two apps in one document)
  const uid = `ap${++instances}`;
  const defs = mk('defs');
  defs.innerHTML = `<linearGradient id="${uid}B" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--ss-wordmark)"/><stop offset="1" style="stop-color:var(--ss-purple)"/></linearGradient>
    <clipPath id="${uid}E"><rect x="0" y="0" width="0" height="${PLOT.h}"/></clipPath>`;
  const eClipRect = defs.querySelector('clipPath rect');
  const gGrid = mk('g', { class: 'ap-grid' });
  const hGrid = Array.from({ length: 9 }, () => mk('line', { x1: 0, x2: CW }, gGrid));
  const vGrid = Array.from({ length: 7 }, () => mk('line', { y1: 0, y2: VY1 }, gGrid));
  mk('line', { x1: CW + 0.5, x2: CW + 0.5, y1: 0, y2: PLOT.h - 24, class: 'ap-axline' });
  mk('line', { x1: 0, x2: PLOT.w, y1: VY1 + 8.5, y2: VY1 + 8.5, class: 'ap-axline' });
  const gVol = mk('g');
  const vols = CANDLES.map(() => mk('rect', { width: BODY, rx: 1 }, gVol));
  const gC = mk('g');
  const wicks = CANDLES.map(() => mk('rect', { width: 1.25 }, gC));
  const bodies = CANDLES.map(() => mk('rect', { width: BODY, rx: 1 }, gC));
  const curLine = mk('line', { x1: 0, x2: CW, class: 'ap-curline' });
  const gEntry = mk('g', { 'clip-path': `url(#${uid}E)` });
  const entryLine = mk('line', { x1: 0, x2: CW, class: 'ap-entryline' }, gEntry);
  const axLabels = Array.from({ length: 9 }, () => mk('text', { x: CW + 10, class: 'ap-axt' }));
  const tLabels = Array.from({ length: 7 }, () => mk('text', { y: PLOT.h - 7, class: 'ap-tt', 'text-anchor': 'middle' }));
  const gETag = mk('g');
  const eTagR = mk('rect', { x: CW + 4, width: AX_W - 6, height: 20, rx: 5, class: 'ap-tag-e' }, gETag);
  const eTagT = mk('text', { x: CW + 10, class: 'ap-tagt' }, gETag);
  const gCTag = mk('g');
  const cTagR = mk('rect', { x: CW + 4, width: AX_W - 6, height: 20, rx: 5 }, gCTag);
  const cTagT = mk('text', { x: CW + 10, class: 'ap-tagt' }, gCTag);
  const gB = mk('g');
  mk('path', { d: 'M0 -13.5 L4 -9 L-4 -9 Z', class: 'ap-b-pt' }, gB);
  mk('circle', { r: 9.5, fill: `url(#${uid}B)` }, gB);
  mk('circle', { r: 9.5, fill: 'none', stroke: '#FFFFFF', 'stroke-opacity': '.9', 'stroke-width': 1.5 }, gB);
  mk('text', { y: 3.6, 'text-anchor': 'middle', class: 'ap-bt' }, gB).textContent = 'B';

  const ohlc = el(`<div class="ap-ohlc"><span class="ap-ohlc-t">GLINT / SOL · 1s</span><span>O <b class="o"></b></span><span>H <b class="h"></b></span><span>L <b class="l"></b></span><span>C <b class="c"></b></span></div>`);
  plot.appendChild(ohlc);
  const oh = { o: ohlc.querySelector('.o'), h: ohlc.querySelector('.h'), l: ohlc.querySelector('.l'), c: ohlc.querySelector('.c') };
  const posTag = el(`<div class="ap-postag"><div class="ap-etag">Entry</div><div class="ap-pnl"><span class="ap-pnl-ic"></span><span class="ap-pnl-v">+0.0%</span></div></div>`);
  plot.appendChild(posTag);
  const pnlChip = posTag.querySelector('.ap-pnl');
  const pnlIc = posTag.querySelector('.ap-pnl-ic');
  const pnlV = posTag.querySelector('.ap-pnl-v');

  const tlist = chart.querySelector('.ap-tlist');
  const tapeRows = Array.from({ length: 6 }, () => {
    const r = el(`<div class="ap-trow ap-tgrid"><div class="ap-side"></div><div class="ap-r ap-ttot"></div><div class="ap-r ap-tamt"></div><div class="ap-r ap-tpx"></div><div class="ap-r ap-tmk"></div><div class="ap-r ap-tage"></div></div>`);
    tlist.appendChild(r);
    return { el: r, side: r.querySelector('.ap-side'), tot: r.querySelector('.ap-ttot'), amt: r.querySelector('.ap-tamt'), px: r.querySelector('.ap-tpx'), mk: r.querySelector('.ap-tmk'), age: r.querySelector('.ap-tage') };
  });

  /* ---------- trade panel ---------- */
  const trade = el(`<div class="ap-panel ap-trade" style="left:${TRADE.x}px;top:${TRADE.y}px;width:${TRADE.w}px;height:${TRADE.h}px">
      <div class="ap-trhead"><div class="ap-h">Trade</div><div class="ap-tokpill">${avatar('GLINT', 20)}<b>$GLINT</b>${I.chev(12)}</div></div>
      <div class="ap-seg"><div class="ap-seg-i ap-on">Buy</div><div class="ap-seg-i">Sell</div></div>
      <div class="ap-flbl"><span>Amount</span><span>Balance <b class="ap-bal-t">24.80 SOL</b></span></div>
      <div class="ap-amount"><span class="ap-amt-v">1.00</span><span class="ap-caret"></span><div class="ap-amt-u">${solCoin(20)}<b>SOL</b></div></div>
      <div class="ap-presets">${PRESETS.map((p) => `<div class="ap-pre">${p}<span>SOL</span></div>`).join('')}</div>
      <div class="ap-opts">
        <div class="ap-opt"><span>Slippage</span><b>15%</b></div>
        <div class="ap-opt"><span>Priority fee</span><b><em class="ap-turbo">${I.bolt(11)}Turbo</em><span class="ap-mut">0.005 SOL</span></b></div>
        <div class="ap-opt"><span>MEV protection</span><b><span class="ap-mut">On</span><span class="ap-tog"><i></i></span></b></div>
        <div class="ap-opt"><span>Auto-sell</span><b><span class="ap-upc">TP +50%</span><span class="ap-mut">·</span><span class="ap-dnc">SL −20%</span></b></div>
        <div class="ap-opt ap-est"><span>Est. receive</span><b class="ap-est-v">18.2M GLINT</b></div>
      </div>
      <div class="ap-buy">
        <div class="ap-buy-grad"></div><div class="ap-buy-ok"></div><div class="ap-buy-shade"></div>
        <div class="ap-buy-c ap-buy-idle">${I.bolt(18)}<span>Snipe $GLINT</span></div>
        <div class="ap-buy-c ap-buy-pend">${I.spin(18)}<span>Executing</span></div>
        <div class="ap-buy-c ap-buy-done">${I.check(18, 2.2)}<span>Filled</span></div>
      </div>
    </div>`);
  root.appendChild(trade);
  const amtV = trade.querySelector('.ap-amt-v');
  const estV = trade.querySelector('.ap-est-v');
  const pres = [...trade.querySelectorAll('.ap-pre')];
  const buy = trade.querySelector('.ap-buy');
  const buyEls = {
    shade: buy.querySelector('.ap-buy-shade'), ok: buy.querySelector('.ap-buy-ok'), grad: buy.querySelector('.ap-buy-grad'),
    idle: buy.querySelector('.ap-buy-idle'), pend: buy.querySelector('.ap-buy-pend'), done: buy.querySelector('.ap-buy-done'),
    spin: buy.querySelector('.ap-spin'),
  };

  /* ---------- positions ---------- */
  const pos = el(`<div class="ap-panel ap-pos" style="left:${POS.x}px;top:${POS.y}px;width:${POS.w}px;height:${POS.h}px">
      <div class="ap-phead"><div class="ap-h">Positions</div><span class="ap-cnt ap-pos-cnt">4</span><div class="ap-ptot"><span>Total PnL</span><b class="ap-ptot-v"></b></div></div>
      <div class="ap-pgrid ap-pcols"><div>Token</div><div class="ap-r">Entry</div><div class="ap-r">Value</div><div class="ap-r">PnL</div></div>
      <div class="ap-plist"></div>
    </div>`);
  root.appendChild(pos);
  const ptot = pos.querySelector('.ap-ptot-v');
  const plist = pos.querySelector('.ap-plist');
  const prow = {};
  for (const p of POSITIONS) {
    const r = el(`<div class="ap-prow">
        <div class="ap-prow-bg"></div>
        <div class="ap-pgrid ap-prow-in">
          <div class="ap-tk">${avatar(p.tk, 32)}<div class="ap-tk-t"><div class="ap-tk-s">$${p.tk}</div><div class="ap-psub"><span class="ap-psz">${p.size.toFixed(2)} SOL</span><span class="ap-tp">${I.check(11, 2.2)}TP hit · sold</span></div></div></div>
          <div class="ap-r ap-n ap-pentry">${pxHTML(p.entry)}</div>
          <div class="ap-r ap-n ap-pval"></div>
          <div class="ap-end"><div class="ap-pchip"><span class="ap-pchip-ic"></span><span class="ap-pchip-v"></span></div></div>
        </div>
      </div>`);
    plist.appendChild(r);
    prow[p.tk] = {
      el: r, bg: r.querySelector('.ap-prow-bg'), val: r.querySelector('.ap-pval'), chip: r.querySelector('.ap-pchip'),
      ic: r.querySelector('.ap-pchip-ic'), v: r.querySelector('.ap-pchip-v'), psz: r.querySelector('.ap-psz'), tp: r.querySelector('.ap-tp'),
    };
  }

  /* ---------- toast ---------- */
  const toast = el(`<div class="ap-toast" style="right:${TOAST.right}px;top:${TOAST.top}px;width:${TOAST.w}px">
      <div class="ap-toast-ic">${I.check(20, 2.4)}</div>
      <div class="ap-toast-tx"><div class="ap-toast-t"></div><div class="ap-toast-s">${I.arrowR(13)}<span></span></div></div>
      <div class="ap-toast-r"><span>now</span>${I.x(12)}</div>
    </div>`);
  root.appendChild(toast);
  const toastT = toast.querySelector('.ap-toast-t');
  const toastS = toast.querySelector('.ap-toast-s span');

  const balV = top.querySelector('.ap-bal-v'), balT = trade.querySelector('.ap-bal-t');
  const tabCnt = top.querySelector('.ap-tab-cnt'), posCnt = pos.querySelector('.ap-pos-cnt');

  /* ------------------------------------------------------------------ state → view */
  let feedModel = [];   // [{tk, y, h, f}] in panel coordinates (current state)
  let feedScroll = 0;
  const chartGeo = { yEntry: 0, bx: 0, by: 0, tagR: 0, tagB: 0 };

  const DEF = {
    feed: { inserted: 0, highlight: null, highlightAmt: 0, snipeHover: 0, snipePress: 0, snipeState: 'idle', scroll: 0 },
    // pnl: null shows the PnL the chart actually draws (current price vs entry)
    chart: { reveal: 1, entry: 0, pnl: null, pnlFlash: 0, price: null },
    trade: { preset: 2, presetHover: -1, buyHover: 0, buyPress: 0, buyState: 'idle' },
    positions: { pnl: { GLINT: 38.2, MOCHI: 12.6, ZORP: -4.1, FROGO: 61.3 }, flash: {}, tp: 0 },
    toast: { show: 0, text: 'Buy filled · 1.00 SOL', sub: '18.2M GLINT · simulated' },
  };

  function updateFeed(s, t) {
    // live dot pulse (1.2 s period)
    const ph = (((t / 1.2) % 1) + 1) % 1;
    css(liveRing, 'transform', `scale(${lerp(1, 2.6, ease.outCubic(ph)).toFixed(3)})`);
    css(liveRing, 'opacity', (0.42 * (1 - ph)).toFixed(3));

    const ins = Math.max(0, s.inserted || 0);
    const n = Math.min(Math.floor(ins), INCOMING.length);
    const f = n >= INCOMING.length ? 0 : ins - n;
    const order = [];
    if (f > 0.0005) order.push({ tk: INCOMING[n], f });
    for (let k = n - 1; k >= 0; k--) order.push({ tk: INCOMING[k], f: 1 });
    for (const tk of OLDER) order.push({ tk, f: 1 });
    let y = LIST_TOP - (s.scroll || 0);
    for (const r of order) {
      r.h = r.f >= 1 ? ROW_H : ROW_H * ease.inOutSine(r.f);
      r.y = y;
      y += r.h;
    }
    feedModel = order;
    feedScroll = s.scroll || 0;

    const shown = new Set();
    for (const r of order) {
      const R = rows[r.tk];
      const vis = r.y + r.h > LIST_TOP - 1 && r.y < FEED.h;
      if (!vis) continue;
      shown.add(r.tk);
      css(R.el, 'display', 'block');
      css(R.el, 'transform', `translateY(${(r.y - LIST_TOP).toFixed(2)}px)`);
      css(R.el, 'height', `${r.h.toFixed(2)}px`);
      // insertion: content slides down from behind the row above, with a lavender flash
      const fi = r.f;
      css(R.inner, 'opacity', fi >= 1 ? '1' : ease.outCubic(clamp(fi * 1.6)).toFixed(3));
      // age = age at detection + the app clock + a small bump per row that streamed in above
      const k = INCOMING.indexOf(r.tk);
      const above = k >= 0 ? Math.max(0, ins - (k + 1)) : ins;
      text(R.age, age(TOK[r.tk].age + Math.max(0, t) + above * AGE_BUMP));

      const isHi = s.highlight === r.tk;
      const hA = isHi ? clamp(s.highlightAmt) : 0;
      const flash = fi >= 1 ? 0 : Math.pow(1 - fi, 0.7) * clamp(fi * 5);
      const tint = Math.max(hA * 0.065, flash * 0.12);
      css(R.bg, 'opacity', tint > 0.001 ? '1' : '0');
      css(R.bg, 'background', `rgba(104, 88, 228, ${tint.toFixed(4)})`);
      css(R.acc, 'transform', `scaleY(${hA.toFixed(3)})`);
      css(R.acc, 'opacity', hA > 0.001 ? '1' : '0');

      // snipe button
      const st = isHi ? s.snipeState : 'idle';
      const hov = isHi ? clamp(s.snipeHover) : 0;
      const prs = isHi ? clamp(s.snipePress) : 0;
      const grad = st === 'done' ? 0 : hA;
      css(R.snGrad, 'opacity', grad.toFixed(3));
      css(R.snSoft, 'opacity', st === 'done' ? '0' : '1');
      css(R.snOk, 'opacity', st === 'done' ? '1' : '0');
      const shade = st === 'done' ? 0 : hov * 0.1 - prs * 0.16;
      css(R.snShade, 'background', shade >= 0 ? `rgba(255,255,255,${shade.toFixed(3)})` : `rgba(20,16,60,${(-shade).toFixed(3)})`);
      css(R.snipe, 'transform', `translateY(${(-1 * hov * (1 - prs)).toFixed(2)}px) scale(${(1 - 0.06 * prs).toFixed(4)})`);
      css(R.snipe, 'box-shadow', st === 'done' ? 'none' : `0 ${(1 + 3 * hov).toFixed(1)}px ${(2 + 8 * hov).toFixed(1)}px rgba(72, 64, 170, ${(grad * (0.22 + 0.12 * hov)).toFixed(3)})`);
      css(R.snipe, 'color', st === 'done' ? '#0C8454' : mix('#5A4FC4', '#FFFFFF', grad));
      css(R.snIdle, 'display', st === 'idle' ? 'flex' : 'none');
      css(R.snPend, 'display', st === 'pending' ? 'flex' : 'none');
      css(R.snDone, 'display', st === 'done' ? 'flex' : 'none');
      if (st === 'pending') css(R.spin, 'transform', `rotate(${((t * 600) % 360).toFixed(1)}deg)`);
    }
    for (const tk in rows) if (!shown.has(tk)) css(rows[tk].el, 'display', 'none');
  }

  function candlesAt(reveal, t) {
    const r = clamp(reveal) * N;
    const n = Math.min(Math.floor(r), N);
    const f = r - n;
    const out = CANDLES.slice(0, n).map((c) => ({ ...c }));
    let amp = n < N ? 0 : 1;
    if (n < N && f > 0.0005) {
      const c = CANDLES[n];
      const p = ease.inOutSine(f);
      const close = lerp(c.o, c.c, p);
      const hi = Math.max(c.o, close, lerp(c.o, c.h, clamp(f * 1.35)));
      const lo = Math.min(c.o, close, lerp(c.o, c.l, clamp(f * 1.35)));
      out.push({ o: c.o, c: close, h: hi, l: lo, v: c.v * f });
      amp = n === N - 1 ? clamp(f * 3) : Math.sin(Math.PI * f);
    }
    // the live candle breathes a little (deterministic noise of the app clock)
    const last = out[out.length - 1];
    if (last && amp > 0) {
      const w = (noise1(t * 2.3, 11) * 0.0055 + noise1(t * 6.1, 5) * 0.0018) * amp;
      last.c *= 1 + w;
      last.h = Math.max(last.h, last.c);
      last.l = Math.min(last.l, last.c);
    }
    return out;
  }

  const hms = (sec) => [Math.floor(sec / 3600), Math.floor((sec % 3600) / 60), sec % 60].map((v, i) => (i ? String(v).padStart(2, '0') : String(v))).join(':');

  function updateChart(s, t) {
    const rv = clamp(s.reveal) * N;
    const cs = candlesAt(s.reveal, t);
    const empty = cs.length === 0;
    // reveal 0: nothing traded yet; the scale sits around the launch price
    const last = empty ? { o: LAUNCH_OPEN, c: LAUNCH_OPEN, h: LAUNCH_OPEN, l: LAUNCH_OPEN, v: 0 } : cs[cs.length - 1];
    // the entry marker exists once the snipe has filled (late in candle ENTRY_IDX)
    const eVis = clamp(s.entry) * clamp((rv - ENTRY_AT) / 0.18);
    // autoscale (continuous in reveal)
    let lo = Infinity, hi = -Infinity;
    for (const c of cs) { lo = Math.min(lo, c.l); hi = Math.max(hi, c.h); }
    if (empty) { lo = LAUNCH_OPEN * 0.96; hi = LAUNCH_OPEN * 1.04; }
    if (eVis > 0) { lo = Math.min(lo, 1); hi = Math.max(hi, 1); }
    const span = hi - lo;
    hi += span * 0.08;
    lo -= span * 0.06;
    const Y = (v) => PY0 + ((hi - v) / (hi - lo)) * (PY1 - PY0);
    const cx = (i) => X0 + i * SLOT + SLOT / 2;
    const yCur = Y(last.c);
    const yEnt = Y(1);

    // axis tags: current price (green/red) and entry (violet), never overlapping
    const upNow = last.c >= last.o;
    let yTagC = yCur, yTagE = yEnt;
    if (eVis > 0 && Math.abs(yTagC - yTagE) < 22) yTagE = yTagC + (yTagE >= yTagC ? 22 : -22);
    const eTagA = ease.outCubic(clamp(eVis * 2 - 0.6));

    // grid + axis labels (one shared precision so the column reads cleanly)
    const rough = (usd(hi) - usd(lo)) / 6;
    const mag = Math.pow(10, Math.floor(Math.log10(rough)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((v) => v >= rough);
    const first = Math.ceil(usd(lo) / step) * step;
    let need = 2;
    for (let i = 0; i < hGrid.length; i++) {
      const p = pxParts(first + i * step, 6);
      if (p.sub) need = Math.max(need, p.d.replace(/0+$/, '').length);
    }
    for (let i = 0; i < hGrid.length; i++) {
      const v = first + i * step;
      const yy = Y(v / ENTRY_USD);
      const on = yy >= PY0 - 30 && yy <= PY1 + 4;
      const yr = Math.round(yy) + 0.5;
      attr(hGrid[i], 'y1', yr); attr(hGrid[i], 'y2', yr);
      attr(hGrid[i], 'opacity', on ? 1 : 0);
      const clash = (!empty && Math.abs(yy - yTagC) < TAG_CLEAR) || (eTagA > 0.3 && Math.abs(yy - yTagE) < TAG_CLEAR);
      attr(axLabels[i], 'y', yy + 3.8);
      attr(axLabels[i], 'opacity', on && !clash ? 1 : 0);
      pxSVG(axLabels[i], v, need);
    }
    for (let i = 0; i < vGrid.length; i++) {
      const idx = i * 8;
      const x = Math.round(cx(idx)) + 0.5;
      attr(vGrid[i], 'x1', x); attr(vGrid[i], 'x2', x);
      attr(tLabels[i], 'x', x);
      text(tLabels[i], hms(T0_SEC + idx));
    }

    // candles + volume
    for (let i = 0; i < N; i++) {
      const c = cs[i];
      if (!c) {
        attr(bodies[i], 'opacity', 0); attr(wicks[i], 'opacity', 0); attr(vols[i], 'opacity', 0);
        continue;
      }
      const up = c.c >= c.o;
      const cls = up ? 'ap-c-up' : 'ap-c-dn';
      const x = cx(i) - BODY / 2;
      const yt = Y(Math.max(c.o, c.c)), yb = Y(Math.min(c.o, c.c));
      attr(bodies[i], 'x', x); attr(bodies[i], 'y', yt); attr(bodies[i], 'height', Math.max(1.2, yb - yt));
      attr(bodies[i], 'class', cls); attr(bodies[i], 'opacity', 1);
      attr(wicks[i], 'x', cx(i) - 0.625); attr(wicks[i], 'y', Y(c.h)); attr(wicks[i], 'height', Math.max(1, Y(c.l) - Y(c.h)));
      attr(wicks[i], 'class', cls); attr(wicks[i], 'opacity', 1);
      const vh = Math.max(1.5, (c.v / VMAX) * (VY1 - VY0));
      attr(vols[i], 'x', x); attr(vols[i], 'y', VY1 - vh); attr(vols[i], 'height', vh);
      attr(vols[i], 'class', up ? 'ap-v-up' : 'ap-v-dn'); attr(vols[i], 'opacity', 1);
    }

    // current price line + tag
    attr(curLine, 'y1', yCur); attr(curLine, 'y2', yCur);
    attr(curLine, 'x1', empty ? 0 : cx(cs.length - 1) + BODY / 2 + 2);
    attr(curLine, 'class', `ap-curline ${upNow ? 'ap-s-up' : 'ap-s-dn'}`);
    attr(curLine, 'opacity', empty ? 0 : 1);
    attr(gCTag, 'opacity', empty ? 0 : 1);
    attr(cTagR, 'y', yTagC - 10); attr(cTagR, 'class', upNow ? 'ap-tag-up' : 'ap-tag-dn');
    attr(cTagT, 'y', yTagC + 3.8); pxSVG(cTagT, usd(last.c));

    // entry marker: full-width dashed position line drawn out from the entry candle,
    // B badge under the entry candle, violet axis tag
    const ex = cx(ENTRY_IDX);
    const eLine = ease.outCubic(eVis);
    attr(entryLine, 'y1', yEnt); attr(entryLine, 'y2', yEnt);
    attr(eClipRect, 'x', ex * (1 - eLine)); attr(eClipRect, 'width', CW * eLine);
    attr(gEntry, 'opacity', eVis > 0 ? 1 : 0);
    attr(gETag, 'opacity', eTagA);
    attr(eTagR, 'y', yTagE - 10); attr(eTagT, 'y', yTagE + 3.8); pxSVG(eTagT, ENTRY_USD);
    const ec = cs[ENTRY_IDX];
    const by = ec ? Y(ec.l) + 22 : yEnt + 22;
    const bs = ease.outBack(clamp(eVis * 1.4), 2.2);
    attr(gB, 'transform', `translate(${ex.toFixed(2)} ${by.toFixed(2)}) scale(${Math.max(0.001, bs).toFixed(3)})`);
    attr(gB, 'opacity', clamp(eVis * 3));
    chartGeo.bx = ex; chartGeo.by = by;

    // position tag ("Entry" + PnL chip): on the entry line, just left of the entry candle,
    // where the pre-entry candles sit below the line and leave the space clear
    const pnl = s.pnl != null ? s.pnl : (last.c - 1) * 100;
    const tagA = ease.outCubic(clamp((eVis - 0.35) / 0.65));
    const tagR = ex - 16, tagB = yEnt - 7;
    css(posTag, 'opacity', tagA.toFixed(3));
    css(posTag, 'transform', `translate(${tagR.toFixed(2)}px, ${tagB.toFixed(2)}px) translate(-100%, -100%) translateY(${((1 - tagA) * 6).toFixed(2)}px)`);
    chartGeo.yEntry = yEnt; chartGeo.tagR = tagR; chartGeo.tagB = tagB;
    text(pnlV, pct(pnl));
    const neg = pnl < 0;
    pnlChip.classList.toggle('ap-neg', neg);
    if (pnlIc.__neg !== neg) { pnlIc.__neg = neg; pnlIc.innerHTML = neg ? I.down(10) : I.up(10); }
    css(pnlChip, '--fl', clamp(s.pnlFlash).toFixed(3));

    // OHLC legend
    setPx(oh.o, usd(last.o), false); setPx(oh.h, usd(last.h), false); setPx(oh.l, usd(last.l), false); setPx(oh.c, usd(last.c), false);
    ohlc.classList.toggle('ap-dn', !upNow);

    // header price (one cache key for both the override and the live price)
    const pxUsd = usd(last.c);
    const pk = s.price != null ? `o:${s.price}` : `p:${pxHTML(pxUsd)}`;
    if (bigP.__k !== pk) {
      bigP.__k = pk;
      if (s.price != null) bigP.textContent = String(s.price);
      else bigP.innerHTML = pxHTML(pxUsd);
    }
    // 5m change: the pair is younger than 5 minutes, so it is measured from the launch price
    const ch = (last.c / LAUNCH_OPEN - 1) * 100;
    text(chgV, pct(ch));
    chg.classList.toggle('ap-neg', ch < 0);
    if (chgIc.__neg !== ch < 0) { chgIc.__neg = ch < 0; chgIc.innerHTML = ch < 0 ? I.down(10) : I.up(10); }
    text(stMc, kfmt(pxUsd * SUPPLY));
    text(stLiq, `${(TOK.GLINT.liq * Math.sqrt(last.c)).toFixed(1)} SOL`);
    text(stHold, Math.round(lerp(34, 288, Math.pow(clamp(rv / N), 2.4))).toLocaleString('en-US'));
    let vol = 0;
    for (const c of cs) vol += c.v;
    text(stVol, kfmt(vol * 1450));
    return last.c;
  }

  const B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  function updateTape(t, price) {
    const kNow = Math.floor(t / TAPE_DT);
    const ph = t / TAPE_DT - kNow;
    const slide = 1 - ease.outCubic(clamp(ph / 0.2));
    for (let j = 0; j < tapeRows.length; j++) {
      const k = kNow - j;
      const R = rng(9001 + ((k * 2654435761) >>> 0));
      R(); R();
      const isBuy = R() < 0.7;
      const sol = Math.pow(10, lerp(-1.15, 0.5, R()));
      const px = price * (1 + (R() - 0.5) * 0.006);
      const toks = (sol * TOK_PER_SOL) / px;
      let a = '', b = '';
      for (let q = 0; q < 4; q++) a += B58[Math.floor(R() * B58.length)];
      for (let q = 0; q < 4; q++) b += B58[Math.floor(R() * B58.length)];
      const T = tapeRows[j];
      text(T.side, isBuy ? 'Buy' : 'Sell');
      if (T.side.__buy !== isBuy) { T.side.__buy = isBuy; T.side.className = `ap-side ${isBuy ? 'ap-upc' : 'ap-dnc'}`; }
      text(T.tot, `${sol.toFixed(sol < 1 ? 3 : 2)} SOL`);
      text(T.amt, mfmt(toks));
      setPx(T.px, usd(px));
      text(T.mk, `${a}…${b}`);
      text(T.age, age(Math.max(0, t - k * TAPE_DT) + 0.4));
      css(T.el, 'transform', `translateY(${((j - slide) * 32).toFixed(2)}px)`);
      css(T.el, 'opacity', j === 0 ? Math.pow(1 - slide, 1.6).toFixed(3) : j >= 5 ? (1 - clamp(j - slide - 4)).toFixed(3) : '1');
      css(T.el, 'background', j === 0 && slide > 0 ? `rgba(${isBuy ? '18,161,107' : '229,72,77'},${(0.07 * slide).toFixed(3)})` : 'transparent');
    }
    const ratio = Math.round(lerp(58, 74, 0.5 + 0.5 * noise1(t * 0.4, 3)));
    text(ratioL, `${ratio}% buys`);
    css(ratioB, 'width', `${ratio}%`);
  }

  function updateTrade(s, t, price) {
    const pi = clamp(Math.round(s.preset ?? 2), 0, 3);
    const amt = PRESETS[pi];
    text(amtV, amt.toFixed(2));
    // live quote at the current price (TOK_PER_SOL is the rate at the entry price)
    text(estV, `${mfmt((amt * TOK_PER_SOL) / price)} GLINT`);
    pres.forEach((p, i) => {
      p.classList.toggle('ap-on', i === pi);
      p.classList.toggle('ap-hov', i === s.presetHover && i !== pi);
    });
    const st = s.buyState || 'idle';
    const hov = clamp(s.buyHover), prs = clamp(s.buyPress);
    css(buyEls.ok, 'opacity', st === 'filled' ? '1' : '0');
    css(buyEls.grad, 'opacity', st === 'filled' ? '0' : '1');
    const shade = hov * 0.09 - prs * 0.14;
    css(buyEls.shade, 'background', shade >= 0 ? `rgba(255,255,255,${shade.toFixed(3)})` : `rgba(20,16,60,${(-shade).toFixed(3)})`);
    css(buy, 'transform', `translateY(${(-1.5 * hov * (1 - prs)).toFixed(2)}px) scale(${(1 - 0.025 * prs).toFixed(4)})`);
    const sh = st === 'filled' ? 'rgba(18,161,107,' : 'rgba(84,80,190,';
    css(buy, 'box-shadow', `0 ${(2 + 6 * hov).toFixed(1)}px ${(6 + 14 * hov).toFixed(1)}px ${sh}${(0.2 + 0.1 * hov - 0.08 * prs).toFixed(3)}), 0 1px 2px ${sh}0.2)`);
    css(buyEls.idle, 'display', st === 'idle' ? 'flex' : 'none');
    css(buyEls.pend, 'display', st === 'pending' ? 'flex' : 'none');
    css(buyEls.done, 'display', st === 'filled' ? 'flex' : 'none');
    if (st === 'pending') css(buyEls.spin, 'transform', `rotate(${((t * 600) % 360).toFixed(1)}deg)`);
    return amt;
  }

  /** The two simulated buys in the state (feed snipe, trade panel) move the wallet and GLINT size. */
  function updateWallet(S, amt) {
    const sniped = S.feed.snipeState === 'done';
    const filled = S.trade.buyState === 'filled';
    const bal = BALANCE - (sniped ? SNIPE_SOL + FEE : 0) - (filled ? amt + FEE : 0);
    text(balV, bal.toFixed(2));
    text(balT, `${bal.toFixed(2)} SOL`);
    return (sniped ? SNIPE_SOL : 0) + (filled ? amt : 0);
  }

  function updatePositions(s, glintSize) {
    let tot = 0, count = 0;
    for (const p of POSITIONS) {
      const size = p.tk === 'GLINT' ? glintSize : p.size;
      const R = prow[p.tk];
      css(R.el, 'display', size > 0 ? 'block' : 'none');
      if (!(size > 0)) continue;
      count++;
      const v = s.pnl[p.tk] ?? 0;
      tot += (size * v) / 100;
      text(R.v, pct(v));
      text(R.psz, `${size.toFixed(2)} SOL`);
      text(R.val, `${(size * (1 + v / 100)).toFixed(2)} SOL`);
      const neg = v < 0;
      R.chip.classList.toggle('ap-neg', neg);
      const isTp = p.tk === 'FROGO' ? clamp(s.tp) : 0;
      const icon = isTp > 0.5 ? 'check' : neg ? 'down' : 'up';
      if (R.ic.__k !== icon) { R.ic.__k = icon; R.ic.innerHTML = icon === 'check' ? I.check(11, 2.4) : icon === 'down' ? I.down(10) : I.up(10); }
      const fl = clamp((s.flash && s.flash[p.tk]) || 0);
      css(R.chip, '--fl', fl.toFixed(3));
      css(R.bg, 'background', neg ? `rgba(229,72,77,${(0.07 * fl).toFixed(3)})` : `rgba(18,161,107,${(0.07 * fl + 0.035 * isTp).toFixed(3)})`);
      // the size line rolls up and the "TP hit · sold" badge rolls in (clipped, no overlap)
      css(R.psz, 'opacity', (1 - isTp).toFixed(3));
      css(R.psz, 'transform', `translateY(${(-19 * isTp).toFixed(2)}px)`);
      css(R.tp, 'opacity', isTp > 0 ? '1' : '0');
      css(R.tp, 'transform', `translateY(${(19 * (1 - isTp)).toFixed(2)}px)`);
      R.el.classList.toggle('ap-sold', isTp > 0.5);
    }
    text(ptot, `${tot >= 0 ? '+' : '−'}${Math.abs(tot).toFixed(2)} SOL`);
    ptot.classList.toggle('ap-neg', tot < 0);
    text(posCnt, count);
    text(tabCnt, count);
  }

  function updateToast(s) {
    const p = clamp(s.show);
    css(toast, 'display', p > 0.001 ? 'flex' : 'none');
    text(toastT, s.text ?? DEF.toast.text);
    text(toastS, s.sub ?? DEF.toast.sub);
    const e = ease.outCubic(p);
    css(toast, 'opacity', clamp(p * 1.8).toFixed(3));
    css(toast, 'transform', `translate(${((1 - e) * 28).toFixed(2)}px, ${((1 - e) * -6).toFixed(2)}px) scale(${lerp(0.97, 1, e).toFixed(4)})`);
  }

  function update(state = {}) {
    const t = state.t || 0;
    const S = {
      feed: { ...DEF.feed, ...(state.feed || {}) },
      chart: { ...DEF.chart, ...(state.chart || {}) },
      trade: { ...DEF.trade, ...(state.trade || {}) },
      positions: { ...DEF.positions, ...(state.positions || {}) },
      toast: { ...DEF.toast, ...(state.toast || {}) },
    };
    S.positions.pnl = { ...DEF.positions.pnl, ...((state.positions && state.positions.pnl) || {}) };
    updateFeed(S.feed, t);
    const price = updateChart(S.chart, t);
    updateTape(t, price);
    const amt = updateTrade(S.trade, t, price);
    updatePositions(S.positions, updateWallet(S, amt));
    updateToast(S.toast);
  }

  /* ------------------------------------------------------------------ rects (app coordinates) */
  const R4 = (x, y, w, hh) => ({ x, y, w, h: hh, cx: x + w / 2, cy: y + hh / 2 });
  /** Rect of a node in app space via the offset chain (ignores transforms). */
  function off(node) {
    let x = 0, y = 0, n = node;
    while (n && n !== root) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; }
    return R4(x, y, node.offsetWidth, node.offsetHeight);
  }
  /** Measure with `node` temporarily displayed (rect of a hidden row or toast). */
  function measureShown(node, show, fn) {
    const hidden = node.style.display === 'none';
    if (hidden) node.style.display = show;
    const r = fn();
    if (hidden) node.style.display = 'none';
    return r;
  }
  function feedRowRect(tk) {
    const m = feedModel.find((r) => r.tk === tk);
    // not inserted yet: a zero-height row at the top of the list, where it will grow in
    if (!m) return { m: null, r: R4(FEED.x, FEED.y + LIST_TOP - feedScroll, FEED.w, 0) };
    return { m, r: R4(FEED.x, FEED.y + m.y, FEED.w, m.h) };
  }
  function feedChild(tk, node) {
    const { m } = feedRowRect(tk);
    const R = rows[tk];
    // offset inside the 88px content block (.ap-frow-in), independent of the row's current height
    const o = measureShown(R.el, 'block', () => {
      let x = 0, y = 0, n = node;
      while (n && n !== R.inner) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; }
      return { x: x + R.inner.offsetLeft, y, w: node.offsetWidth, h: node.offsetHeight };
    });
    // the content block is bottom-anchored in the row (it slides down while the row grows);
    // a row not inserted yet reports where the child lands at the top of the list
    const top = m ? FEED.y + m.y + m.h - ROW_H : FEED.y + LIST_TOP - feedScroll;
    return R4(FEED.x + o.x, top + o.y, o.w, o.h);
  }

  function rect(name) {
    const parts = String(name).split('.');
    switch (parts[0]) {
      case 'topbar': return R4(0, 0, 1920, 72);
      case 'demo': return off(top.querySelector('.ap-demo'));
      case 'logo': return off(logo);
      case 'feed': {
        if (parts.length === 1) return R4(FEED.x, FEED.y, FEED.w, FEED.h);
        if (parts[1] === 'header' && parts.length === 2) return R4(FEED.x, FEED.y, FEED.w, LIST_TOP);
        const tk = parts[2];
        if (!rows[tk]) return null;
        if (parts[1] === 'row') return feedRowRect(tk).r;
        if (parts[1] === 'snipe') return feedChild(tk, rows[tk].snipe);
        if (parts[1] === 'ai') return feedChild(tk, rows[tk].ai);
        return null;
      }
      case 'chart': {
        if (parts.length === 1) return R4(CHART.x, CHART.y, CHART.w, CHART.h);
        const px = CHART.x + PLOT.x, py = CHART.y + PLOT.y;
        if (parts[1] === 'plot') return R4(px, py, PLOT.w, PLOT.h);
        if (parts[1] === 'price') return off(bigP);
        if (parts[1] === 'entry') return R4(px + chartGeo.bx - 10, py + chartGeo.by - 10, 20, 20);
        if (parts[1] === 'pnl') {
          const w = pnlChip.offsetWidth, hh = pnlChip.offsetHeight;
          return R4(px + chartGeo.tagR - w, py + chartGeo.tagB - hh, w, hh);
        }
        return null;
      }
      case 'trade': {
        if (parts.length === 1) return R4(TRADE.x, TRADE.y, TRADE.w, TRADE.h);
        if (parts[1] === 'preset') { const n = /^\d$/.test(parts[2] || '') ? pres[+parts[2]] : null; return n ? off(n) : null; }
        if (parts[1] === 'amount') return off(trade.querySelector('.ap-amount'));
        if (parts[1] === 'buy') return off(buy);
        return null;
      }
      case 'positions': {
        if (parts.length === 1) return R4(POS.x, POS.y, POS.w, POS.h);
        const R = prow[parts[2]];
        if (!R) return null;
        // a position not opened yet reports the slot it will take
        if (parts[1] === 'row') return measureShown(R.el, 'block', () => off(R.el));
        if (parts[1] === 'pnl') return measureShown(R.el, 'block', () => off(R.chip));
        return null;
      }
      case 'toast': return measureShown(toast, 'flex', () => off(toast)); // resting position, also while hidden
      default: return null;
    }
  }

  update({});
  return { el: root, rect, update };
}
