"""Verification: blind onset detection vs cue times, loudness/peak/spectral checks,
and diagnostic PNGs (spectrograms, waveform + loudness with cue markers, onset zooms)."""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import signal
from scipy.ndimage import maximum_filter1d

from .dsp import SR, ns, zp
from .master import momentary

# --------------------------------------------------------------------------- onset detection


def onset_function(x, hp_f=120.0, after=0.0015, before=0.010):
    """Energy-ratio onset function (dB): energy in [n, n+after] vs [n-before, n].
    Zero-phase pre-filter, evaluated at every sample -> sample-accurate."""
    m = np.mean(np.atleast_2d(x), axis=0)
    m = zp(m, 'highpass', hp_f, 2)
    e = m * m
    c = np.concatenate([[0.0], np.cumsum(e)])
    n = len(m)
    A, Bf = ns(after), ns(before)
    idx = np.arange(n)
    ea = (c[np.minimum(idx + A, n)] - c[idx]) / A
    eb = (c[idx] - c[np.maximum(idx - Bf, 0)]) / Bf
    eps = 1e-10
    ratio = 10.0 * np.log10((ea + eps) / (eb + eps))
    level = 10.0 * np.log10(ea + 1e-20)
    return ratio, level


def detect_onsets(x, thresh_db=9.0, floor_db=-62.0, min_gap=0.02, hp_f=120.0):
    ratio, level = onset_function(x, hp_f=hp_f)
    w = ns(min_gap)
    mx = maximum_filter1d(ratio, size=2 * w + 1, mode='nearest')
    cand = np.where((ratio >= mx - 1e-9) & (ratio > thresh_db) & (level > floor_db))[0]
    # collapse plateaus
    out = []
    for c in cand:
        if not out or c - out[-1] > w:
            out.append(c)
    return np.array(out, dtype=int), ratio


def best_band_snr(s, m):
    """Max over 1/3-octave bands (200 Hz-12.5 kHz) of SFX-to-music energy ratio in the
    window: a rough audibility proxy (masking happens per critical band)."""
    a = np.mean(np.atleast_2d(s), axis=0)
    b = np.mean(np.atleast_2d(m), axis=0)
    n = max(len(a), 2048)
    w = np.hanning(len(a))
    A = np.abs(np.fft.rfft(a * w, n)) ** 2
    Bm = np.abs(np.fft.rfft(b * w, n)) ** 2
    f = np.fft.rfftfreq(n, 1 / SR)
    best, bf = -np.inf, 0.0
    for k in range(-10, 9):
        fc = 1000.0 * 2 ** (k / 3)
        sel = (f >= fc / 2 ** (1 / 6)) & (f < fc * 2 ** (1 / 6))
        if not np.any(sel):
            continue
        es, em = A[sel].sum(), Bm[sel].sum()
        if es < 1e-14 * len(a):
            continue
        r = 10 * np.log10((es + 1e-20) / (em + 1e-20))
        if r > best:
            best, bf = r, fc
    return best, bf


def match(onsets, t, window=0.04):
    if len(onsets) == 0:
        return None
    s = ns(t)
    k = int(np.argmin(np.abs(onsets - s)))
    d = (onsets[k] - s) / SR
    return d if abs(d) <= window else None


# --------------------------------------------------------------------------- PNG helpers
def _font(size):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


_CMAP = np.array([  # magma-like
    [0, 0, 4], [28, 16, 68], [79, 18, 123], [129, 37, 129], [181, 54, 122],
    [229, 80, 100], [251, 135, 97], [254, 194, 135], [252, 253, 191]], dtype=float)


def cmap(v):
    v = np.clip(v, 0, 1) * (len(_CMAP) - 1)
    i = np.minimum(np.floor(v).astype(int), len(_CMAP) - 2)
    f = (v - i)[..., None]
    return (_CMAP[i] * (1 - f) + _CMAP[i + 1] * f).astype(np.uint8)


SHORT = {
    'impact_big': 'IMPACT', 'impact_drop': 'IMPACT', 'impact_outro': 'IMPACT', 'hit_cut': 'hit',
    'whoosh_fast': 'wsh', 'whoosh_long': 'wshL', 'whoosh_rise': 'wshR', 'zoom_through': 'zoom',
    'riser': 'riser', 'reverse_swell': 'rev', 'click': 'click', 'tap_soft': 'tap', 'ui_blip': 'blip',
    'success': 'succ', 'toast': 'toast', 'tick': 'tick', 'text_reveal': 'txt',
    'whip': 'whip', 'punch': 'punch', 'click_final': 'CLICK',
}


def _cue_color(typ):
    if typ.startswith('impact'):
        return (255, 80, 80)
    if typ in ('hit_cut', 'punch'):
        return (255, 170, 60)
    if typ in ('click', 'click_final', 'tap_soft', 'tick', 'ui_blip', 'success', 'toast'):
        return (80, 220, 255)
    return (170, 170, 255)


def spectrogram_png(x, path, title, cues, sections, fmin=20.0, fmax=20000.0, nfft=4096, hop=240,
                    W=1800, H=760, rng_db=90.0):
    m = np.mean(np.atleast_2d(x), axis=0)
    f, t, Z = signal.stft(m, fs=SR, window='hann', nperseg=nfft, noverlap=nfft - hop, boundary='even')
    P = 20.0 * np.log10(np.abs(Z) + 1e-9)
    P -= P.max()
    ml, mr, mt, mb = 70, 20, 56, 40
    pw, ph = W - ml - mr, H - mt - mb
    # map pixels -> (time, freq)
    tx = np.linspace(0, len(m) / SR, pw)
    ti = np.clip(np.searchsorted(t, tx), 0, len(t) - 1)
    fy = np.exp(np.linspace(np.log(fmax), np.log(fmin), ph))
    fi = np.interp(fy, f, np.arange(len(f)))
    f0 = np.floor(fi).astype(int)
    ff = fi - f0
    f1 = np.minimum(f0 + 1, len(f) - 1)
    img = P[f0][:, ti] * (1 - ff)[:, None] + P[f1][:, ti] * ff[:, None]
    rgb = cmap((img + rng_db) / rng_db)
    im = Image.new('RGB', (W, H), (14, 14, 18))
    im.paste(Image.fromarray(rgb), (ml, mt))
    d = ImageDraw.Draw(im)
    fn, fs = _font(13), _font(11)
    d.text((ml, 12), title, fill=(235, 235, 240), font=_font(17))
    for fq in (20, 30, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000):
        if fmin <= fq <= fmax:
            y = mt + int((np.log(fmax) - np.log(fq)) / (np.log(fmax) - np.log(fmin)) * (ph - 1))
            d.line([(ml - 6, y), (ml + pw, y)], fill=(255, 255, 255, 40), width=1)
            d.text((6, y - 7), f'{fq/1000:g}k' if fq >= 1000 else f'{fq}', fill=(200, 200, 210), font=fs)
    dur = len(m) / SR
    for s in range(0, int(dur) + 1):
        xx = ml + int(s / dur * (pw - 1))
        d.line([(xx, mt + ph), (xx, mt + ph + 6)], fill=(200, 200, 210))
        d.text((xx - 4, mt + ph + 9), f'{s}', fill=(200, 200, 210), font=fs)
    for name, sec in sections.items():
        xx = ml + int(sec['start'] / dur * (pw - 1))
        d.line([(xx, mt - 18), (xx, mt + ph)], fill=(255, 255, 255), width=1)
        d.text((xx + 3, mt - 18), name, fill=(255, 255, 255), font=fn)
    for c in cues:
        xx = ml + int(c['t'] / dur * (pw - 1))
        d.line([(xx, mt), (xx, mt + 10)], fill=_cue_color(c['type']), width=2)
    im.save(path)


def waveform_png(path, mix, music, sfx, cues, sections, W=1800, H=980):
    dur = mix.shape[1] / SR
    ml, mr = 70, 20
    pw = W - ml - mr
    im = Image.new('RGB', (W, H), (250, 250, 252))
    d = ImageDraw.Draw(im)
    fn, fs = _font(13), _font(11)
    d.text((ml, 10), 'Waveforms (peak / RMS per column) + momentary loudness; cue markers by category', fill=(20, 20, 30), font=_font(16))
    rows = [('MIX (master)', mix, (40, 40, 60)), ('MUSIC stem', music, (60, 80, 170)), ('SFX stem', sfx, (170, 70, 60))]
    top = 40
    rh = 210
    for name, x, col in rows:
        m = np.atleast_2d(x)
        n = m.shape[1]
        edges = np.linspace(0, n, pw + 1).astype(int)
        mx = np.array([np.max(m[:, a:b]) if b > a else 0 for a, b in zip(edges[:-1], edges[1:])])
        mn = np.array([np.min(m[:, a:b]) if b > a else 0 for a, b in zip(edges[:-1], edges[1:])])
        rms = np.array([np.sqrt(np.mean(m[:, a:b] ** 2)) if b > a else 0 for a, b in zip(edges[:-1], edges[1:])])
        cy = top + rh // 2
        sc = rh / 2 - 6
        d.rectangle([ml, top, ml + pw, top + rh], outline=(220, 220, 228))
        for db_ in (-1.0, -6.0):
            a = 10 ** (db_ / 20)
            for sgn in (1, -1):
                y = cy - sgn * a * sc
                d.line([(ml, y), (ml + pw, y)], fill=(235, 220, 220) if db_ == -1 else (232, 232, 238))
        light = tuple(int(c + (255 - c) * 0.55) for c in col)
        for i in range(pw):
            d.line([(ml + i, cy - mx[i] * sc), (ml + i, cy - mn[i] * sc)], fill=light)
            d.line([(ml + i, cy - rms[i] * sc), (ml + i, cy + rms[i] * sc)], fill=col)
        d.text((ml + 6, top + 4), name, fill=(20, 20, 30), font=fn)
        top += rh + 12
    # loudness row
    lh = 190
    d.rectangle([ml, top, ml + pw, top + lh], outline=(220, 220, 228))
    for lv in (-10, -14, -20, -30):
        y = top + int((-6 - lv) / 30 * lh)
        d.line([(ml, y), (ml + pw, y)], fill=(225, 225, 232) if lv != -14 else (240, 180, 180))
        d.text((8, y - 7), f'{lv} LUFS', fill=(90, 90, 100), font=fs)
    for x, col in ((mix, (30, 30, 40)), (music, (60, 80, 170)), (sfx, (170, 70, 60))):
        tt, ll = momentary(x)
        pts = [(ml + int(a / dur * (pw - 1)), top + int(np.clip((-6 - b) / 30, 0, 1) * lh)) for a, b in zip(tt, ll)]
        d.line(pts, fill=col, width=2)
    d.text((ml + 6, top + 4), 'Momentary loudness (400 ms): mix black, music blue, sfx red', fill=(20, 20, 30), font=fn)
    bottom = top + lh
    for s in range(0, int(dur) + 1):
        xx = ml + int(s / dur * (pw - 1))
        d.text((xx - 4, bottom + 6), f'{s}s', fill=(60, 60, 70), font=fs)
    for name, sec in sections.items():
        xx = ml + int(sec['start'] / dur * (pw - 1))
        d.line([(xx, 34), (xx, bottom)], fill=(150, 150, 160), width=1)
        d.text((xx + 3, 24), name, fill=(80, 80, 90), font=fs)
    for c in cues:
        xx = ml + int(c['t'] / dur * (pw - 1))
        d.line([(xx, 40), (xx, bottom)], fill=_cue_color(c['type']) if c['type'] not in ('whoosh_fast', 'whoosh_long', 'whoosh_rise', 'whip', 'riser', 'reverse_swell', 'text_reveal') else (190, 190, 235), width=1)
    im.save(path)


def onset_zoom_png(path, sfx, mix, rows, W=1800):
    """rows: list of (cue, dev_sfx, dev_mix). One panel per transient cue: +-25 ms waveforms."""
    cols = 6
    pw, ph = (W - 20) // cols, 150
    nrows = (len(rows) + cols - 1) // cols
    H = 50 + nrows * (ph + 10)
    im = Image.new('RGB', (W, H), (250, 250, 252))
    d = ImageDraw.Draw(im)
    fs = _font(10)
    d.text((10, 12), 'Transient cues, +-25 ms: SFX stem (red) and final mix (grey); cue time = black line, detected onset = blue (sfx) / green (mix)', fill=(20, 20, 30), font=_font(15))
    span = ns(0.025)
    for k, (cue, dev_s, dev_m) in enumerate(rows):
        r, c = divmod(k, cols)
        x0, y0 = 10 + c * pw, 44 + r * (ph + 10)
        d.rectangle([x0, y0, x0 + pw - 8, y0 + ph], outline=(215, 215, 222), fill=(255, 255, 255))
        s = ns(cue['t'])
        a, b = max(s - span, 0), min(s + span, sfx.shape[1])
        for sig, col in ((mix, (170, 170, 175)), (sfx, (200, 60, 50))):
            seg = np.mean(sig[:, a:b], axis=0)
            pk = max(np.max(np.abs(seg)), 1e-6)
            xs = x0 + 4 + (np.arange(len(seg)) + (a - (s - span))) / (2 * span) * (pw - 16)
            ys = y0 + ph / 2 - seg / pk * (ph / 2 - 22)
            d.line(list(zip(xs.tolist(), ys.tolist())), fill=col, width=1)
        cx = x0 + 4 + (pw - 16) / 2
        d.line([(cx, y0 + 18), (cx, y0 + ph - 2)], fill=(0, 0, 0), width=1)
        if dev_s is not None:
            xx = cx + dev_s / 0.05 * (pw - 16)
            d.line([(xx, y0 + 18), (xx, y0 + ph - 2)], fill=(40, 90, 230), width=1)
        if dev_m is not None:
            xx = cx + dev_m / 0.05 * (pw - 16)
            d.line([(xx, y0 + 30), (xx, y0 + ph - 14)], fill=(40, 170, 80), width=1)
        ds = f'{dev_s*1000:+.2f}' if dev_s is not None else 'n/a'
        dm = f'{dev_m*1000:+.2f}' if dev_m is not None else 'n/a'
        d.text((x0 + 5, y0 + 3), f"{cue['t']:.3f}s {cue['type']}  sfx {ds} / mix {dm} ms", fill=(20, 20, 30), font=fs)
    im.save(path)
