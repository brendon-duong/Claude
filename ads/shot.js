const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();
for(const [n,w,h] of [['ice-bath-ad-feed-4x5',1080,1350],['ice-bath-ad-story-9x16',1080,1920]]){
const p=await b.newPage({viewport:{width:w,height:h}});await p.goto('file://'+__dirname+'/ad.html');await p.screenshot({path:n+'.png'});}
await b.close()})();
