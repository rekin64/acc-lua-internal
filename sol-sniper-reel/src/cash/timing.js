// 5-second cash-footage hook placed BEFORE the unchanged 15 s reel (it replaces the phone-photo hook of
// dist/sol-sniper-reel-with-intro.mp4). Pure data (no DOM): imported by src/cash/cash.js and exported to
// audio/cash_intro_timing.json for audio/build_intro.py (same sound palette as the phone hook).
// The reel starts at hook t = 5.0 with its own impact on its dark title frame, so every beat here is
// counted back from that cut: 125 BPM, beats at 5.0 - n * 0.48 s, frame-snapped.
export const FPS = 30;
export const DURATION = 5.0;
export const BPM = 125;
const BEAT = 60 / BPM;
export const snap = (t) => Math.round(t * FPS) / FPS;
/** The n-th beat before the cut into the reel (G(0) = 5.0). */
export const G = (n) => snap(DURATION - n * BEAT);

export const CUT1 = G(7);   // 1.633  punch-in cut: the hand swings the notes toward the box
export const REVEAL = G(5); // 2.600  the box is open: zoom-out reveal (the lid flies off just before)
export const CUT2 = G(4);   // 3.067  punch-in cut on the static box, the notes start pouring in
export const CUT3 = G(2);   // 4.033  punch-in cut: the hand brings the next bundle
export const FOLLOW = G(1); // 4.533  heartbeat punch on the hand lifting the next bundle (slow motion)
export const WHIP = snap(4.7); // the push down into the box starts: the camera follows it into the whip

export const SECTIONS = {
  open:    { start: 0.0, end: CUT1 },     // the notes fanned in the hand, "Wait..." / "is this legal?"
  move:    { start: CUT1, end: REVEAL },  // speed ramp through the camera's pan to the box, lid off
  box:     { start: REVEAL, end: CUT3 },  // slow-motion reveal of the box, then the notes pour in
  push:    { start: CUT3, end: FOLLOW },  // the next bundle, slow motion
  handoff: { start: FOLLOW, end: DURATION }, // the push down into the box, the camera follows it into the whip
};

// Sound cues (audio/build_intro.py vocabulary; riser / suck END at t, everything else starts at t).
export const CUES = [
  { t: 0.0, type: 'bass_hit' },                 // the footage starts on the hit, "Wait..." with it
  { t: 0.0, type: 'tension', dur: DURATION },   // low drone bed (F minor), swells over the hook
  { t: 0.0, type: 'accent', gain: -4 },         // "Wait..." punch on top of the hit
  { t: snap(0.6), type: 'accent', gain: -2 },   // "is this legal?" punch
  { t: snap(1.5), type: 'whoosh', dur: 0.45 },  // the swing + pan toward the box (peaks with the pan, ~1.76)
  { t: CUT1, type: 'pulse', gain: -9 },         // heartbeat starts on the cut, building to the drop
  { t: G(6), type: 'pulse', gain: -8 },
  { t: 2.4, type: 'whoosh', dur: 0.25, gain: -3 },  // the lid flies off (peaks ~2.55)
  { t: REVEAL, type: 'pulse', gain: -6 },
  { t: CUT2, type: 'pulse', gain: -5 },
  { t: G(3), type: 'pulse', gain: -4 },
  { t: CUT3, type: 'pulse', gain: -3 },
  { t: FOLLOW, type: 'pulse', gain: -2 },
  { t: DURATION, type: 'riser', dur: 1.6 },     // build into the reel's opening impact
  { t: DURATION, type: 'suck', dur: 0.5 },      // follows the push and the whip, stops dead on the cut
];

// Extra motion-blur sub-frames for camera moves: [start, end, samples]
export const FAST_MOTION = [
  [0.0, 0.4, 12],     // the opening hit settles + "Wait..." punch
  [0.58, 0.78, 12],   // "is this legal?" punch
  [1.62, 1.8, 8],     // beat punch
  [2.12, 2.3, 8],     // beat punch
  [2.46, 2.6, 12],    // type exits
  [2.6, 3.06, 16],    // zoom-out reveal of the box
  [3.55, 3.72, 12],   // beat punch
  [4.52, 4.7, 12],    // beat punch
  [4.7, 4.8, 24],     // the camera starts following the push
  [4.8, 5.0, 64],     // whip (~5 frames of motion blur)
];
export const samplesFor = (frame, base = 4, fastMax = 64) => {
  const t = frame / FPS;
  let n = base;
  for (const [a, b, k] of FAST_MOTION) if (t >= a && t < b) n = Math.max(n, Math.min(k, fastMax));
  return n;
};
/** 360° shutter on the whip frames, so each frame's streak reaches the next frame's (no stepping). */
export const shutterFor = (frame, def = 0.5) => (frame >= 143 ? 1.0 : def);
