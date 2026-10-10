// Demo state machine for the app component (dev harness only).
// demoState(t) walks through every state of the update(state) contract, t = 0..7:
//   0    rest (MOCHI / ZORP / FROGO open, no GLINT position yet)
//   1    ZORP row inserting (fractional insert + lavender flash)
//   1.5  GLINT row inserting
//   2    GLINT highlighted, Snipe hover
//   2.5  Snipe pressed
//   3    Snipe pending ("Sniping")
//   3.4  Snipe done ("Bought"): wallet −1.005 SOL, GLINT position opens (1.00 SOL at the
//        entry), in-app toast (text derived by the app: fillQuote)
//   4.1  trade preset 0.5 selected, Buy hover + press, then Executing
//   4.8  trade filled at chart reveal trade.fillAt: GLINT 1.50 SOL at the averaged entry,
//        chart line moves to "Avg entry", B2 marker, Est. receive frozen at the fill quote,
//        chart PnL flash, second toast
//   6    FROGO take-profit at +30% ("TP hit · sold", wallet +2.595 SOL, Positions 3)
//   7    feed keeps streaming (rows inserted below the header, GLINT shifts down)
//
// Like the reel's timeline, every displayed value is frame-locked: state.t and chart.reveal
// step at 7.5 Hz (tick), the continuous t only goes to state.tMotion (spinners, pulse,
// tape slide) and to geometry (row inserts, toasts, hovers).
import { clamp, prog, ease, kf } from '../lib/engine.js';

// Dev-harness nicety: with ?view=cx,cy,zoom the zoomed app overflows the 1080px-tall
// body, which clips it. Let the body fill the viewport so camera crops render fully.
if (typeof location !== 'undefined' && new URLSearchParams(location.search).has('view')) {
  document.documentElement.style.height = '100%';
  document.body.style.height = '100%';
}

const bump = (t, t0, t1, a = 0.12, b = 0.25) => Math.min(ease.outCubic(prog(t, t0, t0 + a)), 1 - ease.inOutSine(prog(t, t1 - b, t1)));
/** 7.5 Hz data clock (4 frames at 30 fps), as in the timeline. */
const tick = (t) => Math.floor(t * 7.5 + 1e-6) / 7.5;
/** Frame clock (30 fps): discrete states flip on frame boundaries, never inside a frame's sub-samples. */
const frame = (t) => Math.floor(t * 30 + 1e-6) / 30;

const fill1 = 3.4;  // feed snipe fills
const fill2 = 4.8;  // trade panel buy fills (on a tick)
// 15 s candles: the chart is past candle 40 here (as in the reel's drop); the second buy
// fills at reveal 0.957 and the last candle closes at t = 7
const revealAt = (t) => kf(t, [[0, 0.84], [fill2, 0.957, ease.linear], [7, 1, ease.linear]]);
const FILL_AT = revealAt(fill2);

export function demoState(t) {
  const td = tick(t), tf = frame(t);
  const toast1 = bump(t, fill1 + 0.05, 4.3, 0.3, 0.25);
  const toast2 = bump(t, fill2 + 0.02, 5.9, 0.25, 0.25);
  return {
    t: td,
    tMotion: t,
    feed: {
      inserted: kf(t, [[0.6, 0], [1.3, 1, ease.inOutSine], [1.35, 1], [1.85, 2, ease.inOutSine], [6.3, 2], [7, 3.5, ease.inOutSine]]),
      highlight: 'GLINT',
      highlightAmt: ease.outCubic(prog(t, 1.8, 1.95)),
      snipeHover: t < 3 ? prog(t, 1.86, 1.98) : 1 - prog(t, 3.6, 3.9),
      snipePress: bump(t, 2.42, 2.62, 0.06, 0.12),
      snipeState: tf < 2.55 ? 'idle' : tf < fill1 ? 'pending' : 'done',
      scroll: 0,
    },
    chart: {
      reveal: revealAt(td),
      entry: 1,
      pnlFlash: bump(t, fill2 + 0.05, 5.45, 0.08, 0.3),
    },
    trade: {
      preset: tf < 4.12 ? 2 : 1,
      presetHover: tf > 3.9 && tf < 4.18 ? 1 : -1,
      buyHover: t < 5 ? prog(t, 4.25, 4.35) : 1 - prog(t, 5.3, 5.6),
      buyPress: bump(t, 4.36, 4.54, 0.06, 0.12),
      buyState: tf < 4.46 ? 'idle' : tf < fill2 ? 'pending' : 'filled',
      fillAt: FILL_AT,
    },
    positions: {
      // GLINT is derived by the app; FROGO ramps into its +30 % take-profit
      pnl: {
        MOCHI: kf(td, [[5.4, 8.2], [5.7, 8.6]]),
        ZORP: -4.1,
        FROGO: kf(td, [[4.5, 26.4], [5.4, 28.1, ease.inOutSine], [6, 30.0, ease.outCubic]]),
      },
      flash: {
        GLINT: bump(t, fill2 + 0.05, 5.6, 0.08, 0.35),
        FROGO: bump(t, 6, 6.6, 0.08, 0.35),
        MOCHI: bump(t, 5.4, 5.9, 0.08, 0.3) * 0.7,
      },
      tp: ease.outCubic(prog(tf, 6, 6.15)),
    },
    // text/sub left to the app: it describes the latest fill (fillQuote)
    toast: { show: tf >= fill2 ? toast2 : clamp(toast1) },
  };
}
