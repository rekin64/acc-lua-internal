// Shared SOL Sniper brand pieces (used by the site, the app and the outro).
//
// NOTE: the logo mark is a vector re-drawing of the ~10px icon visible in the
// supplied screenshot (a gradient diving-bird / pointer shape). To use the
// official artwork, replace the markup returned by logoMarkSVG() (or point it at
// assets/brand/logo-mark.svg) and re-render.

let uid = 0;

// Portrait mark (16:20) redrawn to the captured silhouette: a pink lead-in stroke from the top-left,
// a sky-blue body tapering straight down to a pink tail tip, and a small cyan right wing. One closed
// path, three fills (base body ramp + pink and cyan tints that fade out), so there are no seams.
export const MARK_ASPECT = 16 / 20;

/** Inline SVG string for the gradient logo mark. `size` = height in px (width = size * 0.8). */
export function logoMarkSVG(size = 24) {
  const id = `ssg${++uid}`;
  const w = +(size * MARK_ASPECT).toFixed(2);
  return `<svg class="ss-mark" width="${w}" height="${size}" viewBox="0 0 16 20" fill="none" aria-hidden="true">
  <defs>
    <linearGradient id="${id}b" x1="9.14" y1="3" x2="9.83" y2="19.6" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#80AEF7"/><stop offset=".42" stop-color="#5DB7F6"/><stop offset=".74" stop-color="#7DA8F4"/><stop offset="1" stop-color="#C77FF0"/>
    </linearGradient>
    <linearGradient id="${id}a" x1="0.4" y1="0.45" x2="8.23" y2="6.2" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#E39BF0"/><stop offset=".55" stop-color="#C28FF3"/><stop offset="1" stop-color="#A69BF5" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="${id}c" x1="15.71" y1="1.9" x2="11.31" y2="6.9" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#52CBF6"/><stop offset="1" stop-color="#5DB7F6" stop-opacity="0"/>
    </linearGradient>
    <path id="${id}p" d="M0.4 0.45 C3.31 1.1 5.94 2.4 7.89 4.05 C8.9 4.9 10.3 5.55 11.3 4.75 C12.6 3.7 14 2.6 15.71 1.9 C15.2 3.95 13.94 5.95 12.29 7.5 C11.83 10.6 10.63 14.8 9.83 19.6 C8.69 14.7 6.23 10.4 6.8 6.1 C4.95 4.45 2.75 2.25 0.4 0.45 Z"/>
  </defs>
  <use href="#${id}p" fill="url(#${id}b)"/><use href="#${id}p" fill="url(#${id}a)"/><use href="#${id}p" fill="url(#${id}c)"/>
</svg>`;
}

/**
 * Brand lockup element: mark + "SOL Sniper" wordmark (Open Sans Regular, brand blue).
 * size = wordmark font-size in px.
 */
export function createLogo({ size = 22, gradient = false } = {}) {
  const el = document.createElement('div');
  el.className = 'ss-logo' + (gradient ? ' ss-logo--grad' : '');
  el.style.cssText = `display:inline-flex;align-items:center;gap:${(size * 0.42).toFixed(2)}px;font-family:'Open Sans',sans-serif;font-weight:400;font-size:${size}px;line-height:1;letter-spacing:-0.005em;color:var(--ss-wordmark);white-space:nowrap;`;
  el.innerHTML = `${logoMarkSVG(Math.round(size * 1.12))}<span class="ss-word">SOL Sniper</span>`;
  if (gradient) {
    const w = el.querySelector('.ss-word');
    w.style.cssText = 'background:linear-gradient(90deg,#3F5DB8 0%,#5468D4 45%,#7A63CF 100%);-webkit-background-clip:text;background-clip:text;color:transparent;padding:0.08em 0;';
  }
  return el;
}
