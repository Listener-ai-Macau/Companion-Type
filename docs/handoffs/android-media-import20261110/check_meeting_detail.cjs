const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const followup=process.argv.includes('--followup');
const R='C:/Users/Billy/Desktop/Denzic/Companion',S=R+'/companion-device-closure055',A=R+'/companion-core-android20261109',O=__dirname+(followup?'/followup-108141':'/meeting-detail-finish');
const{build}=require(S+'/node_modules/esbuild'),{chromium}=require(S+'/node_modules/@playwright/test');
const cache='E:/CodexData/Companion/.build-cache/document-context20261110/node-dependencies/.cache/detail-finish-'+Date.now(),roots={mobile:A,windows:S};
fs.mkdirSync(cache,{recursive:true});fs.mkdirSync(O,{recursive:true});
let browser,server;const result={at:new Date().toISOString(),state:'CHECKING_SOURCE_RENDER_ONLY',nativeQualified:false,modelsRun:false,checks:[]};
(async()=>{try{
 for(const[platform,root]of Object.entries(roots)){
  const entry=root+'/.cache/detail-finish-entry.tsx';
  const common=["import React from 'react';import{createRoot}from'react-dom/client';import{MeetingReferenceWorkspace}from'../packages/ui/src/MeetingReferenceWorkspace';",
   platform==='mobile'?"import{RecordingNotes}from'../apps/mobile/src/RecordingNotes';":"import{CompanionMeetingNotes}from'../packages/ui/src/CompanionMeetingNotes';",
   "import{MeetingAiWorkbench}from'../packages/ui/src/MeetingAiWorkbench';import{TranscriptQuoteCapture}from'../packages/ui/src/TranscriptQuoteCapture';",
   "const initial={id:'one',text:'公开排版用例｜下次沟通准备\\n- [ ] 核对预算原件\\n这段说明仍在两条事项之间。\\n- [ ] 确认负责人',atMs:null,bookmarkId:null,kind:'followup',createdAt:1794348000000,updatedAt:1794348000000,references:[{id:'11111111-1111-4111-8111-111111111111',kind:'document',name:'预算讨论附件及下次沟通准备材料.xlsx',sectionLabel:'工作表：预算草案',row:2,sourceSha256:'a'.repeat(64),quote:'A2 人工补充\\nB2 12,000.00\\nC2 FALSE\\nD2 0\\nE2 原表备注完整保留。'}]};",
   "function View(){const[view,setView]=React.useState('notes'),[entry,setEntry]=React.useState(initial),[opened,setOpened]=React.useState(0),[captured,setCaptured]=React.useState(null);const session={id:'public-layout',title:'公开排版用例',status:'saved',audioStored:true,noteRevision:1,meetingNotes:[entry],bookmarks:[]};const value={key:'public-layout',libraryToken:'public',revision:1,entries:[entry]};",
   platform==='mobile'?"const notes=<RecordingNotes recordingKey='public-layout' busy={false} positionMs={0} durationMs={0} onLoad={async()=>value} onSave={async(v,d)=>{const e={...entry,...d};setEntry(e);return{...v,revision:v.revision+1,entries:[e]}}} onImage={async()=>({cancelled:true})} onRemove={async()=>value} onPlay={async()=>{}} onDirtyChange={()=>{}} onExport={()=>{}} onOpenEvidence={async()=>setOpened(v=>v+1)}/>;":"const notes=<CompanionMeetingNotes compact session={session} blocked={false} anyRecording={false} persistenceReady onSave={async()=>({host:{sessions:[session],persistence:{status:'ready'}}})} onSeek={async()=>{}} onOpenEvidence={async()=>setOpened(v=>v+1)}/>;",
   "const assistant=<MeetingAiWorkbench contextId='public-layout' contextVersion='1' title='公开排版用例' scopes={[]} serviceReady={false} busy={false} onSetup={()=>{}} onOpenDocuments={()=>setView('documents')} onOpenNotes={()=>setView('notes')} onAsk={async()=>{throw Error('排版预览不运行AI')}} onCancel={async()=>true} onLoadSaved={async()=>[]} onSave={async()=>{throw Error('排版预览不保存生成结果')}} onCopy={async()=>{}} onOpenSource={async()=>{}}/>;",
   "return <><MeetingReferenceWorkspace view={view} onViewChange={setView} notes={notes} documents={<p>公开排版用例：文档阅读仍使用产品原入口。</p>} assistant={assistant}/><output id='opened'>{opened}</output>{followup&&<TranscriptQuoteCapture contextId='public-layout' text={'原始公开用例。'.repeat(80)+'预算 FALSE 0 尚未确认。'} onQuote={setCaptured}/>}<output id='captured'>{JSON.stringify(captured)}</output></>};createRoot(document.getElementById('app')).render(<View/>);"].join('\n');
  fs.writeFileSync(entry,'const followup='+JSON.stringify(followup)+';\n'+common);await build({entryPoints:[entry],outfile:cache+'/'+platform+'.js',bundle:true,platform:'browser',format:'iife',jsx:'automatic',tsconfig:root+'/apps/windows/tsconfig.json'});
  const styles=platform==='mobile'?['apps/mobile/src/mobile.css','apps/mobile/src/mobileRefinement.css','apps/mobile/src/mobilePremium.css','apps/mobile/src/recordingNotes.css','apps/mobile/src/aiWorkspace.css']:['packages/ui/src/companionUi.css','packages/ui/src/companionDesign.css','packages/ui/src/companionDark.css','apps/windows/src/workspaceRefinement.css'];
  fs.writeFileSync(cache+'/'+platform+'-global.css',styles.map(name=>fs.readFileSync(root+'/'+name,'utf8')).join('\n'));
 }
 server=http.createServer((req,res)=>{const url=new URL(req.url,'http://localhost');if(url.pathname==='/'){
  const platform=url.searchParams.get('platform'),theme=url.searchParams.get('theme');assert(platform in roots);
  res.setHeader('Content-Type','text/html; charset=utf-8');res.end('<!doctype html><html lang="zh-CN"><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/'+platform+'-global.css"><link rel="stylesheet" href="/'+platform+'.css"><style>body{margin:0}#wrap{display:block;padding:20px;min-height:100vh;box-sizing:border-box}#app{max-width:800px;margin:auto}#opened,#captured{display:none}.preview-notice{max-width:800px;margin:auto;font-size:11px;opacity:.65}</style></head><body><div id="wrap" class="'+(platform==='mobile'?'mobile-app':'ct-shell ct-windows '+(theme==='dark'?'ct-theme-dark':''))+'" data-theme="'+theme+'"><p class="preview-notice">公开排版用例 · 源码预览，非原生验收或AI结果</p><div id="app"></div></div><script src="/'+platform+'.js"></script></body></html>');return;
  }const name=path.basename(url.pathname);if(!/^(mobile|windows)(-global)?\.(js|css)$/.test(name)){res.writeHead(404);res.end();return}res.setHeader('Content-Type',name.endsWith('.css')?'text/css':'text/javascript');res.end(fs.readFileSync(cache+'/'+name));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
 const context=await browser.newContext({serviceWorkers:'block'});await context.route('**/*',route=>route.request().url().startsWith(origin+'/')?route.continue():route.abort());const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 for(const platform of ['mobile','windows'])for(const width of platform==='mobile'?[360,393]:[1000,1280])for(const theme of ['light','dark']){
  await page.setViewportSize({width,height:1000});await page.goto(origin+'/?'+new URLSearchParams({platform,theme}));await page.getByRole('checkbox',{name:'核对预算原件',exact:true}).waitFor();
  const cdp=await context.newCDPSession(page);await cdp.send('DOM.enable');await cdp.send('CSS.enable');const dom=await cdp.send('DOM.getDocument');const node=await cdp.send('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'.manual-evidence-heading strong'});const font=await cdp.send('CSS.getPlatformFontsForNode',{nodeId:node.nodeId});await cdp.detach();const family=await page.locator('.manual-evidence-heading strong').evaluate(n=>getComputedStyle(n).fontFamily);
  const shape=await page.locator('.manual-evidence').evaluate(node=>({height:node.getBoundingClientRect().height,open:node.querySelector('details').open,documentWidth:document.documentElement.scrollWidth,viewportWidth:innerWidth}));
  assert(!shape.open);assert(shape.height<190);assert(shape.documentWidth<=shape.viewportWidth);assert(!await page.locator('.manual-evidence blockquote').isVisible());
  await page.getByRole('button',{name:'查看当前依据',exact:true}).click();assert.equal(await page.locator('#opened').textContent(),'1');
  await page.locator('.manual-evidence-expand').click();assert(await page.locator('.manual-evidence blockquote').isVisible());assert((await page.locator('.manual-evidence blockquote').textContent()).includes('C2 FALSE\nD2 0'));
  await page.locator('.manual-evidence-collapse').click();assert(!await page.locator('.manual-evidence blockquote').isVisible());const check=page.getByRole('checkbox',{name:'核对预算原件',exact:true}),size=await check.boundingBox();assert.equal(size.width,18);assert.equal(size.height,18);
  if(width===393||width===1280)await page.screenshot({path:O+'/'+platform+'-notes-'+theme+'.png',fullPage:true});
  await page.getByRole('tab',{name:'AI 助手',exact:true}).click();await page.getByRole('tabpanel',{name:'AI 助手',exact:true}).waitFor();if(width===393||width===1280)await page.screenshot({path:O+'/'+platform+'-assistant-'+theme+'.png',fullPage:true});
  await page.getByRole('tab',{name:'便签与图片',exact:true}).click();assert.equal(await page.locator('.manual-evidence').count(),1);assert.equal(await page.getByRole('checkbox').count(),2);
  if(followup){
   await page.getByRole('button',{name:/^编辑备注 /}).click();
   await page.getByRole('textbox',{name:'跟进事项 2',exact:true}).fill('核对预算原件，暂未确认');
   await page.getByRole('textbox',{name:'新增跟进事项',exact:true}).fill('确认实际日期，不自动猜');
   assert.equal(await page.getByRole('textbox',{name:'跟进事项 5',exact:true}).inputValue(),'确认实际日期，不自动猜');
   await page.getByRole('button',{name:'按原格式编辑',exact:true}).click();
   const raw=page.getByRole('textbox',{name:platform==='mobile'?'备注内容':'编辑备注 one',exact:true});
   assert((await raw.inputValue()).includes('这段说明仍在两条事项之间。'));assert((await raw.inputValue()).includes('- [ ] 确认实际日期，不自动猜'));
   await page.getByRole('button',{name:'按事项编辑',exact:true}).click();
   await page.getByRole('tab',{name:'AI 助手',exact:true}).click();await page.getByRole('tab',{name:'便签与图片',exact:true}).click();assert.equal(await page.getByRole('textbox',{name:'跟进事项 2',exact:true}).inputValue(),'核对预算原件，暂未确认');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(width===393||width===1280)await page.screenshot({path:O+'/'+platform+'-ordinary-editor-'+theme+'.png',fullPage:true});
   await page.getByRole('button',{name:'引用转写到备注',exact:true}).click();await page.getByRole('searchbox',{name:'查找可引用的原文',exact:true}).fill('预算 FALSE 0');
   const literal=await page.locator('.manual-quote-options blockquote').first().textContent();assert(literal.includes('预算 FALSE 0 尚未确认。'));
   if(width===393||width===1280)await page.screenshot({path:O+'/'+platform+'-literal-picker-'+theme+'.png',fullPage:true});
   await page.getByRole('button',{name:'引用原文片段 1',exact:true}).click();
   await page.waitForFunction(()=>document.getElementById('captured').textContent!=='null');const capture=JSON.parse(await page.locator('#captured').textContent());assert.equal(capture.evidence.quote,literal);
  }
  result.checks.push({platform,width,theme,compactSourceHeight:shape.height,cssFontFamily:family,actualGlyphFonts:font.fonts,sourceActionAvailableWhenCollapsed:true,completeLiteralQuoteRetained:true,sourcePaneReturned:true,checkboxSize:[size.width,size.height]});
 }
 assert.deepEqual(errors,[]);result.state=followup?'SOURCE_RENDER_ORDINARY_EDIT_LITERAL_PICKER_REAL_HINT_AND_BOTH_THEMES_PASSED':'SOURCE_RENDER_COMPACT_LITERAL_REFERENCES_CLEAR_AI_ENTRY_AND_BOTH_THEMES_PASSED';
}finally{if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));fs.writeFileSync(O+'/render-result.json',JSON.stringify(result,null,2)+'\n');}})().catch(e=>{console.error(String(e));process.exitCode=1});
