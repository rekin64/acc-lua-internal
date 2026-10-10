# SOL Sniper: 15-second product-demo reel

A vertical 1080×1920 reel for Instagram Reels and TikTok, exactly 15.0 s long at 30 fps (H.264 + AAC). It is built like a real product-demo edit: the SOL Sniper landing page and trading terminal are rebuilt as crisp vector UI, then "filmed" with a virtual camera. That camera does punch-ins, whip pans, and speed ramps, with real motion blur, while a cursor clicks through a trade. The soundtrack and sound design are synthesized and cut to the same 125 BPM grid as the picture.

**Final video:** `dist/sol-sniper-reel.mp4`

## Storyboard (as cut)

| Time | Section | What happens | Super |
|---|---|---|---|
| 0.00–1.43 | Title | Impact on black; type masks in; "REDEFINED." turns brand-colored on the beat | MEMECOIN SNIPING. REDEFINED. |
| 1.43–4.00 | Site reveal | The landing page rises as a card, the camera pushes onto the logo, glides to the hero, and the cursor clicks **Start Sniping** | Built for speed. |
| 4.00–6.23 | Demo | Zoom-through the button into the app. A new pair is detected (AI score 94), sniped from the feed, and filled | Spot. Snipe. React. |
| 6.23–9.60 | Drop | Whip pan to the live chart (entry marker, PnL), a second entry in the trade panel (Executing, then Filled), positions update, take-profit hits at +50%, then a pull-out to the full terminal | Fast entries. Clean execution. |
| 9.60–12.47 | Montage | One cut per beat, then half-beats: headline, CTA press, feed streaming, PnL, candles, Filled, AI score, logo | n/a |
| 12.47–15.00 | Outro | Match-cut on the logo, the **Start Sniping** CTA springs in, final click | SOL Sniper / Start Sniping |

All trading moments are presented as a **simulated demo**. The app shows a "Demo mode · simulated" chip, a "Simulated demo" label stays on screen during trade footage, and the end card carries a short disclaimer. Positions include a small loss, so the demo reads as honest rather than as promised returns.

## How it's built

```
src/
  index.html, main.js     1080×1920 stage; render contract: window.__ready + window.__render(t)
  timing.js               single source of truth: 125 BPM grid, sections, sound cues (frame-snapped)
  timeline.js             the edit: shots, camera dollies, cursor paths, supers, transitions
  components/site.js      vector rebuild of the landing-page hero (from assets/source/)
  components/app.js       the SOL Sniper trading terminal UI (state-driven)
  components/brand.js     logo mark + wordmark lockup
  components/cursor.js    screen-recording cursor with click ring
  lib/engine.js           easing, keyframes, springs, seeded RNG: everything is a pure function of time
audio/build_audio.py      synthesized music + sound design → audio/soundtrack.wav
scripts/render.mjs        Playwright frame capture (4 sub-frames per frame, 180° shutter)
scripts/encode.py         linear-light sub-frame blend (motion blur) + dither → ffmpeg H.264/AAC
assets/source/            your original screenshot (and the cropped site region)
```

Everything is deterministic, so any frame can be rendered at any time, in any order, on any number of workers.

## Commands

Requires Node 18+, Python 3 with numpy and Pillow (scipy for audio), ffmpeg, and Playwright Chromium.

```bash
npm install
npm run render            # audio → frames → dist/sol-sniper-reel.mp4  (≈ 5–10 min on 4 cores)

# individual steps
node scripts/export-timing.mjs && python3 audio/build_audio.py   # soundtrack
node scripts/render.mjs --workers 4 --samples 4                    # frames → out/frames
python3 scripts/encode.py --crf 16                                 # → dist/sol-sniper-reel.mp4

# preview in a browser (plays with the soundtrack, space = pause, click = restart)
node scripts/server.mjs 5173   # then open http://127.0.0.1:5173/src/index.html?play
# single frame
node scripts/snap.mjs src/index.html --times 6.3 --out out/snaps
```

## Editing

- **Copy and numbers:** the supers are in `src/timeline.js` (`makeSuper(...)`). Demo numbers live in `appState()` / `baseApp()` there and in `src/components/app.js`.
- **Timing:** move a beat in `src/timing.js` or `timeline.js`, then re-run the audio and the render. The cues in `timing.js` keep the sound in sync with the picture.
- **Logo:** the mark is a vector redraw of the ~10 px icon in the screenshot. To use your official artwork, replace the SVG in `src/components/brand.js` and re-render.
- **Fonts:** Open Sans (matches the site) and Inter are bundled in `assets/fonts` (SIL OFL).
