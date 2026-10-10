// Shared SOL Sniper brand pieces (used by the site, the app and the outro).
//
// NOTE: the logo mark is a vector re-drawing of the ~10px icon visible in the
// supplied screenshot (a gradient diving-bird / pointer shape). To use the
// official artwork, replace the markup returned by logoMarkSVG() (or point it at
// assets/brand/logo-mark.svg) and re-render.

let uid = 0;

/** Inline SVG string for the gradient logo mark. `size` in px. */
export function logoMarkSVG(size = 24) {
  const id = `ssg${++uid}`;
  return `<svg class="ss-mark" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <defs>
    <linearGradient id="${id}a" x1="2" y1="3" x2="20" y2="16" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#D88AF2"/><stop offset=".45" stop-color="#8FA8F6"/><stop offset="1" stop-color="#5DC2F7"/>
    </linearGradient>
    <linearGradient id="${id}b" x1="10" y1="6" x2="11" y2="21" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#8AB4F7"/><stop offset=".55" stop-color="#6FBFF6"/><stop offset="1" stop-color="#C47FEF"/>
    </linearGradient>
  </defs>
  <path d="M2.4 3.2 L9.1 7.1 L8.3 8.4 Z" fill="url(#${id}a)"/>
  <path d="M9.3 6.6 C11.3 6.4 12.9 7.7 13.1 9.6 C13.3 11.6 12.3 13.5 11.4 15.6 L10.5 20.8 C9.9 18.5 9.5 16.1 9.1 13.7 C8.0 12.5 7.6 10.8 7.9 9.2 C8.1 7.9 8.5 6.9 9.3 6.6 Z" fill="url(#${id}b)"/>
  <path d="M11.5 9.8 C13.9 6.7 17.5 4.6 21.7 4.3 C19.7 6.2 17.7 8.4 15.7 10.3 C14.7 11.2 13.5 11.8 12.4 12.0 Z" fill="url(#${id}a)"/>
</svg>`;
}

/**
 * Brand lockup element: mark + "SOL Sniper" wordmark (Open Sans Regular, brand blue).
 * size = wordmark font-size in px.
 */
export function createLogo({ size = 22, gradient = false } = {}) {
  const el = document.createElement('div');
  el.className = 'ss-logo' + (gradient ? ' ss-logo--grad' : '');
  el.style.cssText = `display:inline-flex;align-items:center;gap:${(size * 0.28).toFixed(1)}px;font-family:'Open Sans',sans-serif;font-weight:400;font-size:${size}px;line-height:1;letter-spacing:-0.005em;color:var(--ss-wordmark);white-space:nowrap;`;
  el.innerHTML = `${logoMarkSVG(Math.round(size * 1.12))}<span class="ss-word">SOL Sniper</span>`;
  if (gradient) {
    const w = el.querySelector('.ss-word');
    w.style.cssText = 'background:linear-gradient(90deg,#3F5DB8 0%,#5468D4 45%,#7A63CF 100%);-webkit-background-clip:text;background-clip:text;color:transparent;padding:0.08em 0;';
  }
  return el;
}
