"""Sound design: one synthesizer per cue type (cue semantics: see the top of build_audio.py).

Each synth returns a list of layers (signal, offset_samples, sends) where
`signal` is stereo (2, n), `offset_samples` is relative to the cue sample
(negative for sounds that END at the cue: riser, reverse_swell), and `sends`
maps reverb bus name -> send gain. Transient sounds start exactly on the cue
sample (no pre-roll), so their onset IS the cue time.
"""
import numpy as np

from .dsp import (SR, TAU, band_mag, bp, bump, convolve_ir, cos_ramp, fades, hp, logpath, lp, midi_hz,
                  ns, pan, rng, saw, sat, shaped_noise, smoothstep, taxis, tv_biquad, width)

# Default level per type, before the cue's own gain offset. Every cue is first normalised so
# that its loudest 10 ms window (RMS, both channels) is 0 dBFS, then set to this level. The
# music bus is calibrated so the drop section measures -16 LUFS (ungated) in the same domain.
# Balance: the drop impact is the loudest event (the opening impact sits ~2.5 dB under it), the
# build-ups stay low enough that the pre-drop gap really dips, UI sounds are subtle (see PEAK_CAP).
LEVELS = {
    'impact_big': -8.5, 'impact_drop': -6.0, 'impact_outro': -12.0, 'hit_cut': -13.0,
    'whoosh_fast': -20.0, 'whoosh_long': -19.0, 'whoosh_rise': -21.0, 'zoom_through': -17.0,
    'riser': -25.0, 'reverse_swell': -26.0,
    'click': -19.0, 'tap_soft': -19.0, 'ui_blip': -20.0, 'success': -19.0, 'toast': -19.0,
    'tick': -23.0, 'text_reveal': -24.0,
    'whip': -17.0, 'punch': -14.0, 'click_final': -15.0,
}

# UI transients also get a sample-peak cap (dB, before the cue's own gain offset): their 15-20 dB
# crest factor would otherwise put their peaks level with the impacts and make the master limiter
# pump on every click.
PEAK_CAP = {'click': -7.5, 'tap_soft': -7.5, 'tick': -7.5, 'toast': -7.5, 'click_final': -6.0, 'punch': -5.0}

# Music ducking while a cue plays (look-ahead, offline): (band, depth dB, hold s, release s).
# 'ui' ducks only the music's 1-8 kHz band (makes room for UI sounds without losing the groove),
# 'tone' ducks 500 Hz-8 kHz (the success dyad sits around 700-950 Hz),
# 'full' is a light broadband dip so hits and impacts punch through.
DUCK = {
    'click': ('ui', 6.0, 0.05, 0.12), 'tap_soft': ('ui', 6.0, 0.05, 0.12), 'tick': ('ui', 6.0, 0.03, 0.1),
    'ui_blip': ('ui', 4.0, 0.08, 0.14), 'success': ('tone', 6.0, 0.25, 0.2), 'toast': ('ui', 3.0, 0.18, 0.16),
    'hit_cut': ('full', 1.5, 0.04, 0.15), 'impact_drop': ('full', 2.0, 0.08, 0.3),
    'impact_outro': ('full', 1.5, 0.1, 0.4),
    'click_final': ('ui', 4.0, 0.08, 0.25), 'punch': ('full', 1.0, 0.03, 0.12),
}

TRANSIENT_TYPES = ('impact_big', 'impact_drop', 'impact_outro', 'hit_cut', 'punch', 'click', 'click_final',
                   'tap_soft', 'tick', 'ui_blip', 'success', 'toast')
# cues whose sound ENDS at t (rendered at a negative offset); everything else starts at t
END_ALIGNED = ('riser', 'reverse_swell', 'whip')


def _noise(n, *seed):
    return rng(*seed).standard_normal(n)


def _onset_ramp(x, samples=3):
    """Very short attack ramp that still leaves energy on the first sample."""
    x = np.array(x, copy=True)
    k = np.linspace(0.45, 1.0, samples, endpoint=False)
    x[..., :samples] *= k
    return x


def _glide_sine(f_start, f_end, tau, n, phase0=0.0):
    t = taxis(n)
    f = f_end + (f_start - f_end) * np.exp(-t / tau)
    return np.sin(TAU * np.cumsum(f) / SR + phase0)


def _decor(n, mag_fn, seed, corr=0.6):
    """Stereo noise pair with a given inter-channel correlation (0 = independent)."""
    a = shaped_noise(n, mag_fn, seed)
    b = shaped_noise(n, mag_fn, seed + 101)
    c = shaped_noise(n, mag_fn, seed + 202)
    k = np.sqrt(corr)
    j = np.sqrt(1 - corr)
    return np.vstack([k * a + j * b, k * a + j * c])


# --------------------------------------------------------------------------- impacts
def impact(kind, seed, low_delay=0, low_polarity=1.0, low_only=False):
    """Layered impact: sub drop + low boom + punch + bright transient (+ reverb via sends).

    `low_delay` (samples) / `low_polarity` move only the low layers (sub + boom + their harmonics)
    so they sum with a grid kick a few ms off the frame-snapped cue instead of cancelling it (see
    render_cue); the punch and the bright transient stay on the cue sample, so the onset is unchanged.
    low_only=True returns just the mono low layer (for that alignment search)."""
    P = {
        # sub glides end on F1 (43.65 Hz, the kick's tuning) for big/drop, Db1 for the outro chord
        'big':   dict(dur=3.4, f0=72.0, f1=43.65, ftau=0.32, sub_t=0.45, sub_p=1.3, sub_a=0.72,
                      boom=0.6, boom_tau=0.30, punch=1.3, trans=0.6, trans_lp=11000.0, hall=0.6,
                      bloom=0.4, harm=0.8, low_hp=32.0),
        'drop':  dict(dur=2.2, f0=64.0, f1=43.65, ftau=0.2, sub_t=0.38, sub_p=1.35, sub_a=0.65,
                      boom=0.55, boom_tau=0.16, punch=1.2, trans=1.15, trans_lp=12500.0, hall=0.45,
                      bloom=0.0, harm=0.7, low_hp=32.0),
        'outro': dict(dur=2.6, f0=69.3, f1=34.65, ftau=0.4, sub_t=0.5, sub_p=1.3, sub_a=0.60,
                      boom=0.5, boom_tau=0.40, punch=1.2, trans=1.0, trans_lp=7000.0, hall=0.8,
                      bloom=0.35, harm=0.3, low_hp=26.0),
    }[kind]
    n = ns(P['dur'])
    t = taxis(n)
    # 1. sub drop
    sub = _glide_sine(P['f0'], P['f1'], P['ftau'], n)
    sub *= np.exp(-(t / P['sub_t']) ** P['sub_p'])
    sub[:ns(0.002)] *= cos_ramp(ns(0.002))
    sub = sat(sub * 1.3, 1.25) * P['sub_a']
    # 2. low boom: pitched thump + low-passed noise
    boom_t = _glide_sine(115.0, 47.0, 0.045, n) * np.exp(-t / P['boom_tau'])
    boom_n = lp(_noise(n, 'imp-boom', kind, seed), 170.0, 4) * 6.0 * np.exp(-t / (P['boom_tau'] * 0.7))
    boom = (0.7 * boom_t + 0.5 * boom_n) * P['boom']
    # 3. punch: low-mid body
    punch = bp(_noise(n, 'imp-punch', kind, seed), 180.0, 950.0, 2) * 2.2 * np.exp(-t / 0.045)
    punch += 0.5 * _glide_sine(220.0, 120.0, 0.02, n) * np.exp(-t / 0.05)
    punch *= P['punch']
    # 4. bright transient (stereo, slightly decorrelated)
    tr = np.zeros((2, n))
    for c in range(2):
        z = _noise(n, 'imp-tr', kind, seed, c)
        crack = bp(z, 1800.0, min(P['trans_lp'], 9000.0), 2) * np.exp(-t / 0.0045)
        sizzle = hp(z, 3000.0, 2) * np.exp(-t / 0.018) * 0.35
        tr[c] = lp(crack * 1.6 + sizzle, P['trans_lp'], 2)
    tr = width(tr, 0.6) * P['trans']
    # 5. bloom: soft low-mid air that swells into the reverb (big / outro)
    bloom = np.zeros((2, n))
    if P['bloom'] > 0:
        mag = lambda tt, f: band_mag(420.0, 1.1)(f) * np.ones_like(tt)
        b = np.vstack([shaped_noise(n, mag, seed + 7), shaped_noise(n, mag, seed + 8)])
        benv = (1 - np.exp(-t / 0.03)) * np.exp(-t / 0.55)
        bloom = b * benv * P['bloom'] * 2.0
    low = hp(sub + boom, P['low_hp'], 2)  # nothing below the sub's last note: saves headroom
    # 6. harmonics of the low layers (driven copy, 140 Hz-1.6 kHz): lets the boom read on phone
    #    speakers that cannot reproduce the sub itself (missing-fundamental effect)
    harm = np.tanh(3.0 * low / (np.max(np.abs(low)) + 1e-9))
    harm = lp(hp(harm, 140.0, 2), 1600.0, 2) * P['harm']
    low = (low + harm) * low_polarity
    boom = boom * low_polarity
    if low_only:
        return low
    if 0 < low_delay < n:
        low = np.concatenate([np.zeros(low_delay), low[:-low_delay]])
        boom = np.concatenate([np.zeros(low_delay), boom[:-low_delay]])
    dry = np.vstack([low, low]) + np.vstack([punch, punch]) + tr + bloom
    # reverb feeds: everything except the sub (keeps the low end clean)
    wet_feed = np.vstack([boom * 0.5 + punch, boom * 0.5 + punch]) + tr * 1.2 + bloom
    dry = _onset_ramp(dry, 3)
    wet_feed = _onset_ramp(wet_feed, 3)
    dry = fades(dry, 0.0, 0.25)
    return [(dry, 0, {}), (wet_feed, 0, {'hall_big': P['hall'], 'glue': 0.12, '_dry': 0.0})]


def hit_cut(seed, knock=True, snap_amt=1.9):
    """Tight cinematic cut accent: bright snap + short mid 'thock' + light low knock + room.

    knock=False drops the low knock when a grid kick lands a few ms off the cue (the kick carries
    the low end there, and two low transients 7-13 ms apart partly cancel). snap_amt is lowered
    when a grid clap is within 20 ms, so the on-grid clap carries the timing (no flam)."""
    n = ns(0.5)
    t = taxis(n)
    st = np.zeros((2, n))
    for c in range(2):
        z = _noise(n, 'hit', seed, c)
        snap = bp(z, 1500.0, 7500.0, 2) * (np.exp(-t / 0.006) + 0.12 * np.exp(-t / 0.035))
        st[c] = snap * snap_amt
    st = width(st, 0.5)
    thock = _glide_sine(205.0, 118.0, 0.018, n) * np.exp(-t / 0.038) * 0.75
    knock = _glide_sine(92.0, 56.0, 0.03, n) * np.exp(-t / 0.06) * (0.38 if knock else 0.0)
    body = bp(_noise(n, 'hit-body', seed), 300.0, 1400.0, 2) * np.exp(-t / 0.02) * 1.2
    mono = thock + knock + body
    x = st + np.vstack([mono, mono])
    x = _onset_ramp(fades(x, 0.0, 0.1), 3)
    return [(x, 0, {'room': 0.35, 'hall_big': 0.10, 'glue': 0.06})]


# --------------------------------------------------------------------------- whooshes
def whoosh(dur, path_x, path_f, peak, k, sigma, pan_from, pan_to, seed, air=0.3, air_mult=3.2,
           corr=0.65, body=0.0):
    n = ns(dur)
    x01 = taxis(n) / dur

    def mag(tt, f):
        fc = logpath(np.clip(tt / dur, 0, 1), path_x, path_f)
        z = np.log2(np.maximum(f, 1.0) / fc) / sigma
        return np.exp(-0.5 * z * z) + 0.05 * np.exp(-0.5 * (z / 3.0) ** 2)

    def mag_air(tt, f):
        fc = logpath(np.clip(tt / dur, 0, 1), path_x, path_f) * air_mult
        z = np.log2(np.maximum(f, 1.0) / np.minimum(fc, 14000.0)) / 0.8
        return np.exp(-0.5 * z * z)

    main = _decor(n, mag, seed, corr)
    hi = _decor(n, mag_air, seed + 5, 0.3) * air
    env = bump(x01, peak, k)
    env = env * cos_ramp(n)[::-1] ** 0.25
    sig = (main + hi) * env
    if body > 0:
        mb = lambda tt, f: band_mag(170.0, 0.6)(f) * np.ones_like(tt)
        b = shaped_noise(n, mb, seed + 9) * bump(x01, peak, k + 1) * body
        sig += np.vstack([b, b])
    # stereo motion
    p = pan_from + (pan_to - pan_from) * smoothstep(x01)
    gl = np.sqrt(2.0) * np.cos((np.clip(p, -1, 1) + 1) * np.pi / 4)
    gr = np.sqrt(2.0) * np.sin((np.clip(p, -1, 1) + 1) * np.pi / 4)
    sig = np.vstack([sig[0] * gl, sig[1] * gr])
    sig = fades(sig, 0.004, 0.02)
    return sig / 0.35  # band noise is ~0.3 rms; bring to ~unity


def whoosh_fast(seed, p=0.0, d=1.0):
    sig = whoosh(0.27, [0, 0.36, 1], [330.0, 2900.0, 620.0], 0.36, 3.0, 0.55, p - 0.5 * d, p + 0.5 * d, seed,
                 air=0.35, body=0.25)
    return [(sig, 0, {'hall_big': 0.12, 'glue': 0.08})]


def whoosh_long(seed, dur, p=0.0, d=1.0):
    sig = whoosh(dur, [0, 0.55, 1], [300.0, 2300.0, 520.0], 0.55, 2.6, 0.6, p - 0.55 * d, p + 0.55 * d, seed,
                 air=0.3, body=0.3)
    return [(sig, 0, {'hall_big': 0.12, 'glue': 0.10})]


def whoosh_rise(seed, p=0.0, d=1.0):
    sig = whoosh(0.66, [0, 0.25, 1], [320.0, 1500.0, 5600.0], 0.22, 2.0, 0.6, p - 0.25 * d, p + 0.25 * d, seed,
                 air=0.45, air_mult=2.4, body=0.2)
    return [(sig, 0, {'hall_big': 0.18, 'glue': 0.1})]


def zoom_through(seed, dur):
    """Accelerating whoosh into the cut, landing on a soft thump at t+dur."""
    tail = 0.42
    n = ns(dur + tail)
    t = taxis(n)
    nd = ns(dur)

    def mag(tt, f):
        x = np.clip(tt / dur, 0, 1.6)
        fc = np.where(x <= 1, logpath(x, [0, 1], [520.0, 4800.0]), logpath(np.clip(x - 1, 0, 0.6) / 0.6, [0, 1], [4800.0, 900.0]))
        z = np.log2(np.maximum(f, 1.0) / fc) / 0.7
        return np.exp(-0.5 * z * z)

    w = _decor(n, mag, seed, 0.55)
    env = np.where(t <= dur, (t / dur) ** 2.2, np.exp(-(t - dur) / 0.045))
    w = w * env * 2.4
    w = fades(w, 0.003, 0.02)
    # soft thump at the cut
    th = np.zeros(n)
    m = n - nd
    tt = taxis(m)
    th_body = _glide_sine(96.0, 46.0, 0.05, m) * np.exp(-tt / 0.12)
    puff = lp(_noise(m, 'zoom-puff', seed), 700.0, 2) * np.exp(-tt / 0.035) * 2.2
    th[nd:] = (th_body * 0.9 + puff * 0.6)
    th[nd:nd + 24] *= cos_ramp(24)
    sig = w + np.vstack([th, th])
    return [(sig, 0, {'hall_big': 0.2, 'room': 0.15, 'glue': 0.1})]


# --------------------------------------------------------------------------- build-ups
def riser(seed, dur, target_midi=53):
    """Band-passed noise sweeping up + quiet rising tonal layer, crescendo ending AT the cue."""
    n = ns(dur)
    x = taxis(n) / dur

    def mag(tt, f):
        u = np.clip(tt / dur, 0, 1)
        fc = 260.0 * (7200.0 / 260.0) ** (u ** 1.3)
        sig = 0.95 - 0.5 * u
        z = np.log2(np.maximum(f, 1.0) / fc) / sig
        return np.exp(-0.5 * z * z) + 0.04

    nz = _decor(n, mag, seed, 0.7)
    air = _decor(n, lambda tt, f: (np.clip(f / 9000.0, 0, 1) ** 2) * np.ones_like(tt), seed + 3, 0.5) * 0.25
    xe = np.minimum(x / (1.0 - 0.04 / dur), 1.0)  # reaches full level 40 ms before the cue, then holds
    env = xe ** 2.3
    sig = (nz + air * x[None, :]) * env * 2.4
    # tonal layer: two detuned saws gliding up an octave onto the target, low-passed
    f_end = float(midi_hz(target_midi))
    f = f_end * 2.0 ** ((x ** 1.6 - 1.0))
    r = rng('riser-tone', seed)
    tone = saw(f * 2 ** (8 / 1200), n, r.random()) + saw(f * 2 ** (-8 / 1200), n, r.random())
    tone = tv_biquad(tone, 'lowpass', 400.0 + 4200.0 * x ** 2, 0.7, block=64, stages=2)
    tone = tone * xe ** 2.6 * 0.22
    sig += np.vstack([tone, tone])
    # (no extra width: the decorrelated noise is wide enough and stays mono-compatible)
    # end exactly at the cue with an 8 ms fade (the impact takes over)
    sig = fades(sig, 0.02, 0.008)
    return [(sig, -n, {'hall_big': 0.1})]


def reverse_swell(seed, dur, chord_midis, ir):
    """Reversed reverb tail of the target chord, ending exactly at the cue."""
    src_n = ns(0.3)
    t = taxis(src_n)
    src = np.zeros(src_n)
    for i, m in enumerate(chord_midis):
        f = float(midi_hz(m))
        src += saw(f, src_n, 0.5 + 0.1 * i) * np.exp(-t / 0.08)
    src = lp(src, 2600.0, 2)
    src += bp(_noise(src_n, 'rev-src', seed), 500.0, 6000.0, 2) * np.exp(-t / 0.02) * 0.8
    src[:24] *= cos_ramp(24)
    pad_n = ir.shape[1] + src_n
    buf = np.zeros(pad_n)
    buf[:src_n] = src
    wet = convolve_ir(buf, ir)
    env = np.sqrt(np.convolve(np.mean(wet ** 2, axis=0), np.ones(ns(0.01)) / ns(0.01), mode='same'))
    pk = int(np.argmax(env))
    rev = wet[:, pk:][:, ::-1]  # reversed tail, ending at the reverb's loudest point
    n = ns(dur)
    seg = rev[:, -n:]
    seg = seg / (np.max(np.abs(seg)) + 1e-12)
    x = taxis(n) / dur
    seg *= (x ** 1.2)[None, :]
    seg = fades(seg, 0.04, 0.008)
    seg = width(seg, 0.65)  # a reversed stereo reverb tail is nearly uncorrelated: narrow it (mono-safe)
    return [(seg, -n, {})]


# --------------------------------------------------------------------------- UI
def _modes(n, freqs, decays, amps, phase=0.0):
    t = taxis(n)
    x = np.zeros(n)
    for f, d, a in zip(freqs, decays, amps):
        x += a * np.sin(TAU * f * t + phase) * np.exp(-t / d)
    return x


def click(seed, p=0.0, release=True):
    """Realistic trackpad click: one crisp press, then a much softer release 80 ms later (well past
    the ~30-50 ms where two transients blur into a 'ti-tick'). The release is dropped when clicks
    follow each other quickly."""
    n = ns(0.14)
    t = taxis(n)

    def part(scale, amp, nseed):
        m = _modes(n, [2900.0 * scale, 4650.0 * scale, 7100.0 * scale, 1150.0 * scale],
                   [0.0026, 0.0017, 0.0009, 0.0045], [1.0, 0.75, 0.25, 0.45])
        z = hp(rng('click-n', seed, nseed).standard_normal(n), 2000.0, 2) * np.exp(-t / 0.00035) * 0.7
        return (m + z) * amp

    x = part(1.0, 1.0, 1)
    if release:
        d = ns(0.08)
        x[d:] += part(1.13, 0.22, 2)[:n - d]
    x = lp(hp(x, 600.0, 2), 9000.0, 2)
    x[:12] *= cos_ramp(12)  # 0.25 ms attack: still crisp, without a needle-thin full-scale spike
    x = fades(x, 0.0, 0.01)
    return [(pan(x, p), 0, {'room': 0.10})]


def tap_soft(seed, p=0.0):
    n = ns(0.1)
    t = taxis(n)
    m = _modes(n, [1750.0, 2650.0, 4100.0, 720.0], [0.0045, 0.003, 0.0016, 0.006], [1.0, 0.6, 0.25, 0.45])
    z = lp(hp(rng('tap', seed).standard_normal(n), 1200.0, 2), 5000.0, 2) * np.exp(-t / 0.0006) * 0.5
    x = m + z
    x[:ns(0.0004)] *= cos_ramp(ns(0.0004))
    x = lp(x, 6500.0, 2)
    x = fades(x, 0.0, 0.01)
    return [(pan(x, p), 0, {'room': 0.10})]


def tick(seed, p=0.0):
    n = ns(0.035)
    t = taxis(n)
    m = _modes(n, [4300.0, 6900.0, 2400.0], [0.0012, 0.0007, 0.0016], [1.0, 0.5, 0.4])
    z = hp(rng('tick', seed).standard_normal(n), 3000.0, 2) * np.exp(-t / 0.0003) * 0.6
    x = _onset_ramp(fades(m + z, 0.0, 0.006), 2)
    return [(pan(x, p), 0, {'room': 0.08})]


def ui_blip(seed, p=0.0):
    """Small modal glass tap (three inharmonic modes, 10 ms ring) with a 0.5 ms noise tick:
    a physical 'tink', not a synthesized beep."""
    n = ns(0.08)
    t = taxis(n)
    x = _modes(n, [1397.0, 2236.0, 3520.0], [0.010, 0.005, 0.0025], [1.0, 0.35, 0.15])
    z = hp(rng('blip-n', seed).standard_normal(n), 3000.0, 2) * np.exp(-t / 0.0005) * 0.3
    x = x + z
    x[:ns(0.0003)] *= cos_ramp(ns(0.0003))
    x = fades(x, 0.0, 0.02)
    return [(pan(x, p), 0, {'plate': 0.18})]


def _bell(f, n, decay, index=0.4):
    """Soft FM bell: low modulation index, faint upper partials (no glassy ring)."""
    t = taxis(n)
    idx = index * np.exp(-t / 0.035) + 0.08
    x = np.sin(TAU * f * t + idx * np.sin(TAU * 2.0 * f * t))
    x += 0.08 * np.sin(TAU * f * 3.0 * t) * np.exp(-t / 0.05)
    x += 0.03 * np.sin(TAU * f * 4.2 * t) * np.exp(-t / 0.018)
    env = np.exp(-t / decay)
    env[:ns(0.0015)] *= cos_ramp(ns(0.0015))
    return fades(x * env, 0.0, 0.03)


# success dyads: two upper tones of the chord the sound rings over (F minor key)
SUCCESS_DYADS = {'Fm9': (77, 80), 'Db': (77, 80), 'Eb': (79, 82), 'Cm7': (79, 82),
                 'Dbmaj9': (77, 80), 'Abmaj9': (79, 84)}


def success(seed, p=0.0, notes=(77, 80), decay=0.12):
    """Soft confirmation: the notes sound together (no rising arpeggio, nothing 'achievement'-like).
    Each occurrence takes its notes from the harmony and gets a slightly different strike."""
    n = ns(0.55)
    r = rng('success', seed)
    x = np.zeros((2, n))
    spread = 0.15 if len(notes) > 1 else 0.0
    for i, m in enumerate(notes):
        f = float(midi_hz(m)) * 2.0 ** (r.uniform(-3.0, 3.0) / 1200.0)
        b = _bell(f, n, decay * (1.0 - 0.15 * i), index=0.4 * r.uniform(0.85, 1.15))
        x += pan(b, p + (spread if i % 2 else -spread)) * (1.0 if i == 0 else 0.7)
    return [(x, 0, {'plate': 0.28})]


def toast(seed, p=0.25, pop=True):
    """Soft pop + airy swish (slides in from the right). pop=False renders the swish only (used
    right after a success sound, so the two don't pile up)."""
    n = ns(0.3)
    t = taxis(n)
    x = np.zeros((2, n))
    if pop:
        pp = _glide_sine(640.0, 380.0, 0.012, n) * np.exp(-t / 0.03)
        pp += 0.25 * _glide_sine(1280.0, 760.0, 0.012, n) * np.exp(-t / 0.012)
        pp[:ns(0.0008)] *= cos_ramp(ns(0.0008))
        pp = lp(pp, 3500.0, 2)
        pp += _modes(n, [3600.0, 5200.0, 2300.0], [0.0011, 0.0007, 0.0015], [1.1, 0.6, 0.5])
        x += pan(pp, p) * 0.9
    sw = whoosh(0.24, [0, 0.35, 1], [3000.0, 6500.0, 4200.0], 0.35, 2.6, 0.7, p + 0.5, p, seed,
                air=0.2, air_mult=1.5)
    x[:, :sw.shape[1]] += sw * 0.35
    x = _onset_ramp(fades(x, 0.0, 0.03), 2)
    return [(x, 0, {'plate': 0.18})]


def text_reveal(seed, p=0.0):
    """Airy shimmer swell: breathy high band + very quiet high partials of the tonic chord."""
    dur = 1.3
    n = ns(dur)
    t = taxis(n)

    def mag(tt, f):
        z = np.log2(np.maximum(f, 1.0) / 8200.0) / 0.85
        return np.exp(-0.5 * z * z)

    air = _decor(n, mag, seed, 0.15)
    env = smoothstep(np.clip(t / 0.30, 0, 1)) * np.exp(-np.maximum(t - 0.30, 0) / 0.40)
    sig = air * env * 2.2
    r = rng('shimmer', seed)
    for i, m in enumerate([92, 96, 99, 103]):  # Ab6 C7 Eb7 G7 (no F6: the UI tones live there)
        f = float(midi_hz(m))
        wob = 0.6 + 0.4 * np.sin(TAU * (1.3 + 0.7 * i) * t + r.random() * TAU)
        tone = np.sin(TAU * f * t + r.random() * TAU) * wob * env * 0.045
        sig += pan(tone, (-0.6, 0.6, -0.3, 0.3)[i])
    sig = fades(sig, 0.01, 0.1)
    return [(sig, 0, {'plate': 0.35})]


# --------------------------------------------------------------------------- camera moves
def whip(seed, dur, p=0.0, d=1.0):
    """Whip pan: an aggressive, accelerating whoosh that builds over `dur` and ENDS AT the cue
    with a sharp stop (2 ms), because the camera lands on t (usually on an impact).

    Band noise whose centre climbs 420 Hz -> 5.6 kHz and narrows as it speeds up, a resonant
    'rip' (Q 5 band sweeping 650 Hz -> 4.8 kHz: the pitched whistle of a fast pan), an air band
    riding above, a light low-mid body (kept above 110 Hz so the pre-drop gap stays clean under
    the impact's sub), turbulence flutter that speeds up (22 -> 60 Hz), and a stereo sweep across
    the field in the direction `d`, landing just past `p`. A little room/hall send lets the hard
    stop breathe, so it doesn't read as a digital cut."""
    dur = max(float(dur), 0.06)
    n = ns(dur)
    t = taxis(n)
    x = t / dur

    def mag(tt, f):
        u = np.clip(tt / dur, 0, 1)
        fc = 420.0 * (5600.0 / 420.0) ** (u ** 1.5)
        z = np.log2(np.maximum(f, 1.0) / fc) / (0.8 - 0.3 * u)
        return np.exp(-0.5 * z * z) + 0.03 * (f > 150.0)

    def mag_air(tt, f):
        u = np.clip(tt / dur, 0, 1)
        fc = np.minimum(1600.0 * (12500.0 / 1600.0) ** (u ** 1.3), 12500.0)
        z = np.log2(np.maximum(f, 1.0) / fc) / 0.6
        return np.exp(-0.5 * z * z)

    main = _decor(n, mag, seed, 0.6)
    air = _decor(n, mag_air, seed + 5, 0.3) * 0.45
    rip = np.zeros((2, n))
    for c in range(2):
        z = tv_biquad(_noise(n, 'whip-rip', seed, c), 'bandpass', 650.0 * (4800.0 / 650.0) ** (x ** 1.4), 5.0,
                      block=32, stages=1)
        rip[c] = z / (np.sqrt(np.mean(z ** 2)) + 1e-12)
    rip = width(rip, 0.5) * 0.4
    rate = 22.0 + 38.0 * x ** 1.5
    flutter = 1.0 - 0.32 * x * (0.5 + 0.5 * np.cos(TAU * np.cumsum(rate) / SR))
    env = x ** 2.0
    sig = (main + air + rip) * (env * flutter)[None, :]
    mb = lambda tt, f: band_mag(240.0, 0.5)(f) * np.ones_like(tt)
    body = hp(shaped_noise(n, mb, seed + 9), 110.0, 2) * x ** 3 * 0.35
    sig += np.vstack([body, body])
    sig = sat(sig * 1.4, 1.2) / 1.4  # a little grit: denser, more aggressive at the peak
    pth = (p - 0.8 * d) + 1.15 * d * x ** 1.6
    gl = np.sqrt(2.0) * np.cos((np.clip(pth, -1, 1) + 1) * np.pi / 4)
    gr = np.sqrt(2.0) * np.sin((np.clip(pth, -1, 1) + 1) * np.pi / 4)
    sig = np.vstack([sig[0] * gl, sig[1] * gr])
    sig = fades(sig, 0.008, 0.002)  # the stop: full level until 2 ms before t
    return [(sig / 0.35, -n, {'room': 0.12, 'hall_big': 0.05, 'glue': 0.05})]


def punch(seed, low_delay=0, low_polarity=1.0, low_only=False, thump=True):
    """Camera punch-in: tight low thump (165 -> 54 Hz, gone in ~120 ms) + a short mid body and a
    3 ms transient. No tail beyond a touch of room.

    low_delay / low_polarity move only the thump (as for the impacts) so it sums with a grid kick
    a few ms off the frame-snapped cue; thump=False drops it when an impact owns the low end."""
    n = ns(0.14)
    t = taxis(n)
    th = _glide_sine(165.0, 54.0, 0.018, n) * np.exp(-(t / 0.055) ** 1.4)
    th += lp(_noise(n, 'punch-puff', seed), 240.0, 2) * 2.0 * np.exp(-t / 0.012)
    th[:ns(0.001)] *= cos_ramp(ns(0.001))
    low = hp(th, 35.0, 2)
    harm = np.tanh(3.0 * low / (np.max(np.abs(low)) + 1e-9))  # phone-speaker harmonics of the thump
    low = (low + lp(hp(harm, 140.0, 2), 1400.0, 2) * 0.35) * low_polarity * (1.0 if thump else 0.0)
    if low_only:
        return low
    if 0 < low_delay < n:
        low = np.concatenate([np.zeros(low_delay), low[:-low_delay]])
    body = bp(_noise(n, 'punch-body', seed), 250.0, 1100.0, 2) * np.exp(-t / 0.010) * 1.4
    body += 0.45 * _glide_sine(300.0, 180.0, 0.008, n) * np.exp(-t / 0.018)
    snap = np.zeros((2, n))
    for c in range(2):
        snap[c] = bp(_noise(n, 'punch-snap', seed, c), 2200.0, 8000.0, 2) * np.exp(-t / 0.0028) * 1.5
    x = width(snap, 0.4) + np.vstack([low + body, low + body])
    x = _onset_ramp(fades(x, 0.0, 0.03), 3)
    return [(x, 0, {'room': 0.12, 'glue': 0.04})]


def sparkle_notes(pad_midis, root_midi, lo=98, gap=2):
    """Chord tones for the click_final sparkle: the chord's pitch classes (root left out when
    enough remain) moved into the 2.3-4.6 kHz octave [lo, lo+12), no two closer than `gap`
    semitones (a semitone cluster up there beats). Up to four notes."""
    pcs = sorted({m % 12 for m in pad_midis})
    if len(pcs) > 3 and root_midi % 12 in pcs:
        pcs.remove(root_midi % 12)
    cand = sorted(lo + (pc - lo) % 12 for pc in pcs)
    out = []
    for m in cand:
        if not out or m - out[-1] >= gap:
            out.append(m)
    return tuple(out[:4])


def click_final(seed, p=0.0, root_hz=103.83, notes=(99, 103, 106, 108)):
    """End-card CTA confirm: the premium version of a click, in three layers.
      1. a crisp press (the trackpad click's modes, slightly lower and fuller; no release click),
      2. a soft low 'thock' tuned to the chord root (90-140 Hz octave) with a little 2nd-harmonic
         body so it reads on phones,
      3. an airy tail, mostly breath: a soft 6-12 kHz swell, a glitter of tiny noise grains that
         thins out over ~0.5 s, and underneath a faint, short bloom of the chord's upper tones
         (2.3-4.6 kHz) struck together with a few ms of random stagger (no rising arpeggio,
         nothing 'level-up'), on the plate.
    The press and the thock start on the cue sample; the tail sits ~20 dB under the press (a few dB
    over the outro chord in its own 2-12 kHz bands for ~0.3 s)."""
    n = ns(0.85)
    t = taxis(n)
    r = rng('cf', seed)
    # 1. press
    m = _modes(n, [2650.0, 4300.0, 6600.0, 1050.0], [0.0028, 0.0018, 0.001, 0.005], [1.0, 0.7, 0.25, 0.5])
    z = hp(rng('cf-click', seed).standard_normal(n), 2000.0, 2) * np.exp(-t / 0.00035) * 0.75
    clk = lp(hp(m + z, 600.0, 2), 10000.0, 2)
    clk[:12] *= cos_ramp(12)
    # 2. thock
    th = _glide_sine(root_hz * 1.9, root_hz, 0.012, n) * np.exp(-t / 0.05)
    th += 0.35 * _glide_sine(root_hz * 3.0, root_hz * 2.0, 0.01, n) * np.exp(-t / 0.025)
    th += lp(_noise(n, 'cf-puff', seed), 500.0, 2) * 1.6 * np.exp(-t / 0.01)
    th[:ns(0.0015)] *= cos_ramp(ns(0.0015))
    th = hp(th, 60.0, 2)
    hit = pan(clk + 1.2 * th, p)
    hit = fades(hit, 0.0, 0.2)
    # 3. tail: mostly air. A soft breath swell, a glitter of tiny band-passed noise grains whose
    #    density thins out, and underneath a faint, short bloom of the chord's upper tones.
    tail = np.zeros((2, n))
    breath = _decor(n, lambda tt, f: band_mag(9000.0, 0.55)(f) * np.ones_like(tt), seed + 3, 0.35)
    tail += breath * ((1.0 - np.exp(-t / 0.025)) * np.exp(-t / 0.28) * 0.22)[None, :]
    g_times = np.sort(0.012 + r.exponential(0.16, 18))
    for g_t in g_times[g_times < 0.6]:
        a = ns(g_t)
        gl_n = ns(r.uniform(0.002, 0.005))
        gn = bp(r.standard_normal(gl_n + 64), 6500.0, 13000.0, 2)[64:] * np.hanning(gl_n)
        amp = 0.30 * r.uniform(0.45, 1.0) * np.exp(-g_t / 0.30)
        tail[:, a:a + gl_n] += pan(gn * amp, p + r.uniform(-0.7, 0.7))
    order = r.permutation(len(notes))
    pans = (-0.45, 0.45, -0.2, 0.25)
    for k, i in enumerate(order):
        f = float(midi_hz(notes[i])) * 2.0 ** (r.uniform(-4.0, 4.0) / 1200.0)
        d0 = ns(0.008 + 0.012 * k + r.uniform(0.0, 0.006))
        tt = taxis(n - d0)
        vib = 1.0 + 0.0025 * np.sin(TAU * 5.5 * tt + r.random() * TAU)
        tone = np.sin(TAU * np.cumsum(f * vib) / SR + r.random() * TAU)
        tone *= 0.75 + 0.25 * np.sin(TAU * (7.0 + 2.0 * k) * tt + r.random() * TAU)
        env = (1.0 - np.exp(-tt / 0.008)) * np.exp(-tt / (0.32 - 0.04 * k))
        tail[:, d0:] += pan(tone * env * (1.0, 0.8, 0.65, 0.55)[k % 4] * 0.11, p + pans[k % 4])
    tail = fades(tail, 0.0, 0.12)
    return [(hit, 0, {'room': 0.10}), (tail, 0, {'plate': 0.30})]


# --------------------------------------------------------------------------- dispatch
POST_PAN = ('impact_big', 'impact_drop', 'impact_outro', 'hit_cut', 'punch', 'zoom_through', 'riser',
            'reverse_swell', 'text_reveal')


def _best_low_alignment(low, kick, max_d, win):
    """(delay, polarity) for an impact's low layer that makes kick + low sum fullest below 160 Hz
    over the first `win` samples. Smallest move wins unless a later one is > 0.3 dB fuller."""
    k = np.zeros(win)
    k[:min(win, len(kick))] = kick[:win]
    K = lp(k, 160.0, 4)
    Lw = lp(low[:win], 160.0, 4)
    best = None
    for d in range(0, max_d + 1, ns(0.0005)):
        sh = np.concatenate([np.zeros(d), Lw[:win - d]])
        for pol in (1.0, -1.0):
            e = float(np.sum((K + pol * sh) ** 2))
            if best is None or e > best[0] * 10 ** 0.03:
                best = (e, d, pol)
    e0 = float(np.sum((K + Lw) ** 2))
    return best[1], best[2], 10 * np.log10(best[0] / e0)


def _offsets(trig, s, lo, hi):
    """Offsets (samples) of the trigger samples that lie within [s + lo, s + hi]."""
    return [k - s for k in trig if lo <= k - s <= hi]


def _kick_align(make_low, s, ctx, level_db, make_full, w20):
    """Kick-aware placement of a cue's low layer: if a grid kick lies within 20 ms of the
    frame-snapped cue, search the (delay, polarity) of the low layer that sums fullest with it.
    Returns (kwargs for the synth, note) or ({}, None)."""
    near = _offsets(ctx.get('kick_trig', []), s, -w20, w20)
    if not near or 'kick_track' not in ctx:
        return {}, None
    rms0, _ = ref_level(make_full())
    g0 = 10.0 ** (level_db / 20.0) / rms0
    win = ns(0.15)
    low = np.zeros(win)
    lo = make_low() * g0
    low[:min(win, len(lo))] = lo[:win]
    dly, pol, gain_db = _best_low_alignment(low, ctx['kick_track'][s:s + win], w20, win)
    kw = dict(low_delay=dly, low_polarity=pol) if (dly or pol < 0) else {}
    return kw, (f'kick {near[0] / SR * 1000:+.2f} ms: low layers moved {dly / SR * 1000:+.2f} ms'
                f"{', polarity flipped' if pol < 0 else ''} ({gain_db:+.1f} dB low end vs as-is)")


def render_cue(cue, idx, ctx):
    """Render one cue -> [(stereo signal, offset, sends)], level-set per LEVELS / PEAK_CAP.

    Cue fields: gain (dB), pan (-1..1; whooshes move through it, in the direction of `dir` or of
    the sign of pan), dur. ctx may carry the music's kick/clap trigger samples, the cue list and the
    harmony, so the sound design can sit with the score (see impact/hit_cut/click/success/toast)."""
    typ = cue['type']
    seed = 1000 + idx
    t = float(cue['t'])
    s = ns(t)
    p = float(cue.get('pan', 0.0))
    d = float(cue.get('dir', np.sign(p) if p else 1.0))
    gain = float(cue.get('gain', 0.0))
    cues = ctx.get('cues', [])
    kicks = ctx.get('kick_trig', [])
    claps = ctx.get('clap_trig', [])
    w20 = ns(0.02)
    kw = {}
    note = []
    if typ in ('impact_big', 'impact_drop', 'impact_outro'):
        kind = typ.split('_')[1]
        make = lambda **k: impact(kind, seed, **k)
        k_kw, k_note = _kick_align(lambda: impact(kind, seed, low_only=True), s, ctx, LEVELS[typ] + gain, make, w20)
        kw.update(k_kw)
        if k_note:
            note.append(k_note)
    elif typ == 'hit_cut':
        near_k = [o for o in _offsets(kicks, s, -w20, w20) if abs(o) >= ns(0.001)]
        if near_k:
            kw['knock'] = False
            note.append(f'no knock (kick {near_k[0] / SR * 1000:+.1f} ms)')
        near_c = _offsets(claps, s, -w20, w20)
        if near_c:
            kw['snap_amt'] = 1.0
            note.append(f'snap thinned (clap {near_c[0] / SR * 1000:+.1f} ms)')
        make = lambda **k: hit_cut(seed, **k)
    elif typ == 'whoosh_fast':
        make = lambda **k: whoosh_fast(seed, p, d)
    elif typ == 'whoosh_long':
        make = lambda **k: whoosh_long(seed, float(cue.get('dur', 0.4)), p, d)
    elif typ == 'whoosh_rise':
        make = lambda **k: whoosh_rise(seed, p, d)
    elif typ == 'zoom_through':
        make = lambda **k: zoom_through(seed, float(cue.get('dur', 0.17)))
    elif typ == 'riser':
        make = lambda **k: riser(seed, float(cue.get('dur', 0.96)), ctx['riser_target'](t))
    elif typ == 'reverse_swell':
        make = lambda **k: reverse_swell(seed, float(cue.get('dur', 0.6)), ctx['swell_chord'](t), ctx['ir_swell'])
    elif typ == 'click':
        if any(j != idx and c['type'] in ('click', 'tap_soft') and abs(c['t'] - t) < 0.25 for j, c in enumerate(cues)):
            kw['release'] = False
            note.append('press only (clicks < 0.25 s apart)')
        make = lambda **k: click(seed, p, **k)
    elif typ == 'tap_soft':
        make = lambda **k: tap_soft(seed, p)
    elif typ == 'tick':
        make = lambda **k: tick(seed, p)
    elif typ == 'ui_blip':
        make = lambda **k: ui_blip(seed, p)
    elif typ == 'success':
        chord = ctx['chord_at_time'](t + 0.06) if 'chord_at_time' in ctx else 'Fm9'
        notes = SUCCESS_DYADS.get(chord, (77, 80))
        crowded = any(c['type'] == 'toast' and 0.0 < c['t'] - t <= 0.12 for c in cues)
        if gain <= -6.0 or crowded:  # quiet accents and crowded moments: a single note
            notes = notes[:1]
        kw['notes'] = notes
        names = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
        note.append(('dyad ' if len(notes) > 1 else 'single ') + '+'.join(f'{names[m % 12]}{m // 12 - 1}' for m in notes)
                    + f' over {chord}' + (' (toast follows)' if crowded else ''))
        make = lambda **k: success(seed, p, **k)
    elif typ == 'toast':
        if any(c['type'] == 'success' and 0.0 <= t - c['t'] <= 0.12 for c in cues):
            kw['pop'] = False
            note.append('swish only (success just before): no transient by design')
        make = lambda **k: toast(seed, 0.25 if 'pan' not in cue else p, **k)
    elif typ == 'text_reveal':
        make = lambda **k: text_reveal(seed, p)
    elif typ == 'whip':
        make = lambda **k: whip(seed, float(cue.get('dur', 0.15)), p, d)
    elif typ == 'punch':
        make = lambda **k: punch(seed, **k)
        imp = [c for c in cues if c['type'] in ('impact_big', 'impact_drop', 'impact_outro') and abs(c['t'] - t) <= 0.03]
        if imp:
            kw['thump'] = False
            note.append(f"no thump ({imp[0]['type']} {1000 * (imp[0]['t'] - t):+.1f} ms owns the low end)")
        else:
            k_kw, k_note = _kick_align(lambda: punch(seed, low_only=True), s, ctx, LEVELS[typ] + gain, make, w20)
            kw.update(k_kw)
            if k_note:
                note.append(k_note)
    elif typ == 'click_final':
        root_m, pad_m = ctx['chord_tones'](t) if 'chord_tones' in ctx else (32, [51, 56, 67, 70, 72, 75])
        root_hz = float(midi_hz(root_m))
        while root_hz < 90.0:
            root_hz *= 2.0
        while root_hz >= 140.0:
            root_hz /= 2.0
        sp = sparkle_notes(pad_m, root_m)
        names = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
        note.append(f'thock {root_hz:.1f} Hz, tail ' + '+'.join(f'{names[m % 12]}{m // 12 - 1}' for m in sp))
        make = lambda **k: click_final(seed, p, root_hz, sp)
    else:
        raise ValueError(f'unknown cue type {typ}')
    layers = make(**kw)
    # variants (a layer dropped / thinned for the context) keep the level of the type's canonical
    # version, so removing a layer makes the cue lighter instead of being normalised back up
    rms, pk = ref_level(make() if kw else layers)
    g = 10.0 ** ((LEVELS[typ] + gain) / 20.0) / rms
    if typ in PEAK_CAP:
        g = min(g, 10.0 ** ((PEAK_CAP[typ] + gain) / 20.0) / pk)
    if typ in POST_PAN and p != 0.0:
        layers = [(pan(sig, p), off, sends) for sig, off, sends in layers]
    if typ in PEAK_CAP and g < 10.0 ** ((LEVELS[typ] + gain) / 20.0) / rms * 0.999:
        note.append(f'peak-capped ({PEAK_CAP[typ] + gain:+.1f} dB)')
    if 'notes' in ctx:
        ctx['notes'][idx] = '; '.join(note)
    if 'soft_onset' in ctx and kw.get('pop') is False:
        ctx['soft_onset'].add(idx)
    return [(sig * g, off, sends) for sig, off, sends in layers]


def ref_level(layers):
    """(loudest 10 ms RMS, sample peak) of the dry sum of a cue's layers."""
    lo = min(off for _, off, _ in layers)
    n = max(off - lo + sig.shape[1] for sig, off, _ in layers)
    buf = np.zeros((2, n))
    for sig, off, sends in layers:
        buf[:, off - lo:off - lo + sig.shape[1]] += sig * sends.get('_dry', 1.0)
    w = ns(0.01)
    ms = np.convolve(np.mean(buf ** 2, axis=0), np.ones(w) / w, mode='valid')
    return float(np.sqrt(ms.max())) + 1e-12, float(np.max(np.abs(buf))) + 1e-12
