// Tiny deterministic animation toolkit. Everything is a pure function of time,
// so any frame can be rendered in any order (required for parallel rendering).

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
/** Normalised progress of t through [t0, t1], clamped to 0..1. */
export const prog = (t, t0, t1) => (t1 <= t0 ? (t >= t1 ? 1 : 0) : clamp((t - t0) / (t1 - t0)));
/** Map t from [t0, t1] to [v0, v1] with an optional easing, clamped. */
export const remap = (t, t0, t1, v0, v1, e = ease.linear) => lerp(v0, v1, e(prog(t, t0, t1)));
/** 1 inside [t0, t1), 0 outside. */
export const within = (t, t0, t1) => t >= t0 && t < t1;

export function cubicBezier(x1, y1, x2, y2) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const sx = (u) => ((ax * u + bx) * u + cx) * u;
  const sy = (u) => ((ay * u + by) * u + cy) * u;
  const dx = (u) => (3 * ax * u + 2 * bx) * u + cx;
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let u = x;
    for (let i = 0; i < 8; i++) {
      const err = sx(u) - x;
      if (Math.abs(err) < 1e-6) break;
      const d = dx(u);
      if (Math.abs(d) < 1e-6) break;
      u -= err / d;
    }
    let lo = 0, hi = 1;
    for (let i = 0; i < 30 && Math.abs(sx(u) - x) > 1e-6; i++) {
      if (sx(u) < x) lo = u; else hi = u;
      u = (lo + hi) / 2;
    }
    return sy(u);
  };
}

export const ease = {
  linear: (x) => x,
  inSine: (x) => 1 - Math.cos((x * Math.PI) / 2),
  outSine: (x) => Math.sin((x * Math.PI) / 2),
  inOutSine: (x) => -(Math.cos(Math.PI * x) - 1) / 2,
  inQuad: (x) => x * x,
  outQuad: (x) => 1 - (1 - x) * (1 - x),
  inOutQuad: (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2),
  inCubic: (x) => x * x * x,
  outCubic: (x) => 1 - Math.pow(1 - x, 3),
  inOutCubic: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  inQuart: (x) => x * x * x * x,
  outQuart: (x) => 1 - Math.pow(1 - x, 4),
  inOutQuart: (x) => (x < 0.5 ? 8 * x * x * x * x : 1 - Math.pow(-2 * x + 2, 4) / 2),
  inQuint: (x) => x * x * x * x * x,
  outQuint: (x) => 1 - Math.pow(1 - x, 5),
  inOutQuint: (x) => (x < 0.5 ? 16 * x * x * x * x * x : 1 - Math.pow(-2 * x + 2, 5) / 2),
  inExpo: (x) => (x <= 0 ? 0 : Math.pow(2, 10 * x - 10)),
  outExpo: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
  inOutExpo: (x) =>
    x <= 0 ? 0 : x >= 1 ? 1 : x < 0.5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2,
  outBack: (x, s = 1.4) => 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2),
  /** Minimum-jerk profile: how a human hand moves a mouse between two targets. */
  minJerk: (x) => x * x * x * (10 - 15 * x + 6 * x * x),
  /** After Effects style "easy ease" (speed ramp in and out). */
  easy: cubicBezier(0.33, 0, 0.67, 1),
  /** Aggressive speed ramp used for whip/push moves (slow-fast-slow). */
  ramp: cubicBezier(0.7, 0, 0.15, 1),
  /** Smooth premium deceleration (like Apple keynote reveals). */
  glide: cubicBezier(0.16, 1, 0.3, 1),
};

/**
 * Keyframe interpolation. keys: [[t, value, easeIntoThisKey?], ...] sorted by t.
 * value may be a number or an array of numbers.
 */
export function kf(t, keys, defEase = ease.easy) {
  if (t <= keys[0][0]) return keys[0][1];
  const last = keys[keys.length - 1];
  if (t >= last[0]) return last[1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, v1, e] = keys[i];
    if (t < t1) {
      const [t0, v0] = keys[i - 1];
      const p = (e || defEase)(prog(t, t0, t1));
      if (Array.isArray(v0)) return v0.map((a, j) => lerp(a, v1[j], p));
      return lerp(v0, v1, p);
    }
  }
  return last[1];
}

/** Damped spring step response (0 -> 1 with overshoot), t in seconds since start. */
export function spring(t, { freq = 2.4, damping = 0.5 } = {}) {
  if (t <= 0) return 0;
  const w = 2 * Math.PI * freq;
  const z = damping;
  if (z >= 1) return 1 - Math.exp(-w * t) * (1 + w * t);
  const wd = w * Math.sqrt(1 - z * z);
  return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + ((z * w) / wd) * Math.sin(wd * t));
}

/** Deterministic PRNG (mulberry32). */
export function rng(seed = 1) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Smooth deterministic 1D noise in [-1, 1] (value noise with cosine interpolation). */
export function noise1(x, seed = 7) {
  const h = (n) => {
    let v = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453;
    return (v - Math.floor(v)) * 2 - 1;
  };
  const i = Math.floor(x), f = x - i;
  const u = (1 - Math.cos(f * Math.PI)) / 2;
  return lerp(h(i), h(i + 1), u);
}

/** Set a style property only when it changes (keeps per-frame DOM writes cheap). */
export function css(el, prop, value) {
  if (!el) return;
  const cache = el.__css || (el.__css = {});
  if (cache[prop] === value) return;
  cache[prop] = value;
  if (prop.startsWith('--')) el.style.setProperty(prop, value);
  else el.style[prop] = value;
}

/** Set textContent only when it changes. */
export function text(el, value) {
  if (!el) return;
  const v = String(value);
  if (el.__text === v) return;
  el.__text = v;
  el.textContent = v;
}

/** Build DOM from an HTML string; returns the first element. */
export function h(html) {
  const tpl = document.createElement('template');
  tpl.innerHTML = html.trim();
  return tpl.content.firstElementChild;
}

/**
 * Rect of `el` in the coordinate space of `root` (ignores CSS transforms on
 * ancestors because it walks the offsetParent chain). Root must be positioned.
 */
export function rectIn(el, root) {
  let x = 0, y = 0, n = el;
  while (n && n !== root) {
    x += n.offsetLeft;
    y += n.offsetTop;
    n = n.offsetParent;
  }
  return { x, y, w: el.offsetWidth, h: el.offsetHeight, cx: x + el.offsetWidth / 2, cy: y + el.offsetHeight / 2 };
}

/** Format helpers for UI numbers. */
export const fmt = {
  pct: (v, d = 1) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(d)}%`,
  num: (v, d = 2) => v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }),
  sol: (v, d = 2) => `${v.toFixed(d)} SOL`,
};
