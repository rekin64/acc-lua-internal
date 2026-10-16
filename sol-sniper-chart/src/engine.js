// Deterministic market simulation for the SOL Sniper chart video.
//
// SYNTHETIC DATA: every price below is generated from a fixed seed. It is a
// visualisation of a memecoin pump, not real market data and not a result
// obtained with SOL Sniper.
//
// Each live candle owns a tick-level price path sampled at SAMPLE_HZ. The
// candle's body, wicks and volume at time t are read from that path, so the
// header price, the candles and the volume bars always agree with each other.

export const W = 1920;
export const H = 1080;
export const FPS = 60;
export const DURATION = 10; // seconds
export const SAMPLE_HZ = 240;

export const HIST_COUNT = 30; // candles already on the chart at t = 0
const HIST_SEED = 107;
export const SLOTS = 48; // fixed x slots: the camera never moves

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gauss(rng) {
  let u = 0;
  while (u === 0) u = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rng());
}

// Live candles, scripted per phase of the brief:
//   0-2 s calm, 2-4 s buyers arrive, 4-7 s breakout, 7-10 s parabolic.
// ret = close/open - 1, uw/lw = wick size relative to price, vol = x base volume.
const LIVE_SCRIPT = [
  // 0 - 2 s : calm, small green and red candles
  { dur: 2 / 3, ret: +0.014, uw: 0.006, lw: 0.008, vol: 1.0 },
  { dur: 2 / 3, ret: -0.011, uw: 0.005, lw: 0.006, vol: 0.9 },
  { dur: 2 / 3, ret: +0.022, uw: 0.007, lw: 0.005, vol: 1.2 },
  // 2 - 4 s : buyers arrive, greens get bigger, volume builds
  { dur: 2 / 3, ret: +0.055, uw: 0.012, lw: 0.006, vol: 1.7 },
  { dur: 2 / 3, ret: -0.018, uw: 0.015, lw: 0.008, vol: 1.5 },
  { dur: 2 / 3, ret: +0.085, uw: 0.016, lw: 0.007, vol: 2.3 },
  // 4 - 7 s : breakout, big turquoise candles with one red correction
  { dur: 0.6, ret: +0.18, uw: 0.025, lw: 0.01, vol: 3.0 },
  { dur: 0.6, ret: +0.25, uw: 0.03, lw: 0.015, vol: 3.6 },
  { dur: 0.6, ret: -0.05, uw: 0.02, lw: 0.02, vol: 2.6 },
  { dur: 0.6, ret: +0.28, uw: 0.03, lw: 0.01, vol: 3.8 },
  { dur: 0.6, ret: +0.20, uw: 0.04, lw: 0.02, vol: 3.4 },
  // 7 - 10 s : parabolic, a run of very large green candles
  { dur: 0.62, ret: +0.27, uw: 0.03, lw: 0.01, vol: 4.2 },
  { dur: 0.62, ret: +0.33, uw: 0.04, lw: 0.015, vol: 5.0 },
  { dur: 0.62, ret: +0.18, uw: 0.06, lw: 0.02, vol: 4.4 },
  { dur: 0.62, ret: +0.36, uw: 0.035, lw: 0.012, vol: 5.5 },
  { dur: 0.62, ret: +0.30, uw: 0.03, lw: 0.01, vol: 5.2 }, // still forming at 10 s
];

// Fritsch-Carlson monotone cubic: never overshoots its keypoints, so the path
// stays inside the candle's high/low.
function monotoneCubic(xs, ys) {
  const n = xs.length;
  const d = [];
  const m = new Array(n).fill(0);
  for (let i = 0; i < n - 1; i++) d.push((ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]));
  m[0] = d[0];
  m[n - 1] = d[n - 2];
  for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) {
      m[i] = 0;
      m[i + 1] = 0;
      continue;
    }
    const a = m[i] / d[i];
    const b = m[i + 1] / d[i];
    const s = a * a + b * b;
    if (s > 9) {
      const k = 3 / Math.sqrt(s);
      m[i] = k * a * d[i];
      m[i + 1] = k * b * d[i];
    }
  }
  return (x) => {
    let i = 0;
    while (i < n - 2 && x > xs[i + 1]) i++;
    const h = xs[i + 1] - xs[i];
    const u = (x - xs[i]) / h;
    const u2 = u * u;
    const u3 = u2 * u;
    return (
      (2 * u3 - 3 * u2 + 1) * ys[i] +
      (u3 - 2 * u2 + u) * h * m[i] +
      (-2 * u3 + 3 * u2) * ys[i + 1] +
      (u3 - u2) * h * m[i + 1]
    );
  };
}

// Tick-level path from open to close that touches the target high and low.
function makePath(o, c, hi, lo, dur, rng) {
  const n = Math.round(dur * SAMPLE_HZ) + 1;
  const range = hi - lo;
  const green = c >= o;
  const a = 0.1 + 0.2 * rng();
  const b = 0.68 + 0.22 * rng();
  const keys = green
    ? [[0, o], [a, lo], [b, hi], [1, c]]
    : [[0, o], [a, hi], [b, lo], [1, c]];

  // Intermediate wiggles between the keypoints: buyers and sellers trading.
  const pts = [keys[0]];
  for (let k = 0; k < keys.length - 1; k++) {
    const [x0, y0] = keys[k];
    const [x1, y1] = keys[k + 1];
    const m = 1 + Math.floor(rng() * 2);
    for (let j = 1; j <= m; j++) {
      const f = (j + (rng() - 0.5) * 0.5) / (m + 1);
      let y = y0 + (y1 - y0) * f + (rng() - 0.5) * 0.45 * Math.abs(y1 - y0);
      y = Math.min(hi - 0.03 * range, Math.max(lo + 0.03 * range, y));
      pts.push([x0 + (x1 - x0) * f, y]);
    }
    pts.push(keys[k + 1]);
  }
  const curve = monotoneCubic(pts.map((p) => p[0]), pts.map((p) => p[1]));

  // Micro noise (value noise at ~14 Hz), faded out at the open and the close.
  const knots = Math.ceil(dur * 14) + 2;
  const nv = Array.from({ length: knots }, () => rng() * 2 - 1);
  const noise = (u) => {
    const x = u * (knots - 1);
    const i = Math.min(knots - 2, Math.floor(x));
    const f = x - i;
    const s = (1 - Math.cos(Math.PI * f)) / 2;
    return nv[i] * (1 - s) + nv[i + 1] * s;
  };

  const p = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const u = i / (n - 1);
    const env = Math.sqrt(Math.sin(Math.PI * u));
    const v = curve(u) + noise(u) * 0.04 * range * env;
    p[i] = Math.min(hi, Math.max(lo, v));
  }
  p[0] = o;
  p[n - 1] = c;
  return p;
}

export function buildMarket(seed = 20251016, histSeed = HIST_SEED) {
  const rng = mulberry32(seed);
  const hrng = mulberry32(histSeed);
  const P0 = 0.00000671; // first open on the chart: the "initial price"

  // ---- 30 historical candles: calm, slowly rising, mixed colours --------
  const hist = [];
  const lr = [];
  for (let i = 0; i < HIST_COUNT; i++) {
    const prog = i / (HIST_COUNT - 1);
    lr.push(0.05 * prog * prog + gauss(hrng) * 0.042);
  }
  const shift = (Math.log(2.3) - lr.reduce((s, x) => s + x, 0)) / HIST_COUNT;
  let price = P0;
  for (let i = 0; i < HIST_COUNT; i++) {
    const o = price;
    const c = o * Math.exp(lr[i] + shift);
    const h = Math.max(o, c) * (1 + 0.004 + Math.abs(gauss(hrng)) * 0.01);
    const l = Math.min(o, c) * (1 - 0.004 - Math.abs(gauss(hrng)) * 0.01);
    const v = (0.55 + 0.6 * hrng()) * (1 + 6 * Math.abs(lr[i] + shift)) * (0.8 + 0.4 * (i / HIST_COUNT));
    hist.push({ o, h, l, c, v });
    price = c;
  }
  const baseVol = hist.reduce((s, k) => s + k.v, 0) / hist.length;

  // ---- live candles with their tick paths -------------------------------
  const live = [];
  let t0 = 0;
  for (const s of LIVE_SCRIPT) {
    const o = price;
    const c = o * (1 + s.ret);
    const hiT = Math.max(o, c) * (1 + s.uw * (0.8 + 0.4 * rng()));
    const loT = Math.min(o, c) * (1 - s.lw * (0.8 + 0.4 * rng()));
    const path = makePath(o, c, hiT, loT, s.dur, rng);
    const n = path.length;
    const pmax = new Float64Array(n);
    const pmin = new Float64Array(n);
    const act = new Float64Array(n); // cumulative traded activity
    for (let i = 0; i < n; i++) {
      pmax[i] = i ? Math.max(pmax[i - 1], path[i]) : path[i];
      pmin[i] = i ? Math.min(pmin[i - 1], path[i]) : path[i];
      act[i] = i ? act[i - 1] + Math.abs(path[i] - path[i - 1]) : 0;
    }
    const v = s.vol * baseVol * (0.9 + 0.2 * rng());
    live.push({ t0, t1: t0 + s.dur, o, c, path, pmax, pmin, act, v });
    t0 += s.dur;
    price = c;
  }

  // Candle (o, h, l, c, v) of a live candle at local time t, while it forms.
  function liveAt(k, t) {
    const L = live[k];
    const i = Math.max(0, Math.min(L.path.length - 1, Math.floor((t - L.t0) * SAMPLE_HZ)));
    const u = i / (L.path.length - 1);
    const a = L.act[L.act.length - 1] > 0 ? L.act[i] / L.act[L.act.length - 1] : u;
    return {
      o: L.o,
      h: L.pmax[i],
      l: L.pmin[i],
      c: L.path[i],
      v: L.v * (0.35 * u + 0.65 * a),
      live: true,
    };
  }

  function candlesAt(t) {
    const out = hist.map((k) => ({ ...k, live: false }));
    for (let k = 0; k < live.length; k++) {
      if (t < live[k].t0) break;
      if (t >= live[k].t1 && k < live.length - 1) {
        const L = live[k];
        out.push({ o: L.o, h: L.pmax[L.pmax.length - 1], l: L.pmin[L.pmin.length - 1], c: L.c, v: L.v, live: false });
      } else {
        out.push(liveAt(k, t));
        break;
      }
    }
    return out;
  }

  // ---- auto-scale timeline (precomputed, so any frame renders identically)
  // Real terminals rescale as new highs print; this eases the rescale a little
  // while never letting a wick leave the plot.
  const steps = Math.ceil(DURATION * SAMPLE_HZ) + 1;
  const yTop = new Float64Array(steps);
  const yBot = new Float64Array(steps);
  const vTop = new Float64Array(steps);
  let sTop = 0;
  let sVol = 0;
  const dt = 1 / SAMPLE_HZ;
  for (let j = 0; j < steps; j++) {
    const cs = candlesAt(j * dt);
    let hi = -Infinity;
    let lo = Infinity;
    let vmax = 0;
    for (const k of cs) {
      hi = Math.max(hi, k.h);
      lo = Math.min(lo, k.l);
      vmax = Math.max(vmax, k.v);
    }
    const range = hi - lo;
    const targetTop = hi + 0.07 * range;
    const targetVol = vmax * 1.12;
    if (j === 0) {
      sTop = targetTop;
      sVol = targetVol;
    } else {
      sTop += (targetTop - sTop) * (1 - Math.exp(-dt / 0.18));
      sVol += (targetVol - sVol) * (1 - Math.exp(-dt / 0.25));
    }
    yTop[j] = Math.max(sTop, hi + 0.012 * range);
    yBot[j] = lo - 0.035 * range;
    vTop[j] = Math.max(sVol, vmax * 1.02);
  }

  function stateAt(t) {
    const tt = Math.max(0, Math.min(DURATION, t));
    const j = Math.min(steps - 1, Math.floor(tt * SAMPLE_HZ));
    const candles = candlesAt(tt);
    // The header ticker refreshes ~10 times per second, like a live feed.
    const tq = Math.floor(tt * 10) / 10;
    const tick = candlesAt(tq);
    const last = tick[tick.length - 1].c;
    return {
      t: tt,
      candles,
      yMin: yBot[j],
      yMax: yTop[j],
      vMax: vTop[j],
      price: last,
      pct: (last / P0 - 1) * 100,
    };
  }

  return { P0, hist, live, stateAt, candlesAt };
}
