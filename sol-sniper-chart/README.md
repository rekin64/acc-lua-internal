# SOL Sniper: candlestick chart video

A 1920×1080, 60 fps, 10 s screen-recording-style candlestick chart of `$USELESS`
in the SOL Sniper interface. It reproduces the reference memecoin chart
(dark navy panel, turquoise/red candles, volume bars, timeframe pills, price and
% top right).

**Output: [`out/sol-sniper-useless.mp4`](out/sol-sniper-useless.mp4)**: H.264 High,
1920×1080, 60 fps, exactly 10.000 s (600 frames), no audio, BT.709. The
validated still is [`out/preview_t8.png`](out/preview_t8.png), and frame 480 of
the video is pixel-identical to it.

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

## Render

```sh
npm install
npm run video                                        # out/sol-sniper-useless.mp4
node scripts/render-still.js 8 out/preview_t8.png   # one frame (t = 8 s), needs Playwright
npm run studio                                       # live preview in Remotion Studio
```

The video is rendered by Remotion 4 (lossless PNG frames, then H.264 at
CRF 16), and an FFmpeg `+faststart` pass follows. The render is deterministic:
re-rendering gives a byte-identical file. Needs Node 18+, FFmpeg and the Inter
font installed system-wide. Set `BROWSER_EXECUTABLE` to use an existing
Chrome headless shell instead of Remotion's download.

## Layout

- `src/engine.js`: deterministic market simulation (candles, tick paths, auto-scale)
- `src/render.js`: Canvas 2D renderer, `drawFrame(ctx, t, market, assets)`
- `src/remotion/`: Remotion composition (`SolSniperChart`, 1920×1080, 60 fps,
  600 frames). A `<canvas>` calls `drawFrame` with t = frame / 60.
- `preview/index.html`: draws one frame (`?t=8`)
- `scripts/render-still.js`: headless Chromium screenshot of the preview
- `scripts/render-video.sh`: full video render
