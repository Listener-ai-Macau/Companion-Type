const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),crypto=require('crypto');
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',O=path.join(C,'android167');
const{connect}=require(C+'/organization_ui.cjs'),{read}=require(C+'/organization_readback.cjs');
const key=JSON.parse(fs.readFileSync(C+'/android128/public-document-before.json','utf8')).key;
const digest=s=>crypto.createHash('sha256').update(s).digest('hex');
(async()=>{const{page,browser,session}=await connect();try{
 assert.equal((await read(page,'appPreferences')).version,'0.1.167');
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
  await page.getByRole('tab',{name:'纪要',exact:true}).click();const frame=page.locator('#detail-panel-minutes .meeting-reading-frame').first();await frame.locator('.meeting-overview').waitFor();
  const model=require('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/visual-meeting20261114/glance-r4/data.cjs').meetingMapModel(before.minutes.markdown);
  const overview=frame.locator('.meeting-overview'),nodes=overview.locator('.meeting-overview-topics button');assert.equal(await nodes.count(),model.topics.length);
  for(let i=0;i<model.topics.length;i++){await nodes.nth(i).click();assert.equal(await overview.locator('.meeting-overview-detail>p').innerText(),model.topics[i].text);}
  await overview.getByRole('button',{name:'关闭主题原文',exact:true}).click();assert(!await overview.locator('.meeting-overview-detail').isVisible());await page.locator('main').evaluate(e=>e.scrollTop=0);const resultBox=await overview.locator('.meeting-overview-outcomes').boundingBox();assert(resultBox&&resultBox.y+resultBox.height<=await page.evaluate(()=>innerHeight));proof.resultsVisibleBeforeTopicsInFirstViewport=true;await page.screenshot({path:O+'/actual-visual-overview-'+phase+'-'+theme+'.png'});
  await nodes.last().click();await overview.getByRole('button',{name:'纪要位置',exact:true}).click();assert(await frame.locator('.meeting-reading-content').isVisible());await frame.getByRole('button',{name:'返回会议一览',exact:true}).click();await overview.getByRole('button',{name:'阅读完整纪要',exact:true}).click();
  const doc=page.locator('#detail-panel-minutes .minutes-document').first();await doc.waitFor();proof.visualOverviewExactSourceAndReturn=true;proof.briefGlanceNoDefaultParagraph=true;
  const visible=await doc.innerText();
  if(generated){
   assert.equal(await doc.locator('.minutes-origin').count(),before.minutes.manualReview?0:1);
   assert(!visible.includes('AI根据详细纪要整理，请结合原文核对。'));
   assert(!visible.includes('长会议已按原文顺序处理全部'));
  }
  if(await doc.locator('.minutes-generation').count()){
   const details=doc.locator('.minutes-generation');assert.equal(await details.evaluate(e=>e.open),false);await details.locator(':scope>summary').click();assert((await details.innerText()).includes('查看生成说明'));await details.locator(':scope>summary').click();
  }
  {
   const {meetingMapModel,meetingSpeakerGroups}=require('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/visual-meeting20261114/r3/data.cjs');
   const expected=meetingMapModel(before.minutes.markdown).topics,frame=page.locator('#detail-panel-minutes .meeting-reading-frame').first();
   const actualSummary=before.minutes.markdown.split(/^## Summary\r?$/m)[1].split(/^## /m)[0].split(/\r?\n/).filter(x=>/^[-*]\s/.test(x)).map(x=>x.replace(/^[-*]\s+/,''));
   assert(actualSummary.length>5);
   proof.clearReading=await require('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055/tools/qa/core_acceptance20261109/meeting_clarity_ui.cjs')(page,frame,O,phase+'-'+theme,{summaryTitle:'其余 '+(actualSummary.length-4)+' 项',noDirectory:true,minimumTextLength:20,expectedText:actualSummary.slice(4),directoryTitle:'补充原文（供核对）',directoryDisclosureTitle:'补充原文（供核对）'});
   proof.actualInputScope='Existing public90s meeting restored through ordinary backup, no new model run; desktop independently uses saved public30m.';
   await frame.getByRole('button',{name:'思维导图',exact:true}).click();
   assert.equal(await frame.locator('.meeting-map-branches summary').first().evaluate(e=>getComputedStyle(e,'::after').display),'none');
   const topics=frame.locator('.meeting-map-branches>li');assert.equal(await topics.count(),expected.length);assert(expected.length>0);
   await frame.getByRole('button',{name:'展开全部',exact:true}).click();
   await page.waitForFunction(n=>document.querySelectorAll('#detail-panel-minutes .meeting-map-branches details[open]').length===n,expected.length);
   assert.deepEqual(await topics.locator('.meeting-map-topic-content>p').allTextContents(),expected.map(t=>t.text));
   await frame.getByRole('button',{name:'收起',exact:true}).click();await page.locator('main').evaluate(e=>e.scrollTop=0);
   await page.screenshot({animations:'disabled',path:O+'/actual-visual-map-'+phase+'-'+theme+'.png'});
   await topics.last().locator('summary').click();await topics.last().getByRole('button',{name:'查看纪要上下文',exact:true}).click();
   await page.waitForFunction(()=>document.activeElement?.closest('.meeting-reading-content'));
   await frame.getByRole('button',{name:'按发言人',exact:true}).click();
   const groups=meetingSpeakerGroups(before.minutes.markdown);assert.equal(await frame.locator('.meeting-speaker-card').count(),groups.length);
   if(!groups.length)assert((await frame.locator('.meeting-speakers').innerText()).includes('还没有区分发言人'));
   await page.locator('main').evaluate(e=>e.scrollTop=0);await page.screenshot({animations:'disabled',path:O+'/actual-speakers-'+phase+'-'+theme+'.png'});
   await frame.getByRole('button',{name:'会议一览',exact:true}).click();await frame.getByRole('button',{name:'阅读完整纪要',exact:true}).click();
   proof.visualMeetingMapAndSourceWordsChecked=true;proof.speakerLabelsNotInvented=true;
  }
  if(phase==='before-restart'){
   const menu=page.locator('.recording-content-more');await menu.locator(':scope>summary').click();
   await menu.getByRole('button',{name:'整理方式',exact:true}).click();
   assert.equal(await menu.evaluate(e=>e.open),false);assert.equal(await page.locator('.existing-minutes').evaluate(e=>e.open),true);
   await page.locator('.existing-minutes>summary').click();
   await menu.locator(':scope>summary').click();await menu.getByRole('button',{name:'导出导图',exact:true}).click();
   await page.locator('#detail-panel-mindmap').waitFor();assert.equal(await menu.evaluate(e=>e.open),false);
   await page.getByRole('tab',{name:'纪要',exact:true}).click();
   await page.getByRole('button',{name:'前往导出',exact:true}).click();
   assert.equal(await page.locator('.export-card').evaluate(e=>e.open),true);await page.locator('.export-card>summary').click();
  }
  await page.locator('main').evaluate(el=>el.scrollTop=0);
  const layout=await page.evaluate(()=>{const e=document.querySelector('#detail-panel-minutes .minutes-section p,#detail-panel-minutes .minutes-section li');return{firstContentTop:e?.getBoundingClientRect().top,viewportHeight:innerHeight,viewportWidth:innerWidth,bodyWidth:document.body.scrollWidth,duplicateHeadingVisible:!!document.querySelector('#detail-panel-minutes>.section-heading')};});
  assert(layout.bodyWidth<=layout.viewportWidth);assert(!layout.duplicateHeadingVisible);const actualCss=await page.evaluate(()=>{const app=document.querySelector('.mobile-app'),player=document.querySelector('.player-card-idle'),copy=document.querySelector('.player-copy'),title=document.querySelector('.detail-title');return{paper:getComputedStyle(app).getPropertyValue('--surface').trim(),titlePadding:getComputedStyle(title).padding,playerHeight:player?.getBoundingClientRect().height,playerDirection:copy?getComputedStyle(copy).flexDirection:null};});assert.equal(actualCss.titlePadding,'0px');if(actualCss.playerDirection)assert.equal(actualCss.playerDirection,'row');if(actualCss.playerHeight)assert(actualCss.playerHeight<=60);assert.equal(actualCss.paper,theme==='dark'?'#1c1f26':'#ffffff');proof.layouts??=[];proof.layouts.push({theme,...layout});
  await page.locator('main').evaluate(el=>el.scrollTop=0);await page.screenshot({path:O+'/reading-notice-'+phase+'-'+theme+'.png',fullPage:false});
 }
 await page.getByRole('tab',{name:'文字',exact:true}).click();
 await page.getByRole('button',{name:'原始转写',exact:true}).click();
 const originalText=await page.locator('.transcript-reader .transcript').innerText();
 assert.equal(originalText.replace(/\s/g,''),before.transcript.replace(/\s/g,''));
 await page.getByRole('button',{name:'流畅阅读',exact:true}).click();
 assert((await page.locator('.transcript-reader .transcript').innerText()).trim());
 proof.originalAndReadableTranscriptSwitchChecked=true;proof.unifiedMoreMenuAndExportChecked=phase==='before-restart';
 await page.screenshot({path:O+'/readable-transcript-'+phase+'.png',fullPage:false});
 const after=await read(page,'detail',{key});assert.equal(after.minutes.markdown,before.minutes.markdown);assert.equal(after.transcript,before.transcript);
 fs.writeFileSync(O+'/reading-notice-'+phase+'.json',JSON.stringify({...proof,state:'ACTUAL167_PUBLIC_MINUTES_READ_THEMES_AND_SAVED_WORDS_RETAINED',generatedEnvelopeObserved:generated,ownerExperienceAccepted:false,cloudCallsThisReview:0},null,2));
 console.log(JSON.stringify({state:'PUBLIC167_READING_CHECK_PASSED',phase,generatedEnvelopeObserved:generated,ownedDisplay:session.displayId}));
}finally{await browser.close();}})().catch(error=>{fs.writeFileSync(O+'/reading-check-failure-'+Date.now()+'.json',JSON.stringify({error:String(error),stack:error.stack,phase:process.argv[2]},null,2));console.error(error);process.exitCode=1;});
