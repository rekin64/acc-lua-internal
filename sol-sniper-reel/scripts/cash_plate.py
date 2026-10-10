#!/usr/bin/env python3
"""Retime the cash footage into the 150-frame plate used by src/cash/ (one image per output frame).

The edit runs the real footage at real speed, with three speed ramps:
  * 1.63-2.03 s  a short speed-up (peak 1.17x) through the camera's own pan to the box, so the lid
                 flies off on 2.47-2.57 and the box is fully open on the 2.60 beat
  * 2.60-3.47 s  a slow-motion dip (down to 0.46x) on the opened box
  * 4.07-4.73 s  a slow-motion dip (down to 0.4x) on the hand lifting the next bundle, so that its
                 push down into the box plays at real speed on 4.77-5.00, under the camera's whip
Where the remap lands between two source frames, the in-between frame is synthesized with dense
optical flow (OpenCV DIS, both directions), like an editor's optical-flow time remap; where the two
warped neighbours disagree (occlusions), the nearer one is used instead of a double exposure.
Whole-frame positions use the source frame untouched.

The shoe-box lid carries a third-party logo (it passes behind the "Wait…" type at 1.8-2.5 s). It is
tracked in the source frames (template match) and blurred into the lid colour before retiming.

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
    (122, 20, -6 / 10),     # slow motion on the hand lifting the next bundle: -6 source frames
]

# logo on the lid: template from source frame 62 (x, y, w, h), searched in source frames 54-76
LOGO_REF, LOGO_TPL, LOGO_RANGE = 62, (435, 390, 280, 220), range(54, 77)


def remap(k):
    """Source frame position (float) shown on output frame k."""
    s = float(k)
    for a, w, amt in RAMPS:
        x = min(max(k - a, 0.0), w)
        s += amt * (0.5 * x - w / (4 * math.pi) * math.sin(2 * math.pi * x / w))
    return s


def load_raw(i):
    return np.asarray(Image.open(os.path.join(SRC, f's_{i:04d}.jpg')).convert('RGB'))


def track_logo():
    """{source frame: (x, y, w, h)} of the lid logo; extrapolated where the match is weak."""
    gray = lambda a: cv2.cvtColor(a, cv2.COLOR_RGB2GRAY).astype(np.float32)
    x0, y0, w0, h0 = LOGO_TPL
    tpl = gray(load_raw(LOGO_REF))[y0:y0 + h0, x0:x0 + w0]
    boxes, prev, vel = {}, None, (0.0, 0.0)
    for i in sorted(LOGO_RANGE, key=lambda i: abs(i - LOGO_REF)):  # outward from the reference frame
        g = gray(load_raw(i))
        best = None
        for sc in (0.8, 0.9, 1.0, 1.1):
            t = cv2.resize(tpl, None, fx=sc, fy=sc)
            _, mx, _, loc = cv2.minMaxLoc(cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED))
            if best is None or mx > best[0]:
                best = (mx, loc[0], loc[1], t.shape[1], t.shape[0])
        mx, x, y, w, h = best
        near = min(boxes, key=lambda j: abs(j - i)) if boxes else None
        ok = mx >= 0.53 and (near is None or math.hypot(x - boxes[near][0], y - boxes[near][1]) < 160)
        if not ok and near is not None:  # extrapolate from the two nearest tracked frames
            n2 = near + (1 if near > i else -1)
            px, py, pw, ph = boxes[near]
            if n2 in boxes:
                dx, dy = px - boxes[n2][0], py - boxes[n2][1]
                x, y, w, h = int(px + dx), int(py + dy), pw, ph
            else:
                x, y, w, h = px, py, pw, ph
        boxes[i] = (int(x), int(y), int(w), int(h))
    return boxes


def hide_logo(img, box):
    """Blur the logo into the lid: a heavy blur pulled toward the surrounding lid colour, feathered."""
    x, y, w, h = box
    H, W = img.shape[:2]
    m = np.zeros((H, W), np.float32)
    pad = 26
    cv2.rectangle(m, (x - pad, y - pad), (x + w + pad, y + h + pad), 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), 18)
    ring = (cv2.GaussianBlur(m, (0, 0), 60) > 0.05) & (m < 0.02)
    f = img.astype(np.float32)
    lum = f.mean(axis=2)
    sel = ring & (lum < 110)
    lid = np.median(f[sel], axis=0) if sel.sum() > 500 else np.median(f[ring], axis=0)
    soft = cv2.GaussianBlur(f, (0, 0), 28)
    patch = 0.25 * soft + 0.75 * lid[None, None, :]
    out = f * (1 - m[..., None]) + patch * m[..., None]
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


LOGO = track_logo()
_cache = {}


def load(i):
    if i not in _cache:
        img = load_raw(i)
        _cache[i] = hide_logo(img, LOGO[i]) if i in LOGO else img
    return _cache[i]


_flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)


def flow(a, b):
    ga, gb = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    return _flow.calc(ga, gb, None)


def warp(img, f):
    h, w = f.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(img, gx + f[..., 0], gy + f[..., 1], cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def between(i, t):
    """Frame at source position i + t (0 < t < 1): bidirectional flow warp, blended in linear light.
    Where the two warps disagree (occlusion, flow failure) the nearer frame's warp wins, so no ghosts."""
    a, b = load(i), load(i + 1)
    f01, f10 = flow(a, b), flow(b, a)
    ft0 = -(1 - t) * t * f01 + t * t * f10              # flow from the in-between frame back to a
    ft1 = (1 - t) * (1 - t) * f01 - t * (1 - t) * f10    # ... and forward to b
    wa, wb = warp(a, ft0), warp(b, ft1)
    lin = lambda x: (x.astype(np.float32) / 255.0) ** 2.2
    la, lb = lin(wa), lin(wb)
    d = np.abs(wa.astype(np.float32) - wb.astype(np.float32)).max(axis=2)
    d = cv2.GaussianBlur(d, (0, 0), 3)
    k = np.clip((d - 14.0) / 26.0, 0.0, 1.0)            # 0: agree -> blend; 1: disagree -> nearer frame
    wbt = (1 - k) * t + k * (1.0 if t >= 0.5 else 0.0)
    mix = (1 - wbt[..., None]) * la + wbt[..., None] * lb
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
json.dump({'plan': plan, 'logo': {str(i): b for i, b in sorted(LOGO.items())}}, open(os.path.join(OUT, 'map.json'), 'w'), indent=0)
print(f'wrote {FRAMES} plate frames ({sum(p["synth"] for p in plan)} flow-synthesized, logo hidden in source '
      f'frames {min(LOGO)}-{max(LOGO)}) to {OUT}')
