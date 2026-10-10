#!/usr/bin/env python3
"""Blend motion-blur sub-frames and encode the final reel.

Each output frame is the linear-light average of its sub-frame samples
(rendered by scripts/render.mjs), then gets a tiny triangular dither so the
soft white/lavender gradients don't band after 8-bit 4:2:0 encoding.
Frames are piped as raw RGB into ffmpeg and muxed with audio/soundtrack.wav.

  python3 scripts/encode.py [--frames out/frames] [--out dist/sol-sniper-reel.mp4] [--crf 16]
  # several frame sets back to back (e.g. the 5 s intro hook + the 15 s reel):
  python3 scripts/encode.py --frames out/intro_frames,out/frames --audio audio/soundtrack_with_intro.wav --out dist/sol-sniper-reel-with-intro.mp4
"""
import json
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def opt(name, default):
    if f'--{name}' in sys.argv:
        return sys.argv[sys.argv.index(f'--{name}') + 1]
    return default


frames_dirs = [os.path.join(ROOT, d) for d in opt('frames', 'out/frames').split(',')]
out_path = os.path.join(ROOT, opt('out', 'dist/sol-sniper-reel.mp4'))
crf = opt('crf', '16')
audio = os.path.join(ROOT, opt('audio', 'audio/soundtrack.wav'))

# (directory, frame index, max samples) for every output frame, in order
jobs = []
for d in frames_dirs:
    meta = json.load(open(os.path.join(d, 'meta.json')))
    fps = meta['fps']
    jobs += [(d, k, meta['samples']) for k in range(meta.get('from', 0), meta.get('to', meta['total']))]
first = json.load(open(os.path.join(frames_dirs[0], 'meta.json'))).get('from', 0) if len(frames_dirs) == 1 else 0
total = len(jobs)
W, H = 1080, 1920

# sRGB <-> linear lookup tables
srgb = np.arange(256, dtype=np.float32) / 255.0
to_lin = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4).astype(np.float32)


def to_srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


os.makedirs(os.path.dirname(out_path), exist_ok=True)
cmd = [
    'ffmpeg', '-y', '-loglevel', 'error',
    '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-framerate', str(fps), '-i', '-',
    '-ss', f'{first / fps:.4f}', '-i', audio,
    '-map', '0:v', '-map', '1:a',
    '-vf', 'scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-profile:v', 'high', '-level:v', '4.2',
    '-g', str(fps), '-bf', '2',
    '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
    '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
    '-t', f'{total / fps:.3f}', '-movflags', '+faststart',
    out_path,
]
def blend(job):
    """Linear-light average of a frame's sub-frames, dithered back to 8-bit."""
    frames_dir, k, samples = job
    acc, n = None, 0
    for j in range(samples):
        f = os.path.join(frames_dir, f'f{k:04d}_{j}.png')
        if not os.path.exists(f):
            continue
        lin = to_lin[np.asarray(Image.open(f).convert('RGB'))]
        acc = lin if acc is None else acc + lin
        n += 1
    if n == 0:
        raise RuntimeError(f'missing frame {k} in {frames_dir}')  # RuntimeError propagates out of the pool (SystemExit would hang it)
    out = to_srgb(acc / n).astype(np.float32) * 255.0
    # the last set (the main reel) keeps its original dither seed, so its pixels match dist/sol-sniper-reel.mp4's source
    seed = k if frames_dir == frames_dirs[-1] else k + 100000 * (frames_dirs.index(frames_dir) + 1)
    out += np.random.default_rng(seed).triangular(-0.75, 0, 0.75, size=out.shape).astype(np.float32)
    return np.clip(np.rint(out), 0, 255).astype(np.uint8).tobytes()


proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
with Pool(max(1, (os.cpu_count() or 2))) as pool:
    for i, buf in enumerate(pool.imap(blend, jobs, chunksize=2)):
        proc.stdin.write(buf)
        if i % 30 == 0:
            print(f'\rencoding {i}/{total}', end='', flush=True)
proc.stdin.close()
proc.wait()
print(f'\nwrote {out_path}')
sys.exit(proc.returncode)
