#!/bin/sh
# One-command reproducible build for Pottsfield Studio Official 10s Game Intro (16:9 Windows/Landscape + 9:16 Mobile Portrait)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-$(cd "$HERE/../.." && pwd)}
export LIB
[ -f "$LIB/core/render/mux.sh" ] || { echo "set LIB to the Lemo-Opuscar library folder"; exit 1; }

PY="$LIB/.venv/bin/python"
[ -x "$PY" ] || PY=python3

mkdir -p "$HERE/out" "$HERE/work"

echo "==> [1/5] Exporting timeline & cue sheet..."
"$PY" "$HERE/timeline.py"

echo "==> [2/5] Preparing 2D woodcut, 3D normal/height & semantic crest layers..."
"$PY" "$HERE/prepare_assets.py"

echo "==> [3/5] Synthesizing score, foley & stereo mix + verifying 0 ms cue lock..."
"$PY" "$HERE/mix.py"
"$PY" "$HERE/cuecheck.py"

echo "==> [4/5] Rendering 1920x1080 (16:9 Landscape — Windows & Landscape Games) @ 30 fps..."
"$PY" "$HERE/render_video.py" --size 1920x1080 --out "$HERE/out/video_16x9.mp4" --poster "$HERE/poster.jpg" --workers 2
LEMO_COLOR=bt709 sh "$LIB/core/render/mux.sh" "$HERE/out/video_16x9.mp4" "$HERE/out/mix.wav" "$HERE/pottsfield-intro.mp4" 30 1

echo "==> [5/5] Rendering 1080x1920 (9:16 Vertical — Portrait Mobile Games) @ 30 fps..."
"$PY" "$HERE/render_video.py" --size 1080x1920 --out "$HERE/out/video_9x16.mp4" --poster "$HERE/poster-vertical.jpg" --workers 2
LEMO_COLOR=bt709 sh "$LIB/core/render/mux.sh" "$HERE/out/video_9x16.mp4" "$HERE/out/mix.wav" "$HERE/pottsfield-intro-vertical.mp4" 30 1

echo "==> [6/6] Rendering 1080x1920 Viral Social Launch Short (YouTube Shorts / TikTok / Reels) @ 30 fps..."
"$PY" "$HERE/social_short.py" --out-raw "$HERE/out/video_social_9x16.mp4" --poster "$HERE/poster-launch-short.jpg" --workers 2
LEMO_COLOR=bt709 sh "$LIB/core/render/mux.sh" "$HERE/out/video_social_9x16.mp4" "$HERE/out/mix_social.wav" "$HERE/pottsfield-launch-short.mp4" 30 1

echo "✓ Build complete:"
echo "  16:9 Game Boot : $HERE/pottsfield-intro.mp4"
echo "  9:16 Game Boot : $HERE/pottsfield-intro-vertical.mp4"
echo "  9:16 Viral Short: $HERE/pottsfield-launch-short.mp4"
echo "  Posters        : $HERE/poster.jpg , $HERE/poster-vertical.jpg , $HERE/poster-launch-short.jpg"
