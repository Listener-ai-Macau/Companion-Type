// Synthetic browser regression. No Android, BLE, user recordings or cloud calls.
const {chromium}=require('@playwright/test');
const fs=require('fs');
const path=require('path');
const http=require('http');
const assert=require('assert/strict');
const dist=path.resolve('apps/mobile/dist');
const output=process.argv[2];
const server=http.createServer((req,res)=>{
 if(req.url==='/favicon.ico'){res.writeHead(204);return res.end();}
 const file=path.resolve(dist,'.'+new URL(req.url,'http://127.0.0.1').pathname);
 if(!file.startsWith(dist+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}
 res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);
});
let browser;
const result={result:'FAIL',scope:'SYNTHETIC_MOBILE_DOM_ONLY',observations:[],errors:[]};
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:390,height:844}});
 page.on('pageerror',error=>result.errors.push(error.message));
 page.on('console',message=>{if(message.type()==='error')result.errors.push(message.text());});
 await page.addInitScript(()=>{
  let tick=0;
  window.syntheticPlaybackTicks=()=>tick;
  window.CompanionNative={setAppearance(){},permissions(){},cancelTranscription(){},cancelMinutes(){},call(id,method,args){
   const a=JSON.parse(args);let value=null;
   if(method==='library')value={rows:['a','b'].map(key=>({key,title:'Synthetic recording '+key,session:key,state:'COMPLETE',segments:1,durationMs:60000})),problems:0};
   else if(method==='status')value={state:'complete',detail:'Synthetic local library',running:false,hasSavedTask:false};
   else if(method==='aiServiceStatus')value={configured:false,saved:false};
   else if(method==='detail')value={transcript:'',revision:0,before:null,minutes:null,minutesRevision:0,minutesChanged:false};
   else if(method==='play')value={complete:true,durationMs:60000};
   else if(method==='playbackStatus')value={playing:true,positionMs:++tick*1000};
   else if(method==='pausePlayback')value={positionMs:tick*1000};
   else if(method==='bookmarks')value={key:a.key,libraryToken:'synthetic-library',binding:'synthetic-binding',complete:true,marks:[{sequence:'1',sourceSamples:16000,elapsedMs:1000}]};
   else if(method==='minutesTemplates')value={templates:[]};
   queueMicrotask(()=>window.companionReply({id,result:value,error:null}));
  }};
 });
 await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
 const count=async(label)=>{const n=await page.locator('.device-bookmarks').count();result.observations.push({label,count:n});return n;};
 await page.getByRole('button',{name:/Synthetic recording a/}).click();
 await page.getByRole('button',{name:'播放录音',exact:true}).waitFor();
 assert.equal(await count('open-a'),1);
 await page.getByRole('button',{name:'读取设备重点',exact:true}).click();
 await page.getByRole('button',{name:/回听设备重点 1/}).waitFor();
 await page.getByRole('button',{name:'播放录音',exact:true}).click();
 await page.waitForFunction(()=>window.syntheticPlaybackTicks()>=4);
 assert.equal(await count('four-playback-ticks'),1,'Playback renders accumulated bookmark sections');
 await page.getByRole('button',{name:'暂停播放',exact:true}).click();
 assert.equal(await count('paused'),1);
 await page.getByRole('button',{name:'返回录音',exact:true}).click();
 assert.equal(await count('return-library'),0,'Bookmark sections survived leaving the recording');
 await page.getByRole('button',{name:/Synthetic recording b/}).click();
 await page.getByRole('button',{name:'播放录音',exact:true}).waitFor();
 assert.equal(await count('open-b'),1);
 assert.equal(await page.getByRole('button',{name:/回听设备重点 1/}).count(),0,'Previous recording bookmark state leaked');
 assert.equal(result.errors.length,0,result.errors.join('\n'));
 result.result='PASS_MOBILE_BOOKMARK_PLAYBACK_LIFECYCLE';
})().catch(error=>{result.failure=error.stack;process.exitCode=1;}).finally(async()=>{
 if(browser)await browser.close();server.close();
 if(output){fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n');}
 console.log(JSON.stringify(result,null,2));
});
