// Actual packaged Tauri controls; public input only, no command mocks.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
module.exports=async function editingJourney(page,plan,out){
 const steps=[],outputs=[],save=()=>fs.writeFileSync(path.join(out,'editing-checkpoints.json'),JSON.stringify(steps,null,2));
 const rows=()=>JSON.parse(fs.readFileSync(plan.statePath,'utf8'));
 async function dialog(id,file,hash,trigger){
  fs.writeFileSync(path.join(out,'dialog-request-'+id+'.json'),JSON.stringify({action:'open',path:file,sha256:hash}));
  await trigger();const reply=path.join(out,'dialog-reply-'+id+'.json'),until=Date.now()+90000;
  while(!fs.existsSync(reply)&&Date.now()<until)await wait(100);assert(fs.existsSync(reply),'Native picker did not complete');
  assert.equal(JSON.parse(fs.readFileSync(reply)).state,'OWNED_NATIVE_FILE_PICKER_ACTION_COMPLETED');
 }
 async function open(title){
  await page.getByRole('button',{name:'我的记录',exact:true}).click();
  await page.locator('.ct-library-card').filter({hasText:title}).click();await page.locator('#ct-saved-recording-workspace').waitFor();
  const edit=page.locator('.audio-derivation');await edit.locator(':scope > summary').click();return edit;
 }
 async function prepare(edit){
  await edit.getByRole('button',{name:'准备这条录音',exact:true}).click();
  await edit.getByLabel('新录音名称',{exact:true}).waitFor({timeout:90000});
 }
 async function finish(edit,names){
  const until=Date.now()+180000;
  while(Date.now()<until){if(names.every(name=>rows().some(r=>r.title===name))&&await edit.locator('.audio-derivation-result').isVisible())break;await wait(200);}
  for(const name of names){await edit.getByText('已保存：'+name,{exact:true}).waitFor({timeout:20000});const row=rows().find(r=>r.title===name);assert(row);assert.equal(row.source,'derivedAudio');assert.equal(row.transcriptText,'');assert.equal(row.minutes,null);assert.equal(row.meetingNotes.length,0);outputs.push(row.id);}
  assert.equal(new Set(outputs).size,outputs.length);steps.push({step:'ordinary-save',names,ids:outputs.slice(-names.length)});save();
 }
 await page.bringToFront();await page.getByRole('button',{name:'设备与同步',exact:true}).click();
 await dialog('edit-public-import',plan.audioInput,plan.audioSha256,()=>page.getByRole('button',{name:'选择音频文件',exact:true}).click());
 await page.getByRole('region',{name:'导入已有音频'}).getByRole('status').getByText('音频已保存，可在录音资料中回听和转写。',{exact:true}).waitFor({timeout:90000});
 const parent=rows().find(r=>r.source==='importedAudio');assert(parent);const baseline=structuredClone(parent);
 let edit=await open(parent.title);await prepare(edit);
 await edit.getByLabel('片段1开始时间',{exact:true}).fill('0:10');await edit.getByLabel('片段1结束时间',{exact:true}).fill('0:25');
 await edit.getByLabel('新录音名称',{exact:true}).fill('公开验收093 · 裁剪15秒');
 await page.getByRole('button',{name:'设备与同步',exact:true}).click();
 assert(await edit.isVisible());assert.equal(await edit.getByLabel('片段1开始时间',{exact:true}).inputValue(),'0:10');
 steps.push({step:'unsaved-edit-navigation-retains-input'});save();
 await edit.getByRole('button',{name:'另存这个片段',exact:true}).click();await finish(edit,['公开验收093 · 裁剪15秒']);
 const trim=rows().find(r=>r.title==='公开验收093 · 裁剪15秒');
 await edit.getByRole('button',{name:'按时间切分',exact:true}).click();await edit.getByLabel('新录音名称',{exact:true}).fill('公开验收093 · 全场切分');
 await edit.getByRole('textbox',{name:'切分时间',exact:true}).fill('0:30');
 await edit.getByRole('button',{name:'保存切分后的各段',exact:true}).click();await finish(edit,['公开验收093 · 全场切分 · 第1段','公开验收093 · 全场切分 · 第2段']);
 await edit.getByRole('button',{name:'合并录音',exact:true}).click();await edit.getByLabel('新录音名称',{exact:true}).fill('公开验收093 · 重排合并8秒');
 await edit.getByLabel('片段1开始时间',{exact:true}).fill('0:01');await edit.getByLabel('片段1结束时间',{exact:true}).fill('0:04');
 await edit.getByRole('combobox',{name:'加入其他录音',exact:true}).selectOption(trim.id);await edit.getByRole('button',{name:'加入',exact:true}).click();
 await edit.getByLabel('片段2开始时间',{exact:true}).fill('0:05');await edit.getByLabel('片段2结束时间',{exact:true}).fill('0:10');
 await edit.getByRole('button',{name:'将片段2上移',exact:true}).click();await edit.getByRole('button',{name:'另存合并录音',exact:true}).click();await finish(edit,['公开验收093 · 重排合并8秒']);
 const merged=rows().find(r=>r.title==='公开验收093 · 重排合并8秒');
 assert.equal(rows().filter(r=>r.id===parent.id).length,1);const after=rows().find(r=>r.id===parent.id);
 for(const key of ['transcriptText','minutes','meetingNotes','audioPath','chunks','durationMs'])assert.deepEqual(after[key],baseline[key]);
 await page.reload();await page.locator('.ct-shell').waitFor();edit=await open(merged.title);
 const source=edit.getByRole('region',{name:'这份录音的来源',exact:true});await source.getByRole('button',{name:'回听原片段',exact:true}).first().waitFor({timeout:90000});
 await source.getByRole('button',{name:'回听原片段',exact:true}).first().click();
 await page.waitForFunction(()=>{const a=document.querySelector('#ct-recording-playback audio');return a&&a.readyState>=1&&Math.abs(a.currentTime-5)<.2;},{},{timeout:90000});
 assert(await page.getByRole('heading',{name:trim.title,exact:true}).count()||await page.getByText(trim.title,{exact:true}).count());
 steps.push({step:'reopen-and-native-validated-original-position',sourceSessionId:trim.id,positionMs:5000,physicalListeningQualified:false});save();
 edit=await open(merged.title);
 for(const theme of ['dark','light']){
  const toggle=page.getByRole('button',{name:theme==='dark'?'切换至深色模式':'切换至浅色模式',exact:true});if(await toggle.count())await toggle.click();
  await edit.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'audio-edit-'+theme+'.png')});
 }
 const result={state:'REAL_TAURI_PUBLIC_AUDIO_TRIM_FULL_SPLIT_REORDER_MERGE_SOURCE_RETURN_AND_REOPEN_PASSED',parentId:parent.id,trimId:trim.id,mergedId:merged.id,outputIds:outputs,checkpoints:steps,generatedTranscriptOrMinutes:false,modelsRun:false,cloudCalls:0,wholeSaleQualified:false};
 fs.writeFileSync(path.join(out,'audio-edit-ui.json'),JSON.stringify(result,null,2));return result;
};
