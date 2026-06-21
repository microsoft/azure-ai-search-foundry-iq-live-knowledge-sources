#!/usr/bin/env bash
# Build assets/how-it-works.gif from captured frames (2-pass palette for clean dark theme).
# Run AFTER `node capture.js`. Requires ffmpeg on PATH.
set -euo pipefail
cd "$(dirname "$0")"

FPS=15
SCALE=900
OUT="../../assets/how-it-works.gif"   # repo path: assets/how-it-works.gif
mkdir -p "$(dirname "$OUT")"

if [ ! -d frames ] || [ -z "$(ls -A frames 2>/dev/null)" ]; then
  echo "no frames/ — run: node capture.js" >&2
  exit 1
fi

ffmpeg -y -framerate "$FPS" -i frames/%04d.png \
  -vf "scale=${SCALE}:-1:flags=lanczos,palettegen=stats_mode=diff" palette.png

ffmpeg -y -framerate "$FPS" -i frames/%04d.png -i palette.png \
  -lavfi "scale=${SCALE}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" \
  "$OUT"

bytes=$(wc -c < "$OUT")
echo "built $OUT (${bytes} bytes)"
# Sanity gate: keep well under the README asset budget.
if [ "$bytes" -gt 1572864 ]; then
  echo "WARNING: GIF > 1.5MB — reduce FPS/SCALE or trim duration" >&2
fi
