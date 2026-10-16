# SOL Sniper: candlestick chart video

A 1920×1080, 60 fps, 10 s screen-recording-style candlestick chart of `$USELESS`
in the SOL Sniper interface. It reproduces the reference memecoin chart
(dark navy panel, turquoise/red candles, volume bars, timeframe pills, price and
% top right). A simulated $500 position, marked to the displayed price, is
shown in a PNL panel.

**Outputs** (H.264 High, 1920×1080, 60 fps, exactly 10.000 s / 600 frames, no audio, BT.709):

- [`out/sol-sniper-useless-pnl.mp4`](out/sol-sniper-useless-pnl.mp4): chart, PNL panel and entry marker
- [`out/sol-sniper-useless-pnl.jpg`](out/sol-sniper-useless-pnl.jpg): capture at t = 9.8 s (frame 588)
- [`out/sol-sniper-useless.mp4`](out/sol-sniper-useless.mp4): original chart only
- [`out/pnl-frames.csv`](out/pnl-frames.csv): displayed price and panel values for every frame

With the overlay disabled, the code reproduces `out/sol-sniper-useless.mp4`
byte-for-byte, so the overlay leaves the chart untouched.

## Data

All prices are **synthetic** and come from a fixed seed. They visualise a
memecoin pump and are not real market data or a result obtained with SOL
Sniper. The position is simulated too, and the panel says so ("Simulated
position · Excl. fees & slippage").

- 30 historical candles are on the chart at t = 0. 16 new candles form over
  the 10 s: calm (0-2 s), buyers arrive (2-4 s), breakout (4-7 s), parabolic
  (7-10 s).
- Each new candle follows a tick-level price path (240 samples/s). Its body,
  wicks and volume are read from that path, so the price, the candles and the
  volume always agree. The header price refreshes 10 times per second.
- The header % change is measured against the first open on the chart.

## Position (PNL panel)

- $500 opened at frame 30 (t = 0.500 s), the first frame whose header shows
  **$0.00001567**. This price trades inside the entry candle. Before entry,
  the panel shows "NO POSITION" and no value, PNL or ROI.
- All values come from the prices **as displayed**, in exact integer
  arithmetic (`src/position.js`):
  tokens = 500 / entry, value = tokens × price, PNL = value − 500,
  ROI = PNL / 500 × 100. Fees and slippage are excluded. The panel refreshes
  on the same frames as the header price, so a red candle lowers the PNL.
- At t = 9.8 s: $0.0001290 → value $4,116.15, PNL +$3,616.15, ROI +723.23%.
  Final frames: $0.0001380 → $4,403.32, +$3,903.32, +780.66%. The ROI is
  measured from the entry, while the header % (+1,956%) is measured from the
  chart start.
- Entry marker: a violet dot just left of the entry candle at the entry
  price, a dashed line from the dot to the price axis, and an
  `ENTRY — $500` tag. The line stops 1 px short of every candle and volume
  bar, so the chart's own marks are never painted over.
- `npm run check` verifies on all 600 frames that the panel (with its
  shadow), the tag, the dot and the line never cover a candle, a volume bar,
  the pills, the header or the price axis. Glow is included for the panel and
  the tag.
- `npm run check:pixels` renders all 600 frames losslessly with and without
  the overlay. It confirms that 0 candle or volume-bar pixels change and that
  nothing changes outside the overlay's own areas.

## Assets

- `public/assets/solsniper-logo.png`: the SOL Sniper logo (icon and
  wordmark) captured from the logo element on solsniper.com, with a
  transparent background. `solsniper-icon.png` is the icon file from the same
  site.
- `public/assets/useless.png`: the official USELESS COIN icon (mint
  `Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk`), from CoinGecko, matching
  DexScreener.
- `public/fonts/InterTnum-*.otf`: Inter with tabular digits as the default
  (made by `scripts/make-tnum-font.py`), so the panel figures never shift
  sideways. Canvas cannot enable the `tnum` feature itself. SIL OFL 1.1, see
  `public/fonts/OFL.txt`.

## Render

```sh
npm install
npm run video            # out/sol-sniper-useless-pnl.mp4
npm run video:original   # out/sol-sniper-useless.mp4 (no overlay)
npm run check            # frame-by-frame overlap check
npm run check:pixels     # lossless proof that no chart pixel changes
npm run pnl-table        # out/pnl-frames.csv
node scripts/render-still.js 9.8 out/frame.png   # one frame, needs Playwright
npm run studio           # live preview in Remotion Studio
```

The video is rendered by Remotion 4 (lossless PNG frames, then H.264 at
CRF 16), and an FFmpeg `+faststart` pass follows. The render is deterministic:
re-rendering gives a byte-identical file. Needs Node 18+, FFmpeg and the Inter
font installed system-wide. Set `BROWSER_EXECUTABLE` to use an existing
Chrome headless shell instead of Remotion's download.

## Layout

- `src/engine.js`: deterministic market simulation (candles, tick paths, auto-scale)
- `src/render.js`: Canvas 2D chart renderer, `drawFrame(ctx, t, market, assets, position?)`
- `src/overlay.js`: PNL panel and entry marker
- `src/position.js`: position math on displayed prices
- `src/format.js`, `src/ui.js`, `src/fonts.js`: formatting, theme/layout, font loading
- `src/remotion/`: Remotion composition (`SolSniperChart`, 1920×1080, 60 fps,
  600 frames, prop `overlay`). A `<canvas>` calls `drawFrame` with t = frame / 60.
- `preview/index.html`: draws one frame (`?t=8`, `&overlay=0`)
- `scripts/`: render, check and export scripts
