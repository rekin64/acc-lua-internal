// Loads "Inter Tnum" (Inter with tabular digits, see scripts/make-tnum-font.py)
// so the panel's figures keep a fixed width while they tick.

export const TNUM_FONTS = [
  ['500', 'InterTnum-Medium.otf'],
  ['600', 'InterTnum-SemiBold.otf'],
  ['700', 'InterTnum-Bold.otf'],
];

export async function loadTnumFonts(urlFor) {
  await Promise.all(
    TNUM_FONTS.map(async ([weight, file]) => {
      const face = new FontFace('Inter Tnum', `url(${urlFor(file)})`, { weight });
      await face.load();
      document.fonts.add(face);
    }),
  );
}
