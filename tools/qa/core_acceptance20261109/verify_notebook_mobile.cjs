const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root='C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109';
const {chromium,expect}=require(root+'/node_modules/@playwright/test');
const out=process.argv[2];assert(out);fs.mkdirSync(out,{recursive:false});
const dist=path.join(root,'apps/mobile/dist');let browser,server,page;const result={state:'CHECKING_NOTEBOOK_MOBILE_SOURCE',nativeQualified:false,modelsRun:false,hardwareQualified:false};
(async()=>{try{
 server=http.createServer((req,res)=>{const file=path.resolve(dist,'.'+new URL(req.url,'http://localhost').pathname);if(!file.startsWith(dist+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html; charset=utf-8');res.end(fs.readFileSync(file));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});page=await browser.newPage({viewport:{width:390,height:852},locale:'zh-CN'});const errors=[];result.pageErrors=errors;page.on('pageerror',error=>errors.push(error.stack||String(error)));
 const retained=fs.readFileSync(root+'/tools/mobile-bridge-smoke.cjs','utf8');const begin=retained.indexOf('await page.addInitScript(()=>{'),end=retained.indexOf('\n  await page.goto',begin);assert(begin>=0&&end>begin);
 const fixture=retained.slice(begin,end).replaceAll("state:'COMPLETE',segments:1","state:'COMPLETE',segments:1,recordedAtUnixSeconds:1794474000,durationMs:23000");await new Function('page','return (async()=>{'+fixture+'})();')(page);
 await page.addInitScript(()=>{
  const original=window.CompanionNative.call.bind(window.CompanionNative);window.fixtureMethods=[];
  const contracts={incomingFiles:{rows:[]},audioImportStatus:{running:false,state:'idle'},libraryStatus:{version:1,activeId:'original',token:'public-source-fixture',libraries:[{id:'original',restoredAt:0}]},appPreferences:{defaultPlaybackSpeed:1,resumePlayback:true,systemDark:false,bluetoothAllowed:true,notificationsAllowed:true,version:'0.1.145'},aiServiceStatus:{configured:false,saved:false}};
  window.CompanionNative.call=(id,method,args)=>{window.fixtureMethods.push(method);const a=JSON.parse(args);let value=contracts[method];
   if(method==='documentContexts')value={contextId:a.key,libraryToken:'public-source-fixture',revision:0,rows:[]};
   if(method==='aiMaterials')value=[];
   if(method==='aiContext')value={libraryToken:'public-source-fixture',available:[],sourceVersion:'public-v1',problems:0};
   if(method==='recordingNotes')value={key:a.key,libraryToken:'public-source-fixture',revision:0,entries:[]};
   if(method==='minutesTemplates')value={version:1,libraryToken:'public-source-fixture',etag:'empty',items:[],selected:{id:'meeting'}};
   if(method==='exportInfo')value={key:a.key,title:'公开虚构录音',libraryToken:'public-source-fixture',binding:'public-binding',available:{minutes:true,transcript:true,translation:false,notes:false},materials:[],manualNotes:[],minutesStale:false,minutesDraft:false,minutesManual:false,translationStale:false,translationLanguage:'',problems:[]};
   if(method==='prepareExport')value={id:'public-export',filename:'public.pdf',mime:'application/pdf',bytes:100,copyAllowed:true,preview:'公开虚构录音\n讨论进度',warnings:[]};
   if(value!==undefined)queueMicrotask(()=>window.companionReply({id,result:value,error:null}));else original(id,method,args);};
  window.CompanionNative.exportPrepared=id=>queueMicrotask(()=>window.companionReply({id,result:false,error:null}));
 });
 await page.route('**/*',route=>route.request().url().startsWith(origin)?route.continue():route.abort());
 await page.goto(origin+'/index.html');await page.locator('.row').first().waitFor();
 await expect(page.getByRole('heading',{name:'我的录音',exact:true})).toBeVisible();
 await expect(page.locator('#library-import-panel')).toBeHidden();
 await page.getByRole('button',{name:'＋ 导入',exact:true}).click();await expect(page.getByRole('region',{name:'导入音视频',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'＋ 导入',exact:true}).click();
 assert.equal(await page.locator('.library-filter-details').evaluate(node=>node.open),false);
 for(const width of [320,390,736]){await page.setViewportSize({width,height:852});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
 await page.setViewportSize({width:390,height:852});await page.screenshot({path:out+'/library-light.png'});
 await page.locator('.row').first().click();
 await expect(page.getByRole('heading',{name:'2026/11/12 17:00 的录音',exact:true})).toBeVisible();
 assert.equal(await page.getByRole('tablist',{name:'录音内容',exact:true}).getByRole('tab').count(),3);
 await page.getByRole('tab',{name:'文字',exact:true}).click();await page.getByRole('button',{name:'编辑',exact:true}).click();
 const editor=page.getByRole('dialog',{name:'编辑转写',exact:true});await editor.getByRole('textbox',{name:'转写文字',exact:true}).fill('公开修订：小林周五确认演示名单。');
 await editor.getByRole('button',{name:'保存',exact:true}).click();await expect(editor).toBeHidden();
 await expect(page.locator('#detail-panel-transcript')).toContainText('公开修订：小林周五确认演示名单。');
 await page.locator('.recording-content-more>summary').click();await page.getByRole('button',{name:'思维导图',exact:true}).click();await expect(page.locator('#detail-panel-mindmap')).toBeVisible();
 await page.getByRole('tab',{name:'纪要',exact:true}).click();await page.getByRole('button',{name:'前往导出',exact:true}).click();
 await expect(page.locator('.export-card')).toHaveAttribute('open','');
 await expect(page.getByLabel('导出文件格式')).toBeVisible();
 await page.getByRole('button',{name:'返回录音',exact:true}).click();await page.locator('.row').first().click();await page.getByRole('tab',{name:'文字',exact:true}).click();
 await expect(page.locator('#detail-panel-transcript')).toContainText('公开修订：小林周五确认演示名单。');
 for(const theme of ['light','dark']){
  await page.locator('.mobile-app').evaluate((el,t)=>el.dataset.theme=t,theme);
  for(const width of [320,390,736]){await page.setViewportSize({width,height:852});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.setViewportSize({width:390,height:852});await page.locator('main').evaluate(el=>el.scrollTop=0);await page.screenshot({path:out+`/detail-${theme}.png`});
 }
 await page.getByRole('button',{name:'返回录音',exact:true}).click();await page.locator('.row').filter({hasText:'未转写示例'}).click();await expect(page.getByRole('button',{name:'本地转写',exact:true})).toBeVisible();
 result.fixtureMethods=await page.evaluate(()=>window.fixtureMethods);assert.deepEqual(errors,[]);result.state='NOTEBOOK_MOBILE_REAL_SOURCE_CONTINUOUS_JOURNEY_PASSED';result.covered=['library/import disclosure','three main reading panes, auxiliary views in More','actual editor UI saves via synthetic native bridge','return and reopen retains saved revision in bridge','fixed export entry opens real content export','untranscribed recording opens usable transcription','320/390/736 light/dark without horizontal overflow'];
}catch(error){result.error=String(error);if(page){result.fixtureMethods=await page.evaluate(()=>window.fixtureMethods);await page.screenshot({path:out+'/failure.png',fullPage:true});fs.writeFileSync(out+'/failure-body.txt',await page.locator('body').innerText());}throw error;}
finally{if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));fs.writeFileSync(out+'/result.json',JSON.stringify(result,null,2));}})().catch(error=>{console.error(error);process.exitCode=1});
