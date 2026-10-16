"""Builds "Inter Tnum": Inter with tabular (fixed-width) digits as the default.

Canvas 2D cannot enable the OpenType `tnum` feature, so the digit code points
are remapped to Inter's own tabular glyphs (zero.tf ... nine.tf). Inter is
licensed under the SIL Open Font License 1.1; the modified font is renamed.
Usage: python3 scripts/make-tnum-font.py
"""
from pathlib import Path

from fontTools.ttLib import TTFont

SRC = Path('/usr/share/fonts/opentype/inter')
OUT = Path(__file__).resolve().parent.parent / 'public' / 'fonts'
DIGITS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']

for style in ['Medium', 'SemiBold', 'Bold']:
    font = TTFont(SRC / f'Inter-{style}.otf')
    glyphs = set(font.getGlyphOrder())
    for table in font['cmap'].tables:
        if not table.isUnicode():
            continue
        for i, name in enumerate(DIGITS):
            if 0x30 + i in table.cmap and f'{name}.tf' in glyphs:
                table.cmap[0x30 + i] = f'{name}.tf'
    names = font['name']
    for rec in names.names:
        if rec.nameID in (1, 16):
            rec.string = 'Inter Tnum'
        elif rec.nameID == 4:
            rec.string = f'Inter Tnum {style}'
        elif rec.nameID == 6:
            rec.string = f'InterTnum-{style}'
    font.save(OUT / f'InterTnum-{style}.otf')
    print('wrote', OUT / f'InterTnum-{style}.otf')
