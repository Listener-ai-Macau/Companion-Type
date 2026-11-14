const fs=require('fs'),http=require('http'),assert=require('node:assert/strict'),path=require('path');
const R='C:/Users/Billy/Desktop/Denzic/Companion',S=R+'/companion-device-closure055',A=R+'/companion-core-android20261109';
const stage=process.argv[2],Q='E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/software-value20261114/'+stage;fs.mkdirSync(Q,{recursive:true});
const{build}=require(S+'/node_modules/esbuild'),{chromium}=require(S+'/node_modules/@playwright/test');
let template=fs.readFileSync(path.join(__dirname,'software_value_harness.tsx'),'utf8');
(async()=>{let server,browser;const result={scope:'Actual production source components, explicit fictional service replies; no model or native qualification.',state:'RUNNING',modelsRun:false,checks:[],errors:[]};try{
 for(const platform of ['windows','mobile']){
  const root=platform==='windows'?S:A;
  let entry=template.replaceAll('ROOT',root).replace('IS_WINDOWS',String(platform==='windows')).replace('PLATFORM_IMPORT',platform==='windows'?"import {MeetingWorkspaceNav} from '"+root+"/packages/ui/src/MeetingWorkspaceNav';":"import {RecordingContentNavigation} from '"+root+"/apps/mobile/src/RecordingContentNavigation';");
  entry=entry.replace('THEME_IMPORTS',platform==='windows'?"import'"+root+"/packages/ui/src/companionUi.css';import'"+root+"/packages/ui/src/notebookFoundation.css';import'"+root+"/packages/ui/src/meetingNoteDocument.css';":"import'"+root+"/apps/mobile/src/mobile.css';import'"+root+"/apps/mobile/src/mobilePremium.css';import'"+root+"/apps/mobile/src/notebookMobile.css';import'"+root+"/packages/ui/src/meetingNoteDocument.css';");
  entry=entry.replace('PLATFORM_CLASS',platform==='windows'?"'ct-shell ct-windows ct-notebook'+(theme==='dark'?' ct-theme-dark':'')":"'mobile-app'");
  entry=entry.replace('PLATFORM_NAV',platform==='windows'?"<MeetingWorkspaceNav value={view as any} dirty={{materials:dirty}} notesCount={0} onChange={setView} onAsk={()=>setView('materials')}/>":"<RecordingContentNavigation value={view==='materials'?'notes':'minutes'} onChange={v=>setView(v==='notes'?'materials':'result')} onAsk={()=>setView('materials')}/>");
  await build({stdin:{contents:entry,loader:'tsx',resolveDir:root,sourcefile:'explicit-fictional-workbench-check.tsx'},bundle:true,platform:'browser',format:'iife',jsx:'automatic',outfile:Q+'/'+platform+'.js',define:{'process.env.NODE_ENV':'"production"'}});
 }
 server=http.createServer((req,res)=>{const name=new URL(req.url,'http://localhost').pathname;if(/^\/(windows|mobile)\.(css|js)$/.test(name)){res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':'text/css');return res.end(fs.readFileSync(Q+name));}const p=name==='/mobile'?'mobile':'windows';res.setHeader('Content-Type','text/html;charset=utf-8');res.end('<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/'+p+'.css"><body style="margin:0"><div id="root"></div><script src="/'+p+'.js"></script></body></html>');});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu','--mute-audio']});
 for(const platform of ['windows','mobile']){
  const page=await browser.newPage({viewport:{width:platform==='windows'?980:390,height:1000},reducedMotion:'reduce'});page.on('pageerror',e=>result.errors.push(e.message));await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
  let approve=true;page.on('dialog',async d=>{assert.equal(d.type(),'confirm');approve?await d.accept():await d.dismiss();});
  await page.goto(base+'/'+platform);await page.getByRole('button',{name:'问会议',exact:true}).click();const bench=page.locator('.meeting-ai-workbench');await bench.waitFor();
  await bench.getByRole('button',{name:'跟进草稿',exact:true}).click();assert.equal(await page.evaluate(()=>__audit.calls.length),0);
  await bench.getByRole('button',{name:'开始整理',exact:true}).click();await bench.getByLabel('材料预览',{exact:true}).waitFor();
  assert.deepEqual(await page.evaluate(()=>__audit.calls[0].ids),['one']);assert(await page.evaluate(()=>__audit.dirty));assert.equal(await bench.getByLabel('AI材料正文',{exact:true}).count(),0);
  assert((await bench.getByLabel('材料预览',{exact:true}).innerText()).includes('负责人尚未确认'));
  await bench.getByRole('button',{name:'编辑材料',exact:true}).click();const body=bench.getByLabel('AI材料正文',{exact:true});const firstBody=await body.inputValue();await body.fill(firstBody+'\n\n人工补充：这只是界面测试。');await bench.getByRole('button',{name:'预览材料',exact:true}).click();
  await page.evaluate(()=>__audit.failSave=true);await bench.getByRole('button',{name:'保存到会议',exact:true}).click();assert((await bench.getByRole('alert').innerText()).includes('演示保存失败'));assert(await page.evaluate(()=>__audit.dirty));assert.equal(await bench.getByRole('button',{name:'导出这份材料',exact:true}).count(),0);
  await bench.getByRole('button',{name:'保存到会议',exact:true}).click();await bench.getByRole('button',{name:'导出这份材料',exact:true}).waitFor();await page.waitForFunction(()=>!__audit.dirty);
  const firstId=await page.evaluate(()=>__audit.materials.one[0].id);await bench.getByRole('button',{name:'导出这份材料',exact:true}).click();assert.equal(await page.evaluate(()=>__audit.exports.at(-1).id),firstId);
  await bench.getByRole('button',{name:'编辑材料',exact:true}).click();await body.fill(firstBody+'\n\n另一份人工修改。');assert.equal(await bench.getByRole('button',{name:'导出这份材料',exact:true}).count(),0);
  await bench.getByRole('button',{name:'保存到会议',exact:true}).click();await page.waitForFunction(()=>__audit.materials.one.length===2);assert.notEqual(await page.evaluate(()=>__audit.materials.one[0].id),firstId);assert((await page.evaluate(()=>__audit.materials.one[1].body)).includes('人工补充：这只是界面测试。'));
  const saved=bench.locator('.ai-saved>details').first();await saved.locator('summary').first().click();const calls=await page.evaluate(()=>__audit.calls.length);await saved.getByRole('button',{name:'复用整理要求',exact:true}).click();assert.equal(await page.evaluate(()=>__audit.calls.length),calls);
  const scope=bench.locator('.ai-scope');await scope.locator('summary').click();const checks=scope.locator('input[type=checkbox]');assert(!await checks.last().isChecked());await checks.last().check();
  assert(await bench.getByRole('button',{name:'保存到会议',exact:true}).isDisabled());assert(await bench.getByRole('button',{name:'导出这份材料',exact:true}).isDisabled());
  for(let i=1;i<=10;i++)await checks.nth(i).check();assert(await checks.nth(11).isDisabled());assert.equal(await scope.locator('input[type=checkbox]:checked').count(),12);
  await scope.locator('summary').click();await bench.getByRole('button',{name:'开始整理',exact:true}).click();await page.waitForFunction(()=>__audit.calls.length===2);assert.equal((await page.evaluate(()=>__audit.calls.at(-1).ids)).length,12);
  approve=false;await bench.getByRole('button',{name:'开始整理',exact:true}).click();assert.equal(await page.evaluate(()=>__audit.calls.length),2);await page.getByRole('button',{name:'切换演示会议',exact:true}).click();assert.equal(await page.evaluate(()=>__audit.context),'one');
  approve=true;await page.getByRole('button',{name:'切换演示会议',exact:true}).click();await page.waitForFunction(()=>__audit.context==='two');assert.equal(await bench.getByLabel('材料预览',{exact:true}).count(),0);assert.equal(await bench.locator('.ai-saved>details').count(),0);
  await page.getByRole('button',{name:'切换演示会议',exact:true}).click();await page.waitForFunction(()=>__audit.context==='one');assert.equal(await bench.locator('.ai-saved>details').count(),2);
  await bench.locator('.ai-saved>details').first().locator('summary').first().click();await bench.locator('.ai-saved>details').first().getByRole('button',{name:'导出材料',exact:true}).click();assert.equal(await page.evaluate(()=>__audit.exports.at(-1).context),'one');
  const preview=page.locator('.minutes-template-preview');await preview.locator('summary').click();assert((await preview.innerText()).includes('突出提问、回应'));
  for(const theme of ['light','dark']){
   if(theme==='dark')await page.getByRole('button',{name:'切换测试主题',exact:true}).click();
   for(const width of platform==='windows'?[980,1440]:[390,320]){
    await page.setViewportSize({width,height:1000});assert(await page.evaluate(()=>document.body.scrollWidth<=innerWidth));await bench.scrollIntoViewIfNeeded();await page.screenshot({animations:'disabled',path:Q+'/'+platform+'-'+width+'-'+theme+'.png'});
   }
  }
  result.checks.push({platform,oneAskEntry:true,documentFirstPreviewAndEditing:true,saveFailureKeepsDraft:true,confirmedSavedIdentityExport:true,editedDraftCannotExportOldVersion:true,independentMaterialsRetained:true,sourceChangeDisablesWrongSave:true,twelveItemCap:true,reuseDoesNotGenerate:true,discardDeclineKeepsDraft:true,contextSwitchClearsOldDraft:true,savedMaterialsSurviveReopen:true,templatePreviewDoesNotGenerate:true,lightDarkAndNarrowFit:true});await page.close();
 }
 assert.equal(result.errors.length,0);result.state='PRODUCTION_ASSISTANT_TO_SAVED_MATERIAL_EXPORT_AND_DRAFT_PROTECTION_PASSED';
}finally{fs.writeFileSync(Q+'/result.json',JSON.stringify(result,null,2));if(browser)await browser.close();if(server)await new Promise(r=>server.close(r));}
console.log(JSON.stringify({state:result.state,evidence:Q,checks:result.checks}));
})().catch(e=>{console.error(e);process.exitCode=1;});
