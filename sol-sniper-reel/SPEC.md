# SOL Sniper reel: production spec

This is the working spec the components are built against. The README covers usage.

## Creative direction (non-negotiable)

- This is a real product demo edit, the kind a senior editor cuts in After Effects or Premiere from screen recordings. It must not look like a sci-fi or AI-generated ad.
- Banned: neon, particles, holograms, glow-heavy UI, floating sci-fi panels, futuristic backgrounds, exaggerated 3D, lens flares, glitch effects, emoji.
- Allowed: clean light UI, real-looking product interactions (cursor moves, hover, click, loading, filled states), screen-recording punch-ins, whip pans, speed ramps, light motion blur, minimal typography.
- Brand: white, clean, purple and blue. The headline gradient runs #3956A4 to #6E5DBE to #AC6AD9. The site font is Open Sans. Ad overlays and the app UI use Inter.
- Trades are SIMULATED. The app UI shows a "Demo mode" chip. Never use the words guaranteed, risk-free, 1000x, or instant riches. Profit figures stay modest and believable, and the demo includes one small red loss.
- Output is 1080×1920, 30 fps, exactly 15.000 s, H.264 + AAC.

## Rendering architecture

- `src/index.html` holds the 1080×1920 stage. `src/main.js` builds the DOM and exposes `window.__ready` (a Promise) and `window.__render(t)` (synchronous, pure function of t in seconds).
- Everything must be deterministic. No CSS transitions or animations, no `Date.now()`, no `Math.random()`, and no requestAnimationFrame-driven state. Every visual is a pure function of the state passed in. For pseudo-randomness, use `rng(seed)` and `noise1()` from `src/lib/engine.js`.
- `scripts/render.mjs` captures frames with Playwright. Each output frame averages 4 sub-frames (180° shutter) to give real motion blur. `scripts/encode.py` blends the sub-frames and muxes the audio.
- Fonts: `src/styles/fonts.css` provides 'Open Sans' (300–800) and 'Inter' (400–800), Latin subset only. Use inline SVG for icons, check marks, and arrows; do not use unicode symbols. `·`, `–`, `−`, `•`, and `…` are fine.
- Tokens: `src/styles/tokens.css` (CSS custom properties). Reuse them rather than inventing new colors.
- Helpers: `src/lib/engine.js` provides clamp, lerp, prog, remap, ease.*, kf, spring, rng, noise1, css, text, h, rectIn, and fmt.
- Snapshot any page with `node scripts/snap.mjs <page> --w W --h H --times a,b,c --out out/snaps --prefix name`, then open the PNGs to look at them. `python3 scripts/contact_sheet.py sheet.png a.png b.png ...` tiles them.

## Component contract: `src/components/site.js` + `src/styles/site.css`

A pixel-faithful vector rebuild of the SOL Sniper landing page hero, matching `assets/source/site-cropped.png` (706×398 capture of a 1920×1080 viewport, scale factor 2.7195).

```js
export function createSite(): {
  el: HTMLElement,              // 1920×1080, position:relative, overflow:hidden, class "site"
  rect(name): {x,y,w,h,cx,cy},  // in site coordinates (1920×1080), unaffected by ancestor transforms
  update(state): void,          // state: { t:number, ctaHover:0..1, ctaPress:0..1 }
}
export function createLogo(opts?: { size?: number }): HTMLElement  // brand lockup (icon + "SOL Sniper"), for the outro
export function createSiteBackground(): HTMLElement                 // the hero background alone (white + soft blobs), any size via CSS (100%/100%)
```

Required rect names: `nav`, `logo`, `logo.icon`, `logo.word`, `nav.features`, `nav.benefits`, `nav.new`, `nav.usecases`, `nav.advantages`, `nav.start`, `headline`, `headline.l1` ("AI"), `headline.l2` ("Memecoin"), `headline.l3` ("Trading."), `subtitle`, `cta`, `dots`.

Fidelity checklist (measured from the screenshot, ×2.7195 to 1920 space):
- Background: white, with a very soft lavender radial blob at the top left (~#F6F5FD at its center) and a pale ice-blue blob at the bottom right (~#F3F8FC). There is also a faint soft grey shade along the very bottom edge.
- Nav: a floating white pill/rounded rectangle about 960×52 at x≈481–1438, y≈11–63, radius about 10, with a soft lavender-grey shadow underneath. Left side: a small gradient icon (pink/violet to sky blue, a pointer or arrow-like mark) and the wordmark "SOL Sniper" in Open Sans Regular about 17px, blue (#5468D4). Right side: links "Features", "Benefits", a "New" badge (lavender pill #F0EEFB with purple text), "Use Cases", "Advantages", "Start", in Open Sans about 12–13px, #555.
- Headline centered, three lines: "AI" / "Memecoin" / "Trading.". Open Sans Bold (700), about 75px, tight line height (~0.98), letter-spacing about −0.02em, with a vertical gradient through the headline block (top #3956A4, middle #6E5DBE, bottom #AC6AD9) using background-clip:text. "Memecoin" is about 362px wide. The block spans roughly y≈407–651 in 1920 space.
- Subtitle, two centered lines: "Begin your Automated Memecoin Sniping Journey today," / "Powered by High-Speed AI.". Open Sans Regular about 17px, #6B6B6B, at y≈673–727.
- CTA: a pill button "Start Sniping" with a vertical gradient (#4159AD to #7A66C8 to #AC6ADF), white Open Sans SemiBold about 16px, about 130×44, centered at y≈781, with a subtle shadow. Hover brightens it slightly and lifts it 1–2px. Press scales it to 0.96 and darkens it slightly.
- Right edge: a vertical white pill (dot navigation) at x≈1814–1858, y≈437–648, containing 5 small black dots (~6px) spaced evenly, with a soft shadow.

## Component contract: `src/components/app.js` + `src/styles/app.css` (+ `src/dev/app-demo.js`)

The SOL Sniper trading terminal: a believable, premium, light-themed desktop web app (1920×1080) in the same brand language as the site. The camera punches into individual panels at 1.4–2.6×, so every panel must look excellent cropped and enlarged. Use crisp 1px borders (#ECECF2), white cards on #F5F6FA, generous radius (14–18px), Inter with tabular numbers (`font-feature-settings: 'tnum'`), and brand gradients only for primary actions and accents. It should look like Linear, Vercel, or Robinhood-level polish, not a crypto-casino dashboard.

Layout (app coordinates):
- Top bar 0–72: brand lockup (icon + "SOL Sniper" in Open Sans, brand blue), tabs (Terminal [active], Positions, Wallet, Settings), right side: amber "Demo mode · simulated" chip, "Solana" connection pill with a green dot, wallet balance "24.80 SOL", avatar.
- Feed panel x 24–584 (w 560), y 96–1056: header "New pairs" with a live pulsing dot, filter chips ("AI score ≥ 80", "Liq ≥ 50 SOL", "Mint revoked"), and column header (Token · Age · Liq · MC · AI). Rows are 84–88px: gradient avatar circle with an initial, `$TICKER` (bold) + name, age, liquidity, market cap, AI-score pill (≥90 green-tinted, 80–89 purple-tinted), and a compact gradient "Snipe" button with a bolt icon.
- Chart panel x 608–1352 (w 744): header with avatar, "$GLINT / SOL", big price, change chip, timeframe tabs (1s 15s 1m 5m 1h; 15s active), and a stat strip (MC, Liq, Holders, Vol 5m). Below that, a candlestick chart (~48 candles) with volume bars, a right-hand price axis, faint grid, a current-price tag, an entry marker (purple "B" badge plus a dashed entry line labelled "Entry"), and a PnL chip on the chart. Under the chart, a compact "Recent trades" tape.
- Right column x 1376–1896 (w 520): the trade panel on top (Buy/Sell segmented control, Amount input "1.00 SOL", presets 0.25 / 0.5 / 1 / 2, Slippage 15%, Priority "Turbo", MEV protection toggle ON, Auto-sell "TP +50% · SL −20%", and a big primary gradient button "Snipe $GLINT" about 64px tall). Positions panel underneath: header "Positions" + total "+2.84 SOL", plus 4 rows (ticker, size, entry, PnL chip). Include exactly one small red row, e.g. −4.1%.
- Toast: a floating card (white, shadow, green check icon) that slides in at the top right of the right column, e.g. "Buy filled · 1.00 SOL → 18.2M GLINT". Use an SVG arrow.

Token cast (fictional): GLINT (hero token), MOCHI, FROGO, ZORP, NOODL, BLIPZ, KOBI, WAFFL, PIPPA, DUNKO.

```js
export function createApp(): {
  el: HTMLElement,              // 1920×1080, position:relative, overflow:hidden, class "app"
  rect(name): {x,y,w,h,cx,cy},  // app coordinates, must reflect current state (e.g. feed rows shifting)
  update(state): void,
}
```

`update(state)` takes a single object (every field optional, with sensible defaults):

```js
{
  t: 0,                         // app clock (s): live-dot pulse, last-candle wiggle, trade tape ticking. Deterministic.
  feed: {
    inserted: 0,                // float ≥ 0. Rows from the INCOMING queue inserted at the top. The fractional part animates
                                // the insert of the next row: height 0→full, slide down, brief lavender flash.
                                // INCOMING queue order: [ZORP, GLINT, NOODL, BLIPZ, KOBI, ...]; 7 older rows are present at inserted=0.
    highlight: null|'GLINT',    // ticker to highlight (lavender row tint + left accent bar), with highlightAmt 0..1
    highlightAmt: 0,
    snipeHover: 0,              // hover amount for the highlighted row's Snipe button
    snipePress: 0,              // press amount (scale .94, darker)
    snipeState: 'idle'|'pending'|'done', // pending: spinner + "Sniping"; done: green "Bought" with check
    scroll: 0,                  // px the list is scrolled (for montage; rows keep streaming)
  },
  chart: {
    reveal: 1,                  // 0..1 portion of candles drawn (last visible candle "forms" smoothly)
    entry: 0,                   // 0..1 entry marker visibility
    pnl: 0,                     // percent shown on the chart PnL chip, e.g. 38.2
    pnlFlash: 0,                // 0..1 green flash on the chip
    price: null,                // optional override of the header price string
  },
  trade: {
    preset: 2,                  // selected preset index (0.25 / 0.5 / 1 / 2) → also sets the Amount field
    presetHover: -1,
    buyHover: 0, buyPress: 0,
    buyState: 'idle'|'pending'|'filled', // pending: spinner "Executing"; filled: green check "Filled"
  },
  positions: {
    pnl: { GLINT: 38.2, MOCHI: 12.6, ZORP: -4.1, FROGO: 61.3 }, // displayed values
    flash: { GLINT: 0 },        // 0..1 per row green/red flash
    tp: 0,                      // 0..1: show a "TP hit · sold" state on FROGO
  },
  toast: { show: 0, text: 'Buy filled · 1.00 SOL', sub: '18.2M GLINT · simulated' }, // show 0..1 = enter progress
}
```

Required rect names: `topbar`, `demo`, `feed`, `feed.header`, `feed.row.<TICKER>`, `feed.snipe.<TICKER>`, `feed.ai.<TICKER>`, `chart`, `chart.plot`, `chart.pnl`, `chart.price`, `chart.entry`, `trade`, `trade.preset.0` … `trade.preset.3`, `trade.amount`, `trade.buy`, `positions`, `positions.row.<TICKER>`, `positions.pnl.<TICKER>`, `toast`, and `logo`.

`src/dev/app-demo.js` must export `demoState(t)`, which walks through every state, for example t=0 at rest, 1 inserting rows, 2 highlight + hover, 3 pending, 4 done + toast, 5 trade filled + PnL flash, 6 TP hit. That lets the author and reviewers snap it.

## Audio contract: `audio/build_audio.py` → `audio/soundtrack.wav`

- Python 3 + numpy (scipy may be pip-installed if needed). Fully synthesized: no samples, no downloads, deterministic (fixed seeds).
- Reads `audio/timing.json` (exported from `src/timing.js` by `node scripts/export-timing.mjs`) for bpm, sections, music markers, and cues. Every SFX lands exactly at its cue `t`. Music lands on the beat grid (t = n × 0.48).
- Output: 48 kHz, 24-bit or 16-bit stereo WAV, exactly 15.000 s (720000 samples). Integrated loudness about −14 LUFS, true peak ≤ −1 dBTP, no clipping, a clean ending (no click), and silence-free start (the impact lands at sample 0).
- Sound palette: premium, expensive tech-commercial. Deep, clean low end; tight transients; tasteful reverb; nothing cheesy, chiptune-like, or "laser". Cue types to implement: `impact_big`, `impact_drop`, `impact_outro`, `hit_cut`, `whoosh_fast`, `whoosh_long` (dur), `whoosh_rise`, `zoom_through` (dur), `riser` (dur, ends AT t), `reverse_swell` (dur, ends AT t), `click`, `tap_soft`, `ui_blip`, `success`, `toast`, `tick`, `text_reveal`. Cue fields: `gain` (dB offset), `pan` (−1..1, applies to every cue type), `dur`, and optional `dir` (±1) for which way a whoosh sweeps across the stereo field. When `dir` is not given, the sweep follows the sign of `pan`.
- Music: built to picture, following `music.markers` (125 BPM, F minor). Modern minimal cinematic electronic: punchy kick, sub bass, crisp hats, claps, filtered plucks and chord stabs, pads, sidechain ducking. Energy curve: intro (no drums) → groove → build with pre-drop gap → full drop at 6.24 → intensified montage → short break → wide warm outro chord that rings out.
- Also writes `audio/stems/music.wav` and `audio/stems/sfx.wav` for inspection, plus `audio/analysis.txt` (LUFS, peak, onset times of detected transients vs. cue times).
