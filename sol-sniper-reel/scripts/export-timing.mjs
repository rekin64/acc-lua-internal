// Writes audio/timing.json from src/timing.js so the Python soundtrack builder
// uses exactly the same beat grid and cue times as the picture.
import fs from 'node:fs';
import path from 'node:path';
import { ROOT } from './server.mjs';
import { FPS, DURATION, BPM, BEAT, SECTIONS, MUSIC, CUES } from '../src/timing.js';

const out = path.join(ROOT, 'audio', 'timing.json');
const cues = [...CUES].sort((a, b) => a.t - b.t);
fs.writeFileSync(out, JSON.stringify({ fps: FPS, duration: DURATION, bpm: BPM, beat: BEAT, sections: SECTIONS, music: MUSIC, cues }, null, 2));
console.log(`wrote ${out} (${cues.length} cues)`);
