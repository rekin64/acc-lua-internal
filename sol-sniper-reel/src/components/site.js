// SOL Sniper landing-page hero: a crisp vector rebuild of assets/source/site-cropped.png
// (a 706x398 capture of a 1920x1080 viewport). Every coordinate below was measured from
// that capture (x2.7195) and verified by re-rendering, re-capturing and diffing
// (see out/site-cmp/v2). Everything is a pure function of the state passed to update().
import { clamp, css, ease, lerp, rectIn } from '../lib/engine.js';
import { createLogo } from './brand.js';

export { createLogo }; // SPEC: the brand lockup is also reachable from site.js (implementation lives in brand.js)

/* ------------------------------------------------------------------ background */

// Soft blobs, fitted as radial Gaussians g(r) = exp(-(r/R)^k) over white.
// rgb = blob colour at full strength, a = its peak opacity over white.
const BLOBS = [
  // top-left lavender: centre (120,116), centre colour ~#F6F4FC
  { at: '120px 116px', R: 271, k: 2.06, rgb: [236, 233, 249], a: 0.5, ext: 720 },
  // bottom-right ice blue: centre (1773,952) = 147px / 128px from the bottom-right corner, ~#F3F7FD
  { at: 'calc(100% - 147px) calc(100% - 128px)', R: 285, k: 2.28, rgb: [230, 240, 251], a: 0.5, ext: 760 },
];

function blobGradient({ at, R, k, rgb, a, ext }) {
  const stops = [];
  const n = 24;
  for (let i = 0; i <= n; i++) {
    const r = (ext * i) / n;
    const al = i === n ? 0 : a * Math.exp(-Math.pow(r / R, k));
    stops.push(`rgba(${rgb.join(',')},${al.toFixed(4)}) ${r.toFixed(1)}px`);
  }
  return `radial-gradient(circle ${ext}px at ${at}, ${stops.join(', ')})`;
}

const BG = BLOBS.map(blobGradient).join(', ') + ', #FFFFFF';

/* ------------------------------------------------------------------ nav shadow */

// The nav's drop shadow (fitted as `0 20px 48px rgba(59,108,185,.25)`) is drawn analytically instead of with
// box-shadow: Chromium rasterises large box-shadow blurs tile by tile, which leaves visible 256px tile seams
// in the 3.5-5.8x logo close-ups. A Gaussian-blurred rectangle is separable, so the same shadow is
// alpha(x,y) = a * Px(x) * Py(y): a vertical gradient (background) times a horizontal one (mask).
// Gradients are evaluated per pixel, so the shadow is seamless and exact at any camera zoom.
function erf(x) { // Abramowitz-Stegun 7.1.26 (|error| < 1.5e-7)
  const s = Math.sign(x), t = 1 / (1 + 0.3275911 * Math.abs(x));
  const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
  return s * y;
}
const NAV_SH = { x0: 480, x1: 1440, y0: 30, y1: 84, sigma: 24, rgb: '59, 108, 185', a: 0.25 }; // shadow rect = nav + (0,20)
const SH_EXT = 3.6 * NAV_SH.sigma; // beyond this the shadow is < 1/4000 of its peak
function box1d(v, lo, hi, sg) { // 1-D Gaussian-blurred box
  const k = Math.SQRT2 * sg;
  return 0.5 * (erf((v - lo) / k) - erf((v - hi) / k));
}
function profileStops(lo, hi, from, to, step, fmt) {
  const out = [];
  const push = (v) => out.push(`${fmt(box1d(v, lo, hi, NAV_SH.sigma))} ${(v - from).toFixed(1)}px`);
  if (hi - lo > 2 * SH_EXT) { // long side: sample the two edge zones, the flat middle interpolates
    for (let v = from; v <= lo + SH_EXT + 1e-6; v += step) push(v);
    for (let v = hi - SH_EXT; v <= to + 1e-6; v += step) push(v);
  } else {
    for (let v = from; v <= to + 1e-6; v += step) push(v);
  }
  return out.join(', ');
}
function navShadowStyle() {
  const { x0, x1, y0, y1, rgb, a } = NAV_SH;
  const L = x0 - SH_EXT, R = x1 + SH_EXT, T = y0 - SH_EXT, B = y1 + SH_EXT;
  const v = profileStops(y0, y1, T, B, 3, (p) => `rgba(${rgb}, ${(a * p).toFixed(5)})`);
  const hm = profileStops(x0, x1, L, R, 3, (p) => `rgba(0, 0, 0, ${p.toFixed(5)})`);
  return `left:${L}px;top:${T}px;width:${R - L}px;height:${B - T}px;` +
    `background:linear-gradient(180deg, ${v});` +
    `-webkit-mask-image:linear-gradient(90deg, ${hm});mask-image:linear-gradient(90deg, ${hm});`;
}

/** The hero background alone (white + soft blobs). Sizes to its container (100% x 100%). */
export function createSiteBackground() {
  const el = document.createElement('div');
  el.className = 'site-bg';
  el.style.background = BG;
  return el;
}

const DOT = '<i class="site-dot"></i>';

/* ------------------------------------------------------------------ site */

export function createSite() {
  const el = document.createElement('div');
  el.className = 'site';

  const bg = createSiteBackground();
  el.appendChild(bg);

  el.insertAdjacentHTML('beforeend', `
    <div class="site-fold"></div>
    <div class="site-nav-sh" style="${navShadowStyle()}"></div>
    <header class="site-nav">
      <div class="site-logo-slot"></div>
      <div class="site-link" style="--cx:988.5px"><span data-r="nav.features">Features</span></div>
      <div class="site-link" style="--cx:1071.2px"><span data-r="nav.benefits">Benefits</span></div>
      <div class="site-link site-link--badge" style="--cx:1124.5px"><span class="site-badge" data-r="nav.new">New</span></div>
      <div class="site-link" style="--cx:1205px"><span data-r="nav.usecases">Use Cases</span></div>
      <div class="site-link" style="--cx:1300.7px"><span data-r="nav.advantages">Advantages</span></div>
      <div class="site-link" style="--cx:1380.1px"><span data-r="nav.start">Start</span></div>
    </header>
    <h1 class="site-h1" data-r="headline">
      <span class="site-h1-l" data-r="headline.l1">AI</span>
      <span class="site-h1-l" data-r="headline.l2">Memecoin</span>
      <span class="site-h1-l" data-r="headline.l3">Trading.</span>
    </h1>
    <p class="site-sub" data-r="subtitle">
      <span class="site-sub-l">Begin your Automated Memecoin Sniping Journey today,</span>
      <span class="site-sub-l">Powered by High-Speed AI.</span>
    </p>
    <div class="site-cta" data-r="cta">
      <div class="site-cta-btn">
        <div class="site-cta-hi"></div>
        <div class="site-cta-tint"></div>
        <span class="site-cta-label">Start Sniping</span>
      </div>
    </div>
    <div class="site-dots" data-r="dots">${DOT.repeat(5)}</div>
  `);

  // nav logo: the shared brand lockup (brand.js createLogo) used exactly as the outro uses it, so the
  // mark-to-word proportions and spacing survive the logo match-cut. Only its position is set here: the
  // lockup is anchored by its right edge (= the wordmark's right edge, measured from the capture), so the
  // word stays put whatever the mark's drawn width is.
  const nav = el.querySelector('.site-nav');
  nav.dataset.r = 'nav';
  const logo = createLogo({ size: 17.5 });
  logo.classList.add('site-logo');
  logo.dataset.r = 'logo';
  const mark = logo.querySelector('svg');
  const markWrap = document.createElement('span'); // HTML box for rect('logo.icon') (SVG has no offset metrics)
  markWrap.className = 'site-mark';
  markWrap.dataset.r = 'logo.icon';
  mark.replaceWith(markWrap);
  markWrap.appendChild(mark);
  logo.querySelector('.ss-word').dataset.r = 'logo.word';
  el.querySelector('.site-logo-slot').replaceWith(logo);

  const R = {};
  el.querySelectorAll('[data-r]').forEach((n) => { R[n.dataset.r] = n; });

  const btn = el.querySelector('.site-cta-btn');
  const hi = el.querySelector('.site-cta-hi');
  const tint = el.querySelector('.site-cta-tint');

  function rect(name) {
    if (name === 'headline') {
      // the h1 box carries extra bottom padding so the gradient reaches the "g" descender;
      // the anchor is the union of the three line boxes.
      const a = rectIn(R['headline.l1'], el), b = rectIn(R['headline.l2'], el), c = rectIn(R['headline.l3'], el);
      const x = Math.min(a.x, b.x, c.x), y = a.y;
      const w = Math.max(a.x + a.w, b.x + b.w, c.x + c.w) - x, hgt = c.y + c.h - y;
      return { x, y, w, h: hgt, cx: x + w / 2, cy: y + hgt / 2 };
    }
    const n = R[name];
    if (!n) throw new Error(`site.rect: unknown anchor "${name}"`);
    return rectIn(n, el);
  }

  function update(state = {}) {
    const hov = clamp(state.ctaHover ?? 0);
    const prs = ease.outCubic(clamp(state.ctaPress ?? 0));
    const hv = ease.outCubic(hov) * (1 - prs); // hover look fades out while the button is held down
    // hover: lift 1.5px; press: settle back and scale to .96 around the centre
    css(btn, 'transform', `translateY(${(-1.5 * hv).toFixed(3)}px) scale(${(1 - 0.04 * prs).toFixed(4)})`);
    // The captured pill sits flat on the page (pure white 2px under it), so at rest there is only a faint
    // contact shadow and a tight, barely-there cast shadow; hover adds the depth, press pulls it back in.
    // Negative spread keeps the cast shadow under the pill (no halo at the sides).
    const c = (r, h, p) => lerp(lerp(r, h, hv), p, prs);
    css(btn, 'boxShadow',
      `0 ${c(1, 1.5, 0.5).toFixed(2)}px ${c(2, 3, 1).toFixed(2)}px rgba(40, 36, 110, ${c(0.07, 0.1, 0.1).toFixed(3)}), ` +
      `0 ${c(4, 9, 1.5).toFixed(2)}px ${c(10, 18, 4).toFixed(2)}px ${c(-4, -6, -2).toFixed(2)}px rgba(62, 54, 150, ${c(0.12, 0.3, 0.1).toFixed(3)})`);
    // brighten = cross-fade to a lighter version of the same gradient (keeps the saturation);
    // darken = a thin ink overlay
    css(hi, 'opacity', (0.75 * hv).toFixed(3));
    css(tint, 'opacity', prs.toFixed(3));
  }

  update({ t: 0, ctaHover: 0, ctaPress: 0 });
  return { el, rect, update };
}
