// Trade-driven market model for the pro terminal layout.
//
// SYNTHETIC DATA: every price, trade and volume comes from fixed seeds. It is
// a visualisation of a memecoin pump, not market data and not a result
// obtained with SOL Sniper.
//
// The pool is a constant-product AMM: every trade moves the price (a buy up,
// a sell down) and its size follows from the price move and the pool depth.
// The last trade is the single source of truth: candle close, price line,
// axis tag, legend, header, position panel and the top of the tape all read
// it, so they always agree.

import { DURATION, SAMPLE_HZ, gauss, makePath, mulberry32 } from '../engine.js';

export const CANDLE_S = 0.5; // video seconds per 1 s candle (2x speed)
export const PLAYBACK_SPEED = 1 / CANDLE_S; // chart seconds per video second (shown as "Speed 2x")
export const HIST = 300; // 1 s candles before t = 0 (5 min, feeds the 5m stats)
export const VIS_HIST = 76; // of which drawn on the chart
export const LIVE = Math.round(DURATION / CANDLE_S); // 20 candles form during the video
export const SLOTS = 100; // fixed x slots: 76 history + 20 live + right margin
export const SUPPLY = 1e9; // USELESS total supply
const ENTRY_PRICE = 0.00001567; // last trade when the simulated position opens (t = 0.5 s)
// Last trade of the video (closes the last candle at t = 9.8 s). It is the
// last trade of the mockup the client reviewed, so the end shows the same
// price ($0.0001043), PNL, ROI and 5m change.
const FINAL_PRICE = 0.000104295;
const RISE_FROM = 8; // first candle of the final run (t = 4 s)
const POOL_USD_AT_ENTRY = 5000; // USD side of the pool at the entry price
export const CLOCK0 = 14 * 3600 + 30 * 60 + 40; // chart clock of history candle 0 (14:30:40)

// History phases (ret = total move, vol = per-candle sigma, rate = trades/s).
const HIST_SEGMENTS = [
  { n: 224, ret: 0.42, vol: 0.012, wick: 0.9, rate: 1.2 }, // earlier session (off-chart)
  { n: 14, ret: 0.08, vol: 0.014, wick: 1.0, rate: 1.6 }, // accumulation
  { n: 12, ret: 0.42, vol: 0.032, wick: 1.0, rate: 3.0 }, // first leg
  { n: 13, ret: -0.07, vol: 0.02, wick: 1.5, rate: 2.4 }, // choppy consolidation
  { n: 11, ret: 0.3, vol: 0.032, wick: 1.0, rate: 3.0 }, // second leg
  { n: 8, ret: -0.1, vol: 0.022, wick: 1.3, rate: 2.6 }, // correction
  { n: 18, ret: 0.07, vol: 0.012, wick: 1.0, rate: 1.6 }, // base, higher lows
];

// Live candles: ret = scripted close/open - 1 (up-moves of the final run are
// rescaled, see below), uw/lw = wick extensions, rate = trades per video
// second. Pullbacks, indecision candles and rejection wicks keep the pump
// from looking mechanical.
const LIVE_SCRIPT = [
  // 0 - 2 s: calm; the position opens on the close of the first candle
  { ret: +0.008, uw: 0.012, lw: 0.014, rate: 6 },
  { ret: -0.012, uw: 0.01, lw: 0.016, rate: 6 },
  { ret: +0.004, uw: 0.016, lw: 0.012, rate: 5 },
  { ret: -0.005, uw: 0.012, lw: 0.014, rate: 5 },
  // 2 - 4 s: buyers arrive
  { ret: +0.06, uw: 0.03, lw: 0.005, rate: 7 },
  { ret: +0.09, uw: 0.025, lw: 0.008, rate: 8 },
  { ret: -0.02, uw: 0.01, lw: 0.02, rate: 7 },
  { ret: +0.13, uw: 0.05, lw: 0.006, rate: 9 },
  // 4 - 10 s: final run. Impulses of different sizes and shapes at an
  // irregular rhythm, single and two-candle pullbacks, an indecision candle
  // and a rejection; wicks vary (dips bought, profit taking). Up-moves are
  // rescaled below so the run ends on FINAL_PRICE.
  { ret: +0.17, uw: 0.04, lw: 0.02, rate: 11 }, // breakout
  { ret: +0.32, uw: 0.075, lw: 0.015, rate: 15 }, // impulse, profit taking at the top
  { ret: -0.045, uw: 0.02, lw: 0.065, rate: 12 }, // pullback, dip bought
  { ret: +0.36, uw: 0.025, lw: 0.02, rate: 16 }, // impulse
  { ret: +0.08, uw: 0.06, lw: 0.02, rate: 11 }, // momentum fades
  { ret: -0.03, uw: 0.04, lw: 0.02, rate: 10 }, // pause
  { ret: -0.055, uw: 0.015, lw: 0.05, rate: 12 }, // second red candle
  { ret: +0.27, uw: 0.03, lw: 0.06, rate: 14 }, // bounce from a dip
  { ret: +0.38, uw: 0.05, lw: 0.015, rate: 16 }, // impulse
  { ret: +0.05, uw: 0.09, lw: 0.04, rate: 12 }, // indecision, long upper wick
  { ret: -0.075, uw: 0.06, lw: 0.045, rate: 13 }, // rejection
  { ret: +0.33, uw: 0.02, lw: 0.035, rate: 22 }, // final push, closes at t = 9.8 s
];

const fmtClock = (sec) => {
  const s = ((Math.floor(sec) % 86400) + 86400) % 86400;
  return [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60].map((v) => String(v).padStart(2, '0')).join(':');
};

// Sorted trade times in [0, 1) for a candle, always including the path's
// extremes and its close, so the candle's high, low and close are real trades.
function tradeFractions(rng, n, mustHave, hi = 0.98) {
  const fr = new Set(mustHave.map((x) => Math.min(0.999, Math.max(0.001, x))));
  while (fr.size < n + mustHave.length) fr.add(0.02 + (hi - 0.02) * rng());
  return [...fr].sort((a, b) => a - b);
}

export function buildProMarket({ seed = 7, histSeed = 3, tradeSeed = 11 } = {}) {
  const rng = mulberry32(seed);
  const hrng = mulberry32(histSeed);
  const trng = mulberry32(tradeSeed);

  // ---- history candle targets (relative prices)
  const targets = [];
  let lp = 0;
  for (const seg of HIST_SEGMENTS) {
    const rs = Array.from({ length: seg.n }, () => seg.vol * gauss(hrng));
    const shift = (Math.log(1 + seg.ret) - rs.reduce((a, b) => a + b, 0)) / seg.n;
    for (let i = 0; i < seg.n; i++) {
      const r = rs[i] + shift;
      const o = Math.exp(lp);
      const c = Math.exp(lp + r);
      const sU = hrng() < 0.08 ? 2.6 : 1;
      const sL = hrng() < 0.08 ? 2.6 : 1;
      const uw = seg.vol * seg.wick * (0.2 + 0.9 * Math.abs(gauss(hrng))) * sU;
      const lw = seg.vol * seg.wick * (0.2 + 0.9 * Math.abs(gauss(hrng))) * sL;
      targets.push({ o, c, h: Math.max(o, c) * Math.exp(uw), l: Math.min(o, c) * Math.exp(-lw), rate: seg.rate * (0.7 + 0.6 * hrng()) });
      lp += r;
    }
  }
  const k = ENTRY_PRICE / (targets[HIST - 1].c * (1 + LIVE_SCRIPT[0].ret));
  for (const x of targets) {
    x.o *= k;
    x.c *= k;
    x.h *= k;
    x.l *= k;
  }

  // ---- AMM: USD side of the pool scales with sqrt(price); a trade that moves
  // the price from p0 to p1 is worth Q(p0) * |sqrt(p1 / p0) - 1| dollars
  const poolUsd = (p) => POOL_USD_AT_ENTRY * Math.sqrt(p / ENTRY_PRICE);
  const tradeUsd = (p0, p1) => poolUsd(p0) * Math.abs(Math.sqrt(p1 / p0) - 1);

  const trades = []; // { tv, chart, price, prev, side, usd, tokens, candle }
  const candles = []; // final OHLCV of every history candle
  let last = targets[0].o;
  const push = (candle, tv, chart, price) => {
    if (price === last) return;
    const usd = tradeUsd(last, price);
    trades.push({ tv, chart, price, prev: last, side: price > last ? 'buy' : 'sell', usd, tokens: usd / ((price + last) / 2), candle });
    last = price;
  };

  // history: coarse intra-candle path o -> l/h -> h/l -> c with small noise
  const KEYS = [1 / 3, 2 / 3, 0.995];
  targets.forEach((x, i) => {
    const up = x.c >= x.o;
    const keys = up ? [x.o, x.l, x.h, x.c] : [x.o, x.h, x.l, x.c];
    const at = (f) => {
      const s = f * 3;
      const j = Math.min(2, Math.floor(s));
      return keys[j] + (keys[j + 1] - keys[j]) * (s - j);
    };
    const n = Math.max(0, Math.round(x.rate * (0.6 + 0.8 * trng())));
    const fr = tradeFractions(trng, n, KEYS);
    const start = trades.length;
    const o = last;
    fr.forEach((f) => {
      const keyHit = KEYS.some((m) => Math.abs(m - f) < 1e-9);
      const noise = keyHit ? 0 : (trng() - 0.5) * 0.08 * (x.h - x.l);
      const p = f >= 0.995 ? x.c : Math.min(x.h, Math.max(x.l, at(f) + noise));
      push(i, (i - HIST + f) * CANDLE_S, i + f, p);
    });
    const ts = trades.slice(start);
    const ps = [o, ...ts.map((tr) => tr.price)];
    candles.push({ o, h: Math.max(...ps), l: Math.min(...ps), c: last, usd: ts.reduce((a, tr) => a + tr.usd, 0) });
  });

  // The final run is rescaled so the video ends exactly on FINAL_PRICE: its
  // up-moves are stretched by one common factor, pullbacks keep their depth.
  const logRet = LIVE_SCRIPT.map((s) => Math.log(1 + s.ret));
  const sum = (xs) => xs.reduce((a, b) => a + b, 0);
  const run = logRet.slice(RISE_FROM, LIVE);
  const need = Math.log(FINAL_PRICE / ENTRY_PRICE) - sum(logRet.slice(1, RISE_FROM));
  const stretch = (need - sum(run.filter((x) => x < 0))) / sum(run.filter((x) => x > 0));

  // live: tick paths from the shared path generator, sampled at trade times
  const live = [];
  LIVE_SCRIPT.forEach((s, j) => {
    const o = last;
    const lastCandle = j === LIVE - 1;
    let c = o * (1 + s.ret);
    if (j === 0) c = ENTRY_PRICE;
    else if (lastCandle) c = FINAL_PRICE;
    else if (j >= RISE_FROM && s.ret > 0) c = o * Math.exp(logRet[j] * stretch);
    const hiT = Math.max(o, c) * (1 + s.uw * (0.85 + 0.3 * rng()));
    const loT = Math.min(o, c) * (1 - s.lw * (0.85 + 0.3 * rng()));
    const path = makePath(o, c, hiT, loT, CANDLE_S, rng);
    const N = path.length - 1;
    let iMax = 0;
    let iMin = 0;
    for (let i = 0; i <= N; i++) {
      if (path[i] > path[iMax]) iMax = i;
      if (path[i] < path[iMin]) iMin = i;
    }
    const n = Math.max(1, Math.round(s.rate * CANDLE_S * (0.8 + 0.4 * trng())));
    // extremes before the close, so the close is the candle's last trade; the
    // last candle closes at 0.6 (t = 9.8 s), so the final price holds on screen
    // for the video's last 12 frames
    const cf = lastCandle ? 0.6 : 0.98;
    const fr = tradeFractions(trng, n, [Math.min(cf - 0.02, iMax / N), Math.min(cf - 0.02, iMin / N), cf], cf);
    const t0 = j * CANDLE_S;
    const churn = Math.min(0.55, Math.abs(s.ret) * 2.2); // profit-taking grows with the move
    fr.forEach((f, q) => {
      const p = f >= cf ? c : path[Math.round(f * N)];
      const prev = last;
      push(HIST + j, t0 + f * CANDLE_S, HIST + j + f, p);
      // after a buy, some holders sell part of the move back (never on the close)
      const next = q + 1 < fr.length ? fr[q + 1] : cf;
      if (f < cf && p > prev && trng() < churn && next - f > 0.03) {
        const back = Math.max(loT, p - (0.35 + 0.3 * trng()) * (p - prev));
        push(HIST + j, t0 + (f + 0.45 * (next - f)) * CANDLE_S, HIST + j + f + 0.45 * (next - f), back);
      }
    });
    live.push({ t0, t1: t0 + CANDLE_S, o });
  });

  // ---- what is on screen at time t: everything reads the last trade <= t
  const tvs = trades.map((tr) => tr.tv);
  const lastIndexAt = (t) => {
    let lo = 0;
    let hi = tvs.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (tvs[mid] <= t + 1e-9) lo = mid;
      else hi = mid - 1;
    }
    return lo;
  };
  const histCandles = candles.slice(HIST - VIS_HIST, HIST);
  const firstLive = trades.findIndex((tr) => tr.candle >= HIST);

  function candlesAt(t) {
    const out = histCandles.map((x) => ({ ...x }));
    const li = lastIndexAt(t);
    for (let j = 0; j < LIVE; j++) {
      if (t < live[j].t0) break;
      const ts = [];
      for (let q = firstLive; q <= li; q++) if (trades[q].candle === HIST + j) ts.push(trades[q]);
      const o = live[j].o;
      const ps = [o, ...ts.map((tr) => tr.price)];
      out.push({ o, h: Math.max(...ps), l: Math.min(...ps), c: ts.length ? ts[ts.length - 1].price : o, usd: ts.reduce((a, tr) => a + tr.usd, 0) });
    }
    return out;
  }

  // ---- log-scale auto range over the visible candles, precomputed. A
  // critically damped follower (two first-order lags) moves the scale without
  // a jolt. It looks only 80 ms (5 frames) ahead, and a fresh high may sit up
  // to OVERSHOOT of the price pane above its top margin (a fresh volume bar up
  // to VOL_OVERSHOOT of its pane), so a single large trade never forces a
  // jump; the scale then eases to make room.
  const steps = Math.ceil(DURATION * SAMPLE_HZ) + 1;
  const dt = 1 / SAMPLE_HZ;
  const LOOK = Math.round(0.08 * SAMPLE_HZ);
  const TAU = 0.06;
  const OVERSHOOT = 1.067;
  const VOL_OVERSHOOT = 1.15;
  const lh = new Float64Array(steps);
  const ll = new Float64Array(steps);
  const vm = new Float64Array(steps);
  for (let j = 0; j < steps; j++) {
    let hi = -Infinity;
    let lo = Infinity;
    for (const x of candlesAt(j * dt)) {
      hi = Math.max(hi, x.h);
      lo = Math.min(lo, x.l);
      vm[j] = Math.max(vm[j], x.usd);
    }
    lh[j] = Math.log(hi);
    ll[j] = Math.log(lo);
  }
  const ahead = (arr, j, f) => {
    let v = -Infinity;
    for (let k = j; k <= Math.min(steps - 1, j + LOOK); k++) v = Math.max(v, f(arr[k], k));
    return v;
  };
  const yTop = new Float64Array(steps);
  const yBot = new Float64Array(steps);
  const vTop = new Float64Array(steps);
  const ease = 1 - Math.exp(-dt / TAU);
  let aTop = 0;
  let sTop = 0;
  let aVol = 0;
  let sVol = 0;
  for (let j = 0; j < steps; j++) {
    const target = ahead(lh, j, (h, q) => h + 0.06 * (h - ll[q]));
    const vTarget = ahead(vm, j, (v) => v * 1.1);
    if (j === 0) {
      aTop = sTop = target;
      aVol = sVol = vTarget;
    } else {
      aTop += (target - aTop) * ease;
      sTop += (aTop - sTop) * ease;
      aVol += (vTarget - aVol) * ease;
      sVol += (aVol - sVol) * ease;
    }
    // lowest top that keeps the high within OVERSHOOT of the pane, given
    // that the bottom sits 4% of (top - low) under the low
    const minTop = (lh[j] + 1.04 * (OVERSHOOT - 1) * ll[j]) / (1.04 * OVERSHOOT - 0.04);
    yTop[j] = Math.max(sTop, minTop);
    yBot[j] = ll[j] - 0.04 * (yTop[j] - ll[j]);
    vTop[j] = Math.max(sVol, vm[j] / VOL_OVERSHOOT);
  }

  const P0 = candles[HIST - VIS_HIST].o;
  const windowStats = (li, chartNow, secs) => {
    let buys = 0;
    let sells = 0;
    let buyUsd = 0;
    let sellUsd = 0;
    for (let q = li; q >= 0 && trades[q].chart > chartNow - secs; q--) {
      if (trades[q].side === 'buy') {
        buys++;
        buyUsd += trades[q].usd;
      } else {
        sells++;
        sellUsd += trades[q].usd;
      }
    }
    return { buys, sells, buyUsd, sellUsd, vol: buyUsd + sellUsd, txns: buys + sells };
  };
  const priceAtChart = (chartSec) => {
    let q = 0;
    while (q + 1 < trades.length && trades[q + 1].chart <= chartSec) q++;
    return trades[q].price;
  };

  function stateAt(t) {
    const tt = Math.max(0, Math.min(DURATION, t));
    const j = Math.min(steps - 1, Math.floor(tt * SAMPLE_HZ));
    const li = lastIndexAt(tt);
    const chartNow = HIST + tt / CANDLE_S;
    const price = trades[li].price;
    let ath = 0;
    let buysTotal = 0;
    for (let q = 0; q <= li; q++) {
      if (trades[q].price > ath) ath = trades[q].price;
      if (trades[q].side === 'buy') buysTotal++;
    }
    const p5m = priceAtChart(chartNow - 300);
    return {
      t: tt,
      candles: candlesAt(tt),
      logMin: yBot[j],
      logMax: yTop[j],
      vMax: vTop[j],
      price,
      pct: (price / P0 - 1) * 100,
      pct5m: (price / p5m - 1) * 100,
      mcap: price * SUPPLY,
      liquidity: 2 * poolUsd(price),
      ath,
      holders: 1180 + Math.floor(buysTotal * 0.35),
      chartNow,
      clock: fmtClock(CLOCK0 + chartNow),
      tape: trades.slice(Math.max(0, li - 15), li + 1).reverse().map((x) => ({ ...x, age: Math.max(0, Math.floor(chartNow - x.chart)) })),
      stats1m: windowStats(li, chartNow, 60),
      stats5m: windowStats(li, chartNow, 300),
    };
  }

  return {
    P0,
    trades,
    candles,
    stateAt,
    candlesAt,
    clockOf: (slot) => fmtClock(CLOCK0 + HIST - VIS_HIST + slot),
    isMinute: (slot) => (CLOCK0 + HIST - VIS_HIST + slot) % 60 === 0,
    isTen: (slot) => (CLOCK0 + HIST - VIS_HIST + slot) % 10 === 0,
  };
}
