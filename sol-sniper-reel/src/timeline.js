// The edit. Six sections on a 125 BPM grid (see timing.js). Every shot is a pure
// function of time: render(t) shows the shots that cover t and poses them.
//
//  1  0.00–1.43  Title on black: "MEMECOIN SNIPING. REDEFINED."
//  2  1.43–4.00  Site card rises, push to the logo, glide to the hero, cursor clicks "Start Sniping"
//  3  4.00–6.23  Zoom-through into the app: new pair detected, sniped, filled  ("Spot. Snipe. React.")
//  4  6.23–9.60  Whip to the chart, second entry in the trade panel, positions + take-profit ("Fast entries. Clean execution.")
//  5  9.60–12.47 Montage: one cut per beat, half-beats at the end
//  6  12.47–15.0 Match-cut to the logo, "Start Sniping" CTA, final click
import { clamp, lerp, prog, remap, ease, kf, spring, css, h } from './lib/engine.js';
import { beat, snap } from './timing.js';
import { createSite, createSiteBackground } from './components/site.js';
import { createApp } from './components/app.js';
import { createLogo } from './components/brand.js';
import { createCursor, cursorAt, clickState } from './components/cursor.js';

const CX = 540, CY = 960;
/** Beat n on the frame grid. */
const B = (n) => snap(beat(n));
const val = (v) => (typeof v === 'function' ? v() : v);
/** Smooth 0→1→0 bump: rises over [t0, t0+a], holds, falls over [t1-b, t1]. */
const bump = (t, t0, t1, a = 0.08, b = 0.2) => Math.min(ease.outCubic(prog(t, t0, t0 + a)), 1 - ease.inOutSine(prog(t, t1 - b, t1)));

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
/** Lower-third super, word-masked. lines: [['Spot.', 'Snipe.', 'React.'], ...] */
function makeSuper(stage, lines, { top, light = false } = {}) {
  const el = h(`<div class="super${light ? ' super--light' : ''}"></div>`);
  el.style.top = `${top}px`;
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
function poseSuper(sup, t, ins, out) {
  const visible = t >= ins[0] - 0.01 && t < out + 0.24;
  css(sup.el, 'display', visible ? 'block' : 'none');
  if (!visible) return;
  sup.words.forEach((w, i) => {
    const pin = ease.glide(prog(t, ins[i], ins[i] + 0.42));
    const pout = ease.inCubic(prog(t, out + i * 0.025, out + i * 0.025 + 0.2));
    const y = (1 - pin) * 112 - pout * 112;
    css(w, 'transform', `translate3d(0, ${y.toFixed(2)}%, 0)`);
    css(w, 'opacity', (clamp(pin * 1.6) * (1 - pout)).toFixed(3));
  });
}

// ------------------------------------------------------------------ the reel
export function buildReel(stage) {
  const parts = [];

  /* ============================== 1 · TITLE ============================== */
  const T1_END = B(3);
  const s1 = shot(stage, '#050507');
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
      if (!title.__top) title.__top = CY - title.offsetHeight / 2 - 20;
      const settle = ease.glide(prog(t, 0, 1.35));
      const exit = ease.inCubic(prog(t, 1.18, T1_END));
      const scale = lerp(1.075, 1, settle) * lerp(1, 1.04, exit);
      css(title, 'top', `${title.__top}px`);
      css(title, 'transform', `translate3d(0, ${(-150 * exit).toFixed(2)}px, 0) scale(${scale.toFixed(4)})`);
      css(title, 'opacity', (1 - exit).toFixed(3));
      const blur = Math.max(lerp(7, 0, ease.outCubic(prog(t, 0, 0.22))), 9 * exit);
      css(title, 'filter', blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : 'none');
      titleLines.forEach((ln, i) => {
        const p = ease.glide(prog(t, i * 0.07, i * 0.07 + 0.62));
        css(ln, 'transform', `translate3d(0, ${((1 - p) * 104).toFixed(2)}%, 0)`);
      });
      // "REDEFINED." turns brand on beat 2
      const g = ease.inOutCubic(prog(t, B(2) - 0.02, B(2) + 0.3));
      css(titlePaint, 'clipPath', `inset(-10% ${((1 - g) * 101).toFixed(2)}% -10% 0)`);
    },
  });

  /* ============================== 2 · SITE REVEAL ============================== */
  const T2 = B(3), T2_END = snap(4.0);
  const s2 = shot(stage, '#050507');
  const siteA = createSite();
  const cardA = h(`<div class="world-card"></div>`);
  cardA.appendChild(siteA.el);
  const curA = createCursor();
  s2.rig.append(cardA, curA.el);
  const flashA = h(`<div class="flash" style="background:var(--ss-grad-btn)"></div>`);
  s2.el.appendChild(flashA);
  const SA = (n) => () => siteA.rect(n);
  const logoCam = (dz = 0, dx = 0) => () => aim(siteA.rect('logo').cx + dx, siteA.rect('logo').cy, 3.45 + dz, CX, 470);
  const heroCam = (z) => () => {
    const hl = siteA.rect('headline'), cta = siteA.rect('cta');
    return aim(960, (hl.y + cta.y + cta.h) / 2, z, CX, 900);
  };
  const s2Keys = [
    { t: T2, x: 960, y: 540, z: 0.54 },
    { t: B(4), x: 960, y: 540, z: 0.585, e: ease.outSine },
    { t: B(5), ...wrapCam(logoCam(0)), e: ease.ramp },
    { t: B(6.5), ...wrapCam(logoCam(0.14, 14)), e: ease.inOutSine },
    { t: B(7.25), ...wrapCam(heroCam(1.9)), e: ease.ramp },
    { t: B(8), ...wrapCam(heroCam(1.97)), e: ease.outSine },
    { t: T2_END, x: () => siteA.rect('cta').cx, y: () => siteA.rect('cta').cy, z: 15, e: ease.inExpo },
  ];
  const s2Clicks = [B(8)];
  const supSpeed = makeSuper(stage, [['Built', 'for', 'speed.']], { top: 1296 });
  parts.push({
    t0: T2, t1: T2_END, el: s2.el,
    render(t) {
      const cta = siteA.rect('cta');
      const { press, ring } = clickState(t, s2Clicks);
      siteA.update({ t, ctaHover: prog(t, B(7.6), B(7.6) + 0.08), ctaPress: press });
      const rise = ease.glide(prog(t, T2, T2 + 0.62));
      const cam = camAt(t, s2Keys);
      css(s2.rig, 'transform', camTransform(cam, 0, (1 - rise) * 1500));
      // card chrome only while it reads as a card
      css(cardA, 'borderRadius', `${(22).toFixed(1)}px`);
      const [cx, cy] = cursorAt(t, [
        [B(6.9), cta.cx + 250, cta.cy + 330],
        [B(7.6), cta.cx + 8, cta.cy + 6, 0.1],
      ]);
      curA.update({ x: cx, y: cy, opacity: ease.outCubic(prog(t, B(6.9), B(6.9) + 0.1)), press, ring });
      const zt = prog(t, B(8) + 0.04, T2_END);
      css(s2.rig, 'filter', zt > 0 ? `blur(${(ease.inQuad(zt) * 14).toFixed(2)}px)` : 'none');
      css(flashA, 'opacity', (ease.inQuad(prog(t, T2_END - 0.09, T2_END)) * 0.9).toFixed(3));
    },
  });

  /* ============================== 3+4 · APP DEMO ============================== */
  const T3 = T2_END, T4_END = B(20);
  const s3 = shot(stage, '#050507');
  const appA = createApp();
  const cardB = h(`<div class="world-card" style="border-radius:26px"></div>`);
  cardB.appendChild(appA.el);
  const curB = createCursor();
  s3.rig.append(cardB, curB.el);
  const flashB = h(`<div class="flash" style="background:var(--ss-grad-btn)"></div>`);
  s3.el.appendChild(flashB);
  const AR = (n) => appA.rect(n);
  const FEED_Z = 1.92;
  const feedCam = (z = FEED_Z, dy = 0) => () => { const f = AR('feed'); return aim(f.cx, f.y, z, CX, 118 + dy); };
  const chartCam = (z) => () => { const c = AR('chart'); return aim(c.cx, c.y, z, CX, 150); };
  const tradeCam = (z) => () => { const r = AR('trade'); return aim(r.cx, r.y + r.h / 2, z, CX, 640); };
  const posCam = (z) => () => { const r = AR('positions'); return aim(r.cx, r.y + r.h / 2, z, CX, 620); };
  const s3Keys = [
    { t: T3, ...wrapCam(feedCam(2.9)) },
    { t: T3 + 0.42, ...wrapCam(feedCam(FEED_Z)), e: ease.glide },
    { t: B(12), ...wrapCam(feedCam(2.0, -16)), e: ease.inOutSine },
    { t: B(12.6), ...wrapCam(feedCam(2.1, -30)), e: ease.inQuad },
    { t: B(13) + 0.18, ...wrapCam(chartCam(1.42)), e: ease.inOutExpo },
    { t: B(14), ...wrapCam(chartCam(1.47)), e: ease.outSine },
    { t: B(14), ...wrapCam(tradeCam(1.86)) },
    { t: B(16), ...wrapCam(tradeCam(1.93)), e: ease.linear },
    { t: B(16) + 0.3, ...wrapCam(posCam(1.9)), e: ease.ramp },
    { t: B(19), ...wrapCam(posCam(1.98)), e: ease.linear },
    { t: T4_END, x: 960, y: 540, z: 0.555, e: ease.glide },
  ];
  const s3Clicks = [B(10), B(14.5), B(15)];
  const supSpot = makeSuper(stage, [['Spot.', 'Snipe.', 'React.']], { top: 1296 });
  const supFast = makeSuper(stage, [['Fast', 'entries.'], ['Clean', 'execution.']], { top: 1236 });
  const scrim = h(`<div class="scrim"></div>`);
  stage.appendChild(scrim);
  const simChip = h(`<div class="sim-chip"><i></i>Simulated demo</div>`);
  stage.appendChild(simChip);
  const toast = h(`<div class="ntoast">
      <div class="ic"><svg width="34" height="34" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="#12A16B" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
      <div class="tx"><div class="t1">Buy filled · 1.00 SOL</div><div class="t2">18.2M GLINT · TP +50% / SL −20% armed</div></div>
      <div class="tag">Simulated</div>
    </div>`);
  stage.appendChild(toast);

  function appState(t) {
    const ins = kf(t, [[T3, 0], [T3 + 0.06, 0], [T3 + 0.22, 1, ease.outCubic], [B(9) - 0.02, 1], [B(9) + 0.2, 2, ease.outCubic], [B(12.2), 2], [B(12.8), 3, ease.inOutCubic]]);
    const { press } = clickState(t, s3Clicks);
    const near = (c) => (Math.abs(t - c) < 0.2 ? press : 0);
    return {
      t,
      feed: {
        inserted: ins,
        highlight: 'GLINT',
        highlightAmt: ease.outCubic(prog(t, B(9) + 0.1, B(9) + 0.28)),
        snipeHover: t < B(10) + 0.3 ? prog(t, B(10) - 0.12, B(10) - 0.04) : 1 - prog(t, B(10.8), B(11.2)),
        snipePress: near(B(10)),
        snipeState: t < B(10) + 0.05 ? 'idle' : t < B(10.6) ? 'pending' : 'done',
      },
      chart: {
        reveal: remap(t, T3, T4_END, 0.84, 1),
        entry: 1,
        pnl: kf(t, [[B(13), 24.8], [B(15), 38.2, ease.outCubic], [B(17), 38.2], [B(17) + 0.2, 41.7, ease.outCubic]]),
        pnlFlash: bump(t, B(15) - 0.08, B(15) + 0.5),
      },
      trade: {
        preset: t < B(14.5) + 0.03 ? 2 : 1,
        presetHover: t > B(14.5) - 0.1 && t < B(14.5) + 0.16 ? 1 : -1,
        buyHover: t < B(15) + 0.3 ? prog(t, B(15) - 0.1, B(15) - 0.03) : 1 - prog(t, B(15.6), B(15.9)),
        buyPress: near(B(15)),
        buyState: t < B(15) + 0.05 ? 'idle' : t < B(15.5) ? 'pending' : 'filled',
      },
      positions: {
        pnl: {
          GLINT: kf(t, [[B(16), 38.2], [B(17), 38.2], [B(17) + 0.22, 41.7, ease.outCubic]]),
          MOCHI: kf(t, [[B(16), 12.6], [B(18), 12.6], [B(18) + 0.2, 13.4]]),
          ZORP: -4.1,
          FROGO: kf(t, [[B(16), 46.2], [B(17.5), 48.1, ease.inOutSine], [B(18), 50.0, ease.outCubic]]),
        },
        flash: { GLINT: bump(t, B(17), B(17) + 0.45), FROGO: bump(t, B(18), B(18) + 0.55) },
        tp: ease.outCubic(prog(t, B(18), B(18) + 0.12)),
      },
      toast: { show: bump(t, B(15.5) + 0.02, B(16) + 0.25, 0.22, 0.12), text: 'Buy filled · 0.50 SOL', sub: '9.1M GLINT · simulated' },
    };
  }
  parts.push({
    t0: T3, t1: T4_END, el: s3.el,
    render(t) {
      appA.update(appState(t));
      const cam = camAt(t, s3Keys);
      css(s3.rig, 'transform', camTransform(cam));
      const blur = Math.max(lerp(14, 0, ease.outCubic(prog(t, T3, T3 + 0.14))), 0);
      css(s3.rig, 'filter', blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : 'none');
      css(flashB, 'opacity', (0.9 * (1 - ease.outCubic(prog(t, T3, T3 + 0.16)))).toFixed(3));
      // cursor: Snipe on the GLINT row, then preset 0.5 + Buy in the trade panel
      const sn = AR('feed.snipe.GLINT'), p1 = AR('trade.preset.1'), buy = AR('trade.buy');
      let c;
      if (t < B(13) + 0.18) {
        c = cursorAt(t, [[B(9) + 0.08, sn.cx + 150, sn.cy + 300], [B(10) - 0.08, sn.cx - 6, sn.cy + 4, -0.12], [B(11.4), sn.cx - 4, sn.cy + 6], [B(12.6), sn.cx - 40, sn.cy + 120, 0.1]]);
      } else {
        c = cursorAt(t, [[B(14), p1.cx + 120, p1.cy + 240], [B(14.5) - 0.07, p1.cx + 2, p1.cy + 4, 0.1], [B(15) - 0.08, buy.cx + 30, buy.cy + 6, -0.12], [B(16), buy.cx + 70, buy.cy + 90]]);
      }
      const { press, ring } = clickState(t, s3Clicks);
      const curOp = t < B(13) + 0.18 ? ease.outCubic(prog(t, B(9) + 0.08, B(9) + 0.18)) : t < B(16) ? ease.outCubic(prog(t, B(14), B(14) + 0.06)) : 1 - prog(t, B(16), B(16) + 0.15);
      curB.update({ x: c[0], y: c[1], opacity: curOp, press, ring });
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
  siteRig.append(siteB.el, curC.el);
  appRig.appendChild(appB.el);
  const SB = (n) => siteB.rect(n);
  const BR = (n) => appB.rect(n);
  const baseApp = (t) => ({
    t: 9 + t,
    feed: { inserted: 2, highlight: 'GLINT', highlightAmt: 1, snipeState: 'done' },
    chart: { reveal: 1, entry: 1, pnl: 41.7 },
    trade: { preset: 1, buyState: 'filled' },
    positions: { pnl: { GLINT: 41.7, MOCHI: 13.4, ZORP: -4.1, FROGO: 50.0 }, tp: 1 },
    toast: { show: 0 },
  });
  const cuts = [
    { // "Memecoin" extreme close-up, drifting right
      t0: T5, t1: B(21), world: 'site',
      cam: (p) => { const l = SB('headline.l2'); return aim(lerp(l.x + l.w * 0.34, l.x + l.w * 0.46, p), l.cy, lerp(4.3, 4.65, p)); },
    },
    { // CTA close-up with the cursor press
      t0: B(21), t1: B(22), world: 'site', cursor: true,
      cam: (p) => { const c = SB('cta'); return aim(c.cx, c.cy, lerp(5.6, 5.95, p)); },
    },
    { // feed streaming fast
      t0: B(22), t1: B(23), world: 'app',
      state: (t, p) => ({ ...baseApp(t), feed: { inserted: lerp(2, 5.6, ease.inOutSine(p)), highlight: null, highlightAmt: 0, snipeState: 'idle' } }),
      cam: (p) => { const f = BR('feed'); return aim(f.cx, f.y + 230, lerp(2.45, 2.3, p), CX, 700); },
    },
    { // PnL close-up
      t0: B(23), t1: B(23.5), world: 'app',
      state: (t, p) => ({ ...baseApp(t), positions: { pnl: { GLINT: lerp(38.2, 41.7, ease.outCubic(p)), MOCHI: 13.4, ZORP: -4.1, FROGO: 50.0 }, flash: { GLINT: 1 - p * 0.6 }, tp: 1 } }),
      cam: (p) => { const r = BR('positions.pnl.GLINT'); return aim(r.cx, r.cy, lerp(4.2, 4.5, p)); },
    },
    { // chart: candles forming
      t0: B(23.5), t1: B(24), world: 'app',
      state: (t, p) => ({ ...baseApp(t), chart: { reveal: lerp(0.93, 1, p), entry: 1, pnl: 41.7 } }),
      cam: (p) => { const c = BR('chart.plot'); return aim(c.x + c.w * 0.74, c.y + c.h * 0.42, lerp(2.7, 2.85, p)); },
    },
    { // Buy -> Filled close-up
      t0: B(24), t1: B(24.5), world: 'app',
      state: (t, p) => ({ ...baseApp(t), trade: { preset: 1, buyState: p < 0.3 ? 'pending' : 'filled' } }),
      cam: (p) => { const b = BR('trade.buy'); return aim(b.cx, b.cy, lerp(3.1, 3.3, p)); },
    },
    { // AI score close-up
      t0: B(24.5), t1: B(25), world: 'app',
      state: (t, p) => baseApp(t),
      cam: (p) => { const a = BR('feed.ai.GLINT'); return aim(a.cx - 40, a.cy, lerp(4.6, 4.9, p)); },
    },
    { // logo close-up: match-cuts into the outro lockup
      t0: B(25), t1: T5_END, world: 'site',
      cam: (p) => { const l = SB('logo'); return aim(l.cx, l.cy, lerp(5.3, 5.75, ease.inSine(p)), CX, 800); },
    },
  ];
  parts.push({
    t0: T5, t1: T5_END, el: s5.el,
    render(t) {
      const c = cuts.find((k) => t >= k.t0 && t < k.t1) || cuts[cuts.length - 1];
      const p = prog(t, c.t0, c.t1);
      const isSite = c.world === 'site';
      css(siteRig, 'display', isSite ? 'block' : 'none');
      css(appRig, 'display', isSite ? 'none' : 'block');
      if (isSite) {
        const { press, ring } = clickState(t, [B(21.25)]);
        siteB.update({ t, ctaHover: c.cursor ? prog(t, B(21) + 0.04, B(21) + 0.1) : 0, ctaPress: c.cursor ? press : 0 });
        css(siteRig, 'transform', camTransform(c.cam(p)));
        if (c.cursor) {
          const r = SB('cta');
          const [x, y] = cursorAt(t, [[B(21), r.cx + 46, r.cy + 34], [B(21.25) - 0.04, r.cx + 10, r.cy + 6, 0.1]]);
          curC.update({ x, y, opacity: 1, press, ring });
        } else curC.update({ x: -100, y: -100, opacity: 0 });
      } else {
        appB.update(c.state(t, p));
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
  const group = h(`<div style="position:absolute;inset:0;transform-origin:540px 900px"></div>`);
  const logo = createLogo({ size: 104, gradient: true });
  const logoWrap = h(`<div class="outro-center" style="top:752px"></div>`);
  logoWrap.appendChild(logo);
  const ctaWrap = h(`<div class="outro-center" style="top:986px"></div>`);
  const cta = h(`<div class="outro-cta">Start Sniping<span class="hl"></span></div>`);
  ctaWrap.appendChild(cta);
  const disc = h(`<div class="disclaimer" style="top:1384px">Demo footage with simulated trades, for illustration only.<br>Not financial advice. Crypto trading involves risk.</div>`);
  const curD = createCursor({ size: 46 });
  group.append(logoWrap, ctaWrap, curD.el);
  s6.el.append(obg, group, disc);
  const ctaHl = cta.querySelector('.hl');
  parts.push({
    t0: T6, t1: T6_END + 1, el: s6.el,
    render(t) {
      css(group, 'transform', `scale(${lerp(1, 1.035, ease.inOutSine(prog(t, T6, T6_END))).toFixed(4)})`);
      const lp = ease.glide(prog(t, T6, T6 + 0.95));
      css(logo, 'transform', `scale(${lerp(1.1, 1, lp).toFixed(4)})`);
      const lb = lerp(3, 0, ease.outCubic(prog(t, T6, T6 + 0.2)));
      css(logo, 'filter', lb > 0.05 ? `blur(${lb.toFixed(2)}px)` : 'none');
      // CTA
      const ct = B(28);
      const sp = spring(t - ct, { freq: 2.1, damping: 0.72 });
      css(cta, 'opacity', ease.outCubic(prog(t, ct, ct + 0.18)).toFixed(3));
      const { press, ring } = clickState(t, [B(30)]);
      const hover = prog(t, B(29.6), B(29.6) + 0.08);
      css(cta, 'transform', `translate3d(0, ${((1 - sp) * 46 - hover * 3).toFixed(2)}px, 0) scale(${(lerp(0.9, 1, sp) * (1 - 0.045 * press)).toFixed(4)})`);
      css(ctaHl, 'opacity', (hover * 0.35 - press * 0.2).toFixed(3));
      const r = { cx: 540, cy: 986 + 64 };
      const [x, y] = cursorAt(t, [[B(28.6), r.cx + 330, r.cy + 420], [B(29.6), r.cx + 52, r.cy + 18, 0.12]]);
      curD.update({ x, y, opacity: ease.outCubic(prog(t, B(28.6), B(28.6) + 0.12)), press, ring });
      css(disc, 'opacity', ease.outCubic(prog(t, T6 + 0.5, T6 + 0.9)).toFixed(3));
    },
  });

  /* ============================== overlays ============================== */
  function overlays(t) {
    poseSuper(supSpeed, t, [B(5), B(5) + 0.07, B(5) + 0.14], B(6.5) - 0.16);
    poseSuper(supSpot, t, [B(9), B(10), B(11)], B(12.5));
    poseSuper(supFast, t, [B(13), B(13) + 0.08, B(15), B(15) + 0.08], B(19) - 0.25);
    css(scrim, 'opacity', (ease.outCubic(prog(t, T3 + 0.1, T3 + 0.4)) * (1 - ease.inOutSine(prog(t, B(19) - 0.2, B(19) + 0.1)))).toFixed(3));
    css(simChip, 'opacity', (ease.outCubic(prog(t, T3 + 0.15, T3 + 0.4)) * (1 - prog(t, T5_END - 0.12, T5_END))).toFixed(3));
    // floating "filled" notification for "React."
    const tin = B(11) - 0.01;
    const tp = spring(t - tin, { freq: 2.6, damping: 0.75 });
    const tout = ease.inCubic(prog(t, B(12.6), B(12.6) + 0.2));
    css(toast, 'display', t >= tin && t < B(12.6) + 0.22 ? 'flex' : 'none');
    css(toast, 'top', '1090px');
    css(toast, 'opacity', (ease.outCubic(prog(t, tin, tin + 0.12)) * (1 - tout)).toFixed(3));
    css(toast, 'transform', `translate3d(0, ${((1 - tp) * 60 + tout * 30).toFixed(2)}px, 0) scale(${lerp(0.96, 1, tp).toFixed(4)})`);
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

/** Spread a lazily-evaluated camera into {x,y,z} getters for camAt keys. */
function wrapCam(fn) {
  return { x: () => fn().x, y: () => fn().y, z: () => fn().z };
}
