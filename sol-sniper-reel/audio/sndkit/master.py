"""Mastering: BS.1770-4 loudness, true peak, glue compression, soft clip, look-ahead
true-peak limiter, codec (AAC) overshoot guard, short end fade to digital silence."""
import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d

from .dsp import SR, cos_ramp, hp, ns

# ITU-R BS.1770-4 K-weighting, 48 kHz coefficients
_K1 = (np.array([1.53512485958697, -2.69169618940638, 1.19839281085285]),
       np.array([1.0, -1.69065929318241, 0.73248077421585]))
_K2 = (np.array([1.0, -2.0, 1.0]),
       np.array([1.0, -1.99004745483398, 0.99007225036621]))


def kweight(x):
    y = signal.lfilter(_K1[0], _K1[1], x, axis=-1)
    return signal.lfilter(_K2[0], _K2[1], y, axis=-1)


def _block_loudness(x, block, step):
    y = kweight(np.atleast_2d(x))
    p = y ** 2
    c = np.concatenate([np.zeros((p.shape[0], 1)), np.cumsum(p, axis=1)], axis=1)
    starts = np.arange(0, p.shape[1] - block + 1, step)
    z = (c[:, starts + block] - c[:, starts]) / block  # mean square per channel
    return starts, -0.691 + 10.0 * np.log10(np.maximum(z.sum(axis=0), 1e-20))


def integrated_lufs(x):
    _, l = _block_loudness(x, ns(0.4), ns(0.1))
    l = l[l > -70.0]
    if len(l) == 0:
        return -np.inf
    rel = 10.0 * np.log10(np.mean(10.0 ** (l / 10.0))) - 10.0
    l = l[l > rel]
    return 10.0 * np.log10(np.mean(10.0 ** (l / 10.0)))


def momentary(x):
    s, l = _block_loudness(x, ns(0.4), ns(0.05))
    return (s + ns(0.4)) / SR, l  # time stamp = end of window


def short_term(x):
    s, l = _block_loudness(x, ns(3.0), ns(0.1))
    return (s + ns(3.0)) / SR, l


def loudness_range(x):
    _, l = _block_loudness(x, ns(3.0), ns(0.1))
    l = l[l > -70.0]
    if len(l) == 0:
        return 0.0
    rel = 10.0 * np.log10(np.mean(10.0 ** (l / 10.0))) - 20.0
    l = np.sort(l[l > rel])
    return float(np.percentile(l, 95) - np.percentile(l, 10))


def segment_lufs(x, t0, t1):
    """Ungated loudness of a segment (mean-square over the segment, K-weighted)."""
    a, b = ns(t0), ns(t1)
    y = kweight(np.atleast_2d(x))[:, a:b]
    return -0.691 + 10.0 * np.log10(max(np.mean(y ** 2, axis=1).sum(), 1e-20))


def true_peak(x, os=4):
    up = signal.resample_poly(np.atleast_2d(x), os, 1, axis=1)
    return float(20.0 * np.log10(max(np.max(np.abs(up)), 1e-12)))


def _tp_envelope(x, os=4):
    up = signal.resample_poly(x, os, 1, axis=1)
    a = np.max(np.abs(up), axis=0)
    a = a[:x.shape[1] * os].reshape(x.shape[1], os).max(axis=1)
    return np.maximum(a, np.max(np.abs(x), axis=0))


# --------------------------------------------------------------------------- dynamics
def glue_comp(x, thr_db, ratio=2.0, attack=0.025, release=0.2, knee=6.0, sc_hp=110.0, block=48):
    """Stereo-linked RMS bus compressor (sidechain high-passed so the sub doesn't pump it)."""
    det = hp(0.5 * (x[0] + x[1]), sc_hp, 2)
    nb = len(det) // block
    ms = np.mean(det[:nb * block].reshape(nb, block) ** 2, axis=1)
    lvl = 10.0 * np.log10(np.maximum(ms, 1e-12)) + 3.0  # RMS of sine ~ peak-3 dB convention
    a_c = np.exp(-block / (attack * SR))
    r_c = np.exp(-block / (release * SR))
    sm = np.empty(nb)
    s = lvl[0]
    for i in range(nb):
        v = lvl[i]
        c = a_c if v > s else r_c
        s = c * s + (1 - c) * v
        sm[i] = s
    over = sm - thr_db
    gr = np.where(over <= -knee / 2, 0.0,
                  np.where(over >= knee / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee / 2) ** 2 / (2 * knee)))
    centers = (np.arange(nb) + 0.5) * block
    g_db = -np.interp(np.arange(x.shape[1]), centers, gr)
    return x * (10.0 ** (g_db / 20.0))[None, :], gr


def soft_clip(x, thr=0.8, os=4):
    """Oversampled smooth saturation above `thr` (linear below)."""
    up = signal.resample_poly(x, os, 1, axis=1)
    a = np.abs(up)
    k = 1.0 - thr
    y = np.where(a > thr, np.sign(up) * (thr + k * np.tanh((a - thr) / k)), up)
    return signal.resample_poly(y, 1, os, axis=1)[:, :x.shape[1]]


def limiter(x, ceiling_db=-1.3, lookahead=0.0015, release=0.08, start_extra_db=0.25, start_len=0.03,
            extra_db=None):
    """Look-ahead true-peak limiter (offline, zero added latency).

    The first `start_len` seconds get `start_extra_db` more headroom: the opening impact starts
    from digital silence, where an AAC encoder's first frame tends to overshoot. `extra_db`
    (optional, per sample, >= 0) lowers the ceiling locally on top of that."""
    n = x.shape[1]
    k = ns(start_len)
    ex = np.zeros(n)
    ex[:k] = start_extra_db
    ex[k:2 * k] = start_extra_db * (1.0 - cos_ramp(k))[:max(0, min(k, n - k))]
    if extra_db is not None:
        ex = ex + np.asarray(extra_db, dtype=float)
    c = 10.0 ** ((ceiling_db - ex) / 20.0)
    pk = _tp_envelope(x)
    req = np.minimum(1.0, c / np.maximum(pk, 1e-12))
    L = max(ns(lookahead), 1)
    g = minimum_filter1d(req, size=2 * L + 1, mode='nearest')
    g = uniform_filter1d(g, size=L + 1, mode='nearest')
    g = np.minimum(g, req)
    # program-dependent release (smooth recovery)
    rc = np.exp(-1.0 / (release * SR))
    out = np.empty_like(g)
    s = 1.0
    for i in range(len(g)):
        v = g[i]
        s = v if v < s else v - (v - s) * rc
        out[i] = s
    return x * out[None, :], out


def end_fade(n, fade_out):
    """Gain curve: 1 until the last `fade_out` seconds, then a raised-cosine fade that reaches
    exactly 0 on the last sample (digital silence AT the end, no click)."""
    g = np.ones(n)
    nf = ns(fade_out)
    if nf > 1:
        g[n - nf:] = 0.5 + 0.5 * np.cos(np.pi * np.arange(nf) / (nf - 1))
    g[-1] = 0.0
    return g


def master(mix, target_lufs=-14.0, ceiling_db=-1.3, fade_out=0.15, log=print, guard_db=None, g_db=4.0):
    """hp -> -18 LUFS -> glue comp -> [gain -> soft clip -> true-peak limiter -> codec guard -> end
    fade], with the gain iterated until the integrated loudness hits `target_lufs`.

    guard_db (optional, per sample, dB >= 0): a smooth gain dip applied after the limiter where
    the AAC delivery encode would overshoot (see build_audio.aac_guard). It sits after the limiter
    so it scales the whole AAC frame (codec overshoot scales with it) instead of only the peaks.
    g_db: starting make-up gain (pass the previous result to converge in one or two passes)."""
    x = hp(mix, 18.0, 2)  # DC / subsonic guard
    x *= 10.0 ** ((-18.0 - integrated_lufs(x)) / 20.0)
    x, gr = glue_comp(x, thr_db=-13.5, ratio=2.0, attack=0.02, release=0.18, knee=6.0)
    log(f'  glue comp: max GR {gr.max():.2f} dB, mean GR (where active) {gr[gr > 0.05].mean() if np.any(gr > 0.05) else 0:.2f} dB')
    n = x.shape[1]
    fade = end_fade(n, fade_out)
    post = fade if guard_db is None else fade * 10.0 ** (-np.asarray(guard_db, dtype=float) / 20.0)
    y = None
    for it in range(8):
        y = x * 10.0 ** (g_db / 20.0)
        y = soft_clip(y, thr=10.0 ** ((ceiling_db - 1.5) / 20.0))
        y, lg = limiter(y, ceiling_db)
        y = y * post[None, :]
        lufs = integrated_lufs(y)
        err = target_lufs - lufs
        log(f'  iter {it}: gain {g_db:+.2f} dB -> {lufs:.2f} LUFS, TP {true_peak(y):.2f} dBTP, max limiter GR {-20*np.log10(lg.min()):.2f} dB')
        if abs(err) < 0.03:
            break
        g_db += err
    glue_t = (np.arange(len(gr)) + 0.5) * 48 / SR  # glue_comp works on 48-sample blocks
    return y, dict(gain_db=g_db, limiter_gr_db=float(-20 * np.log10(lg.min())), glue_gr_db=float(gr.max()),
                   limiter_gain=lg, glue_gr=gr, glue_t=glue_t, fade=fade)
