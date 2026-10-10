#!/usr/bin/env python3
"""SOL Sniper reel: sound design for the 5 s intro hook, prepended to the finished soundtrack.

  node scripts/export-intro-timing.mjs   # (re)export audio/intro_timing.json from src/intro/timing.js
  python3 audio/build_intro.py           # -> audio/intro.wav + audio/soundtrack_with_intro.wav (+ analysis)

Options:
  --timing PATH   build from this intro timing JSON, used as is (default: audio/intro_timing.json,
                  re-exported first when src/intro/timing.js is newer)
  --body PATH     the finished reel soundtrack to prepend the hook to (default: audio/soundtrack.wav)
  --out DIR       output directory (default: audio/)
  --fast          skip the PNGs
  --no-ffmpeg     skip every ffmpeg step: no AAC delivery guard, no ebur128 report

Writes:
  intro.wav                   48 kHz / 24-bit stereo, exactly 5.000 s (240000 samples)
  soundtrack_with_intro.wav   intro.wav followed by the body, exactly 20.000 s (960000 samples).
                              The body is NEVER decoded or processed: its PCM frames are copied byte
                              for byte, so the last 720000 frames are bit-identical to soundtrack.wav.
  stems/intro_bed.wav         pre-master tension bed (drone)            } one shared gain:
  stems/intro_sfx.wav         pre-master hits / whoosh / riser / suck   } bed + sfx = pre-master mix
  intro_analysis.txt          loudness vs the body's opening, WAV + AAC-delivery peaks of the full
                              20 s file, cue alignment, end-aligned stops, join continuity, stereo, spectra
  intro_spectrogram.png       0-7 s of the joined file (log frequency, cue markers)
  intro_spectrogram_low.png   0-7 s, 20-400 Hz (low-end cleanliness)
  intro_join.png              the cut at 5.000 s: +-40 ms waveform and +-0.6 s envelope

CUE SEMANTICS (intro_timing.json `cues`: {t, type, gain?, dur?}; same rules as build_audio.py)
  t      seconds. Onset cues put their transient ON the sample round(t * 48000); END-ALIGNED cues
         (riser, suck) end on that sample instead (their last sample is the one before it).
  gain   dB offset from the type's default level (sndkit/intro_fx.py LEVELS).
  dur    seconds, for the types marked (dur).

  bass_hit   deep hit from black: sub drop onto F1 + felt low thud + dark attack (no bright crack)
             + a low-mid bloom into a long dark hall.
  tension    (dur) F minor drone bed starting at t: F1 sub (the phase reference for every low layer)
             + dark just-intonation Fm7 pad (F2 C3 | F3 Ab3 C4 Eb4) whose low-pass swells open
             (320 Hz -> 2 kHz) + faint dark air. Breathes with the pulses (sidechain), dips under the
             accents, recedes 5 dB in its last 0.55 s under the riser / suck; its sub is pulled out
             after the last pulse (4.55-4.95 s) so the reel's impact gets the low end to itself.
             Level set by loudness (intro_fx.BED_LUFS), not by its loudest 10 ms.
  accent     felt text punch: tight thump onto F2 + locked sub + short knock + soft tick, into the hall.
  whoosh     (dur) dark push-in whoosh starting at t (sfx.whoosh with a low path, gentle drift).
  pulse      sub heartbeat thump on F1 with a soft felt knock and phone-speaker harmonics. Transient at t.
  riser      (dur) low cinematic riser ENDING AT t: root + fifth + low octave gliding up an octave onto
             F3 / C4 + dark noise climbing to ~2.4 kHz. Full level for its last 25 ms, then a 1.5 ms stop.
  suck       (dur) reverse swell ENDING AT t: reversed dark-hall tail of an Fm9 hit (the reel's first
             chord) + zoom-in whoosh narrowing to the centre. Full level for its last 20 ms, 1.5 ms stop.

MIX / MASTER (intro only; the body is untouched):
  levels: intro_fx.LEVELS / BED_LUFS; hook bus EQ intro_fx.BUS_EQ (broad low-mid dip at 260 Hz).
  pre-master mix -> sndkit/master.py master() (hp 18 Hz, glue comp, soft clip, 4x true-peak limiter at
  TP_CEILING) with the make-up gain iterated to TARGET_LUFS, and the master's end fade set to END_STOP
  (1.5 ms raised cosine reaching 0 on sample 239999): everything in the hook stops dead on the cut and
  the reel's own impact on sample 240000 is the release.
  AAC delivery guard: the JOINED 20 s file is encoded exactly like scripts/encode.py (ffmpeg AAC-LC 320k,
  48 kHz), decoded and measured (4x true-peak meter + ffmpeg ebur128). Where the decoded AAC exceeds
  AAC_TP_TARGET inside the hook, a smooth post-limiter dip is added there and the hook is re-mastered
  (closed loop). Overshoots inside the body cannot be fixed here (the body is not processed): they are
  reported.

Python 3 + numpy + scipy only. No samples, fixed seeds -> bit-identical output on every run (with the
same ffmpeg build for the AAC guard).
"""
import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import wave  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from scipy import signal  # noqa: E402
from scipy.ndimage import convolve1d, maximum_filter1d, uniform_filter1d  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_audio as BA  # noqa: E402  (io + AAC round trip helpers; importing it has no side effects)
from sndkit import intro_fx as IFX  # noqa: E402
from sndkit import master as MS  # noqa: E402
from sndkit import music as MU  # noqa: E402
from sndkit import report as R  # noqa: E402
from sndkit.dsp import SR, add_at, convolve_ir, make_ir, ns, zp  # noqa: E402

N_INTRO = 240000           # 5.000 s
N_BODY = 720000            # 15.000 s
TARGET_LUFS = -14.5        # hook integrated loudness (brief: -15 to -14; the body is -14.0)
TP_CEILING = -2.5          # WAV limiter ceiling (dBTP), as the body
AAC_TP_TARGET = -1.5       # decoded AAC true peak of the joined file (dBTP)
END_STOP = 0.0015          # the hook's hard stop on the cut (s, raised cosine to 0 on the last sample)


# --------------------------------------------------------------------------- io
def _md5(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def wav_frames(path):
    """-> (params, raw PCM frame bytes) without decoding anything."""
    with wave.open(path, 'rb') as w:
        p = w.getparams()
        return p, w.readframes(p.nframes)


def write_joined(path, intro_path, body_path):
    """intro + body at the byte level: the body's PCM frames are copied verbatim."""
    pi, fi = wav_frames(intro_path)
    pb, fb = wav_frames(body_path)
    assert (pi.nchannels, pi.sampwidth, pi.framerate) == (pb.nchannels, pb.sampwidth, pb.framerate), (pi, pb)
    with wave.open(path, 'wb') as w:
        w.setnchannels(pb.nchannels)
        w.setsampwidth(pb.sampwidth)
        w.setframerate(pb.framerate)
        w.writeframes(fi + fb)


def ensure_timing(log, path=None):
    if path:
        log(f'timing: {path} (as given, no re-export)')
        return _load_json(path)
    src = os.path.join(ROOT, 'src', 'intro', 'timing.js')
    dst = os.path.join(HERE, 'intro_timing.json')
    if os.path.exists(src) and (not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)):
        if shutil.which('node'):
            log('src/intro/timing.js is newer than audio/intro_timing.json -> re-exporting')
            subprocess.run(['node', os.path.join(ROOT, 'scripts', 'export-intro-timing.mjs')], check=True, cwd=ROOT)
        else:
            log('WARNING: src/intro/timing.js is newer than audio/intro_timing.json and node is not available')
    return _load_json(dst)


# --------------------------------------------------------------------------- build
def build(timing, log):
    """-> (bed, sfx, info): pre-master stereo buses (N_INTRO samples) and per-cue renders."""
    N = ns(timing['duration'])
    assert N == N_INTRO, N
    assert timing['bpm'] == 125
    t0 = time.time()
    ir_hall = make_ir(4.0, 3.0, 1.3, seed=41, predelay=0.022, hp_f=140.0, lp_f=5200.0, er_span=0.05)
    ir_room = make_ir(0.7, 0.45, 0.28, seed=42, predelay=0.005, hp_f=250.0, lp_f=8000.0, er_span=0.02)
    ir_suck = make_ir(2.8, 2.4, 1.2, seed=43, predelay=0.0, hp_f=180.0, lp_f=6000.0)
    log(f'  IRs {time.time() - t0:.1f}s')
    cues = timing['cues']
    ctx = dict(chord=MU.CHORDS['Fm9']['pad'], ir_suck=ir_suck,
               pulse_samples=[ns(c['t']) for c in cues if c['type'] == 'pulse'],
               accent_samples=[ns(c['t']) for c in cues if c['type'] == 'accent'])
    t0 = time.time()
    bed = np.zeros((2, N))
    dry = np.zeros((2, N))
    buses = {k: np.zeros((2, N)) for k in ('hall', 'room')}
    per_cue = {}   # idx -> (dry render placed in the hook, wet feeds placed)
    for i, cue in enumerate(cues):
        lay = IFX.render_cue(cue, i, ctx)
        s = ns(cue['t'])
        cd = np.zeros((2, N))
        cw = {k: np.zeros((2, N)) for k in buses}
        for sig, off, sends in lay:
            add_at(cd, sig * sends.get('_dry', 1.0), s + off)
            for bus, g in sends.items():
                if bus != '_dry':
                    add_at(cw[bus], sig * g, s + off)
        if cue['type'] in IFX.BED_TYPES:
            # the bed is set by loudness over its sustained stretch, not by its loudest 10 ms
            g = 10.0 ** ((IFX.BED_LUFS - MS.segment_lufs(cd, 1.3, 4.2)) / 20.0)
            cd *= g
            cw = {k: v * g for k, v in cw.items()}
            bed += cd
        else:
            dry += cd
        for k in buses:
            buses[k] += cw[k]
        per_cue[i] = (cd, cw)
    rev = {'hall': convolve_ir(buses['hall'], ir_hall) * 0.9, 'room': convolve_ir(buses['room'], ir_room)}
    # reverb returns go with the SFX bus (the bed's small hall send included)
    sfx = dry + rev['hall'] + rev['room']
    bed, sfx = IFX.bus_eq(bed), IFX.bus_eq(sfx)  # linear: bed + sfx is still the pre-master mix
    # per-cue reverb (for the isolated transient stem used by the onset check)
    iso_rev = {}
    for i, (cd, cw) in per_cue.items():
        if cues[i]['type'] in IFX.TRANSIENT_TYPES:
            iso_rev[i] = convolve_ir(cw['hall'], ir_hall) * 0.9 + convolve_ir(cw['room'], ir_room)
    log(f'  render {time.time() - t0:.1f}s')
    return bed, sfx, dict(per_cue=per_cue, iso_rev=iso_rev)


def master_for_delivery(pre, body_path, log, use_ffmpeg):
    """Master the hook; then encode the JOINED file (hook + untouched body) like scripts/encode.py and
    dip the hook (post-limiter, smooth) wherever its decoded AAC true peak exceeds AAC_TP_TARGET;
    re-master until it passes (closed loop, as build_audio.master_for_delivery).
    -> (master, master info, aac info or None)."""
    n = pre.shape[1]
    guard = np.zeros(n)
    g_db = 4.0
    aac = None
    ffmpeg_ok = use_ffmpeg and shutil.which('ffmpeg') is not None
    if use_ffmpeg and not ffmpeg_ok:
        log('WARNING: ffmpeg not found: AAC delivery guard skipped (WAV ceiling only)')
    win = np.hanning(ns(0.01) + 1)
    win /= win.sum()
    with tempfile.TemporaryDirectory() as td:
        for rnd in range(10):
            out, minfo = MS.master(pre, TARGET_LUFS, TP_CEILING, END_STOP, log=log,
                                   guard_db=guard if guard.any() else None, g_db=g_db)
            g_db = minfo['gain_db']
            if not ffmpeg_ok:
                break
            p_i, p_j = os.path.join(td, 'intro.wav'), os.path.join(td, 'joined.wav')
            BA.write_wav24(p_i, out)
            write_joined(p_j, p_i, body_path)
            dec, ff, _ = BA.aac_roundtrip(p_j, td)
            env = MS._tp_envelope(dec)[:n + N_BODY]
            tp_hook = float(20 * np.log10(env[:n].max()))
            tp_body = float(20 * np.log10(env[n:].max()))
            tp = max(tp_hook, tp_body, ff['TP'] if ff and ff['TP'] is not None else -np.inf)
            ok = tp <= AAC_TP_TARGET
            aac = dict(tp_hook=tp_hook, tp_body=tp_body, t_hook=int(np.argmax(env[:n])) / SR,
                       t_body=(n + int(np.argmax(env[n:]))) / SR, ff=ff, rounds=rnd + 1, ok=ok)
            log(f'  AAC guard pass {rnd}: joined file decoded true peak: hook {tp_hook:.2f} dBTP, body {tp_body:.2f} '
                f'dBTP (ebur128 {ff["TP"]} dBFS), I {ff["I"]} LUFS -> {"OK" if ok else "over " + f"{AAC_TP_TARGET:.1f}"}')
            if ok:
                break
            if tp_hook <= AAC_TP_TARGET:
                log('WARNING: the AAC overshoot is inside the body, which this script must not process')
                break
            need = np.maximum(20 * np.log10(np.maximum(env[:n], 1e-9)) - (AAC_TP_TARGET - 0.15), 0.0)
            need = maximum_filter1d(need, size=2 * 2048 + 1, mode='nearest')
            guard += convolve1d(need, win, mode='nearest')
    minfo['guard_db'] = guard
    return out, minfo, aac


# --------------------------------------------------------------------------- analysis
def _rms_db(x, a, b):
    return 20 * np.log10(np.sqrt(np.mean(x[:, a:b] ** 2)) + 1e-12)


def detect_low(x, thresh_db=6.0, floor_db=-75.0, min_gap=0.02):
    """Onsets in the low band only (< 250 Hz): the sub pulses under the riser."""
    lo = zp(np.mean(np.atleast_2d(x), axis=0), 'lowpass', 250.0, 4)
    return R.detect_onsets(lo, thresh_db=thresh_db, floor_db=floor_db, min_gap=min_gap, hp_f=25.0)[0]


def join_png(path, full, n0):
    W, H = 1800, 620
    im = Image.new('RGB', (W, H), (250, 250, 252))
    d = ImageDraw.Draw(im)
    f13, f11 = R._font(13), R._font(11)
    d.text((20, 10), 'The cut at 5.000 s (sample 240000): hook (left of the red line) -> reel (right). '
                     'Top: +-40 ms waveform (L dark, R light). Bottom: +-0.6 s, 5 ms RMS in dBFS.',
           fill=(20, 20, 30), font=R._font(15))
    ml, pw = 60, W - 80
    # top: +-40 ms samples
    a, b = n0 - ns(0.04), n0 + ns(0.04)
    y0, ph = 40, 300
    d.rectangle([ml, y0, ml + pw, y0 + ph], outline=(215, 215, 222), fill=(255, 255, 255))
    pk = np.max(np.abs(full[:, a:b])) + 1e-9
    xs = ml + (np.arange(b - a) / (b - a - 1)) * pw
    for c, col in ((1, (160, 170, 220)), (0, (40, 50, 110))):
        ys = y0 + ph / 2 - full[c, a:b] / pk * (ph / 2 - 10)
        d.line(list(zip(xs.tolist(), ys.tolist())), fill=col, width=1)
    xc = ml + (n0 - a) / (b - a - 1) * pw
    d.line([(xc, y0), (xc, y0 + ph)], fill=(220, 40, 40), width=1)
    for ms in (-40, -20, -10, 0, 10, 20, 40):
        xx = ml + (ns(ms / 1000) + n0 - a) / (b - a - 1) * pw
        d.text((xx - 10, y0 + ph + 4), f'{ms:+d} ms', fill=(80, 80, 90), font=f11)
    d.text((ml + 6, y0 + 4), f'peak {20 * np.log10(pk):.1f} dBFS', fill=(20, 20, 30), font=f13)
    # bottom: +-0.6 s envelope
    a, b = n0 - ns(0.6), n0 + ns(0.6)
    y0, ph = 360, 220
    d.rectangle([ml, y0, ml + pw, y0 + ph], outline=(215, 215, 222), fill=(255, 255, 255))
    e = np.sqrt(uniform_filter1d(np.mean(full[:, a:b] ** 2, axis=0), ns(0.005)))
    edb = 20 * np.log10(e + 1e-9)
    lo_db = -60.0
    xs = ml + (np.arange(b - a) / (b - a - 1)) * pw
    ys = y0 + np.clip(-edb / -lo_db, 0, 1) * ph
    step = 40
    d.line(list(zip(xs[::step].tolist(), ys[::step].tolist())), fill=(40, 50, 110), width=2)
    for lv in (-10, -20, -30, -40, -50):
        yy = y0 + (-lv / -lo_db) * ph
        d.line([(ml, yy), (ml + pw, yy)], fill=(230, 230, 236))
        d.text((8, yy - 7), f'{lv} dB', fill=(90, 90, 100), font=f11)
    xc = ml + (n0 - a) / (b - a - 1) * pw
    d.line([(xc, y0), (xc, y0 + ph)], fill=(220, 40, 40), width=1)
    for s in (-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6):
        xx = ml + (ns(s) + n0 - a) / (b - a - 1) * pw
        d.text((xx - 12, y0 + ph + 4), f'{5 + s:.1f}s', fill=(80, 80, 90), font=f11)
    im.save(path)


def analyse(timing, body_timing, paths, bed, sfx, info, minfo, aac, use_ffmpeg, fast, logs, outdir):
    L = []
    w = L.append
    cues = timing['cues']
    hook, ii = BA.read_wav24(paths['intro'])
    full, fi = BA.read_wav24(paths['full'])
    body, _ = BA.read_wav24(paths['body'])
    n0 = hook.shape[1]
    w('SOL Sniper reel: 5 s intro hook analysis (generated by audio/build_intro.py)')
    w('=' * 78)
    w('FILES')
    for name, inf, want in (('intro', ii, N_INTRO), ('full', fi, N_INTRO + N_BODY)):
        ok = inf['frames'] == want and inf['rate'] == 48000 and inf['channels'] == 2 and inf['sampwidth'] == 3
        w(f"  {os.path.relpath(paths[name], ROOT)}: {inf['rate']} Hz, {inf['channels']} ch, {8 * inf['sampwidth']}-bit PCM, "
          f"{inf['frames']} samples = {inf['frames'] / inf['rate']:.6f} s (want {want}) -> {'OK' if ok else 'FAIL'}")
    _, fb = wav_frames(paths['body'])
    _, ff_ = wav_frames(paths['full'])
    _, fh = wav_frames(paths['intro'])
    bw = 2 * 3
    same = ff_[N_INTRO * bw:] == fb and ff_[:N_INTRO * bw] == fh
    w(f"  body: frames {N_INTRO}-{N_INTRO + N_BODY - 1} of the joined file vs {os.path.relpath(paths['body'], ROOT)}: "
      f"{'BIT-IDENTICAL' if ff_[N_INTRO * bw:] == fb else 'DIFFERENT'} (md5 of PCM {hashlib.md5(ff_[N_INTRO * bw:]).hexdigest()} vs "
      f"{hashlib.md5(fb).hexdigest()}); frames 0-{N_INTRO - 1} = intro.wav: {'yes' if ff_[:N_INTRO * bw] == fh else 'NO'} -> "
      f"{'OK' if same else 'FAIL'}")
    w(f"  md5 of the files: soundtrack.wav {_md5(paths['body'])}, intro.wav {_md5(paths['intro'])}, "
      f"soundtrack_with_intro.wav {_md5(paths['full'])}")
    w('')

    # loudness
    w('LOUDNESS / PEAK')
    li, lf, lb = MS.integrated_lufs(hook), MS.integrated_lufs(full), MS.integrated_lufs(body)
    w(f'  intro.wav integrated (own BS.1770-4): {li:.2f} LUFS (target {TARGET_LUFS:.1f}, brief -15..-14) -> '
      f"{'OK' if -15.0 <= li <= -14.0 else 'CHECK'}")
    w(f'  joined 20 s integrated:               {lf:.2f} LUFS (brief ~-14) -> {"OK" if abs(lf + 14.0) <= 0.3 else "CHECK"}')
    w(f'  body (reference) integrated {lb:.2f} LUFS, its first 5 s {MS.integrated_lufs(body[:, :N_INTRO]):.2f} LUFS')
    tmh, lmh = MS.momentary(hook)
    tmb, lmb = MS.momentary(body)
    open_sel = tmb - 0.2 < 1.44
    w(f'  momentary (400 ms) max: hook {lmh.max():.1f} LUFS @ {tmh[np.argmax(lmh)] - 0.2:.2f}s vs body opening (title) '
      f'{lmb[open_sel].max():.1f} LUFS @ {tmb[open_sel][np.argmax(lmb[open_sel])] - 0.2:.2f}s '
      f"({lmh.max() - lmb[open_sel].max():+.1f} LU; want <= 0, 'as strong, not louder') -> "
      f"{'OK' if lmh.max() <= lmb[open_sel].max() + 0.05 else 'CHECK'}")
    _, lsh = MS.short_term(hook)
    tsb, lsb = MS.short_term(body)
    w(f'  short-term (3 s) max: hook {lsh.max():.1f} LUFS vs body over its first 5 s {lsb[tsb <= 5.0].max():.1f} LUFS')
    w(f'  loudness range: hook {MS.loudness_range(hook):.1f} LU, joined {MS.loudness_range(full):.1f} LU')
    tph, tpf = MS.true_peak(hook), MS.true_peak(full)
    w(f'  true peak (4x): intro.wav {tph:.2f} dBTP, joined {tpf:.2f} dBTP; sample peak intro '
      f'{20 * np.log10(np.max(np.abs(hook))):.2f} dBFS; samples at full scale: {int(np.sum(np.abs(hook) >= 0.9999))}')
    if use_ffmpeg and shutil.which('ffmpeg'):
        for name in ('intro', 'full'):
            e = BA.ffmpeg_ebur128(paths[name])
            w(f"  ffmpeg ebur128 ({os.path.basename(paths[name])}): I = {e['I']} LUFS, LRA = {e['LRA']} LU, "
              f"true peak = {e['TP']} dBFS")
    lg = minfo['limiter_gain']
    gr = -20 * np.log10(np.maximum(lg, 1e-12))
    w(f"  hook master: make-up gain {minfo['gain_db']:+.2f} dB, glue comp max GR {minfo['glue_gr_db']:.2f} dB, "
      f"limiter max GR {gr.max():.2f} dB at {np.argmax(gr) / SR:.3f}s, WAV ceiling {TP_CEILING:.1f} dBTP")
    dc = np.mean(hook, axis=1)
    w(f'  DC offset (hook): L {dc[0]:+.2e}  R {dc[1]:+.2e}')
    w('')

    w('AAC DELIVERY (joined 20 s file encoded like scripts/encode.py: ffmpeg AAC-LC 320k, 48 kHz, muxed in an MP4)')
    if use_ffmpeg and shutil.which('ffmpeg'):
        with tempfile.TemporaryDirectory() as td:
            dec, fm, md5_mp4 = BA.aac_roundtrip(paths['full'], td, mux=True)
            _, _, md5_m4a = BA.aac_roundtrip(paths['full'], td, mux=False)
        env = MS._tp_envelope(dec)[:full.shape[1]]
        th, tb = 20 * np.log10(env[:n0].max()), 20 * np.log10(env[n0:].max())
        ok = fm['TP'] is not None and fm['TP'] <= AAC_TP_TARGET and max(th, tb) <= AAC_TP_TARGET
        w(f"  MP4 replica, ffmpeg ebur128 (peak=true): I = {fm['I']} LUFS, true peak = {fm['TP']} dBTP "
          f"(want <= {AAC_TP_TARGET:.1f}) -> {'OK' if ok else 'FAIL'}")
        w(f'  decoded AAC, own 4x meter: hook {th:.2f} dBTP @ {np.argmax(env[:n0]) / SR:.3f}s, body {tb:.2f} dBTP @ '
          f'{(n0 + np.argmax(env[n0:])) / SR:.3f}s; integrated {MS.integrated_lufs(dec[:, :full.shape[1]]):.2f} LUFS')
        w(f'  WAV -> AAC overshoot: hook {th - tph:+.2f} dB; MP4 audio bit-identical to the audio-only encode the '
          f"guard measures: {'yes' if md5_mp4 == md5_m4a else 'NO'}")
        g = minfo.get('guard_db')
        if aac:
            w(f"  delivery guard: {aac['rounds']} master pass(es); "
              + ('dips: ' + f'max {g.max():.2f} dB at {np.argmax(g) / SR:.3f}s' if g is not None and g.max() > 0.005
                 else 'no dips needed'))
    else:
        w('  skipped (--no-ffmpeg or no ffmpeg): the AAC delivery true peak is NOT verified')
    w('')

    # energy curve
    secs = timing['sections']
    w('ENERGY CURVE (momentary 400 ms loudness of the joined file; t = window centre; hook sections use only windows'
      ' that end by 5.000 s)')
    tm, lm = MS.momentary(full)
    tc = tm - 0.2
    for name, s in secs.items():
        sel = (tc >= s['start']) & (tc < s['end']) & (tm <= 5.0 + 1e-9)  # hook-only windows (none across the cut)
        w(f"  {name:8s} {s['start']:4.2f}-{s['end']:4.2f}s  max {lm[sel].max():6.1f} LUFS @ {tc[sel][np.argmax(lm[sel])]:4.2f}s"
          f"   median {np.median(lm[sel]):6.1f}   ungated {MS.segment_lufs(full, s['start'], s['end']):6.1f}")
    pre_cut = tm <= 5.0 + 1e-9
    into = lm[pre_cut & (tm >= 4.0)]
    post = lm[(tm >= 5.4 - 1e-9) & (tm <= 5.8)]  # reel-only windows (start at or after the cut)
    w(f'  into the cut (windows ending <= 5.000): max {into.max():.1f} LUFS, last {lm[pre_cut][-1]:.1f} LUFS; reel impact '
      f'(windows 5.0-5.8 s) max {post.max():.1f} LUFS -> the release is {post.max() - into.max():+.1f} LU '
      f"(want >= +1.0) -> {'OK' if post.max() - into.max() >= 1.0 else 'CHECK'}")
    rise = [MS.segment_lufs(full, a, a + 0.4) for a in (3.4, 3.8, 4.2, 4.6)]
    w('  build-up, ungated 400 ms blocks 3.4-5.0 s: ' + ' -> '.join(f'{v:.1f}' for v in rise)
      + f" LUFS ({'rising' if all(np.diff(rise) > 0) else 'NOT monotonic'})")
    ph = zp(zp(full, 'highpass', 300.0, 4), 'lowpass', 12000.0, 2)
    w('  phone-speaker sim (HP 300 Hz / LP 12 kHz), ungated: ' + '  '.join(
        f"{nm} {MS.segment_lufs(ph, s['start'], s['end']):.1f}" for nm, s in secs.items())
      + f"   | reel title {MS.segment_lufs(ph, 5.0, 6.44):.1f}")
    w('')

    # cue alignment
    w('CUE ALIGNMENT (blind energy-ratio onset detector, sample resolution; deviation = detected - cue)')
    trans = [(i, c) for i, c in enumerate(cues) if c['type'] in IFX.TRANSIENT_TYPES]
    stem = np.zeros_like(hook)
    for i, _ in trans:
        stem += info['per_cue'][i][0] + info['iso_rev'][i]
    on_stem, _ = R.detect_onsets(stem, thresh_db=8.0, floor_db=-80.0)
    on_stem_lo = detect_low(stem)
    on_mix_b, _ = R.detect_onsets(hook, thresh_db=6.0, floor_db=-60.0, min_gap=0.006)
    on_mix_h, _ = R.detect_onsets(hook, thresh_db=6.0, floor_db=-66.0, hp_f=2500.0, min_gap=0.006)
    on_mix_l = detect_low(hook)
    on_mix = np.unique(np.concatenate([on_mix_b, on_mix_h]))
    w('  stem = the transient cues alone (dry + their reverb); mix = intro.wav as written. Detectors: broadband '
      '(HP 120 Hz) and low band (< 250 Hz, for the sub pulses)')
    w('  t (s)    type        gain   stem dev (ms)  stem low (ms)   mix dev (ms)   mix low (ms)')
    worst_stem, worst_mix = 0.0, 0.0
    f = lambda d: f'{d * 1000:+9.2f}' if d is not None else '      n/a'
    for i, c in trans:
        ds, dsl = R.match(on_stem, c['t']), R.match(on_stem_lo, c['t'])
        dm, dml = R.match(on_mix, c['t']), R.match(on_mix_l, c['t'])
        best_s = min([abs(v) for v in (ds, dsl) if v is not None], default=np.inf)
        best_m = min([abs(v) for v in (dm, dml) if v is not None], default=np.inf)
        worst_stem, worst_mix = max(worst_stem, best_s), max(worst_mix, best_m)
        w(f"  {c['t']:6.3f}   {c['type']:10s} {c.get('gain', 0):+4.0f}   {f(ds)}      {f(dsl)}      {f(dm)}      {f(dml)}")
    w(f"  bass_hit / accent / pulse: max |dev| (best detector) stem {worst_stem * 1000:.2f} ms, mix {worst_mix * 1000:.2f} ms "
      f"-> {'PASS (< 2 ms)' if worst_stem < 0.002 and worst_mix < 0.002 else 'FAIL'}")
    # end-aligned
    w('  END-ALIGNED cues (isolated dry render as placed in the hook; must end ON the cue sample = the cut):')
    worst = 0.0
    for i, c in enumerate(cues):
        if c['type'] not in IFX.END_ALIGNED:
            continue
        iso = info['per_cue'][i][0]
        m = np.max(np.abs(iso), axis=0)
        nz = np.flatnonzero(m > m.max() * 1e-4)
        a, last = int(nz[0]), int(nz[-1])
        dev = (last + 1 - ns(c['t'])) / SR
        worst = max(worst, abs(dev))
        e1 = np.sqrt(uniform_filter1d(np.mean(iso ** 2, axis=0), ns(0.001)))
        stop = (last - int(np.flatnonzero(e1 >= e1.max() * 0.5)[-1])) / SR
        e20 = np.sqrt(uniform_filter1d(np.mean(iso ** 2, axis=0), ns(0.02)))
        tail = _rms_db(iso, last + 1 - ns(0.02), last + 1) - 20 * np.log10(e20.max())
        w(f"    {c['t']:6.3f} {c['type']:6s} dur {c.get('dur', 0):.3f}: starts {a / SR:.3f}s ({(a - ns(c['t'])) / SR * 1000:+.1f} ms), "
          f"last sample {last} -> ends {dev * 1000:+.3f} ms re cue; last 20 ms {tail:+.1f} dB re its loudest 20 ms; "
          f'stop (-6 dB -> silence) {stop * 1000:.1f} ms')
    w(f"  end-aligned |dev| max {worst * 1000:.3f} ms -> {'PASS' if worst < 0.002 else 'FAIL'}")
    w('')

    # join
    w('JOIN AT 5.000 s (sample 240000; hook -> reel)')
    w(f'  hook last samples  L {hook[0, -3]:+.5f} {hook[0, -2]:+.5f} {hook[0, -1]:+.5f}   R {hook[1, -3]:+.5f} {hook[1, -2]:+.5f} {hook[1, -1]:+.5f}')
    w(f'  body first samples L {body[0, 0]:+.5f} {body[0, 1]:+.5f} {body[0, 2]:+.5f}   R {body[1, 0]:+.5f} {body[1, 1]:+.5f} {body[1, 2]:+.5f}')
    d1 = np.abs(np.diff(full, axis=1))
    step = float(d1[:, n0 - 1].max())
    w(f'  step across the join |x[240000] - x[239999]|: {step:.5f} ({20 * np.log10(step + 1e-12):.1f} dBFS); '
      f'max |first difference| in the hook\'s last 50 ms {d1[:, n0 - ns(0.05):n0 - 1].max():.5f}, in the reel\'s first 10 ms '
      f'{d1[:, n0:n0 + ns(0.01)].max():.5f}')
    d2 = np.abs(np.diff(full, n=2, axis=1))
    loc = np.sqrt(uniform_filter1d(d2 ** 2, size=ns(0.02), axis=1, mode='nearest')) + 1e-9
    ratio = np.max(d2 / loc, axis=0)
    jr = float(ratio[n0 - ns(0.002):n0 + 2].max())
    w(f'  2nd-difference outlier ratio (build_audio click metric, > 14 = click) within 2 ms before the join: {jr:.1f} '
      f"-> {'OK' if jr <= 14.0 else 'CHECK'}")
    hk = zp(hook, 'highpass', 200.0, 4)  # the riser / suck band (leaves out the sub pulses)
    pk20 = max(_rms_db(hk, a, a + ns(0.02)) for a in range(n0 - ns(0.3), n0 - ns(0.02) + 1, ns(0.0025)))
    l20 = _rms_db(hk, n0 - ns(0.02), n0 - ns(0.0015))
    w(f'  hook above 200 Hz: RMS of its last 20 ms (before the 1.5 ms stop) {l20:.1f} dBFS vs its loudest 20 ms in the last '
      f"0.3 s {pk20:.1f} dBFS ({l20 - pk20:+.1f} dB; want >= -1.0: riser/suck at their peak on the cut) -> "
      f"{'OK' if l20 - pk20 >= -1.0 else 'CHECK'}")
    pk_h = 20 * np.log10(np.max(np.abs(hook[:, n0 - ns(0.1):])))
    pk_b = 20 * np.log10(np.max(np.abs(body[:, :ns(0.1)])))
    w(f'  sample peak, last 100 ms of the hook {pk_h:.1f} dBFS -> first 100 ms of the reel {pk_b:.1f} dBFS '
      f'({pk_b - pk_h:+.1f} dB: the impact transient lands well above the riser peak)')
    k = [MS.segment_lufs(hook, a, a + 0.1) for a in np.arange(4.2, 5.0 - 1e-9, 0.1)]
    w('  hook loudness in 100 ms blocks 4.2-5.0 s (pulses at 4.53): ' + ' '.join(f'{v:.1f}' for v in k)
      + f" LUFS; reel's first 100 ms {MS.segment_lufs(body, 0.0, 0.1):.1f} LUFS")
    lo = zp(full, 'lowpass', 120.0, 4)
    w(f'  below 120 Hz (the low-end vacuum before the reel impact): 4.30-4.50s {_rms_db(lo, ns(4.3), ns(4.5)):.1f}, '
      f'4.80-4.98s {_rms_db(lo, ns(4.8), ns(4.98)):.1f}, reel 5.00-5.20s {_rms_db(lo, n0, n0 + ns(0.2)):.1f} dBFS RMS')
    w(f"  the reel's first 50 ms in the joined file: RMS {_rms_db(full, n0, n0 + ns(0.05)):.1f} dBFS (identical samples to "
      f"soundtrack.wav: {'yes' if np.array_equal(full[:, n0:], body) else 'NO'})")
    w('')

    # stereo
    w('STEREO / MONO COMPATIBILITY (hook)')
    for name, s in secs.items():
        a, b = ns(s['start']), ns(s['end'])
        L_, R_ = hook[0, a:b], hook[1, a:b]
        M = 0.5 * (L_ + R_)
        loss = 10 * np.log10(np.mean(M ** 2) / (0.5 * (np.mean(L_ ** 2) + np.mean(R_ ** 2))))
        w(f"  {name:8s} L/R corr {np.corrcoef(L_, R_)[0, 1]:+.2f}, mono sum vs stereo {loss:+.2f} dB")
    W, H = ns(0.1), ns(0.05)
    cs = sorted((np.corrcoef(hook[0, i:i + W], hook[1, i:i + W])[0, 1], i / SR) for i in range(0, n0 - W, H))
    w('  lowest 100 ms L/R correlation: ' + ', '.join(f'{c:+.2f}@{t:.2f}s' for c, t in cs[:4])
      + f" (want >= +0.3, as the reel) -> {'OK' if cs[0][0] >= 0.3 else 'CHECK'}")
    lo_h = zp(hook, 'lowpass', 150.0, 4)
    w(f'  L/R correlation below 150 Hz: {np.corrcoef(lo_h[0], lo_h[1])[0, 1]:.3f} (1.0 = mono low end)')
    w('')

    # spectra
    w('SECTION SPECTRA (% of section energy, mono sum; reel title for reference)')
    rows = list(secs.items()) + [('reel 0-1.44', dict(start=5.0, end=6.44))]
    for name, s in rows:
        seg = np.mean(full[:, ns(s['start']):ns(s['end'])], axis=0)
        F = np.abs(np.fft.rfft(seg)) ** 2
        fr = np.fft.rfftfreq(len(seg), 1 / SR)
        def e(lo_, hi_, F=F, fr=fr):
            return 100.0 * F[(fr >= lo_) & (fr < hi_)].sum() / F[(fr >= 20) & (fr < 20000)].sum()

        w(f"  {name:11s} <30 Hz {e(20, 30):5.1f}  30-80 {e(30, 80):5.1f}  80-200 {e(80, 200):5.1f}  200-400 {e(200, 400):5.1f}  "
          f"400-900 {e(400, 900):5.1f}  0.9-2k {e(900, 2000):5.2f}  2-5k {e(2000, 5000):5.2f}  5-10k {e(5000, 10000):5.2f}  "
          f"10-20k {e(10000, 20000):5.3f}")
    spec = np.abs(np.fft.rfft(np.mean(hook, axis=0))) ** 2
    fr = np.fft.rfftfreq(hook.shape[1], 1 / SR)
    bands = [16, 31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    e = [np.sum(spec[(fr >= b / np.sqrt(2)) & (fr < b * np.sqrt(2))]) for b in bands]
    e = 10 * np.log10(np.array(e) / max(e))
    w('  hook octave bands (dB re loudest): ' + '  '.join(f'{b:g}Hz {v:+.1f}' for b, v in zip(bands, e)))
    w(f'  hook energy below 25 Hz: {100 * np.sum(spec[fr < 25]) / np.sum(spec):.2f}% of total')
    fw, Pw = signal.welch(np.mean(hook, axis=0), fs=SR, nperseg=8192)
    Pd = 10 * np.log10(Pw + 1e-20)
    lf = np.log2(np.maximum(fw, 1.0))
    smooth = np.array([Pd[(lf > v - 1 / 6) & (lf < v + 1 / 6)].mean() for v in lf])
    ex = Pd - smooth
    names = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    for lo_, hi_ in ((30.0, 400.0), (400.0, 4000.0), (4000.0, 16000.0)):
        sel = np.where((fw >= lo_) & (fw < hi_))[0]
        picked = []
        for k in sel[np.argsort(ex[sel])[::-1]]:
            if all(abs(fw[k] - fw[j]) > fw[k] * 0.05 for j in picked):
                picked.append(k)
            if len(picked) == 4:
                break
        desc = []
        for k in picked:
            m = 69 + 12 * np.log2(fw[k] / 440.0)
            q = round(m)
            desc.append(f'{fw[k]:.0f} Hz +{ex[k]:.1f} dB ({names[q % 12]}{q // 12 - 1}{(m - q) * 100:+.0f}c)')
        w(f'  strongest narrowband peaks {lo_:g}-{hi_:g} Hz: ' + ', '.join(desc))
    w('')
    w('BUILD LOG')
    for s in logs:
        w('  ' + s.strip())
    txt = '\n'.join(L) + '\n'
    with open(os.path.join(outdir, 'intro_analysis.txt'), 'w') as f:
        f.write(txt)
    print(txt)

    if not fast:
        span = full[:, :ns(7.0)]
        pc = [dict(c) for c in cues if c['type'] != 'tension']
        pc += [dict(c, t=c['t'] + 5.0) for c in body_timing.get('cues', []) if c['t'] < 2.0]
        sec = dict(secs)
        sec['reel'] = dict(start=5.0, end=7.0)
        R.spectrogram_png(span, os.path.join(outdir, 'intro_spectrogram.png'),
                          'Hook (0-5 s) + reel (5-7 s), log-frequency spectrogram (90 dB range); markers: cues',
                          pc, sec)
        R.spectrogram_png(span, os.path.join(outdir, 'intro_spectrogram_low.png'),
                          'Hook (0-5 s) + reel (5-7 s), 20-400 Hz detail (nfft 16384): sub / drone / pulses / vacuum',
                          pc, sec, fmin=20.0, fmax=400.0, nfft=16384, hop=480, H=600, rng_db=70.0)
        join_png(os.path.join(outdir, 'intro_join.png'), full, n0)


def main():
    ap = argparse.ArgumentParser(description='Build the intro hook and prepend it to the reel (see the docstring).')
    ap.add_argument('--timing', default=None, help='intro timing JSON, used as is')
    ap.add_argument('--body', default=os.path.join(HERE, 'soundtrack.wav'), help='finished reel soundtrack')
    ap.add_argument('--out', default=HERE, help='output directory (default: audio/)')
    ap.add_argument('--fast', action='store_true', help='skip the PNGs')
    ap.add_argument('--no-ffmpeg', action='store_true', help='skip ffmpeg (no AAC guard / ebur128)')
    args = ap.parse_args()
    use_ffmpeg = not args.no_ffmpeg
    outdir = os.path.abspath(args.out)
    body_path = os.path.abspath(args.body)
    T0 = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)

    timing = ensure_timing(log, args.timing)
    pb, _ = wav_frames(body_path)
    assert (pb.nchannels, pb.sampwidth, pb.framerate, pb.nframes) == (2, 3, SR, N_BODY), pb
    body_md5 = _md5(body_path)
    log(f'body: {os.path.relpath(body_path, ROOT)} md5 {body_md5} (read only, never processed)')
    log('building the hook')
    bed, sfx, info = build(timing, log)
    pre = bed + sfx
    g0 = 10.0 ** ((-18.0 - MS.integrated_lufs(pre)) / 20.0)
    pk = max(np.max(np.abs(bed)), np.max(np.abs(sfx))) * g0
    stem_gain = g0 * min(1.0, 10.0 ** (-1.0 / 20.0) / pk)
    log('mastering the hook (+ AAC delivery guard on the joined file)')
    out, minfo, aac = master_for_delivery(pre * g0, body_path, log, use_ffmpeg)

    os.makedirs(os.path.join(outdir, 'stems'), exist_ok=True)
    paths = dict(intro=os.path.join(outdir, 'intro.wav'), full=os.path.join(outdir, 'soundtrack_with_intro.wav'),
                 body=body_path)
    BA.write_wav24(paths['intro'], out)
    write_joined(paths['full'], paths['intro'], body_path)
    BA.write_wav24(os.path.join(outdir, 'stems', 'intro_bed.wav'), bed * stem_gain)
    BA.write_wav24(os.path.join(outdir, 'stems', 'intro_sfx.wav'), sfx * stem_gain)
    assert _md5(body_path) == body_md5, 'the body changed while building'
    log(f"wrote {os.path.relpath(paths['intro'], ROOT)} and {os.path.relpath(paths['full'], ROOT)}  "
        f"({time.time() - T0:.1f}s)")
    bt = os.path.join(HERE, 'timing.json')
    body_timing = _load_json(bt) if os.path.exists(bt) else {}
    analyse(timing, body_timing, paths, bed * stem_gain, sfx * stem_gain, info, minfo, aac, use_ffmpeg, args.fast,
            logs, outdir)
    log(f'done in {time.time() - T0:.1f}s')


if __name__ == '__main__':
    main()
