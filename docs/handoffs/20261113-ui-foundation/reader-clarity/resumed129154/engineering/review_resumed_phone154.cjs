const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),crypto=require('crypto');
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',O=path.join(C,'android154');
const{connect}=require(C+'/organization_ui.cjs'),{read}=require(C+'/organization_readback.cjs');
const key=JSON.parse(fs.readFileSync(C+'/android128/public-document-before.json','utf8')).key;
const digest=s=>crypto.createHash('sha256').update(s).digest('hex');
(async()=>{const{page,browser,session}=await connect();try{
 assert.equal((await read(page,'appPreferences')).version,'0.1.154');
 const own=JSON.parse(fs.readFileSync(O+'/public-libraries.json','utf8'));assert(own.ids.includes((await read(page,'libraryStatus')).activeId));
 const rows=await read(page,'library'),target=rows.rows.find(r=>r.key===key);assert(target,'Only the declared public backup record may be opened');
 const nav=()=>page.getByRole('navigation',{name:'主导航',exact:true});
 async function open(){await nav().getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('heading',{name:'我的录音',exact:true}).waitFor();await page.locator('.library-managed-list .row').filter({hasText:target.title}).click();await page.getByRole('tablist',{name:'录音内容',exact:true}).waitFor();}
 await open();const before=await read(page,'detail',{key});assert(before.minutes?.markdown?.trim(),'Declared public minutes are required for this affected reading review');
 const ai=await read(page,'aiServiceStatus');
 const proof={key,title:target.title,minutesSha256:digest(before.minutes.markdown),transcriptSha256:digest(before.transcript),ownedDisplay:session.displayId,phoneAiConfigured:!!ai.configured,modelsRun:false,cloudCalls:0,boardAccessed:false};
 const phase=process.argv[2];
 if(phase==='after-restart'){
  const checkpoint=JSON.parse(fs.readFileSync(O+'/reading-notice-before-restart.json','utf8'));
  assert.equal(proof.minutesSha256,checkpoint.minutesSha256);assert.equal(proof.transcriptSha256,checkpoint.transcriptSha256);
 }
 const generated=/^Minutes engine: llm_deepseek \(final\)$/m.test(before.minutes.markdown);
 for(const theme of phase==='before-restart'?['light','dark']:['dark']){
  await nav().getByRole('button',{name:'设置',exact:true}).click();await page.getByRole('radio',{name:theme==='light'?'浅色':'深色',exact:true}).check();await open();
  await page.getByRole('tab',{name:'纪要',exact:true}).click();const doc=page.locator('#detail-panel-minutes .minutes-document').first();await doc.waitFor();
  const visible=await doc.innerText();
  if(generated){
   assert.equal(await doc.locator('.minutes-origin').count(),before.minutes.manualReview?0:1);
   assert(!visible.includes('AI根据详细纪要整理，请结合原文核对。'));
   assert(!visible.includes('长会议已按原文顺序处理全部'));
  }
  if(await doc.locator('.minutes-generation').count()){
   const details=doc.locator('.minutes-generation');assert.equal(await details.evaluate(e=>e.open),false);await details.locator(':scope>summary').click();assert((await details.innerText()).includes('查看生成说明'));await details.locator(':scope>summary').click();
  }
  await page.locator('main').evaluate(el=>el.scrollTop=0);await page.screenshot({path:O+'/reading-notice-'+phase+'-'+theme+'.png',fullPage:false});
 }
 const after=await read(page,'detail',{key});assert.equal(after.minutes.markdown,before.minutes.markdown);assert.equal(after.transcript,before.transcript);
 fs.writeFileSync(O+'/reading-notice-'+phase+'.json',JSON.stringify({...proof,state:'ACTUAL154_PUBLIC_MINUTES_READ_THEMES_AND_SAVED_WORDS_RETAINED',generatedEnvelopeObserved:generated,ownerExperienceAccepted:false,cloudCallsThisReview:0},null,2));
 console.log(JSON.stringify({state:'PUBLIC154_READING_CHECK_PASSED',phase,generatedEnvelopeObserved:generated,ownedDisplay:session.displayId}));
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
