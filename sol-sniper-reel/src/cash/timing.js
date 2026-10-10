// New 5 s opening built from the client's cash footage (assets/source/cash-footage.mp4).
// It REPLACES reel 0.00-5.00; the reel continues unchanged from 5.00 (its frame 150).
// Cuts sit on the reel's own 125 BPM grid (beats at 0.48 s), so the original music
// keeps playing underneath; the transition lands on an added impact at exactly 5.00.
export const FPS = 30;
export const DURATION = 5.0;
export const BPM = 125;
const BEAT = 60 / BPM;
export const snap = (t) => Math.round(t * FPS) / FPS;
export const B = (n) => snap(n * BEAT);

export const CUES = [
  { t: 0.0, type: 'impact_big', gain: -1 },             // footage starts immediately on a hit
  { t: 0.0, type: 'accent', gain: 0 },                  // "Wait..." punch
  { t: B(1), type: 'accent', gain: -2 },                // "is this legal?" punch (0.47)
  { t: B(3), type: 'hit_cut', gain: -4 },               // jump cut + sped-up move to the box (1.43)
  { t: B(3), type: 'whoosh_fast', gain: -6, pan: -0.2 },
  { t: B(5), type: 'hit_cut', gain: -3 },               // the box opens: reveal punch-in (2.40)
  { t: B(5), type: 'whoosh_rise', gain: -8 },
  { t: B(6), type: 'tick', gain: -8 },                  // punch (2.87)
  { t: B(7), type: 'tick', gain: -7 },                  // punch (3.37)
  { t: B(8), type: 'hit_cut', gain: -4 },               // jump cut + punch on the groove's downbeat (3.83)
  { t: B(9), type: 'tick', gain: -6 },                  // punch (4.33)
  { t: 5.0, type: 'whip', dur: 0.4, pan: 0.0, dir: 0 }, // restrained whoosh following the hand down (centred: vertical move), ENDS at 5.00
  { t: 5.0, type: 'impact_drop', gain: -2 },            // the cut into the trading interface
];

// Extra motion-blur sub-frames for camera moves: [start, end, samples]
export const FAST_MOTION = [
  [0.0, 0.5, 12],     // the opening hit settles + "Wait..." punch
  [0.45, 0.62, 12],   // "is this legal?" punch
  [0.95, 1.12, 8],    // beat punch
  [1.42, 1.6, 8],     // beat punch on the type
  [1.92, 2.1, 8],     // beat punch
  [2.26, 2.4, 12],    // type exits
  [2.4, 3.05, 16],    // zoom-out reveal of the box
  [3.35, 3.52, 12],   // beat punch
  [4.32, 4.5, 12],    // beat punch
  [4.58, 4.83, 24],   // following the push
  [4.83, 5.0, 64],    // whip (~5 frames of heavy motion blur)
];
export const samplesFor = (frame, base = 4, fastMax = 64) => {
  const t = frame / FPS;
  let n = base;
  for (const [a, b, k] of FAST_MOTION) if (t >= a && t < b) n = Math.max(n, Math.min(k, fastMax));
  return n;
};
