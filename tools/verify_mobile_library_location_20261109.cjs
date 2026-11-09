// Actual built mobile App with a controlled public native bridge. No phone/UI takeover.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('@playwright/test');
const root=path.resolve(__dirname,'..'),dist=path.join(root,'apps/mobile/dist');
const out='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-mobile-library-location';
fs.mkdirSync(out,{recursive:true});
const results=[];
(async()=>{
 const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://127.0.0.1'),relative=decodeURIComponent(url.pathname).replace(/^\/+/,''),file=path.resolve(dist,relative||'index.html');
  if(!file.startsWith(dist+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',file.endsWith('.html')?'text/html; charset=utf-8':file.endsWith('.css')?'text/css':'text/javascript');res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
 try{
  for(const mode of ['restored','receiving','bad-status','missing-original','late-status','original-only']){
   const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',error=>errors.push(error.message));
   let accept=false;page.on('dialog',dialog=>accept?dialog.accept():dialog.dismiss());
   await page.addInitScript(mode=>{
    localStorage.setItem('companion-theme','light');
    window.qaCalls=[];window.qaMode=mode;window.qaStatusHealthy=false;
    let active=['late-status','original-only'].includes(mode)?'original':'restore-public',statusReads=0;
    const location=()=>({version:1,activeId:active,token:'token-'+active,libraries:mode==='original-only'?[{id:'original',restoredAt:0}]:[{id:'original',restoredAt:0},{id:'restore-public',restoredAt:1794184200000}]});
    window.CompanionNative={setAppearance(){},finishApp(){},call(id,method,args){
     const input=JSON.parse(args||'{}');window.qaCalls.push({method,args:input});let result,error=null;
     if(method==='library')result={rows:[{key:active==='original'?'public-original':'public-restored',title:active==='original'?'公开原有会议':'公开恢复会议',session:'fixture',state:'COMPLETE',segments:1}],problems:0};
     else if(method==='status')result={state:mode==='receiving'?'receiving':'complete',detail:'',running:mode==='receiving',hasSavedTask:false};
     else if(method==='aiServiceStatus')result={configured:false,saved:false};
     else if(method==='libraryStatus'){
      statusReads++;result=location();
      if(mode==='bad-status'&&!window.qaStatusHealthy)result={...result,libraries:[...result.libraries,result.libraries[0]]};
      if(mode==='missing-original'&&!window.qaStatusHealthy)result={...result,libraries:result.libraries.filter(item=>item.id!=='original')};
      if(mode==='late-status'&&statusReads===1){const old={...location(),activeId:'restore-public',token:'stale-token'};setTimeout(()=>window.companionReply({id,result:old,error:null}),350);return;}
     }else if(method==='libraryActivate'){
      assertToken(input);active=input.id;result=location();
     }else if(method==='recordingTrash')result={rows:[],problems:0,libraryToken:'token-'+active};
     else error='Unexpected fixture call: '+method;
     queueMicrotask(()=>window.companionReply({id,result,error}));
    }};
    function assertToken(input){if(input.token!=='token-'+active||input.id!=='original')throw Error('Wrong library identity/token used');}
   },mode);
   await page.goto('http://127.0.0.1:'+server.address().port+'/');
   const card=page.getByRole('region',{name:'当前资料位置',exact:true});
   if(mode==='restored'){
    await card.getByRole('button',{name:'返回原有资料',exact:true}).waitFor();
    const layouts=[];
    for(const theme of ['light','dark']){
     for(const width of [360,393,430]){
      await page.setViewportSize({width,height:852});await page.locator('.mobile-app').evaluate((el,theme)=>el.setAttribute('data-theme',theme),theme);
      const dimensions=await page.evaluate(()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,cardWidth:document.querySelector('.library-location').scrollWidth,cardClient:document.querySelector('.library-location').clientWidth}));
      assert.ok(dimensions.documentWidth<=width&&dimensions.cardWidth<=dimensions.cardClient,JSON.stringify(dimensions));layouts.push({theme,...dimensions});
     }
     await page.setViewportSize({width:393,height:852});await page.screenshot({path:path.join(out,'restored-'+theme+'.png')});
    }
    await card.getByRole('button',{name:'返回原有资料',exact:true}).click();
    assert.equal(await page.evaluate(()=>window.qaCalls.filter(call=>call.method==='libraryActivate').length),0,'cancel must preserve current library');
    await page.getByRole('button',{name:/公开恢复会议/}).waitFor();
    accept=true;await card.getByRole('button',{name:'返回原有资料',exact:true}).click();
    await page.getByRole('button',{name:/公开原有会议/}).waitFor();await card.getByText('原有资料',{exact:true}).waitFor();
    assert.deepEqual(await page.evaluate(()=>window.qaCalls.filter(call=>call.method==='libraryActivate').map(call=>call.args)),[{id:'original',token:'token-restore-public'}]);
    await card.getByRole('button',{name:'备份与恢复',exact:true}).click();
    await page.getByRole('region',{name:'本机资料备份与恢复'}).waitFor();
    await page.getByRole('button',{name:'返回录音库',exact:true}).click();await page.getByRole('button',{name:/公开原有会议/}).waitFor();
    results.push({mode,result:'PASS',layouts,cancelPreserves:true,nativeTokenBound:true,settingsAndReturn:true});
   }else if(mode==='receiving'){
    await card.getByRole('button',{name:'返回原有资料',exact:true}).waitFor();assert.equal(await card.getByRole('button',{name:'返回原有资料',exact:true}).isDisabled(),true);
    assert.equal(await page.evaluate(()=>window.qaCalls.filter(call=>call.method==='libraryActivate').length),0);
    results.push({mode,result:'PASS',switchBlockedDuringReception:true});
   }else if(mode==='bad-status'||mode==='missing-original'){
    await card.getByRole('alert').waitFor();assert.equal(await card.getByRole('button',{name:'返回原有资料',exact:true}).count(),0);
    await page.evaluate(()=>window.qaStatusHealthy=true);await card.getByRole('button',{name:'重新读取资料信息'}).click();await card.getByRole('button',{name:'返回原有资料',exact:true}).waitFor();
    results.push({mode,result:'PASS',invalidSnapshotNotActionable:true,retryRecovers:true});
   }else if(mode==='late-status'){
    await page.getByRole('button',{name:/公开原有会议/}).waitFor();await card.getByText('原有资料',{exact:true}).waitFor();await page.waitForTimeout(450);
    assert.equal(await card.getByRole('button',{name:'返回原有资料',exact:true}).count(),0,'late old location must not replace current state');
    results.push({mode,result:'PASS',lateOldSnapshotExcluded:true});
   }else{
    await page.getByRole('button',{name:/公开原有会议/}).waitFor();await page.waitForFunction(()=>document.querySelector('.library-location-loading')===null);
    assert.equal(await card.count(),0,'ordinary single-library users need no extra switching card');
    results.push({mode,result:'PASS',ordinaryLibraryUncluttered:true});
   }
   assert.deepEqual(errors,[]);await page.close();
  }
  fs.writeFileSync(path.join(out,'browser-verification.json'),JSON.stringify({at:new Date().toISOString(),state:'PASS_BUILT_MOBILE_APP_CONTROLLED_BRIDGE_LIBRARY_LOCATION',results,phoneTested:false,systemPickerTested:false,privateUserDataUsed:false,modelRun:false},null,2));
  console.log('PASS built mobile App: restored/original identification, cancellation, guarded return, settings navigation, reception block, invalid status/retry, delayed old reply, 360/393/430 light+dark. No phone or OS UI.');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{fs.writeFileSync(path.join(out,'browser-failure.json'),JSON.stringify({error:String(error),stack:error.stack,results},null,2));console.error(error);process.exitCode=1;});
