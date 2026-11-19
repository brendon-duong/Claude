const {chromium}=require('playwright');const fs=require('fs');(async()=>{
const v=process.argv[2],only=process.argv[3];const b=await chromium.launch();const pg=await b.newPage({viewport:{width:1080,height:1920}});
await pg.goto('file://'+__dirname+'/'+v+'.html');await pg.evaluate(()=>document.fonts.ready);
const S=t=>pg.evaluate(async t=>{seek(+t);await Promise.all([...document.images].filter(i=>i.getAttribute('src')).map(i=>i.decode().catch(()=>{})))},t);
const dur=await pg.evaluate(()=>window.DUR);
if(only){for(const t of only.split(',')){await S(t);await pg.screenshot({path:`chk_${v}_${t}.jpg`,type:'jpeg',quality:70});}}
else{fs.mkdirSync('frames_'+v,{recursive:true});const n=Math.round(dur*30);for(let i=0;i<n;i++){await S(i/30);await pg.screenshot({path:`frames_${v}/f${String(i).padStart(4,'0')}.jpg`,type:'jpeg',quality:94});}}
await b.close()})();
