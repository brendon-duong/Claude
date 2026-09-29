#!/usr/bin/env bash
# v2: shared body + 4 hooks. Inputs in ./clips: hook0 hook1 hook2 hook3 (mp4), 2.mp4 3.mp4 4.mp4 5.mp4, vo4.mp3 vo5.mp3
set -euo pipefail
V="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1"
ENC="-c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -ac 2"
D=ov/disclaimer.png

one() { # one <in> <out> <caption png> [trim_start]
  ffmpeg -y -loglevel error -ss "${4:-0}" -i "$1" -i "$3" -i $D -filter_complex "[0:v]$V[v];[v][1]overlay[a];[a][2]overlay[out];[0:a]aresample=48000[au]" -map "[out]" -map "[au]" $ENC "$2"
}
# hooks
one clips/hook0.mp4 h0.mp4 ov/c1.png
one clips/hook1.mp4 h1.mp4 ov/h1.png
one clips/hook2.mp4 h2.mp4 ov/h2.png
one clips/hook3.mp4 h3.mp4 ov/h3.png
# body
one clips/2.mp4 b2.mp4 ov/c2.png 1.2
ffmpeg -y -loglevel error -i clips/3.mp4 -i ov/c3a.png -i ov/c3b.png -i $D -filter_complex "[0:v]$V[v];[v][1]overlay=enable='lt(t,3.4)'[a];[a][2]overlay=enable='gte(t,3.4)'[b];[b][3]overlay[out];[0:a]aresample=48000[au]" -map "[out]" -map "[au]" $ENC b3.mp4
# scene 4: VO over ducked clip audio
ffmpeg -y -loglevel error -i clips/4.mp4 -i clips/vo4.mp3 -i ov/c4a.png -i ov/c4b.png -i $D -filter_complex "[0:v]$V[v];[v][2]overlay=enable='lt(t,2.6)'[a];[a][3]overlay=enable='gte(t,2.6)'[b];[b][4]overlay[out];[0:a]volume=0.35,aresample=48000[bg];[1:a]adelay=300|300,aresample=48000,volume=1.4[vo];[bg][vo]amix=inputs=2:duration=first:normalize=0[au]" -map "[out]" -map "[au]" $ENC b4.mp4
ffmpeg -y -loglevel error -i clips/5.mp4 -i clips/vo5.mp3 -i ov/c5.png -i $D -filter_complex "[0:v]$V[v];[v][2]overlay[a];[a][3]overlay[out];[0:a]volume=0.35,aresample=48000[bg];[1:a]adelay=400|400,aresample=48000,volume=1.4[vo];[bg][vo]amix=inputs=2:duration=first:normalize=0[au]" -map "[out]" -map "[au]" $ENC b5.mp4
ffmpeg -y -loglevel error -loop 1 -t 3.5 -i ov/endcard.png -f lavfi -t 3.5 -i anullsrc=r=48000:cl=stereo \
  -filter_complex "[0:v]scale=1188:2112,zoompan=z='min(1+0.0009*on,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=105:s=1080x1920:fps=30,setsar=1[out]" \
  -map "[out]" -map 1:a $ENC -shortest b6.mp4
for h in 0 1 2 3; do
  printf "file '%s'\n" h$h.mp4 b2.mp4 b3.mp4 b4.mp4 b5.mp4 b6.mp4 > l$h.txt
  ffmpeg -y -loglevel error -f concat -safe 0 -i l$h.txt $ENC -movflags +faststart nitidus_v2_hook$h.mp4
  echo "hook$h $(ffprobe -v error -show_entries format=duration -of csv=p=0 nitidus_v2_hook$h.mp4)"
done
