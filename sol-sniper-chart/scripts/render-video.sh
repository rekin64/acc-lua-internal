#!/usr/bin/env sh
# Renders the 10 s video: Remotion draws 600 lossless PNG frames and encodes
# H.264, then FFmpeg moves the index to the front for instant playback.
#   default     -> out/sol-sniper-useless-pnl.mp4 (chart + simulated position)
#   OVERLAY=0   -> out/sol-sniper-useless.mp4     (original chart only)
# Optional: BROWSER_EXECUTABLE=/path/to/chrome-headless-shell to skip
# Remotion's own browser download.
set -e
cd "$(dirname "$0")/.."

if [ "${OVERLAY:-1}" = "0" ]; then
  OUT=out/sol-sniper-useless.mp4
  PROPS='{"overlay":false}'
else
  OUT=out/sol-sniper-useless-pnl.mp4
  PROPS='{"overlay":true}'
fi

npx remotion render src/remotion/index.jsx SolSniperChart out/render_raw.mp4 \
  --props="$PROPS" \
  --codec=h264 --crf=16 --x264-preset=slow --pixel-format=yuv420p \
  --color-space=bt709 --image-format=png --muted \
  ${BROWSER_EXECUTABLE:+--browser-executable="$BROWSER_EXECUTABLE"}

ffmpeg -v error -y -i out/render_raw.mp4 -map 0:v:0 -c copy -movflags +faststart "$OUT"
rm -f out/render_raw.mp4
echo "wrote $OUT"
