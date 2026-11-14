// Normal packaged Tauri app, real persistence/export; explicit local HTTP reply
// fixture. This is no speech/model-quality claim or Owner profile operation.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055/node_modules/@playwright/test');
const [port,out,stage]=process.argv.slice(2),plan=JSON.parse(fs.readFileSync(path.join(out,'plan.json'),'utf8'));
const syntheticServiceFixture=process.env.COMPANION_ACCEPTANCE_REAL_AI_FUNCTIONAL!=='1';
(async()=>{const browser=await chromium.connectOverCDP('http://127.0.0.1:'+port);let page;
 try{
  page=browser.contexts()[0].pages()[0];await page.locator('.ct-shell').waitFor();
  assert(await page.evaluate(()=>typeof window.__TAURI_INTERNALS__?.invoke==='function'));
  const rows=()=>JSON.parse(fs.readFileSync(plan.statePath,'utf8')),row=()=>rows().find(r=>r.id===plan.sessionId);
  const before=rows();
  await page.getByRole('button',{name:/^(?:全部录音|录音)$/,exact:true}).click();
  await page.locator('.ct-library-card').filter({hasText:plan.title}).click();
  const ask=page.getByRole('navigation',{name:'会议工作区',exact:true}).getByRole('button',{name:'问会议',exact:true});
  await ask.click();const ai=page.getByRole('region',{name:'会议AI助手',exact:true});await ai.waitFor();
  const question='明确虚构工程检查：小王负责什么？追加费用是否已经批准？';
  if(stage==='product-reopen'){
   assert(plan.previousAppExited&&plan.firstPid!==plan.reopenedPid);
   const note=row().meetingNotes.find(n=>n.text.includes('原生流程验收材料'));
   assert(note);const card=ai.locator('.ai-saved > details').filter({hasText:'原生流程验收材料'});await card.locator(':scope > summary').click();
   await card.getByRole('button',{name:'复用整理要求',exact:true}).click();
   assert.equal(await ai.getByRole('textbox',{name:'会议AI问题',exact:true}).inputValue(),question);
   assert((await card.innerText()).includes('追加20%的费用尚未批准'));
   assert.deepEqual(rows(),plan.expectedSnapshot);
   await page.screenshot({path:path.join(out,'native-material-reopened.png'),fullPage:true});
   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({state:'ACTUAL_NATIVE_MATERIAL_REOPEN_AND_QUESTION_REUSE_PASSED',previousAppExited:true,firstPid:plan.firstPid,reopenedPid:plan.reopenedPid,allPublicLibraryRowsUnchanged:true,reuseDoesNotAutomaticallyCallService:true,syntheticServiceFixture}));return;
  }
  await ai.getByRole('textbox',{name:'会议AI问题',exact:true}).fill(question);
  await ai.getByRole('button',{name:'开始整理',exact:true}).click();
  await ai.locator('[aria-label="材料预览"]').waitFor({timeout:45000});
  assert.match(await ai.locator('.ai-draft-document').innerText(),/尚未批准|未批准|未获批准|尚待批准/);
  await ai.getByRole('button',{name:'编辑材料',exact:true}).click();
  await ai.getByRole('textbox',{name:'AI材料名称',exact:true}).fill('原生流程验收材料');
  const body=ai.getByRole('textbox',{name:'AI材料正文',exact:true});const text=await body.inputValue();await body.fill(text+'\n\n人工核对：等待书面确认后再跟进。');
  await ai.getByRole('button',{name:'预览材料',exact:true}).click();
  await ai.getByRole('button',{name:'保存到会议',exact:true}).click();
  await ai.getByRole('button',{name:'导出这份材料',exact:true}).waitFor();
  const saved=row().meetingNotes.find(n=>n.text.startsWith('AI 材料（请核对）｜原生流程验收材料\n'));
  assert(saved&&saved.text.includes('问题：'+question)&&saved.text.includes('原文依据：')&&saved.text.includes('人工核对：等待书面确认后再跟进。'));
  await ai.getByRole('button',{name:'导出这份材料',exact:true}).click();
  const panel=page.locator('.ct-content-export');await panel.getByRole('button',{name:'预览所选内容',exact:true}).click();
  const preview=await panel.getByRole('region',{name:'所选正文预览',exact:true}).innerText();
  assert(preview.includes('原生流程验收材料')&&preview.includes('人工核对：等待书面确认后再跟进。')&&!preview.includes('EXCLUDED_CORE_NOTE_20261109'));
  await panel.getByLabel('所选内容文件格式').selectOption('txt');
  if(!await panel.getByRole('button',{name:'复制所选文件',exact:true}).isVisible())await panel.locator('.ct-content-share-alternative > summary').click();
  await panel.getByRole('button',{name:'复制所选文件',exact:true}).click();
  const status=panel.getByLabel('所选内容操作结果');await status.getByText(/文件已复制：/).waitFor({timeout:45000});
  const fileName=(await status.innerText()).match(/文件已复制：(.+?)。可在/s)?.[1];assert(fileName);
  fs.writeFileSync(path.join(out,'handoff-request-material.json'),JSON.stringify({fileName,expected:'人工核对：等待书面确认后再跟进。',excluded:'EXCLUDED_CORE_NOTE_20261109'}));
  const reply=path.join(out,'handoff-reply-material.json'),until=Date.now()+30000;while(!fs.existsSync(reply)&&Date.now()<until)await new Promise(r=>setTimeout(r,100));assert(fs.existsSync(reply));
  assert(JSON.parse(fs.readFileSync(reply)).selectedContentsVerified);
  await ask.click();
  for(const theme of ['light','dark']){const toggle=page.getByRole('button',{name:theme==='dark'?'切换至深色模式':'切换至浅色模式',exact:true});if(await toggle.count())await toggle.click();await ai.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'native-material-'+theme+'.png'),fullPage:true});}
  assert.equal(row().transcriptText,before.find(r=>r.id===plan.sessionId).transcriptText);
  assert.deepEqual(row().minutes,before.find(r=>r.id===plan.sessionId).minutes);
  assert.deepEqual(rows().filter(r=>r.id!==plan.sessionId),before.filter(r=>r.id!==plan.sessionId));
  fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({state:'ACTUAL_NATIVE_ASSISTANT_SAVE_EXACT_EXPORT_PASSED',savedNoteId:saved.id,unrelatedNoteExcluded:true,originalTranscriptMinutesAndOtherRowsUnchanged:true,syntheticServiceFixture,modelQualityQualified:false,ordinaryRecipientTested:false}));
 }catch(e){if(page){fs.writeFileSync(path.join(out,'ui-failure-body.txt'),await page.locator('body').innerText());await page.screenshot({path:path.join(out,'ui-failure.png'),fullPage:true});}throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
