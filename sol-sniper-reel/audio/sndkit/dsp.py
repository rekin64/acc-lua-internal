"""DSP primitives: oscillators, envelopes, filters, shaped noise, reverb, delay.

Conventions
- Sample rate SR = 48 kHz. Mono signals are 1-D float64 arrays, stereo
  signals are (2, n) arrays.
- Every random source takes an explicit seed (see `rng`).
"""
import zlib

import numpy as np
from scipy import signal

SR = 48000
TAU = 2.0 * np.pi


# --------------------------------------------------------------------------- basics
def ns(t):
    """Seconds -> whole samples."""
    return int(round(float(t) * SR))


def taxis(n):
    return np.arange(n) / SR


def midi_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


def db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-12))


def undb(d):
    return 10.0 ** (np.asarray(d, dtype=float) / 20.0)


def seed_of(*parts):
    return zlib.crc32('|'.join(str(p) for p in parts).encode('utf-8'))


def rng(*parts):
    return np.random.default_rng(seed_of(*parts))


def stereo(x):
    x = np.asarray(x, dtype=float)
    return np.vstack([x, x]) if x.ndim == 1 else x


def add_at(buf, sig, start):
    """Mix `sig` (mono or stereo) into stereo `buf` starting at sample `start` (may be negative)."""
    sig = stereo(sig)
    n = sig.shape[1]
    a, b = start, start + n
    sa, sb = 0, n
    if a < 0:
        sa, a = -a, 0
    if b > buf.shape[1]:
        sb -= b - buf.shape[1]
        b = buf.shape[1]
    if b > a and sb > sa:
        buf[:, a:b] += sig[:, sa:sb]


def pan_gains(p):
    """Constant-power pan law normalised so centre = unity on both sides."""
    a = (np.clip(p, -1.0, 1.0) + 1.0) * np.pi / 4.0
    return np.sqrt(2.0) * np.cos(a), np.sqrt(2.0) * np.sin(a)


def pan(x, p=0.0):
    x = np.asarray(x, dtype=float)
    gl, gr = pan_gains(p)
    if x.ndim == 1:
        return np.vstack([x * gl, x * gr])
    return np.vstack([x[0] * gl, x[1] * gr])


def width(st, w):
    m = 0.5 * (st[0] + st[1])
    s = 0.5 * (st[0] - st[1]) * w
    return np.vstack([m + s, m - s])


def sat(x, drive=1.0):
    """tanh saturation with unity small-signal gain."""
    return np.tanh(drive * x) / drive


def soft_norm_sat(x, drive=1.5):
    """tanh saturation normalised so that +-1 maps to +-1."""
    return np.tanh(drive * x) / np.tanh(drive)


# --------------------------------------------------------------------------- envelopes
def cos_ramp(n):
    """0 -> 1 raised-cosine ramp of n samples."""
    if n <= 0:
        return np.ones(0)
    return 0.5 - 0.5 * np.cos(np.pi * (np.arange(n) + 0.5) / n)


def fades(x, fin=0.0, fout=0.0):
    """Raised-cosine fade in/out (seconds) on mono or stereo arrays (in place copy)."""
    x = np.array(x, dtype=float, copy=True)
    n = x.shape[-1]
    a, b = min(ns(fin), n), min(ns(fout), n)
    if a > 0:
        x[..., :a] *= cos_ramp(a)
    if b > 0:
        x[..., n - b:] *= cos_ramp(b)[::-1]
    return x


def env_exp(n, tau, attack=0.0, hold=0.0):
    """Instant/linear-cos attack, optional hold, exponential decay."""
    t = taxis(n)
    e = np.exp(-np.maximum(t - attack - hold, 0.0) / tau)
    na = ns(attack)
    if na > 0:
        e[:na] *= cos_ramp(na)
    return e


def env_adsr(n, a, d, s, r_start, r):
    """ADSR with raised-cosine attack and release; r_start = note-off time (s)."""
    t = taxis(n)
    e = np.where(t < a, 0.5 - 0.5 * np.cos(np.pi * np.clip(t / max(a, 1e-6), 0, 1)),
                 s + (1 - s) * np.exp(-np.maximum(t - a, 0) / max(d, 1e-6)))
    rel = np.clip((t - r_start) / max(r, 1e-6), 0, 1)
    return e * (0.5 + 0.5 * np.cos(np.pi * rel))


def bump(x, peak=0.5, k=3.0):
    """Gamma-like bell on x in [0,1], max 1 at `peak`, 0 at x=0. Falls to ~0 by x=1 for k>=3."""
    x = np.clip(np.asarray(x, dtype=float), 0.0, None)
    u = x / max(peak, 1e-6)
    return np.power(u, k) * np.exp(k * (1.0 - u))


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def logpath(x, pts, vals):
    """Piecewise-linear interpolation in log domain (for frequency paths)."""
    return np.exp(np.interp(x, pts, np.log(vals)))


# --------------------------------------------------------------------------- oscillators
def phase(freq, n, phase0=0.0):
    """Phase in cycles for a (possibly time-varying) frequency, starting at phase0."""
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    inc = f / SR
    ph = np.empty(n)
    ph[0] = phase0
    if n > 1:
        ph[1:] = phase0 + np.cumsum(inc[:-1])
    return ph


def sine(freq, n, phase0=0.0):
    return np.sin(TAU * phase(freq, n, phase0))


def _polyblep(t, dt):
    out = np.zeros_like(t)
    m = t < dt
    x = t[m] / dt[m]
    out[m] = x + x - x * x - 1.0
    m2 = t > 1.0 - dt
    x = (t[m2] - 1.0) / dt[m2]
    out[m2] = x * x + x + x + 1.0
    return out


def saw(freq, n, phase0=0.0):
    """Band-limited (PolyBLEP) sawtooth, -1..1."""
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    dt = np.clip(f / SR, 1e-9, 0.5)
    t = np.mod(phase(f, n, phase0), 1.0)
    return 2.0 * t - 1.0 - _polyblep(t, dt)


def supersaw(freq, n, voices=7, detune_cents=12.0, seed=0, spread=0.85, center_gain=1.0):
    """Stereo detuned saw stack. freq scalar or array. Returns (2, n)."""
    r = np.random.default_rng(seed)
    offs = np.linspace(-1.0, 1.0, voices)
    offs = np.sign(offs) * np.abs(offs) ** 1.25 * detune_cents
    phases = r.random(voices)
    order = np.argsort(r.random(voices))
    pans = np.linspace(-spread, spread, voices)[order]
    out = np.zeros((2, n))
    f = np.asarray(freq, dtype=float)
    for i in range(voices):
        g = center_gain if offs[i] == 0 else 1.0
        v = saw(f * 2.0 ** (offs[i] / 1200.0), n, phases[i]) * g
        gl, gr = pan_gains(pans[i])
        out[0] += v * gl
        out[1] += v * gr
    return out / np.sqrt(voices)


# --------------------------------------------------------------------------- filters
def sos(kind, f, order=2):
    return signal.butter(order, f, btype=kind, fs=SR, output='sos')


def filt(x, kind, f, order=2):
    """Static Butterworth filter on the last axis. kind: lowpass/highpass/bandpass."""
    if kind == 'lowpass' and f >= SR * 0.49:
        return np.array(x, dtype=float, copy=True)
    return signal.sosfilt(sos(kind, f, order), x, axis=-1)


def lp(x, f, order=2):
    return filt(x, 'lowpass', f, order)


def hp(x, f, order=2):
    return filt(x, 'highpass', f, order)


def bp(x, lo, hi, order=2):
    return filt(x, 'bandpass', [lo, hi], order)


def zp(x, kind, f, order=2):
    """Zero-phase (forward-backward) static filter; used only on IRs / diagnostics."""
    return signal.sosfiltfilt(sos(kind, f, order), x, axis=-1)


def rbj(kind, f0, q, gain_db=0.0):
    """RBJ cookbook biquad coefficients; f0/q may be arrays. Returns b (3,...), a (3,...) normalised."""
    f0 = np.clip(np.asarray(f0, dtype=float), 5.0, SR * 0.45)
    q = np.asarray(q, dtype=float)
    w0 = TAU * f0 / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2.0 * q)
    A = 10.0 ** (gain_db / 40.0)
    if kind == 'lowpass':
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == 'highpass':
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == 'bandpass':  # constant 0 dB peak
        b = [alpha, 0 * cw, -alpha]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == 'peak':
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind in ('lowshelf', 'highshelf'):
        sq = 2 * np.sqrt(A) * alpha
        if kind == 'lowshelf':
            b = [A * ((A + 1) - (A - 1) * cw + sq), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sq)]
            a = [(A + 1) + (A - 1) * cw + sq, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sq]
        else:
            b = [A * ((A + 1) + (A - 1) * cw + sq), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sq)]
            a = [(A + 1) - (A - 1) * cw + sq, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sq]
    else:
        raise ValueError(kind)
    b = np.array(np.broadcast_arrays(*b), dtype=float)
    a = np.array(np.broadcast_arrays(*a), dtype=float)
    return b / a[0], a / a[0]


def eq(x, kind, f0, q=0.707, gain_db=0.0):
    b, a = rbj(kind, f0, q, gain_db)
    return signal.lfilter(b, a, x, axis=-1)


def tv_biquad(x, kind, fc, q=0.707, block=32, stages=1):
    """Time-varying RBJ biquad (cascaded `stages` times), coefficients updated every `block` samples.

    fc / q: scalar or per-sample arrays. Works on mono or stereo input.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim == 2:
        return np.vstack([tv_biquad(c, kind, fc, q, block, stages) for c in x])
    n = len(x)
    fc = np.broadcast_to(np.asarray(fc, dtype=float), (n,))
    q = np.broadcast_to(np.asarray(q, dtype=float), (n,))
    centers = np.minimum(np.arange(0, n, block) + block // 2, n - 1)
    b, a = rbj(kind, fc[centers], q[centers])
    y = x.copy()
    for _ in range(stages):
        zi = np.zeros(2)
        out = np.empty(n)
        for k, s in enumerate(range(0, n, block)):
            e = min(s + block, n)
            out[s:e], zi = signal.lfilter(b[:, k], a[:, k], y[s:e], zi=zi)
        y = out
    return y


# --------------------------------------------------------------------------- shaped noise
def shaped_noise(n, mag_fn, seed, nfft=1024, hop=256, t0=0.0):
    """Gaussian noise whose short-time magnitude spectrum follows mag_fn(t, f).

    mag_fn receives t (frames,1) seconds and f (1,bins) Hz and returns linear
    magnitudes (broadcastable to (frames, bins)). A magnitude of 1 everywhere
    gives unit-variance white noise. Smooth time-varying filtering without
    zipper noise; used for whooshes, risers, air and reverb tails.
    """
    r = np.random.default_rng(seed)
    pad = nfft // hop
    nfr = int(np.ceil(n / hop)) + 2 * pad + 1
    tf = (np.arange(nfr) - pad) * hop / SR + t0
    freqs = np.fft.rfftfreq(nfft, 1.0 / SR)
    mag = np.broadcast_to(np.asarray(mag_fn(tf[:, None], freqs[None, :]), dtype=float), (nfr, len(freqs)))
    spec = (r.standard_normal(mag.shape) + 1j * r.standard_normal(mag.shape)) * (mag / np.sqrt(2.0))
    spec[:, 0] = 0.0
    frames = np.fft.irfft(spec, n=nfft, axis=1) * np.sqrt(nfft)
    win = signal.windows.hann(nfft, sym=False)
    frames *= win[None, :] / np.sqrt(np.sum(win ** 2) / hop)
    total = (nfr - 1) * hop + nfft
    out = np.zeros(total)
    idx = (np.arange(nfr) * hop)[:, None] + np.arange(nfft)[None, :]
    np.add.at(out, idx.ravel(), frames.ravel())
    off = pad * hop + nfft // 2
    return out[off:off + n]


def band_mag(fc, sigma_oct, floor=0.0):
    """Gaussian band in log-frequency, returned as a mag_fn factory component."""
    def fn(f):
        z = np.log2(np.maximum(f, 1.0) / fc) / sigma_oct
        return np.exp(-0.5 * z * z) + floor
    return fn


# --------------------------------------------------------------------------- reverb / delay
def make_ir(dur, rt_lo, rt_hi, seed, predelay=0.012, hp_f=180.0, lp_f=11000.0,
            er_n=12, er_span=0.07, er_gain=0.5, buildup=0.012, f_lo=250.0, f_hi=8000.0):
    """Stereo reverb impulse response: early reflections + frequency-dependent
    exponentially decaying diffuse tail (decorrelated L/R). Unit energy per channel."""
    n = ns(dur)

    def rt_of(f):
        x = np.clip(np.log(np.maximum(f, 1.0) / f_lo) / np.log(f_hi / f_lo), 0.0, 1.0)
        return rt_lo + (rt_hi - rt_lo) * x

    def mag(t, f):
        return np.exp(-6.9078 * np.maximum(t, 0.0) / rt_of(f))

    out = np.zeros((2, n))
    t = taxis(n)
    r = np.random.default_rng(seed)
    pd = ns(predelay)
    for c in range(2):
        tail = shaped_noise(n, mag, seed + 17 * (c + 1))
        tail *= 1.0 - np.exp(-t / buildup)
        out[c, pd:] += tail[:n - pd]
        # early reflections
        times = np.sort(r.uniform(0.002, er_span, er_n)) + predelay * 0.6
        for k, tt in enumerate(times):
            i = ns(tt)
            if i < n:
                g = er_gain * np.exp(-tt / (er_span * 0.9)) * (1.0 if r.random() > 0.35 else -1.0)
                out[c, i] += g * 3.0
    out = hp(out, hp_f, 2)
    out = lp(out, lp_f, 2)
    out /= np.sqrt(np.sum(out ** 2, axis=1, keepdims=True))
    return out


def convolve_ir(x, ir):
    """Mono or stereo input through a stereo IR -> stereo output (same length as x)."""
    x = np.asarray(x, dtype=float)
    n = x.shape[-1]
    if x.ndim == 1:
        return np.vstack([signal.fftconvolve(x, ir[c])[:n] for c in range(2)])
    # stereo in: L->L, R->R (true-stereo-lite) plus a little crossfeed for diffusion
    yl = signal.fftconvolve(x[0], ir[0])[:n]
    yr = signal.fftconvolve(x[1], ir[1])[:n]
    xl = signal.fftconvolve(x[1], ir[0])[:n]
    xr = signal.fftconvolve(x[0], ir[1])[:n]
    return np.vstack([0.8 * yl + 0.35 * xl, 0.8 * yr + 0.35 * xr])


def shift(x, d):
    y = np.zeros_like(x)
    if d < x.shape[-1]:
        y[..., d:] = x[..., :x.shape[-1] - d]
    return y


def pingpong(x, delay, fb=0.45, reps=6, lp_f=4500.0, hp_f=350.0, first='L', cross=0.15):
    """Mono in -> stereo ping-pong echoes (wet only). Each repeat gets darker."""
    x = hp(np.asarray(x, dtype=float), hp_f, 2)
    out = np.zeros((2, len(x)))
    d = ns(delay)
    cur = x
    side = 0 if first == 'L' else 1
    for k in range(1, reps + 1):
        cur = lp(cur, max(lp_f * (0.86 ** (k - 1)), 900.0), 1)
        tap = shift(cur, d * k) * (fb ** k)
        out[side] += tap * (1.0 - cross)
        out[1 - side] += tap * cross
        side = 1 - side
    return out


def duck_env(n, trig, depth, release=0.12, attack=0.003, curve=2.2):
    """Sidechain gain curve: ducks by `depth` (0..1, scalar or one value per trigger) at each
    trigger sample (reaching full depth AT the trigger, look-ahead style) and recovers over `release`."""
    g = np.ones(n)
    na, nr = max(ns(attack), 1), ns(release)
    depths = np.broadcast_to(np.asarray(depth, dtype=float), (len(trig),))
    ramp_dn = cos_ramp(na)
    ramp_up = (1.0 - np.linspace(0.0, 1.0, nr)) ** curve
    for s, dp in zip(trig, depths):
        shape = np.concatenate([1.0 - dp * ramp_dn, 1.0 - dp * ramp_up])
        a = s - na
        b = a + len(shape)
        sa = 0
        if a < 0:
            sa, a = -a, 0
        b = min(b, n)
        if b > a:
            g[a:b] = np.minimum(g[a:b], shape[sa:sa + (b - a)])
    return g


def event_duck(n, events):
    """Gain curve from (start_sample, depth_db, hold_s, attack_s, release_s) events.
    Reaches full depth AT start (look-ahead attack), holds, then recovers smoothly."""
    g_db = np.zeros(n)
    for s, depth, hold, att, rel in events:
        na, nh, nr = max(ns(att), 1), ns(hold), max(ns(rel), 1)
        shape = np.concatenate([cos_ramp(na), np.ones(nh), cos_ramp(nr)[::-1]]) * (-abs(depth))
        a = s - na
        sa = 0
        if a < 0:
            sa, a = -a, 0
        b = min(a + len(shape) - sa, n)
        if b > a:
            g_db[a:b] = np.minimum(g_db[a:b], shape[sa:sa + (b - a)])
    return 10.0 ** (g_db / 20.0)
