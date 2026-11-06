const fs=require('fs'),path=require('path');
const root='C:/Users/Billy/Desktop/Denzic/Companion/recovered-software050';
const {chromium}=require(root+'/node_modules/@playwright/test');
const folder='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-material-exports052/pptx-geometry-preview';
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--disable-gpu','--disable-extensions','--disable-background-networking']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});
  const inputs=JSON.parse(fs.readFileSync(path.join(folder,'inputs.json'),'utf8'));const rows=[];
  for(const [i,file] of inputs.files.entries()){
   await page.goto(require('url').pathToFileURL(file).href);await page.screenshot({path:path.join(folder,`slide-${i+1}.png`)});
   const overflow=await page.locator('.frame').evaluateAll(boxes=>boxes.filter(b=>b.scrollHeight>b.clientHeight+2||b.scrollWidth>b.clientWidth+2).map(b=>b.innerText));
   rows.push({slide:i+1,textFrameOverflow:overflow});
  }
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({scope:inputs.scope,rows},null,2));
  if(rows.some(r=>r.textFrameOverflow.length))throw Error('Native text frames overflow in local font preview');
  console.log(JSON.stringify({status:'PPTX_TEXT_FRAME_PREVIEW_CHECKED',slides:rows.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
