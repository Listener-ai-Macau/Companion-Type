const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),crypto=require('crypto');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const digest=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
module.exports=async(page,plan,out,reopened)=>{
 const spec=plan.publicSourceImport,rows=()=>JSON.parse(fs.readFileSync(plan.statePath,'utf8'));
 assert.equal(spec.publicSourceOnly,true);assert.equal(digest(spec.audioInput),spec.audioSha256);
 let row;
 if(!reopened){
  const before=rows();const incoming=page.locator('.incoming-file').filter({hasText:path.basename(spec.audioInput)});
  await incoming.getByRole('button',{name:'存为新录音',exact:true}).waitFor({timeout:30000});
  await incoming.getByRole('button',{name:'存为新录音',exact:true}).click();
  await incoming.getByRole('button',{name:'打开所属录音',exact:true}).waitFor({timeout:90000});
  const added=rows().filter(r=>!before.some(old=>old.id===r.id));assert.equal(added.length,1);row=added[0];
  assert.equal(row.source,'importedAudio');assert(row.audioStored);assert(Math.abs(row.durationMs-spec.durationSeconds*1000)<100);
  const original=row.chunks.find(c=>c.status==='importedOriginal');assert(original);assert.equal(digest(original.path),spec.audioSha256);
  await incoming.getByRole('button',{name:'打开所属录音',exact:true}).click();await page.getByRole('navigation',{name:'会议工作区',exact:true}).waitFor();
  const started=Date.now();await page.getByRole('button',{name:'转文字',exact:true}).click();
  const deadline=Date.now()+360000;
  while(Date.now()<deadline){row=rows().find(r=>r.id===row.id);if(row.transcriptFinal)break;await delay(300);}
  assert(row.transcriptFinal,'The ordinary fixed local ASR must finish');assert(row.transcriptText.length>6000);assert((row.transcriptText.match(/[，。？！；：]/g)||[]).length>100);
  assert.deepEqual(rows().filter(r=>r.id!==row.id),before,'Import and ASR must preserve earlier library rows');
  assert.equal(digest(original.path),spec.audioSha256);assert.equal(digest(spec.audioInput),spec.audioSha256);
  plan.sessionId=row.id;plan.title=row.title;plan.publicImportedTextSha256=crypto.createHash('sha256').update(row.transcriptText).digest('hex');
  fs.writeFileSync(path.join(out,'plan.json'),JSON.stringify(plan,null,2));fs.writeFileSync(path.join(out,'actual-imported-session.json'),JSON.stringify(row,null,2));fs.writeFileSync(path.join(out,'actual-source-transcript.txt'),row.transcriptText);
  fs.writeFileSync(path.join(out,'public-source-import.json'),JSON.stringify({sessionId:row.id,source:'importedAudio',sourceAudioSha256:spec.audioSha256,originalPath:original.path,decodedPath:row.audioPath,decodedAudioSha256:digest(row.audioPath),durationMs:row.durationMs,transcriptSha256:plan.publicImportedTextSha256,asrSeconds:(Date.now()-started)/1000,modelsRun:true,cloudCalls:0,boardOrAcousticQualification:false},null,2));
 }else{
  assert(plan.previousAppExited);assert.deepEqual(rows(),plan.expectedSnapshot);row=rows().find(r=>r.id===plan.sessionId);assert(row?.transcriptFinal);assert.equal(crypto.createHash('sha256').update(row.transcriptText).digest('hex'),plan.publicImportedTextSha256);
  await page.locator('.ct-library-card').filter({hasText:row.title}).click();await page.getByRole('navigation',{name:'会议工作区',exact:true}).waitFor();
 }
 await page.getByRole('navigation',{name:'会议工作区',exact:true}).getByRole('button',{name:'文字',exact:true}).click();await page.locator('#ct-recording-text').waitFor();
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'actual-public-source-transcript-viewport.png'),fullPage:false});
 return {state:reopened?'ACTUAL_PUBLIC_SOURCE_IMPORT_AND_ASR_REOPENED':'ACTUAL_PUBLIC_SOURCE_ORDINARY_NATIVE_IMPORT_AND_LOCAL_ASR_PASSED',sessionId:row.id,previousAppExited:reopened?plan.previousAppExited:undefined,allPublicLibraryRowsUnchanged:!!reopened,newAsrRun:!reopened,sourceAudioSha256:spec.audioSha256,modelWordsOrReferenceSubstituted:false,cloudCalls:0,ownerForegroundUsed:false,boardOrAcousticQualification:false};
};
