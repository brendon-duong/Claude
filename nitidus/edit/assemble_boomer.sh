#!/usr/bin/env bash
# 50+ mums set: hook g1..g3 + shared body (m1 talking head, glove clip + VO, m5 closing + VO, end card)
set -euo pipefail
V="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1"
ENC="-c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -ac 2"
one() { ffmpeg -y -loglevel error -i "$1" -i "$3" -filter_complex "[0:v]$V[v];[v][1]overlay[out];[0:a]aresample=48000[au]" -map "[out]" -map "[au]" $ENC "$2"; }
two() { # two <in> <out> <capA> <capB> <switch_t>
  ffmpeg -y -loglevel error -i "$1" -i "$3" -i "$4" -filter_complex "[0:v]$V[v];[v][1]overlay=enable='lt(t,$5)'[a];[a][2]overlay=enable='gte(t,$5)'[out];[0:a]aresample=48000[au]" -map "[out]" -map "[au]" $ENC "$2"; }
for h in 1 2 3; do one clips/g$h.mp4 hk$h.mp4 ov/g$h.png; done
two clips/m1.mp4 k1.mp4 ov/m1a.png ov/m1b.png "${M1_SWITCH:-3.2}"
ffmpeg -y -loglevel error -i clips/4.mp4 -i clips/vo4.mp3 -i ov/m4a.png -i ov/m4b.png -filter_complex "[0:v]$V[v];[v][2]overlay=enable='lt(t,2.6)'[a];[a][3]overlay=enable='gte(t,2.6)'[out];[0:a]volume=0.35,aresample=48000[bg];[1:a]adelay=300|300,aresample=48000,volume=1.4[vo];[bg][vo]amix=inputs=2:duration=first:normalize=0[au]" -map "[out]" -map "[au]" $ENC k2.mp4
ffmpeg -y -loglevel error -i clips/m5.mp4 -i clips/vo5.mp3 -i ov/m5.png -filter_complex "[0:v]$V[v];[v][2]overlay[out];[0:a]volume=0.35,aresample=48000[bg];[1:a]adelay=300|300,aresample=48000,volume=1.4[vo];[bg][vo]amix=inputs=2:duration=first:normalize=0[au]" -map "[out]" -map "[au]" $ENC k3.mp4
ffmpeg -y -loglevel error -loop 1 -t 3.5 -i ov/endcard.png -f lavfi -t 3.5 -i anullsrc=r=48000:cl=stereo \
  -filter_complex "[0:v]scale=1188:2112,zoompan=z='min(1+0.0009*on,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=105:s=1080x1920:fps=30,setsar=1[out]" \
  -map "[out]" -map 1:a $ENC -shortest k4.mp4
for h in 1 2 3; do
  printf "file '%s'\n" hk$h.mp4 k1.mp4 k2.mp4 k3.mp4 k4.mp4 > m$h.txt
  ffmpeg -y -loglevel error -f concat -safe 0 -i m$h.txt $ENC -movflags +faststart nitidus_50plus_hook$h.mp4
  echo "hook$h $(ffprobe -v error -show_entries format=duration -of csv=p=0 nitidus_50plus_hook$h.mp4)"
done
