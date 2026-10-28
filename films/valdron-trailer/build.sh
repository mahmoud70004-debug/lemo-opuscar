#!/bin/sh
# One-command reproducible build for VALDRON vertical teaser:
#   9.00 s Lumrook Game Studio intro + 120.00 s pixel-art trailer = 129.00 s (1080x1920, 24 fps, -14 LUFS)
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-$(cd "$HERE/../.." && pwd)}
export LIB

# Support sandbox local toolchain automatically if present
if [ -d "/home/user/bin" ]; then export PATH="/home/user/bin:$PATH"; fi
if [ -d "/home/user/nss-libs" ]; then export LD_LIBRARY_PATH="/home/user/nss-libs:${LD_LIBRARY_PATH:-}"; fi
if [ -z "${PLAYWRIGHT_CHROME:-}" ] && [ -x "/tmp/chromium" ]; then export PLAYWRIGHT_CHROME="/tmp/chromium"; fi

[ -f "$LIB/core/render/video.mjs" ] || { echo "set LIB to the library folder"; exit 1; }
PY="$LIB/.venv/bin/python"
mkdir -p "$HERE/work"

cd "$LIB"

echo "[1/7] Exporting frame-accurate timeline events..."
node core/render/events.mjs "$HERE" --size 1080x1920

echo "[2/7] Checking caption & title reading times..."
node core/render/readcheck.mjs "$HERE" --size 1080x1920

echo "[3/7] Synthesizing original 120.0s stereo score & foley mix..."
"$PY" "$HERE/mix.py"

echo "[4/7] Rendering 120.0s vertical pixel-art trailer body (2880 frames @ 1080x1920, 24 fps)..."
node core/render/video.mjs "$HERE" --fps 24 --workers 4 --size 1080x1920 --out "$HERE/work/trailer_raw.mp4"

echo "[5/7] Mastering 120.0s trailer body to -14 LUFS (grain=0 for crisp pixel art)..."
LEMO_COLOR=bt709 sh core/render/mux.sh "$HERE/work/trailer_raw.mp4" "$HERE/work/mix.wav" "$HERE/work/trailer_body_120s.mp4" 24 0

echo "[6/7] Formatting 9.0s Lumrook intro for 1080x1920 vertical & concatenating master film..."
INTRO_SRC="$HERE/assets/lumrook-intro.mp4"
if [ -f "$INTRO_SRC" ]; then
  # Measure intro loudness for matched -14 LUFS transition
  IM=$(ffmpeg -hide_banner -nostats -i "$INTRO_SRC" -af loudnorm=I=-14:TP=-1.2:LRA=11:print_format=json -f null - 2>&1)
  IJ=$(echo "$IM" | sed -n '/{/,/}/p')
  ig() { echo "$IJ" | grep "\"$1\"" | sed 's/.*: "\(.*\)".*/\1/'; }
  ILN="loudnorm=I=-14:TP=-1.2:LRA=11:measured_I=$(ig input_i):measured_TP=$(ig input_tp):measured_LRA=$(ig input_lra):measured_thresh=$(ig input_thresh):offset=$(ig target_offset):linear=true"

  # Seamless 1080x1920 vertical framing of 16:9 studio intro over pure Lumrook #0d0618 studio canvas (zero ghosted logo blur)
  ffmpeg -y -loglevel error -f lavfi -i "color=c=0x0b0514:s=1080x1920:r=24:d=9.0" -i "$INTRO_SRC" \
    -filter_complex "[1:v]fps=24,scale=1080:-2:flags=lanczos,format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='255*min(1,min(Y/44,(H-1-Y)/44))'[front];[0:v][front]overlay=(W-w)/2:(H-h)/2:shortest=1,fade=t=out:st=8.45:d=0.52,scale=in_range=tv:out_range=tv:out_color_matrix=bt709,format=yuv420p,setsar=1[v];[1:a]$ILN,aresample=48000,afade=t=out:st=8.50:d=0.48[a]" \
    -map "[v]" -map "[a]" -t 9.0 -r 24 -c:v libx264 -preset medium -crf 18 -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -c:a pcm_s16le "$HERE/work/intro_9s.mkv"

  ffmpeg -y -loglevel error -i "$HERE/work/intro_9s.mkv" -i "$HERE/work/trailer_body_120s.mp4" \
    -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" \
    -map "[v]" -map "[a]" -r 24 -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
    -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
    -c:a aac -b:a 256k -movflags +faststart "$HERE/valdron-trailer.mp4"
  INTRO_OFFSET=9.0
else
  cp "$HERE/work/trailer_body_120s.mp4" "$HERE/valdron-trailer.mp4"
  INTRO_OFFSET=0.0
fi

echo "[7/7] Generating synchronized .srt subtitles & vertical key-art poster.jpg..."
"$PY" - "$HERE/timeline.json" "$HERE/work/cues.json" "$INTRO_OFFSET" <<'PYEOF'
import json, sys
tl = json.load(open(sys.argv[1]))
off = float(sys.argv[3])
cues = [{"t0": round(c["t0"] + off, 3), "t1": round(c["t1"] + off, 3), "text": c["text"]} for c in tl["captions"]]
json.dump(cues, open(sys.argv[2], "w"), indent=2)
PYEOF
"$PY" core/render/srt.py "$HERE/work/cues.json" "$HERE/valdron-trailer.srt"

node core/render/still.mjs "$HERE" 0 --q 'poster=1' --prefix keyart_ --size 1080x1920 --out "$HERE/work"
cp "$HERE/work/keyart_0.jpg" "$HERE/poster.jpg"

echo "Build complete: $HERE/valdron-trailer.mp4"
