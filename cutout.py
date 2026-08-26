import sys, subprocess, os
from collections import deque

FF="node_modules/ffmpeg-static/ffmpeg"
src, out, tol = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv)>3 else 34

# probe size
info = subprocess.run([FF,"-hide_banner","-i",src], capture_output=True, text=True).stderr
import re
m = re.search(r", (\d+)x(\d+)", info); W,H = int(m.group(1)), int(m.group(2))
subprocess.run([FF,"-hide_banner","-loglevel","error","-y","-i",src,"-f","rawvideo","-pix_fmt","rgba","_t.bin"],check=True)
d=bytearray(open("_t.bin","rb").read())
def I(x,y): return (y*W+x)*4

# background colour = median of the four corners, so a white sweep, a pale
# blue set and a grey plinth all work without per-image tuning
cor=[d[I(2,2):I(2,2)+3], d[I(W-3,2):I(W-3,2)+3], d[I(2,H-3):I(2,H-3)+3], d[I(W-3,H-3):I(W-3,H-3)+3]]
bgc=[sorted(c[k] for c in cor)[1] for k in range(3)]

def isbg(i):
    return (abs(d[i]-bgc[0])<=tol and abs(d[i+1]-bgc[1])<=tol and abs(d[i+2]-bgc[2])<=tol)

bg=bytearray(W*H); q=deque()
for x in range(W):
    for y in (0,H-1):
        if isbg(I(x,y)) and not bg[y*W+x]: bg[y*W+x]=1; q.append((x,y))
for y in range(H):
    for x in (0,W-1):
        if isbg(I(x,y)) and not bg[y*W+x]: bg[y*W+x]=1; q.append((x,y))
while q:
    x,y=q.popleft()
    for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
        if 0<=nx<W and 0<=ny<H and not bg[ny*W+nx] and isbg(I(nx,ny)):
            bg[ny*W+nx]=1; q.append((nx,ny))

lab=[0]*(W*H); best=0; bestn=0; cur=0
for sy in range(H):
    for sx in range(W):
        if bg[sy*W+sx] or lab[sy*W+sx]: continue
        cur+=1; n=0; q=deque([(sx,sy)]); lab[sy*W+sx]=cur
        while q:
            x,y=q.popleft(); n+=1
            for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if 0<=nx<W and 0<=ny<H and not bg[ny*W+nx] and not lab[ny*W+nx]:
                    lab[ny*W+nx]=cur; q.append((nx,ny))
        if n>bestn: bestn=n; best=cur

A=[255 if lab[p]==best else 0 for p in range(W*H)]
er=[0]*(W*H)
for y in range(H):
    for x in range(W):
        p=y*W+x
        if not A[p]: continue
        er[p]=255 if all(0<=x+dx<W and 0<=y+dy<H and A[(y+dy)*W+x+dx]
                         for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))) else 0
x0,y0,x1,y1=W,H,0,0
for y in range(H):
    for x in range(W):
        s=n=0
        for dy in(-1,0,1):
            for dx in(-1,0,1):
                nx,ny=x+dx,y+dy
                if 0<=nx<W and 0<=ny<H: s+=er[ny*W+nx]; n+=1
        a=s//n; d[I(x,y)+3]=a
        if a>8:
            x0=min(x0,x); x1=max(x1,x); y0=min(y0,y); y1=max(y1,y)
open("_o.bin","wb").write(bytes(d))
cw,ch=x1-x0+1,y1-y0+1
subprocess.run([FF,"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgba",
  "-s",f"{W}x{H}","-i","_o.bin","-vf",f"crop={cw}:{ch}:{x0}:{y0},format=rgba","-frames:v","1",out],check=True)
print(f"{os.path.basename(src):46s} bg={tuple(bgc)} comps={cur} product={100*bestn/(W*H):.1f}%  -> {cw}x{ch}")
