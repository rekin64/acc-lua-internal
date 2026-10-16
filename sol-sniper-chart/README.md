# SOL Sniper: candlestick chart video

A 1920×1080, 60 fps, 10 s screen-recording-style candlestick chart of `$USELESS`
in the SOL Sniper interface. It reproduces the reference memecoin chart
(dark navy panel, turquoise/red candles, volume bars, timeframe pills, price and
% top right).

**Status: still preview awaiting validation (step 3). The video is not rendered yet.**

## Data

All prices are **synthetic** and come from a fixed seed. They visualise a
memecoin pump and are not real market data or a result obtained with SOL
Sniper. The frame carries a discreet `Simulated data` mark.

- 30 historical candles are on the chart at t = 0. 16 new candles form over
  the 10 s: calm (0-2 s), buyers arrive (2-4 s), breakout (4-7 s), parabolic
  (7-10 s).
- Each new candle follows a tick-level price path (240 samples/s). Its body,
  wicks and volume are read from that path, so the price, the candles and the
  volume always agree.
- The % change is measured against the first open on the chart.

## Assets

- `public/assets/solsniper-logo.png`: the SOL Sniper logo (icon and
  wordmark) captured from the logo element on solsniper.com, with a
  transparent background.
- `public/assets/useless.png`: the official USELESS COIN icon (mint
  `Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk`), from CoinGecko, matching
  DexScreener.

## Render a still

```sh
node scripts/render-still.js 8 out/preview_t8.png   # frame at t = 8 s
```

Needs Node 18+ and Playwright with Chromium. Fonts: Inter, installed system-wide.

## Layout

- `src/engine.js`: deterministic market simulation (candles, tick paths, auto-scale)
- `src/render.js`: Canvas 2D renderer, `drawFrame(ctx, t, market, assets)`
- `preview/index.html`: draws one frame (`?t=8`)
- `scripts/render-still.js`: headless Chromium screenshot of the preview
