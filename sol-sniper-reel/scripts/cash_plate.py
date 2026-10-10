#!/usr/bin/env python3
"""Retime the cash footage into the 150-frame plate used by src/cash/ (one image per output frame).

The edit runs the real footage at real speed, with two speed ramps:
  * 1.63-2.03 s  a short speed-up (peak 1.17x) through the camera's own pan to the box, so the lid
                 flies off on 2.47-2.57 and the box is fully open on the 2.60 beat
  * 2.60-3.47 s  a slow-motion dip (down to 0.46x) on the opened box, so that the hand's push into
                 the box lands on 4.53-4.83 and the camera follows it into the whip (4.53-5.00)
Where the remap lands between two source frames, the in-between frame is synthesized with dense
optical flow (OpenCV DIS, both directions), like an editor's optical-flow time remap. Whole-frame
positions use the source frame untouched.

  python3 scripts/cash_frames.py && python3 scripts/cash_plate.py   # -> out/cash/plate/p_0000.jpg ... p_0149.jpg
"""
import json
import math
import os

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'out/cash/frames')
OUT = os.path.join(ROOT, 'out/cash/plate')
FRAMES = 150  # 5.00 s at 30 fps

# speed ramps as raised-cosine bumps on the playback speed: (start frame, width, amount)
RAMPS = [
    (49, 12, +1 / 6),       # pan to the box: +1 source frame
    (78, 26, -7 / 13),      # slow motion on the opened box: -7 source frames
]


def remap(k):
    """Source frame position (float) shown on output frame k."""
    s = float(k)
    for a, w, amt in RAMPS:
        x = min(max(k - a, 0.0), w)
        s += amt * (0.5 * x - w / (4 * math.pi) * math.sin(2 * math.pi * x / w))
    return s


def load(i):
    return np.asarray(Image.open(os.path.join(SRC, f's_{i:04d}.jpg')).convert('RGB'))


_flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)


def flow(a, b):
    ga, gb = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    return _flow.calc(ga, gb, None)


def warp(img, f):
    h, w = f.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(img, gx + f[..., 0], gy + f[..., 1], cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def between(i, t):
    """Frame at source position i + t (0 < t < 1): bidirectional flow warp, blended in linear light."""
    a, b = load(i), load(i + 1)
    f01, f10 = flow(a, b), flow(b, a)
    ft0 = -(1 - t) * t * f01 + t * t * f10              # flow from the in-between frame back to a
    ft1 = (1 - t) * (1 - t) * f01 - t * (1 - t) * f10    # ... and forward to b
    lin = lambda x: (x.astype(np.float32) / 255.0) ** 2.2
    mix = (1 - t) * lin(warp(a, ft0)) + t * lin(warp(b, ft1))
    return np.clip(np.rint(255.0 * mix ** (1 / 2.2)), 0, 255).astype(np.uint8)


os.makedirs(OUT, exist_ok=True)
n_src = len([f for f in os.listdir(SRC) if f.endswith('.jpg')])
plan = []
for k in range(FRAMES):
    s = remap(k)
    i, t = int(math.floor(s)), s - math.floor(s)
    if t < 0.03 or t > 0.97 or i + 1 >= n_src:
        i, t = min(int(round(s)), n_src - 1), 0.0
        img = load(i)
    else:
        img = between(i, t)
    Image.fromarray(img).save(os.path.join(OUT, f'p_{k:04d}.jpg'), quality=97, subsampling=0)
    plan.append({'k': k, 'source': round(s, 3), 'synth': t > 0})
json.dump(plan, open(os.path.join(OUT, 'map.json'), 'w'), indent=0)
print(f'wrote {FRAMES} plate frames ({sum(p["synth"] for p in plan)} flow-synthesized) to {OUT}')
