import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  AbsoluteFill,
  cancelRender,
  continueRender,
  delayRender,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { buildMarket } from '../engine.js';
import { drawFrame } from '../render.js';

const market = buildMarket();

const loadImage = (src) =>
  new Promise((resolve, reject) => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = () => reject(new Error(`Failed to load ${src}`));
    im.src = src;
  });

export const ChartVideo = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const canvas = useRef(null);
  const [assets, setAssets] = useState(null);
  const [handle] = useState(() => delayRender('Loading logo, token icon and fonts'));
  const released = useRef(false);

  useEffect(() => {
    Promise.all([
      loadImage(staticFile('assets/solsniper-logo.png')),
      loadImage(staticFile('assets/useless.png')),
      ...['500 20px Inter', '500 28px Inter', '600 46px Inter', '700 50px Inter'].map((f) => document.fonts.load(f)),
    ])
      .then(([logo, token]) => setAssets({ logo, token }))
      .catch((err) => cancelRender(err));
  }, []);

  // Layout effect: the frame is drawn before Remotion captures it.
  useLayoutEffect(() => {
    if (!assets || !canvas.current) return;
    const ctx = canvas.current.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    drawFrame(ctx, frame / fps, market, assets);
    if (!released.current) {
      released.current = true;
      continueRender(handle);
    }
  }, [frame, fps, assets, handle]);

  return (
    <AbsoluteFill style={{ backgroundColor: '#01040B' }}>
      <canvas ref={canvas} width={width} height={height} />
    </AbsoluteFill>
  );
};
