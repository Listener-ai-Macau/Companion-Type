// Exact packaged Tauri runtime, normal controls and native dialogs on owned CI.
// All text is a declared fictional/public software fixture. No cloud/model call.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const wait=ms=>new Promise(r=>setTimeout(r,ms)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
module.exports=async function documentJourney(page,plan,out){
 const steps=[],save=()=>fs.writeFileSync(path.join(out,'document-checkpoints.json'),JSON.stringify(steps,null,2));
 async function dialog(id,action,file,hash,trigger){fs.writeFileSync(path.join(out,'dialog-request-'+id+'.json'),JSON.stringify({action,path:file,sha256:hash}));await trigger();const reply=path.join(out,'dialog-reply-'+id+'.json'),until=Date.now()+90000;while(!fs.existsSync(reply)&&Date.now()<until)await wait(100);assert(fs.existsSync(reply),'Native picker result required: '+id);const result=JSON.parse(fs.readFileSync(reply));assert.equal(result.state,'OWNED_NATIVE_FILE_PICKER_ACTION_COMPLETED');steps.push({step:id,actualNativePicker:result.action});save();}
 function row(){return JSON.parse(fs.readFileSync(plan.statePath,'utf8')).find(r=>r.id===plan.sessionId);}
 async function openMeeting(){await page.getByRole('button',{name:'我的记录',exact:true}).click();await page.locator('.ct-library-card').filter({hasText:plan.title}).click();await page.locator('#ct-saved-recording-workspace').waitFor();}
 await page.bringToFront();await openMeeting();const panel=page.getByRole('region',{name:'补充文档材料'});await panel.getByRole('button',{name:'添加文档',exact:true}).waitFor();let before=row();
 if(Number(plan.appVersion.split('.').at(-1))>=97){
  const notes=page.locator('#ct-recording-notes'),sourceBefore=row();
  const oldBody='公开阅读便签甲｜'+('这是一份公开软件检查中的人工说明，不是录音结论。'.repeat(20))+'原样保留的旧便签末尾';
  const newBody='公开阅读便签乙｜'+('这是一份新写的人工接续卡，保留全部原文字。'.repeat(20))+'原样保留的新便签末尾';
  async function addNote(body){
   const composer=notes.locator('.ct-note-composer');if(!await composer.evaluate(node=>node.open))await composer.locator(':scope > summary').click();
   await notes.getByRole('textbox',{name:'新录音备注',exact:true}).fill(body);await notes.getByRole('button',{name:'保存备注',exact:true}).click();
   await notes.locator('.ct-note-body').filter({hasText:body.slice(0,12)}).waitFor();
   const actual=row().meetingNotes.find(note=>note.text===body);assert(actual,'Ordinary save must durably retain the complete body');return actual;
  }
  const oldNote=await addNote(oldBody),newNote=await addNote(newBody);
  const cards=notes.locator('.ct-notes-list > li');assert((await cards.first().innerText()).includes('原样保留的新便签末尾'));
  const oldCard=cards.filter({hasText:'公开阅读便签甲'});assert(!(await oldCard.locator('.ct-note-body').innerText()).includes('原样保留的旧便签末尾'));
  await notes.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'notes-reading-recent.png')});
  await notes.getByRole('combobox',{name:'备注排序',exact:true}).selectOption('created');assert((await cards.first().innerText()).includes('公开阅读便签甲'));
  await oldCard.getByRole('button',{name:'展开全文',exact:true}).click();assert((await oldCard.locator('.ct-note-body').innerText()).includes('原样保留的旧便签末尾'));
  await oldCard.getByRole('button',{name:'编辑备注 '+oldNote.id,exact:true}).click();assert.equal(await oldCard.getByRole('textbox',{name:'编辑备注 '+oldNote.id,exact:true}).inputValue(),oldBody);
  await oldCard.getByRole('button',{name:'取消编辑',exact:true}).click();assert.equal(row().meetingNotes.find(n=>n.id===oldNote.id).text,oldBody);
  await oldCard.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'notes-reading-created.png')});
  await page.getByRole('button',{name:'我的记录',exact:true}).click();await page.getByPlaceholder('搜索录音和补充',{exact:true}).fill('原样保留的旧便签末尾');await page.locator('.ct-library-card').filter({hasText:plan.title}).click();
  await notes.locator('.ct-note-body').filter({hasText:'原样保留的旧便签末尾'}).waitFor();assert((await notes.locator('.ct-note-body').filter({hasText:'原样保留的旧便签末尾'}).innerText()).includes(oldBody));
  await notes.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'notes-reading-source-search.png')});
  await page.getByRole('button',{name:'我的记录',exact:true}).click();await page.getByPlaceholder('搜索录音和补充',{exact:true}).fill('');await openMeeting();
  before=row();assert.equal(before.transcriptText,sourceBefore.transcriptText);assert.deepEqual(before.minutes,sourceBefore.minutes);
  for(const note of sourceBefore.meetingNotes||[])assert.deepEqual(before.meetingNotes.find(n=>n.id===note.id),note);
  fs.writeFileSync(path.join(out,'notes-reading-ui.json'),JSON.stringify({state:'ORDINARY_NATIVE_RECENT_CREATED_COMPLETE_EDIT_AND_SEARCH_READING_PASSED',oldNoteId:oldNote.id,newNoteId:newNote.id,oldBodyPreserved:true,newBodyPreserved:true,sourceTranscriptMinutesAndPreviousNotesUnchanged:true},null,2));
  steps.push({step:'native-recent-notes-presentation',latestUpdatedFirst:true,createdOrderSelectable:true,oldLongNoteFoldedAndReversible:true,editLoadsCompleteSource:true,searchDisplaysCompleteMatchingNote:true});save();
 }
 await dialog('document-cancel','cancel',null,null,()=>panel.getByRole('button',{name:'添加文档',exact:true}).click());await panel.getByText('已取消选择，已有材料保留。',{exact:true}).waitFor();assert.equal(row().documentContext?.rows?.length??0,0);
 const docs=[];
 for(const input of plan.documentInputs){
  await dialog('document-import-'+input.name.replace(/\W/g,'_'),'open',input.path,input.sha256,()=>panel.getByRole('button',{name:'添加文档',exact:true}).click());await panel.getByText('文档原件已保存在本机。打开材料后可提取文字，不会自动发送给AI。',{exact:true}).waitFor();
  const item=panel.locator('.document-list article').filter({hasText:input.name});await item.getByRole('button').first().click();await panel.getByRole('button',{name:'在本机提取文字',exact:true}).click();
  if(input.name==='no-text.pdf'){await panel.getByRole('alert').filter({hasText:'未提取到可读取文字'}).waitFor();const doc=row().documentContext.rows.find(d=>d.name===input.name);assert(!doc.extraction);docs.push(doc);continue;}
  if(input.name==='protected.pdf'){
   await panel.getByRole('alert').filter({hasText:'需要密码'}).waitFor();await panel.getByLabel('PDF密码',{exact:true}).fill('public-wrong-password');await panel.getByRole('button',{name:'在本机提取文字',exact:true}).click();await panel.getByRole('alert').filter({hasText:'PDF密码不正确'}).waitFor();assert.equal(await panel.getByLabel('PDF密码',{exact:true}).inputValue(),'');await panel.getByLabel('PDF密码',{exact:true}).fill('local-password');await panel.getByRole('button',{name:'在本机提取文字',exact:true}).click();
  }
  if(input.name==='material-gb.txt'){await panel.getByRole('alert').waitFor();await panel.getByRole('combobox',{name:'文档文字编码',exact:true}).selectOption('gb18030');await panel.getByRole('button',{name:'在本机提取文字',exact:true}).click();}
  await panel.getByText('文字已提取并保存在本机，可随会议备份恢复。',{exact:true}).waitFor({timeout:55000});const doc=row().documentContext.rows.find(d=>d.name===input.name);assert(doc?.extraction);assert.equal(doc.sourceSha256,input.sha256);assert.equal(sha(path.join(plan.recordingDirectory,doc.file)),input.sha256);const extracted=JSON.parse(fs.readFileSync(path.join(plan.recordingDirectory,doc.extraction.file),'utf8'));assert.equal(extracted.sourceSha256,input.sha256);assert(extracted.characters>0);if(input.expected)assert(extracted.sections.some(s=>s.text.includes(input.expected)));docs.push(doc);steps.push({step:'native-'+input.name,sourceSha256:doc.sourceSha256,characters:extracted.characters,warnings:extracted.warnings});save();
 }
 const xlsx=panel.locator('.document-list article').filter({hasText:'material.xlsx'});await xlsx.getByRole('button').first().click();
 const grid=panel.locator('.document-table-reader');await grid.getByRole('table').waitFor();
 const storedWorkbook=row().documentContext.rows.find(d=>d.name==='material.xlsx'),storedTable=JSON.parse(fs.readFileSync(path.join(plan.recordingDirectory,storedWorkbook.extraction.file),'utf8'));
 assert(storedTable.sections.some(section=>section.tableRows?.length),'New extraction must durably preserve real row/column layout');
 if(Number(plan.appVersion.split('.').at(-1))>=97){
  const rowHeader=grid.getByRole('rowheader',{name:'1048576',exact:true});await rowHeader.scrollIntoViewIfNeeded();
  const shape=await rowHeader.evaluate(element=>{const range=document.createRange();range.selectNodeContents(element);return {cellWidth:element.getBoundingClientRect().width,textRects:Array.from(range.getClientRects()).map(rect=>({width:rect.width,height:rect.height}))};});
  assert.equal(shape.textRects.length,1,'The full saved row number must remain on one visible line');assert(shape.textRects[0].width<=shape.cellWidth);
  steps.push({step:'extreme-row-number-readable',actualTextRange:shape});save();
 }
 await grid.getByRole('button',{name:'原始文字',exact:true}).click();assert.equal(await grid.locator('pre').innerText(),storedTable.sections[0].text);
 await grid.getByRole('button',{name:'表格阅读',exact:true}).click();
 await panel.getByRole('textbox',{name:'查找材料文字',exact:true}).fill('12,000.00');await panel.locator('.document-pages mark').filter({hasText:'12,000.00'}).waitFor();await panel.getByRole('textbox',{name:'查找材料文字',exact:true}).fill('');
 for(const theme of ['dark','light']){const change=page.getByRole('button',{name:theme==='dark'?'切换至深色模式':'切换至浅色模式',exact:true});if(await change.count())await change.click();await grid.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'table-reading-'+theme+'.png')});}
 steps.push({step:'native-structured-table-reading',savedLayoutPresent:true,rawTextExact:true,literalSearchMatched:true,ordinaryThemeScreens:true});save();
 const original=path.join(plan.exportDirectory,'Companion-public-material088.xlsx');await dialog('document-save-original','save',original,null,()=>panel.getByRole('button',{name:'另存原件',exact:true}).click());await panel.getByText('文档原件已另存。',{exact:true}).waitFor();assert.equal(sha(original),plan.documentInputs.find(d=>d.name==='material.xlsx').sha256);
 await page.reload();await page.locator('.ct-shell').waitFor();await openMeeting();await panel.locator('.document-list article').filter({hasText:'material.docx'}).getByRole('button').first().click();await panel.locator('.document-pages').getByText(/预算草案为12000元/).waitFor();
 const after=row();assert.equal(after.transcriptText,before.transcriptText);assert.deepEqual(after.minutes,before.minutes);assert.deepEqual(after.meetingNotes,before.meetingNotes);assert.equal(after.audioStored,false);assert(!JSON.stringify(after.documentContext).includes('local-password'));
 await page.getByRole('button',{name:'问这场会议',exact:true}).click();const ai=page.getByRole('region',{name:'会议AI助手',exact:true});await ai.locator('.ai-scope > summary').click();const choices=await ai.locator('.ai-scope-list label').evaluateAll(nodes=>nodes.map(n=>({text:n.innerText,checked:n.querySelector('input').checked})));assert.equal(choices.filter(c=>c.checked).length,1);const materials=choices.filter(c=>c.text.includes('人工提供，非会议转写'));assert.equal(materials.length,6);assert(materials.every(c=>!c.checked));assert(!choices.some(c=>c.text.includes('no-text.pdf')));const meeting=ai.locator('.ai-scope-list label').filter({hasText:plan.title}).getByRole('checkbox');await meeting.uncheck();const material=ai.locator('.ai-scope-list label').filter({hasText:'material.docx'}).getByRole('checkbox');await material.check();await ai.getByText('已选 1 项资料 · 含人工补充材料',{exact:true}).waitFor();await ai.getByText(/不会发送音频、文档原件或密码/).waitFor();await ai.getByRole('button',{name:'设置AI服务',exact:true}).waitFor();assert.equal(await ai.getByRole('button',{name:'开始整理',exact:true}).count(),0);await material.uncheck();await meeting.check();
 await ai.getByText('已保存的 AI 草稿',{exact:false}).waitFor();await ai.getByRole('textbox',{name:'会议AI问题',exact:true}).fill('本机保留的待提问题');
 await ai.getByRole('button',{name:'阅读补充文档',exact:true}).click();const documentBounds=await panel.boundingBox();assert(documentBounds&&documentBounds.y>=-10&&documentBounds.y<await page.evaluate(()=>innerHeight));
 await page.getByRole('button',{name:'问这场会议',exact:true}).click();await ai.getByRole('button',{name:'查看人工备注',exact:true}).click();const noteBounds=await page.locator('#ct-recording-notes').boundingBox();assert(noteBounds&&noteBounds.y>=-10&&noteBounds.y<await page.evaluate(()=>innerHeight));
 await page.getByRole('button',{name:'问这场会议',exact:true}).click();assert.equal(await ai.getByRole('textbox',{name:'会议AI问题',exact:true}).inputValue(),'本机保留的待提问题');
 steps.push({step:'ordinary-ai-drafts-document-notes-return',unconfiguredServiceNotCalled:true,questionDraftRetained:true});save();
 steps.push({step:'native-explicit-ai-source-scope',readyDocuments:6,documentsUncheckedByDefault:true,noTextDocumentExcluded:true,unconfiguredServiceNotClaimedAsOnlineSuccess:true});save();
 for(const theme of ['dark','light']){const button=page.getByRole('button',{name:theme==='dark'?'切换至深色模式':'切换至浅色模式',exact:true});if(await button.count())await button.click();await panel.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'documents-'+theme+'.png')});}
 if(Number(plan.appVersion.split('.').at(-1))>=90){await page.getByRole('button',{name:'设备与同步',exact:true}).click();const input=page.locator('details[aria-label="电脑按住说话"]');await input.locator(':scope > summary').click();await input.getByText('先连接 Companion 录音卡。',{exact:true}).waitFor();await input.getByRole('status').waitFor();assert(await input.getByRole('button',{name:'启用按住说话',exact:true}).isDisabled());const paste=input.getByRole('combobox',{name:'输入框粘贴方式',exact:true});for(const mode of ['ctrlShiftV','shiftInsert','ctrlV']){await paste.selectOption(mode);assert.equal(await paste.inputValue(),mode);}assert.equal(await input.getByRole('alert').count(),0);await input.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'preserved-desktop-input.png')});steps.push({step:'preserved-installed089-desktop-input-entry',ordinaryDisconnectedEntryReadable:true,enableDisabledWithoutDevice:true,pasteModesSelectable:true,actualTauriStatusCommandUsed:true,physicalInputCaptureAsrPasteQualified:false});save();await input.locator(':scope > summary').click();}
 steps.push({step:'reopen-search-save-original',literalSearchMatched:true,originalSaveSha256:sha(original),originalTranscriptMinutesAndNotesUnchanged:true});save();return{state:'REAL_TAURI_DOCUMENT_ORIGINAL_IMPORT_EXTRACTION_RETRY_READ_SEARCH_REOPEN_AND_NATIVE_SAVE_PASSED',sessionId:plan.sessionId,documents:docs,checkpoints:steps,modelCalls:0,aiServiceCalls:0,sourceAudioInvented:false,ownerDataUsed:false,wholeSaleQualified:false};
};
