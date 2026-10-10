// 5-second hook placed BEFORE the existing 15 s reel. Pure data (no DOM): imported by
// src/intro/intro.js and exported to audio/intro_timing.json for audio/build_intro.py.
// The existing reel starts at intro t = 5.0 with its own impact on a black frame, so
// the hook ends on a beat-exact cut into it.
export const FPS = 30;
export const DURATION = 5.0;
export const BPM = 125; // same grid as the main reel, counted back from the 5.0 s cut
export const snap = (t) => Math.round(t * FPS) / FPS;

export const SECTIONS = {
  black:   { start: 0.0, end: 0.4 },  // bass hit from black, tension starts
  text:    { start: 0.4, end: 1.3 },  // "Wait..." / "is this legal?"
  phone:   { start: 1.3, end: 2.8 },  // phone from the reference image, cinematic push-in
  build:   { start: 2.8, end: 4.2 },  // parallax, speed ramp, glow on the profit area
  handoff: { start: 4.2, end: 5.0 },  // zoom into the screen, cut on the beat into the reel
};

const s = snap;
// Pulse beats leading into the cut (125 BPM back from 5.0 s)
const pulse = (k) => s(DURATION - k * (60 / BPM));
export const CUES = [
  { t: 0.0, type: 'bass_hit' },                       // deep hit from black
  { t: 0.0, type: 'tension', dur: 5.0 },              // low drone bed (F minor), swells over the hook
  { t: s(0.4), type: 'accent', gain: 0 },             // "Wait..." punch
  { t: s(0.8), type: 'accent', gain: -3 },            // "is this legal?" punch
  { t: s(1.3), type: 'whoosh', dur: 0.5 },            // phone push-in
  { t: pulse(5), type: 'pulse', gain: -6 },           // heartbeat sub pulses build tension
  { t: pulse(4), type: 'pulse', gain: -5 },
  { t: pulse(3), type: 'pulse', gain: -4 },
  { t: pulse(2), type: 'pulse', gain: -3 },
  { t: pulse(1), type: 'pulse', gain: -2 },
  { t: s(2.8), type: 'accent', gain: -6 },            // intensity step (glow on the profit area)
  { t: DURATION, type: 'riser', dur: 1.6 },           // low cinematic riser ENDING at the cut
  { t: DURATION, type: 'suck', dur: 0.8 },            // reverse swell / zoom-in whoosh ENDING at the cut
];
