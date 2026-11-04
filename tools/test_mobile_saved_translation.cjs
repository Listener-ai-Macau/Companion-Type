const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('@playwright/test');
const dist=path.resolve('apps/mobile/dist');
const output='E:/CodexData/Companion/core-meeting-delivery-20261104/translation-browser-check';
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const server=http.createServer((req,res)=>{
  const name=req.url.split('?')[0],file=path.join(dist,name==='/'?'index.html':name);
  if(!file.startsWith(dist)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
  res.setHeader('content-type',file.endsWith('.html')?'text/html':file.endsWith('.css')?'text/css':'text/javascript');res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true});const results=[];
 try{
  for(const mode of ['saved-light','saved-dark','stale','unreadable']){
   const page=await browser.newPage({viewport:{width:390,height:844}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(mode=>{
    localStorage.setItem('companion-theme',mode==='saved-dark'?'dark':'light');
    const original='周五之前核对报价，尚未确定负责人。';
    const translation={text:'金曜日までに見積もりを確認します。担当者は未確定です。',language:'ja',source:original,revision:1,saved:true};
    window.translationCalls=[];window.copiedTranslations=[];
    window.CompanionNative={setAppearance(){},copyTranslation(text){window.copiedTranslations.push(text);},
     call(id,method,args){window.translationCalls.push(method);let result;
      if(method==='library')result={rows:[{key:'saved-translation',title:'译文持久化测试',session:'one',state:'COMPLETE',segments:1}],problems:0};
      else if(method==='status')result={state:'complete',detail:'',running:false,hasSavedTask:false};
      else if(method==='detail')result={transcript:mode==='stale'?original+' 周一再讨论。':original,revision:mode==='stale'?2:1,before:null,minutes:null,minutesRevision:0,minutesChanged:false,translation:mode==='unreadable'?null:translation,translationUnreadable:mode==='unreadable'};
      else throw Error('Unexpected service request while reading saved text: '+method);
      queueMicrotask(()=>window.companionReply({id,result,error:null}));
     }};
   },mode);
   await page.goto('http://127.0.0.1:'+server.address().port+'/');
   const open=async()=>{await page.getByRole('button',{name:/译文持久化测试/}).click();await page.getByRole('tab',{name:'翻译',exact:true}).click();};
   await open();
   if(mode==='unreadable'){
    await page.getByText('已保存译文暂时无法读取，原文件已保留；录音和原文仍可使用。',{exact:true}).waitFor();
    await page.getByRole('tab',{name:'转写',exact:true}).click();
    assert.ok((await page.locator('main').innerText()).includes('周五之前核对报价'));
   }else{
    await page.getByText('金曜日までに見積もりを確認します。担当者は未確定です。',{exact:true}).waitFor();
    assert.equal(await page.getByLabel('目标语言').inputValue(),'ja');
    if(mode==='stale')await page.getByText('转写已更改，以下译文依据较早的文字，请重新翻译。',{exact:true}).waitFor();
    else{
     const savedText=await page.getByText('金曜日までに見積もりを確認します。担当者は未確定です。',{exact:true}).boundingBox();
     assert.ok(savedText&&savedText.y+savedText.height<774,'saved text must be readable before optional service setup');
     assert.equal(await page.locator('.translation-options').evaluate(element=>element.open),false);
     await page.getByRole('button',{name:'复制译文',exact:true}).click();
     assert.equal((await page.evaluate(()=>window.copiedTranslations))[0],'金曜日までに見積もりを確認します。担当者は未確定です。');
     await page.reload();await open();
     await page.getByText('金曜日までに見積もりを確認します。担当者は未確定です。',{exact:true}).waitFor();
     await page.screenshot({path:path.join(output,mode+'.png')});
    }
   }
   assert.ok(!(await page.evaluate(()=>window.translationCalls)).includes('translate'));
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(errors,[]);results.push({mode,result:'PASS',readingDoesNotCallAI:true});await page.close();
  }
 }finally{await browser.close();server.close();}
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({scope:'Built Android frontend in a browser with explicit saved-detail bridge fixture; no Android OS or cloud claim',results},null,2));
 console.log(JSON.stringify({state:'SAVED_TRANSLATION_READING_PASSED',results}));
})().catch(error=>{console.error(error);process.exitCode=1;});
