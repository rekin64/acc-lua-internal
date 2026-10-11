#!/usr/bin/env python3
"""Overlay approximate Instagram Reels UI zones on frames (QA only).
   python3 -I scripts/safezone.py out.png frame.png"""
import sys
from PIL import Image, ImageDraw

out, src = sys.argv[1], sys.argv[2]
im = Image.open(src).convert('RGBA')
ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
d = ImageDraw.Draw(ov)
red = (255, 40, 40, 70)
d.rectangle([0, 0, 1080, 200], fill=red)          # top bar (Reels title / camera)
d.rectangle([0, 1520, 1080, 1920], fill=red)      # caption, username, audio, nav
d.rectangle([950, 1000, 1080, 1520], fill=red)    # like / comment / share column
d.rectangle([60, 200, 950, 1520], outline=(40, 200, 90, 200), width=3)  # safe text area
Image.alpha_composite(im, ov).convert('RGB').save(out)
print(out)
