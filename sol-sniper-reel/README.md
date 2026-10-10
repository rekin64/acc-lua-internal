# SOL Sniper: 15-second product-demo reel

A vertical 1080×1920 reel for Instagram Reels and TikTok, exactly 15.0 s long at 30 fps (H.264 + AAC). It is built like a real product-demo edit: the SOL Sniper landing page and trading terminal are rebuilt as crisp vector UI, then "filmed" with a virtual camera. That camera does punch-ins, whip pans, and speed ramps, with real motion blur, while a cursor clicks through a trade. The soundtrack and sound design are synthesized and cut to the same 125 BPM grid as the picture.

**Final videos:**
- `dist/sol-sniper-reel-cash-intro.mp4` (20.0 s): a 5 s "Wait… is this legal?" hook cut from the client's real cash footage, followed by the complete, unchanged 15 s reel (see below)
- `dist/sol-sniper-reel-with-intro.mp4` (20.0 s): the earlier 5 s phone-photo hook followed by the unchanged reel
- `dist/sol-sniper-reel.mp4` (15.0 s): the reel on its own

## Storyboard (as cut)

| Time | Section | What happens | Super |
|---|---|---|---|
| 0.00–1.43 | Title | Impact; type masks in over a dark, defocused live terminal; "REDEFINED." turns brand-colored on the beat | MEMECOIN SNIPING. REDEFINED. |
| 1.43–4.00 | Site reveal | Hard cut to light: the landing page rises as a card, the camera pushes onto the logo, glides to the hero, and the cursor clicks **Start Sniping**. The camera zooms through the button | Built for speed. |
| 4.00–6.23 | Demo | In the app, a new pair streams in and the camera punches onto AI score 94. Snipe, then Sniping, then Bought; a "Buy filled" notification follows. The camera settles on the GLINT row through the pre-drop gap | Spot. Snipe. React. |
| 6.23–9.60 | Drop | A whip pan lands on the chart on the drop (launch, then entry, then climb; Sim PnL ≈ +12%). The camera follows the cursor through a second buy (0.5 SOL, Executing, then Filled). Positions update and FROGO's take-profit hits at +30%. Then a pull-out to the full terminal | Fast entries. Clean execution. |
| 9.60–12.47 | Montage | One cut per beat, then half-beats: headline, CTA press, new pairs streaming, PnL column, chart, Filled, AI 94 + Bought, logo push | n/a |
| 12.47–15.00 | Outro | Match-cut on the logo, which glides up into the site hero rebuilt as an end card ("AI Memecoin Trading."). The **Start Sniping** CTA springs in and gets a final click | SOL Sniper / Start Sniping |

All trading moments are presented as a **simulated demo**:
- The app shows a "Demo mode · simulated" chip, and PnL figures are labelled "Sim PnL" and "Total PnL · sim".
- A "Simulated demo" label is on screen throughout the trade footage.
- The end card carries the disclaimer "Simulated demo trades. Not financial advice. Crypto trading is high risk."

Returns are kept modest: GLINT is about +10–13%, MOCHI +8%, and one loss is shown (ZORP −4.1%). The take-profit at +30% matches the app's Auto-sell setting (TP +30% · SL −15%). A sniper's chart starts at the token's launch (15 s candles), and the whip on the drop reads as a time jump.

**Before running it as a paid ad:** Meta's crypto-advertising policy applies to the advertiser. Repeat the disclaimer in the post caption.

## Intro hook (5 s, prepended)

| Time | What happens |
|---|---|
| 0.00–0.40 | Black, deep bass hit, tension starts |
| 0.40 / 0.80 | "Wait..." then "is this legal?" punch in on the sound accents (centred, Inter ExtraBold, soft glow) |
| 1.20–2.80 | The phone from the client photo rises out of the dark and the type glides up above it; slow cinematic push-in |
| 2.80–4.20 | One continuous speed ramp with subtle parallax (phone vs. dashboard), a fine light sweep and a green glow on the profit figures on the heartbeat pulses |
| 4.20–5.00 | The type flies past the camera; the push lands on "$815,122.73" exactly where the reel's "MEMECOIN" title appears, then a hard cut on the beat into the reel's opening impact (match cut) |

- **Plates:** `scripts/intro_plates.py` splits the photo (`assets/source/intro-reference.png`) into layers, removing its burned-in text and the iOS bar on the way. The layers are a background, a cut-out phone, a screen bloom and a profit glow, saved in `assets/intro/`.
- **Scene:** the hook itself is `src/intro/` (`intro.js`, `intro.css`, `timing.js`).
- **Sound:** `audio/build_intro.py` (with `sndkit/intro_fx.py`) synthesizes the hook's sound design. It writes `audio/intro.wav` and `audio/soundtrack_with_intro.wav`; the reel's 15 s soundtrack is copied in bit for bit.

```bash
python3 -I scripts/intro_plates.py && python3 audio/build_intro.py
node scripts/render.mjs --page src/intro/index.html --timing src/intro/timing.js --out out/intro_frames
python3 scripts/encode.py --frames out/intro_frames,out/frames --audio audio/soundtrack_with_intro.wav --out dist/sol-sniper-reel-with-intro.mp4
```

## Cash-footage hook (5 s, before the reel)

`dist/sol-sniper-reel-cash-intro.mp4` is exactly 20.00 s: the 5 s hook, then the whole 15 s reel from its first frame. The hook replaces the phone-photo hook of `dist/sol-sniper-reel-with-intro.mp4`. Everything from 5.00 is the reel as delivered: its 450 rendered frames, its soundtrack bit for bit, and its "Simulated demo" labels. The hook is cut from the client's own footage (`assets/source/cash-footage.mp4`, real euro notes put into a shoe box). Every cut and punch sits on the reel's 125 BPM grid, counted back from 5.00.

| Time | What happens |
|---|---|
| 0.00–1.63 | The notes fanned in the hand, from the very first frame, on the opening hit. "Wait…" punches in with the hit and "is this legal?" on the next accent |
| 1.63–2.60 | Punch-in cut; the move to the box with a slight speed ramp. The lid flies off and the box is fully open on the 2.60 beat |
| 2.60–4.03 | Zoom-out reveal of the box in slow motion, then a punch-in cut at 3.07 as the notes pour in at real speed; heartbeat punches |
| 4.03–4.73 | Punch-in cut; slow motion as the hand lifts the next bundle (heartbeat punch at 4.53) |
| 4.73–5.00 | Real speed: the hand pushes the bundle down into the box and the camera follows the push, tilting down and diving in (motion blur with a 360° shutter on the last frames) into the shadow of the box. Hard cut on the beat into the reel's dark title frame, whose type rises the same way, and its opening impact |

- **Footage:** `scripts/cash_frames.py` extracts the clip with the correct BT.709 colours. `scripts/cash_plate.py` retimes it into the 150-frame plate: the speed ramps, with in-between frames synthesized by optical flow (occlusion-aware, no double exposures). It also tracks the third-party logo on the shoe-box lid and blurs it into the lid.
- **Scene:** `src/cash/` (`cash.js`, `cash.css`, `timing.js`).
- **Sound:** `audio/build_intro.py` builds it from `audio/cash_intro_timing.json` (exported from `src/cash/timing.js`), with the same palette as the phone hook: a bass hit, the tension bed, text accents, heartbeat pulses on the cuts, whooshes on the moves, and a riser plus a suck that stop dead on the cut. It writes `audio/cash_intro/intro.wav` and `audio/cash_intro/soundtrack_with_intro.wav`. The reel's soundtrack follows bit for bit, so its own impact at 5.00 lands on the cut.
- **Claims:** the hook adds no figures or claims. The footage is not presented as SOL Sniper results.

```bash
python3 scripts/cash_frames.py && python3 scripts/cash_plate.py
node scripts/export-cash-timing.mjs && python3 audio/build_intro.py --timing audio/cash_intro_timing.json --out audio/cash_intro
node scripts/render.mjs --page src/cash/index.html --timing src/cash/timing.js --fast-samples 64 --out out/cash_frames
python3 scripts/encode.py --frames out/cash_frames,out/frames --audio audio/cash_intro/soundtrack_with_intro.wav --out dist/sol-sniper-reel-cash-intro.mp4
```

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

Everything is deterministic, so any frame can be rendered at any time, in any order, on any number of workers. Product UI state is frame-locked: numbers, rows and buttons hold constant across a frame's motion-blur sub-samples and tick at 7.5 Hz, like a real screen capture. Only the camera, the cursor and the editor's typography move continuously, so only they get motion blur.

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
