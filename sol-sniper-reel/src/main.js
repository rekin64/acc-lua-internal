// Entry point. Render contract used by scripts/render.mjs and scripts/snap.mjs:
//   window.__ready  -> Promise resolved when fonts + DOM are ready
//   window.__render(t) -> draws the frame at time t (seconds), synchronously
// Browser preview (no render needed):  node scripts/server.mjs  then open
//   http://127.0.0.1:5173/src/index.html?play        (plays with the soundtrack, space = pause, click = restart)
//   http://127.0.0.1:5173/src/index.html?t=6.3        (shows a single frame)
import { buildReel } from './timeline.js';
import { DURATION } from './timing.js';

const stage = document.getElementById('stage');
const reel = buildReel(stage);
window.__duration = DURATION;
window.__render = (t) => reel.render(Math.max(0, Math.min(DURATION - 1e-6, t)));
window.__ready = document.fonts.ready.then(() => new Promise((r) => requestAnimationFrame(() => { window.__render(0); r(); })));

const q = new URLSearchParams(location.search);
if (q.has('play') || q.has('t')) {
  // Fit the 1080x1920 stage into the window for previewing.
  const fit = () => {
    const s = Math.min(innerWidth / 1080, innerHeight / 1920);
    stage.style.transformOrigin = '0 0';
    stage.style.transform = `translate(${(innerWidth - 1080 * s) / 2}px, ${(innerHeight - 1920 * s) / 2}px) scale(${s})`;
  };
  fit();
  addEventListener('resize', fit);
}
if (q.has('t')) window.__ready.then(() => window.__render(Number(q.get('t'))));
if (q.has('play')) {
  const audio = new Audio('../audio/soundtrack.wav');
  let start = null, paused = false, pausedAt = 0;
  const loop = (now) => {
    if (start === null) start = now;
    const t = paused ? pausedAt : ((now - start) / 1000) % DURATION;
    window.__render(t);
    requestAnimationFrame(loop);
  };
  const restart = () => { start = null; paused = false; audio.currentTime = 0; audio.play().catch(() => {}); };
  addEventListener('click', restart);
  addEventListener('keydown', (e) => {
    if (e.code !== 'Space') return;
    paused = !paused;
    if (paused) { pausedAt = audio.currentTime; audio.pause(); } else { start = performance.now() - pausedAt * 1000; audio.play(); }
  });
  audio.addEventListener('ended', restart);
  window.__ready.then(() => { requestAnimationFrame(loop); audio.play().catch(() => {}); });
}
