#!/usr/bin/env python3
"""A/V sync + spec report for the final video.

Detects picture cuts (large frame-to-frame changes) and audio transients
(spectral-flux onsets), then lines both up against the cue sheet in
audio/timing.json.

  python3 -I scripts/sync_report.py dist/sol-sniper-reel.mp4
"""
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
video = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'dist/sol-sniper-reel.mp4')

probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', video]))
print('== Spec')
for s in probe['streams']:
    if s['codec_type'] == 'video':
        print(f"video  {s['codec_name']} {s.get('profile')} {s['width']}x{s['height']} {s['r_frame_rate']} {s['pix_fmt']} "
              f"frames={s.get('nb_frames')} dur={s.get('duration')} color={s.get('color_space')}/{s.get('color_transfer')}")
    else:
        print(f"audio  {s['codec_name']} {s['sample_rate']} Hz ch={s['channels']} dur={s.get('duration')} br={s.get('bit_rate')}")
print(f"format dur={probe['format']['duration']} size={int(probe['format']['size']) / 1e6:.1f} MB")

# --- picture cuts
W, H = 108, 192
raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', video, '-vf', f'scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'])
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
diff = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
fps = 30
med = np.median(diff) + 1e-3
cuts = [(i + 1) / fps for i in range(len(diff)) if diff[i] > max(18, 6 * med) and (i == 0 or diff[i] > diff[i - 1]) and (i + 1 >= len(diff) or diff[i] >= diff[i + 1])]

# --- audio onsets (spectral flux)
pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', video, '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'])
a = np.frombuffer(pcm, np.float32)
hop, n = 240, 1024  # 5 ms hop
frames = np.lib.stride_tricks.sliding_window_view(np.pad(a, (n, n)), n)[::hop] * np.hanning(n)
mag = np.abs(np.fft.rfft(frames, axis=1))
flux = np.maximum(0, np.diff(np.log1p(mag * 10), axis=0)).sum(axis=1)
flux = (flux - np.median(flux)) / (np.std(flux) + 1e-9)
onsets = []
for i in range(1, len(flux) - 1):
    if flux[i] > 2.5 and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1]:
        t = (i * hop - n + n / 2) / 48000
        if not onsets or t - onsets[-1] > 0.04:
            onsets.append(t)

timing = json.load(open(os.path.join(ROOT, 'audio/timing.json')))
cues = timing['cues']
print(f'\n== Picture cuts detected: {len(cuts)}')
for c in cuts:
    near_cue = min(cues, key=lambda q: abs(q['t'] - c))
    near_on = min(onsets, key=lambda o: abs(o - c)) if onsets else None
    print(f"cut {c:6.3f}s  nearest cue {near_cue['type']:<13} {near_cue['t']:6.3f} ({(c - near_cue['t']) * 1000:+5.0f} ms)  "
          f"nearest audio onset {near_on:6.3f} ({(c - near_on) * 1000:+5.0f} ms)")
print(f'\n== Hard cues vs audio onsets')
hard = ('impact_big', 'impact_drop', 'impact_outro', 'hit_cut', 'click', 'tick', 'ui_blip', 'success')
errs = []
for q in cues:
    if q['type'] in hard:
        o = min(onsets, key=lambda o: abs(o - q['t'])) if onsets else float('nan')
        errs.append(abs(o - q['t']))
        print(f"{q['type']:<13} cue {q['t']:6.3f}  onset {o:6.3f}  ({(o - q['t']) * 1000:+5.0f} ms)")
if errs:
    print(f'max |onset - cue| = {max(errs) * 1000:.0f} ms, median {np.median(errs) * 1000:.0f} ms')
