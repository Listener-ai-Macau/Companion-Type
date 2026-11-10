// Built production App with an explicit fictional bridge. Not native-phone acceptance.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const code=process.argv[2]||'126';if(!['126','127'].includes(code))throw Error('Unsupported scoped version');
const root='C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109',out=path.join(__dirname,'android'+code);fs.mkdirSync(out,{recursive:true});
const {chromium}=require(root+'/node_modules/@playwright/test'),dist=path.resolve(root,'apps/mobile/dist');
const server=http.createServer((req,res)=>{const file=path.resolve(dist,'.'+new URL(req.url,'http://127.0.0.1').pathname);if(!file.startsWith(dist+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
let browser;
(async()=>{try{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
 const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{
  const rows=[{key:'fictional-one',title:'产品交付评审 · 决定与待办',session:'fictional-one',source:'importedAudio',state:'COMPLETE',segments:1,durationMs:5400000,organization:{folder:'客户会议/产品交付',tags:['待复核']}},{key:'fictional-two',title:'项目周会 · 本周进度',session:'fictional-two',source:'importedAudio',state:'COMPLETE',segments:1,durationMs:1800000,organization:{folder:'项目周会',tags:['本周']}}];
  let sync={state:'idle',running:false,hasSavedTask:false,detail:'原接收任务保留在另一份资料中；切回该资料后可继续。'},active='fixture-restored',empty=false;
  window.fixtureSync=value=>{sync=value;};window.fixtureEmpty=value=>{empty=value;};
  const lib=()=>({version:1,token:'fixture-token',activeId:active,libraries:[{id:'original',restoredAt:0},{id:'fixture-restored',restoredAt:1794272400000}]});
  window.CompanionNative={setAppearance(){},cancelAudioImport(){},call(id,method,json){let result,error=null;const a=JSON.parse(json);switch(method){
   case 'appPreferences':result={systemDark:false,defaultPlaybackSpeed:1,resumePlayback:true};break;
   case 'aiServiceStatus':result={configured:false,saved:false};break;
   case 'detail':result={revision:1,libraryToken:'fixture-token',transcript:'本次将核对两项交付，负责人和时间尚未确认。',minutes:{markdown:'## Summary\n- 两项交付待核对。\n\n## Decisions\n- None captured\n\n## Action Items\n- None captured'},playback:{positionMs:12000,speed:1}};break;
   case 'recordingNotes':result={key:a.key,libraryToken:'fixture-token',revision:1,entries:[{id:'fictional-note',text:'独立备注词：阅读后需要继续确认。',atMs:null,createdAt:1794272400000,updatedAt:1794272400000}]};break;
   case 'aiContext':result={libraryToken:'fixture-token',available:[],sourceVersion:'fixture',problems:0};break;
   case 'bookmarks':result={key:a.key,libraryToken:'fixture-token',binding:'fixture',complete:true,marks:[]};break;
   case 'stopPlayback':result={};break;
   case 'library':result={rows:empty?[]:a.query?a.query==='独立备注词'?[{...rows[0],matchSource:'notes',matchSnippet:'独立备注词：阅读后需要继续确认。',matchStart:0,matchEnd:5}]:rows.filter(r=>r.title.includes(a.query)):rows,problems:0,organization:{available:true,revision:2,libraryToken:'fixture-token'},searchQuery:a.query,searchScope:a.scope,searchProblems:0};break;
   case 'libraryStatus':result=lib();break;
   case 'activateLibrary':if(a.token!=='fixture-token')throw Error('Fixture token mismatch');active=a.id;result=lib();break;
   case 'audioImportStatus':result={running:false,state:'complete',message:'历史导入完成'};break;
   case 'status':result=sync;break;
   case 'recordingTrash':result={rows:[],problems:0,libraryToken:'fixture-token'};break;
   default:error='No fictional bridge implementation: '+method;
  }queueMicrotask(()=>window.companionReply({id,result,error}));}};
 });
 await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);await page.getByRole('button',{name:/产品交付评审/}).waitFor();
 const widths=[];
 for(const [width,height] of [[360,780],[393,852],[430,932]]){
  await page.setViewportSize({width,height});await page.locator('main').evaluate(el=>el.scrollTop=0);
  const geometry=await page.evaluate(()=>{const b=s=>{const e=document.querySelector(s);if(!e)throw Error(s);const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right};};return {width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,mainWidth:document.querySelector('main').scrollWidth,mainClient:document.querySelector('main').clientWidth,search:b('.search-label'),filters:b('.library-organization-filters'),first:b('.library-managed-list .row'),nav:b('.bottom-nav'),maintenance:b('.library-maintenance')};});
  if(geometry.documentWidth>width||geometry.mainWidth>geometry.mainClient||geometry.first.top>=geometry.nav.top||geometry.filters.bottom>=geometry.nav.top||geometry.maintenance.top<=geometry.first.top)throw Error('Library hierarchy/overflow '+JSON.stringify(geometry));widths.push(geometry);
 }
 await page.setViewportSize({width:393,height:852});await page.screenshot({path:path.join(out,'library'+code+'-source-light.png')});await page.getByRole('button',{name:'切换深色模式'}).click();await page.screenshot({path:path.join(out,'library'+code+'-source-dark.png')});
 await page.getByLabel('按文件夹筛选').selectOption('客户会议');await page.getByRole('button',{name:/产品交付评审/}).waitFor();if(await page.getByRole('button',{name:/项目周会 · 本周进度/}).count())throw Error('Parent folder filter');await page.getByLabel('按文件夹筛选').selectOption('*');
 await page.getByRole('searchbox').fill('本周');await page.getByRole('button',{name:/项目周会 · 本周进度/}).waitFor();if(await page.getByRole('button',{name:/产品交付评审/}).count())throw Error('Search filtered old row visible');await page.getByRole('searchbox').fill('');await page.getByRole('button',{name:/产品交付评审/}).waitFor();
 const active={state:'receiving',running:true,hasSavedTask:true,detail:'正在接收公开样例'};await page.evaluate(s=>window.fixtureSync(s),active);await page.getByRole('button',{name:'刷新',exact:true}).click();await page.getByRole('button',{name:'停止接收',exact:true}).waitFor();
 const activeGeometry=await page.locator('.status').boundingBox();if(!activeGeometry||activeGeometry.y>=widths[1].nav.top)throw Error('Active sync no longer prominent');
 await page.evaluate(()=>window.fixtureSync({state:'paused',running:false,hasSavedTask:true,detail:'公开样例待继续'}));await page.getByRole('button',{name:'刷新',exact:true}).click();await page.getByRole('button',{name:'继续原任务',exact:true}).waitFor();
 if(code==='127'){
  await page.evaluate(()=>window.fixtureSync({state:'idle',running:false,hasSavedTask:false,detail:''}));await page.getByRole('button',{name:'刷新',exact:true}).click();await page.getByRole('button',{name:/产品交付评审/}).click();await page.getByText('这份纪要未记录明确结论。',{exact:true}).waitFor();
  if(await page.getByRole('combobox',{name:'回听倍速',exact:true}).count())throw Error('Idle detail still shows disabled transport');const player=await page.locator('.player-card').boundingBox();if(!player||player.height>100)throw Error('Idle player not compact '+JSON.stringify(player));await page.screenshot({path:path.join(out,'reading127-source-dark.png')});
  await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('searchbox').fill('独立备注词');await page.getByText('人工备注',{exact:true}).waitFor();await page.locator('.library-managed-list .row').click();await page.locator('.recording-note mark').waitFor();if(await page.getByRole('tab',{name:'备注',exact:true}).getAttribute('aria-selected')!=='true')throw Error('Note hit did not open notes directly');await page.screenshot({path:path.join(out,'note-search127-source-dark.png')});await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('searchbox').fill('');
 }
 await page.evaluate(()=>{window.fixtureSync({state:'idle',running:false,hasSavedTask:false,detail:''});window.fixtureEmpty(true);});await page.getByRole('button',{name:'刷新',exact:true}).click();await page.getByText('已有录音，也可以从这里开始',{exact:true}).waitFor();await page.getByRole('button',{name:/连接录音卡/}).waitFor();
 if(errors.length)throw Error(errors.join('\n'));fs.writeFileSync(path.join(out,'source-visual-result.json'),JSON.stringify({at:new Date().toISOString(),state:'PRODUCTION_MOBILE_APP_FICTIONAL_BRIDGE_LIBRARY_HIERARCHY_PASSED',widths,errors,checks:['First recording/search/classification visible in 360/393/430 viewports','No horizontal overflow','Parent folder and literal search remain usable','Running and paused sync action remains prominent','Empty library retains full import welcome and device action'],nativePhoneQualified:false,ownerDataUsed:false,modelsRun:false},null,2));console.log('PASS production mobile library hierarchy, source-only fictional bridge.');
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}})().catch(e=>{console.error(e);process.exitCode=1;});
