#!/usr/bin/env bash
# Assemble the Nitidus ad: clips 1-5 in ./clips, overlays in ./ov -> nitidus_ad_v1.mp4
set -euo pipefail
V="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1"
A="aresample=48000,aformat=channel_layouts=stereo"

seg() { # seg <n> <overlay filter chain on [v][...]> <inputs...>
  local n=$1; shift; local fc=$1; shift
  ffmpeg -y -loglevel error -i clips/$n.mp4 "$@" -filter_complex "$fc" \
    -map "[out]" -map 0:a -af "$A" -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest s$n.mp4
}

D="ov/disclaimer.png"
seg 1 "[0:v]$V[v];[v][1]overlay[a];[a][2]overlay[out]" -i ov/c1.png -i $D
seg 2 "[0:v]$V[v];[v][1]overlay[a];[a][2]overlay[out]" -i ov/c2.png -i $D
seg 3 "[0:v]$V[v];[v][1]overlay=enable='lt(t,3.4)'[a];[a][2]overlay=enable='gte(t,3.4)'[b];[b][3]overlay[out]" -i ov/c3a.png -i ov/c3b.png -i $D
seg 4 "[0:v]$V[v];[v][1]overlay=enable='lt(t,2.6)'[a];[a][2]overlay=enable='gte(t,2.6)'[b];[b][3]overlay[out]" -i ov/c4a.png -i ov/c4b.png -i $D
seg 5 "[0:v]$V[v];[v][1]overlay[a];[a][2]overlay[out]" -i ov/c5.png -i $D

# end card: 3.5s with a gentle push-in
ffmpeg -y -loglevel error -loop 1 -t 3.5 -i ov/endcard.png -f lavfi -t 3.5 -i anullsrc=r=48000:cl=stereo \
  -filter_complex "[0:v]scale=1188:2112,zoompan=z='min(1+0.0009*on,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=105:s=1080x1920:fps=30,setsar=1[out]" \
  -map "[out]" -map 1:a -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest s6.mp4

printf "file 's%d.mp4'\n" 1 2 3 4 5 6 > list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart nitidus_ad_v1.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 nitidus_ad_v1.mp4
