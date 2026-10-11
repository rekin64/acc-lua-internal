#!/usr/bin/env python3
"""Split the client's intro reference photo into animation plates.

  assets/source/intro-reference.png  (1206x2622: phone on a dark car dashboard, with
                                      "Wait... is this legal?" burned in and an iOS bar)
  -> assets/intro/clean.png    the photo with the burned-in text and the iOS home bar removed
  -> assets/intro/phone.png    the phone cut out (RGBA), for parallax against the background
  -> assets/intro/bg.png       the background with the phone region filled (only slivers are
                               ever revealed by the parallax)
  -> assets/intro/glow.png     screen bloom (bright parts of the screen, blurred), RGBA
  -> assets/intro/profit.png   green bloom of the "+$2,600.03 / +0.32%" figures, RGBA
Run: python3 -I scripts/intro_plates.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import maximum_filter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets/source/intro-reference.png')
OUT = os.path.join(ROOT, 'assets/intro')
os.makedirs(OUT, exist_ok=True)

im = Image.open(SRC).convert('RGB')
W, H = im.size
a = np.asarray(im).astype(np.float32)
lum = a.mean(axis=2)
rng = np.random.default_rng(7)

# ---- 1. remove the burned-in text (y 585-912) and the iOS home bar (y ~2583-2597)
def fill_band(arr, y0, y1, x0, x1, src_mask):
    """Replace masked pixels in a band by a vertical blend of the rows just outside it, plus grain."""
    top = arr[y0 - 6:y0, x0:x1].mean(axis=0)
    bot = arr[y1:y1 + 6, x0:x1].mean(axis=0)
    t = np.linspace(0, 1, y1 - y0)[:, None, None]
    fill = top[None] * (1 - t) + bot[None] * t
    fill = fill + rng.normal(0, 0.9, fill.shape)
    m = src_mask[y0:y1, x0:x1][..., None]
    arr[y0:y1, x0:x1] = arr[y0:y1, x0:x1] * (1 - m) + fill * m

# text: glyphs + their glow, generously dilated; filled by normalized convolution of the
# surrounding (text-free) background, so the fill is smooth and matches the local tone
txt = (lum > 6).astype(np.float32)
txt[:560] = 0; txt[935:] = 0
tm = Image.fromarray((maximum_filter(txt, size=81) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(30))
tmask = np.clip(np.asarray(tm).astype(np.float32) / 255.0 * 1.8, 0, 1)
keep = 1.0 - maximum_filter(txt, size=121)
def blur(x, r):
    return np.asarray(Image.fromarray(np.clip(x, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32)
num = np.dstack([blur(a[..., c] * keep * 4, 60) for c in range(3)])
den = blur(keep * 255, 60)[..., None] / 255.0 * 4
est = num / np.maximum(den, 1e-3)
est = est + rng.normal(0, 0.6, est.shape)
a = a * (1 - tmask[..., None]) + est * tmask[..., None]
bar = np.zeros((H, W), np.float32); bar[2560:2622, 300:906] = 1
fill_band(a, 2560, 2616, 300, 906, bar)
a[2616:] = a[2600:2606].mean(axis=0)[None]
clean = np.clip(a, 0, 255).astype(np.uint8)
Image.fromarray(clean).save(os.path.join(OUT, 'clean.png'), optimize=True)

# ---- 2. phone matte: rounded quadrilateral measured on the photo (outer rim)
S = 4
corners = [(110, 987), (642, 950), (852, 2112), (226, 2152)]  # TL, TR, BR, BL
big = Image.new('L', (W * S, H * S), 0)
ImageDraw.Draw(big).polygon([(x * S, y * S) for x, y in corners], fill=255)
# round the corners (~55 px radius): blur then threshold, then a 1.5 px feather
big = big.filter(ImageFilter.GaussianBlur(26 * S)).point(lambda v: 255 if v > 128 else 0)
m = big.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.5))
mask = np.asarray(m).astype(np.float32) / 255.0
phone = np.dstack([clean, (mask * 255).astype(np.uint8)])
Image.fromarray(phone, 'RGBA').save(os.path.join(OUT, 'phone.png'), optimize=True)

# ---- 3. background plate: diffuse the surroundings into the phone region
small = 8
bg = clean.astype(np.float32)
sw, sh = W // small, H // small
sm = np.asarray(Image.fromarray(clean).resize((sw, sh), Image.BOX)).astype(np.float32)
mm = np.asarray(m.resize((sw, sh), Image.BOX)).astype(np.float32) / 255.0
hole = mm > 0.02
known = ~hole
val = sm.copy(); val[hole] = 0
for _ in range(400):
    p = np.pad(val, ((1, 1), (1, 1), (0, 0)), mode='edge')
    avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
    val = np.where(hole[..., None], avg, sm)
fillimg = np.asarray(Image.fromarray(np.clip(val, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(np.float32)
fillimg = fillimg * 0.85 + rng.normal(0, 1.2, fillimg.shape)
mk = np.asarray(m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(6))).astype(np.float32)[..., None] / 255.0
bgp = bg * (1 - mk) + fillimg * mk
Image.fromarray(np.clip(bgp, 0, 255).astype(np.uint8)).save(os.path.join(OUT, 'bg.png'), optimize=True)

# ---- 4. screen bloom: bright screen content, blurred
cl = clean.astype(np.float32)
l2 = cl.mean(axis=2) / 255.0
bright = np.clip((l2 - 0.45) / 0.4, 0, 1) * mask
g = np.dstack([cl * bright[..., None], bright * 255]).astype(np.uint8)
gi = Image.fromarray(g, 'RGBA').filter(ImageFilter.GaussianBlur(22))
gi.save(os.path.join(OUT, 'glow.png'), optimize=True)

# ---- 5. profit bloom: the green "+$2,600.03 / +0.32%" figures (measured ~x 185-415, y 1238-1280)
R, G, B = cl[..., 0], cl[..., 1], cl[..., 2]
green = ((G > 110) & (G > R + 35) & (G > B + 25)).astype(np.float32)
pm = np.zeros_like(green); pm[1228:1290, 175:425] = 1
green *= pm
# halo only: nothing glows over the figures themselves, so the dark glyphs in the chip stay readable
gm = Image.fromarray((green * 255).astype(np.uint8))
solid = np.asarray(gm.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))).astype(np.float32) / 255.0
halo = np.asarray(gm.filter(ImageFilter.GaussianBlur(9))).astype(np.float32) / 255.0 * (1.0 - solid)
pg = np.dstack([np.full_like(green, 70), np.full_like(green, 255), np.full_like(green, 120), np.clip(halo * 1.6, 0, 1) * 255]).astype(np.uint8)
Image.fromarray(pg, 'RGBA').save(os.path.join(OUT, 'profit.png'), optimize=True)

# film grain at native output resolution (soft-light keeps true blacks black)
for i in range(4):
    gr = np.clip(128 + np.random.default_rng(100 + i).normal(0, 20, (1920, 1080)), 0, 255).astype(np.uint8)
    Image.fromarray(gr, 'L').save(os.path.join(OUT, f'grain_{i}.png'), optimize=True)
print('plates written to', OUT, 'size', W, H)
