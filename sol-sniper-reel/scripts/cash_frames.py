#!/usr/bin/env python3
"""Extract the cash footage (assets/source/cash-footage.mp4) to still frames for src/cash/.

The clip is HEVC 1080x1920, BT.709 limited range. Frames are decoded with an explicit BT.709 matrix to
full-range RGB, then written as 4:4:4 JPEG (quality 97, so the browser decodes them with the standard
JPEG matrix and the colors stay exactly the source's). Every coded frame is kept (no frame-rate
conversion); src/cash/cash.js picks source frames by index.

  python3 scripts/cash_frames.py   # -> out/cash/frames/s_0000.jpg ... (gitignored)
"""
import os
import subprocess

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets/source/cash-footage.mp4')
OUT = os.path.join(ROOT, 'out/cash/frames')
W, H = 1080, 1920

os.makedirs(OUT, exist_ok=True)
cmd = ['ffmpeg', '-v', 'error', '-i', SRC, '-fps_mode', 'passthrough', '-an',
       '-vf', 'scale=in_color_matrix=bt709:in_range=tv:out_range=full,format=rgb24',
       '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
n = 0
while True:
    buf = proc.stdout.read(W * H * 3)
    if len(buf) < W * H * 3:
        break
    img = Image.fromarray(np.frombuffer(buf, np.uint8).reshape(H, W, 3))
    img.save(os.path.join(OUT, f's_{n:04d}.jpg'), quality=97, subsampling=0)
    n += 1
proc.wait()
print(f'wrote {n} frames to {OUT}')
