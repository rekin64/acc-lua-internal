// Demo state machine for the app component (dev harness only).
// demoState(t) walks through every state of the update(state) contract, t = 0..7:
//   0    rest
//   1    ZORP row inserting (fractional insert + lavender flash)
//   1.5  GLINT row inserting
//   2    GLINT highlighted, Snipe hover
//   2.5  Snipe pressed
//   3    Snipe pending ("Sniping"), chart still forming
//   4    Snipe done ("Bought"): B marker + entry line on the chart (gated by the
//        candle the fill lands in), wallet −1.005 SOL, GLINT position opens, toast
//   4.4  trade preset 0.5 selected, Buy hover + press, then Executing
//   5    trade filled (wallet and GLINT size update), chart PnL flash, GLINT position flash, second toast
//   6    FROGO take-profit hit ("TP hit · sold")
//   7    feed keeps streaming (rows inserted below the header, GLINT shifts down)
import { clamp, prog, ease, kf } from '../lib/engine.js';
import { glintPnl } from '../components/app.js';

// Dev-harness nicety: with ?view=cx,cy,zoom the zoomed app overflows the 1080px-tall
// body, which clips it. Let the body fill the viewport so camera crops render fully.
if (typeof location !== 'undefined' && new URLSearchParams(location.search).has('view')) {
  document.documentElement.style.height = '100%';
  document.body.style.height = '100%';
}

const bump = (t, t0, t1, a = 0.12, b = 0.25) => Math.min(ease.outCubic(prog(t, t0, t0 + a)), 1 - ease.inOutSine(prog(t, t1 - b, t1)));

// 3 significant digits, like the app's token amounts (6.77M)
const m3 = (v) => { const m = v / 1e6; return `${m >= 10 ? m.toFixed(1) : m.toFixed(2)}M`; };

const fill1 = 3.4;  // feed snipe fills
const fill2 = 4.8;  // trade panel buy fills
// 1s candles: chop until the snipe fills late in candle 41, then the climb plays out to t=7
const revealAt = (t) => kf(t, [[0, 38.4 / 48], [fill1, 41.8 / 48, ease.linear], [7, 1, ease.linear]]);

export function demoState(t) {
  const reveal = revealAt(t);
  // PnL keyed to the drawn price path, so the chip, the drawn gap and the positions row agree
  const pnl = glintPnl(reveal);
  const pnl2 = glintPnl(revealAt(fill2)); // price when the second buy fills → tokens received
  const toast1 = bump(t, fill1 + 0.05, 4.3, 0.3, 0.25);
  const toast2 = bump(t, fill2 + 0.02, 5.9, 0.25, 0.25);
  const second = t >= 4.4;
  return {
    t,
    feed: {
      inserted: kf(t, [[0.6, 0], [1.3, 1, ease.inOutSine], [1.35, 1], [1.85, 2, ease.inOutSine], [6.3, 2], [7, 3.5, ease.inOutSine]]),
      highlight: 'GLINT',
      highlightAmt: ease.outCubic(prog(t, 1.8, 1.95)),
      snipeHover: t < 3 ? prog(t, 1.86, 1.98) : 1 - prog(t, 3.6, 3.9),
      snipePress: bump(t, 2.42, 2.62, 0.06, 0.12),
      snipeState: t < 2.55 ? 'idle' : t < fill1 ? 'pending' : 'done',
      scroll: 0,
    },
    chart: {
      reveal,
      entry: 1,
      pnl,
      pnlFlash: bump(t, fill2 + 0.05, 5.45, 0.08, 0.3),
    },
    trade: {
      preset: t < 4.12 ? 2 : 1,
      presetHover: t > 3.9 && t < 4.18 ? 1 : -1,
      buyHover: t < 5 ? prog(t, 4.25, 4.35) : 1 - prog(t, 5.3, 5.6),
      buyPress: bump(t, 4.36, 4.54, 0.06, 0.12),
      buyState: t < 4.46 ? 'idle' : t < fill2 ? 'pending' : 'filled',
    },
    positions: {
      pnl: {
        GLINT: pnl,
        MOCHI: kf(t, [[5.4, 12.6], [5.7, 13.4]]),
        ZORP: -4.1,
        FROGO: kf(t, [[4.5, 46.2], [5.4, 48.1, ease.inOutSine], [5.75, 50.0, ease.outCubic]]),
      },
      flash: {
        GLINT: bump(t, fill2 + 0.05, 5.6, 0.08, 0.35),
        FROGO: bump(t, 5.75, 6.4, 0.08, 0.35),
        MOCHI: bump(t, 5.4, 5.9, 0.08, 0.3) * 0.7,
      },
      tp: ease.outCubic(prog(t, 5.75, 5.9)),
    },
    toast: second
      ? { show: toast2, text: 'Buy filled · 0.50 SOL', sub: `${m3((0.5 * 18.2e6) / (1 + pnl2 / 100))} GLINT · simulated` }
      : { show: clamp(toast1), text: 'Buy filled · 1.00 SOL', sub: '18.2M GLINT · simulated' },
  };
}
