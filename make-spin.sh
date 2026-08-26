#!/usr/bin/env bash
# make-spin.sh — a rotation video becomes a turntable frame sequence.
#
#   ./make-spin.sh VIDEO [FRAMES] [OUTDIR]
#
# The video must be exactly one full rotation. Trim it first if it is not
# (ffmpeg -ss START -to END -c copy trimmed.mp4).
#
# Why the two passes: framing has to be identical in every frame or the
# product jitters as it turns. Pass one accumulates ONE crop box across the
# whole clip (cropdetect reset=0); pass two applies that same box to every
# frame. Cropping each frame to its own content is the classic way to get a
# turntable that wobbles.
set -euo pipefail

FF="${FF:-node_modules/ffmpeg-static/ffmpeg}"
VIDEO="${1:?usage: make-spin.sh VIDEO [FRAMES] [OUTDIR]}"
FRAMES="${2:-36}"
OUT="${3:-frames}"
KEY="${KEY:-white}"          # background colour to knock out; "none" to skip
SIM="${SIM:-0.16}"           # keying tolerance
W="${W:-1600}"; H="${H:-2000}"
MARGIN="${MARGIN:-8}"        # % of the frame kept clear around the product

command -v "$FF" >/dev/null 2>&1 || [ -x "$FF" ] || { echo "no ffmpeg at $FF"; exit 1; }
mkdir -p "$OUT"; rm -f "$OUT"/spin-*.png

# -f null -, not a bare -i: ffmpeg with no output exits 1, and under
# pipefail that would abort the script on a perfectly good probe.
DUR=$("$FF" -hide_banner -i "$VIDEO" -f null - 2>&1 \
      | sed -n 's/.*Duration: \([0-9:.]*\),.*/\1/p' | head -1 \
      | awk -F: '{print ($1*3600)+($2*60)+$3}')
[ -n "$DUR" ] || { echo "could not read duration"; exit 1; }
echo "duration ${DUR}s -> ${FRAMES} frames"

if [ "$KEY" = "none" ]; then CHAIN="format=rgba,"; else CHAIN="format=rgba,colorkey=color=${KEY}:similarity=${SIM}:blend=0.04,"; fi

# Pass 1 — one crop box for the whole clip.
# alphaextract turns the keyed-out background into black and the product into
# white, which is the only thing cropdetect can actually measure — colorkey
# leaves the RGB white and sets alpha only, so detecting on luma finds nothing
# and returns the full frame.
CROP=$("$FF" -hide_banner -i "$VIDEO" \
       -vf "${CHAIN}alphaextract,cropdetect=limit=0.05:round=2:reset=0" \
       -f null - 2>&1 | sed -n 's/.*\(crop=[0-9:]*\).*/\1/p' | tail -1)
echo "crop: ${CROP:-none detected}"

# The crop box is tight to the product, so scaling it straight to the frame
# leaves it touching all four edges. Scale into an inset box instead and let
# pad restore the full frame, giving the same clear margin on every side.
IW=$(( W - (W * MARGIN / 50) ))
IH=$(( H - (H * MARGIN / 50) ))
echo "inset: ${IW}x${IH} inside ${W}x${H} (${MARGIN}% margin)"

# Pass 2 — sample evenly, apply that box, pad to the target ratio on transparency.
"$FF" -hide_banner -loglevel error -i "$VIDEO" \
  -vf "${CHAIN}${CROP:+${CROP},}fps=${FRAMES}/${DUR},scale=${IW}:${IH}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=#00000000,format=rgba" \
  -frames:v "$FRAMES" -vsync 0 "$OUT/spin-%02d.png"

echo "wrote $(ls "$OUT"/spin-*.png | wc -l) frames to $OUT/"
