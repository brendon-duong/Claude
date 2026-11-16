const {chromium}=require('playwright');const fs=require('fs');(async()=>{
const v=process.argv[2],only=process.argv[3],clip=process.env.CLIP||0;const S=async(pg,t)=>pg.evaluate(async t=>{seek(+t);const i=document.getElementById('clip');if(i.src){try{await i.decode()}catch(e){}}},t);const b=await chromium.launch();const pg=await b.newPage({viewport:{width:1080,height:1920}});
await pg.goto('file://'+__dirname+'/video.html?clip='+clip+'&v='+v);await pg.evaluate(()=>document.fonts.ready);
if(only){for(const t of only.split(',')){await S(pg,t);await pg.screenshot({path:`chk_${v}_${t}.jpg`,type:'jpeg',quality:70});}}
else{fs.mkdirSync('frames_'+v,{recursive:true});const fps=30,n=15*fps;for(let i=0;i<n;i++){await S(pg,i/fps);await pg.screenshot({path:`frames_${v}/f${String(i).padStart(4,'0')}.jpg`,type:'jpeg',quality:95});}}
await b.close()})();
