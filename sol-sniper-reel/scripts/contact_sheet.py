#!/usr/bin/env python3
"""Tile PNG frames into a labelled contact sheet.
   python3 scripts/contact_sheet.py out.png frame1.png frame2.png ... [--cols 6] [--width 270]"""
import sys
from PIL import Image, ImageDraw

args = sys.argv[1:]
cols, width = 6, 270
if '--cols' in args:
    i = args.index('--cols'); cols = int(args[i + 1]); del args[i:i + 2]
if '--width' in args:
    i = args.index('--width'); width = int(args[i + 1]); del args[i:i + 2]
out, files = args[0], args[1:]
ims = [Image.open(f).convert('RGB') for f in files]
w = width
h = int(ims[0].height * w / ims[0].width)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (w + 8) + 8, rows * (h + 30) + 8), (40, 40, 44))
d = ImageDraw.Draw(sheet)
for k, (im, f) in enumerate(zip(ims, files)):
    r, c = divmod(k, cols)
    x, y = 8 + c * (w + 8), 8 + r * (h + 30)
    sheet.paste(im.resize((w, h), Image.LANCZOS), (x, y))
    label = f.rsplit('/', 1)[-1].rsplit('.', 1)[0][-18:]
    d.text((x + 2, y + h + 6), label, fill=(230, 230, 230))
sheet.save(out)
print(out)
