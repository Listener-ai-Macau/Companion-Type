// Public 61-minute meeting, synthetic native bridge: no phone or recording card.
const fs=require('node:fs');
const http=require('node:http');
const path=require('node:path');
const {chromium}=require('@playwright/test');
const fixture='E:/CodexData/Companion/public-long-meeting-mobile-20261103/';
const transcript=fs.readFileSync(fixture+'phone-transcript-61min.txt','utf8');
const minutes=JSON.parse(fs.readFileSync(fixture+'phone-real-minutes-after-lock-fix.json','utf8')).markdown;
const quote=minutes.split('## 分段原文依据')[1].split(/\r?\n/).map(x=>/^- (.+)$/.exec(x)?.[1]).find(Boolean);
const windows=fs.readFileSync(fixture+'phone-timing.tsv','utf8').trim().split(/\r?\n/).map(line=>{
  const [start,end,text]=line.split('\t');return {startMs:Number(start),endMs:Number(end),text:Buffer.from(text,'base64').toString('utf8')};
});
if(!quote||transcript.includes(quote)||windows.some(w=>w.text.includes(quote)))throw Error('fixture must exercise the original cross-window failure');
const root=path.resolve('apps/mobile/dist');
const server=http.createServer((req,res)=>{
  const file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
  if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
  res.setHeader('content-type',({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[path.extname(file)]||'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage({viewport:{width:390,height:844}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(({transcript,quote,windows})=>{
    window.CompanionNative={permissions(){},setAppearance(){},call(id,method){
      let result=null;
      if(method==='library')result={rows:[{key:'public',title:'公开会议',session:'public',state:'COMPLETE',segments:1}],problems:0};
      if(method==='status')result={state:'complete',detail:'录音已保存到手机',running:false,hasSavedTask:false};
      if(method==='detail')result={transcript,revision:1,before:null,minutes:{markdown:'## 会议概览\n\n公开会议\n\n## 分段原文依据\n\n### 第1段\n\n- '+quote},minutesRevision:1,minutesChanged:false};
      if(method==='timing')result={available:true,original:false,windows};
      queueMicrotask(()=>window.companionReply({id,result,error:null}));
    }};
  },{transcript,quote,windows});
  await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
  await page.getByRole('button',{name:/公开会议/}).click();
  await page.getByRole('tab',{name:'纪要'}).click();
  await page.getByText('展开核对').click();
  await page.getByRole('button',{name:'查看这条原话的位置'}).click();
  await page.getByText('已找到对应的原文时间段；点击该段可从近似位置回听。').waitFor();
  if(!await page.locator('#timing-window-3').evaluate(el=>el.classList.contains('timing-row-focus')))throw Error('expected first matching window was not highlighted');
  if(errors.length)throw Error('browser error: '+errors.join('; '));
  console.log('Public long-meeting source quote: cross-window location highlighted in headless mobile UI. Synthetic bridge only.');
 } finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
