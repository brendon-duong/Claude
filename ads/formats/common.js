const $=id=>document.getElementById(id),cl=(x,a=0,b=1)=>Math.max(a,Math.min(b,x)),p=(t,a,b)=>cl((t-a)/(b-a)),eo=x=>1-Math.pow(1-x,3),lerp=(a,b,x)=>a+(b-a)*x,back=x=>{const c=1.7;return 1+(c+1)*Math.pow(x-1,3)+c*Math.pow(x-1,2)};
const NC=121,cf=k=>'../video/clip/c'+String(cl(Math.round(k),0,NC-1)+1).padStart(4,'0')+'.jpg';
const play=(dt)=>{if(dt<0)return 0;if(dt<4)return dt*30;const span=NC-1-70,x=((dt-4)*14)%(2*span);return NC-1-(x<span?x:2*span-x)};
function setImg(el,src){if(el.dataset.s!==src){el.dataset.s=src;el.src=src}}
const typed=(s,t,a,cps=20)=>s.slice(0,Math.max(0,Math.floor((t-a)*cps)));
const pop=(t,a,d=.3)=>t<a?0:lerp(.6,1,back(p(t,a,a+d)));
