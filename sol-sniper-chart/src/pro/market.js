// Market model for the pro terminal layout: 1 s candles shown at 2x speed
// (each candle forms in 0.5 s of video), with a trade tape derived from the
// same prices.
//
// SYNTHETIC DATA: every price, volume and trade comes from fixed seeds. It is
// a visualisation of a memecoin pump, not market data and not a result
// obtained with SOL Sniper.

import { DURATION, SAMPLE_HZ, gauss, makePath, mulberry32 } from '../engine.js';

export const CANDLE_S = 0.5; // video seconds per 1 s candle
export const HIST = 100; // candles already on the chart at t = 0
export const LIVE = Math.round(DURATION / CANDLE_S); // 20 candles form during the video
export const SLOTS = 128; // fixed x slots, with a right margin like TradingView
export const SUPPLY = 1e9; // USELESS total supply
export const CLOCK0 = 14 * 3600 + 34 * 60 + 20; // chart clock of candle 0 (14:34:20)
const ENTRY_PRICE = 0.00001567; // displayed price when the simulated position opens (t = 0.5 s)
const LIQ0 = 3900; // pool liquidity (USD) at the first price; scales with sqrt(price)

// History: one entry per phase. ret = total move, vol = per-candle sigma,
// usd = typical 1 s volume, wick = wick size relative to sigma.
const HIST_SEGMENTS = [
  { n: 24, ret: 0.14, vol: 0.011, usd: 130, wick: 0.9 }, // accumulation
  { n: 15, ret: 0.46, vol: 0.021, usd: 360, wick: 1.0 }, // first leg
  { n: 17, ret: -0.07, vol: 0.017, usd: 240, wick: 1.4 }, // choppy consolidation
  { n: 14, ret: 0.33, vol: 0.02, usd: 340, wick: 1.0 }, // second leg
  { n: 9, ret: -0.11, vol: 0.019, usd: 280, wick: 1.2 }, // correction
  { n: 21, ret: 0.07, vol: 0.01, usd: 150, wick: 0.9 }, // base, higher lows
];

// Live candles (0.5 s each): calm, buyers, breakout, parabolic, with
// pullbacks. ret = close/open - 1, uw/lw = wicks, usd = 1 s volume.
const LIVE_SCRIPT = [
  // 0 - 2 s: calm; the position opens at the close of the first candle
  { ret: +0.008, uw: 0.004, lw: 0.006, usd: 210 },
  { ret: -0.012, uw: 0.004, lw: 0.007, usd: 260 },
  { ret: +0.005, uw: 0.006, lw: 0.004, usd: 190 },
  { ret: -0.004, uw: 0.005, lw: 0.006, usd: 170 },
  // 2 - 4 s: buyers arrive
  { ret: +0.05, uw: 0.01, lw: 0.004, usd: 820 },
  { ret: +0.08, uw: 0.018, lw: 0.006, usd: 1300 },
  { ret: -0.02, uw: 0.012, lw: 0.01, usd: 760 },
  { ret: +0.12, uw: 0.02, lw: 0.005, usd: 1750 },
  // 4 - 7 s: breakout with a pullback and a short pause
  { ret: +0.18, uw: 0.03, lw: 0.008, usd: 2300 },
  { ret: +0.25, uw: 0.05, lw: 0.012, usd: 3400 },
  { ret: -0.06, uw: 0.02, lw: 0.025, usd: 2100 },
  { ret: +0.17, uw: 0.03, lw: 0.01, usd: 2900 },
  { ret: +0.3, uw: 0.045, lw: 0.012, usd: 4700 },
  { ret: -0.03, uw: 0.03, lw: 0.03, usd: 2800 },
  // 7 - 10 s: parabolic, with a sharp correction and a long upper wick
  { ret: +0.25, uw: 0.04, lw: 0.01, usd: 5700 },
  { ret: +0.32, uw: 0.06, lw: 0.015, usd: 7800 },
  { ret: -0.09, uw: 0.08, lw: 0.03, usd: 6300 },
  { ret: +0.27, uw: 0.035, lw: 0.012, usd: 7500 },
  { ret: +0.33, uw: 0.05, lw: 0.015, usd: 9700 },
  { ret: +0.18, uw: 0.06, lw: 0.012, usd: 8400 }, // still forming at the end
];

function genHistory(rng) {
  const out = [];
  let lp = 0;
  for (const seg of HIST_SEGMENTS) {
    const rs = Array.from({ length: seg.n }, () => seg.vol * gauss(rng));
    const shift = (Math.log(1 + seg.ret) - rs.reduce((a, b) => a + b, 0)) / seg.n;
    for (let i = 0; i < seg.n; i++) {
      const r = rs[i] + shift;
      const o = Math.exp(lp);
      const c = Math.exp(lp + r);
      const spikeU = rng() < 0.07 ? 2.6 : 1;
      const spikeL = rng() < 0.07 ? 2.6 : 1;
      const uw = seg.vol * seg.wick * (0.15 + 0.85 * Math.abs(gauss(rng))) * spikeU;
      const lw = seg.vol * seg.wick * (0.15 + 0.85 * Math.abs(gauss(rng))) * spikeL;
      const usd = seg.usd * (0.45 + (1.5 * Math.abs(r)) / seg.vol) * Math.exp(0.35 * gauss(rng)) * (spikeU > 1 || spikeL > 1 ? 1.6 : 1);
      out.push({ o, h: Math.max(o, c) * Math.exp(uw), l: Math.min(o, c) * Math.exp(-lw), c, usd });
      lp += r;
    }
  }
  return out;
}

function fmtClock(sec) {
  const s = ((Math.floor(sec) % 86400) + 86400) % 86400;
  return [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60].map((v) => String(v).padStart(2, '0')).join(':');
}

export function buildProMarket({ seed = 7, histSeed = 3, tradeSeed = 11 } = {}) {
  const rng = mulberry32(seed);
  const hrng = mulberry32(histSeed);
  const trng = mulberry32(tradeSeed);

  // ---- prices: relative history, then live candles; scaled so the entry tick
  // (close of live candle 0) is displayed as $0.00001567
  const histRel = genHistory(hrng);
  const entryRel = histRel[HIST - 1].c * (1 + LIVE_SCRIPT[0].ret);
  const k = ENTRY_PRICE / entryRel;
  const hist = histRel.map((x) => ({ o: x.o * k, h: x.h * k, l: x.l * k, c: x.c * k, usd: x.usd }));
  const P0 = hist[0].o;

  const live = [];
  let price = hist[HIST - 1].c;
  LIVE_SCRIPT.forEach((s, j) => {
    const o = price;
    const c = j === 0 ? ENTRY_PRICE : o * (1 + s.ret);
    const hiT = Math.max(o, c) * (1 + s.uw * (0.85 + 0.3 * rng()));
    const loT = Math.min(o, c) * (1 - s.lw * (0.85 + 0.3 * rng()));
    const path = makePath(o, c, hiT, loT, CANDLE_S, rng);
    const n = path.length;
    const pmax = new Float64Array(n);
    const pmin = new Float64Array(n);
    const act = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      pmax[i] = i ? Math.max(pmax[i - 1], path[i]) : path[i];
      pmin[i] = i ? Math.min(pmin[i - 1], path[i]) : path[i];
      act[i] = i ? act[i - 1] + Math.abs(path[i] - path[i - 1]) : 0;
    }
    live.push({ t0: j * CANDLE_S, t1: (j + 1) * CANDLE_S, o, c, path, pmax, pmin, act, usd: s.usd * (0.92 + 0.16 * rng()) });
    price = c;
  });

  const idxAt = (L, t) => Math.max(0, Math.min(L.path.length - 1, Math.floor((t - L.t0) * SAMPLE_HZ)));

  function liveAt(j, t) {
    const L = live[j];
    const i = idxAt(L, t);
    const u = i / (L.path.length - 1);
    const a = L.act[L.act.length - 1] > 0 ? L.act[i] / L.act[L.act.length - 1] : u;
    return { o: L.o, h: L.pmax[i], l: L.pmin[i], c: L.path[i], usd: L.usd * (0.3 * u + 0.7 * a) };
  }

  function candlesAt(t) {
    const out = hist.map((x) => ({ ...x }));
    for (let j = 0; j < live.length; j++) {
      if (t < live[j].t0) break;
      if (t >= live[j].t1 && j < live.length - 1) {
        const L = live[j];
        out.push({ o: L.o, h: L.pmax[L.pmax.length - 1], l: L.pmin[L.pmin.length - 1], c: L.c, usd: L.usd });
      } else {
        out.push(liveAt(j, t));
        break;
      }
    }
    return out;
  }

  // ---- trade tape: each candle's volume split into trades at prices on the
  // candle's own path; side follows the tick direction (with some noise)
  const trades = [];
  const addTrades = (chartSec, tv0, usd, priceAt, dirAt, bias) => {
    const n = Math.max(1, Math.min(9, Math.round(Math.sqrt(usd) * 0.1)));
    const w = Array.from({ length: n }, () => Math.exp(0.95 * gauss(trng)));
    const ws = w.reduce((a, b) => a + b, 0);
    const fr = Array.from({ length: n }, () => trng()).sort((a, b) => a - b);
    fr.forEach((f, i) => {
      const p = priceAt(f);
      const d = dirAt(f);
      const pBuy = Math.min(0.92, Math.max(0.08, 0.5 + 0.38 * Math.sign(d || bias) + 0.1 * bias));
      const v = (usd * w[i]) / ws;
      trades.push({ tv: tv0 + f * CANDLE_S, chart: chartSec + f, side: trng() < pBuy ? 'buy' : 'sell', usd: v, price: p, tokens: v / p });
    });
  };
  hist.forEach((x, i) => {
    const dir = Math.sign(x.c - x.o);
    // o -> (l or h) -> (h or l) -> c, as a rough intra-candle path
    const pts = dir >= 0 ? [x.o, x.l, x.h, x.c] : [x.o, x.h, x.l, x.c];
    const at = (f) => {
      const s = f * 3;
      const k2 = Math.min(2, Math.floor(s));
      return pts[k2] + (pts[k2 + 1] - pts[k2]) * (s - k2);
    };
    addTrades(i, (i - HIST) * CANDLE_S, x.usd, at, (f) => at(Math.min(1, f + 0.05)) - at(Math.max(0, f - 0.05)), dir);
  });
  live.forEach((L, j) => {
    const at = (f) => L.path[Math.round(f * (L.path.length - 1))];
    const dir = (f) => at(Math.min(1, f + 0.04)) - at(Math.max(0, f - 0.04));
    addTrades(HIST + j, L.t0, L.usd, at, dir, Math.sign(L.c - L.o));
  });
  trades.sort((a, b) => a.tv - b.tv);

  // ---- auto-scale timelines (precomputed so every frame renders the same)
  const steps = Math.ceil(DURATION * SAMPLE_HZ) + 1;
  const yTop = new Float64Array(steps);
  const yBot = new Float64Array(steps);
  const vTop = new Float64Array(steps);
  const dt = 1 / SAMPLE_HZ;
  let sTop = 0;
  let sVol = 0;
  for (let j = 0; j < steps; j++) {
    const cs = candlesAt(j * dt);
    let hi = -Infinity;
    let lo = Infinity;
    let vmax = 0;
    for (const x of cs) {
      hi = Math.max(hi, x.h);
      lo = Math.min(lo, x.l);
      vmax = Math.max(vmax, x.usd);
    }
    // log scale: margins and easing are applied to log(price)
    const lh = Math.log(hi);
    const ll = Math.log(lo);
    const range = lh - ll;
    const targetTop = lh + 0.06 * range;
    if (j === 0) {
      sTop = targetTop;
      sVol = vmax * 1.1;
    } else {
      sTop += (targetTop - sTop) * (1 - Math.exp(-dt / 0.18));
      sVol += (vmax * 1.1 - sVol) * (1 - Math.exp(-dt / 0.25));
    }
    yTop[j] = Math.max(sTop, lh + 0.01 * range);
    yBot[j] = ll - 0.04 * range;
    vTop[j] = Math.max(sVol, vmax * 1.02);
  }

  function stateAt(t) {
    const tt = Math.max(0, Math.min(DURATION, t));
    const j = Math.min(steps - 1, Math.floor(tt * SAMPLE_HZ));
    const candles = candlesAt(tt);
    // the header ticker, the panel and the tape refresh 10 times per second
    const tq = Math.floor(tt * 10) / 10;
    const tick = candlesAt(tq);
    const last = tick[tick.length - 1].c;
    const chartNow = HIST + tq / CANDLE_S;
    const done = trades.filter((x) => x.tv <= tq);
    const recent = done.filter((x) => x.chart > chartNow - 60);
    const sum = (arr) => arr.reduce((a, x) => a + x.usd, 0);
    const buys = recent.filter((x) => x.side === 'buy');
    const sells = recent.filter((x) => x.side === 'sell');
    return {
      t: tt,
      candles,
      logMin: yBot[j], // log(price) at the bottom / top of the price pane
      logMax: yTop[j],
      vMax: vTop[j],
      price: last,
      pct: (last / P0 - 1) * 100,
      mcap: last * SUPPLY,
      liquidity: LIQ0 * Math.sqrt(last / P0),
      chartNow,
      clock: fmtClock(CLOCK0 + chartNow),
      tape: done.slice(-16).reverse().map((x) => ({ ...x, age: Math.max(0, Math.floor(chartNow - x.chart)) })),
      stats: {
        vol: sum(recent),
        buys: buys.length,
        sells: sells.length,
        buyUsd: sum(buys),
        sellUsd: sum(sells),
        txns: recent.length,
      },
    };
  }

  return { P0, hist, live, trades, stateAt, candlesAt, clockOf: (slot) => fmtClock(CLOCK0 + slot) };
}
