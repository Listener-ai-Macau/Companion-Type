const fs=require('fs'),path=require('path'),http=require('http'),assert=require('node:assert/strict');
const S='C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055',A='C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109',O='E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113';
const stage=process.argv[2]||'baseline',Q=path.join(O,'library-closure20261114',stage);fs.mkdirSync(Q,{recursive:false});
const{build}=require(S+'/node_modules/esbuild'),{chromium}=require(S+'/node_modules/@playwright/test');
const original=JSON.parse(fs.readFileSync(O+'/note-readability-public-native129/minutes.json','utf8'));
const rows=['产品周会','客户访谈','设计评审'].map((title,i)=>({...original,id:'synthetic-ui-'+i,title:'公开界面测试 · '+title,startedAt:'2026-11-'+(12+i)+'T01:00:00Z',organization:{revision:1,folder:i===1?'客户':'工作/产品',tags:[i===1?'访谈':'待跟进'],favorite:false,protected:false,trashedAt:null}}));
const entry="import React from 'react';import{createRoot}from'react-dom/client';import{createCompanionV1Fixture}from'./packages/core/src/companionV1';import{CompanionDashboard}from'./packages/ui/src/CompanionDashboard';import'./packages/ui/src/companionUi.css';import'./packages/ui/src/notebookFoundation.css';import'./packages/ui/src/meetingNoteDocument.css';const snapshot=createCompanionV1Fixture();snapshot.host.sessions="+JSON.stringify(rows)+";snapshot.host.selectedSessionId=snapshot.host.sessions[0].id;snapshot.host.persistence={status:'ready'};createRoot(document.getElementById('root')).render(<CompanionDashboard snapshot={snapshot} surface='windows' busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}} onSaveLibraryOrganization={async()=>snapshot} onExportLibrary={async()=>null} onBackupLibrary={async()=>null} onRestoreLibrary={async()=>null}/>);";
(async()=>{let server,browser,win,phone;const result={scope:'Actual production UI and styles with declared synthetic/public-only data. Browser adapter, not native/backend/model acceptance.',modelsRun:false,ownerDesktopUsed:false,stage,checks:[],errors:[]};
try{
 const testedEntry=entry.replace('onSaveLibraryOrganization={async()=>snapshot}','onSaveLibraryOrganization={async(request)=>{window.capturedLibraryRequests??=[];window.capturedLibraryRequests.push(request);return snapshot;}}');
 await build({stdin:{contents:testedEntry,resolveDir:S,sourcefile:'library-review.tsx',loader:'tsx'},outfile:Q+'/windows.js',bundle:true,platform:'browser',format:'iife',jsx:'automatic',tsconfig:S+'/apps/windows/tsconfig.json',define:{'process.env.NODE_ENV':'"production"'}});
 server=http.createServer((req,res)=>{const u=new URL(req.url,'http://localhost');let p;if(u.pathname==='/windows'){res.setHeader('Content-Type','text/html;charset=utf-8');res.end('<html><head><meta charset="utf-8"><link rel="stylesheet" href="/windows.css"></head><body style="margin:0"><div id="root"></div><script src="/windows.js"></script></body></html>');return;}
 if(['/windows.js','/windows.css'].includes(u.pathname))p=Q+u.pathname;else p=path.join(A,'apps/mobile/dist',u.pathname==='/'?'index.html':u.pathname);
 if(!fs.existsSync(p)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',p.endsWith('.js')?'text/javascript':p.endsWith('.css')?'text/css':p.endsWith('.html')?'text/html;charset=utf-8':'application/octet-stream');res.end(fs.readFileSync(p));});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});win=await browser.newPage({viewport:{width:1440,height:1000},locale:'zh-CN'});win.on('pageerror',e=>result.errors.push(e.message));
 await win.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());await win.goto(base+'/windows');await win.locator('.ct-library-card').first().waitFor();
 await win.getByRole('button',{name:'管理',exact:true}).click();const manager=win.getByRole('dialog',{name:'管理录音',exact:true});await manager.waitFor();await win.screenshot({path:Q+'/desktop-manage-empty.png'});
 result.checks.push({platform:'windows',case:'empty management',visibleInputs:await manager.locator('input:visible,select:visible').count(),text:(await manager.innerText()).slice(0,500)});
 if(stage!=='baseline'){
  assert.equal(await manager.locator('input:visible,select:visible').count(),0);
  await manager.getByRole('button',{name:'返回列表选择',exact:true}).click();await manager.waitFor({state:'hidden'});
  const rowChecks=win.locator('.ct-library-list .ct-library-entry>input');await rowChecks.first().waitFor();assert(await rowChecks.first().evaluate(e=>e===document.activeElement));await rowChecks.first().check();
  await win.getByRole('button',{name:'整理所选',exact:true}).click();await manager.waitFor();assert((await manager.locator('.ct-library-target-summary').innerText()).includes(rows[0].title));
  await manager.getByLabel('修改文件夹',{exact:true}).check();await manager.getByLabel('目标录音文件夹',{exact:true}).fill('工作/验收');
  assert(await manager.getByRole('button',{name:'清除整理选择',exact:true}).isDisabled());
  await manager.getByRole('button',{name:'关闭录音面板',exact:true}).click();assert(await manager.isVisible());assert((await manager.innerText()).includes('还有未保存'));
  await manager.getByRole('button',{name:'保存 1 场分类',exact:true}).click();await manager.getByRole('button',{name:'返回列表选择',exact:true}).waitFor();
  const requests=await win.evaluate(()=>window.capturedLibraryRequests);assert.equal(requests.length,1);assert.deepEqual(requests[0].targets,[{sessionId:rows[0].id,expectedRevision:1}]);assert.equal(requests[0].folder,'工作/验收');
  result.checks.push({platform:'windows',case:'choose one -> exact target/draft guard -> save',capturedRequest:requests[0],nativeBackendCalled:false});
 }
 await manager.getByRole('button',{name:'关闭录音面板',exact:true}).click();await win.getByRole('button',{name:'筛选',exact:true}).click();await win.getByLabel('筛选录音文件夹',{exact:true}).selectOption('工作');await win.getByRole('button',{name:'关闭录音面板',exact:true}).click();await win.screenshot({path:Q+'/desktop-filtered-library.png'});
 result.checks.push({platform:'windows',case:'active filter',visibleActiveFilterLabels:await win.locator('.ct-library-active-filters').count(),remainingRows:await win.locator('.ct-library-card').count()});
 if(stage!=='baseline'){
  const chips=win.getByRole('group',{name:'当前筛选',exact:true});assert((await chips.innerText()).includes('工作'));
  await win.getByRole('textbox',{name:'搜索标题、转写、补充或整理结果',exact:true}).fill('公开界面测试');
  await win.getByRole('button',{name:'筛选',exact:true}).click();await win.getByLabel('筛选录音开始日期',{exact:true}).fill('2026-11-14');await win.getByLabel('筛选录音结束日期',{exact:true}).fill('2026-11-12');await win.getByRole('button',{name:'关闭录音面板',exact:true}).click();
  assert((await win.locator('.ct-library-scope-warning').first().innerText()).includes('日期范围有误'));
  await chips.getByRole('button',{name:'取消日期筛选',exact:true}).click();await chips.getByRole('button',{name:'清除筛选',exact:true}).click();
  assert.equal(await win.getByRole('textbox',{name:'搜索标题、转写、补充或整理结果',exact:true}).inputValue(),'公开界面测试');assert.equal(await win.locator('.ct-library-card').count(),3);
  await win.waitForFunction(()=>document.activeElement?.id==='ct-library-filter-button');
  await win.getByRole('button',{name:'取消选择',exact:true}).click();await win.getByRole('button',{name:'管理',exact:true}).click();await manager.getByRole('button',{name:'返回列表选择',exact:true}).waitFor();assert.equal(await manager.locator('input:visible,select:visible').count(),0);await manager.getByRole('button',{name:'关闭录音面板',exact:true}).click();
  for(const width of [1024,1440]){await win.setViewportSize({width,height:1000});assert(await win.evaluate(()=>document.body.scrollWidth<=innerWidth));}
 }
 phone=await browser.newPage({viewport:{width:390,height:852},locale:'zh-CN',isMobile:true,hasTouch:true});phone.on('pageerror',e=>result.errors.push(e.message));
 const retained=fs.readFileSync(A+'/tools/mobile-bridge-smoke.cjs','utf8'),begin=retained.indexOf('await page.addInitScript(()=>{'),end=retained.indexOf('\n  await page.goto',begin);assert(begin>=0&&end>begin);await new Function('page','return (async()=>{'+retained.slice(begin,end)+'})();')(phone);
 await phone.addInitScript(()=>{
  const original=window.CompanionNative.call.bind(window.CompanionNative);
  const rows=['产品周会','客户访谈','设计评审'].map((title,i)=>({key:i===0?'synthetic':i===1?'new':'third',title:'公开界面测试 · '+title,session:String(i+1),state:'COMPLETE',segments:1,durationMs:90000,recordedAtUnixSeconds:1794445200+i*86400,organization:{folder:i===1?'客户':'工作/产品',tags:[i===1?'访谈':'待跟进']},lifecycle:{revision:1,protected:false}}));
  const contracts={library:{rows,problems:0,organization:{available:true,revision:1,libraryToken:'synthetic-ui-library'}},incomingFiles:{rows:[]},audioImportStatus:{running:false,state:'idle'},libraryStatus:{version:1,activeId:'original',token:'synthetic-ui-library',libraries:[{id:'original',restoredAt:0}]},status:{state:'idle',detail:'',running:false,hasSavedTask:false},appPreferences:{defaultPlaybackSpeed:1,resumePlayback:true,systemDark:false,bluetoothAllowed:true,notificationsAllowed:true,version:'0.1.157'},aiServiceStatus:{configured:false,saved:false}};
  window.CompanionNative.call=(id,method,args)=>{if(contracts[method]!==undefined)queueMicrotask(()=>window.companionReply({id,result:contracts[method],error:null}));else original(id,method,args);};
 });
 await phone.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());await phone.goto(base+'/');await phone.locator('.library-managed-list .row').first().waitFor();
 await phone.getByRole('button',{name:'选择',exact:true}).click();await phone.locator('.library-row-check input').first().check();await phone.locator('main').evaluate(e=>e.scrollTop=0);
 await phone.screenshot({path:Q+'/phone-one-selected.png'});
 result.checks.push({platform:'mobile',case:'one selected',layout:await phone.evaluate(()=>{const first=document.querySelector('.library-managed-row'),panel=document.querySelector('.library-management-panel');return{firstRowTop:first.getBoundingClientRect().top,actionPanelHeight:panel?.getBoundingClientRect().height,viewport:innerHeight};})});
 if(stage!=='baseline'){
  const panel=phone.locator('.library-management-panel');assert.equal(await panel.evaluate(e=>e.open),false);assert.equal(await phone.getByLabel('目标文件夹',{exact:true}).isVisible(),false);
  const geometry=await phone.evaluate(()=>{const r=document.querySelectorAll('.library-managed-row'),main=document.querySelector('main').getBoundingClientRect();return{first:r[0].getBoundingClientRect().bottom,second:r[1].getBoundingClientRect().top,mainBottom:main.bottom};});assert(geometry.first<=geometry.mainBottom&&geometry.second<geometry.mainBottom);
  await phone.locator('.library-row-check input').nth(1).check();await panel.locator(':scope>summary').click();await phone.getByLabel('目标文件夹',{exact:true}).fill('工作/待确认');await panel.locator(':scope>summary').click();assert((await panel.locator(':scope>summary').innerText()).includes('未应用'));
  phone.once('dialog',d=>d.dismiss());await phone.getByRole('button',{name:'取消选择',exact:true}).click();assert.equal(await phone.locator('.library-row-check input:checked').count(),2);
  phone.once('dialog',d=>d.accept());await phone.getByRole('button',{name:'取消选择',exact:true}).click();assert.equal(await phone.locator('.library-row-check input:checked').count(),0);
  await phone.getByRole('button',{name:'完成',exact:true}).click();const filters=phone.locator('.library-filter-details');await filters.locator(':scope>summary').click();await phone.getByLabel('按文件夹筛选',{exact:true}).selectOption('工作');await phone.getByLabel('按标签筛选',{exact:true}).selectOption('待跟进');await filters.locator(':scope>summary').click();
  const chips=phone.getByRole('group',{name:'当前筛选',exact:true});assert((await chips.innerText()).includes('工作'));await chips.getByRole('button',{name:'取消文件夹筛选',exact:true}).click();assert.equal(await phone.locator('.library-managed-row').count(),2);await chips.getByRole('button',{name:'清除筛选',exact:true}).click();assert.equal(await phone.locator('.library-managed-row').count(),3);
  result.checks.push({platform:'mobile',case:'multi selection/hidden draft cancel and filter reset',selectionPreservedOnDismiss:true,draftDiscardExplicit:true,firstAndNextTargetsVisible:true});
 }
 for(const width of [320,390,736]){await phone.setViewportSize({width,height:852});assert(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
 assert.deepEqual(result.errors,[]);result.state=stage==='baseline'?'PRODUCTION_UI_BASELINE_CAPTURED':'PRODUCTION_UI_SCOPE_SELECTION_AND_DRAFT_FLOW_PASSED';
}catch(e){result.error=String(e);for(const[name,page]of[['windows',win],['mobile',phone]])if(page){await page.screenshot({path:Q+'/failure-'+name+'.png'}).catch(()=>{});fs.writeFileSync(Q+'/failure-'+name+'.txt',await page.locator('body').innerText());}throw e;}finally{if(browser)await browser.close();if(server)await new Promise(r=>server.close(r));fs.writeFileSync(Q+'/result.json',JSON.stringify(result,null,2));}})().catch(e=>{console.error(e);process.exitCode=1;});
