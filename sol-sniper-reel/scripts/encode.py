#!/usr/bin/env python3
"""Blend motion-blur sub-frames and encode the final reel.

Each output frame is the linear-light average of its sub-frame samples
(rendered by scripts/render.mjs), then gets a tiny triangular dither so the
soft white/lavender gradients don't band after 8-bit 4:2:0 encoding.
Frames are piped as raw RGB into ffmpeg and muxed with audio/soundtrack.wav.

  python3 scripts/encode.py [--frames out/frames] [--out dist/sol-sniper-reel.mp4] [--crf 16]
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def opt(name, default):
    if f'--{name}' in sys.argv:
        return sys.argv[sys.argv.index(f'--{name}') + 1]
    return default


frames_dir = os.path.join(ROOT, opt('frames', 'out/frames'))
out_path = os.path.join(ROOT, opt('out', 'dist/sol-sniper-reel.mp4'))
crf = opt('crf', '16')
audio = os.path.join(ROOT, opt('audio', 'audio/soundtrack.wav'))

meta = json.load(open(os.path.join(frames_dir, 'meta.json')))
fps, samples, total = meta['fps'], meta['samples'], meta['total']
W, H = 1080, 1920

# sRGB <-> linear lookup tables
srgb = np.arange(256, dtype=np.float32) / 255.0
to_lin = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4).astype(np.float32)


def to_srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


rng = np.random.default_rng(1234)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
cmd = [
    'ffmpeg', '-y', '-loglevel', 'error',
    '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-framerate', str(fps), '-i', '-',
    '-i', audio,
    '-map', '0:v', '-map', '1:a',
    '-vf', 'scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-profile:v', 'high', '-level:v', '4.2',
    '-g', str(fps), '-bf', '2',
    '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
    '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
    '-t', f'{total / fps:.3f}', '-movflags', '+faststart',
    out_path,
]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for k in range(total):
    acc = None
    n = 0
    for j in range(samples):
        f = os.path.join(frames_dir, f'f{k:04d}_{j}.png')
        if not os.path.exists(f):
            continue
        img = np.asarray(Image.open(f).convert('RGB'))
        lin = to_lin[img]
        acc = lin if acc is None else acc + lin
        n += 1
    if n == 0:
        raise SystemExit(f'missing frame {k}')
    out = to_srgb(acc / n) * 255.0
    out += rng.triangular(-0.75, 0, 0.75, size=out.shape).astype(np.float32)
    proc.stdin.write(np.clip(np.rint(out), 0, 255).astype(np.uint8).tobytes())
    if k % 30 == 0:
        print(f'\rencoding {k}/{total}', end='', flush=True)
proc.stdin.close()
proc.wait()
print(f'\nwrote {out_path}')
sys.exit(proc.returncode)
