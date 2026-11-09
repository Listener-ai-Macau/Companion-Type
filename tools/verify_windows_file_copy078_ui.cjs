const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {build}=require('esbuild'),{chromium}=require('@playwright/test');
const root=path.resolve(__dirname,'..'),cache=path.join(root,'.cache/file-copy078'),out=path.resolve(root,'../docs/handoffs/20261109-windows-file-copy078');
fs.mkdirSync(cache,{recursive:true});fs.mkdirSync(out,{recursive:true});
(async()=>{
 fs.writeFileSync(path.join(cache,'view.tsx'),`import React from 'react';import{createRoot}from'react-dom/client';import{ContentExportPanel}from'../../packages/ui/src/ContentExportPanel';import'../../packages/ui/src/companionUi.css';import'../../packages/ui/src/companionDesign.css';import'../../packages/ui/src/companionDark.css';import'../../apps/windows/src/workspaceRefinement.css';
 window.fileCopyCalls=[];const props={sessionId:'public-file-copy078',meetingMode:'offlineStore',sourceVersion:'fixture-v1',minutes:true,transcript:true,highlights:true,timing:true,exactTiming:true,notes:[{id:'public-note',text:'公开虚构材料 · 等待书面确认'}, {id:'exclude-note',text:'不选择的材料'}],blocked:false,unsaved:{title:false,minutes:false,transcript:false,highlights:false,notes:false},onPreview:async request=>({contentHash:'f'.repeat(64),textContent:'公开虚构验收文字：追加20%的费用尚未批准。'}),onSave:async()=>null,onCopy:async()=>({status:'copied'}),onShare:async(request,destination)=>{window.fileCopyCalls.push({request,destination});return{status:destination==='clipboard'?'fileCopied':destination==='folder'?'folderOpened':'opened',fileName:'公开会议-所选内容.pdf',bytes:200};}};createRoot(document.getElementById('root')).render(<main className="ct-shell ct-simple ct-windows" style={{display:'block',padding:32,minHeight:'100vh'}}><section style={{maxWidth:850,margin:'0 auto'}}><h1>公开虚构资料 · 文件导出验收</h1><ContentExportPanel {...props}/></section></main>);`);
 await build({entryPoints:[path.join(cache,'view.tsx')],outfile:path.join(cache,'view.js'),bundle:true,platform:'browser',format:'iife',jsx:'automatic'});
 fs.writeFileSync(path.join(cache,'view.html'),'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="view.css"><div id="root"></div><script src="view.js"></script></html>');
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('file:///'+path.join(cache,'view.html').replaceAll('\\','/'));
  await page.locator('.ct-content-export > summary').click();
  await page.getByLabel('整理结果',{exact:true}).uncheck();await page.getByLabel('录音文字',{exact:true}).check();
  await page.locator('.ct-content-materials > summary').click();await page.getByLabel('选择材料：公开虚构材料 · 等待书面确认',{exact:true}).check();
  await page.locator('.ct-content-share-alternative > summary').click();await page.getByRole('button',{name:'复制所选文件',exact:true}).click();
  await page.getByText(/文件已复制：公开会议-所选内容.pdf/).waitFor();
  const calls=await page.evaluate(()=>window.fileCopyCalls);assert.equal(calls.length,1);assert.equal(calls[0].destination,'clipboard');
  assert.deepEqual(calls[0].request.contentSections,{minutes:false,transcript:true,highlights:false,timeline:false,noteIds:['public-note']});
  assert.equal(calls[0].request.expectedContentHash,'f'.repeat(64));
  assert.match(await page.getByLabel('所选内容操作结果').innerText(),/文件尚未发送/);
  const layouts=[];
  for(const dark of [false,true]){
   await page.locator('.ct-shell').evaluate((node,dark)=>node.classList.toggle('ct-theme-dark',dark),dark);
   for(const width of [1080,1280,1440]){
    await page.setViewportSize({width,height:900});const layout=await page.evaluate(()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth}));assert.ok(layout.documentWidth<=width,JSON.stringify(layout));layouts.push({dark,...layout});
   }
   await page.setViewportSize({width:1280,height:900});await page.screenshot({path:path.join(out,dark?'file-copy-dark.png':'file-copy-light.png'),fullPage:true});
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'ui-verification.json'),JSON.stringify({state:'PASS_PRODUCTION_EXPORT_COMPONENT_CONTROLLED_BROWSER',at:new Date().toISOString(),exactSelectionAndHash:true,route:'clipboard',noFalseSentFeedback:true,layouts,pageErrors:errors,nativeClipboardTouched:false,ordinaryRecipientTested:false,modelsRun:false},null,2));
  console.log('PASS actual export component: explicit file clipboard route, selected material only, original content hash, truthful feedback, 1080/1280/1440 light/dark. Controlled bridge, no system UI.');
 }finally{await browser.close();}
})().catch(error=>{fs.writeFileSync(path.join(out,'ui-failure.json'),JSON.stringify({error:String(error),stack:error.stack},null,2));console.error(error);process.exitCode=1;});
