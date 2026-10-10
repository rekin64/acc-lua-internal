// The edit. Six sections on a 125 BPM grid (see timing.js). Every shot is a pure
// function of time: render(t) shows the shots that cover t and poses them.
//
//  1  0.00–1.43  Title over the live terminal (dark, defocused): "MEMECOIN SNIPING. REDEFINED."
//  2  1.43–4.00  Site card rises, push to the logo, glide to the hero, cursor clicks "Start Sniping"
//  3  4.00–6.23  Zoom-through into the app: new pair detected (AI 94), sniped, filled ("Spot. Snipe. React.")
//  4  6.23–9.60  Whip lands on the chart ON the drop, second entry with cursor-follow punch-ins,
//                positions + take-profit, pull-out to the full terminal ("Fast entries. Clean execution.")
//  5  9.60–12.47 Montage: one cut per beat, half-beats at the end
//  6  12.47–15.0 Match-cut on the logo, the hero rebuilt as an end card, "Start Sniping" + final click
//
// Screen-recording rule: product UI state (numbers, rows, buttons) is FRAME-LOCKED
// (constant across a frame's motion-blur sub-samples, like a real capture) and data
// ticks at 7.5 Hz like a real terminal. Only the camera, the cursor and the editor's
// typography move continuously, so only they get motion blur.
import { clamp, lerp, prog, remap, ease, kf, spring, css, h } from './lib/engine.js';
import { FPS, beat, snap } from './timing.js';
import { createSite, createSiteBackground } from './components/site.js';
import { createApp, fillQuote } from './components/app.js';
import { createLogo } from './components/brand.js';
import { createCursor, cursorAt, clickState } from './components/cursor.js';

const CX = 540, CY = 960;
/** Beat n on the frame grid. */
const B = (n) => snap(beat(n));
/** Frame-locked time (start of the frame that t belongs to). */
const fl = (t) => Math.floor(t * FPS + 1e-6) / FPS;
/** Data clock: 7.5 Hz ticks (every 4 frames), how a live terminal updates. */
const tick = (t) => Math.floor(t * 7.5 + 1e-6) / 7.5;
const val = (v) => (typeof v === 'function' ? v() : v);
/** Smooth 0→1→0 bump: rises over [t0, t0+a], holds, falls over [t1-b, t1]. */
const bump = (t, t0, t1, a = 0.08, b = 0.2) => Math.min(ease.outCubic(prog(t, t0, t0 + a)), 1 - ease.inOutSine(prog(t, t1 - b, t1)));

// Outro layout (also drives the montage's last push so the match-cut lines up)
const OUTRO_LOGO = 96, OUTRO_LOGO_Y = 520, MATCH_Y = 800, MATCH_SIZE = 116;
const OUTRO_H1 = 640, OUTRO_CTA = 1060, OUTRO_DISC = 1286;
// Lower-third grid: every super's box ends here (multi-line supers grow upward)
const SUPER_BOTTOM = 1400;

// ------------------------------------------------------------------ camera
function camTransform({ x, y, z }, dx = 0, dy = 0) {
  return `translate(${(CX + dx).toFixed(2)}px, ${(CY + dy).toFixed(2)}px) scale(${z.toFixed(5)}) translate(${(-x).toFixed(3)}px, ${(-y).toFixed(3)}px)`;
}
/**
 * Interpolate between two camera states. Zoom is interpolated in log space and
 * the point we zoom toward (or away from) travels in a straight line on screen,
 * which reads like a real dolly/punch-in instead of a swinging pan.
 */
function dolly(p, a, b) {
  const z = Math.exp(lerp(Math.log(a.z), Math.log(b.z), p));
  const k = b.z >= a.z ? b : a;
  const sx = lerp((k.x - a.x) * a.z, (k.x - b.x) * b.z, p);
  const sy = lerp((k.y - a.y) * a.z, (k.y - b.y) * b.z, p);
  return { x: k.x - sx / z, y: k.y - sy / z, z };
}
/** keys: [{t, x, y, z, e?}], values may be functions. Equal consecutive t = hard cut. */
function camAt(t, keys) {
  const R = (k) => ({ x: val(k.x), y: val(k.y), z: val(k.z) });
  if (t <= keys[0].t) return R(keys[0]);
  for (let i = 1; i < keys.length; i++) {
    if (t < keys[i].t) {
      const p = (keys[i].e || ease.easy)(prog(t, keys[i - 1].t, keys[i].t));
      return dolly(p, R(keys[i - 1]), R(keys[i]));
    }
  }
  return R(keys[keys.length - 1]);
}
/** Camera that puts world point (wx, wy) at screen point (sx, sy) with zoom z. */
const aim = (wx, wy, z, sx = CX, sy = CY) => ({ x: wx - (sx - CX) / z, y: wy - (sy - CY) / z, z });
/** Spread a lazily-evaluated camera into {x,y,z} getters for camAt keys. */
const wrapCam = (fn) => ({ x: () => fn().x, y: () => fn().y, z: () => fn().z });
/** Camera key helper: K(t, camFn, ease). */
const K = (t, fn, e) => ({ t, ...wrapCam(fn), e });

// ------------------------------------------------------------------ DOM helpers
function shot(stage, bg = '#050507') {
  const el = h(`<div class="shot"></div>`);
  el.style.background = bg;
  const rig = h(`<div class="rig"></div>`);
  el.appendChild(rig);
  stage.appendChild(el);
  return { el, rig };
}
function setOn(el, on) {
  if (el.__on === on) return;
  el.__on = on;
  el.classList.toggle('on', on);
}
/** Lower-third super, word-masked, bottom-anchored. lines: [['Spot.', 'Snipe.', 'React.'], ...] */
function makeSuper(stage, lines, { light = false } = {}) {
  const el = h(`<div class="super${light ? ' super--light' : ''}"></div>`);
  el.style.bottom = `${1920 - SUPER_BOTTOM}px`;
  const words = [];
  for (const line of lines) {
    const ln = h(`<div class="ln"></div>`);
    line.forEach((w, i) => {
      const body = w.endsWith('.') ? `${w.slice(0, -1)}<span class="dot">.</span>` : w;
      const outer = h(`<span class="w"><span class="wi">${body}</span></span>`);
      ln.appendChild(outer);
      if (i < line.length - 1) ln.appendChild(document.createTextNode(' '));
      words.push(outer.firstElementChild);
    });
    el.appendChild(ln);
  }
  stage.appendChild(el);
  return { el, words };
}
/** Pose a super: words[i] enters at ins[i]; everything exits over [out, out+0.2]. */
function poseSuper(sup, t, ins, out, dx = 0) {
  const visible = t >= ins[0] - 0.01 && t < out + 0.3;
  css(sup.el, 'display', visible ? 'block' : 'none');
  if (!visible) return;
  css(sup.el, 'transform', `translate3d(${dx.toFixed(2)}px, 0, 0)`);
  sup.words.forEach((w, i) => {
    const pin = ease.glide(prog(t, ins[i], ins[i] + 0.42));
    const pout = ease.inCubic(prog(t, out + i * 0.025, out + i * 0.025 + 0.2));
    const y = (1 - pin) * 112 - pout * 112;
    css(w, 'transform', `translate3d(0, ${y.toFixed(2)}%, 0)`);
    css(w, 'opacity', (clamp(pin * 1.6) * (1 - pout)).toFixed(3));
  });
}
/** Mirrored copy of the site background directly above (dir=-1) or below (dir=1) a site. */
function pageExt(dir) {
  const el = createSiteBackground();
  const top = dir < 0 ? -1077 : 1077; // 3px overlap hides the seam
  el.style.cssText += `;position:absolute;left:0;top:${top}px;width:1920px;height:1080px;transform:scaleY(-1);pointer-events:none;`;
  return el;
}

// ------------------------------------------------------------------ the reel
export function buildReel(stage) {
  const parts = [];

  /* ============================== 1 · TITLE ============================== */
  const T1_END = B(3);
  const s1 = shot(stage, '#050507');
  // the live terminal behind the title: dark and defocused, so the hook moves from frame 0
  const appT = createApp();
  const ghost = h(`<div class="ghost-ui"></div>`);
  ghost.appendChild(s1.rig);
  s1.el.appendChild(ghost);
  s1.rig.appendChild(appT.el);
  const title = h(`<div class="title">
      <span class="ln"><span class="in">Memecoin</span></span>
      <span class="ln"><span class="in">sniping.</span></span>
      <span class="ln"><span class="in grad">Redefined.<span class="paint">Redefined.</span></span></span>
    </div>`);
  s1.el.appendChild(title);
  const titleLines = [...title.querySelectorAll('.in')];
  const titlePaint = title.querySelector('.paint');
  parts.push({
    t0: 0, t1: T1_END, el: s1.el,
    render(t) {
      const tf = fl(t);
      appT.update({ t: tick(t), feed: { inserted: kf(tf, [[0, 0], [0.2, 0.0], [0.42, 1, ease.outCubic], [0.75, 1], [0.95, 2, ease.outCubic], [1.15, 2], [1.33, 3, ease.outCubic]]) }, chart: { reveal: 0.84, entry: 1 } });
      const f = appT.rect('feed');
      css(s1.rig, 'transform', camTransform(aim(f.cx + 40, f.y + 420, lerp(1.95, 2.12, ease.inOutSine(prog(t, 0, T1_END))))));
      css(ghost, 'opacity', (ease.inOutSine(prog(t, 0.06, 0.7)) * (1 - ease.inCubic(prog(t, 1.2, T1_END)))).toFixed(3));

      if (!title.__top) title.__top = CY - title.offsetHeight / 2 - 20;
      const settle = ease.glide(prog(t, 0, 1.35));
      css(title, 'top', `${title.__top}px`);
      css(title, 'transform', `scale(${lerp(1.06, 1, settle).toFixed(4)})`);
      const blur = lerp(3, 0, ease.outCubic(prog(t, 0, 0.16)));
      css(title, 'filter', blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : 'none');
      titleLines.forEach((ln, i) => {
        const pin = ease.glide(prog(t, i * 0.06 - 0.06, i * 0.06 + 0.5));
        const pout = ease.inCubic(prog(t, 1.25 + i * 0.03, 1.25 + i * 0.03 + 0.15));
        css(ln, 'transform', `translate3d(0, ${((1 - pin) * 104 - pout * 104).toFixed(2)}%, 0)`);
      });
      // "REDEFINED." turns brand on beat 2 (feathered wipe)
      const g = ease.outCubic(prog(t, B(2) - 0.02, B(2) + 0.18));
      css(titlePaint, '--p', `${(g * 125 - 5).toFixed(2)}%`);
    },
  });

  /* ============================== 2 · SITE REVEAL ============================== */
  const T2 = B(3), T2_END = snap(4.0);
  const s2 = shot(stage, '#E6E8F0'); // hard cut from black to the light stage on the beat
  const siteA = createSite();
  const cardA = h(`<div class="world-card"></div>`);
  cardA.appendChild(siteA.el);
  const curA = createCursor();
  // The page continues above/below the hero (mirrored background), so punch-ins near the
  // nav or the fold never reveal the stage behind the card.
  const extUp = pageExt(-1), extDown = pageExt(1);
  s2.rig.append(cardA, extUp, extDown, curA.el);
  const flashA = h(`<div class="flash" style="background:var(--ss-grad-btn)"></div>`);
  s2.el.appendChild(flashA);
  const logoCam = (z, dx = 0) => () => { const l = siteA.rect('logo'); return aim(l.cx + dx, l.cy, z, CX, 640); };
  const heroCam = (z) => () => {
    const hl = siteA.rect('headline'), cta = siteA.rect('cta');
    return aim(960, (hl.y + cta.y + cta.h) / 2, z, CX, 760);
  };
  const ctaCam = (z) => () => { const c = siteA.rect('cta'); return aim(c.cx, c.cy, z); };
  const s2Keys = [
    { t: T2, x: 960, y: 540, z: 0.56 },
    { t: B(3.75), x: 960, y: 540, z: 0.585, e: ease.outSine },
    K(B(5), logoCam(3.2), ease.inOutCubic),
    K(B(5.75), logoCam(3.32, 10), ease.inOutSine),
    K(B(6.75), heroCam(1.95), ease.ramp),
    K(B(8), heroCam(2.03), ease.inOutSine),
    K(T2_END - 1 / FPS, ctaCam(8.5), ease.inCubic),
    K(T2_END, ctaCam(15), ease.linear),
  ];
  const s2Clicks = [B(8)];
  const supSpeed = makeSuper(stage, [['Built', 'for', 'speed.']]);
  parts.push({
    t0: T2, t1: T2_END, el: s2.el,
    render(t) {
      const tf = fl(t);
      const cta = siteA.rect('cta');
      const { press, ring } = clickState(t, s2Clicks);
      siteA.update({ t: tf, ctaHover: prog(tf, B(7.6), B(7.6) + 0.08), ctaPress: clickState(tf, s2Clicks).press });
      const rise = ease.glide(prog(t, T2, T2 + 0.5));
      const ext = ease.inOutSine(prog(t, B(3.75) + 0.05, B(3.75) + 0.36));
      css(extUp, 'opacity', ext.toFixed(3));
      css(extDown, 'opacity', ext.toFixed(3));
      css(cardA, 'boxShadow', `0 30px 90px rgba(28,30,60,${(0.2 * (1 - ext)).toFixed(3)}), 0 0 0 1px rgba(28,30,60,${(0.07 * (1 - ext)).toFixed(3)})`);
      const cam = camAt(t, s2Keys);
      css(s2.rig, 'transform', camTransform(cam, 0, (1 - rise) * 1050));
      const [cx, cy] = cursorAt(t, [
        [B(6.9), cta.cx + 300, cta.cy + 360],
        [B(7.6), cta.cx + 22, cta.cy + 9, 0.1],
      ]);
      curA.update({ x: cx, y: cy, opacity: ease.outCubic(prog(t, B(6.9), B(6.9) + 0.08)), press, ring });
      const zt = prog(t, B(8) + 0.05, T2_END);
      css(s2.rig, 'filter', zt > 0 ? `blur(${(ease.inQuad(zt) * 6).toFixed(2)}px)` : 'none');
      css(flashA, 'opacity', (ease.inQuad(prog(t, T2_END - 0.04, T2_END)) * 0.5).toFixed(3));
    },
  });

  /* ============================== 3+4 · APP DEMO ============================== */
  const T3 = T2_END, T4_END = B(20);
  const WHIP0 = B(12.72), WHIP1 = B(13);
  let whipDX = 0;
  const s3 = shot(stage, '#F5F6FA');
  const appA = createApp();
  const cardB = h(`<div class="world-card" style="border-radius:26px"></div>`);
  cardB.appendChild(appA.el);
  const curB = createCursor();
  s3.rig.append(cardB, curB.el);
  const flashB = h(`<div class="flash" style="background:var(--ss-grad-btn)"></div>`);
  s3.el.appendChild(flashB);
  const greyB = h(`<div class="flash" style="background:#E6E8F0"></div>`);
  s3.el.insertBefore(greyB, s3.rig);
  const AR = (n) => appA.rect(n);
  const FEED_Z = 1.8;
  const feedCam = (z = FEED_Z, dy = 0) => () => { const f = AR('feed'); return aim(f.cx, f.y, z, CX, 150 + dy); };
  const aiCam = (z) => () => { const a = AR('feed.ai.GLINT'), s = AR('feed.snipe.GLINT'); return aim((a.x + s.x + s.w) / 2 - 40, a.cy, z, CX, 620); };
  const rowCamFeed = (z) => () => { const r = AR('feed.row.GLINT'); return aim(r.cx, r.cy, z, CX, 640); };
  const chartCam = (z, fx = 0.62, sy = 600) => () => { const c = AR('chart.plot'); return aim(c.x + c.w * fx, c.y + c.h * 0.5, z, CX, sy); };
  const pnlCam = (z) => () => { const c = AR('chart.pnl'); return aim(c.cx, c.cy, z, CX, 700); };
  const tradeCam = (z) => () => { const r = AR('trade'); return aim(r.cx, r.y + r.h / 2, z, CX, 680); };
  const elCam = (name, z, sy) => () => { const r = AR(name); return aim(r.cx, r.cy, z, CX, sy); };
  const posCam = (z) => () => { const r = AR('positions'); return aim(r.cx, r.y + r.h / 2, z, CX, 700); };
  const rowCam = (tk, z) => () => { const r = AR('positions.row.' + tk); return aim(r.x + r.w * 0.52, r.cy, z, CX, 720); };
  const s3Keys = [
    K(T3, feedCam(1.55)),
    K(T3 + 0.4, feedCam(FEED_Z), ease.glide),                 // keeps pushing in after the zoom-through
    K(B(9) + 0.1, feedCam(FEED_Z + 0.03), ease.linear),
    K(B(9) + 0.42, aiCam(2.6), ease.ramp),                    // Spot: punch onto AI 94 + Snipe
    K(B(11) - 0.05, aiCam(2.72), ease.linear),                // Snipe -> Sniping -> Bought
    K(B(12.5), rowCamFeed(2.5), ease.inOutSine),              // React + build: settle onto the GLINT row
    K(WHIP0, rowCamFeed(2.56), ease.linear),                  // hold through the pre-drop gap
    K(WHIP1, chartCam(1.42, 0.5), ease.inOutExpo),            // whip lands ON the drop: launch -> entry -> climb
    K(B(13) + 0.1, chartCam(1.44, 0.5), ease.outSine),
    K(B(14), pnlCam(1.72), ease.inOutSine),                   // drift toward the Sim PnL chip
    K(B(14), tradeCam(1.62)),                                 // hard cut: trade panel
    K(B(14.5) - 0.12, elCam('trade.preset.1', 2.35, 760), ease.glide), // cursor-follow punch-in
    K(B(15) - 0.08, elCam('trade.buy', 2.15, 900), ease.easy),
    K(B(15.5), elCam('trade.buy', 2.22, 900), ease.linear),   // Executing -> Filled
    K(B(15.5) + 0.26, tradeCam(1.62), ease.glide),            // breathe out for the fill toast
    K(B(16), tradeCam(1.66), ease.linear),
    K(B(16) + 0.3, posCam(1.82), ease.ramp),                  // pan to positions
    K(B(17) - 0.06, posCam(1.86), ease.linear),
    K(B(17) + 0.24, rowCam('GLINT', 2.25), ease.glide),       // GLINT position ticks up
    K(B(18) - 0.2, rowCam('GLINT', 2.3), ease.linear),
    K(B(18), rowCam('FROGO', 2.4), ease.ramp),               // take-profit lands on the beat
    K(B(19), rowCam('FROGO', 2.46), ease.linear),
    { t: T4_END, x: 960, y: 540, z: 0.555, e: ease.ramp },    // pull-out: the whole terminal
  ];
  const s3Clicks = [B(10), B(14.5), B(15)];
  const supSpot = makeSuper(stage, [['Spot.', 'Snipe.', 'React.']]);
  const supFast = makeSuper(stage, [['Fast', 'entries.'], ['Clean', 'execution.']]);
  const scrim = h(`<div class="scrim"></div>`);
  stage.appendChild(scrim);
  const chipBand = h(`<div class="chip-band"></div>`);
  stage.appendChild(chipBand);
  const simChip = h(`<div class="sim-chip"><i></i>Simulated demo</div>`);
  stage.appendChild(simChip);
  const toast = h(`<div class="ntoast">
      <div class="ic"><svg width="34" height="34" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="#12A16B" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
      <div class="tx"><div class="t1">Buy filled · 1.00 SOL</div><div class="t2">${fillQuote({ feed: { snipeState: 'done' } }, 1).tokensText} · TP +30% / SL −15% armed</div></div>
      <div class="tag">Simulated</div>
    </div>`);
  stage.appendChild(toast);

  // During the feed shots GLINT has just launched (entry candle forming), so the snipe
  // fills at ~0%. The whip on the drop is a time jump: minutes later, the climb.
  const REVEAL = (t) => (t < WHIP1 ? 0.055 : remap(t, T3, T4_END, 0.84, 1));
  const CLOCK = (t) => tick(t) + (t < WHIP1 ? 0 : 690);
  const FILL2 = REVEAL(tick(B(15.5)));
  function appState(t) {
    const tf = fl(t), td = tick(t);
    const ins = kf(tf, [[T3, 0], [T3 + 0.08, 0], [T3 + 0.22, 1, ease.outCubic], [B(9) - 0.02, 1], [B(9) + 0.16, 2, ease.outCubic], [B(11.7), 2], [B(11.7) + 0.16, 3, ease.outCubic]]);
    const { press } = clickState(tf, s3Clicks);
    const near = (c) => (Math.abs(tf - c) < 0.2 ? press : 0);
    return {
      t: CLOCK(t), tMotion: tf,
      feed: {
        inserted: ins,
        highlight: 'GLINT',
        highlightAmt: ease.outCubic(prog(tf, B(9) + 0.1, B(9) + 0.28)),
        snipeHover: tf < B(10) + 0.3 ? prog(tf, B(10) - 0.12, B(10) - 0.04) : 1 - prog(tf, B(10.8), B(11.2)),
        snipePress: near(B(10)),
        snipeState: tf < B(10) + 0.05 ? 'idle' : tf < B(10.6) ? 'pending' : 'done',
      },
      chart: { reveal: REVEAL(td), entry: tf >= B(10.6) ? 1 : 0, pnlFlash: bump(tf, B(13), B(13) + 0.5) },
      trade: {
        preset: tf < B(14.5) + 0.03 ? 2 : 1,
        presetHover: tf > B(14.5) - 0.1 && tf < B(14.5) + 0.16 ? 1 : -1,
        buyHover: tf < B(15) + 0.3 ? prog(tf, B(15) - 0.1, B(15) - 0.03) : 1 - prog(tf, B(15.6), B(15.9)),
        buyPress: near(B(15)),
        buyState: tf < B(15) + 0.05 ? 'idle' : tf < B(15.5) ? 'pending' : 'filled',
        fillAt: FILL2,
      },
      positions: {
        pnl: {
          MOCHI: kf(td, [[B(16), 8.2], [B(18), 8.2], [B(18) + 0.27, 8.6]]),
          ZORP: -4.1,
          FROGO: kf(td, [[B(16), 26.4], [B(17.5), 28.1, ease.inOutSine], [B(18), 30.0, ease.outCubic]]),
        },
        flash: { GLINT: bump(tf, B(17), B(17) + 0.45), FROGO: bump(tf, B(18), B(18) + 0.55) },
        tp: ease.outCubic(prog(tf, B(18), B(18) + 0.12)),
      },
      toast: { show: bump(tf, B(15.5) + 0.02, B(16) + 0.25, 0.22, 0.12), text: 'Buy filled · 0.50 SOL', sub: null },
    };
  }
  let snipeRest = null;
  parts.push({
    t0: T3, t1: T4_END, el: s3.el,
    render(t) {
      appA.update(appState(t));
      const pull = ease.inOutSine(prog(t, B(19) + 0.04, B(19) + 0.3));
      css(greyB, 'opacity', pull.toFixed(3));
      css(cardB, 'boxShadow', `0 30px 90px rgba(28,30,60,${(0.22 * pull).toFixed(3)}), 0 0 0 1px rgba(28,30,60,${(0.07 * pull).toFixed(3)})`);
      const cam = camAt(t, s3Keys);
      const punch = 1 + 0.035 * Math.sin(Math.PI * prog(t, WHIP1, WHIP1 + 0.22)) * (1 - prog(t, WHIP1, WHIP1 + 0.22));
      css(s3.rig, 'transform', camTransform({ ...cam, z: cam.z * punch }));
      // overlays ride the whip pan out of frame (same screen-space motion as the UI)
      if (t >= WHIP0 && t < WHIP1) {
        const c0 = camAt(WHIP0, s3Keys);
        whipDX = (c0.x - cam.x) * cam.z;
      } else whipDX = t >= WHIP1 ? -4000 : 0;
      const blur = lerp(6, 0, ease.outCubic(prog(t, T3, T3 + 0.1)));
      css(s3.rig, 'filter', blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : 'none');
      css(flashB, 'opacity', (0.45 * (1 - ease.outCubic(prog(t, T3, T3 + 0.1)))).toFixed(3));
      // cursor: Snipe on the GLINT row, then preset 0.5 + Buy in the trade panel
      const sn = AR('feed.snipe.GLINT'), p1 = AR('trade.preset.1'), buy = AR('trade.buy');
      if (t < B(10.2)) snipeRest = { ...sn };
      const sr = snipeRest || sn;
      let c, op;
      if (t < WHIP1) {
        c = cursorAt(t, [[B(9) + 0.08, sn.cx + 170, sn.cy + 280], [B(10) - 0.08, sn.cx - 4, sn.cy + 5, -0.12], [B(11.2), sr.cx - 2, sr.cy + 7], [B(12), sr.cx + 60, sr.cy + 70, 0.1]]);
        op = ease.outCubic(prog(t, B(9) + 0.08, B(9) + 0.16));
      } else {
        c = cursorAt(t, [[B(14), p1.cx + 140, p1.cy + 220], [B(14.5) - 0.07, p1.cx + 2, p1.cy + 4, 0.1], [B(15) - 0.08, buy.cx + 40, buy.cy + 6, -0.12], [B(16), buy.cx + 150, buy.cy + 18]]);
        op = t < B(16) ? ease.outCubic(prog(t, B(14), B(14) + 0.06)) : 1 - prog(t, B(16), B(16) + 0.15);
      }
      const { press, ring } = clickState(t, s3Clicks);
      curB.update({ x: c[0], y: c[1], opacity: op, press, ring, ringScale: 2 / cam.z });
    },
  });

  /* ============================== 5 · MONTAGE ============================== */
  const T5 = B(20), T5_END = B(26);
  const s5 = shot(stage, '#FFFFFF');
  const siteB = createSite();
  const appB = createApp();
  const curC = createCursor();
  const siteRig = s5.rig;
  const appRig = h(`<div class="rig"></div>`);
  s5.el.appendChild(appRig);
  siteRig.append(siteB.el, pageExt(-1), pageExt(1), curC.el);
  appRig.appendChild(appB.el);
  const SB = (n) => siteB.rect(n);
  const BR = (n) => appB.rect(n);
  // the story continues: final states only (no rewinds), live clock keeps ticking
  const baseApp = (t) => {
    return {
      t: tick(t) + 690, tMotion: fl(t),
      feed: { inserted: 3, highlight: 'GLINT', highlightAmt: 1, snipeState: 'done' },
      chart: { reveal: 1, entry: 1 },
      trade: { preset: 1, buyState: 'filled', fillAt: FILL2 },
      positions: { pnl: { MOCHI: 8.6, ZORP: -4.1, FROGO: 30.0 }, tp: 1 },
      toast: { show: 0 },
    };
  };
  const cuts = [
    { // the client's headline, whole, sliding laterally with a speed ramp
      t0: T5, t1: B(21), world: 'site', e: ease.outCubic,
      cam: (p) => { const l = SB('headline.l2'); return aim(l.cx + lerp(70, -30, p), l.cy, lerp(2.5, 2.62, p)); },
    },
    { // CTA close-up with the cursor press
      t0: B(21), t1: B(22), world: 'site', cursor: true, e: ease.outQuart,
      cam: (p) => { const c = SB('cta'); return aim(c.cx, c.cy, lerp(5.4, 5.0, p)); },
    },
    { // AI-score / Snipe column streaming new pairs
      t0: B(22), t1: B(23), world: 'app', chip: true, e: ease.outCubic,
      state: (t, p) => { const b = baseApp(t); return { ...b, feed: { ...b.feed, inserted: 3 + [0.02, 0.5].reduce((a, s) => a + ease.outCubic(prog(p, s, s + 0.28)), 0) } }; },
      cam: (p) => { const a = BR('feed.ai.GLINT'); const f = BR('feed'); return aim(a.x + 40, f.y + 300, lerp(2.9, 2.7, p), CX, 760); },
    },
    { // positions PnL column (inside the safe area)
      t0: B(23), t1: B(23.5), world: 'app', chip: true, e: ease.outCubic,
      state: (t, p) => ({ ...baseApp(t), positions: { ...baseApp(t).positions, flash: { GLINT: 1 - p * 0.6 } } }),
      cam: (p) => { const r = BR('positions.pnl.GLINT'); return aim(r.cx - 60, r.cy + 90, lerp(3.3, 3.48, p)); },
    },
    { // chart: latest candles, sliding left to right
      t0: B(23.5), t1: B(24), world: 'app', chip: true, e: ease.outCubic,
      state: (t) => baseApp(t),
      cam: (p) => { const c = BR('chart.plot'); return aim(c.x + c.w * lerp(0.7, 0.8, p), c.y + c.h * 0.45, 2.6); },
    },
    { // Filled
      t0: B(24), t1: B(24.5), world: 'app', chip: true, e: ease.outCubic,
      state: (t) => baseApp(t),
      cam: (p) => { const b = BR('trade.buy'); return aim(b.cx, b.cy, lerp(2.2, 2.34, p), CX, 860); },
    },
    { // AI 94 + Bought
      t0: B(24.5), t1: B(25), world: 'app', chip: true, e: ease.outCubic,
      state: (t) => baseApp(t),
      cam: (p) => { const a = BR('feed.ai.GLINT'), b = BR('feed.snipe.GLINT'); return aim(lerp(a.cx, b.x + b.w, 0.5) + lerp(14, -14, p), a.cy, lerp(3.95, 3.75, p)); },
    },
    { // logo: accelerating push that match-cuts into the end card at the same size and place
      t0: B(25), t1: T5_END, world: 'site', e: ease.inQuad,
      cam: (p) => { const l = SB('logo'), w = SB('logo.word'); return aim(l.cx, l.cy, lerp(4.6, MATCH_SIZE * 1.02 / (w.h * 0.98), p), CX, MATCH_Y); },
    },
  ];
  let montageChip = 0;
  parts.push({
    t0: T5, t1: T5_END, el: s5.el,
    render(t) {
      const tf = fl(t);
      const c = cuts.find((k) => t >= k.t0 && t < k.t1) || cuts[cuts.length - 1];
      const p = c.e(prog(t, c.t0, c.t1));
      montageChip = c.chip ? 1 : 0;
      const isSite = c.world === 'site';
      css(siteRig, 'display', isSite ? 'block' : 'none');
      css(appRig, 'display', isSite ? 'none' : 'block');
      if (isSite) {
        const { press, ring } = clickState(t, [B(21.25)]);
        siteB.update({ t: tf, ctaHover: c.cursor ? prog(tf, B(21) + 0.04, B(21) + 0.1) : 0, ctaPress: c.cursor ? clickState(tf, [B(21.25)]).press : 0 });
        const cam = c.cam(p);
        css(siteRig, 'transform', camTransform(cam));
        if (c.cursor) {
          const r = SB('cta');
          const [x, y] = cursorAt(t, [[B(21), r.cx + 52, r.cy + 34], [B(21.25) - 0.04, r.cx + 24, r.cy + 10, 0.1]]);
          curC.update({ x, y, opacity: 1, press, ring, ringScale: 1.4 / cam.z, ringLight: true });
        } else curC.update({ x: -100, y: -100, opacity: 0 });
      } else {
        appB.update(c.state(t, prog(tf, c.t0, c.t1)));
        css(appRig, 'transform', camTransform(c.cam(p)));
      }
    },
  });

  /* ============================== 6 · OUTRO ============================== */
  const T6 = B(26), T6_END = 15.0;
  const s6 = shot(stage, '#FFFFFF');
  const obg = createSiteBackground();
  obg.style.position = 'absolute';
  obg.style.inset = '0';
  const group = h(`<div style="position:absolute;inset:0;transform-origin:540px 860px"></div>`);
  const logo = createLogo({ size: OUTRO_LOGO });
  const logoWrap = h(`<div class="outro-center" style="top:0;height:0;align-items:center"></div>`);
  logoWrap.appendChild(logo);
  const h1 = h(`<div class="outro-h1" style="top:${OUTRO_H1}px">
      <span class="ln"><span class="in" style="--bp:0%">AI</span></span>
      <span class="ln"><span class="in" style="--bp:50%">Memecoin</span></span>
      <span class="ln"><span class="in" style="--bp:100%">Trading.</span></span>
    </div>`);
  const h1Lines = [...h1.querySelectorAll('.in')];
  const ctaWrap = h(`<div class="outro-center" style="top:${OUTRO_CTA}px"></div>`);
  const cta = h(`<div class="outro-cta"><span class="lbl">Start Sniping</span><span class="hl"></span></div>`);
  const ctaPing = h(`<div class="outro-ping"></div>`);
  cta.appendChild(ctaPing);
  ctaWrap.appendChild(cta);
  const disc = h(`<div class="disclaimer" style="top:${OUTRO_DISC}px">Simulated demo trades. Not financial advice.<br>Crypto trading is high risk.</div>`);
  const curD = createCursor({ size: 46 });
  group.append(logoWrap, h1, ctaWrap, curD.el);
  s6.el.append(obg, group, disc);
  const ctaHl = cta.querySelector('.hl');
  parts.push({
    t0: T6, t1: T6_END + 1, el: s6.el,
    render(t) {
      css(group, 'transform', `scale(${lerp(1, 1.03, ease.inOutSine(prog(t, T6, T6_END))).toFixed(4)})`);
      // match-cut: the logo arrives where (and as big as) the montage left it, keeps
      // pushing for a beat, then glides up into the end-card lockup
      const up = ease.glide(prog(t, B(26.9), B(27.9)));
      const startScale = (MATCH_SIZE * 1.02) / OUTRO_LOGO;
      const s = lerp(startScale * lerp(1, 1.035, ease.outSine(prog(t, T6, B(27.4)))), 1, up);
      css(logoWrap, 'transform', `translate3d(0, ${lerp(MATCH_Y, OUTRO_LOGO_Y, up).toFixed(2)}px, 0)`);
      css(logo, 'transform', `scale(${s.toFixed(4)})`);
      // the hero headline returns, line by line
      h1Lines.forEach((ln, i) => {
        const p = ease.glide(prog(t, B(27.2) + i * 0.08, B(27.2) + i * 0.08 + 0.55));
        css(ln, 'transform', `translate3d(0, ${((1 - p) * 104).toFixed(2)}%, 0)`);
      });
      // CTA
      const ct = B(28.25);
      const sp = spring(t - ct, { freq: 2.1, damping: 0.72 });
      css(cta, 'opacity', ease.outCubic(prog(t, ct, ct + 0.16)).toFixed(3));
      const { press, ring } = clickState(t, [B(30)]);
      const hover = prog(t, B(29.6), B(29.6) + 0.08) * (1 - ease.outCubic(prog(t, B(30) + 0.15, B(30) + 0.45)));
      css(cta, 'transform', `translate3d(0, ${((1 - sp) * 40 - hover * 3).toFixed(2)}px, 0) scale(${(lerp(0.92, 1, sp) * (1 - 0.05 * press)).toFixed(4)})`);
      css(ctaHl, 'opacity', (hover * 0.3).toFixed(3));
      // click payoff: a soft ring pulses out of the button
      const pg = prog(t, B(30), B(30) + 0.6);
      css(ctaPing, 'opacity', pg > 0 && pg < 1 ? (0.5 * (1 - ease.outCubic(pg))).toFixed(3) : '0');
      css(ctaPing, 'transform', `scale(${lerp(1, 1.32, ease.outCubic(pg)).toFixed(4)}, ${lerp(1, 1.9, ease.outCubic(pg)).toFixed(4)})`);
      const r = { cx: 540, cy: OUTRO_CTA + 66 };
      const [x, y] = cursorAt(t, [[B(28.7), 1180, 1700], [B(29.6), r.cx + 170, r.cy + 34, 0.1], [B(30) + 0.25, r.cx + 172, r.cy + 36], [B(31.1), r.cx + 460, r.cy + 300, -0.1]]);
      curD.update({ x, y, opacity: 1 - prog(t, B(30) + 0.45, B(31)), press, ring, ringLight: true, ringScale: 1.2 });
      css(disc, 'opacity', ease.outCubic(prog(t, T6, T6 + 0.18)).toFixed(3));
    },
  });

  /* ============================== overlays ============================== */
  function overlays(t) {
    poseSuper(supSpeed, t, [B(4), B(4) + 0.07, B(4) + 0.14], B(8) - 0.24);
    poseSuper(supSpot, t, [B(9), B(10), B(11)], WHIP1 - 0.1, whipDX);
    poseSuper(supFast, t, [B(13), B(13) + 0.08, B(15), B(15) + 0.08], B(19) - 0.25);
    css(scrim, 'opacity', (ease.outCubic(prog(t, T3 + 0.1, T3 + 0.4)) * (1 - ease.inOutSine(prog(t, B(19) - 0.2, B(19) + 0.1)))).toFixed(3));
    const inDemo = ease.outCubic(prog(t, T3 + 0.15, T3 + 0.4)) * (t < T5 ? 1 : 0);
    const chip = t < T5 ? inDemo : t < T5_END ? montageChip : 0;
    css(simChip, 'opacity', chip.toFixed(3));
    css(chipBand, 'opacity', (t >= T5 && t < T5_END ? montageChip : 0).toFixed(3));
    // floating "filled" notification for "React."
    const tin = B(11) - 0.01;
    const tp = spring(t - tin, { freq: 2.6, damping: 0.75 });
    css(toast, 'display', t >= tin && t < WHIP1 ? 'flex' : 'none');
    css(toast, 'top', '1086px');
    css(toast, 'opacity', ease.outCubic(prog(t, tin, tin + 0.12)).toFixed(3));
    css(toast, 'transform', `translate3d(${whipDX.toFixed(2)}px, ${((1 - tp) * 60).toFixed(2)}px, 0) scale(${lerp(0.96, 1, tp).toFixed(4)})`);
  }

  return {
    render(t) {
      for (const p of parts) {
        const on = t >= p.t0 && t < p.t1;
        setOn(p.el, on);
        if (on) p.render(t);
      }
      overlays(t);
    },
  };
}
