// 5-second hook on the client's real cash footage, placed BEFORE the unchanged 15 s reel (it replaces the
// phone-photo hook). Every cut and punch sits on the 125 BPM grid counted back from the cut into the reel
// at 5.00 (timing.js G), where the reel opens with its own impact on its dark title frame.
//
//  0.00-1.63  the notes fanned in the hand, from the first frame, on the opening hit; "Wait…" punches in
//             with it and "is this legal?" on the next accent
//  1.63-2.60  punch-in cut; the move to the box with a slight speed ramp; the lid flies off and the box
//             is fully open on the 2.60 beat
//  2.60-4.03  zoom-out reveal of the box in slow motion, punch-in cut at 3.07 as the notes pour in at
//             real speed; heartbeat punches
//  4.03-4.53  punch-in cut: the hand brings the next bundle
//  4.53-5.00  the hand pushes the bundle down into the box and the camera follows it, accelerating into a
//             downward whip (mirrored edges, motion blur on the last ~5 frames) that dives into the shadow
//             of the box: hard cut on the beat into the reel's dark title frame and its impact
//
// Render contract (scripts/render.mjs --page src/cash/index.html --timing src/cash/timing.js):
//   window.__ready (Promise), window.__render(t) -> Promise (the plate frame is decoded before capture).
import { lerp, prog, ease, css, h } from '../lib/engine.js';
import { FPS, DURATION, G, CUT1, REVEAL, CUT2, CUT3, FOLLOW } from './timing.js';

const PLATE = '../../out/cash/plate/';
const PLATE_FRAMES = 150;
const LINE2 = 0.6; // "is this legal?" (accent cue)

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
    S = lerp(1.04, 1.08, ease.inOutSine(prog(t, 0, CUT1)));
    S *= 1 + 0.075 * (1 - ease.outCubic(prog(t, 0, 0.5)));          // the opening hit settles
    S *= 1 + punch(t, LINE2, 0.035);
    fy = 960 + 30 * prog(t, 0, CUT1);
  } else if (t < REVEAL) {
    S = lerp(1.12, 1.15, prog(t, CUT1, REVEAL)) * (1 + punch(t, G(6), 0.03));
    fy = 980;
  } else if (t < CUT2) {
    const r = ease.outCubic(prog(t, REVEAL, REVEAL + 0.62));         // zoom-out reveal of the box
    S = lerp(1.24, 1.07, r) * lerp(1, 1.025, ease.inOutSine(prog(t, REVEAL + 0.62, CUT2)));
    fx = 560; fy = 820;
  } else if (t < CUT3) {
    S = lerp(1.13, 1.16, ease.inOutSine(prog(t, CUT2, CUT3))) * (1 + punch(t, G(3), 0.035));
    fx = 560; fy = 860;
  } else {
    S = lerp(1.17, 1.19, ease.inOutSine(prog(t, CUT3, FOLLOW))) * (1 + punch(t, FOLLOW, 0.03));
    fx = 560; fy = 900;
    // the hand's push carries on as the whip: the frame accelerates downward, slightly left like the hand
    const p = prog(t, FOLLOW, DURATION);
    S *= lerp(1, 1.05, ease.inQuad(p));
    dy = 2200 * Math.pow(p, 4);
    dx = -60 * p * p;
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
stage.append(cam, vignette, shade, hook);

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

  // ---- type: "Wait…" alone and centred, then "is this legal?" joins on the next accent
  if (!hook.__h) { hook.__h = hook.offsetHeight; hook.__h2 = lines[1].offsetHeight; }
  const exit = ease.inQuad(prog(t, REVEAL - 0.135, REVEAL));
  const cy = 520 + (hook.__h2 / 2) * (1 - ease.outCubic(prog(t, LINE2, LINE2 + 0.2)));
  const sc = (1 + punch(t, CUT1, 0.035) + punch(t, G(6), 0.03)) * (1 + 0.08 * exit);
  css(hook, 'transform', `translate3d(0, ${(cy - (hook.__h * sc) / 2).toFixed(2)}px, 0) scale(${sc.toFixed(4)})`);
  css(hook, 'opacity', t >= REVEAL ? '0' : (1 - exit).toFixed(3));
  css(hook, 'filter', exit > 0.01 ? `blur(${(exit * 10).toFixed(2)}px)` : 'none');
  css(shade, 'opacity', t >= REVEAL ? '0' : (1 - exit).toFixed(3));
  [0, LINE2].forEach((t0, i) => {
    const pin = ease.outCubic(prog(t, t0, t0 + 0.3));
    const b = lerp(7, 0, ease.outCubic(prog(t, t0, t0 + 0.18)));
    css(lines[i], 'opacity', t >= t0 ? '1' : '0'); // full on the accent frame
    css(lines[i], 'transform', `scale(${lerp(1.14, 1, pin).toFixed(4)})`);
    css(lines[i], 'filter', b > 0.05 && t >= t0 ? `blur(${b.toFixed(2)}px)` : 'none');
  });

  // ---- exposure bridge: the whip dives into the shadow of the box, toward the reel's dark title frame
  const ex = ease.inQuad(prog(t, 4.78, DURATION));
  css(cam, 'filter', `contrast(1.05) saturate(1.06) brightness(${(1 - 0.5 * ex).toFixed(4)})`);

  // ---- the footage frame for this output frame (frame-locked across motion-blur sub-samples)
  return showPlate(Math.min(PLATE_FRAMES - 1, Math.floor(t * FPS + 1e-6)));
}

window.__duration = DURATION;
window.__render = (t) => render(Math.max(0, Math.min(DURATION - 1e-6, t)))
  .then(() => new Promise((r) => requestAnimationFrame(() => r())));
window.__ready = document.fonts.ready.then(() => window.__render(0));

const q = new URLSearchParams(location.search);
if (q.has('t')) window.__ready.then(() => window.__render(Number(q.get('t'))));
