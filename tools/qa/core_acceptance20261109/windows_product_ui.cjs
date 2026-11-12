// One continuous ordinary native workflow on the declared public fixture.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
module.exports=async function productJourney(page,plan,out){
 const nav=()=>page.getByRole('navigation',{name:'会议工作区',exact:true});
 const row=()=>JSON.parse(fs.readFileSync(plan.statePath,'utf8')).find(r=>r.id===plan.sessionId);
 const before=row(),unrelated=JSON.parse(fs.readFileSync(plan.statePath,'utf8')).filter(r=>r.id!==plan.sessionId);
 if(process.env.COMPANION_ACCEPTANCE_OWNER_PREFLIGHT==='1'){
  const connection=page.getByRole('region',{name:'录音卡连接',exact:true});await connection.waitFor();
  assert(await connection.isVisible());assert((await connection.innerText()).includes('未连接'));
  const connectionBox=await connection.boundingBox();assert(connectionBox&&connectionBox.y>=0&&connectionBox.y+connectionBox.height<=await page.evaluate(()=>innerHeight));
  await connection.getByRole('button',{name:'连接录音卡',exact:true}).waitFor();
  await page.screenshot({path:path.join(out,'self-acceptance-library-entry.png'),fullPage:true});
  await page.getByRole('button',{name:'设备与同步',exact:true}).click();
  const readiness=page.getByRole('region',{name:'录前准备',exact:true});
  await readiness.getByRole('heading',{name:'录音卡',exact:true}).waitFor();
  await readiness.getByRole('button',{name:'连接设备',exact:true}).waitFor();
  const linkState=readiness.locator('.ct-connection-state');assert(await linkState.isVisible());assert.equal((await linkState.innerText()).trim(),'未连接');assert.equal(await linkState.evaluate(node=>node.closest('details')),null);
  const secondary=page.locator('details').filter({has:page.locator('summary').getByText('电脑录音与文件导入',{exact:true})});
  assert(!await secondary.evaluate(node=>node.open));
  assert(!await page.locator('.ct-device-options:not(.ct-sync-details)').evaluate(node=>node.open));
  if(await page.locator('.ct-sync-details').count()){
   assert(!await page.locator('.ct-sync-details').evaluate(node=>node.open));
   assert.equal(await page.getByRole('region',{name:'录音同步进度',exact:true}).count(),0);
  }
  assert((await readiness.boundingBox()).y<(await secondary.boundingBox()).y);
  await page.screenshot({path:path.join(out,'self-acceptance-device-entry.png'),fullPage:true});
 }
 async function open(){await page.getByRole('button',{name:'我的记录',exact:true}).click();await page.locator('.ct-library-card').filter({hasText:plan.title}).click();await nav().waitFor();}
 if(!plan.backgroundOnly)await page.bringToFront();await open();await page.locator('#ct-meeting-result-pane').waitFor({state:'visible'});await page.locator('#ct-recording-text').waitFor({state:'hidden'});
 await page.locator('#ct-recording-result[open]').waitFor();
 await page.screenshot({path:path.join(out,'product-result-light.png'),fullPage:true});
 await nav().getByRole('button',{name:'导出',exact:true}).click();
 const complete=page.locator('.ct-content-export');await complete.getByRole('button',{name:'预览所选内容',exact:true}).click();
 const completePreview=complete.getByRole('region',{name:'所选正文预览',exact:true});await completePreview.waitFor();const completeText=await completePreview.innerText();
 assert(completeText.includes('会议摘要')&&completeText.includes('尚未批准'));assert(!completeText.includes('Minutes engine:')&&!completeText.includes('Generated:')&&!completeText.includes('EXCLUDED_CORE_NOTE_20261109'));

 await nav().getByRole('button',{name:'录音与文字',exact:true}).click();await page.getByRole('button',{name:'引用转写到备注',exact:true}).click();
 const search=page.getByRole('searchbox',{name:'查找可引用的原文',exact:true});await search.fill(before.transcriptText.split('\n')[0].slice(0,12));
 const quote=await page.locator('.manual-quote-options blockquote').first().textContent();assert(before.transcriptText.includes(quote));
 await page.getByRole('button',{name:'引用原文片段 1',exact:true}).click();await page.locator('#ct-meeting-materials-pane').waitFor({state:'visible'});
 const notes=page.locator('#ct-recording-notes'),composer=notes.locator('.ct-note-composer');
 await composer.getByRole('textbox',{name:'新录音备注',exact:true}).fill('本次人工跟进\n- [ ] 核对采购清单\n- [ ] 确认追加费用，尚未批准');
 await composer.getByRole('combobox',{name:'补充类型',exact:true}).selectOption('followup');
 await nav().getByRole('button',{name:'纪要',exact:true}).click();await nav().getByRole('button',{name:/笔记与资料/}).click();
 const first=composer.getByRole('textbox',{name:'跟进事项 2',exact:true});assert.equal(await first.inputValue(),'核对采购清单');
 await composer.getByRole('button',{name:'保存备注',exact:true}).click();await notes.getByText('备注已保存到本机。',{exact:true}).waitFor();
 await composer.getByRole('button',{name:'保存备注',exact:true}).waitFor({state:'hidden'});
 const saved=row().meetingNotes.find(n=>n.text.includes('本次人工跟进'));assert(saved&&saved.references.some(r=>r.quote===quote));
 const card=()=>notes.locator('.ct-notes-list > li').filter({has:page.getByRole('button',{name:'编辑备注 '+saved.id,exact:true})});
 await card().getByRole('checkbox',{name:'核对采购清单',exact:true}).click();
 const savedUntil=Date.now()+15000;while(!row().meetingNotes.find(n=>n.id===saved.id).text.includes('- [x] 核对采购清单')&&Date.now()<savedUntil)await wait(100);fs.writeFileSync(path.join(out,'product-public-note-save.json'),JSON.stringify({savedNote:row().meetingNotes.find(n=>n.id===saved.id),noteRevision:row().noteRevision,ui:await notes.innerText(),checked:await card().getByRole('checkbox',{name:'核对采购清单',exact:true}).isChecked()},null,2));assert(row().meetingNotes.find(n=>n.id===saved.id).text.includes('- [x] 核对采购清单'));
 await card().getByRole('button',{name:'查看当前依据',exact:true}).click();await page.getByRole('region',{name:'待核对的补充依据',exact:true}).waitFor({state:'visible'});
 await page.getByRole('button',{name:/返回.*备注|返回.*补充/}).first().click();await page.locator('#ct-meeting-materials-pane').waitFor({state:'visible'});
 await page.reload();await page.locator('.ct-shell').waitFor();await open();await nav().getByRole('button',{name:/笔记与资料/}).click();
 assert(await card().getByRole('checkbox',{name:'核对采购清单',exact:true}).isChecked());const persisted=row().meetingNotes.find(n=>n.id===saved.id);
 await card().getByRole('button',{name:'导出这张清单',exact:true}).click();await page.locator('#ct-meeting-handoff-pane').waitFor({state:'visible'});const panel=page.locator('.ct-content-export');
 await panel.getByLabel('所选内容文件格式').selectOption('txt');await panel.getByRole('button',{name:'预览所选内容',exact:true}).click();const preview=panel.getByRole('region',{name:'所选正文预览',exact:true});await preview.waitFor();
 const expected=await preview.locator('pre').innerText(),quotedPersisted=persisted.text.split('\n').map(line=>'> '+line).join('\n');assert(expected.includes(quotedPersisted));assert(expected.replace(/^> ?/gm,'').includes(quote));assert(!expected.includes('EXCLUDED_CORE_NOTE_20261109'));
 async function dialog(id,action,file,trigger){fs.writeFileSync(path.join(out,'dialog-request-'+id+'.json'),JSON.stringify({action,path:file,sha256:null}));await trigger();const reply=path.join(out,'dialog-reply-'+id+'.json'),end=Date.now()+90000;while(!fs.existsSync(reply)&&Date.now()<end)await wait(100);assert(fs.existsSync(reply));assert.equal(JSON.parse(fs.readFileSync(reply)).state,'OWNED_NATIVE_FILE_PICKER_ACTION_COMPLETED');}
 if(!plan.backgroundOnly){
 await dialog('product-cancel','cancel',null,()=>panel.getByRole('button',{name:'保存 TXT…',exact:true}).click());await panel.getByText('已取消保存，原内容保持不变。',{exact:true}).waitFor();
 const destination=path.join(plan.exportDirectory,'本次人工跟进.txt');await dialog('product-save','save',destination,()=>panel.getByRole('button',{name:'保存 TXT…',exact:true}).click());await panel.getByText(/已保存：本次人工跟进.txt/).waitFor();assert(fs.readFileSync(destination,'utf8').includes(quotedPersisted));
 }
 await panel.getByRole('button',{name:'复制所选内容',exact:true}).click();await panel.getByText('已复制所选内容，可粘贴到常用应用。',{exact:true}).waitFor();
 await panel.locator('summary').filter({hasText:'更多分享方式'}).click();
 await panel.getByRole('button',{name:'复制所选文件',exact:true}).click();const feedback=panel.getByLabel('所选内容操作结果');await feedback.getByText(/文件已复制：/).waitFor();const name=(await feedback.innerText()).match(/文件已复制：(.+?)。可在/s)?.[1];assert(name);
 fs.writeFileSync(path.join(out,'handoff-request-product.json'),JSON.stringify({fileName:name,format:'txt',expected:quotedPersisted,excluded:'EXCLUDED_CORE_NOTE_20261109'}));const reply=path.join(out,'handoff-reply-product.json'),end=Date.now()+30000;while(!fs.existsSync(reply)&&Date.now()<end)await wait(100);assert(fs.existsSync(reply));const received=JSON.parse(fs.readFileSync(reply,'utf8'));
 await page.screenshot({path:path.join(out,'product-handoff-light.png'),fullPage:true});
 await nav().getByRole('button',{name:'纪要',exact:true}).click();const theme=page.getByRole('button',{name:/切换.*深色/}).first();await theme.click();await page.screenshot({path:path.join(out,'product-result-dark.png'),fullPage:true});
 assert.equal(row().transcriptText,before.transcriptText);assert.deepEqual(row().minutes,before.minutes);assert.deepEqual(JSON.parse(fs.readFileSync(plan.statePath,'utf8')).filter(r=>r.id!==plan.sessionId),unrelated);
 if(plan.verifyDateOnly){
  await page.getByRole('button',{name:'编辑清单',exact:true}).click();await page.getByLabel('待办 1 时间与负责人',{exact:true}).click();
  await page.getByRole('textbox',{name:'待办 1 时间',exact:true}).fill('十一月十六日之前');await page.getByRole('button',{name:'保存修改',exact:true}).click();
  await page.getByRole('button',{name:'保存修改',exact:true}).waitFor({state:'hidden'});
  await page.locator('summary').filter({hasText:'清单与日历工具'}).click();await page.getByRole('button',{name:'导出到日历',exact:true}).click();
  const dateDialog=page.getByRole('dialog',{name:'待办 1 日历时间',exact:true}),reviewRow=page.getByRole('button',{name:'日历事项 1 确认清单截止日期和时刻',exact:true});
  await Promise.race([dateDialog.waitFor(),reviewRow.waitFor()]);if(!await dateDialog.isVisible())await reviewRow.click();
  await dateDialog.waitFor();assert(!await dateDialog.getByRole('checkbox',{name:'待办 1 指定时刻',exact:true}).isChecked());
  await dateDialog.getByLabel('待办 1 日历日期',{exact:true}).fill('2026-11-16');await dateDialog.getByRole('button',{name:/^(确认这个截止时间|使用此日历时间)$/}).click();
  await page.getByRole('button',{name:'保存修改并返回日历预览',exact:true}).click();
  await page.getByRole('region',{name:'逐项日历预览',exact:true}).getByText(/清单截止：2026年11月16日前/).waitFor();
  assert(row().minutesByMode.offlineStore.markdown.includes('due: 2026-11-16前'));
  await page.screenshot({path:path.join(out,'product-date-only-calendar.png'),fullPage:true});
  await page.reload();await page.locator('.ct-shell').waitFor();await open();assert(row().minutesByMode.offlineStore.markdown.includes('due: 2026-11-16前'));
  assert.equal(row().transcriptText,before.transcriptText);assert.deepEqual(JSON.parse(fs.readFileSync(plan.statePath,'utf8')).filter(r=>r.id!==plan.sessionId),unrelated);
 }
 return {state:plan.backgroundOnly?'REAL_NATIVE_COHERENT_MEETING_SOURCE_FOLLOWUP_REOPEN_PREVIEW_AND_PRIVATE_FILE_PASSED':'REAL_NATIVE_COHERENT_MEETING_SOURCE_FOLLOWUP_REOPEN_PREVIEW_SAVE_CANCEL_COPY_AND_RECIPIENT_PASSED',dateOnlyCalendarSavedAndReopened:!!plan.verifyDateOnly,nativeSaveCancelRetested:!plan.backgroundOnly,ordinaryRecipientRetested:!plan.backgroundOnly,notesPersisted:true,literalSourceRetained:true,exactSelectedNote:true,ordinaryRecipient:received,originalMeetingAndOtherRecordsUnchanged:true,modelsRun:false,hardwareQualified:false};
};
