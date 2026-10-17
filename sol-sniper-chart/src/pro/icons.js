// Lucide icons (ISC, see public/icons/LICENSE-lucide.txt) rasterised per colour
// so the canvas can draw them crisply at any size.

export const ICONS = [
  'search', 'chevron-down', 'star', 'bell', 'settings', 'circle-user', 'crosshair', 'pen-line', 'rows-3',
  'pencil', 'type', 'ruler', 'zoom-in', 'magnet', 'lock', 'eye', 'trash-2', 'smile', 'chart-candlestick',
  'square-function', 'layout-grid', 'maximize', 'camera', 'undo-2', 'redo-2', 'copy', 'globe', 'calendar',
  'share-2', 'sliders-horizontal', 'zap', 'spline', 'external-link', 'info', 'play',
];

export const ICON_COLORS = {
  muted: '#7E8AB0',
  dim: '#4C5778',
  active: '#9BB0FF',
  white: '#E6EAF5',
};

const loadImage = (src) =>
  new Promise((resolve, reject) => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = () => reject(new Error('icon failed to load'));
    im.src = src;
  });

// Returns icons[name][colourKey] -> HTMLImageElement (24 x 24 viewBox, drawn at 64 px).
export async function loadIcons(urlFor) {
  const out = {};
  await Promise.all(
    ICONS.map(async (name) => {
      const svg = await (await fetch(urlFor(`${name}.svg`))).text();
      const body = svg
        .replace(/<!--[\s\S]*?-->/g, '')
        .replace('width="24"', 'width="64"')
        .replace('height="24"', 'height="64"')
        .replace('stroke-width="2"', 'stroke-width="1.75"');
      out[name] = {};
      await Promise.all(
        Object.entries(ICON_COLORS).map(async ([key, color]) => {
          const src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(body.replaceAll('currentColor', color));
          out[name][key] = await loadImage(src);
        }),
      );
    }),
  );
  return out;
}
