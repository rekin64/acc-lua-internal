import React from 'react';
import { Composition } from 'remotion';
import { DURATION, FPS, H, W } from '../engine.js';
import { ChartVideo } from './ChartVideo.jsx';

export const Root = () => (
  <Composition
    id="SolSniperChart"
    component={ChartVideo}
    width={W}
    height={H}
    fps={FPS}
    durationInFrames={FPS * DURATION}
  />
);
