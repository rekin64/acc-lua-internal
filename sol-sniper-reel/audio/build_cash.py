#!/usr/bin/env python3
"""SOL Sniper reel, cash version: sound design for the new 5 s opening (euro banknotes placed into a
shoe box) over the reel's own music, joined back into the untouched original soundtrack.

  python3 audio/build_cash.py        # -> audio/soundtrack_cash.wav (+ cash_analysis.txt, cash_join.png)

Options:
  --timing PATH   cue sheet of the new opening (default: audio/cash_timing.json, exported from
                  src/cash/timing.js; used as is, a warning is printed when timing.js is newer)
  --orig PATH     the finished original soundtrack (default: audio/soundtrack.wav; read only)
  --out DIR       output directory (default: audio/)
  --fast          skip the PNG
  --no-ffmpeg     skip every ffmpeg step: no AAC delivery guard, no ebur128 report

Reads (never modified): cash_timing.json; timing.json (the original cue sheet: the score is re-rendered
from it); stems/music.wav + stems/sfx.wav (the original pre-master stems); soundtrack.wav; analysis.txt.

Writes:
  soundtrack_cash.wav   48 kHz / 24-bit stereo, exactly 15.000 s (720000 samples). Samples [0, K) are the
                        new master (K = 240000 + L, see TRANSITION); every PCM frame from K on is copied
                        byte for byte from soundtrack.wav (bit-identical, never decoded or re-quantised).
  stems/cash_music.wav  new pre-master music bus   } one shared gain: music + sfx = the new pre-master mix
  stems/cash_sfx.wav    new pre-master SFX bus     } (the original stems' domain, trimmed for 1 dB headroom)
  cash_analysis.txt     method + reproduction residual, loudness (full / 0-5 new vs original / 5-15), WAV and
                        AAC-delivery true peaks, the filter-down, the cut at 5.000, the impact tail and the
                        crossfade back, bit-identity, cue alignment, clicks / DC / silence
  cash_join.png         the cut at 5.000 s (+-40 ms waveform), 4.3-6.2 s envelopes new vs original with the
                        filter cutoff, and the new-minus-original difference (nothing left from K on)

CUE SEMANTICS (cash_timing.json `cues`: {t, type, gain?, pan?, dir?, dur?}; same rules as build_audio.py)
  t      seconds. Onset cues put their transient ON the sample round(t * 48000) (no pre-roll); END-ALIGNED
         cues (whip, riser, reverse_swell) end on that sample instead.
  gain   dB offset from the type's default level (sndkit/sfx.py LEVELS / PEAK_CAP; accent: ACCENT_LEVEL).
  pan / dir / dur   as build_audio.py.
  accent       sndkit/intro_fx.py's felt text punch (thump onto F2 + locked sub + knock + soft tick), rendered
               exactly as build_intro.py renders it (its dark hall / room, the hook's bus EQ) and level-mapped
               into this pre-master domain: ACCENT_LEVEL (see below).
  every other type: sndkit/sfx.py render_cue with the score as context (grid kicks / claps, harmony),
               exactly as build_audio.py (e.g. a hit_cut 1-20 ms off a grid kick drops its low knock).
  Music ducking under the new cues: build_audio.py's logic and sndkit/sfx.py DUCK table, unchanged.

METHOD (one master chain for the whole 15 s, then a splice back into the original)
  1. Score: build_audio.build() on the ORIGINAL timing.json re-renders the original music + SFX buses
     (deterministic). Their stems are checked against stems/*.wav to the LSB, and build_audio's cue ducking
     is re-applied and checked too: the music bus BEFORE that ducking is the original music with the old
     picture's ducks taken out (same notes, same grid, same level).
  2. New pre-master, in the original stems' domain (stem gain reproduced from build_audio.main):
     music  0 - 5.000: that undocked original music, ducked for the NEW cues (build_audio DUCK logic), then
                       the filter-down into the cut (FILTER_*); from 5.000: stems/music.wav itself. The
                       impact's own light broadband duck (DUCK['impact_drop']) acts over 5.0-5.4 s.
     sfx    the new cues incl. their reverb tails, held to 5.000 + TAIL_HOLD and faded to silence by
            5.000 + TAIL_END (the impact's long hall is cut short there, under the reel), plus stems/sfx.wav
            from 5.000 on (SFX_FADE_IN raised-cosine fade-in: only the old cues' ~-60 dBFS reverb tails are
            there). The original 0-5 s SFX belonged to the old picture: none of them is kept before 5.000.
  3. Master: sndkit/master.py's chain (hp 18 Hz, normalisation, glue comp, make-up gain, soft clip, 4x
     true-peak limiter at TP_CEILING, end fade) with BOTH gains fixed to the original master's: the
     normalisation gain of the original pre-master and its make-up gain (+4.38 dB, analysis.txt). They are
     reproduced, not typed in: MS.master() run on the original stems gives soundtrack.wav back within a few
     LSB (reported), and master_fixed() == MS.master() bit for bit on those stems. Same chain + same gains
     -> once the new material has gone (5.000 + TAIL_END), the new master converges onto soundtrack.wav.
  4. Splice: new master on [0, K - XFADE); equal-gain raised-cosine crossfade (gains sum to 1, both sides
     the same program, so phase-coherent) into soundtrack.wav over [K - XFADE, K); soundtrack.wav's own PCM
     bytes from K = 240000 + round((TAIL_END + XFADE) * 48000) on.
  AAC delivery guard (as build_audio.py / build_intro.py): the spliced file is encoded exactly like
  scripts/encode.py (ffmpeg native AAC-LC 320k, 48 kHz), decoded and measured (4x true-peak meter + ffmpeg
  ebur128). Wherever the decoded AAC exceeds AAC_TP_TARGET inside [0, K), a smooth post-limiter gain dip is
  added there and the new part is re-mastered (closed loop). Nothing past K can change (reported only).

TRANSITION (the cut at 5.000 s = sample 240000)
  4.52-4.56   music crossfades into a time-varying low-pass (2 x RBJ biquad, Q FILTER_Q) parked at 20 kHz
  4.56-4.98   the cutoff sweeps 20 kHz -> FILTER_F1 (log frequency, accelerating) and the music dips
              FILTER_DIP_DB (smoothstep); held to the cut. The whip (4.60 -> 5.000) carries the movement.
  5.000       impact_drop transient on sample 240000; the full, dry music returns under it (FILTER_RETURN
              raised cosine) and the reel's own SFX stem fades in (SFX_FADE_IN)
  +TAIL_HOLD -> +TAIL_END   every new sound (impact hall, whip room, ...) fades to silence under the reel
  K - XFADE -> K            crossfade into soundtrack.wav; bit-identical from K on

Python 3 + numpy + scipy only (PIL for the PNG). No samples, fixed seeds -> bit-identical output on every
run (with the same ffmpeg build for the AAC guard).
"""
import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import wave  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from scipy.ndimage import convolve1d, maximum_filter1d, uniform_filter1d  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_audio as BA  # noqa: E402  (io, build(), AAC round trip; importing it has no side effects)
import build_intro as BI  # noqa: E402  (frame-level wav io, low-band onset detector)
from sndkit import intro_fx as IFX  # noqa: E402
from sndkit import master as MS  # noqa: E402
from sndkit import music as MU  # noqa: E402
from sndkit import report as R  # noqa: E402
from sndkit import sfx as FX  # noqa: E402
from sndkit.dsp import (SR, add_at, convolve_ir, cos_ramp, duck_env, event_duck, hp, make_ir, ns, smoothstep,  # noqa: E402
                        tv_biquad, zp)

N = 720000                 # 15.000 s
N_CUT = 240000             # 5.000 s: the cut into the reel (and the impact's transient)
TARGET_LUFS = BA.TARGET_LUFS      # -14.0 (the original master's target; its make-up gain is reused as is)
TP_CEILING = BA.TP_CEILING        # -2.5 dBTP WAV limiter ceiling, as the original
AAC_TP_TARGET = BA.AAC_TP_TARGET  # -1.5 dBTP decoded AAC (spec <= -1.0)
FADE_OUT = BA.FADE_OUT            # the master's end fade (only matters for the reproduction)

# accent level (loudest 10 ms RMS, dB) in THIS pre-master domain. intro_fx.LEVELS['accent'] = -6 dB lives in
# the hook's pre-master domain, which build_intro normalised by -2.26 dB and mastered with +3.70 dB
# (= +1.44 dB); the reel's pre-master is normalised by -1.27 dB and mastered with +4.38 dB (= +3.12 dB). Same
# loudness after the master -> -6 + 1.44 - 3.12 = -7.7 dB.
ACCENT_LEVEL = -7.7
IFX_TYPES = ('accent',)

# pre-transition move on the music bus (see TRANSITION)
FILTER_START = 4.56        # 8th note before beat 10 (4.80)
FILTER_IN = 0.04           # dry -> filter path crossfade before FILTER_START (cutoff parked at FILTER_F0)
FILTER_LOW = 4.98          # cutoff reaches FILTER_F1 here, held to the cut
FILTER_F0 = 20000.0
FILTER_F1 = 500.0
FILTER_CURVE = 1.2         # log-frequency progress = u ** FILTER_CURVE (u: 0 at FILTER_START, 1 at FILTER_LOW)
FILTER_Q = 0.9             # per stage (2 stages): a gentle resonance, the 'classic' filter colour
FILTER_DIP_DB = -7.0       # broadband dip, smoothstep over FILTER_START -> FILTER_LOW
FILTER_RETURN = 0.004      # s: filtered -> full dry music, raised cosine starting ON sample 240000
SFX_FADE_IN = 0.005        # s: the original SFX stem fades in from sample 240000

# the new sound design after the cut, and the splice back into soundtrack.wav
TAIL_HOLD = 0.30           # s after the cut: impact + tails at full level
TAIL_END = 0.72            # s after the cut: raised-cosine fade reaches silence
XFADE = 0.12               # s: equal-gain crossfade into soundtrack.wav, [K - XFADE, K)
L_NEW = TAIL_END + XFADE   # s of new master after the cut
K = N_CUT + ns(L_NEW)      # first sample copied from soundtrack.wav
SFX_SPAN = 6.4             # s: the new cues (and their reverbs) are rendered over [0, SFX_SPAN)

BW = 2 * 3                 # bytes per PCM frame (2 ch, 24 bit)


# --------------------------------------------------------------------------- io
def _md5(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def pcm_ints(frames, ch=2):
    """Raw 24-bit little-endian PCM frame bytes -> int32 (ch, n)."""
    raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    v = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
    v = np.where(v >= 1 << 23, v - (1 << 24), v)
    return v.reshape(-1, ch).T


def pcm_bytes(x):
    """Float (2, n) -> 24-bit PCM frame bytes, quantised exactly like build_audio.write_wav24."""
    x = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0 - 2.0 ** -23)
    q = np.round(x.T * 8388607.0).astype(np.int32).reshape(-1)
    b = np.empty((q.size, 3), dtype=np.uint8)
    b[:, 0] = q & 0xFF
    b[:, 1] = (q >> 8) & 0xFF
    b[:, 2] = (q >> 16) & 0xFF
    return b.tobytes()


def write_frames(path, frames, ch=2):
    with wave.open(path, 'wb') as w:
        w.setnchannels(ch)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(frames)


def read_float(path):
    """-> float (2, n) on write_wav24's scale (int / 8388607), so a value re-quantises to its own int."""
    p, fr = BI.wav_frames(path)
    assert (p.nchannels, p.sampwidth, p.framerate) == (2, 3, SR), p
    return pcm_ints(fr) / 8388607.0, fr


def splice_bytes(new, orig_frames):
    """Frames [0, K) from the float array `new`, frames [K, N) = soundtrack.wav's own bytes."""
    return pcm_bytes(new[:, :K]) + orig_frames[K * BW:]


# --------------------------------------------------------------------------- the original
def original_score(timing, log):
    """Re-render the original reel's music + SFX buses with build_audio.build() and reproduce the stems'
    common gain (build_audio.main). -> dict (LEVELS domain arrays + stem_gain + build info)."""
    binfo = {}
    music_d, sfx_o, tracks, kick_trig = BA.build(timing, log, binfo)
    music_raw = sum(tracks.values())  # calibrated music bus BEFORE build_audio's cue ducking
    pre = music_d + sfx_o
    g0 = 10.0 ** ((-18.0 - MS.integrated_lufs(pre)) / 20.0)
    pk = max(np.max(np.abs(music_d)), np.max(np.abs(sfx_o))) * g0
    stem_gain = g0 * min(1.0, 10.0 ** (-1.0 / 20.0) / pk)
    return dict(music_d=music_d, sfx=sfx_o, music_raw=music_raw, tracks=tracks, kick_trig=kick_trig,
                events=binfo['events'], stem_gain=stem_gain)


def duck_music(music, cues):
    """build_audio.build()'s music ducking under `cues` (sndkit/sfx.py DUCK), operation for operation.
    -> (ducked music, broadband gain curve)."""
    n = music.shape[1]
    ev = {'ui': [], 'tone': [], 'full': []}
    for cue in cues:
        d = FX.DUCK.get(cue['type'])
        if d:
            band, depth, hold, rel = d
            if band == 'full':
                depth = max(depth + 0.5 * float(cue.get('gain', 0.0)), 0.5)  # quieter hit -> lighter dip
            ev[band].append((ns(cue['t']), depth, hold, 0.004, rel))
    g_full = event_duck(n, ev['full'])
    for band_name, (lo, hi) in (('ui', (1000.0, 8000.0)), ('tone', (500.0, 8000.0))):
        if ev[band_name]:
            g = event_duck(n, ev[band_name])
            band = zp(music, 'bandpass', [lo, hi], 2)
            music = music - band + band * g[None, :]
    return music * g_full[None, :], g_full


# --------------------------------------------------------------------------- master
def master_fixed(pre, norm_db, g_db, guard_db=None, ceiling=TP_CEILING, fade_out=FADE_OUT):
    """sndkit/master.py master() with its two gains FIXED instead of measured / iterated: `norm_db` replaces
    the -18 LUFS normalisation of THIS input, `g_db` the make-up gain loop. Every other step is the same
    call with the same arguments (hp 18 Hz -> glue comp -> make-up -> soft clip -> 4x true-peak limiter ->
    [codec guard dip] -> end fade), so on the original stems it returns MS.master()'s output bit for bit."""
    x = hp(pre, 18.0, 2)
    x *= 10.0 ** (norm_db / 20.0)
    x, gr = MS.glue_comp(x, thr_db=-13.5, ratio=2.0, attack=0.02, release=0.18, knee=6.0)
    n = x.shape[1]
    fade = MS.end_fade(n, fade_out)
    post = fade if guard_db is None else fade * 10.0 ** (-np.asarray(guard_db, dtype=float) / 20.0)
    y = x * 10.0 ** (g_db / 20.0)
    y = MS.soft_clip(y, thr=10.0 ** ((ceiling - 1.5) / 20.0))
    y, lg = MS.limiter(y, ceiling)
    y = y * post[None, :]
    glue_t = (np.arange(len(gr)) + 0.5) * 48 / SR
    return y, dict(gain_db=g_db, norm_db=norm_db, limiter_gain=lg, limiter_gr_db=float(-20 * np.log10(lg.min())),
                   glue_gr=gr, glue_gr_db=float(gr.max()), glue_t=glue_t)


def reproduce_master(stem_music, stem_sfx, orig_ints, log):
    """Prove the master chain + gains: MS.master() (its own normalisation and make-up loop, started at
    4.0 dB like build_audio) on the original stems vs soundtrack.wav, and master_fixed() vs MS.master()."""
    pre = stem_music + stem_sfx
    norm_db = -18.0 - MS.integrated_lufs(hp(pre, 18.0, 2))
    out, minfo = MS.master(pre, TARGET_LUFS, TP_CEILING, FADE_OUT, log=log, g_db=4.0)
    g_db = float(minfo['gain_db'])
    q = np.round(np.clip(out, -1.0, 1.0 - 2.0 ** -23) * 8388607.0).astype(np.int64)
    d = q - orig_ints
    out2, _ = master_fixed(pre, norm_db, g_db)
    return dict(norm_db=norm_db, g_db=g_db, max_lsb=int(np.abs(d).max()), rms_lsb=float(np.sqrt(np.mean(d ** 2.0))),
                n_diff=int(np.count_nonzero(np.any(d != 0, axis=0))),
                max_dbfs=float(20 * np.log10(max(np.abs(d).max(), 1e-9) / 8388607.0)),
                fixed_vs_master=float(np.abs(out2 - out).max()), lufs=MS.integrated_lufs(out))


def analysis_makeup():
    """The make-up gain printed in audio/analysis.txt (build_audio's log), for the cross-check."""
    p = os.path.join(HERE, 'analysis.txt')
    if not os.path.exists(p):
        return None
    with open(p) as f:
        m = re.search(r'make-up gain ([+-][\d.]+) dB', f.read())
    return float(m.group(1)) if m else None


# --------------------------------------------------------------------------- the new opening
def reel_irs():
    """build_audio.build()'s SFX reverbs (same make_ir calls) -> {bus: (ir, return gain)}."""
    return dict(hall_big=(make_ir(4.2, 3.3, 1.5, seed=13, predelay=0.016, hp_f=140.0, lp_f=8500.0), 0.9),
                room=(make_ir(0.6, 0.36, 0.24, seed=14, predelay=0.004, hp_f=450.0, lp_f=11000.0, er_span=0.02), 1.0),
                plate=(make_ir(2.0, 1.4, 1.1, seed=15, predelay=0.012, hp_f=500.0, lp_f=12000.0), 0.8),
                glue=(make_ir(2.8, 2.2, 1.0, seed=11, predelay=0.024, hp_f=230.0, lp_f=9000.0), 1.0))


def hook_irs():
    """build_intro.build()'s reverbs (the accent's own space) -> {bus: (ir, return gain)}."""
    return dict(hall=(make_ir(4.0, 3.0, 1.3, seed=41, predelay=0.022, hp_f=140.0, lp_f=5200.0, er_span=0.05), 0.9),
                room=(make_ir(0.7, 0.45, 0.28, seed=42, predelay=0.005, hp_f=250.0, lp_f=8000.0, er_span=0.02), 1.0))


def render_cues(cues, orig, log):
    """Every cue rendered in isolation (dry + its own reverb returns) over [0, SFX_SPAN), LEVELS domain.
    Reverb is linear, so the sum of the isolated renders is build_audio's shared-bus mix.
    -> (sfx, per-cue dict idx -> {'iso': dry + wet, 'dry': dry (END_ALIGNED only)}, render notes)."""
    n = ns(SFX_SPAN)
    t0 = time.time()
    irs = {'reel': reel_irs(), 'hook': hook_irs()}
    ir_swell = make_ir(2.8, 2.5, 1.4, seed=16, predelay=0.0, hp_f=200.0, lp_f=9000.0)
    log(f'  IRs {time.time() - t0:.1f}s')

    def riser_target(t):
        root = MU.CHORDS[MU.chord_at(round(t / MU.BEAT))]['root']
        return 60 + (root - 60) % 12

    tracks = orig['tracks']
    ctx = dict(riser_target=riser_target, swell_chord=lambda t: MU.CHORDS[MU.chord_at(round(t / MU.BEAT))]['pad'],
               ir_swell=ir_swell, cues=cues, kick_trig=orig['kick_trig'], clap_trig=orig['events']['clap'],
               chord_at_time=MU.chord_at_time, kick_track=np.mean(tracks['kick'], axis=0),
               chord_tones=lambda t: (MU.CHORDS[MU.chord_at_time(t + 0.01)]['root'],
                                      MU.CHORDS[MU.chord_at_time(t + 0.01)]['pad']),
               notes={}, soft_onset=set())
    t0 = time.time()
    sfx = np.zeros((2, n))
    per = {}
    for i, cue in enumerate(cues):
        hook = cue['type'] in IFX_TYPES
        if hook:
            lay = IFX.render_cue(cue, i, {})
            g = 10.0 ** ((ACCENT_LEVEL - IFX.LEVELS[cue['type']]) / 20.0)
            lay = [(sig * g, off, snd) for sig, off, snd in lay]
            ctx['notes'][i] = 'intro_fx accent (hook hall/room + bus EQ)'
        else:
            lay = FX.render_cue(cue, i, ctx)
        s = ns(cue['t'])
        dry = np.zeros((2, n))
        feeds = {}
        for sig, off, sends in lay:
            add_at(dry, sig * sends.get('_dry', 1.0), s + off)
            for bus, g in sends.items():
                if bus != '_dry' and g:
                    feeds.setdefault(bus, np.zeros((2, n)))
                    add_at(feeds[bus], sig * g, s + off)
        wet = np.zeros((2, n))
        for bus in sorted(feeds):
            ir, gain = irs['hook' if hook else 'reel'][bus]
            wet += convolve_ir(feeds[bus], ir) * gain
        if hook:
            dry, wet = IFX.bus_eq(dry), IFX.bus_eq(wet)  # linear: the hook's bus EQ on this cue's share
        iso = dry + wet
        sfx += iso
        nz = np.flatnonzero(np.any(dry != 0.0, axis=0))
        per[i] = dict(iso=iso, dry=dry if cue['type'] in FX.END_ALIGNED else None,
                      first=int(nz[0]) if len(nz) else None, last=int(nz[-1]) if len(nz) else None)
    log(f'  cues {time.time() - t0:.1f}s')
    return sfx, per, ctx['notes']


def filter_down(m):
    """The pre-transition move on the music bus (see TRANSITION). -> (music, info)."""
    a0 = ns(FILTER_START - FILTER_IN - 0.1)  # 0.1 s warm-up for the filter state (output unused there)
    b0 = N_CUT + ns(FILTER_RETURN)
    t = np.arange(a0, b0) / SR
    u = np.clip((t - FILTER_START) / (FILTER_LOW - FILTER_START), 0.0, 1.0)
    fc = FILTER_F0 * (FILTER_F1 / FILTER_F0) ** (u ** FILTER_CURVE)
    filt = tv_biquad(m[:, a0:b0], 'lowpass', fc, FILTER_Q, block=16, stages=2)
    dip = 10.0 ** (FILTER_DIP_DB * smoothstep(u) / 20.0)
    x = np.zeros(b0 - a0)
    i_in0, i_in1 = ns(FILTER_START - FILTER_IN) - a0, ns(FILTER_START) - a0
    x[i_in0:i_in1] = cos_ramp(i_in1 - i_in0)
    x[i_in1:] = 1.0
    r = ns(FILTER_RETURN)
    x[N_CUT - a0:] = 1.0 - cos_ramp(r)
    out = m.copy()
    out[:, a0:b0] = m[:, a0:b0] * (1.0 - x) + filt * (dip * x)[None, :]
    return out, dict(a0=a0, t=t, fc=fc, dip=dip, x=x)


def tail_env():
    """Gain on every new sound: 1 to the cut + TAIL_HOLD, raised cosine to 0 at the cut + TAIL_END."""
    e = np.ones(N)
    a, b = N_CUT + ns(TAIL_HOLD), N_CUT + ns(TAIL_END)
    e[a:b] = cos_ramp(b - a)[::-1]
    e[b:] = 0.0
    return e


def yield_to_reel(new, orig, reel_cues):
    """After the cut the reel has priority: the new sounds still ringing there (impact tail, whip room) are
    ducked by the reel's own events, with the rules the reel's music already follows:
      - its UI sounds (success, toast, ...) duck the new sounds' band exactly as they duck the music
        (build_audio DUCK logic), so they keep the space they had in the original;
      - its grid kicks side-chain the new sounds below 150 Hz (depth / release of the score's bass
        sidechain, sndkit/music.py), so the impact's sub tail doesn't thin out the build's first kick.
    -> (new, info)"""
    after = [c for c in reel_cues if N_CUT <= ns(c['t']) < K]
    new, _ = duck_music(new, after)
    kicks = [(s, v) for s, v in orig['events']['kick'] if N_CUT < s < K]
    g = np.ones(N)
    if kicks:
        g = duck_env(N, [s for s, _ in kicks], [min(v, 0.88) for _, v in kicks], release=0.11)
        lo = zp(new, 'lowpass', 150.0, 4)
        new = new - lo + lo * g[None, :]
    return new, dict(ui=[f"{c['type']}@{c['t']:.3f}" for c in after if c['type'] in FX.DUCK],
                     kicks=[(s, v) for s, v in kicks], g_kick=g)


def build(cues, reel_cues, orig, stem_music, stem_sfx, log):
    """-> (music bus, sfx bus) of the new 15 s pre-master (stem domain) + info."""
    sg = orig['stem_gain']
    # music: the original music without the old picture's ducks, ducked for the new cues before the cut
    pre_cut = [c for c in cues if ns(c['t']) < N_CUT]
    post_cut = [c for c in cues if ns(c['t']) >= N_CUT]
    m_new, _ = duck_music(orig['music_raw'] * sg, pre_cut)
    music = np.concatenate([m_new[:, :N_CUT], stem_music[:, N_CUT:]], axis=1)
    join_step = float(np.abs(m_new[:, N_CUT - 1:N_CUT + 1] - stem_music[:, N_CUT - 1:N_CUT + 1]).max())
    music, g_post = duck_music(music, post_cut)  # the impact's light broadband duck (over the cut)
    music, finfo = filter_down(music)
    # sfx: the new cues (faded out after the cut) + the reel's own SFX stem from the cut on
    sfx_new, per, notes = render_cues(cues, orig, log)
    tail = tail_env()
    new = np.zeros((2, N))
    new[:, :sfx_new.shape[1]] = sfx_new * sg
    new *= tail[None, :]
    new, yinfo = yield_to_reel(new, orig, reel_cues)
    fin = np.zeros(N)
    nf = ns(SFX_FADE_IN)
    fin[N_CUT:N_CUT + nf] = cos_ramp(nf)
    fin[N_CUT + nf:] = 1.0
    old = stem_sfx * fin[None, :]
    info = dict(per=per, notes=notes, finfo=finfo, tail=tail, new_sfx=new, old_sfx=old, music_new0=m_new,
                g_post=g_post, join_step=join_step, yinfo=yinfo)
    return music, new + old, info


def master_for_delivery(pre, rep, orig_f, orig_frames, log, use_ffmpeg):
    """Master the new pre-master with the original's fixed gains; splice; encode the spliced file like
    scripts/encode.py and dip the new part (post-limiter, smooth) wherever its decoded AAC true peak exceeds
    AAC_TP_TARGET; re-master until it passes (closed loop, as build_audio.master_for_delivery).
    -> (new master float, spliced float, minfo, aac info or None)."""
    guard = np.zeros(N)
    aac = None
    ffmpeg_ok = use_ffmpeg and shutil.which('ffmpeg') is not None
    if use_ffmpeg and not ffmpeg_ok:
        log('WARNING: ffmpeg not found: AAC delivery guard skipped (WAV ceiling only)')
    win = np.hanning(ns(0.01) + 1)
    win /= win.sum()
    with tempfile.TemporaryDirectory() as td:
        for rnd in range(10):
            out, minfo = master_fixed(pre, rep['norm_db'], rep['g_db'], guard_db=guard if guard.any() else None)
            full = splice(out, orig_f)
            log(f"  master pass {rnd}: fixed gains (norm {rep['norm_db']:+.4f} dB, make-up {rep['g_db']:+.4f} dB), "
                f"limiter max GR {minfo['limiter_gr_db']:.2f} dB, glue comp max GR {minfo['glue_gr_db']:.2f} dB")
            if not ffmpeg_ok:
                break
            p = os.path.join(td, 'cash.wav')
            write_frames(p, splice_bytes(full, orig_frames))
            dec, ff, _ = BA.aac_roundtrip(p, td)
            env = MS._tp_envelope(dec)[:N]
            tp_new = float(20 * np.log10(env[:K].max()))
            tp_rest = float(20 * np.log10(env[K:].max()))
            tp = max(tp_new, tp_rest, ff['TP'] if ff and ff['TP'] is not None else -np.inf)
            ok = tp <= AAC_TP_TARGET
            aac = dict(tp_new=tp_new, tp_rest=tp_rest, ff=ff, rounds=rnd + 1, ok=ok)
            log(f'  AAC guard pass {rnd}: decoded true peak: new part {tp_new:.2f} dBTP, original part {tp_rest:.2f} dBTP '
                f'(ebur128 {ff["TP"]} dBFS), I {ff["I"]} LUFS -> {"OK" if ok else "over " + f"{AAC_TP_TARGET:.1f}"}')
            if ok:
                break
            if tp_new <= AAC_TP_TARGET:
                log('WARNING: the AAC overshoot is in the part copied from soundtrack.wav, which must not change')
                break
            need = np.maximum(20 * np.log10(np.maximum(env, 1e-9)) - (AAC_TP_TARGET - 0.15), 0.0)
            need[K:] = 0.0
            need = maximum_filter1d(need, size=2 * 2048 + 1, mode='nearest')
            guard += convolve1d(need, win, mode='nearest')
            guard[K:] = 0.0
    minfo['guard_db'] = guard
    return out, full, minfo, aac


def splice(new, orig_f):
    """new master on [0, K - XFADE), equal-gain raised-cosine crossfade into the original on [K - XFADE, K),
    the original from K on (as floats; the file takes its bytes from K on)."""
    out = orig_f.copy()
    a = K - ns(XFADE)
    out[:, :a] = new[:, :a]
    w = cos_ramp(K - a)  # 0 -> 1; (1 - w) + w = 1
    out[:, a:K] = new[:, a:K] * (1.0 - w)[None, :] + orig_f[:, a:K] * w[None, :]
    return out


# --------------------------------------------------------------------------- analysis
def _rms_db(x, a, b):
    return 20 * np.log10(np.sqrt(np.mean(np.atleast_2d(x)[:, a:b] ** 2)) + 1e-12)


def _click_ratio(x):
    """build_audio's click metric per sample: |2nd difference| over its local (20 ms) RMS, max over channels."""
    d2 = np.abs(np.diff(x, n=2, axis=1))
    loc = np.sqrt(uniform_filter1d(d2 ** 2, size=ns(0.02), axis=1, mode='nearest')) + 1e-9
    return np.max(d2 / loc, axis=0)


def _mom_within(x, t0, t1):
    tm, lm = MS.momentary(x)
    sel = (tm - 0.4 >= t0 - 1e-9) & (tm <= t1 + 1e-9)
    return tm[sel], lm[sel]


def _short_within(x, t0, t1):
    ts, ls = MS.short_term(x)
    sel = (ts - 3.0 >= t0 - 1e-9) & (ts <= t1 + 1e-9)
    return ts[sel], ls[sel]


def join_png(path, out, orig, finfo, cues):
    W, H = 1800, 1010
    im = Image.new('RGB', (W, H), (250, 250, 252))
    d = ImageDraw.Draw(im)
    f13, f11 = R._font(13), R._font(11)
    d.text((20, 10), 'Cash version: the cut at 5.000 s (sample 240000) and the splice back into soundtrack.wav '
                     f'(bit-identical from sample {K} = {K / SR:.3f} s)', fill=(20, 20, 30), font=R._font(15))
    ml, pw = 70, W - 90
    # 1. +-40 ms waveform around the cut
    a, b = N_CUT - ns(0.04), N_CUT + ns(0.04)
    y0, ph = 40, 270
    d.rectangle([ml, y0, ml + pw, y0 + ph], outline=(215, 215, 222), fill=(255, 255, 255))
    pk = np.max(np.abs(out[:, a:b])) + 1e-9
    xs = ml + (np.arange(b - a) / (b - a - 1)) * pw
    for c, col in ((1, (160, 170, 220)), (0, (40, 50, 110))):
        ys = y0 + ph / 2 - out[c, a:b] / pk * (ph / 2 - 10)
        d.line(list(zip(xs.tolist(), ys.tolist())), fill=col, width=1)
    xc = ml + (N_CUT - a) / (b - a - 1) * pw
    d.line([(xc, y0), (xc, y0 + ph)], fill=(220, 40, 40), width=1)
    for msec in (-40, -30, -20, -10, 0, 10, 20, 30, 40):
        xx = ml + (ns(msec / 1000) + N_CUT - a) / (b - a - 1) * pw
        d.text((xx - 12, y0 + ph + 4), f'{msec:+d} ms', fill=(80, 80, 90), font=f11)
    d.text((ml + 6, y0 + 4), f'+-40 ms around 5.000 s: whip stop (left) -> impact_drop transient on sample 240000 (red); '
                             f'L dark, R light; peak {20 * np.log10(pk):.1f} dBFS', fill=(20, 20, 30), font=f13)
    # 2. envelopes 4.3 - 6.2 s
    t_a, t_b = 4.30, 6.20
    a, b = ns(t_a), ns(t_b)
    y0, ph = 340, 380
    d.rectangle([ml, y0, ml + pw, y0 + ph], outline=(215, 215, 222), fill=(255, 255, 255))
    lo_db = -60.0
    X = lambda s: ml + (s - a) / (b - a - 1) * pw
    Y = lambda v: y0 + np.clip(-v / -lo_db, 0, 1) * ph
    k0, k1 = K - ns(XFADE), K
    d.rectangle([X(k0), y0 + 1, X(k1), y0 + ph - 1], fill=(225, 245, 228))
    t_h, t_e = N_CUT + ns(TAIL_HOLD), N_CUT + ns(TAIL_END)
    d.rectangle([X(t_h), y0 + 1, X(t_e), y0 + ph - 1], fill=(252, 240, 222))
    fs, fe = ns(FILTER_START), ns(FILTER_LOW)
    d.rectangle([X(fs), y0 + 1, X(fe), y0 + ph - 1], fill=(238, 234, 250))
    for lv in (-10, -20, -30, -40, -50):
        yy = Y(lv)
        d.line([(ml, yy), (ml + pw, yy)], fill=(230, 230, 236))
        d.text((8, yy - 7), f'{lv} dB', fill=(90, 90, 100), font=f11)
    step = 48
    for sig, col, wd in ((orig, (175, 175, 182), 3), (out, (40, 50, 110), 1)):
        e = np.sqrt(uniform_filter1d(np.mean(sig[:, a:b] ** 2, axis=0), ns(0.005)))
        edb = 20 * np.log10(e + 1e-9)
        idx = np.arange(0, b - a, step)
        d.line(list(zip(X(a + idx).tolist(), Y(edb[idx]).tolist())), fill=col, width=wd)
    # filter cutoff (right axis, log 200 Hz - 20 kHz)
    fa = finfo['a0']
    t_f = np.arange(len(finfo['fc']))
    sel = (fa + t_f >= ns(FILTER_START - FILTER_IN)) & (fa + t_f <= N_CUT)
    fy = lambda f: y0 + (np.log(20000.0) - np.log(f)) / (np.log(20000.0) - np.log(200.0)) * ph
    pts = [(X(fa + i), fy(finfo['fc'][i])) for i in t_f[sel][::step]]
    d.line(pts, fill=(140, 90, 210), width=2)
    for f in (500, 2000, 8000, 20000):
        d.text((ml + pw + 2, fy(f) - 7), f'{f / 1000:g}k', fill=(140, 90, 210), font=f11)
    d.line([(X(N_CUT), y0), (X(N_CUT), y0 + ph)], fill=(220, 40, 40), width=1)
    d.line([(X(K), y0), (X(K), y0 + ph)], fill=(30, 150, 60), width=2)
    whip = [c for c in cues if c['type'] == 'whip']
    if whip:
        ws = ns(whip[0]['t'] - float(whip[0].get('dur', 0.15)))
        d.line([(X(ws), y0 + ph - 30), (X(ws), y0 + ph)], fill=(110, 110, 200), width=2)
        d.text((X(ws) + 3, y0 + ph - 28), 'whip', fill=(110, 110, 200), font=f11)
    d.text((ml + 6, y0 + 4), '5 ms RMS (dBFS): soundtrack_cash.wav (dark) vs soundtrack.wav (grey).  Shaded: filter sweep '
                             '(violet; cutoff = violet line, right axis), tail fade (orange), crossfade (green); '
                             'red = cut, green line = K', fill=(20, 20, 30), font=f13)
    for s in np.arange(4.4, 6.21, 0.2):
        d.text((X(ns(s)) - 12, y0 + ph + 4), f'{s:.1f}s', fill=(80, 80, 90), font=f11)
    # 3. difference new - original
    y0, ph = 760, 200
    d.rectangle([ml, y0, ml + pw, y0 + ph], outline=(215, 215, 222), fill=(255, 255, 255))
    lo2 = -120.0
    Y2 = lambda v: y0 + np.clip(-v / -lo2, 0, 1) * ph
    d.rectangle([X(k0), y0 + 1, X(k1), y0 + ph - 1], fill=(225, 245, 228))
    for lv in (-20, -40, -60, -80, -100):
        yy = Y2(lv)
        d.line([(ml, yy), (ml + pw, yy)], fill=(230, 230, 236))
        d.text((8, yy - 7), f'{lv} dB', fill=(90, 90, 100), font=f11)
    diff = out[:, a:b] - orig[:, a:b]
    e = np.sqrt(uniform_filter1d(np.mean(diff ** 2, axis=0), ns(0.005)))
    edb = 20 * np.log10(e + 1e-12)
    idx = np.arange(0, b - a, step)
    d.line(list(zip(X(a + idx).tolist(), Y2(edb[idx]).tolist())), fill=(170, 50, 40), width=2)
    d.line([(X(N_CUT), y0), (X(N_CUT), y0 + ph)], fill=(220, 40, 40), width=1)
    d.line([(X(K), y0), (X(K), y0 + ph)], fill=(30, 150, 60), width=2)
    d.text((ml + 6, y0 + 4), 'difference soundtrack_cash.wav - soundtrack.wav, 5 ms RMS (dBFS): the new material, then only '
                             'the master converging; exactly 0 (off the scale) from K on', fill=(20, 20, 30), font=f13)
    for s in np.arange(4.4, 6.21, 0.2):
        d.text((X(ns(s)) - 12, y0 + ph + 4), f'{s:.1f}s', fill=(80, 80, 90), font=f11)
    im.save(path)


def analyse(cues, otim, paths, out_new, full, orig_f, music, sfx, binfo, orig, rep, minfo, aac, use_ffmpeg, fast,
            logs, outdir, md5_before):
    L = []
    w = L.append
    sg = orig['stem_gain']
    cash, ci = BA.read_wav24(paths['out'])  # analysis scale (int / 2^23), as build_audio
    og, _ = BA.read_wav24(paths['orig'])
    _, fr_c = BI.wav_frames(paths['out'])
    _, fr_o = BI.wav_frames(paths['orig'])
    ic, io = pcm_ints(fr_c), pcm_ints(fr_o)
    differ = np.flatnonzero(np.any(ic != io, axis=0))
    j_id = int(differ[-1]) + 1 if len(differ) else 0
    w('SOL Sniper reel, cash version: soundtrack analysis (generated by audio/build_cash.py)')
    w('=' * 78)
    w('FILES')
    ok = ci['frames'] == N and ci['rate'] == SR and ci['channels'] == 2 and ci['sampwidth'] == 3
    w(f"  {os.path.relpath(paths['out'], ROOT)}: {ci['rate']} Hz, {ci['channels']} ch, {8 * ci['sampwidth']}-bit PCM, "
      f"{ci['frames']} samples = {ci['frames'] / ci['rate']:.6f} s (want {N}) -> {'OK' if ok else 'FAIL'}")
    w(f"  md5: soundtrack_cash.wav {_md5(paths['out'])}; soundtrack.wav {_md5(paths['orig'])} (before the build "
      f"{md5_before}: {'unchanged' if _md5(paths['orig']) == md5_before else 'CHANGED'})")
    same_tail = fr_c[K * BW:] == fr_o[K * BW:]
    w(f'  bit-identity with soundtrack.wav (PCM frames compared): frames {K}-{N - 1} ({K / SR:.3f}-{N / SR:.3f} s) '
      f"{'BIT-IDENTICAL' if same_tail else 'DIFFERENT'} (md5 of those PCM bytes {hashlib.md5(fr_c[K * BW:]).hexdigest()} vs "
      f'{hashlib.md5(fr_o[K * BW:]).hexdigest()})')
    w(f'  last frame that differs: {j_id - 1} -> the file is bit-identical to soundtrack.wav from sample {j_id} '
      f'({j_id / SR:.4f} s) on; designed splice point K = {K} = 240000 + {K - N_CUT} (L = {(K - N_CUT) / SR:.3f} s, '
      f'crossfade {K - ns(XFADE)}-{K - 1})')
    w(f'  frames that differ in [0, {K}): {len(differ)} of {K}')
    w('')

    w('METHOD (details: the build_cash.py docstring)')
    w(f"  original stems re-rendered (build_audio.build on timing.json): music stem max |diff| {binfo['chk_music']} LSB, "
      f"sfx stem {binfo['chk_sfx']} LSB vs stems/*.wav; build_audio's ducking re-applied to the undocked music: max |diff| "
      f"{binfo['chk_duck']:.1e}")
    w(f"  stem gain {20 * np.log10(sg):+.4f} dB (build_audio.main: common gain of the original stems)")
    w(f"  REPRODUCTION: sndkit/master.py master() on stems/music.wav + stems/sfx.wav (its own normalisation and make-up "
      f"loop from 4.0 dB) -> make-up gain {rep['g_db']:+.6f} dB (analysis.txt: {binfo['g_txt']:+.2f} dB), integrated "
      f"{rep['lufs']:.3f} LUFS")
    w(f"    vs soundtrack.wav: max |residual| {rep['max_lsb']} LSB = {rep['max_dbfs']:.1f} dBFS, RMS {rep['rms_lsb']:.2f} LSB, "
      f"{rep['n_diff']} of {N} frames differ by any LSB (the stems are 24-bit quantised; the master was fed the float buses)")
    w(f"    master_fixed() (both gains fixed) vs master() on the same stems: max |diff| {rep['fixed_vs_master']:.1e} "
      f"({'bit-identical' if rep['fixed_vs_master'] == 0 else 'NOT identical'})")
    w(f"  new master: same chain, normalisation gain FIXED at {rep['norm_db']:+.4f} dB (the original pre-master's), make-up "
      f"gain FIXED at {rep['g_db']:+.4f} dB, WAV ceiling {TP_CEILING:.1f} dBTP")
    w(f"  music join at 5.000 (undocked re-render -> stems/music.wav): max step vs the stem {binfo['join_step']:.1e}")
    w('')

    # loudness
    w('LOUDNESS (own BS.1770-4 meter; "orig" = soundtrack.wav)')
    lf, lo_ = MS.integrated_lufs(cash), MS.integrated_lufs(og)
    w(f'  full 0-15 s integrated: cash {lf:.2f} LUFS, orig {lo_:.2f} LUFS (target ~-14) -> '
      f"{'OK' if abs(lf + 14.0) <= 0.3 else 'CHECK'}")
    if use_ffmpeg and shutil.which('ffmpeg'):
        e1, e0 = BA.ffmpeg_ebur128(paths['out']), BA.ffmpeg_ebur128(paths['orig'])
        w(f"  ffmpeg ebur128: cash I = {e1['I']} LUFS, LRA = {e1['LRA']} LU, TP = {e1['TP']} dBFS;  orig I = {e0['I']} LUFS, "
          f"LRA = {e0['LRA']} LU, TP = {e0['TP']} dBFS")
    c5, o5 = cash[:, :N_CUT], og[:, :N_CUT]
    i5c, i5o = MS.integrated_lufs(c5), MS.integrated_lufs(o5)
    s5c, s5o = MS.segment_lufs(cash, 0.0, 5.0), MS.segment_lufs(og, 0.0, 5.0)
    w(f'  0-5 s: integrated (gated) cash {i5c:.2f} vs orig {i5o:.2f} LUFS ({i5c - i5o:+.2f} LU); ungated segment '
      f'{s5c:.2f} vs {s5o:.2f} LUFS ({s5c - s5o:+.2f} LU) -> {"OK" if abs(s5c - s5o) <= 1.0 else "CHECK"} (want within 1 LU)')
    _, stc = _short_within(cash, 0.0, 5.0)
    _, sto = _short_within(og, 0.0, 5.0)
    w(f'  0-5 s short-term (3 s windows inside 0-5 s): max cash {stc.max():.1f} vs orig {sto.max():.1f} LUFS, '
      f'min {stc.min():.1f} vs {sto.min():.1f}, mean {np.mean(stc):.1f} vs {np.mean(sto):.1f}')
    tmc, lmc = _mom_within(cash, 0.0, 5.0)
    tmo, lmo = _mom_within(og, 0.0, 5.0)
    w(f'  0-5 s momentary (400 ms): max cash {lmc.max():.1f} LUFS @ {tmc[np.argmax(lmc)] - 0.2:.2f}s vs orig {lmo.max():.1f} '
      f'@ {tmo[np.argmax(lmo)] - 0.2:.2f}s; median {np.median(lmc):.1f} vs {np.median(lmo):.1f}')
    i15c, i15o = MS.integrated_lufs(cash[:, N_CUT:]), MS.integrated_lufs(og[:, N_CUT:])
    w(f'  5-15 s integrated: cash {i15c:.2f} vs orig {i15o:.2f} LUFS ({i15c - i15o:+.3f} LU; only 5.000-{K / SR:.3f} s differ)')
    w(f'  loudness range: cash {MS.loudness_range(cash):.1f} LU, orig {MS.loudness_range(og):.1f} LU')
    cuts = [0.0] + sorted({round(c['t'], 4) for c in cues if c['type'] in ('hit_cut',)}) + [5.0]
    w('  picture sections, ungated (cash / orig LUFS): ' + '   '.join(
        f'{a:.3f}-{b:.3f} {MS.segment_lufs(cash, a, b):.1f} / {MS.segment_lufs(og, a, b):.1f}' for a, b in zip(cuts[:-1], cuts[1:])))
    ph_c = zp(zp(cash, 'highpass', 300.0, 4), 'lowpass', 12000.0, 2)
    ph_o = zp(zp(og, 'highpass', 300.0, 4), 'lowpass', 12000.0, 2)
    w(f'  phone-speaker sim (HP 300 Hz / LP 12 kHz), 0-5 s ungated: cash {MS.segment_lufs(ph_c, 0, 5):.1f} vs orig '
      f'{MS.segment_lufs(ph_o, 0, 5):.1f} LUFS')
    w('')

    # peaks
    w('TRUE PEAK / DELIVERY')
    tpc = MS.true_peak(cash)
    tpn = MS.true_peak(cash[:, :K])
    w(f'  WAV true peak (4x): whole file {tpc:.2f} dBTP, new part [0, K) {tpn:.2f} dBTP (want <= -1.5) -> '
      f"{'OK' if tpc <= -1.5 else 'FAIL'}; sample peak {20 * np.log10(np.max(np.abs(cash))):.2f} dBFS; samples at full "
      f'scale: {int(np.sum(np.abs(cash) >= 0.9999))}')
    lg = minfo['limiter_gain']
    gr = -20 * np.log10(np.maximum(lg, 1e-12))
    w(f"  new master: limiter max GR {gr[:K].max():.2f} dB at {np.argmax(gr[:K]) / SR:.3f}s (orig's max {2.65:.2f} dB at "
      f"6.234s), glue comp max GR {minfo['glue_gr'][:K // 48].max():.2f} dB")
    if use_ffmpeg and shutil.which('ffmpeg'):
        with tempfile.TemporaryDirectory() as td:
            dec, fm, md5_mp4 = BA.aac_roundtrip(paths['out'], td, mux=True)
            _, _, md5_m4a = BA.aac_roundtrip(paths['out'], td, mux=False)
            deco, fmo, _ = BA.aac_roundtrip(paths['orig'], td, mux=True)
        env = MS._tp_envelope(dec)[:N]
        envo = MS._tp_envelope(deco)[:N]
        ta, tb = 20 * np.log10(env[:K].max()), 20 * np.log10(env[K:].max())
        ok = fm['TP'] is not None and fm['TP'] <= -1.0 and max(ta, tb) <= -1.0
        w(f"  AAC delivery (MP4 replica as scripts/encode.py: ffmpeg AAC-LC 320k 48 kHz), ebur128: I = {fm['I']} LUFS, true "
          f"peak = {fm['TP']} dBTP (spec <= -1.0, guard target {AAC_TP_TARGET:.1f}) -> {'OK' if ok else 'FAIL'}")
        w(f'  decoded AAC, own 4x meter: new part [0, K) {ta:.2f} dBTP @ {np.argmax(env[:K]) / SR:.3f}s, copied part '
          f'{tb:.2f} dBTP @ {(K + np.argmax(env[K:])) / SR:.3f}s; integrated {MS.integrated_lufs(dec[:, :N]):.2f} LUFS; '
          f'0-5 s {20 * np.log10(env[:N_CUT].max()):.2f} dBTP')
        w(f"  original soundtrack.wav through the same encode: {20 * np.log10(envo.max()):.2f} dBTP (ebur128 {fmo['TP']}), "
          f"its 0-5 s {20 * np.log10(envo[:N_CUT].max()):.2f} dBTP")
        w(f"  WAV -> AAC overshoot (new part) {ta - tpn:+.2f} dB; MP4 audio bit-identical to the audio-only encode the guard "
          f"measures: {'yes' if md5_mp4 == md5_m4a else 'NO'}")
        g = minfo.get('guard_db')
        if aac:
            w(f"  delivery guard: {aac['rounds']} master pass(es); "
              + (f'dips: max {g.max():.2f} dB at {np.argmax(g) / SR:.3f}s' if g is not None and g.max() > 0.005 else
                 'no dips needed'))
    else:
        w('  AAC: skipped (--no-ffmpeg or no ffmpeg): the AAC delivery true peak is NOT verified')
    dc = np.mean(cash, axis=1)
    dcn = np.mean(cash[:, :K], axis=1)
    w(f'  DC offset: whole file L {dc[0]:+.2e} R {dc[1]:+.2e}; new part L {dcn[0]:+.2e} R {dcn[1]:+.2e} (orig L '
      f'{np.mean(og[0]):+.2e} R {np.mean(og[1]):+.2e})')
    w('')

    # transition
    fi = binfo['finfo']
    w(f'PRE-TRANSITION MOVE (music bus, {FILTER_START - FILTER_IN:.2f}-5.000 s)')
    pts = []
    for t in (4.56, 4.65, 4.70, 4.75, 4.80, 4.85, 4.90, 4.95, 4.98):
        i = ns(t) - fi['a0']
        pts.append(f"{t:.2f} {fi['fc'][i]:.0f} Hz / {20 * np.log10(fi['dip'][i]):+.1f} dB")
    w('  cutoff / level dip: ' + ',  '.join(pts) + f'  (2 x RBJ low-pass, Q {FILTER_Q} each; filter path in from '
      f'{FILTER_START - FILTER_IN:.2f} s at {FILTER_F0 / 1000:.0f} kHz)')
    unmoved = binfo['music_new0']  # the same music bus without the move (new cue ducks only)
    blk = np.arange(4.50, 5.0 - 1e-9, 0.05)
    w('  music bus vs the same music without the move, per 50 ms block (K-weighted dB / above 600 Hz dB): ' + '  '.join(
        f'{a:.2f} {MS.segment_lufs(music, a, a + 0.05) - MS.segment_lufs(unmoved, a, a + 0.05):+.1f}/'
        f'{_rms_db(zp(music[:, ns(a) - 2400:ns(a + 0.05) + 2400], "highpass", 600.0, 4), 2400, -2400) - _rms_db(zp(unmoved[:, ns(a) - 2400:ns(a + 0.05) + 2400], "highpass", 600.0, 4), 2400, -2400):+.1f}'
        for a in blk))
    w(f'  over 4.93-4.98 s: K-weighted {MS.segment_lufs(music, 4.93, 4.98) - MS.segment_lufs(unmoved, 4.93, 4.98):+.1f} dB, '
      f'RMS {_rms_db(music, ns(4.93), ns(4.98)) - _rms_db(unmoved, ns(4.93), ns(4.98)):+.1f} dB (the gain dip alone is '
      f'{FILTER_DIP_DB:+.1f} dB; the rest is the low-pass)')
    r50 = [(a, _rms_db(cash, ns(a), ns(a + 0.05)), _rms_db(og, ns(a), ns(a + 0.05))) for a in np.arange(4.40, 5.0 - 1e-9, 0.05)]
    w('  final mix 50 ms RMS (dBFS, cash / orig): ' + '  '.join(f'{a:.2f} {v:.1f}/{o:.1f}' for a, v, o in r50)
      + f"  -> min {min(v for _, v, _ in r50):.1f} dBFS (no hole: want > -30) -> {'OK' if min(v for _, v, _ in r50) > -30 else 'CHECK'}")
    tm, lm = MS.momentary(cash)
    into = lm[(tm <= 5.0 + 1e-9) & (tm >= 4.6)]
    post = lm[(tm > 5.0) & (tm <= 5.6)]
    w(f'  momentary into the cut (windows ending 4.60-5.000 s): max {into.max():.1f} LUFS, last {into[-1]:.1f}; after the '
      f'cut (windows ending 5.05-5.60 s) max {post.max():.1f} LUFS -> the release is {post.max() - into.max():+.1f} LU '
      f"(want >= +2) -> {'OK' if post.max() - into.max() >= 2.0 else 'CHECK'}")
    w('')

    w('THE CUT AT 5.000 s (sample 240000)')
    n0 = N_CUT
    w(f'  samples 239997-240002 L: ' + ' '.join(f'{v:+.5f}' for v in cash[0, n0 - 3:n0 + 3])
      + '   R: ' + ' '.join(f'{v:+.5f}' for v in cash[1, n0 - 3:n0 + 3]))
    d1 = np.abs(np.diff(cash, axis=1))
    w(f'  |x[n+1] - x[n]|: max over 239760-239998 (last 5 ms, whip stop) {d1[:, n0 - ns(0.005):n0 - 1].max():.5f}; across '
      f'239999 -> 240000 {d1[:, n0 - 1].max():.5f}; max over the first 5 ms of the impact {d1[:, n0:n0 + ns(0.005)].max():.5f}')
    ratio = _click_ratio(cash)
    jr = float(ratio[n0 - ns(0.003):n0 - 1].max())
    w(f'  2nd-difference outlier ratio (build_audio click metric, > 14 = click) over the 3 ms before the transient: {jr:.1f} '
      f"-> {'OK' if jr <= 14.0 else 'CHECK'}")
    imp = [i for i, c in enumerate(cues) if c['type'] == 'impact_drop' and ns(c['t']) == N_CUT]
    if imp:
        iso = binfo['per'][imp[0]]['iso']
        m = np.max(np.abs(iso), axis=0)
        first = int(np.flatnonzero(m > 0)[0])
        on_i, _ = R.detect_onsets(iso, thresh_db=8.0, floor_db=-80.0)
        dv = R.match(on_i, 5.0)
        w(f'  impact_drop (isolated render): first non-zero sample {first} (cue sample {N_CUT}); onset detector '
          f"{'%+.2f ms' % (dv * 1000) if dv is not None else 'n/a'}; peak of its first 10 ms "
          f'{20 * np.log10(np.max(np.abs(iso[:, n0:n0 + ns(0.01)])) * sg):.1f} dBFS (stem domain)')
    w(f'  sample peak: last 100 ms before the cut {20 * np.log10(np.max(np.abs(cash[:, n0 - ns(0.1):n0]))):.1f} dBFS -> '
      f'first 100 ms after {20 * np.log10(np.max(np.abs(cash[:, n0:n0 + ns(0.1)]))):.1f} dBFS; 50 ms RMS '
      f'{_rms_db(cash, n0 - ns(0.05), n0):.1f} -> {_rms_db(cash, n0, n0 + ns(0.05)):.1f} dBFS')
    w(f'  music return: music bus RMS 4.990-4.999 s {_rms_db(music, n0 - ns(0.01), n0):.1f} dBFS -> 5.005-5.015 s '
      f'{_rms_db(music, n0 + ns(0.005), n0 + ns(0.015)):.1f} dBFS (filtered -7 dB -> full, {FILTER_RETURN * 1000:.0f} ms raised '
      f'cosine from sample 240000, under the impact); the impact duck takes it {20 * np.log10(binfo["g_post"][n0 + ns(0.05)]):+.1f} dB '
      f'for 80 ms')
    w(f"  reel's SFX stem from 5.000: {SFX_FADE_IN * 1000:.0f} ms fade-in over its {_rms_db(sfx - binfo['new_sfx'], n0, n0 + ns(0.005)):.0f} dBFS "
      f'(stem domain) reverb tails of the old cues')
    w('')

    # tail + crossfade
    w(f'IMPACT TAIL AND THE SPLICE (new sound design held to 5.000 + {TAIL_HOLD:.2f} s, faded out by 5.000 + {TAIL_END:.2f} s; '
      f'crossfade {(K - ns(XFADE)) / SR:.3f}-{K / SR:.3f} s)')
    nd = binfo['new_sfx']
    rows = []
    for a in (5.05, 5.15, 5.25, 5.35, 5.45, 5.55, 5.65, 5.75):
        rows.append(f'{a:.2f} {_rms_db(nd, ns(a), ns(a + 0.05)) - _rms_db(music + sfx - nd, ns(a), ns(a + 0.05)):+.1f}')
    w('  new sound design vs the reel under it (pre-master, 50 ms RMS, dB): ' + '  '.join(rows))
    rows = []
    for c in otim['cues']:
        if not (5.0 <= c['t'] < 5.0 + L_NEW) or c['type'] not in BA.UI_AUDIBLE:
            continue
        a = ns(c['t'])
        b = a + ns(0.02 if c['type'] in ('click', 'tap_soft', 'tick') else 0.08)  # build_audio's windows
        bo, fo = R.best_band_snr(binfo['stem_sfx'][:, a:b], binfo['stem_music'][:, a:b])
        bn, fn = R.best_band_snr((sfx - nd)[:, a:b], music[:, a:b] + nd[:, a:b])
        rows.append(f"{c['type']}@{c['t']:.3f}: {bo:+.1f} dB @ {fo:.0f} Hz -> {bn:+.1f} dB @ {fn:.0f} Hz")
    w("  the reel's own sounds after the cut, best 1/3-octave band over everything else (orig -> cash; want >= +6): "
      + '; '.join(rows))
    a, b = K - ns(XFADE), K
    res = out_new[:, a:b] - orig_f[:, a:b]
    sig_rms = np.sqrt(np.mean(orig_f[:, a:b] ** 2))
    w(f'  new master vs soundtrack.wav inside the crossfade window (before blending): max |diff| {np.abs(res).max():.2e} '
      f'({20 * np.log10(np.abs(res).max() + 1e-15):.1f} dBFS), RMS {20 * np.log10(np.sqrt(np.mean(res ** 2)) / sig_rms + 1e-15):.1f} dB '
      f're the program -> the two sides are the same signal (coherent)')
    pre_x = out_new[:, a - ns(0.1):a] - orig_f[:, a - ns(0.1):a]
    w(f'  same, over the 100 ms before the crossfade: RMS {20 * np.log10(np.sqrt(np.mean(pre_x ** 2)) / sig_rms + 1e-15):.1f} dB re '
      f'the program')
    d1c = np.abs(np.diff(cash[:, a - ns(0.005):b + ns(0.005)], axis=1)).max()
    d1o = np.abs(np.diff(og[:, a - ns(0.005):b + ns(0.005)], axis=1)).max()
    jr2 = float(ratio[a - ns(0.005):b + ns(0.005)].max())
    jr2o = float(_click_ratio(og[:, a - ns(0.02):b + ns(0.02)])[ns(0.015):-ns(0.015)].max())
    w(f'  around the crossfade ({(a - ns(0.005)) / SR:.3f}-{(b + ns(0.005)) / SR:.3f} s): max |x[n+1] - x[n]| cash {d1c:.5f} vs '
      f'orig {d1o:.5f}; 2nd-difference outlier ratio cash {jr2:.1f} vs orig {jr2o:.1f} -> '
      f"{'OK' if jr2 <= max(14.0, jr2o + 0.5) else 'CHECK'}")
    w(f'  across K-1 -> K: |step| {np.abs(cash[:, K] - cash[:, K - 1]).max():.5f} vs the original\'s own step there '
      f'{np.abs(og[:, K] - og[:, K - 1]).max():.5f}')
    w('')

    # cue alignment
    w('CUE ALIGNMENT (blind energy-ratio onset detector, sample resolution; deviation = detected - cue sample)')
    tr_types = FX.TRANSIENT_TYPES + IFX.TRANSIENT_TYPES
    trans = [(i, c) for i, c in enumerate(cues) if c['type'] in tr_types]
    stem = np.zeros((2, ns(SFX_SPAN)))
    for i, _ in trans:
        stem += binfo['per'][i]['iso']
    on_stem, _ = R.detect_onsets(stem, thresh_db=8.0, floor_db=-80.0)
    on_stem_lo = BI.detect_low(stem)
    span = cash[:, :ns(SFX_SPAN)]
    on_mix = np.unique(np.concatenate([R.detect_onsets(span, thresh_db=6.0, floor_db=-60.0, min_gap=0.006)[0],
                                       R.detect_onsets(span, thresh_db=6.0, floor_db=-66.0, hp_f=2500.0, min_gap=0.006)[0]]))
    on_mix_lo = BI.detect_low(span)
    w('  stem = the transient cues alone (dry + their reverb); mix = soundtrack_cash.wav. Detectors: broadband (HP 120 Hz; '
      'mix: + a >2.5 kHz band) and low band (< 250 Hz)')
    w('  render = first sample of the cue\'s isolated dry render minus the cue sample (END-ALIGNED: last sample + 1 minus '
      'the cue sample): exact by construction; the blind detectors confirm it in the stem and in the final file. Low-band '
      'detector only for cues with a low layer.')
    w('  t (s)    sample   type          gain  render   stem (ms)  stem low   mix (ms)   mix low   SFX/music K-wtd  best 1/3-oct '
      'band   notes')
    worst_s, worst_m, worst_r = 0.0, 0.0, 0
    f = lambda d_: f'{d_ * 1000:+8.2f}' if d_ is not None else '     n/a'
    nsfx = binfo['new_sfx']
    low_types = ('impact_big', 'impact_drop', 'impact_outro', 'hit_cut', 'punch') + IFX_TYPES
    for i, c in enumerate(cues):
        typ = c['type']
        a = ns(c['t'])
        if typ == 'whip':
            a0, a1 = a - ns(min(c.get('dur', 0.15), 0.06)), a
        elif typ in ('whoosh_fast', 'whoosh_rise'):
            a0, a1 = a, a + ns(0.25)
        elif typ == 'tick':
            a0, a1 = a, a + ns(0.02)
        else:
            a0, a1 = a, a + ns(0.08)
        ks, km = MS.kweight(nsfx[:, a0:a1]), MS.kweight(music[:, a0:a1])
        snr = 10 * np.log10((np.mean(ks ** 2) + 1e-20) / (np.mean(km ** 2) + 1e-20))
        bb, bf = R.best_band_snr(nsfx[:, a0:a1], music[:, a0:a1])
        snr_s = f'{snr:+8.1f}' if snr < 40 else '    >+40'
        bb_s = f'{bb:+6.1f}' if bb < 40 else '  >+40'
        pc = binfo['per'][i]
        rd = (pc['last'] + 1 - a) if typ in FX.END_ALIGNED else (pc['first'] - a)
        worst_r = max(worst_r, abs(rd))
        if typ in tr_types:
            lowc = typ in low_types
            ds, dm = R.match(on_stem, c['t']), R.match(on_mix, c['t'])
            dsl = R.match(on_stem_lo, c['t']) if lowc else None
            dml = R.match(on_mix_lo, c['t']) if lowc else None
            bs_ = min([abs(v) for v in (ds, dsl) if v is not None], default=np.inf)
            bm_ = min([abs(v) for v in (dm, dml) if v is not None], default=np.inf)
            worst_s, worst_m = max(worst_s, bs_), max(worst_m, bm_)
            g_ = lambda d_: f(d_) if lowc else '       -'
            cols = f'{f(ds)}   {g_(dsl)}   {f(dm)}   {g_(dml)}'
        else:
            cols = '       -          -          -          -'
        w(f"  {c['t']:6.3f}  {a:7d}   {typ:13s} {c.get('gain', 0):+4.0f}  {rd:+5d}   {cols}   {snr_s}        {bb_s} dB @ "
          f"{bf:5.0f} Hz   {binfo['notes'].get(i, '')}")
    w(f'  render offsets: max |offset| {worst_r} samples -> {"PASS (every cue ON its sample)" if worst_r == 0 else "FAIL"}')
    w(f"  transient cues ({len(trans)}), blind detectors: max |dev| (best detector) stem {worst_s * 1000:.2f} ms, final mix "
      f"{worst_m * 1000:.2f} ms -> {'PASS (< 2 ms)' if worst_s < 0.002 and worst_m < 0.002 else 'FAIL'}")
    w('  END-ALIGNED cues (isolated dry render; must end ON the cue sample):')
    for i, c in enumerate(cues):
        if c['type'] not in FX.END_ALIGNED:
            continue
        iso = binfo['per'][i]['dry']
        m = np.max(np.abs(iso), axis=0)
        nz = np.flatnonzero(m > m.max() * 1e-4)
        a_, last = int(nz[0]), int(nz[-1])
        dev = (last + 1 - ns(c['t'])) / SR
        e10 = np.sqrt(np.maximum(uniform_filter1d(np.mean(iso ** 2, axis=0), ns(0.01)), 0.0))
        tail = _rms_db(iso, last + 1 - ns(0.01), last + 1) - 20 * np.log10(e10.max())
        w(f"    {c['t']:6.3f} {c['type']:6s} dur {c.get('dur', 0):.3f}: starts {a_ / SR:.3f}s, last sample {last} -> ends "
          f"{dev * 1000:+.3f} ms re cue; last 10 ms {tail:+.1f} dB re its loudest 10 ms -> {'PASS' if abs(dev) < 0.002 else 'FAIL'}")
    # ui audibility of the new ticks
    low_ui = [f"{c['type']}@{c['t']:.3f}" for c in cues if c['type'] in BA.UI_AUDIBLE
              and R.best_band_snr(nsfx[:, ns(c['t']):ns(c['t']) + ns(0.02)], music[:, ns(c['t']):ns(c['t']) + ns(0.02)])[0] < 6.0]
    w('  UI audibility of the new ticks (best 1/3-octave band over the music, want >= +6 dB): '
      + ('all OK' if not low_ui else 'LOW: ' + ', '.join(low_ui)))
    w('')

    # low end
    w('LOW-END ALIGNMENT (below 160 Hz over the first 150 ms: the two parts summed vs their power sum; ~0 or above = no '
      'cancellation)')
    kick = np.mean(orig['tracks']['kick'], axis=0) * sg
    lpk = zp(kick, 'lowpass', 160.0, 4)
    rows = []
    for i, c in enumerate(cues):
        if c['type'] not in BA.HIT_TYPES:
            continue
        s = ns(c['t'])
        x = zp(np.mean(binfo['per'][i]['iso'], axis=0) * sg, 'lowpass', 160.0, 4)
        a, b = s, s + ns(0.15)
        near = [k for k in orig['kick_trig'] if abs(k - s) <= ns(0.03)]
        if near:
            k_ = float(np.mean(lpk[a:b] ** 2))
            x_ = float(np.mean(x[a:b] ** 2))
            both = float(np.mean((lpk[a:b] + x[a:b]) ** 2))
            rows.append(f"{c['type']}@{c['t']:.3f} + grid kick {(near[0] - s) / SR * 1000:+.1f} ms: {10 * np.log10(both / (k_ + x_)):+.1f} dB")
        for j, c2 in enumerate(cues):
            if j != i and c2['type'] in IFX_TYPES and abs(ns(c2['t']) - s) <= ns(0.03):
                y = zp(np.mean(binfo['per'][j]['iso'], axis=0) * sg, 'lowpass', 160.0, 4)
                k_ = float(np.mean(y[a:b] ** 2))
                x_ = float(np.mean(x[a:b] ** 2))
                both = float(np.mean((y[a:b] + x[a:b]) ** 2))
                rows.append(f"{c['type']}@{c['t']:.3f} + {c2['type']}@{c2['t']:.3f}: {10 * np.log10(both / (k_ + x_)):+.1f} dB")
        if s >= N_CUT:
            xo = zp(np.mean(nsfx, axis=0), 'lowpass', 160.0, 4)  # all new sounds as mixed (tail env + sidechain)
            for kk, _ in binfo['yinfo']['kicks']:
                a2, b2 = kk, kk + ns(0.15)
                k_ = float(np.mean(lpk[a2:b2] ** 2))
                x_ = float(np.mean(xo[a2:b2] ** 2))
                both = float(np.mean((lpk[a2:b2] + xo[a2:b2]) ** 2))
                raw = float(np.mean((lpk[a2:b2] + x[a2:b2] * binfo['tail'][a2:b2]) ** 2))
                raw_p = k_ + float(np.mean((x[a2:b2] * binfo['tail'][a2:b2]) ** 2))
                rows.append(f"{c['type']}@{c['t']:.3f} tail + grid kick @{kk / SR:.3f} (sidechained, new sounds "
                            f"{10 * np.log10(x_ / k_):+.1f} dB re kick): {10 * np.log10(both / (k_ + x_)):+.1f} dB "
                            f"(without the sidechain {10 * np.log10(raw / raw_p):+.1f} dB)")
            mm = zp(np.mean(music, axis=0), 'lowpass', 160.0, 4)
            k_ = float(np.mean(mm[a:b] ** 2))
            x_ = float(np.mean(x[a:b] ** 2))
            both = float(np.mean((mm[a:b] + x[a:b]) ** 2))
            rows.append(f"{c['type']}@{c['t']:.3f} + the reel's music (bass Db2 at 5.04 s): {10 * np.log10(both / (k_ + x_)):+.1f} dB")
    for r_ in rows:
        w('  ' + r_)
    w('')

    # clicks / silence
    w('CLICKS / DC / SILENCE (2nd-difference outliers vs local level, as build_audio; new part + 0.1 s)')
    known = [ns(c['t']) for c in cues] + [ns(c['t']) for c in otim['cues'] if c['t'] >= 5.0] + [0]
    known += list(R.detect_onsets(music[:, :K + ns(0.1)], thresh_db=10.0, floor_db=-50.0, min_gap=0.03)[0])
    known += list(R.detect_onsets(sfx[:, :K + ns(0.1)], thresh_db=8.0, floor_db=-70.0)[0])
    known = np.unique(np.array(known))
    flagged = np.where(ratio[:K + ns(0.1)] > 14.0)[0]
    clusters = []
    for s in flagged:
        if not clusters or s - clusters[-1][-1] > ns(0.005):
            clusters.append([s])
        else:
            clusters[-1].append(s)
    unexplained = [c[0] for c in clusters if np.min(np.abs(known - c[0])) > ns(0.004)]
    w(f'  outlier clusters in [0, K + 0.1 s): {len(clusters)}, not at a designed transient / note onset: {len(unexplained)}'
      + (f"  at {', '.join(f'{u / SR:.3f}s' for u in unexplained[:12])}" if unexplained else '')
      + f"  -> {'OK' if not unexplained else 'CHECK'}")
    r = np.sqrt(uniform_filter1d(np.mean(cash ** 2, axis=0), ns(0.05)))
    rr = 20 * np.log10(r[ns(0.025):ns(15.0 - FADE_OUT - 0.025)] + 1e-12)
    w(f'  quietest 50 ms (0-{15.0 - FADE_OUT:.2f} s): {rr.min():.1f} dBFS at {(np.argmin(rr) + ns(0.025)) / SR:.3f}s; in the new part '
      f'{rr[:K - ns(0.025)].min():.1f} dBFS at {(np.argmin(rr[:K - ns(0.025)]) + ns(0.025)) / SR:.3f}s (no silence gap: want > -40) -> '
      f"{'OK' if rr[:K - ns(0.025)].min() > -40 else 'CHECK'}")
    w(f'  first sample L {cash[0, 0]:+.4f} R {cash[1, 0]:+.4f} (the opening hit lands on sample 0, as the original: '
      f'L {og[0, 0]:+.4f} R {og[1, 0]:+.4f})')
    w('')

    # dynamics
    w('MASTER DYNAMICS (new master; limiter GR should work on the big hits, not on the ticks)')
    row = []
    for c in cues:
        if c['type'] in tr_types:
            s = ns(c['t'])
            row.append(f"{c['type']}@{c['t']:.2f} {gr[max(s - ns(0.004), 0):s + ns(0.03)].max():.1f}")
    w('  GR per transient cue (dB): ' + ', '.join(row))
    w(f"  glue comp max GR in the new part {minfo['glue_gr'][:K // 48].max():.2f} dB at "
      f"{minfo['glue_t'][int(np.argmax(minfo['glue_gr'][:K // 48]))]:.2f}s")
    w('')

    # stereo / spectrum
    w('STEREO / SPECTRUM (0-5 s; orig for reference)')
    for name, x in (('cash', cash), ('orig', og)):
        L_, R_ = x[0, :N_CUT], x[1, :N_CUT]
        M = 0.5 * (L_ + R_)
        loss = 10 * np.log10(np.mean(M ** 2) / (0.5 * (np.mean(L_ ** 2) + np.mean(R_ ** 2))))
        Wn, Hn = ns(0.1), ns(0.05)
        cs = sorted(np.corrcoef(x[0, i:i + Wn], x[1, i:i + Wn])[0, 1] for i in range(0, N_CUT - Wn, Hn))
        lo_x = zp(x[:, :N_CUT], 'lowpass', 150.0, 4)
        seg = np.mean(x[:, :N_CUT], axis=0)
        F = np.abs(np.fft.rfft(seg)) ** 2
        fr = np.fft.rfftfreq(len(seg), 1 / SR)
        e = lambda lo, hi: 100.0 * F[(fr >= lo) & (fr < hi)].sum() / F[(fr >= 20) & (fr < 20000)].sum()
        w(f'  {name}: L/R corr {np.corrcoef(L_, R_)[0, 1]:+.2f} (lowest 100 ms {cs[0]:+.2f}), below 150 Hz '
          f'{np.corrcoef(lo_x[0], lo_x[1])[0, 1]:.3f}; mono sum vs stereo {loss:+.2f} dB;  % energy: <30 Hz {e(20, 30):.1f}  '
          f'30-80 {e(30, 80):.1f}  80-200 {e(80, 200):.1f}  200-400 {e(200, 400):.1f}  400-900 {e(400, 900):.1f}  '
          f'0.9-2k {e(900, 2000):.2f}  2-5k {e(2000, 5000):.2f}  5-10k {e(5000, 10000):.2f}  10-20k {e(10000, 20000):.3f}')
    w('')
    w('BUILD LOG')
    for s in logs:
        w('  ' + s.strip())
    txt = '\n'.join(L) + '\n'
    with open(os.path.join(outdir, 'cash_analysis.txt'), 'w') as fh:
        fh.write(txt)
    print(txt)
    if not fast:
        join_png(os.path.join(outdir, 'cash_join.png'), cash, og, binfo['finfo'], cues)


def main():
    ap = argparse.ArgumentParser(description='Build the cash version of the soundtrack (see the docstring).')
    ap.add_argument('--timing', default=os.path.join(HERE, 'cash_timing.json'), help='cash cue sheet JSON, used as is')
    ap.add_argument('--orig', default=os.path.join(HERE, 'soundtrack.wav'), help='the original finished soundtrack')
    ap.add_argument('--out', default=HERE, help='output directory (default: audio/)')
    ap.add_argument('--fast', action='store_true', help='skip the PNG')
    ap.add_argument('--no-ffmpeg', action='store_true', help='skip ffmpeg (no AAC guard / ebur128)')
    args = ap.parse_args()
    use_ffmpeg = not args.no_ffmpeg
    outdir = os.path.abspath(args.out)
    orig_path = os.path.abspath(args.orig)
    T0 = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)

    tim = _load_json(args.timing)
    src = os.path.join(ROOT, 'src', 'cash', 'timing.js')
    if os.path.exists(src) and os.path.getmtime(src) > os.path.getmtime(args.timing):
        log(f'WARNING: src/cash/timing.js is newer than {os.path.relpath(args.timing, ROOT)} (re-export the cue sheet)')
    log(f'timing: {os.path.relpath(os.path.abspath(args.timing), ROOT)} ({len(tim["cues"])} cues, used as is)')
    assert tim['bpm'] == 125 and abs(float(tim['duration']) - 5.0) < 1e-9, tim
    cues = tim['cues']
    otim = _load_json(os.path.join(HERE, 'timing.json'))
    md5_before = _md5(orig_path)
    log(f'original: {os.path.relpath(orig_path, ROOT)} md5 {md5_before} (read only)')
    orig_f, orig_frames = read_float(orig_path)
    assert orig_f.shape == (2, N), orig_f.shape
    stem_music, fr_m = read_float(os.path.join(HERE, 'stems', 'music.wav'))
    stem_sfx, fr_s = read_float(os.path.join(HERE, 'stems', 'sfx.wav'))

    log('reproducing the original master from its stems')
    rep = reproduce_master(stem_music, stem_sfx, pcm_ints(orig_frames), log)
    g_txt = analysis_makeup()
    log(f"  make-up gain {rep['g_db']:+.6f} dB (analysis.txt {g_txt:+.2f}), normalisation {rep['norm_db']:+.6f} dB; "
        f"residual vs soundtrack.wav max {rep['max_lsb']} LSB ({rep['max_dbfs']:.1f} dBFS); fixed-gain chain vs master(): "
        f"{rep['fixed_vs_master']:.1e}")
    assert g_txt is None or abs(rep['g_db'] - g_txt) < 0.006, (rep['g_db'], g_txt)
    assert rep['fixed_vs_master'] == 0.0 and rep['max_lsb'] <= 16, rep

    log('re-rendering the original score (build_audio.build on timing.json)')
    orig = original_score(otim, log)
    sg = orig['stem_gain']
    chk_m = int(np.abs(np.round(np.clip(orig['music_d'] * sg, -1, 1 - 2.0 ** -23) * 8388607.0).astype(np.int64)
                       - pcm_ints(fr_m)).max())
    chk_s = int(np.abs(np.round(np.clip(orig['sfx'] * sg, -1, 1 - 2.0 ** -23) * 8388607.0).astype(np.int64)
                       - pcm_ints(fr_s)).max())
    md, _ = duck_music(orig['music_raw'], otim['cues'])
    chk_d = float(np.abs(md - orig['music_d']).max())
    log(f'  stems reproduced: music max |diff| {chk_m} LSB, sfx {chk_s} LSB; ducking replica max |diff| {chk_d:.1e}; '
        f'stem gain {20 * np.log10(sg):+.4f} dB')
    assert chk_m <= 1 and chk_s <= 1 and chk_d < 1e-9, (chk_m, chk_s, chk_d)

    log('building the new pre-master')
    music, sfx, binfo = build(cues, otim['cues'], orig, stem_music, stem_sfx, log)
    binfo.update(chk_music=chk_m, chk_sfx=chk_s, chk_duck=chk_d, g_txt=g_txt if g_txt is not None else np.nan,
                 stem_music=stem_music, stem_sfx=stem_sfx)
    pre = music + sfx
    log(f'mastering (fixed gains) + splice at K = {K} + AAC delivery guard')
    out_new, full, minfo, aac = master_for_delivery(pre, rep, orig_f, orig_frames, log, use_ffmpeg)

    os.makedirs(os.path.join(outdir, 'stems'), exist_ok=True)
    paths = dict(out=os.path.join(outdir, 'soundtrack_cash.wav'), orig=orig_path)
    write_frames(paths['out'], splice_bytes(full, orig_frames))
    trim = min(1.0, 10.0 ** (-1.0 / 20.0) / max(np.max(np.abs(music)), np.max(np.abs(sfx))))
    BA.write_wav24(os.path.join(outdir, 'stems', 'cash_music.wav'), music * trim)
    BA.write_wav24(os.path.join(outdir, 'stems', 'cash_sfx.wav'), sfx * trim)
    assert _md5(orig_path) == md5_before, 'soundtrack.wav changed while building'
    log(f"wrote {os.path.relpath(paths['out'], ROOT)} (md5 {_md5(paths['out'])}) + stems/cash_*.wav (shared trim "
        f'{20 * np.log10(trim):+.2f} dB re the original stems)  ({time.time() - T0:.1f}s)')
    analyse(cues, otim, paths, out_new, full, orig_f, music, sfx, binfo, orig, rep, minfo, aac, use_ffmpeg, args.fast,
            logs, outdir, md5_before)
    log(f'done in {time.time() - T0:.1f}s')


if __name__ == '__main__':
    main()
