const {chromium}=require('playwright');const fs=require('fs');(async()=>{
const only=process.argv[2];const b=await chromium.launch();const pg=await b.newPage({viewport:{width:1080,height:1920}});
await pg.goto('file://'+__dirname+'/video.html');await pg.evaluate(()=>document.fonts.ready);
if(only){for(const t of only.split(',')){await pg.evaluate(t=>seek(+t),t);await pg.screenshot({path:`chk_${t}.jpg`,type:'jpeg',quality:70});}}
else{fs.mkdirSync('frames',{recursive:true});const fps=30,n=15*fps;for(let i=0;i<n;i++){await pg.evaluate(t=>seek(t),i/fps);await pg.screenshot({path:`frames/f${String(i).padStart(4,'0')}.jpg`,type:'jpeg',quality:95});}}
await b.close()})();
