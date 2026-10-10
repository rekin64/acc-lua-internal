// 5-second hook in front of the main reel (built from the client's phone photo).
//
//  0.00–0.40  black, bass hit
//  0.40–1.30  "Wait..." / "is this legal?" punch in, centered
//  1.30–2.80  the phone rises out of the dark, cinematic push-in, type glides up
//  2.80–4.20  speed ramp builds, parallax between phone and dashboard, profit figures glow on the pulses
//  4.20–5.00  accelerating zoom into the balance on the screen, hard cut on the beat into the reel
//
// Render contract (scripts/render.mjs --page src/intro/index.html --timing src/intro/timing.js):
//   window.__ready (Promise), window.__render(t) synchronous, pure function of t.
import { clamp, lerp, prog, ease, css, h } from '../lib/engine.js';
import { FPS, DURATION, CUES } from './timing.js';

const CX = 540, CY = 960;
const Z0 = 1080 / 1206;            // photo width fills the frame
const A = '../../assets/intro/';
const F0 = { x: 603, y: 1249 };    // the reference composition (phone below the type)
const F1 = { x: 588, y: 1262 };    // after the slow push
const TARGET = { x: 334, y: 1222 }; // "$815,122.73" + "+$2,600.03" on the screen
const PULSES = CUES.filter((c) => c.type === 'pulse').map((c) => c.t);
const fl = (t) => Math.floor(t * FPS + 1e-6) / FPS;

function camT(c, dx = 0, dy = 0) {
  return `translate(${(CX + dx).toFixed(2)}px, ${(CY + dy).toFixed(2)}px) scale(${c.z.toFixed(5)}) translate(${(-c.x).toFixed(3)}px, ${(-c.y).toFixed(3)}px)`;
}
/** Log-zoom dolly toward b; b's focal point travels in a straight line on screen. */
function dolly(p, a, b) {
  const z = Math.exp(lerp(Math.log(a.z), Math.log(b.z), p));
  const sx = lerp((b.x - a.x) * a.z, 0, p), sy = lerp((b.y - a.y) * a.z, 0, p);
  return { x: b.x - sx / z, y: b.y - sy / z, z };
}
function camera(t) {
  if (t < 2.8) {
    const p = ease.outSine(prog(t, 1.3, 2.8));
    return dolly(p, { ...F0, z: Z0 * 0.98 }, { ...F1, z: Z0 * 1.08 });
  }
  // one accelerating move from the composition into the screen: slow start, speed ramp, plunge
  const p = Math.pow(prog(t, 2.8, DURATION), 5);
  return dolly(p, { ...F1, z: Z0 * 1.08 }, { ...TARGET, z: Z0 * 6.6 });
}
const pulseAt = (t) => PULSES.reduce((m, p) => Math.max(m, t >= p ? Math.exp(-(t - p) / 0.16) : 0), 0);

const stage = document.getElementById('stage');
const bg = h(`<div class="layer bg"><img src="${A}bg.png"></div>`);
const ph = h(`<div class="layer"><img src="${A}phone.png"><img class="screenfx glow" src="${A}glow.png"><img class="screenfx profit" src="${A}profit.png"><div class="sweep"></div></div>`);
const glow = ph.querySelector('.glow'), profit = ph.querySelector('.profit'), sweep = ph.querySelector('.sweep');
const shade = h(`<div class="shade"></div>`);
const vignette = h(`<div class="vignette"></div>`);
const hook = h(`<div class="hook"><span class="ln">Wait...</span><span class="ln">is this legal?</span></div>`);
const lines = [...hook.querySelectorAll('.ln')];
const grain = h(`<div class="grain"></div>`);
stage.append(bg, ph, shade, vignette, hook, grain);

function render(t) {
  // ---- camera + parallax (dashboard drifts slower than the phone)
  const cam = camera(t);
  const q = ease.inOutSine(prog(t, 1.3, 4.6));
  css(bg, 'transform', camT({ ...cam, z: cam.z * (1 - 0.05 * q) }, 30 * q, 6 * q));
  css(ph, 'transform', camT({ ...cam, z: cam.z * (1 + 0.012 * q) }, -12 * q, 0));

  // ---- exposure: black, then the phone rises out of the dark
  const lightUp = ease.inOutSine(prog(t, 1.3, 1.95));
  const endDip = ease.inQuad(prog(t, DURATION - 0.1, DURATION)) * 0.35;
  css(shade, 'opacity', Math.max(1 - lightUp, endDip).toFixed(3));
  css(vignette, 'opacity', (t < 1.3 ? 0 : 1).toString());

  // ---- screen bloom + profit glow on the pulses
  const pulse = pulseAt(t);
  css(glow, 'opacity', (lerp(0, 0.32, lightUp) + 0.14 * pulse + 0.12 * ease.inQuad(prog(t, 2.8, DURATION))).toFixed(3));
  const pr = ease.inOutSine(prog(t, 2.6, 3.0));
  css(profit, 'opacity', (pr * (0.38 + 0.5 * pulse)).toFixed(3));
  // light sweeps across the glass: once as the phone appears, once as the build starts
  const s1 = prog(t, 1.42, 2.02), s2 = prog(t, 3.05, 3.6);
  const sw = s1 > 0 && s1 < 1 ? s1 : s2;
  css(sweep, 'opacity', (s1 > 0 && s1 < 1 ? 0.24 * Math.sin(Math.PI * s1) : s2 > 0 && s2 < 1 ? 0.16 * Math.sin(Math.PI * s2) : 0).toFixed(3));
  css(sweep, 'backgroundPosition', `${(100 - 100 * ease.inOutSine(sw)).toFixed(2)}% 0`);

  // ---- type: punch in, glide up over the phone, fly past the camera into the zoom
  if (!hook.__h) hook.__h = hook.offsetHeight;
  const up = ease.glide(prog(t, 1.3, 1.85));
  const cyText = lerp(lerp(935, 520, up), 486, ease.inOutSine(prog(t, 1.85, 4.2)));
  const out = ease.inCubic(prog(t, 4.2, 4.52));
  const sc = lerp(lerp(1, 0.9, up), 0.93, ease.inOutSine(prog(t, 1.85, 4.2))) * lerp(1, 1.45, out);
  css(hook, 'transform', `translate3d(0, ${(cyText - (hook.__h * sc) / 2).toFixed(2)}px, 0) scale(${sc.toFixed(4)})`);
  css(hook, 'opacity', (1 - out).toFixed(3));
  css(hook, 'filter', out > 0.01 ? `blur(${(out * 12).toFixed(2)}px)` : 'none');
  [[0.4, 1.38], [0.8, 1.26]].forEach(([t0, s0], i) => {
    const pin = ease.outExpo(prog(t, t0, t0 + 0.24));
    const b = lerp(14, 0, ease.outCubic(prog(t, t0, t0 + 0.16)));
    css(lines[i], 'opacity', clamp(prog(t, t0, t0 + 0.05)).toFixed(3));
    css(lines[i], 'transform', `scale(${lerp(s0, 1, pin).toFixed(4)})`);
    css(lines[i], 'filter', b > 0.05 ? `blur(${b.toFixed(2)}px)` : 'none');
  });

  // ---- film grain (changes every frame, constant within a frame's sub-samples)
  css(grain, 'backgroundImage', `url('${A}grain_${Math.floor(fl(t) * FPS) % 4}.png')`);
}

window.__duration = DURATION;
window.__render = (t) => render(Math.max(0, Math.min(DURATION - 1e-6, t)));
const imgs = [...stage.querySelectorAll('img')];
window.__ready = Promise.all([document.fonts.ready, ...imgs.map((i) => (i.complete ? Promise.resolve() : new Promise((r) => { i.onload = r; i.onerror = r; })))])
  .then(() => Promise.all([0, 1, 2, 3].map((k) => new Promise((r) => { const g = new Image(); g.onload = r; g.onerror = r; g.src = `${A}grain_${k}.png`; }))))
  .then(() => new Promise((r) => requestAnimationFrame(() => { window.__render(0); r(); })));

const q = new URLSearchParams(location.search);
if (q.has('t')) window.__ready.then(() => window.__render(Number(q.get('t'))));
