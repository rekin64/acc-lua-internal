// Writes audio/cash_intro_timing.json from src/cash/timing.js for audio/build_intro.py.
import fs from 'node:fs';
import path from 'node:path';
import { ROOT } from './server.mjs';
import { FPS, DURATION, BPM, SECTIONS, CUES } from '../src/cash/timing.js';

const out = path.join(ROOT, 'audio', 'cash_intro_timing.json');
fs.writeFileSync(out, JSON.stringify({ fps: FPS, duration: DURATION, bpm: BPM, sections: SECTIONS, cues: [...CUES].sort((a, b) => a.t - b.t) }, null, 2));
console.log(`wrote ${out}`);
