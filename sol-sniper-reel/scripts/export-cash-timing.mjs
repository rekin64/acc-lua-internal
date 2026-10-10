// Writes audio/cash_timing.json from src/cash/timing.js for audio/build_cash.py.
import fs from 'node:fs';
import path from 'node:path';
import { ROOT } from './server.mjs';
import { FPS, DURATION, BPM, CUES } from '../src/cash/timing.js';

const out = path.join(ROOT, 'audio', 'cash_timing.json');
fs.writeFileSync(out, JSON.stringify({ fps: FPS, duration: DURATION, bpm: BPM, cues: [...CUES].sort((a, b) => a.t - b.t) }, null, 2));
console.log(`wrote ${out}`);
