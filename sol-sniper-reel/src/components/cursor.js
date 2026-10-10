// Screen-recording style mouse cursor (macOS-like arrow) with a subtle click ring.
// Lives in WORLD coordinates (inside a camera rig), so it scales with punch-ins
// exactly like a cursor in a zoomed screen recording.
import { css, clamp, ease, prog, lerp } from '../lib/engine.js';

export function createCursor({ size = 26 } = {}) {
  const el = document.createElement('div');
  el.className = 'cursor';
  el.innerHTML = `
    <div class="cursor-ring"></div>
    <svg class="cursor-arrow" width="${size}" height="${size * 1.4}" viewBox="0 0 20 28" aria-hidden="true">
      <path d="M1.5 1.2 L1.5 21.6 L6.4 16.9 L9.7 24.9 L13.2 23.4 L9.9 15.6 L16.6 15.6 Z"
            fill="#111216" stroke="#FFFFFF" stroke-width="1.6" stroke-linejoin="round"/>
    </svg>`;
  const ring = el.querySelector('.cursor-ring');
  const arrow = el.querySelector('.cursor-arrow');
  return {
    el,
    /** state: { x, y, opacity=1, press=0 (0..1), ring=-1 (0..1 progress of click ring, <0 hidden) } */
    update({ x = 0, y = 0, opacity = 1, press = 0, ring: rp = -1 }) {
      css(el, 'transform', `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px)`);
      css(el, 'opacity', opacity.toFixed(3));
      css(arrow, 'transform', `scale(${(1 - 0.12 * press).toFixed(3)})`);
      if (rp >= 0 && rp <= 1) {
        const r = lerp(6, 30, ease.outCubic(rp));
        css(ring, 'opacity', (0.55 * (1 - ease.inQuad(rp))).toFixed(3));
        css(ring, 'transform', `translate(-50%, -50%) scale(${(r / 20).toFixed(3)})`);
      } else css(ring, 'opacity', '0');
    },
  };
}

/**
 * Cursor path from timed waypoints: [[t, x, y, bend?], ...]. Between waypoints the
 * hand follows a minimum-jerk profile along a slightly curved arc (bend = arc
 * height as a fraction of the segment length; sign picks the side).
 * x/y may be functions (evaluated lazily, e.g. to target live element rects).
 */
export function cursorAt(t, keys) {
  const val = (v) => (typeof v === 'function' ? v() : v);
  if (t <= keys[0][0]) return [val(keys[0][1]), val(keys[0][2])];
  for (let i = 1; i < keys.length; i++) {
    const [t1, x1f, y1f, bend = 0.12] = keys[i];
    if (t < t1) {
      const [t0, x0f, y0f] = keys[i - 1];
      const x0 = val(x0f), y0 = val(y0f), x1 = val(x1f), y1 = val(y1f);
      const p = ease.minJerk(prog(t, t0, t1));
      const dx = x1 - x0, dy = y1 - y0;
      const arc = Math.sin(Math.PI * p) * bend;
      return [x0 + dx * p - dy * arc, y0 + dy * p + dx * arc];
    }
  }
  const last = keys[keys.length - 1];
  return [val(last[1]), val(last[2])];
}

/** Press amount (0..1) and ring progress for a list of click times. */
export function clickState(t, clicks) {
  let press = 0, ring = -1;
  for (const c of clicks) {
    const d = t - c;
    if (d >= -0.03 && d < 0.14) press = Math.max(press, d < 0 ? (d + 0.03) / 0.03 : clamp(1 - (d - 0.06) / 0.08));
    if (d >= 0 && d < 0.42) ring = d / 0.42;
  }
  return { press, ring };
}
