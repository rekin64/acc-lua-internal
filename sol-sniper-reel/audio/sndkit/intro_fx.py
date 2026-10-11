"""Sound design for the 5 s intro hook prepended to the reel (used by audio/build_intro.py only).

Same conventions as sfx.py: every synth returns [(stereo signal, offset_samples, sends)] with the
offset relative to the cue sample (negative for sounds that END at the cue) and `sends` mapping a
reverb bus ('hall', 'room') to a send gain ('_dry' = gain of the dry signal, default 1). Transient
sounds start ON the cue sample (no pre-roll), so their onset IS the cue time.

Palette (dark, low, restrained; nothing bright or 'sci-fi'):
  bass_hit   deep hit from black: sub drop onto F1 + a felt low thud + a dark attack (no crack)
             + a low-mid bloom that opens into a long dark hall
  tension    F minor drone bed: phase-reference F1 sub + a dark just-intonation Fm7 pad whose low-pass
             swells open over the hook + a faint dark air layer; breathes with the pulses, recedes
             under the riser / suck in the last 0.5 s, its sub pulled out after the last pulse
  accent     felt text punch: tight thump tuned to F2 + a little locked sub + a short knock and a
             soft tick, into the hall (a premium 'thock', not a cartoon hit)
  whoosh     dark, slow push-in whoosh (low-mid band noise, gentle stereo drift)
  pulse      sub heartbeat: short F1 thump with a soft felt knock and phone-speaker harmonics
  riser      low cinematic riser: root + fifth + low octave gliding up an octave onto F3 / C4 through
             an opening low-pass + dark band noise climbing to ~2.4 kHz; full level for the last
             25 ms, 1.5 ms stop
  suck       reverse swell into the cut: the reversed dark-hall tail of an Fm9 hit (the reel's
             first chord) + a zoom-in whoosh that narrows to the centre; 1.5 ms stop on the cue

Low end: every F1 (43.65 Hz) component (bass hit, accents, pulses, drone sub) is phase-locked to
one free-running reference sine sin(2 pi (F1 * S / SR + C_REF)) (S = absolute sample), so layered
lows sum instead of beating or cancelling.
"""
import numpy as np

from . import sfx as FX
from .dsp import (SR, TAU, band_mag, bp, convolve_ir, cos_ramp, duck_env, eq, fades, hp, lp, midi_hz, ns, phase,
                  rng, sat, saw, shaped_noise, smoothstep, supersaw, taxis, tv_biquad, width)

F1 = float(midi_hz(29))   # 43.654 Hz: the reel's kick / impact tuning
F2 = float(midi_hz(41))   # 87.307 Hz
C2 = float(midi_hz(36))   # 65.406 Hz
C_REF = 0.0               # phase (cycles) of the F1 reference at sample 0

# Level per type (dB, loudest 10 ms RMS of the dry sound, before the cue's gain offset), same
# convention as sfx.LEVELS. The tension bed is set by loudness instead (BED_LUFS).
# Balance (after the hook is mastered to -14.5 LUFS integrated; see intro_analysis.txt): the bass hit is
# the loudest moment but no louder than the reel's opening impact (momentary max -12.6 vs -12.2 LUFS); the
# bed carries the middle (momentary median ~-15); the riser + suck take over in the last 0.8 s and peak on
# the cut (~-13.3 LUFS momentary), ~1 LU and ~3 dB of sample peak under the reel's impact, so the impact
# lands as the release. Sub-heavy layers carry 150 Hz-1.5 kHz harmonics so they read on phone speakers.
LEVELS = {'bass_hit': -9.0, 'accent': -6.0, 'whoosh': -19.0, 'pulse': -14.0, 'riser': -20.5, 'suck': -21.5}
BED_LUFS = -16.0          # tension bed, ungated K-weighted loudness over its 1.3-4.2 s stretch

# Hook bus EQ (applied by build_intro to both pre-master buses): a broad low-mid dip, so the drone's
# chord tones and the hits' phone harmonics stay clean instead of boxy (200-400 Hz).
BUS_EQ = (('peak', 260.0, 0.8, -2.5),)

TRANSIENT_TYPES = ('bass_hit', 'accent', 'pulse')
END_ALIGNED = ('riser', 'suck')
BED_TYPES = ('tension',)


def locked_glide(f0, f1, tau, n, start, c_ref=C_REF):
    """Sine gliding exponentially f0 -> f1 (time constant tau) whose phase converges onto the
    free-running reference sin(2 pi (f1 * S / SR + c_ref)), S = absolute sample (`start` = the
    sample this sound starts on)."""
    k = np.arange(n)
    f = f1 + (f0 - f1) * np.exp(-k / (tau * SR))
    r = np.exp(-1.0 / (tau * SR))
    extra = (f0 - f1) / SR / (1.0 - r)  # cycles the glide gains over a steady f1 sine (k -> inf)
    return np.sin(TAU * phase(f, n, f1 * start / SR + c_ref - extra))


def _harmonics(x, lo, hi, drive=3.0):
    """Driven copy of a low layer, band-limited to lo-hi Hz: lets it read on phone speakers."""
    h = np.tanh(drive * x / (np.max(np.abs(x)) + 1e-9))
    return lp(hp(h, lo, 2), hi, 2)


def _mono(x):
    return np.vstack([x, x])


def bus_eq(x):
    for kind, f0, q, g in BUS_EQ:
        x = eq(x, kind, f0, q, g)
    return x


# --------------------------------------------------------------------------- hits
def bass_hit(seed, start=0):
    n = ns(3.2)
    t = taxis(n)
    # 1. sub drop onto F1, phase-locked to the drone; long, deep decay
    sub = locked_glide(68.0, F1, 0.15, n, start)
    sub *= np.exp(-(t / 0.6) ** 1.25) * 0.75
    sub[:ns(0.003)] *= cos_ramp(ns(0.003))
    sub = sat(sub * 1.2, 1.15)
    # 2. felt thud: pitched body gliding onto C2 (the fifth) + low-passed noise
    thud = FX._glide_sine(150.0, C2, 0.03, n) * np.exp(-t / 0.10) * 0.6
    thud += lp(FX._noise(n, 'ih-thud', seed), 210.0, 4) * 5.0 * np.exp(-t / 0.045)
    thud[:ns(0.0015)] *= cos_ramp(ns(0.0015))
    low = sub + thud
    harm = _harmonics(low, 120.0, 1500.0, 4.0) * 1.5 * np.exp(-t / 0.35)
    # 3. dark attack: a felt 'thock' with only a whisper of top (no crack)
    att = np.zeros((2, n))
    for c in range(2):
        z = FX._noise(n, 'ih-att', seed, c)
        att[c] = bp(z, 220.0, 2400.0, 2) * np.exp(-t / 0.014) * 2.0 \
            + bp(z, 2400.0, 6000.0, 2) * np.exp(-t / 0.0025) * 0.3
    att = width(att, 0.5)
    # 4. bloom: low-mid air that swells into the hall (the space of the hit)
    mag = lambda tt, f: band_mag(420.0, 0.9)(f) * np.ones_like(tt)
    bloom = np.vstack([shaped_noise(n, mag, seed + 21), shaped_noise(n, mag, seed + 22)])
    bloom = width(bloom, 0.5) * ((1 - np.exp(-t / 0.04)) * np.exp(-t / 0.8) * 1.4)[None, :]
    dry = _mono(low + harm) + att + bloom
    dry = FX._onset_ramp(fades(dry, 0.0, 0.3), 3)
    wet = _mono(thud * 0.5 + harm) + att * 1.2 + bloom * 1.6
    wet = FX._onset_ramp(wet, 3)
    return [(dry, 0, {}), (wet, 0, {'hall': 0.8, '_dry': 0.0})]


def accent(seed, start):
    n = ns(0.9)
    t = taxis(n)
    thump = FX._glide_sine(185.0, F2, 0.018, n) * np.exp(-(t / 0.08) ** 1.4)
    thump[:ns(0.001)] *= cos_ramp(ns(0.001))
    sub = locked_glide(76.0, F1, 0.03, n, start) * np.exp(-(t / 0.14) ** 1.5) * 0.3
    sub[:ns(0.002)] *= cos_ramp(ns(0.002))
    body = bp(FX._noise(n, 'ia-body', seed), 180.0, 1400.0, 2) * np.exp(-t / 0.02) * 2.0
    low = thump + sub + body
    harm = _harmonics(thump + body, 170.0, 1500.0) * 0.7 * np.exp(-t / 0.09)
    tick = np.zeros((2, n))
    for c in range(2):
        tick[c] = bp(FX._noise(n, 'ia-tick', seed, c), 1600.0, 6500.0, 2) * np.exp(-t / 0.0028) * 0.5
    tick = width(tick, 0.4)
    dry = FX._onset_ramp(fades(_mono(low + harm) + tick, 0.0, 0.25), 3)
    wet = FX._onset_ramp(_mono(body + harm + 0.3 * thump) + tick, 3)
    return [(dry, 0, {}), (wet, 0, {'hall': 0.32, 'room': 0.10, '_dry': 0.0})]


def pulse(seed, start):
    n = ns(0.42)
    t = taxis(n)
    env = np.exp(-(t / 0.13) ** 1.6)
    env[:ns(0.0015)] *= cos_ramp(ns(0.0015))
    sub = locked_glide(82.0, F1, 0.025, n, start) * env
    knock = lp(FX._noise(n, 'ip-knock', seed), 650.0, 2) * np.exp(-t / 0.006) * 1.0
    knock += FX._glide_sine(300.0, 150.0, 0.006, n) * np.exp(-t / 0.014) * 0.5     # felt 'dum'
    knock += bp(FX._noise(n, 'ip-tick', seed), 900.0, 3500.0, 2) * np.exp(-t / 0.0015) * 0.5  # definition
    knock[:ns(0.0005)] *= cos_ramp(ns(0.0005))
    harm = _harmonics(sub, 150.0, 1200.0, 5.0) * 1.0
    x = fades(sub + knock + harm, 0.0, 0.05)
    return [(_mono(x), 0, {'room': 0.04})]


# --------------------------------------------------------------------------- bed
def tension(seed, dur, pulse_samples=(), accent_samples=()):
    """F minor drone bed over the whole hook (starts at the cue sample, lasts `dur`; sample
    positions are relative to its start). Returns [(bed, 0, sends)] at an arbitrary level
    (build_intro sets it by loudness)."""
    n = ns(dur)
    t = taxis(n)
    u = t / dur
    # sub 'vacuum': from just after the last pulse's attack to 50 ms before the cut
    v0 = (max(pulse_samples) / SR + 0.017) if len(pulse_samples) else dur - 0.45
    vd = max(dur - 0.05 - v0, 0.05)
    # 1. sub: the F1 phase reference itself; enters under the hit's tail, swells a little, and is
    #    pulled out after the last pulse ('vacuum') so the reel's impact gets the low end to itself
    sub = np.sin(TAU * (F1 * np.arange(n) / SR + C_REF))
    sub_env = smoothstep((t - 0.3) / 1.5) * (0.7 + 0.3 * smoothstep((t - 1.6) / 2.6)) \
        * (1.0 - smoothstep((t - v0) / vd))
    duck_p = duck_env(n, list(pulse_samples), 0.6, release=0.28, attack=0.002, curve=1.6)
    sub *= sub_env * duck_p * 0.3
    # 2. dark pad, just-intonation Fm7 on F1 (F2 C3 | F3 Ab3 C4 Eb4): pure fifths and octaves, so the
    #    low voices never beat against each other (an equal-tempered fifth beats at ~0.3 Hz down
    #    here, a slow 3-4 dB pumping of the bed). The two low voices are single saws (steady), the
    #    upper four gently detuned 7-voice stacks (a slow, even shimmer). Low-pass opens 320 Hz -> 2 kHz.
    voices = [(2.0, 0.7, 0.0, 1), (3.0, 0.55, 0.0, 1), (4.0, 0.6, 0.6, 7), (4.8, 0.5, 0.75, 7), (6.0, 0.36, 0.8, 7),
              (7.2, 0.25, 0.85, 7)]
    pad = np.zeros((2, n))
    for i, (ratio, a, spread, nv) in enumerate(voices):
        pad += supersaw(F1 * ratio, n, voices=nv, detune_cents=4.0, seed=(seed + 1) * 7 + i, spread=spread) * a
    fc = 320.0 * (2000.0 / 320.0) ** (u ** 1.35)
    pad = tv_biquad(pad, 'lowpass', fc, 0.75, block=64, stages=2)
    pad = hp(pad, 60.0, 2)
    pad = eq(eq(pad, 'peak', 240.0, 0.8, -4.0), 'peak', 700.0, 1.0, 2.0)  # less low-mid mud, more phone presence
    # level: -3 dB under the hit, opens by 2 s, +1 dB more through the build, then recedes 5 dB in the
    # last 0.55 s so the riser / suck carry the climax
    pad_env = smoothstep(t / 0.7) * 10.0 ** ((-3.0 + 2.0 * smoothstep((t - 0.8) / 1.2)
                                              + 1.0 * smoothstep((t - 0.52 * dur) / (0.32 * dur))
                                              - 5.0 * smoothstep((t - (dur - 0.55)) / 0.5)) / 20.0)
    duck_a = duck_env(n, list(accent_samples), 0.3, release=0.35, attack=0.003, curve=1.6)
    duck_pp = duck_env(n, list(pulse_samples), 0.18, release=0.3, attack=0.002, curve=1.6)
    pad *= (pad_env * duck_a * duck_pp)[None, :]
    # 3. faint dark air: band noise around 500 Hz with a slow drift (room tone, not hiss)
    mag = lambda tt, f: band_mag(520.0, 1.1)(f) * (0.8 + 0.2 * np.sin(TAU * 0.17 * tt + 1.0)) * np.ones_like(f)
    air = FX._decor(n, mag, seed + 40, 0.4) * (smoothstep(t / 1.5) * 0.09)[None, :]
    bed = _mono(sub) + pad + air
    return [(bed, 0, {'hall': 0.06})]


# --------------------------------------------------------------------------- end-aligned
def low_riser(seed, dur, root_midi=53, stop=0.0015, hold=0.025):
    """Low cinematic riser ENDING at the cue: root + fifth (detuned saws) gliding up an octave onto
    `root_midi` / +7 through an opening low-pass, plus dark band noise climbing to ~3 kHz. Reaches
    full level `hold` s before the cue, then a `stop` s raised-cosine stop."""
    n = ns(dur)
    t = taxis(n)
    x = t / dur
    xe = np.minimum(t / max(dur - hold, 1e-3), 1.0)
    r = rng('intro-riser', seed)
    glide = 2.0 ** (xe ** 1.8 - 1.0)  # one octave up, slow start, accelerating
    tone = np.zeros((2, n))
    for ratio, a in ((1.0, 1.0), (1.5, 0.6), (0.5, 0.45)):  # root, just fifth, octave below
        f = float(midi_hz(root_midi)) * ratio * glide
        v = np.zeros((2, n))
        for c, det in enumerate((-7.0, 7.0)):
            v[c] = saw(f * 2 ** (det / 1200), n, r.random()) + saw(f * 2 ** (-det / 2400), n, r.random())
        tone += width(v, 0.6) * a
    tone = tv_biquad(tone, 'lowpass', 260.0 + 2400.0 * xe ** 2.2, 0.8, block=64, stages=2)
    tone = hp(tone, 70.0, 2)
    tone *= (xe ** 1.3 * 0.2)[None, :]

    def mag(tt, f):
        uu = np.clip(tt / max(dur - hold, 1e-3), 0, 1)
        fc = 170.0 * (2400.0 / 170.0) ** (uu ** 1.4)
        z = np.log2(np.maximum(f, 1.0) / fc) / (1.0 - 0.45 * uu)
        return np.exp(-0.5 * z * z) + 0.02

    nz = FX._decor(n, mag, seed + 3, 0.6) * (xe ** 0.8)[None, :]
    air = FX._decor(n, lambda tt, f: band_mag(6500.0, 0.6)(f) * np.ones_like(tt), seed + 5, 0.4)
    air *= (smoothstep((x - 0.55) / 0.45) ** 2 * 0.10)[None, :]
    sig = tone + nz + air
    sig = fades(sig, 0.03, stop)
    return [(sig, -n, {'hall': 0.08})]


def suck(seed, dur, chord_midis, ir, stop=0.0015, hold=0.02):
    """Reverse swell / zoom-in whoosh ENDING at the cue with a `stop` s stop.
    1. the reversed dark-hall tail of a short Fm9 hit (the reel's first chord), ending at the
       reverb's loudest point, so it 'sucks' into the cut;
    2. an accelerating band-noise whoosh (380 Hz -> 2 kHz) whose stereo image narrows to the
       centre as the camera dives into the screen."""
    n = ns(dur)
    t = taxis(n)
    x = t / dur
    xe = np.minimum(t / max(dur - hold, 1e-3), 1.0)
    # 1. reversed reverb
    src_n = ns(0.3)
    ts = taxis(src_n)
    src = np.zeros(src_n)
    for i, m in enumerate(chord_midis):
        src += saw(float(midi_hz(m)), src_n, 0.37 * i) * np.exp(-ts / 0.09)
    src = lp(src, 1800.0, 2)
    src += bp(FX._noise(src_n, 'is-src', seed), 250.0, 3500.0, 2) * np.exp(-ts / 0.03) * 1.2
    src[:24] *= cos_ramp(24)
    buf = np.zeros(ir.shape[1] + src_n)
    buf[:src_n] = src
    wet = convolve_ir(buf, ir)
    env = np.sqrt(np.convolve(np.mean(wet ** 2, axis=0), np.ones(ns(0.01)) / ns(0.01), mode='same'))
    pk = int(np.argmax(env))
    rev = wet[:, pk:][:, ::-1][:, -n:]
    if rev.shape[1] < n:
        rev = np.concatenate([np.zeros((2, n - rev.shape[1])), rev], axis=1)
    rev = width(rev / (np.max(np.abs(rev)) + 1e-12), 0.6) * smoothstep(x / 0.15)[None, :]  # its own exponential rise

    # 2. zoom-in whoosh
    def mag(tt, f):
        uu = np.clip(tt / max(dur - hold, 1e-3), 0, 1)
        fc = 380.0 * (2000.0 / 380.0) ** (uu ** 1.6)
        z = np.log2(np.maximum(f, 1.0) / fc) / (0.95 - 0.3 * uu)
        return np.exp(-0.5 * z * z)

    wh = FX._decor(n, mag, seed + 7, 0.5)
    wh = wh * (xe ** 1.2)[None, :]
    mid, side = 0.5 * (wh[0] + wh[1]), 0.5 * (wh[0] - wh[1]) * (1.0 - 0.7 * smoothstep(x))
    wh = np.vstack([mid + side, mid - side])
    sig = rev * 0.8 + wh * 1.2
    sig = fades(sig, 0.03, stop)
    return [(sig, -n, {})]


# --------------------------------------------------------------------------- dispatch
def render_cue(cue, idx, ctx):
    """One intro cue -> [(stereo signal, offset, sends)], level-set per LEVELS (+ cue gain).
    ctx: chord (midis for the suck), ir_suck, pulse_samples, accent_samples."""
    typ = cue['type']
    seed = 2000 + idx
    s = ns(cue['t'])
    gain = float(cue.get('gain', 0.0))
    dur = float(cue.get('dur', 0.5))
    if typ == 'bass_hit':
        layers = bass_hit(seed, s)
    elif typ == 'accent':
        layers = accent(seed, s)
    elif typ == 'pulse':
        layers = pulse(seed, s)
    elif typ == 'whoosh':
        sig = FX.whoosh(dur, [0, 0.58, 1], [190.0, 1350.0, 380.0], 0.58, 2.4, 0.7, -0.3, 0.3, seed,
                        air=0.18, air_mult=2.8, corr=0.7, body=0.5)
        layers = [(sig, 0, {'hall': 0.18})]
    elif typ == 'riser':
        layers = low_riser(seed, dur)
    elif typ == 'suck':
        layers = suck(seed, dur, ctx['chord'], ctx['ir_suck'])
    elif typ == 'tension':
        return tension(seed, dur, ctx.get('pulse_samples', ()), ctx.get('accent_samples', ()))
    else:
        raise ValueError(f'unknown intro cue type {typ}')
    rms, _ = FX.ref_level(layers)
    g = 10.0 ** ((LEVELS[typ] + gain) / 20.0) / rms
    return [(sig * g, off, sends) for sig, off, sends in layers]
