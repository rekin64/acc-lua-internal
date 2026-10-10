// Single source of truth for timing. Pure data, no DOM: imported by the browser
// timeline AND exported to audio/timing.json (scripts/export-timing.mjs) so the
// soundtrack and the picture are always cut to the same grid.

export const FPS = 30;
export const DURATION = 15.0;
export const BPM = 125;
export const BEAT = 60 / BPM; // 0.48 s
export const beat = (n) => +(n * BEAT).toFixed(4);
/** Snap a time to the video frame grid (cuts must land on frame boundaries). */
export const snap = (t) => Math.round(t * FPS) / FPS;

// Storyboard sections (brief: 0 / 1.40 / 3.80 / 6.20 / 9.50 / 12.50 / 15.00),
// quantised to the 125 BPM beat grid.
export const SECTIONS = {
  title:    { start: beat(0),  end: beat(3)  }, // 0.00 – 1.44  "MEMECOIN SNIPING. REDEFINED."
  reveal:   { start: beat(3),  end: beat(8)  }, // 1.44 – 3.84  site reveal, "Built for speed."
  demo:     { start: beat(8),  end: beat(13) }, // 3.84 – 6.24  app: "Spot. Snipe. React."
  drop:     { start: beat(13), end: beat(20) }, // 6.24 – 9.60  trades: "Fast entries. Clean execution."
  montage:  { start: beat(20), end: beat(26) }, // 9.60 – 12.48 fast montage
  outro:    { start: beat(26), end: DURATION }, // 12.48 – 15.00 "SOL Sniper" / "Start Sniping."
};

// Music arrangement markers (seconds). The music is built to picture: each
// section starts a new phrase, so phrase lengths follow the edit.
export const MUSIC = {
  bpm: BPM,
  key: 'F minor',
  markers: [
    { t: 0.0,        name: 'intro',    note: 'Impact + dark pad swell, no drums. Reverse swell into 1.44.' },
    { t: beat(3),    name: 'groove_a', note: 'Kick on quarters (low-passed), sub pulses, filtered 16th pluck arp, soft offbeat hats. Chord: Fm9.' },
    { t: beat(8),    name: 'groove_b', note: 'Add light clap on 2 & 4, 8th hats, arp filter opens. Chord: Dbmaj7.' },
    { t: beat(11),   name: 'build',    note: 'Snare roll 8ths -> 16ths, riser, filter sweep up. Chord: Eb. Kick drops out at 6.00 (pre-drop gap).' },
    { t: beat(12.5), name: 'gap',      note: 'Pre-drop gap: only riser tail / reverse swell.' },
    { t: beat(13),   name: 'drop',     note: 'Full groove: kick 4/4, clap 2 & 4, open hats offbeat, sidechained rolling bass, chord stabs. Fm9 (3 beats) -> Dbmaj7 (2) -> Eb (2).' },
    { t: beat(20),   name: 'montage',  note: 'Drop continues + 16th hats + extra perc, accents on cut hits. Fm9 -> Db -> Eb -> Cm7, one chord per beat pair.' },
    { t: beat(25),   name: 'break',    note: 'Everything cuts except short riser / reverse swell into the outro.' },
    { t: beat(26),   name: 'outro',    note: 'Final impact, wide warm sustained chord (Dbmaj9 -> Abmaj9 / resolve bright), no drums. Tail rings out, clean fade to silence at 15.00.' },
  ],
};

const s = snap;
// Sound-design cues, aligned to the cut frames used by the timeline.
// gain is in dB relative to the type's default level; pan -1..1; dur in seconds where relevant.
// riser / reverse_swell / whip END at t; whooshes start at t.
export const CUES = [
  // 1 · Title
  { t: s(0.0),  type: 'impact_big' },
  { t: s(0.0),  type: 'text_reveal', gain: -4 },
  { t: s(beat(2)), type: 'tick', gain: -6 },                // "REDEFINED." turns brand
  { t: s(1.2),  type: 'whoosh_fast', gain: -5 },            // title masks out
  // 2 · Site reveal
  { t: s(beat(3)), type: 'whoosh_rise' },                   // cut to light + site card rises
  { t: s(beat(3)), type: 'hit_cut', gain: -6 },
  { t: s(beat(3.75)), type: 'whoosh_long', dur: 0.6 },      // push to the logo
  { t: s(beat(4)), type: 'text_reveal', gain: -8 },         // "Built for speed."
  { t: s(beat(5.75)), type: 'whoosh_long', dur: 0.48, pan: 0.2 }, // glide down to the hero
  { t: s(beat(7.6)), type: 'tap_soft', gain: -6 },          // cursor hover on CTA
  { t: s(beat(8)), type: 'click' },                         // click "Start Sniping"
  { t: s(beat(8)), type: 'zoom_through', dur: +(s(4.0) - s(beat(8))).toFixed(4) }, // thump on the cut into the app (4.00)
  // 3 · Demo
  { t: s(beat(9)),  type: 'ui_blip' },                      // Spot. new pair detected
  { t: s(beat(9) + 0.12), type: 'whoosh_fast', gain: -12, pan: 0.2 }, // punch onto AI 94
  { t: s(beat(10)), type: 'click' },                        // Snipe.
  { t: s(beat(10.6)), type: 'success', gain: -3 },          // filled
  { t: s(beat(11)), type: 'toast' },                        // React.
  { t: s(beat(13)), type: 'riser', dur: 0.96 },             // build into the drop
  { t: s(beat(13)), type: 'reverse_swell', dur: 0.6 },
  // 4 · Drop
  { t: s(beat(13)), type: 'whip', dur: +(s(beat(13)) - s(beat(12.72))).toFixed(4), pan: 0.3 }, // whip lands ON the drop
  { t: s(beat(13)), type: 'impact_drop' },
  { t: s(beat(14)), type: 'hit_cut', gain: -5 },            // hard cut to trade panel
  { t: s(beat(14)), type: 'whoosh_fast', pan: -0.3, gain: -8 },
  { t: s(beat(14.5)), type: 'click', gain: -3 },            // preset 0.5 SOL
  { t: s(beat(15)), type: 'click' },                        // Buy
  { t: s(beat(15.5)), type: 'success' },                    // filled
  { t: s(beat(15.6)), type: 'toast', gain: -3 },
  { t: s(beat(16)), type: 'whoosh_long', dur: 0.3, pan: 0.2 }, // pan to positions
  { t: s(beat(17)), type: 'tick', gain: -4 },               // GLINT position ticks
  { t: s(beat(18)), type: 'success', gain: -4 },            // take-profit hit
  { t: s(beat(18)), type: 'punch', gain: -6 },
  { t: s(beat(19)), type: 'whoosh_long', dur: 0.46, gain: -2 }, // pull out to full app
  // 5 · Montage
  { t: s(beat(20)), type: 'hit_cut' },
  { t: s(beat(20)), type: 'whoosh_fast', gain: -4 },
  { t: s(beat(21)), type: 'hit_cut', gain: -2 },
  { t: s(beat(21.25)), type: 'click', gain: -4 },
  { t: s(beat(22)), type: 'hit_cut', gain: -2 },
  { t: s(beat(22)), type: 'whoosh_fast', gain: -6, pan: -0.4 },
  { t: s(beat(23)), type: 'hit_cut', gain: -2 },
  { t: s(beat(23)), type: 'tick', gain: -6 },
  { t: s(beat(23.5)), type: 'hit_cut', gain: -4 },
  { t: s(beat(24)), type: 'hit_cut', gain: -2 },
  { t: s(beat(24)), type: 'success', gain: -8 },
  { t: s(beat(24.5)), type: 'hit_cut', gain: -4 },
  { t: s(beat(25)), type: 'hit_cut', gain: -1 },
  { t: s(beat(26)), type: 'riser', dur: 0.48 },
  { t: s(beat(26)), type: 'reverse_swell', dur: 0.48 },
  // 6 · Outro
  { t: s(beat(26)), type: 'impact_outro' },
  { t: s(beat(27.2)), type: 'text_reveal', gain: -8 },      // headline returns
  { t: s(beat(28.25)), type: 'whoosh_rise', gain: -8 },     // CTA springs in
  { t: s(beat(29.6)), type: 'tap_soft', gain: -8 },         // cursor hover
  { t: s(beat(30)), type: 'click_final' },                  // final click + payoff
];

// Fast camera moves get extra motion-blur sub-frames (smooth streaks instead of
// stepped copies): [start, end, samples]. Everything else uses the default count.
export const FAST_MOTION = [
  [1.43, 1.95, 24],   // card rise
  [1.80, 2.42, 48],   // push to the logo
  [2.76, 3.26, 32],   // glide down to the hero
  [3.83, 4.12, 48],   // zoom-through the CTA and landing in the app
  [4.44, 4.77, 24],   // punch onto AI 94
  [5.10, 5.60, 16],   // breathe out for the notification
  [6.10, 6.30, 48],   // whip pan landing on the drop
  [6.73, 7.20, 24],   // cursor-follow punch-ins (trade panel)
  [7.40, 7.98, 24],   // breathe out + pan to positions
  [8.10, 8.70, 24],   // punch to GLINT / FROGO rows
  [9.10, 9.60, 32],   // pull-out to the full terminal
  [12.30, 12.50, 32], // push into the outro match-cut
  [12.86, 13.40, 24], // logo glides up into the end card
  [14.40, 15.0, 16],  // cursor drifts off
];
export const samplesFor = (frame, base = 4, fastMax = 48) => {
  const t = frame / FPS;
  let n = base;
  for (const [a, b, k] of FAST_MOTION) if (t >= a && t < b) n = Math.max(n, Math.min(k, fastMax));
  return n;
};
