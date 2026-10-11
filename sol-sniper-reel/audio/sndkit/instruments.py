"""Music instruments. Each returns a mono (n,) or stereo (2, n) array starting at
its onset sample (no pre-roll), so it can be dropped on the grid with add_at."""
import numpy as np

from .dsp import (SR, TAU, bp, cos_ramp, eq, fades, hp, lp, midi_hz, ns, pan, rng, saw, sat,
                  soft_norm_sat, supersaw, taxis, tv_biquad)

KICK_TUNE = midi_hz(29)  # F1 (43.65 Hz): the kick is tuned to the key


# --------------------------------------------------------------------------- drums
def kick(vel=1.0, soft=False, seed=0):
    """Sine body with fast exponential pitch drop (~150 -> 44 Hz), ~300 ms decay,
    a 3 ms band-passed click and gentle tanh saturation."""
    n = ns(0.46)
    t = taxis(n)
    f = KICK_TUNE + (158.0 - KICK_TUNE) * np.exp(-t / 0.036) + 130.0 * np.exp(-t / 0.004)
    body = np.sin(TAU * np.cumsum(f) / SR)
    amp = np.exp(-(t / 0.175) ** 1.8)
    body *= amp
    r = rng('kick-click', seed)
    click = r.standard_normal(n) * np.exp(-t / 0.0011)
    click[:8] *= cos_ramp(8)
    click = bp(click, 1400.0, 6500.0, 2) * 0.55
    knock = np.sin(TAU * 210.0 * t) * np.exp(-t / 0.012) * 0.10  # small mid "knock" for phone speakers
    x = body + click + knock
    x = soft_norm_sat(x * 1.05, 2.0)
    # parallel driven layer, band-limited to 120-900 Hz: harmonics that carry the kick on phones
    drive = np.tanh(4.0 * body)
    x += lp(hp(drive, 120.0, 2), 900.0, 2) * 0.22
    x = fades(x, 0.0, 0.06)
    if soft:
        x = lp(x, 900.0, 2) * 1.08
    return x * vel


def clap(vel=1.0, seed=0):
    """Four band-passed noise bursts ~10 ms apart; the last one carries the tail."""
    n = ns(0.32)
    r = rng('clap', seed)
    t = taxis(n)
    noise = r.standard_normal(n)
    env = np.zeros(n)
    offs = [0.0, 0.0105, 0.0205, 0.0315]
    amps = [0.72, 0.62, 0.85, 1.0]
    for i, (o, a) in enumerate(zip(offs, amps)):
        tt = t - o
        tau = 0.0032 if i < 3 else 0.055
        e = np.where(tt >= 0, np.exp(-np.maximum(tt, 0) / tau), 0.0)
        e *= np.clip(tt / 0.0004, 0, 1)
        env = np.maximum(env, a * e)
    body = bp(noise, 900.0, 2600.0, 2) * 1.6
    pres = bp(noise, 2600.0, 6500.0, 2) * 0.75
    air = hp(noise, 7000.0, 2) * 0.3
    x = (body + pres + air) * env
    x = eq(x, 'peak', 1250.0, 1.4, 3.0)
    x = fades(x, 0.0, 0.05)
    return x * vel


def snare(vel=1.0, seed=0, bright=1.0):
    n = ns(0.3)
    t = taxis(n)
    r = rng('snare', seed)
    f = 178.0 + 40.0 * np.exp(-t / 0.01)
    body = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t / 0.055)
    body += 0.35 * np.sin(TAU * 331.0 * t) * np.exp(-t / 0.03)
    nz = bp(r.standard_normal(n), 1500.0, 9500.0 * bright, 2) * np.exp(-t / 0.05)
    nz[:12] *= cos_ramp(12)
    x = 0.55 * body + 0.9 * nz
    x = sat(x * 1.2, 1.3)
    return fades(x, 0.0, 0.04) * vel


def hat(vel=1.0, open_=False, seed=0):
    """High-passed noise (>7 kHz) with a soft metallic sheen; closed ~45 ms, open ~200 ms."""
    dur = 0.32 if open_ else 0.085
    n = ns(dur)
    t = taxis(n)
    r = rng('hat', open_, seed)
    nz = r.standard_normal(n)
    # a little inharmonic metal (sum of detuned squares, band-limited by the HP below)
    metal = np.zeros(n)
    for f in (317.0, 469.0, 563.0, 787.0, 840.0, 1243.0):
        metal += np.sign(np.sin(TAU * f * 1.37 * t + r.random() * TAU))
    x = nz + 0.18 * metal
    x = hp(x, 7000.0, 4)
    x = eq(x, 'peak', 9000.0, 1.2, 2.0)
    x = lp(x, 12500.0, 2)
    if open_:
        env = np.exp(-t / 0.075) * np.clip(1.0 - (t - 0.17) / 0.12, 0, 1)
    else:
        env = np.exp(-t / 0.013)
    env[:10] *= cos_ramp(10)
    return fades(x * env, 0.0, 0.01) * vel


def shaker(vel=1.0, seed=0):
    n = ns(0.09)
    t = taxis(n)
    r = rng('shaker', seed)
    x = bp(r.standard_normal(n), 4500.0, 10000.0, 2)
    env = np.minimum(t / 0.006, 1.0) ** 2 * np.exp(-np.maximum(t - 0.006, 0) / 0.02)
    return fades(x * env, 0.0, 0.01) * vel


def crash(vel=1.0, seed=0, dur=1.6):
    n = ns(dur)
    t = taxis(n)
    out = np.zeros((2, n))
    for c in range(2):
        r = rng('crash', seed, c)
        x = r.standard_normal(n)
        x = hp(x, 3800.0, 2)
        x = tv_biquad(x, 'lowpass', 13000.0 * np.exp(-t / 0.9) + 4500.0, 0.6, block=64)
        out[c] = x
    env = np.exp(-t / 0.42)
    env[:20] *= cos_ramp(20)
    return fades(out * env, 0.0, 0.2) * vel


# --------------------------------------------------------------------------- tonal
def bass_note(midi, dur, vel=1.0, mid=0.42, cutoff=380.0, attack=0.004, release=0.03, decay=0.9, drive=1.2):
    """Sub sine (+ a touch of 2nd harmonic) with a low-passed saw layer for small-speaker
    translation. Mono, phase-coherent from zero (no click)."""
    n = ns(dur + release)
    t = taxis(n)
    f = float(midi_hz(midi))
    ph = TAU * f * t
    sub = np.sin(ph) + 0.10 * np.sin(2 * ph)
    mids = saw(f, n, 0.5)
    mids = lp(mids, cutoff, 4) * mid
    x = sub + mids
    env = np.exp(-t / decay)
    na = ns(attack)
    env[:na] *= cos_ramp(na)
    off = ns(dur)
    env[off:] *= cos_ramp(n - off)[::-1] if n - off > 0 else 1.0
    x = sat(x * env * 1.25, drive)
    return x * vel


def pluck(midi, vel=1.0, cut_peak=2500.0, cut_base=350.0, decay=0.16, seed=0, dur=0.42):
    """Two detuned saws through an enveloped 4-pole low-pass."""
    n = ns(dur)
    t = taxis(n)
    f = float(midi_hz(midi))
    r = rng('pluck', seed)
    x = saw(f * 2 ** (6 / 1200), n, r.random()) + saw(f * 2 ** (-6 / 1200), n, r.random())
    x += 0.35 * np.sin(TAU * f * 0.5 * t)  # soft sub-octave body
    fc = cut_base + (cut_peak - cut_base) * np.exp(-t / 0.055)
    x = tv_biquad(x, 'lowpass', fc, 0.9, block=32, stages=1)
    x = lp(x, max(cut_peak * 1.5, 2000.0), 2)
    env = np.exp(-t / decay)
    env[:ns(0.0015)] *= cos_ramp(ns(0.0015))
    return fades(x * env * 0.5, 0.0, 0.03) * vel


def pad(midis, dur, attack=0.5, release=0.6, cutoff=1800.0, seed=0, voices=7, detune=12.0,
        hp_f=170.0, q=0.6, stages=2):
    """Supersaw chord pad (7 voices +-12 cents), slow attack, low-passed, wide. Stereo.
    cutoff may be scalar or per-sample array (length of dur+release)."""
    n = ns(dur + release)
    out = np.zeros((2, n))
    for i, m in enumerate(midis):
        out += supersaw(float(midi_hz(m)), n, voices, detune, seed=seed * 31 + i * 7 + int(m))
    out /= np.sqrt(len(midis))
    if np.ndim(cutoff) == 0:
        out = lp(out, float(cutoff), 2)
    else:
        out = tv_biquad(out, 'lowpass', cutoff, q, block=64, stages=stages)
    out = hp(out, hp_f, 2)
    t = taxis(n)
    env = np.clip(t / max(attack, 1e-3), 0, 1)
    env = 0.5 - 0.5 * np.cos(np.pi * env)
    rel = np.clip((t - dur) / max(release, 1e-3), 0, 1)
    env *= 0.5 + 0.5 * np.cos(np.pi * rel)
    return out * env


def stab(midis, vel=1.0, seed=0, decay=0.10, cut_peak=7000.0, cut_base=1700.0, dur=0.36):
    """Short supersaw chord stab with fast filter envelope. Stereo."""
    n = ns(dur)
    t = taxis(n)
    out = np.zeros((2, n))
    for i, m in enumerate(midis):
        out += supersaw(float(midi_hz(m)), n, 5, 9.0, seed=seed * 13 + i, spread=0.7)
    out /= np.sqrt(len(midis))
    fc = cut_base + (cut_peak - cut_base) * np.exp(-t / 0.045)
    out = tv_biquad(out, 'lowpass', fc, 0.8, block=32, stages=1)
    out = lp(out, 9000.0, 2)
    out = hp(out, 200.0, 2)
    env = np.exp(-t / decay) * 0.85 + 0.15 * np.exp(-t / (decay * 3))
    env[:ns(0.002)] *= cos_ramp(ns(0.002))
    out = sat(out * env * 1.4, 1.1)
    return fades(out, 0.0, 0.05) * vel


def keys(midis, dur, vel=1.0, seed=0, spread=0.5, lp_f=3800.0, hp_f=120.0):
    """Warm FM electric-piano chord (1:1 carrier/modulator, decaying index). Stereo."""
    n = ns(dur)
    t = taxis(n)
    out = np.zeros((2, n))
    k = len(midis)
    for i, m in enumerate(midis):
        f = float(midi_hz(m))
        idx = 1.1 * np.exp(-t / 0.28) + 0.12
        ph = TAU * f * t
        x = np.sin(ph + idx * np.sin(ph + 0.3))
        x += 0.06 * np.sin(TAU * f * 4.0 * t) * np.exp(-t / 0.05)  # soft tine
        a = np.exp(-t / (2.2 - 0.08 * i)) * 0.8 + 0.2 * np.exp(-t / 0.4)
        a[:ns(0.004)] *= cos_ramp(ns(0.004))
        p = (i / max(k - 1, 1) - 0.5) * 2 * spread
        out += pan(x * a, p)
    out /= np.sqrt(k)
    out = lp(out, lp_f, 2)
    out = hp(out, hp_f, 2)
    return fades(out, 0.0, 0.3) * vel


def shimmer(midis, dur, attack=0.35, release=1.0, seed=0, air=0.35, tone=0.5):
    """Soft top line over a sustained chord: sine partials (chord tones two octaves up), each
    slowly breathing at its own rate, plus a faint 7-16 kHz breath band. Wide but correlated
    (mono-safe). Stereo."""
    n = ns(dur + release)
    t = taxis(n)
    r = rng('shimmer', seed)
    out = np.zeros((2, n))
    for i, m in enumerate(midis):
        f = float(midi_hz(m))
        ph = r.random() * TAU
        for c in range(2):
            wob = 0.7 + 0.3 * np.sin(TAU * (0.6 + 0.29 * i + 0.07 * c) * t + r.random() * TAU)
            out[c] += np.sin(TAU * f * t + ph + 0.25 * c) * wob
    out *= tone / len(midis)
    common = r.standard_normal(n)
    breath = np.vstack([0.75 * common + 0.66 * r.standard_normal(n), 0.75 * common + 0.66 * r.standard_normal(n)])
    breath = lp(hp(breath, 7000.0, 2), 16000.0, 2) * air
    out = out + breath
    env = np.clip(t / attack, 0, 1)
    env = 0.5 - 0.5 * np.cos(np.pi * env)
    rel = np.clip((t - dur) / release, 0, 1)
    env *= 0.5 + 0.5 * np.cos(np.pi * rel)
    return out * env
