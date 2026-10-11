# SOL Sniper: brand assets

## The idea

An **S** made from one ring split into two hooks. Each hook turns into a short horizontal stub, and the two stubs close in on a **coin** at the centre: the moment a new token is spotted and locked onto.
Describe it as "S + lock-on (coin)". Never call it a scope or a reticle (see *Positioning* below).

## Construction (64-unit grid, centre 32/32)

| Part | Master (`logo-mark*`, 48 px and up) | Small masters (`favicon-16/32`, `logo-horizontal-small`) |
|---|---|---|
| Ring | outer r 28, inner r 20 (stroke 8) | same |
| Stubs | band y 28.25 to 35.75 (7.5, optically equal to the curved 8), ends x 23 / 41 | band y 28 to 36 (8), ends x 24 / 40 |
| Coin | r 4.5 (1.125 × stroke), gaps 4.5 | r 4 (= stroke), gaps 4 |
| Terminals | radial cuts at 36° | 36.87° (3-4-5 triangle, inner end on grid point 48/20) |

The narrowest part of each opening equals the stroke (8), so stroke, opening, coin and gaps all come from one module. The mark has 180° rotational symmetry.
The favicon-16 master is pixel-hinted: 2 px ring, 2 px spine on rows 7 and 8, 1 px gaps, a 2 × 2 coin, and terminals cut flat on a pixel edge. The favicon-32 master has 4 px bars, 2 px gaps and a 4 px coin.

## Colour

| Token | Hex | Use |
|---|---|---|
| Blue | `#3956A4` | gradient top, "SOL" in the colour lockup |
| Violet | `#6E5DBE` | gradient middle (52 %), small-size end stop |
| Lilac | `#AC6AD9` | gradient bottom, 48 px and up only |
| Indigo | `#5A56BD` | flat brand colour when a gradient is not possible |
| Ice | `#8FA2F5` | dark-ground gradient top |
| Orchid | `#C77DFF` | dark-ground gradient bottom |
| Ink | `#15161C` | "Sniper", one-colour version |
| White | `#FFFFFF` | reversed version |
| Dark ground | `#0E0F14` | reference dark background |

- **48 px and up, light grounds:** vertical gradient Blue → Violet (52 %) → Lilac, which is the site's headline gradient.
- **32 px and below:** two stops, Blue → Violet, or flat Indigo. Lilac is only about 3.3:1 on white.
- **Dark grounds:** Ice → Orchid (`*-dark`, `logo-horizontal-white`, `logo-stacked-white`), or plain white. Blue is too dark on `#0E0F14`.
- **App icon:** white mark on a 45° Blue → Violet → Lilac tile.

## Typography

The wordmark is outlined Inter (SIL OFL), with "SOL" and "Sniper" set as two separate words:

- **SOL:** Inter ExtraBold 800, +0.012 em. Its stem is close to the ring stroke, so the mark and "SOL" carry the weight.
- **Sniper:** Inter Medium 500, −0.012 em. The tittle on the i is redrawn as a true circle, echoing the coin.
- **Colour split:** in the colour lockup "SOL" is Blue and "Sniper" is Ink. One-colour versions separate the words by weight alone.
- **Lockup:** the mark is 1.8 × cap height. Caps are centred on the stub axis. The mark-to-text gap is 0.56 cap, and the gap from L to S is 0.37 cap.

For running text, keep using Inter / Open Sans as live fonts. Do not retype the logo.

## Clear space and minimum sizes

**X = the ring stroke = 1/7 of the mark's height.** Keep at least **2X** clear on every side of the mark and of every lockup. For a lockup, X = lockup height / 7.

| Asset | Minimum (screen) | Minimum (print) | Notes |
|---|---|---|---|
| Mark | 16 px | 5 mm | 16 to 23 px: `favicon-16*`. 24 to 47 px: `favicon-32*`. 48 px and up: `logo-mark*` |
| Horizontal lockup | 20 px tall (≈105 px wide) | 6 mm tall | 32 px tall or less: `logo-horizontal-small.svg`, which is pixel-exact at 28 px tall |
| Stacked lockup | 72 px wide | 15 mm wide | |
| App icon | n/a | n/a | Let the OS mask it. Never pre-round it for the stores |

## Do

- Use the supplied files as they are, scaled proportionally.
- Use the colour version on white or very light grounds, the `-dark` / `-white` versions on dark grounds, and the ink or white version wherever only one colour is possible.
- For browser tabs, use `favicon.svg`, which switches to the dark-ground colours in dark UI. Keep the PNG and ICO files as fallbacks:

  ```html
  <link rel="icon" href="/favicon.ico" sizes="48x48">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="/apple-touch-icon-180.png">
  ```

## Don't

- Stretch, skew, rotate or redraw the mark. Do not change the spacing or proportions of the lockup.
- Recolour outside this palette, put the gradient on the wordmark, or use Lilac on marks smaller than 48 px.
- Add effects: shadows, glows, outlines, bevels, 3D or textures.
- Place the mark inside a circle or badge, or use a red/white two-tone fill, which reads as a Pokéball.
- Enlarge the coin.
- Add a vertical hair, tick marks, a vignette or crosshair overlays. Do not pair the mark with weapons imagery.
- Put the colour version on busy photos or mid-tone grounds. Use white on a dark overlay instead.

## Positioning

- In copy, ads and store listings, call the mark "S + lock-on" or "the coin". Never call it a scope, crosshair or reticle. This keeps the brand clear of weapons readings under ad and app-store policies.
- Before launch, run a trademark clearance on circle-S monograms and on ring + horizontal band + centre dot marks (USPTO, EUIPO, WIPO; Nice classes 9, 36 and 42). Include the Pokéball and Solana-ecosystem circle marks in the comparison.

## Files

| File | What it is |
|---|---|
| `logo-mark.svg` | Mark, full colour, light grounds |
| `logo-mark-dark.svg` | Mark, Ice → Orchid, dark grounds |
| `logo-mark-ink.svg` / `logo-mark-white.svg` | Mark in one colour, `#15161C` / `#FFFFFF` |
| `logo-horizontal.svg` | Mark + wordmark, colour, light grounds |
| `logo-horizontal-white.svg` | Dark grounds: dark-ground mark + white wordmark |
| `logo-horizontal-ink.svg` / `logo-horizontal-white-mono.svg` | Lockup in one colour |
| `logo-horizontal-small.svg` | Lockup for 32 px tall and below (nav bars), small-master mark, 2-stop gradient |
| `logo-stacked.svg`, `-white`, `-ink` | Mark centred above the wordmark |
| `app-icon.svg` | 1024 × 1024 full-bleed tile, iOS and Android (the OS applies the mask) |
| `app-icon-android-foreground.svg` / `-background.svg` | Android adaptive-icon layers (108 dp, mark inside the 66 dp safe zone) |
| `favicon-16*.svg`, `favicon-32*.svg` | Pixel-hinted small masters: colour, `-ink`, `-white`, `-dark` |
| `favicon.svg` | Adaptive SVG favicon, light/dark UI |
| `favicon.ico` | 16 + 32 (hinted) + 48 |
| `png/logo-mark-1024.png`, `png/logo-mark-dark-1024.png` | Mark, transparent |
| `png/logo-horizontal-2400w.png`, `png/logo-horizontal-white-2400w.png` | Lockups, transparent |
| `png/logo-stacked-1200w.png` | Stacked lockup, transparent |
| `png/app-icon-1024.png`, `png/app-icon-512.png` | App Store / Play Store icon, opaque, no alpha |
| `png/apple-touch-icon-180.png` | iOS home-screen web icon |
| `png/app-icon-android-foreground-432.png`, `png/app-icon-android-background-432.png` | Adaptive layers at xxxhdpi |
| `png/favicon-32.png`, `png/favicon-16.png` | Hinted favicons, transparent |
| `png/og-image-1200x630.png` | Social share image |
