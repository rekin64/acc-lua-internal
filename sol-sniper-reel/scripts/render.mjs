// Frame renderer. Captures every output frame as N sub-frame samples spread over
// a 180° shutter (half a frame), which scripts/encode.py averages into real
// motion blur. Workers run in parallel browsers, each rendering an interleaved
// subset of frames (any frame can be rendered in any order: the timeline is a
// pure function of time).
//
//   node scripts/render.mjs [--workers 4] [--samples 4] [--fast-samples 12] [--shutter 0.5] [--from 0 --to 450] [--out out/frames] [--page src/index.html] [--resume]
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { startServer, ROOT } from './server.mjs';
import { launch, openPage } from './browser.mjs';
import { FPS, DURATION, samplesFor } from '../src/timing.js';

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf('--' + name); return i >= 0 ? args[i + 1] : def; };
const WORKERS = Number(opt('workers', Math.max(1, Math.min(6, os.cpus().length))));
const SAMPLES = Number(opt('samples', 4));
const FAST_SAMPLES = Number(opt('fast-samples', 12)); // used inside timing.js FAST_MOTION windows
const SHUTTER = Number(opt('shutter', 0.5)); // fraction of the frame interval the shutter is open
const TOTAL = Math.round(DURATION * FPS);
const FROM = Number(opt('from', 0));
const TO = Number(opt('to', TOTAL));
const OUT = path.resolve(ROOT, opt('out', 'out/frames'));
fs.mkdirSync(OUT, { recursive: true });

const { server, port } = await startServer();
const url = `http://127.0.0.1:${port}/${opt('page', 'src/index.html')}?render`;
const frames = [];
for (let k = FROM; k < TO; k++) frames.push(k);

const started = performance.now();
let done = 0;
async function worker(w) {
  const browser = await launch();
  try {
    const page = await openPage(browser, url);
    for (let i = w; i < frames.length; i += WORKERS) {
      const k = frames[i];
      const n = SAMPLES > 1 ? samplesFor(k, SAMPLES, FAST_SAMPLES) : 1;
      for (let j = 0; j < n; j++) {
        const t = k / FPS + (n > 1 ? (j / n) * (SHUTTER / FPS) : 0);
        const file = path.join(OUT, `f${String(k).padStart(4, '0')}_${j}.png`);
        if (fs.existsSync(file) && args.includes('--resume')) continue;
        await page.evaluate((t) => window.__render(t), t);
        await page.screenshot({ path: file, type: 'png' });
      }
      done++;
      if (done % 15 === 0 || done === frames.length) {
        const el = (performance.now() - started) / 1000;
        process.stdout.write(`\r${done}/${frames.length} frames  ${el.toFixed(0)}s elapsed  ~${((el / done) * (frames.length - done)).toFixed(0)}s left   `);
      }
    }
    if (page.__errors.length) console.error(`\n[worker ${w}] page errors:\n` + page.__errors.join('\n'));
  } finally {
    await browser.close();
  }
}

await Promise.all(Array.from({ length: WORKERS }, (_, w) => worker(w)));
server.close();
fs.writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify({ fps: FPS, samples: Math.max(SAMPLES, FAST_SAMPLES), shutter: SHUTTER, total: TOTAL, from: FROM, to: TO }));
console.log(`\nRendered ${frames.length} frames (${SAMPLES}, fast ${FAST_SAMPLES} sub-frames) to ${OUT} in ${((performance.now() - started) / 1000).toFixed(1)}s`);
