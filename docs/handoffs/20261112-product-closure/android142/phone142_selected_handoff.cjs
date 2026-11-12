// One continuous use on the installed Android142 and declared public library.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),cp=require('node:child_process'),crypto=require('node:crypto');
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',O=path.join(C,'android142');
const {connect,native}=require(path.join(C,'organization_ui.cjs')),{read}=require(path.join(C,'organization_readback.cjs'));
const A='C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';
const base=JSON.parse(fs.readFileSync(path.join(C,'android128/public-document-before.json'))),own=JSON.parse(fs.readFileSync(path.join(O,'public-libraries.json'))),prior=JSON.parse(fs.readFileSync(path.join(O,'detail-workflow.json'))),sleep=ms=>new Promise(r=>setTimeout(r,ms));
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
function adb(args,required=true){const r=cp.spawnSync(A,['-s','d6bd213d',...args],{windowsHide:true,timeout:30000,maxBuffer:8*1024**2});if(required)assert.equal(r.status,0,r.stderr?.toString());return r;}
(async()=>{const {page,browser,session}=await connect();try{
 assert.equal((await read(page,'appPreferences')).version,'0.1.142');assert.equal((await read(page,'libraryStatus')).activeId,own.working);
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('searchbox').fill('');await page.locator('.library-managed-list .row').filter({hasText:base.title}).click();
 await page.getByRole('tab',{name:'资料',exact:true}).click();const workspace=page.getByRole('region',{name:'会议补充资料',exact:true});await workspace.getByRole('tab',{name:'便签与图片',exact:true}).click();
 const before=await read(page,'recordingNotes',{key:base.key}),detail=await read(page,'detail',{key:base.key}),chosen=before.entries.find(n=>n.id===prior.quoteNote.id);assert(chosen&&chosen.references.length);const excluded='公开界面验收｜会后准备';
 const card=page.locator('.recording-notes .recording-note').filter({hasText:'公开原文准备｜'});await card.getByRole('button',{name:'导出这张清单',exact:true}).click();
 const panel=page.locator('details.content-export');assert(await panel.evaluate(n=>n.open));await panel.getByText('仅导出这条人工补充',{exact:true}).waitFor();
 const outputs=[];let firstPreview;
 for(const format of ['txt','bundle']){
  await panel.getByRole('combobox',{name:'导出文件格式',exact:true}).selectOption(format);await panel.getByRole('button',{name:'预览所选正文',exact:true}).click();
  const preview=panel.getByRole('region',{name:'所选正文预览',exact:true});await preview.waitFor();const text=await preview.locator('pre').textContent();assert(text.includes(chosen.text));assert(text.includes(chosen.references[0].quote));assert(!text.includes(excluded));assert(text.length>350,'Real saved literal source must be visible beyond the former350-character snippet');assert(!await preview.getByText('以下是正文片段，完整内容保留在文件中。',{exact:true}).isVisible());
  if(!firstPreview)firstPreview=text;else assert.equal(text,firstPreview);
  await page.screenshot({path:path.join(O,'selected-note-'+format+'-preview.png'),fullPage:true});
  const filename='Companion-public-selected142.'+(format==='bundle'?'zip':'txt'),remote='/sdcard/Download/'+filename;
  const local=path.join(O,filename),exists=adb(['shell','test','-e',remote],false).status===0;
  if(exists){assert.equal(format,'txt');assert(fs.existsSync(local));assert.deepEqual(adb(['exec-out','cat',remote]).stdout,fs.readFileSync(local),'Resume only the exact file from the first own save');}
  else{await panel.getByRole('button',{name:'保存文件',exact:true}).click();let ready=false;
  for(let i=0;i<25;i++){const result=JSON.parse(native('dump'));if(result.nodes.some(n=>n.id==='android:id/title'&&n.class==='android.widget.EditText')){ready=true;break;}await sleep(150);}
  assert(ready,'Owned-display native Save picker required');native('setText','id:android:id/title',filename);native('click','id:android:id/button1');
  await panel.getByRole('status').filter({hasText:'文件已保存到你选择的位置。'}).waitFor({timeout:60000});
  }
  const bytes=adb(['exec-out','cat',remote]).stdout;assert(bytes.length>0);fs.writeFileSync(path.join(O,filename),bytes);
  if(format==='txt')assert.equal(bytes.toString('utf8'),base.title+'\n\n'+text,'Actual saved TXT retains its document title and the exact full preview body');
  outputs.push({format,fileName:filename,remotePath:remote,bytes:bytes.length,sha256:digest(bytes),actualExternalFileReadBack:true,nativePickerOnOwnedDisplay:true});
 }
 assert.deepEqual((await read(page,'recordingNotes',{key:base.key})).entries,before.entries);const after=await read(page,'detail',{key:base.key});assert.equal(after.transcript,detail.transcript);assert.deepEqual(after.minutes,detail.minutes);
 fs.writeFileSync(path.join(O,'selected-note-result.json'),JSON.stringify({at:new Date().toISOString(),state:'ANDROID142_ACTUAL_SINGLE_NOTE_LITERAL_SOURCE_FULL_PREVIEW_NATIVE_SAVE_TXT_AND_BUNDLE_READBACK_PASSED',actualVersion:'0.1.142',publicLibrary:own.working,ownedDisplay:session.displayId,selectedNoteId:chosen.id,selectedNote:chosen,excludedMarker:excluded,previewCharacters:firstPreview.length,previewSha256:digest(Buffer.from(firstPreview)),outputs,notesTranscriptMinutesUnchanged:true,ownerMainDisplayOperated:false,modelsCloudMicBleUsed:false,ordinaryMessengerSendQualified:false},null,2)+'\n');
 console.log('Android142 full selected note/source preview and native TXT+ZIP external file receipt passed.');
}catch(error){try{fs.writeFileSync(path.join(O,'selected-note-failure-public-body.txt'),await page.locator('body').innerText());await page.screenshot({path:path.join(O,'selected-note-failure.png'),fullPage:true});}catch{}throw error;}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
