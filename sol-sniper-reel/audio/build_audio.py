#!/usr/bin/env python3
"""SOL Sniper reel: fully synthesized, deterministic soundtrack + sound design.

  node scripts/export-timing.mjs      # (re)export audio/timing.json from src/timing.js
  python3 audio/build_audio.py        # -> audio/soundtrack.wav (+ stems, analysis, PNGs)

Options:
  --timing PATH   build from this timing JSON instead of audio/timing.json (used as is, no
                  re-export; same as env SOL_TIMING=PATH). For trying cue lists on a copy.
  --out DIR       write soundtrack.wav, stems/, analysis.txt and the PNGs to DIR (default audio/)
  --fast          skip the PNGs
  --no-ffmpeg     skip every ffmpeg step: no AAC delivery guard (see MASTERING), no ebur128 report

Reads the timing JSON (bpm, sections, music markers, cues) and writes:
  soundtrack.wav        48 kHz / 24-bit stereo, exactly 15.000 s (720000 samples)
  stems/music.wav       pre-master music bus (24-bit)
  stems/sfx.wav         pre-master SFX bus   (one shared gain: music + sfx = pre-master mix)
  analysis.txt          loudness, WAV + AAC-delivery peaks, start/end + outro checks, energy curve,
                        cue alignment (onsets and end-aligned cues) + UI audibility, limiter activity
                        per cue, stereo, low-end alignment, spectra
  spectrogram.png       full-range log-frequency spectrogram with cue markers
  spectrogram_low.png   20-400 Hz detail (low-end cleanliness)
  waveform.png          mix / music / sfx waveforms + momentary loudness + cues
  onsets.png            +-25 ms zooms of every transient cue (cue vs detected onset)

CUE SEMANTICS (timing.json `cues`: {t, type, gain?, pan?, dir?, dur?}; any cue list works)
  t      seconds. Onset cues put their transient ON the sample round(t * 48000) (no pre-roll);
         END-ALIGNED cues (riser, reverse_swell, whip) end on that sample instead.
  gain   dB offset from the type's default level (sndkit/sfx.py LEVELS, PEAK_CAP).
  pan    -1..1, applies to every type; moving sounds (whooshes, whip) sweep through it.
  dir    +-1, which way a sweep crosses the stereo field; default = sign of pan, else +1.
  dur    seconds, for the types marked (dur).

  impact_big | impact_drop | impact_outro
                 layered impact: sub drop + boom + punch + crack (+ hall). Low layers are
                 phase-aligned to a grid kick 1-20 ms away.
  hit_cut        cinematic cut accent: snap + mid thock + low knock + room.
  punch          camera punch-in: tight low thump (165 -> 54 Hz) + short body + 3 ms transient,
                 ~120 ms, no tail. Transient at t. The thump is dropped when an impact_* lies
                 within 30 ms (the impact owns the low end); otherwise it is phase-aligned to a
                 grid kick 1-20 ms away, like the impacts.
  whoosh_fast    0.27 s whoosh starting at t.          whoosh_rise   0.66 s rising whoosh from t.
  whoosh_long    (dur) whoosh starting at t, lasting dur.
  whip           (dur, pan, dir) whip pan: an aggressive whoosh that BUILDS over dur and ENDS AT t
                 with a 2 ms hard stop, because the camera lands on t (put the impact on the same
                 t). Sounds from t - dur to t (dur >= 0.06 s); sweeps across the field in `dir`
                 and lands just past `pan`; a touch of room keeps the stop natural.
  zoom_through   (dur) accelerating whoosh from t, landing on a soft thump at t + dur.
  riser          (dur) noise + tonal crescendo that ENDS AT t.
  reverse_swell  (dur) reversed reverb of the chord at t, ENDS AT t.
  click          trackpad click: press at t + soft release 80 ms later (press only when clicks
                 are < 0.25 s apart).
  click_final    end-card CTA confirm: crisp press + soft low 'thock' tuned to the chord root
                 (both at t), then an airy tail (~0.5 s, ~15 dB under the press) of the chord's
                 upper tones struck together + breath + sparse glints on the plate. Ducks the
                 music's 1-8 kHz band by 4 dB so it reads over the outro chord.
  tap_soft, tick, ui_blip, success, toast, text_reveal: UI / type sounds (sndkit/sfx.py).

MASTERING (sndkit/master.py): hp 18 Hz -> glue comp -> soft clip -> 4x true-peak limiter at
TP_CEILING -> AAC delivery guard -> end fade, with the make-up gain iterated to -14 LUFS.
  AAC delivery guard: the master is encoded exactly like scripts/encode.py (ffmpeg native AAC-LC
  320k, 48 kHz), decoded, and measured with a 4x true-peak meter and ffmpeg ebur128. Wherever
  the decoded AAC would exceed AAC_TP_TARGET, a smooth gain dip (one AAC window wide) is applied
  after the limiter and the master is re-run, until the AAC result passes. Deterministic for a
  given ffmpeg build; skipped with --no-ffmpeg (then only the WAV ceiling applies).
  End: the music holds the last chord to the end; the mix stays up to 15.000 - FADE_OUT s and a
  raised-cosine fade reaches digital silence (0) exactly on the last sample.

Python 3 + numpy + scipy only. No samples, no downloads, fixed seeds -> bit-identical output on
every run (with the same ffmpeg build for the AAC guard).
"""
import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import wave  # noqa: E402

import numpy as np  # noqa: E402
from scipy import signal  # noqa: E402
from scipy.ndimage import convolve1d, maximum_filter1d, uniform_filter1d  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from sndkit import master as MS  # noqa: E402
from sndkit import music as MU  # noqa: E402
from sndkit import report as R  # noqa: E402
from sndkit import sfx as FX  # noqa: E402
from sndkit.dsp import SR, add_at, convolve_ir, event_duck, make_ir, ns, zp  # noqa: E402

TARGET_LUFS = -14.0
TP_CEILING = -2.5          # WAV limiter ceiling (dBTP); spec <= -1 dBTP
AAC_TP_TARGET = -1.5       # decoded AAC delivery true peak (dBTP). Spec <= -1.0 on the muxed MP4,
                           # release target <= -1.2; 0.3 dB of margin under that
AAC_ARGS = ['-c:a', 'aac', '-b:a', '320k', '-ar', '48000']  # = scripts/encode.py
FADE_OUT = 0.15            # end fade (s): the mix is held up to 14.85 s, digital silence AT 15.000
MUSIC_GAIN = 1.0
SFX_GAIN = 1.0


# --------------------------------------------------------------------------- io
def write_wav24(path, x):
    x = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0 - 2.0 ** -23)
    q = np.round(x.T * 8388607.0).astype(np.int32).reshape(-1)
    b = np.empty((q.size, 3), dtype=np.uint8)
    b[:, 0] = q & 0xFF
    b[:, 1] = (q >> 8) & 0xFF
    b[:, 2] = (q >> 16) & 0xFF
    with wave.open(path, 'wb') as w:
        w.setnchannels(x.shape[0])
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(b.tobytes())


def read_wav24(path):
    with wave.open(path, 'rb') as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = np.frombuffer(w.readframes(n), dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    v = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
    v = np.where(v >= 1 << 23, v - (1 << 24), v)
    return (v.reshape(n, ch).T / 8388608.0), dict(channels=ch, sampwidth=sw, rate=sr, frames=n)


def ffmpeg_ebur128(path):
    if not shutil.which('ffmpeg'):
        return None
    p = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128=peak=true',
                        '-f', 'null', '-'], capture_output=True, text=True)
    txt = p.stderr
    summ = txt[txt.rfind('Summary:'):]
    g = lambda pat: float(re.search(pat, summ, re.S).group(1)) if re.search(pat, summ, re.S) else None
    return dict(I=g(r'I:\s+(-?[\d.]+) LUFS'), LRA=g(r'LRA:\s+(-?[\d.]+) LU'),
                TP=g(r'True peak:.*?Peak:\s+(-?[\d.inf]+) dBFS'))


def aac_roundtrip(x, td, mux=False):
    """Encode `x` (a float array, written with write_wav24 = the very bytes of soundtrack.wav, or the
    path of a WAV file) exactly the way scripts/encode.py does (WAV input with `-ss 0.0000`, ffmpeg
    AAC 320k 48 kHz, `-t` = reel length) and decode it back. mux=True writes an .mp4 with a dummy
    H.264 stream next to the audio, like the real delivery; mux=False an .m4a (same AAC stream).
    The AAC encoder is sensitive to LSB-level changes (its overshoot moves by ~0.1 dB), so always
    measure the exact bytes that get delivered.
    -> (decoded float64 (2, n), ebur128 dict, md5 of the decoded audio)."""
    if isinstance(x, str):
        wav = x
        with wave.open(wav, 'rb') as wf:
            dur = f'{wf.getnframes() / wf.getframerate():.3f}'
    else:
        wav = os.path.join(td, 'master.wav')
        write_wav24(wav, x)
        dur = f'{x.shape[1] / SR:.3f}'
    if mux:
        out = os.path.join(td, 'delivery.mp4')
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=white:s=1080x1920:r=30',
               '-ss', '0.0000', '-i', wav, '-map', '0:v', '-map', '1:a',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '40', *AAC_ARGS,
               '-t', dur, '-movflags', '+faststart', out]
    else:
        out = os.path.join(td, 'delivery.m4a')
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-ss', '0.0000', '-i', wav, *AAC_ARGS, '-t', dur, out]
    subprocess.run(cmd, check=True)
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', out, '-map', '0:a', '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    dec = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).T.astype(np.float64)
    return dec, ffmpeg_ebur128(out), hashlib.md5(raw).hexdigest()


# --------------------------------------------------------------------------- build
def build(timing, log, info=None):
    """-> (music, sfx, tracks, kick_trig). `info` (optional dict) receives per-cue render notes,
    the cues rendered without a transient, and the music's trigger events."""
    N = ns(timing['duration'])
    assert N == 720000, N
    assert abs(timing['beat'] - MU.BEAT) < 1e-9 and timing['bpm'] == 125

    t0 = time.time()
    ir_music_hall = make_ir(2.8, 2.2, 1.0, seed=11, predelay=0.024, hp_f=230.0, lp_f=9000.0)
    ir_drum_room = make_ir(0.9, 0.55, 0.32, seed=12, predelay=0.006, hp_f=260.0, lp_f=10000.0, er_span=0.03)
    ir_sfx_hall = make_ir(4.2, 3.3, 1.5, seed=13, predelay=0.016, hp_f=140.0, lp_f=8500.0)
    ir_ui_room = make_ir(0.6, 0.36, 0.24, seed=14, predelay=0.004, hp_f=450.0, lp_f=11000.0, er_span=0.02)
    ir_plate = make_ir(2.0, 1.4, 1.1, seed=15, predelay=0.012, hp_f=500.0, lp_f=12000.0)
    ir_swell = make_ir(2.8, 2.5, 1.4, seed=16, predelay=0.0, hp_f=200.0, lp_f=9000.0)
    log(f'  IRs {time.time() - t0:.1f}s')

    t0 = time.time()
    tracks, kick_trig, events = MU.build_music(N, ir_music_hall, ir_drum_room, timing['cues'])
    music = sum(tracks.values())
    # calibrate: the drop section of the music bus sits at -16 LUFS (ungated); SFX levels are set
    # in this same domain (see sndkit/sfx.py LEVELS)
    cal = 10.0 ** ((-16.0 - MS.segment_lufs(music, timing['sections']['drop']['start'],
                                            timing['sections']['drop']['end'])) / 20.0)
    music *= cal * MUSIC_GAIN
    tracks = {k: v * cal for k, v in tracks.items()}
    log(f'  music {time.time() - t0:.1f}s')

    t0 = time.time()

    def riser_target(t):
        root = MU.CHORDS[MU.chord_at(round(t / MU.BEAT))]['root']
        return 60 + (root - 60) % 12

    def swell_chord(t):
        return MU.CHORDS[MU.chord_at(round(t / MU.BEAT))]['pad']

    # the sound design sees the score: kick / clap positions (phase-aligned low layers, no flams),
    # the harmony (pitched UI sounds) and the other cues (no pile-ups)
    ctx = dict(riser_target=riser_target, swell_chord=swell_chord, ir_swell=ir_swell, cues=timing['cues'],
               kick_trig=kick_trig, clap_trig=events['clap'], chord_at_time=MU.chord_at_time,
               kick_track=np.mean(tracks['kick'], axis=0),
               chord_tones=lambda t: (MU.CHORDS[MU.chord_at_time(t + 0.01)]['root'],
                                      MU.CHORDS[MU.chord_at_time(t + 0.01)]['pad']),
               notes={}, soft_onset=set())
    dry = np.zeros((2, N))
    buses = {k: np.zeros((2, N)) for k in ('hall_big', 'room', 'plate', 'glue')}
    spans = {}  # cue index -> (first, last + 1) sample of its dry sound; dry signal for END_ALIGNED
    ea_dry = np.zeros((2, N))  # dry END_ALIGNED sounds (riser, swell, whip): taken out for onset detection
    for i, cue in enumerate(timing['cues']):
        lay = FX.render_cue(cue, i, ctx)
        for sig, off, sends in lay:
            s = ns(cue['t']) + off
            add_at(dry, sig * sends.get('_dry', 1.0), s)
            if cue['type'] in FX.END_ALIGNED:
                add_at(ea_dry, sig * sends.get('_dry', 1.0) * SFX_GAIN, s)
            for bus, g in sends.items():
                if bus != '_dry':
                    add_at(buses[bus], sig * g, s)
        dl = [(off, sig * sends.get('_dry', 1.0)) for sig, off, sends in lay if sends.get('_dry', 1.0) > 0]
        if dl:
            lo = min(o for o, _ in dl)
            hi = max(o + x.shape[1] for o, x in dl)
            iso = None
            if cue['type'] in FX.END_ALIGNED:
                iso = np.zeros((2, hi - lo))
                for o, x in dl:
                    iso[:, o - lo:o - lo + x.shape[1]] += x
            spans[i] = (ns(cue['t']) + lo, ns(cue['t']) + hi, iso)
    sfx = dry + convolve_ir(buses['hall_big'], ir_sfx_hall) * 0.9 + convolve_ir(buses['room'], ir_ui_room) \
        + convolve_ir(buses['plate'], ir_plate) * 0.8 + convolve_ir(buses['glue'], ir_music_hall)
    sfx *= SFX_GAIN
    # duck the music under cues (band-limited for UI sounds, light broadband for hits)
    ev = {'ui': [], 'tone': [], 'full': []}
    for cue in timing['cues']:
        d = FX.DUCK.get(cue['type'])
        if d:
            band, depth, hold, rel = d
            if band == 'full':
                depth = max(depth + 0.5 * float(cue.get('gain', 0.0)), 0.5)  # quieter hit -> lighter dip
            ev[band].append((ns(cue['t']), depth, hold, 0.004, rel))
    g_full = event_duck(N, ev['full'])
    for band_name, (lo, hi) in (('ui', (1000.0, 8000.0)), ('tone', (500.0, 8000.0))):
        if ev[band_name]:
            g = event_duck(N, ev[band_name])
            band = zp(music, 'bandpass', [lo, hi], 2)
            music = music - band + band * g[None, :]
    music = music * g_full[None, :]
    log(f'  sfx {time.time() - t0:.1f}s')
    if info is not None:
        info.update(notes=ctx['notes'], soft_onset=ctx['soft_onset'], events=events, spans=spans, ea_dry=ea_dry)
    return music, sfx, tracks, kick_trig


def ensure_timing(log, path=None):
    """Load the timing JSON. Default: audio/timing.json, re-exported first if src/timing.js is newer
    (keeps picture and sound in sync). An explicit path is loaded as is (never re-exported)."""
    if path:
        log(f'timing: {path} (as given, no re-export)')
        return json.load(open(path))
    src = os.path.join(ROOT, 'src', 'timing.js')
    dst = os.path.join(HERE, 'timing.json')
    if os.path.exists(src) and (not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)):
        if shutil.which('node'):
            log('src/timing.js is newer than audio/timing.json -> re-exporting')
            subprocess.run(['node', os.path.join(ROOT, 'scripts', 'export-timing.mjs')], check=True, cwd=ROOT)
        else:
            log('WARNING: src/timing.js is newer than audio/timing.json and node is not available')
    return json.load(open(dst))


def master_for_delivery(pre, log, use_ffmpeg):
    """Master, then check the AAC delivery encode of the exact bytes that will be written; where the
    decoded AAC would exceed AAC_TP_TARGET, add a smooth post-limiter gain dip there and master
    again (closed loop). ffmpeg's AAC rate control is global, so a dip can move a small overshoot
    elsewhere: the loop keeps going until the whole file passes, and from the 5th pass on it also
    lowers the WAV ceiling by the remaining excess (fallback; never needed so far).
    -> (master, master info, guard_db per sample, AAC info or None)."""
    n = pre.shape[1]
    guard = np.zeros(n)
    g_db = 4.0
    ceiling = TP_CEILING
    aac = None
    ffmpeg_ok = use_ffmpeg and shutil.which('ffmpeg') is not None
    if use_ffmpeg and not ffmpeg_ok:
        log('WARNING: ffmpeg not found: AAC delivery guard skipped (WAV ceiling only)')
    win = np.hanning(ns(0.01) + 1)
    win /= win.sum()
    with tempfile.TemporaryDirectory() as td:
        for rnd in range(10):
            out, minfo = MS.master(pre, TARGET_LUFS, ceiling, FADE_OUT, log=log,
                                   guard_db=guard if guard.any() else None, g_db=g_db)
            g_db = minfo['gain_db']
            if not ffmpeg_ok:
                break
            dec, ff, _ = aac_roundtrip(out, td)
            env = MS._tp_envelope(dec)
            tp_own = float(20 * np.log10(env.max()))
            tp = max(tp_own, ff['TP'] if ff and ff['TP'] is not None else -np.inf)
            ok = tp <= AAC_TP_TARGET
            aac = dict(tp_own=tp_own, ff=ff, rounds=rnd + 1, ceiling=ceiling, ok=ok)
            log(f'  AAC guard pass {rnd}: decoded AAC true peak {tp_own:.2f} dBTP (ebur128 {ff["TP"]} dBFS), '
                f'I {ff["I"]} LUFS -> {"OK" if ok else "over " + f"{AAC_TP_TARGET:.1f}"}')
            if ok:
                break
            # required dip (aim 0.15 dB under the target), spread over +-1 long AAC window, smoothed
            need = np.maximum(20 * np.log10(np.maximum(env[:n], 1e-9)) - (AAC_TP_TARGET - 0.15), 0.0)
            need = maximum_filter1d(need, size=2 * 2048 + 1, mode='nearest')
            guard += convolve1d(need, win, mode='nearest')
            if rnd >= 4:
                ceiling -= tp - AAC_TP_TARGET + 0.1
                log(f'  AAC guard: lowering the WAV ceiling to {ceiling:.2f} dBTP')
        if aac is not None and not aac['ok']:
            log(f'WARNING: AAC delivery true peak {aac["tp_own"]:.2f} dBTP still over {AAC_TP_TARGET:.1f} after '
                f'{aac["rounds"]} passes')
    minfo['guard_db'] = guard
    minfo['ceiling'] = ceiling
    return out, minfo, guard, aac


def main():
    ap = argparse.ArgumentParser(description='Build the SOL Sniper soundtrack (see the module docstring).')
    ap.add_argument('--timing', default=os.environ.get('SOL_TIMING') or None,
                    help='timing JSON to build from, used as is (default: audio/timing.json, re-exported '
                         'from src/timing.js when that is newer). Env: SOL_TIMING')
    ap.add_argument('--out', default=HERE, help='output directory (default: audio/)')
    ap.add_argument('--fast', action='store_true', help='skip the PNGs')
    ap.add_argument('--no-ffmpeg', action='store_true', help='skip ffmpeg (no AAC guard / ebur128)')
    args = ap.parse_args()
    use_ffmpeg = not args.no_ffmpeg
    outdir = os.path.abspath(args.out)
    T0 = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)

    timing = ensure_timing(log, args.timing)
    log('building music + sfx')
    binfo = {}
    music, sfx, tracks, kick_trig = build(timing, log, binfo)
    pre = music + sfx
    g0 = 10.0 ** ((-18.0 - MS.integrated_lufs(pre)) / 20.0)
    # stems share one gain (so music + sfx = the pre-master mix) with 1 dB of sample-peak headroom
    pk = max(np.max(np.abs(music)), np.max(np.abs(sfx))) * g0
    stem_gain = g0 * min(1.0, 10.0 ** (-1.0 / 20.0) / pk)
    music_s, sfx_s = music * stem_gain, sfx * stem_gain
    binfo['ea_dry'] = binfo['ea_dry'] * stem_gain

    log('mastering (+ AAC delivery guard)')
    out, minfo, guard, aac = master_for_delivery(pre * g0, log, use_ffmpeg)

    os.makedirs(os.path.join(outdir, 'stems'), exist_ok=True)
    p_mix = os.path.join(outdir, 'soundtrack.wav')
    write_wav24(p_mix, out)
    write_wav24(os.path.join(outdir, 'stems', 'music.wav'), music_s)
    write_wav24(os.path.join(outdir, 'stems', 'sfx.wav'), sfx_s)
    log(f'wrote {p_mix}  ({time.time() - T0:.1f}s)')

    log(f'stems: common gain {20 * np.log10(stem_gain):+.2f} dB (pre-master domain, before glue/limiter)')
    analyse(timing, p_mix, music_s, sfx_s, tracks, kick_trig, minfo, use_ffmpeg, args.fast, logs, binfo,
            outdir=outdir, aac=aac)
    log(f'done in {time.time() - T0:.1f}s')


# --------------------------------------------------------------------------- analysis
UI_AUDIBLE = ('click', 'click_final', 'tap_soft', 'tick', 'ui_blip', 'success', 'toast')
HIT_TYPES = ('hit_cut', 'punch', 'impact_big', 'impact_drop', 'impact_outro')


def _marker(timing, name, default):
    for m in timing.get('music', {}).get('markers', []):
        if m['name'] == name:
            return float(m['t'])
    return default


def _nearest_cue(timing, t, window=0.06):
    c = [x for x in timing['cues'] if abs(x['t'] - t) <= window]
    c.sort(key=lambda x: abs(x['t'] - t))
    return f"{c[0]['type']}@{c[0]['t']:.3f}" if c else '-'


def energy_curve(timing, mix, w):
    """The arc the picture needs: the drop is the biggest moment, the pre-drop gap really dips."""
    secs = timing['sections']
    tm, lm = MS.momentary(mix)  # 400 ms windows, 50 ms hop; time = window end
    tc = tm - 0.2
    w('ENERGY CURVE (momentary 400 ms loudness, final mix)')
    mx = {}
    for name, s in secs.items():
        sel = (tc >= s['start']) & (tc < s['end'])
        i = int(np.argmax(lm[sel]))
        mx[name] = lm[sel][i]
        w(f"  {name:8s} max {lm[sel][i]:6.1f} LUFS @ {tc[sel][i]:5.2f}s   median {np.median(lm[sel]):6.1f}")
    if all(k in mx for k in ('drop', 'title', 'montage')):
        d1, d2 = mx['drop'] - mx['title'], mx['drop'] - mx['montage']
        w(f"  drop max vs title max {d1:+.1f} LU (want >= +2), vs montage max {d2:+.1f} LU (want >= +1) -> "
          f"{'OK' if d1 >= 2 and d2 >= 1 else 'CHECK'}")
    t_build, t_gap = _marker(timing, 'build', 5.28), _marker(timing, 'gap', 6.0)
    drop_cue = [c['t'] for c in timing['cues'] if c['type'] == 'impact_drop']
    t_drop = drop_cue[0] if drop_cue else _marker(timing, 'drop', 6.24)
    # a whip landing on the drop is the camera's own wind-up INTO the impact: the dip is the part
    # of the gap before it (both are reported)
    whips = [c for c in timing['cues'] if c['type'] == 'whip' and abs(c['t'] - t_drop) <= 0.02]
    t_w = min(c['t'] - float(c.get('dur', 0.15)) for c in whips) if whips else t_drop
    t_dip = t_w if t_w - t_gap >= 0.04 else t_drop
    lb, lg = MS.segment_lufs(mix, t_build, t_gap), MS.segment_lufs(mix, t_gap, t_dip)
    w(f"  build {t_build:.2f}-{t_gap:.2f}s {lb:.1f} LUFS, pre-drop gap {t_gap:.2f}-{t_dip:.3f}s"
      f"{' (before the whip)' if t_dip < t_drop else ''} {lg:.1f} LUFS: "
      f"{lg - lb:+.1f} LU (want <= -3) -> {'OK' if lg - lb <= -3 else 'CHECK'}")
    if t_dip < t_drop:
        lw = MS.segment_lufs(mix, t_dip, t_drop)
        tm, lm = MS.momentary(mix)
        sel = (tm > t_dip) & (tm <= t_drop + 0.001)
        dsel = (tm - 0.2 >= t_drop - 0.05) & (tm - 0.2 < t_drop + 0.6)
        w(f"  whip wind-up {t_dip:.3f}-{t_drop:.3f}s {lw:.1f} LUFS ungated; momentary max into the drop "
          f"{lm[sel].max():.1f} LUFS vs drop max {lm[dsel].max():.1f} LUFS "
          f"({lm[sel].max() - lm[dsel].max():+.1f} LU, want <= -2) -> "
          f"{'OK' if lm[sel].max() - lm[dsel].max() <= -2 else 'CHECK'}")
    ph = zp(zp(mix, 'highpass', 300.0, 4), 'lowpass', 12000.0, 2)  # crude phone speaker
    w('  phone-speaker sim (HP 300 Hz / LP 12 kHz), ungated: ' + '  '.join(
        f"{n} {MS.segment_lufs(ph, s['start'], s['end']):.1f}" for n, s in secs.items()))
    w('')


def master_dynamics(timing, minfo, w):
    lg = minfo.get('limiter_gain')
    if lg is None:
        return
    gr = -20.0 * np.log10(np.maximum(lg, 1e-12))
    imax = int(np.argmax(gr))
    w('MASTER DYNAMICS (limiter gain reduction; should work on the big hits, not on UI clicks)')
    w(f"  limiter max GR {gr[imax]:.2f} dB at {imax / SR:.3f}s ({_nearest_cue(timing, imax / SR)}); "
      f"glue comp max GR {minfo['glue_gr_db']:.2f} dB at {minfo['glue_t'][int(np.argmax(minfo['glue_gr']))]:.2f}s")
    row = []
    worst_ui, worst_at = 0.0, '-'
    hits = [c['t'] for c in timing['cues'] if c['type'] in HIT_TYPES]
    for c in timing['cues']:
        if c['type'] in FX.TRANSIENT_TYPES:
            s = ns(c['t'])
            g = float(gr[max(s - ns(0.004), 0):s + ns(0.03)].max())
            row.append(f"{c['type']}@{c['t']:.2f} {g:.1f}")
            alone = not any(abs(h - c['t']) <= 0.03 for h in hits)
            if c['type'] in UI_AUDIBLE and alone and g > worst_ui:
                worst_ui, worst_at = g, f"{c['type']}@{c['t']:.3f}"
    w('  GR per transient cue (dB): ' + ', '.join(row))
    w(f"  max GR on a UI cue (not sharing its frame with a hit): {worst_ui:.2f} dB at {worst_at} (want < 0.5) -> "
      f"{'OK' if worst_ui < 0.5 else 'CHECK'}")
    w('')


def stereo_report(timing, mix, w):
    w('STEREO / MONO COMPATIBILITY')
    for name, s in timing['sections'].items():
        a, b = ns(s['start']), ns(s['end'])
        L_, R_ = mix[0, a:b], mix[1, a:b]
        M = 0.5 * (L_ + R_)
        loss = 10 * np.log10(np.mean(M ** 2) / (0.5 * (np.mean(L_ ** 2) + np.mean(R_ ** 2))))
        w(f"  {name:8s} L/R corr {np.corrcoef(L_, R_)[0, 1]:+.2f}, mono sum vs stereo {loss:+.2f} dB")
    W, H = ns(0.1), ns(0.05)
    cs = []
    for i in range(0, mix.shape[1] - W, H):
        l_, r_ = mix[0, i:i + W], mix[1, i:i + W]
        if np.std(l_) > 1e-4 and np.std(r_) > 1e-4:
            cs.append((np.corrcoef(l_, r_)[0, 1], i / SR))
    cs.sort()
    w('  lowest 100 ms L/R correlation: ' + ', '.join(f'{c:+.2f}@{t:.2f}s' for c, t in cs[:5])
      + f" (want >= +0.3) -> {'OK' if cs and cs[0][0] >= 0.3 else 'CHECK'}")
    w('')


def low_end_alignment(timing, tracks, kick_trig, sfx, w):
    """Low band (<160 Hz) of kick + impact/hit over the first 150 ms, as rendered vs the plain
    power sum of the two parts: below the power sum = the two low layers cancel."""
    kick = tracks['kick']
    lpk = zp(np.mean(kick, axis=0), 'lowpass', 160.0, 4)
    lps = zp(np.mean(sfx, axis=0), 'lowpass', 160.0, 4)
    rows = []
    for i, c in enumerate(timing['cues']):
        if c['type'] not in HIT_TYPES:
            continue
        s = ns(c['t'])
        if not any(abs(kt - s) <= ns(0.03) for kt in kick_trig):
            continue
        a, b = s, s + ns(0.15)
        k = float(np.mean(lpk[a:b] ** 2))
        x = float(np.mean(lps[a:b] ** 2))
        both = float(np.mean((lpk[a:b] + lps[a:b]) ** 2))
        rows.append(f"{c['type']}@{c['t']:.3f}: sum {10 * np.log10(both / (k + x)):+.1f} dB vs power sum")
    w('LOW-END ALIGNMENT (cues within 30 ms of a kick: kick + sfx below 160 Hz over the first 150 ms,'
      ' vs the power sum of the two; ~0 or above = no cancellation)')
    for r in rows:
        w('  ' + r)
    w('')


def section_spectra(timing, mix, w):
    w('SECTION SPECTRA (% of section energy, mono sum)')
    for name, s in timing['sections'].items():
        seg = np.mean(mix[:, ns(s['start']):ns(s['end'])], axis=0)
        F = np.abs(np.fft.rfft(seg)) ** 2
        fr = np.fft.rfftfreq(len(seg), 1 / SR)
        e = lambda lo, hi: 100.0 * F[(fr >= lo) & (fr < hi)].sum() / F[(fr >= 20) & (fr < 20000)].sum()
        w(f"  {name:8s} 30-80 Hz {e(30, 80):5.1f}   80-200 {e(80, 200):5.1f}   200-400 {e(200, 400):5.1f}   "
          f"400-900 {e(400, 900):5.1f}   2-5k {e(2000, 5000):5.2f}   8-20k {e(8000, 20000):5.2f}")
    w('')


def analyse(timing, p_mix, music, sfx, tracks, kick_trig, minfo, use_ffmpeg, fast, logs, binfo=None,
            outdir=HERE, aac=None):
    binfo = binfo or {}
    notes = binfo.get('notes', {})
    soft = binfo.get('soft_onset', set())
    mix, info = read_wav24(p_mix)
    N = mix.shape[1]
    L = []
    w = L.append
    w('SOL Sniper reel: soundtrack analysis (generated by audio/build_audio.py)')
    w('=' * 78)
    w(f"file: {os.path.relpath(p_mix, ROOT)}  {info['rate']} Hz, {info['channels']} ch, {8 * info['sampwidth']}-bit PCM, "
      f"{info['frames']} samples = {info['frames'] / info['rate']:.6f} s")
    w(f"spec: 720000 samples -> {'OK' if info['frames'] == 720000 and info['rate'] == 48000 else 'FAIL'}")
    w('')
    lufs = MS.integrated_lufs(mix)
    tp = MS.true_peak(mix)
    sp = 20 * np.log10(np.max(np.abs(mix)))
    w('LOUDNESS / PEAK')
    w(f'  integrated (own BS.1770-4):  {lufs:.2f} LUFS   (target {TARGET_LUFS:.1f})')
    w(f'  loudness range:              {MS.loudness_range(mix):.1f} LU')
    w(f'  true peak (4x oversampled):  {tp:.2f} dBTP  (limit -1.0)')
    w(f'  sample peak:                 {sp:.2f} dBFS; samples at full scale: {int(np.sum(np.abs(mix) >= 0.9999))}')
    ff = ffmpeg_ebur128(p_mix) if use_ffmpeg else None
    if ff:
        w(f"  ffmpeg ebur128 (WAV):        I = {ff['I']} LUFS, LRA = {ff['LRA']} LU, true peak = {ff['TP']} dBFS")
    w(f"  master: make-up gain {minfo['gain_db']:+.2f} dB, glue comp max GR {minfo['glue_gr_db']:.2f} dB, "
      f"limiter max GR {minfo['limiter_gr_db']:.2f} dB (WAV ceiling {minfo.get('ceiling', TP_CEILING):.1f} dBTP)")
    dc = np.mean(mix, axis=1)
    w(f'  DC offset: L {dc[0]:+.2e}  R {dc[1]:+.2e}')
    w('')
    w('AAC DELIVERY (as scripts/encode.py muxes it: ffmpeg native AAC-LC 320k, 48 kHz, into the MP4)')
    if use_ffmpeg and shutil.which('ffmpeg'):
        with tempfile.TemporaryDirectory() as td:
            dec, fm, md5_mp4 = aac_roundtrip(p_mix, td, mux=True)  # the delivered file's own bytes
            _, _, md5_m4a = aac_roundtrip(p_mix, td, mux=False)
        tpa = MS.true_peak(dec)
        ok = fm['TP'] is not None and fm['TP'] <= -1.2 and tpa <= -1.2
        w(f"  MP4 replica, ffmpeg ebur128: I = {fm['I']} LUFS, true peak = {fm['TP']} dBTP   "
          f"(spec <= -1.0, target <= -1.2) -> {'OK' if ok else 'FAIL'}")
        w(f'  decoded AAC, own 4x meter:   true peak {tpa:.2f} dBTP, sample peak '
          f'{20 * np.log10(np.max(np.abs(dec))):.2f} dBFS, integrated {MS.integrated_lufs(dec):.2f} LUFS')
        w(f'  WAV -> AAC overshoot {tpa - tp:+.2f} dB; MP4 audio bit-identical to the audio-only encode the '
          f"guard measures: {'yes' if md5_mp4 == md5_m4a else 'NO'}")
        g = minfo.get('guard_db')
        if aac:
            w(f"  delivery guard: {aac['rounds']} master pass(es), AAC target {AAC_TP_TARGET:.1f} dBTP")
        if g is not None and np.any(g > 0.005):
            on = np.concatenate([[0], (g > 0.005).astype(int), [0]])
            st, en = np.flatnonzero(np.diff(on) == 1), np.flatnonzero(np.diff(on) == -1)
            w('  guard gain dips (post-limiter, smooth): ' + ', '.join(
                f'{(a + int(np.argmax(g[a:b]))) / SR:.3f}s -{g[a:b].max():.2f} dB over {(b - a) / SR * 1000:.0f} ms'
                for a, b in zip(st, en)))
        else:
            w('  guard gain dips: none needed')
    else:
        w('  skipped (--no-ffmpeg or no ffmpeg): the AAC delivery true peak is NOT verified')
    w('')
    w('START / END')
    first = mix[:, :ns(0.01)]
    w(f'  first sample: L {mix[0, 0]:+.4f}  R {mix[1, 0]:+.4f};  RMS of first 10 ms: '
      f'{20 * np.log10(np.sqrt(np.mean(first ** 2)) + 1e-12):.1f} dBFS (impact lands at sample 0)')
    pk5 = 20 * np.log10(np.max(np.abs(mix[:, :ns(0.005)])) + 1e-12)
    w(f'  peak of first 5 ms: {pk5:.1f} dBFS')
    rms_db = lambda a, b: 20 * np.log10(np.sqrt(np.mean(mix[:, a:b] ** 2)) + 1e-12)
    T_end = N / SR
    w('  outro, 50 ms RMS (dBFS): ' + '  '.join(
        f'{x:.2f} {rms_db(ns(x), ns(x + 0.05)):.1f}' for x in np.arange(T_end - 0.70, T_end - 0.01, 0.05)))
    t_scan = np.arange(ns(T_end - 2.0), N - ns(0.05), ns(0.005))
    below = [i for i in t_scan if rms_db(i, i + ns(0.05)) < -36.0]
    t_below = below[0] / SR if below else T_end
    hold = rms_db(ns(T_end - FADE_OUT - 0.05), ns(T_end - FADE_OUT))
    ref = rms_db(ns(T_end - 0.60), ns(T_end - FADE_OUT - 0.05))
    w(f'  held to the fade: {T_end - FADE_OUT - 0.05:.2f}-{T_end - FADE_OUT:.2f}s at {hold:.1f} dBFS ({hold - ref:+.1f} dB vs '
      f'{T_end - 0.6:.2f}-{T_end - FADE_OUT - 0.05:.2f}s); first 50 ms window below -36 dBFS starts at {t_below:.3f}s '
      f"(want >= {T_end - FADE_OUT:.2f}) -> {'OK' if t_below >= T_end - FADE_OUT - 1e-6 else 'CHECK'}")
    nz = int(np.sum(np.all(mix[:, ::-1] == 0.0, axis=0).cumprod()))
    w(f'  end fade {T_end - FADE_OUT:.3f} -> {T_end:.3f}s (raised cosine); last 10 ms peak '
      f'{20 * np.log10(np.max(np.abs(mix[:, -ns(0.01):])) + 1e-12):.1f} dBFS; last sample L {mix[0, -1]:+.1e} '
      f"R {mix[1, -1]:+.1e} ({nz} trailing all-zero sample(s)) -> {'OK' if nz >= 1 else 'FAIL'}")
    for c in timing['cues']:
        if c['type'] == 'click_final':
            s0 = ns(c['t'])
            pre_, at_ = rms_db(s0 - ns(0.06), s0 - ns(0.01)), rms_db(s0, s0 + ns(0.05))
            tm, lm = MS.momentary(mix)
            l_pre = float(np.interp(c['t'] - 0.02, tm, lm))
            l_at = float(lm[(tm > c['t']) & (tm <= c['t'] + 0.45)].max())
            w(f"  click_final@{c['t']:.3f}: 50 ms RMS {pre_:.1f} -> {at_:.1f} dBFS ({at_ - pre_:+.1f} dB); "
              f'momentary loudness {l_pre:.1f} -> max {l_at:.1f} LUFS ({l_at - l_pre:+.1f} LU)')
    w('')

    # sections
    w('SECTION LOUDNESS (ungated, K-weighted; final mix / music stem / sfx stem as written)')
    for name, s in timing['sections'].items():
        a, b = s['start'], s['end']
        w(f"  {name:8s} {a:5.2f}-{b:5.2f}s   mix {MS.segment_lufs(mix, a, b):6.1f}   music "
          f"{MS.segment_lufs(music, a, b):6.1f}   sfx {MS.segment_lufs(sfx, a, b):6.1f} LUFS")
    w('')
    energy_curve(timing, mix, w)

    # onsets
    cues = timing['cues']
    # stem onsets: the SFX stem without the dry END_ALIGNED sounds (a whip at full level right up to
    # a hit leaves no level jump for an energy-ratio detector; those have their own check below)
    sfx_on = sfx - binfo['ea_dry'] if 'ea_dry' in binfo else sfx
    on_sfx, _ = R.detect_onsets(sfx_on, thresh_db=8.0, floor_db=-70.0)
    on_mix_b, _ = R.detect_onsets(mix, thresh_db=6.0, floor_db=-60.0, min_gap=0.006)
    on_mix_h, _ = R.detect_onsets(mix, thresh_db=6.0, floor_db=-66.0, hp_f=2500.0, min_gap=0.006)
    on_mix = np.unique(np.concatenate([on_mix_b, on_mix_h]))
    is_tr = lambda i, c: c['type'] in FX.TRANSIENT_TYPES and i not in soft
    trans = [c for i, c in enumerate(cues) if is_tr(i, c)]
    w('CUE ALIGNMENT (blind energy-ratio onset detector, sample resolution; deviation = detected - cue)')
    w(f'  detected onsets: sfx stem {len(on_sfx)} (without the dry riser/swell/whip layers), final mix {len(on_mix)} '
      f'(broadband + >2.5 kHz band)')
    ea_ends = [ns(c['t']) for c in cues if c['type'] in FX.END_ALIGNED and c['type'] == 'whip']
    masked = 0
    w('  t (s)    type           gain   sfx stem dev (ms)   final mix dev (ms)   SFX/music: K-wtd  best 1/3-oct band'
      '      render notes')
    rows = []
    low_ui = []
    devs_s, devs_m = [], []
    crit = ('impact_big', 'impact_drop', 'impact_outro', 'hit_cut', 'punch', 'click', 'click_final')
    crit_s, crit_m = [], []
    for i, c in enumerate(cues):
        typ = c['type']
        tr = is_tr(i, c)
        ds = R.match(on_sfx, c['t']) if tr else None
        dm = R.match(on_mix, c['t']) if tr else None
        a = ns(c['t'])
        if typ in ('riser', 'reverse_swell'):
            a0, a1 = a - ns(min(c.get('dur', 0.5), 0.25)), a  # the climax
        elif typ == 'whip':
            a0, a1 = a - ns(min(c.get('dur', 0.15), 0.06)), a  # its loudest part, right before the stop
        elif typ in ('whoosh_long', 'zoom_through'):
            a0, a1 = a, a + ns(c.get('dur', 0.4))
        elif typ in ('whoosh_fast', 'whoosh_rise', 'text_reveal'):
            a0, a1 = a, a + ns(0.25)
        elif typ in ('click', 'tap_soft', 'tick'):
            a0, a1 = a, a + ns(0.02)
        elif typ == 'click_final':
            a0, a1 = a, a + ns(0.03)
        else:
            a0, a1 = a, a + ns(0.08)
        ks, km = MS.kweight(sfx[:, a0:a1]), MS.kweight(music[:, a0:a1])
        snr = 10 * np.log10((np.mean(ks ** 2) + 1e-20) / (np.mean(km ** 2) + 1e-20))
        bb, bf = R.best_band_snr(sfx[:, a0:a1], music[:, a0:a1])
        f = lambda d: f'{d * 1000:+8.2f}' if d is not None else ('     n/a' if tr else '       -')
        on_whip = tr and dm is None and any(abs(e - a) <= ns(0.002) for e in ea_ends)
        if on_whip:
            masked += 1
            notes[i] = '; '.join(x for x in (notes.get(i, ''), 'mix: lands on a whip stop, no level jump to detect') if x)
        snr_s = f'{snr:+11.1f}' if snr < 40 else '       >+40'
        bb_s = f'{bb:+6.1f}' if bb < 40 else '  >+40'
        flag = ''
        if typ in UI_AUDIBLE and bb < 6.0:
            flag = ' LOW'
            low_ui.append(f"{typ}@{c['t']:.3f} ({bb:+.1f} dB)")
        w(f"  {c['t']:6.3f}   {typ:13s} {c.get('gain', 0):+4.0f}   {f(ds):>18s}   {f(dm):>18s}   {snr_s}  {bb_s} dB @ {bf:>5.0f} Hz"
          f"{flag:4s}  {notes.get(i, '')}")
        if tr:
            rows.append((c, ds, dm))
            if ds is not None:
                devs_s.append(abs(ds))
            if dm is not None:
                devs_m.append(abs(dm))
            if typ in crit:
                crit_s.append(abs(ds) if ds is not None else np.inf)
                if not on_whip:
                    crit_m.append(abs(dm) if dm is not None else np.inf)
    w(f'  transient cues: {len(trans)} (+{len(soft)} rendered without a transient by design); '
      f'matched in sfx stem {len(devs_s)}, in final mix {len(devs_m)}'
      + (f' ({masked} landing on a whip stop: no level jump in the mix, see the stem)' if masked else ''))
    w("  UI audibility (best 1/3-octave band over the music, want >= +6 dB): "
      + ('all OK' if not low_ui else 'LOW: ' + ', '.join(low_ui)))
    if devs_s:
        w(f'  sfx stem  |dev|: max {max(devs_s) * 1000:.2f} ms, mean {np.mean(devs_s) * 1000:.2f} ms')
    if crit_s:
        w(f"  click/impact/hit cues (sfx stem): max |dev| {max(crit_s) * 1000:.2f} ms -> "
          f"{'PASS (< 2 ms)' if max(crit_s) < 0.002 else 'FAIL'}")
    if devs_m:
        w(f'  final mix |dev|: max {max(devs_m) * 1000:.2f} ms, mean {np.mean(devs_m) * 1000:.2f} ms')
    if crit_m:
        w(f"  click/impact/hit cues (final mix): max |dev| {max(crit_m) * 1000:.2f} ms -> "
          f"{'PASS (< 2 ms)' if max(crit_m) < 0.002 else 'FAIL'}")
    # music grid
    on_kick, _ = R.detect_onsets(tracks['kick'], thresh_db=8.0, floor_db=-70.0, hp_f=30.0)
    kd = np.abs(np.array([(on_kick[int(np.argmin(np.abs(on_kick - s)))] - s) / SR for s in kick_trig]))
    grid_ok = all(s % MU.BEAT_N == 0 for s in kick_trig)
    w(f'  music beat grid: {len(kick_trig)} kicks placed at n*23040 samples ({"OK" if grid_ok else "FAIL"}); '
      f'detected kick onsets vs beat grid: max |dev| {kd.max() * 1000:.2f} ms')
    on_mus, _ = R.detect_onsets(music, thresh_db=10.0, floor_db=-50.0, min_gap=0.03)
    on_mus = on_mus[(on_mus >= ns(1.44) - 240) & (on_mus < ns(12.0))]  # rhythmic sections
    # an onset in the summed stem with no onset in any instrument track within 3 ms is interference
    # between sustained parts (pad / arp / bass beating), not a note: listed separately
    inst = np.concatenate([R.detect_onsets(tracks[k], thresh_db=6.0, floor_db=-80.0, min_gap=0.01)[0]
                           for k in ('kick', 'bass', 'clap', 'snare', 'hats', 'perc', 'arp', 'pad', 'stab', 'keys', 'fx', 'crash')])
    real = np.array([np.min(np.abs(inst - o)) <= ns(0.003) for o in on_mus], dtype=bool)
    spurious = on_mus[~real]
    on_mus = on_mus[real]
    six = MU.BEAT_N // 4
    gd = np.abs(((on_mus + six // 2) % six) - six // 2) / SR
    w(f'  music stem (1.44-12.0 s): {len(on_mus)} detected note onsets (>10 dB); distance to the 16th-note '
      f'grid: median {np.median(gd) * 1000:.2f} ms, 90th pct {np.percentile(gd, 90) * 1000:.2f} ms, '
      f'max {gd.max() * 1000:.2f} ms'
      + (f"  ({len(spurious)} detector hit(s) without an instrument onset ignored: "
         f"{', '.join(f'{v / SR:.3f}s' for v in spurious)})" if len(spurious) else ''))

    # end-aligned cues
    spans = binfo.get('spans', {})
    ea = [(i, c) for i, c in enumerate(cues) if c['type'] in FX.END_ALIGNED and i in spans]
    if ea:
        w('  END-ALIGNED cues (isolated dry render; sound must end ON the cue sample; stop = time from its last')
        w('  -6 dB point re its loudest 1 ms to silence; level re its loudest 10 ms over its last 10 ms):')
        worst = 0.0
        for i, c in ea:
            a, b, iso = spans[i]
            m = np.max(np.abs(iso), axis=0)
            last = int(np.flatnonzero(m > m.max() * 1e-4)[-1])
            dev = (a + last + 1 - ns(c['t'])) / SR
            worst = max(worst, abs(dev))
            e1 = np.sqrt(uniform_filter1d(np.mean(iso ** 2, axis=0), ns(0.001)))
            stop = (last - int(np.flatnonzero(e1 >= e1.max() * 0.5)[-1])) / SR
            e10 = np.sqrt(uniform_filter1d(np.mean(iso ** 2, axis=0), ns(0.01)))
            tail = 20 * np.log10(np.sqrt(np.mean(iso[:, max(last - ns(0.01), 0):last + 1] ** 2)) / e10.max())
            w(f"    {c['t']:6.3f} {c['type']:13s} dur {c.get('dur', 0):.3f}: starts {(a - ns(c['t'])) / SR * 1000:+8.1f} ms, "
              f'ends {dev * 1000:+.2f} ms re cue; stop {stop * 1000:.1f} ms; last 10 ms {tail:+.1f} dB')
        w(f"  end-aligned |dev| max {worst * 1000:.2f} ms -> {'PASS (< 2 ms)' if worst < 0.002 else 'FAIL'}")
    w('')

    # discontinuity / click scan
    w('CLICK / DISCONTINUITY SCAN (2nd-difference outliers vs local level, final mix)')
    d2 = np.diff(mix, n=2, axis=1)
    loc = np.sqrt(uniform_filter1d(d2 ** 2, size=ns(0.02), axis=1, mode='nearest')) + 1e-9
    ratio = np.max(np.abs(d2) / loc, axis=0)
    flagged = np.where(ratio > 14.0)[0]
    known = np.unique(np.concatenate([[ns(c['t']) for c in cues], on_mus, on_sfx, [0, N - 1]]))
    clusters = []
    for s in flagged:
        if not clusters or s - clusters[-1][-1] > ns(0.005):
            clusters.append([s])
        else:
            clusters[-1].append(s)
    unexplained = [c[0] for c in clusters if np.min(np.abs(known - c[0])) > ns(0.004)]
    w(f'  outlier clusters: {len(clusters)}, not at a designed transient: {len(unexplained)}'
      + (f"  at {', '.join(f'{u / SR:.3f}s' for u in unexplained[:12])}" if unexplained else ''))
    w('')

    master_dynamics(timing, minfo, w)
    stereo_report(timing, mix, w)
    low_end_alignment(timing, tracks, kick_trig, sfx, w)

    # spectral balance
    w('SPECTRAL BALANCE (final mix, octave bands, dB rel. loudest band)')
    spec = np.abs(np.fft.rfft(np.mean(mix, axis=0))) ** 2
    fr = np.fft.rfftfreq(N, 1 / SR)
    bands = [16, 31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    e = [np.sum(spec[(fr >= b / np.sqrt(2)) & (fr < b * np.sqrt(2))]) for b in bands]
    e = 10 * np.log10(np.array(e) / max(e))
    w('  ' + '  '.join(f'{b:g}Hz {v:+.1f}' for b, v in zip(bands, e)))
    sub = np.sum(spec[fr < 25]) / np.sum(spec)
    w(f'  energy below 25 Hz: {100 * sub:.2f}% of total')
    lo = zp(mix, 'lowpass', 150.0, 4)
    corr_lo = np.corrcoef(lo[0], lo[1])[0, 1]
    corr = np.corrcoef(mix[0], mix[1])[0, 1]
    w(f'  L/R correlation: full band {corr:.3f}, below 150 Hz {corr_lo:.3f} (1.0 = mono-compatible low end)')
    # narrowband peaks of the long-term spectrum vs its 1/3-octave average: musical notes are
    # expected (F minor chord tones / UI tones); an off-key peak above 2 kHz would be a resonance
    fw, Pw = signal.welch(np.mean(mix, axis=0), fs=SR, nperseg=8192)
    Pd = 10 * np.log10(Pw + 1e-20)
    lf = np.log2(np.maximum(fw, 1.0))
    smooth = np.array([Pd[(lf > l - 1 / 6) & (lf < l + 1 / 6)].mean() for l in lf])
    ex = Pd - smooth
    names = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    for lo, hi in ((150.0, 2000.0), (2000.0, 16000.0)):
        sel = np.where((fw >= lo) & (fw < hi))[0]
        picked = []
        for i in sel[np.argsort(ex[sel])[::-1]]:
            if all(abs(fw[i] - fw[j]) > fw[i] * 0.05 for j in picked):
                picked.append(i)
            if len(picked) == 5:
                break
        desc = []
        for i in picked:
            m = 69 + 12 * np.log2(fw[i] / 440.0)
            k = int(round(m))
            desc.append(f'{fw[i]:.0f} Hz +{ex[i]:.1f} dB ({names[k % 12]}{k // 12 - 1}{(m - k) * 100:+.0f}c)')
        w(f'  strongest narrowband peaks {lo:g}-{hi:g} Hz: ' + ', '.join(desc))
    w('')
    section_spectra(timing, mix, w)
    w('BUILD LOG')
    for s in logs:
        w('  ' + s.strip())

    txt = '\n'.join(L) + '\n'
    open(os.path.join(outdir, 'analysis.txt'), 'w').write(txt)
    print(txt)

    if not fast:
        secs = timing['sections']
        R.spectrogram_png(mix, os.path.join(outdir, 'spectrogram.png'),
                          'Final mix, log-frequency spectrogram (90 dB range); markers: red impact, orange hit, cyan UI, violet whoosh/riser',
                          cues, secs)
        R.spectrogram_png(mix, os.path.join(outdir, 'spectrogram_low.png'),
                          'Final mix, 20-400 Hz detail (nfft 16384): kick / sub / bass cleanliness',
                          cues, secs, fmin=20.0, fmax=400.0, nfft=16384, hop=480, H=600, rng_db=70.0)
        R.waveform_png(os.path.join(outdir, 'waveform.png'), mix, music, sfx, cues, secs)
        R.onset_zoom_png(os.path.join(outdir, 'onsets.png'), sfx, mix, rows)


if __name__ == '__main__':
    main()
