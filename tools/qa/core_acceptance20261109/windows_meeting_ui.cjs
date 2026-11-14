const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('@playwright/test');
const [port,out,stage]=process.argv.slice(2);
const plan=JSON.parse(fs.readFileSync(path.join(out,'plan.json'),'utf8'));
(async()=>{
 const browser=await chromium.connectOverCDP('http://127.0.0.1:'+port);
 try{
  const context=browser.contexts()[0];let page=context.pages()[0];if(!page)page=await context.waitForEvent('page',{timeout:10000});
  await page.waitForLoadState('domcontentloaded');await page.locator('.ct-shell').waitFor({timeout:30000});
  const identity=await page.evaluate(()=>({url:location.href,tauri:typeof window.__TAURI_INTERNALS__?.invoke==='function',title:document.title}));
  assert.ok(identity.tauri,'Real Tauri runtime required; no browser/mock fallback');
  if(plan.realPublicReview)await page.locator('.ct-library-card').first().waitFor({timeout:30000});
  else await page.waitForFunction(expected=>document.body.innerText.includes(expected),plan.title,{timeout:30000});
  const text=await page.locator('body').innerText();if(!plan.realPublicReview)assert.ok(text.includes(plan.title));
  fs.writeFileSync(path.join(out,'ui-body.txt'),text);
  fs.writeFileSync(path.join(out,'ui-controls.json'),JSON.stringify(await page.locator('button,input,select,summary').evaluateAll(nodes=>nodes.map(node=>({tag:node.tagName,text:node.innerText||'',aria:node.getAttribute('aria-label'),type:node.getAttribute('type')}))),null,2));
  await page.screenshot({path:path.join(out,'native-workspace.png'),fullPage:true});
  if(plan.publicSourceImport){
   const result=await require('./windows_public_source_ui.cjs')(page,plan,out,stage==='product-reopen');
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(plan.realPublicReview){
   const result=await require(plan.realPublicSpec?.retranscriptionOnly?'./windows_public_retranscribe_ui.cjs':plan.realPublicSpec?.sourcePointerOnly?'./windows_public_source_pointer_ui.cjs':'./windows_real_public_ui.cjs')(page,plan,out,stage==='product-reopen');
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='product-reopen'){
   const result=await require('./windows_product_reopen_ui.cjs')(page,plan,out);
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='product'||stage==='product-background'){
   const result=await require('./windows_product_ui.cjs')(page,plan,out);
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='audio'||stage==='transcribe'){
   const result=await require('./windows_audio_ui.cjs')(page,plan,out);
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='editing'){
   const result=await require('./windows_audio_edit_ui.cjs')(page,plan,out);
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='incoming'){
   const result=await require('./windows_incoming_ui.cjs')(page,plan,out);
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='documents'){
   const result=await require('./windows_document_ui.cjs')(page,plan,out);
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='context'){
   const result=await require('./windows_context_ui.cjs')(page,plan,out);
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='actions'){
   const result=await require('./windows_actions_ui.cjs')(page,plan,out);
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='ai'){
   const result=await require('./windows_reviewed_ai_ui.cjs')(page,plan,out);
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));
  }else if(stage==='handoff'){
   await page.locator('.ct-library-card').filter({hasText:plan.title}).click();
   await page.locator('#ct-saved-recording-workspace').waitFor({state:'visible'});
   await page.getByRole('button',{name:'导出分享',exact:true}).click();
   const panel=page.locator('.ct-content-export');await panel.locator(':scope > summary').click();
   await panel.getByLabel('整理结果',{exact:true}).check();await panel.getByLabel('录音文字',{exact:true}).uncheck();
   await panel.locator('.ct-content-materials > summary').click();
   const material=panel.getByLabel('选择材料：工程验收补充（不是会议原话）：后续导出必须保留未确认状态。',{exact:true});await material.check();
   await panel.locator('.ct-content-share-alternative > summary').click();
   const received=[];
   for(const format of ['txt','docx','pdf']){
    await panel.getByLabel('所选内容文件格式').selectOption(format);
    await panel.getByRole('button',{name:'复制所选文件',exact:true}).click();
    const status=panel.getByLabel('所选内容操作结果');await status.getByText(/文件已复制：/).waitFor({timeout:60000});
    const feedback=await status.innerText();assert.match(feedback,/文件尚未发送/);
    const name=feedback.match(/文件已复制：(.+?)。可在/s)?.[1];assert.ok(name);assert.ok(name.endsWith('.'+format));
    const request=path.join(out,'handoff-request-'+format+'.json');fs.writeFileSync(request+'.tmp',JSON.stringify({format,fileName:name}));fs.renameSync(request+'.tmp',request);
    const reply=path.join(out,'handoff-reply-'+format+'.json'),deadline=Date.now()+25000;
    while(!fs.existsSync(reply)&&Date.now()<deadline)await new Promise(r=>setTimeout(r,100));
    assert.ok(fs.existsSync(reply),'Ordinary app must confirm the exact received file before next copy');received.push(JSON.parse(fs.readFileSync(reply,'utf8')));
   }
   await page.screenshot({path:path.join(out,'native-selected-files-delivered.png'),fullPage:true});
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({state:'REAL_TAURI_SELECTED_FILE_HANDOFF_TO_ORDINARY_RECEIVER_PASSED',identity,sourceMeeting:plan.sourceMeeting,received,publicFixtureVisible:true,ordinaryRecipientTested:true,captureOrModelQualified:false},null,2));
  }else fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({state:'ACTUAL_NATIVE_LIBRARY_INSPECTED',identity,publicFixtureVisible:true,ordinaryRecipientTested:false,captureOrModelQualified:false},null,2));
 }catch(error){
  for(const page of contextPages(browser)){
   try{fs.writeFileSync(path.join(out,'ui-failure-body.txt'),await page.locator('body').innerText());await page.screenshot({path:path.join(out,'ui-failure.png'),fullPage:true});}catch{}
  }
  throw error;
 }finally{await browser.close();}
})().catch(error=>{fs.writeFileSync(path.join(out,'ui-failure.json'),JSON.stringify({error:String(error),stack:error.stack},null,2));console.error(error);process.exitCode=1;});
function contextPages(browser){return browser.contexts().flatMap(context=>context.pages());}
