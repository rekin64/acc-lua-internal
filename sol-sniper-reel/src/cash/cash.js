// 5-second opening on the client's real cash footage. Replaces reel 0.00-5.00; the reel continues
// unchanged from its frame 150 (the "Sniping" button press).
//
//  0.00-1.43  the notes fanned in the hand; "Wait…" / "is this legal?" punch in on the accents,
//             subtle punch-ins on the beats
//  1.43-2.40  punch-in cut; the move to the box with a speed ramp (plate retime, see scripts/cash_plate.py)
//  2.40-3.83  the lid comes off on the hit: zoom-out reveal of the box in slow motion, then real speed
//             as the notes go in; punch-ins on the beats
//  3.83-4.60  punch-in cut on the groove's downbeat; the hand lifts the next bundle
//  4.60-5.00  the hand pushes the bundle down into the box and the frame carries that movement on:
//             a downward whip (mirrored edges, ~5 frames of heavy motion blur), hard cut on the impact
//             at 5.00 into the cursor pressing "Sniping"
//
// Render contract (scripts/render.mjs --page src/cash/index.html --timing src/cash/timing.js):
//   window.__ready (Promise), window.__render(t) -> Promise (the plate frame is decoded before capture).
import { lerp, prog, ease, css, h } from '../lib/engine.js';
import { FPS, DURATION, B } from './timing.js';

const PLATE = '../../out/cash/plate/';
const PLATE_FRAMES = 150;
const CUT1 = B(3), CUT2 = B(5), CUT3 = B(8); // 1.433, 2.400, 3.833: punch-in cuts on the beat
const FOLLOW = 4.6;                          // camera starts following the push, whip peaks on the cut

/** Beat punch-in: a 1.5-frame push in, then an eased release. */
function punch(t, t0, amt, rel = 0.42) {
  const u = t - t0;
  if (u < 0) return 0;
  const att = 0.045;
  return amt * (u < att ? ease.outQuad(u / att) : 1 - ease.inOutSine(prog(u, att, att + rel)));
}

/** Virtual camera: scale S around the source point (fx, fy) at frame centre, plus a whip offset. */
function camera(t) {
  let S, fx = 540, fy = 960, dx = 0, dy = 0;
  if (t < CUT1) {
    S = lerp(1.04, 1.075, ease.inOutSine(prog(t, 0, CUT1)));
    S *= 1 + 0.075 * (1 - ease.outCubic(prog(t, 0, 0.5)));          // the opening hit settles
    S *= 1 + punch(t, B(1), 0.035) + punch(t, B(2), 0.025);
    fy = 960 + 30 * prog(t, 0, CUT1);
  } else if (t < CUT2) {
    S = lerp(1.12, 1.15, prog(t, CUT1, CUT2)) * (1 + punch(t, B(4), 0.03));
    fy = 980;
  } else if (t < CUT3) {
    const r = ease.outCubic(prog(t, CUT2, CUT2 + 0.62));             // zoom-out reveal of the box
    S = lerp(1.24, 1.07, r) * lerp(1, 1.035, ease.inOutSine(prog(t, CUT2 + 0.62, CUT3)));
    S *= 1 + punch(t, B(6), 0.03) + punch(t, B(7), 0.035);
    fx = 560; fy = 820;
  } else {
    S = lerp(1.16, 1.19, ease.inOutSine(prog(t, CUT3, FOLLOW))) * (1 + punch(t, B(9), 0.035));
    fx = 560; fy = 900;
    // the hand's push carries on as the whip: the frame accelerates downward, slightly left like the hand
    const p = prog(t, FOLLOW, DURATION);
    S *= lerp(1, 1.06, ease.inQuad(p));
    dy = 3000 * Math.pow(p, 4);
    dx = -70 * p * p;
  }
  // keep the frame covered by the footage (the whip offset is covered by the mirrored tiles)
  const tx = Math.min(0, Math.max(1080 - 1080 * S, 540 - fx * S));
  const ty = Math.min(0, Math.max(1920 - 1920 * S, 960 - fy * S));
  return { S, x: tx + dx, y: ty + dy };
}

const stage = document.getElementById('stage');
const cam = h(`<div class="cam"><img class="t0"><img class="t1"><img class="t2"></div>`);
const tiles = [...cam.querySelectorAll('img')];
const vignette = h(`<div class="vignette"></div>`);
const shade = h(`<div class="topshade"></div>`);
const hook = h(`<div class="hook"><span class="ln">Wait…</span><span class="ln">is this legal?</span></div>`);
const lines = [...hook.querySelectorAll('.ln')];
const lift = h(`<div class="lift"></div>`);
stage.append(cam, vignette, shade, hook, lift);

// plate frames: fetched once per output frame, shared by the three tiles via a blob URL
let shown = -1, blobUrl = null;
async function showPlate(k) {
  if (k === shown) return;
  const res = await fetch(`${PLATE}p_${String(k).padStart(4, '0')}.jpg`);
  if (!res.ok) throw new Error(`missing plate frame ${k}`);
  const url = URL.createObjectURL(await res.blob());
  tiles.forEach((img) => { img.src = url; });
  await Promise.all(tiles.map((img) => img.decode()));
  if (blobUrl) URL.revokeObjectURL(blobUrl);
  blobUrl = url; shown = k;
}

function render(t) {
  // ---- camera
  const c = camera(t);
  css(cam, 'transform', `translate(${c.x.toFixed(2)}px, ${c.y.toFixed(2)}px) scale(${c.S.toFixed(5)})`);
  css(vignette, 'opacity', (1 - ease.inQuad(prog(t, 4.7, DURATION))).toFixed(3));

  // ---- type: "Wait…" alone and centred, then "is this legal?" joins on the next accent
  if (!hook.__h) { hook.__h = hook.offsetHeight; hook.__h2 = lines[1].offsetHeight; }
  const exit = ease.inQuad(prog(t, CUT2 - 0.135, CUT2));
  let cy = 520 + (hook.__h2 / 2) * (1 - ease.outCubic(prog(t, B(1), B(1) + 0.2)));
  const sc = (1 + punch(t, B(2), 0.03) + punch(t, CUT1, 0.035) + punch(t, B(4), 0.03)) * (1 + 0.08 * exit);
  css(hook, 'transform', `translate3d(0, ${(cy - (hook.__h * sc) / 2).toFixed(2)}px, 0) scale(${sc.toFixed(4)})`);
  css(hook, 'opacity', t >= CUT2 ? '0' : (1 - exit).toFixed(3));
  css(hook, 'filter', exit > 0.01 ? `blur(${(exit * 10).toFixed(2)}px)` : 'none');
  css(shade, 'opacity', t >= CUT2 ? '0' : (1 - exit).toFixed(3));
  [0, B(1)].forEach((t0, i) => {
    const pin = ease.outCubic(prog(t, t0, t0 + 0.3));
    const b = lerp(7, 0, ease.outCubic(prog(t, t0, t0 + 0.18)));
    css(lines[i], 'opacity', t >= t0 ? '1' : '0'); // full on the accent frame
    css(lines[i], 'transform', `scale(${lerp(1.14, 1, pin).toFixed(4)})`);
    css(lines[i], 'filter', b > 0.05 && t >= t0 ? `blur(${b.toFixed(2)}px)` : 'none');
  });

  // ---- exposure bridge: the last frames of the whip open up about a stop toward the light interface
  const ex = ease.inQuad(prog(t, 4.85, DURATION));
  css(cam, 'filter', `contrast(1.05) saturate(1.06) brightness(${(1 + 0.38 * ex).toFixed(4)})`);
  css(lift, 'opacity', (0.1 * ex).toFixed(3));

  // ---- the footage frame for this output frame (frame-locked across motion-blur sub-samples)
  return showPlate(Math.min(PLATE_FRAMES - 1, Math.floor(t * FPS + 1e-6)));
}

window.__duration = DURATION;
window.__render = (t) => render(Math.max(0, Math.min(DURATION - 1e-6, t)))
  .then(() => new Promise((r) => requestAnimationFrame(() => r())));
window.__ready = document.fonts.ready.then(() => window.__render(0));

const q = new URLSearchParams(location.search);
if (q.has('t')) window.__ready.then(() => window.__render(Number(q.get('t'))));
