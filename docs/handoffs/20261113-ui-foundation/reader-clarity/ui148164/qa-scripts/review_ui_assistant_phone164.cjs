const fs=require('fs'),assert=require('node:assert/strict'),crypto=require('crypto');
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',O=C+'/android164';
const{connect}=require(C+'/organization_ui.cjs'),{read}=require(C+'/organization_readback.cjs');
const key=JSON.parse(fs.readFileSync(C+'/android128/public-document-before.json','utf8')).key;
const digest=s=>crypto.createHash('sha256').update(s).digest('hex');
(async()=>{const{page,browser,session}=await connect();try{
 assert.equal((await read(page,'appPreferences')).version,'0.1.164');
 const own=JSON.parse(fs.readFileSync(O+'/public-libraries.json'));assert(own.ids.includes((await read(page,'libraryStatus')).activeId));
 const rows=await read(page,'library'),target=rows.rows.find(r=>r.key===key);assert(target);
 const nav=()=>page.getByRole('navigation',{name:'主导航',exact:true});
 async function open(){await nav().getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('heading',{name:'我的录音',exact:true}).waitFor();await page.locator('.library-managed-list .row').filter({hasText:target.title}).click();await page.getByRole('tablist',{name:'录音内容',exact:true}).waitFor();}
 await open();const before=await read(page,'detail',{key}),aiStatus=await read(page,'aiServiceStatus');assert(!aiStatus.configured,'Keep this no-cloud phone scope explicit');
 const phase=process.argv[2],proof={key,ownedDisplay:session.displayId,phoneAiConfigured:false,minutesSha256:digest(before.minutes.markdown),transcriptSha256:digest(before.transcript),modelsRun:false,cloudCalls:0};
 if(phase==='after-restart'){const old=JSON.parse(fs.readFileSync(O+'/assistant-before-restart.json'));assert.equal(proof.minutesSha256,old.minutesSha256);assert.equal(proof.transcriptSha256,old.transcriptSha256);}
 for(const theme of phase==='before-restart'?['light','dark']:['dark']){
  await nav().getByRole('button',{name:'设置',exact:true}).click();await page.getByRole('radio',{name:theme==='light'?'浅色':'深色',exact:true}).check();await open();
  const ask=page.getByRole('button',{name:'问会议',exact:true});assert.equal(await ask.count(),1);assert(await ask.isVisible());await ask.click();
  const ai=page.getByRole('region',{name:'会议AI助手',exact:true});await ai.waitFor();await ai.getByRole('button',{name:'设置AI服务',exact:true}).waitFor();assert.equal(await ai.getByRole('button',{name:'开始整理',exact:true}).count(),0);
  const scope=ai.locator('.ai-scope');await scope.getByText('本次使用 1/12 项资料',{exact:true}).waitFor({state:'attached',timeout:30000});await scope.locator(':scope > summary').click();
  const checked=await scope.getByRole('checkbox').evaluateAll(nodes=>nodes.filter(n=>n.checked).length);assert.equal(checked,1);assert((await scope.innerText()).includes('本次使用 1/12 项资料'));await scope.locator(':scope > summary').click();
  const question=ai.getByRole('textbox',{name:'会议AI问题',exact:true});await question.fill('公开软件检查：先保留待提问题，不自动调用服务。');
  await page.getByRole('tab',{name:'纪要',exact:true}).click();await ask.click();assert.equal(await question.inputValue(),'公开软件检查：先保留待提问题，不自动调用服务。');await question.fill('');
  await page.locator('main').evaluate(e=>e.scrollTop=0);await page.screenshot({path:O+'/native-assistant-'+phase+'-'+theme+'.png'});
  const menu=page.locator('.recording-content-more');await menu.locator(':scope > summary').click();await menu.getByRole('button',{name:'整理方式',exact:true}).click();
  const picker=page.locator('.template-picker');if(!await picker.evaluate(e=>e.open))await picker.locator(':scope > summary').click();const preview=page.locator('.minutes-template-preview');await preview.locator(':scope > summary').click();assert((await preview.innerText()).includes('这是整理要求的预览'));await page.screenshot({path:O+'/native-template-'+phase+'-'+theme+'.png'});await preview.locator(':scope > summary').click();
  await page.locator('.existing-minutes > summary').click();await menu.locator(':scope > summary').click();await menu.getByRole('button',{name:'导出导图',exact:true}).click();await page.locator('#detail-panel-mindmap').waitFor();
  await page.getByRole('tab',{name:'纪要',exact:true}).click();const frame=page.locator('#detail-panel-minutes .meeting-reading-frame').first();await frame.getByRole('button',{name:'思维导图',exact:true}).click();await frame.locator('.meeting-map-branches').waitFor();await frame.getByRole('button',{name:'阅读纪要',exact:true}).click();
  assert(await page.evaluate(()=>document.body.scrollWidth<=innerWidth));
 }
 const after=await read(page,'detail',{key});assert.equal(after.minutes.markdown,before.minutes.markdown);assert.equal(after.transcript,before.transcript);assert.deepEqual(after.notes,before.notes);
 fs.writeFileSync(O+'/assistant-'+phase+'.json',JSON.stringify({...proof,state:'NORMAL164_VISIBLE_ASSISTANT_SOURCE_SCOPE_TEMPLATE_AND_REOPEN_CHECK_PASSED',visibleSingleAskEntry:true,unconfiguredServiceNotPresentedAsGeneratedSuccess:true,questionDraftRetainedAcrossReading:true,templatePreviewAndMapExportDistinct:true,minutesTranscriptAndPreviousNotesUnchanged:true,actualAiMaterialGenerationOnPhoneTested:false,actualPhoneMaterialSaveExportRetested:false},null,2));console.log('NORMAL164_ACTUAL_UI_PASSED '+phase);
}catch(e){fs.writeFileSync(O+'/assistant-failure-'+Date.now()+'.json',JSON.stringify({error:String(e),stack:e.stack}));fs.writeFileSync(O+'/assistant-failure-body.txt',await page.locator('body').innerText());throw e;}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
