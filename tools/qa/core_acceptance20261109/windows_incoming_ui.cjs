// Ordinary file-argument delivery and controls on the disposable native CI desktop.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto'),cp=require('node:child_process');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
module.exports=async function incomingJourney(page,plan,out){
 const steps=[],warm=[],receiptPath=plan.statePath+'.incoming-v1.json';
 const write=(state='RUNNING')=>fs.writeFileSync(path.join(out,'incoming-ui.json'),JSON.stringify({state,steps,warm,modelsRun:false,cloudCalled:false,ownerDesktopUsed:false},null,2));
 const rows=()=>JSON.parse(fs.readFileSync(plan.statePath,'utf8'));
 const receipt=()=>JSON.parse(JSON.parse(fs.readFileSync(receiptPath,'utf8')).body).rows;
 const card=file=>page.locator('.incoming-file').filter({hasText:path.basename(file)});
 const sha=async file=>{const hash=crypto.createHash('sha256');for await(const chunk of fs.createReadStream(file))hash.update(chunk);return hash.digest('hex');};
 async function poll(test,message,timeout=45000){const start=Date.now();while(Date.now()-start<timeout){if(await test())return;await wait(80);}throw Error(message);}
 function openFile(file){
  assert(fs.existsSync(file)&&path.dirname(file)===plan.receivedDirectory,'Only this case public files may enter the OS launch');
  const start=Date.now(),run=cp.spawnSync(plan.appExecutable,[file],{cwd:path.dirname(plan.appExecutable),env:process.env,windowsHide:true,timeout:20000,encoding:'utf8'});
  warm.push({name:path.basename(file),exitCode:run.status,signal:run.signal,seconds:(Date.now()-start)/1000});write();
  assert.equal(run.status,0,'Warm file delivery must exit before starting another GUI/device owner: '+(run.stderr||'').slice(-500));
 }
 const original=rows(),protectedFields=['id','title','transcriptText','minutes','minutesByMode','meetingNotes','documentContext','audioPath','chunks','retention'];
 function sameExisting(actual,expected,label){if(expected===null||expected===undefined){assert(actual===null||actual===undefined,'Unrelated null field changed: '+label);return;}if(Array.isArray(expected)){assert(Array.isArray(actual)&&actual.length===expected.length,'Unrelated array changed: '+label);expected.forEach((value,index)=>sameExisting(actual[index],value,label+'.'+index));return;}if(typeof expected==='object'){assert(actual&&typeof actual==='object','Unrelated object disappeared: '+label);for(const [name,value] of Object.entries(expected))sameExisting(actual[name],value,label+'.'+name);return;}assert.deepEqual(actual,expected,'Unrelated field changed: '+label);}
 function protect(){for(const old of original){const current=rows().find(row=>row.id===old.id);assert(current,'An unrelated record disappeared');for(const field of protectedFields){if(field==='documentContext'&&old[field]==null){assert(!current[field]||current[field].revision===0&&current[field].rows.length===0,'Unrelated documents added');continue;}sameExisting(current[field],old[field],field);}}}

 await card(plan.incomingAudio).waitFor();assert.equal(receipt().length,1);assert.equal(receipt()[0].state,'ready');assert.equal(rows().length,original.length);
 steps.push({step:'cold-normal-file-launch',pendingOnly:true,originalNotImportedBeforeConfirmation:true});write();
 openFile(plan.incomingAudio);await wait(2300);assert.equal(receipt().length,1,'Pending duplicate launch must use one receipt');
 await card(plan.incomingAudio).getByRole('button',{name:'存为新录音',exact:true}).click();
 await poll(()=>receipt().some(item=>item.name===path.basename(plan.incomingAudio)&&item.state==='complete'),'Normal media reception did not commit');
 await card(plan.incomingAudio).getByRole('button',{name:'打开所属录音',exact:true}).waitFor();
 const savedAudio=rows().find(row=>row.source==='importedAudio');assert(savedAudio);const key=savedAudio.id;
 assert.equal(rows().length,original.length+1);assert.equal(savedAudio.transcriptText,'');assert(!savedAudio.minutes);
 const originalChunk=savedAudio.chunks.find(item=>item.status==='importedOriginal');assert(originalChunk);assert.equal(await sha(originalChunk.path),plan.incomingAudioSha256);assert.equal(await sha(plan.incomingAudio),plan.incomingAudioSha256);protect();
 steps.push({step:'explicit-media-confirmation',key,originalBytesIdentical:true,pendingDuplicateCreatedNoRecord:true});write();
 // Reopening the source after a completed delivery is another explicit pending choice.
 openFile(plan.incomingAudio);await poll(()=>receipt().filter(item=>item.name===path.basename(plan.incomingAudio)).length===2,'Completed-source reopening did not ask for a new confirmation');
 const pendingAudio=card(plan.incomingAudio).filter({has:page.getByRole('button',{name:'移除待接收项',exact:true})});
 await pendingAudio.getByRole('button',{name:'移除待接收项',exact:true}).click();await poll(()=>receipt().length===1,'Scoped dismissal did not finish');assert.equal(rows().length,original.length+1);assert.equal(await sha(originalChunk.path),plan.incomingAudioSha256);
 const doc=plan.documentInputs.find(item=>item.name==='material.docx');openFile(doc.path);await card(doc.path).waitFor();
 await card(doc.path).getByRole('combobox').selectOption({label:savedAudio.title});
 // The source is temporarily unavailable after sharing. The error must keep the fixed target.
 const moved=doc.path+'.temporarily-moved';fs.renameSync(doc.path,moved);
 try{
  await card(doc.path).getByRole('button',{name:'保存到所选会议',exact:true}).click();
  await poll(()=>receipt().some(item=>item.name===doc.name&&item.state==='failed'),'Unavailable file was not reported');
  const failed=receipt().find(item=>item.name===doc.name);assert.equal(failed.key,key);assert.equal((rows().find(item=>item.id===key).documentContext?.rows||[]).length,0);
 }finally{fs.renameSync(moved,doc.path);}
 await card(doc.path).getByRole('button',{name:'在原目标核对并重试',exact:true}).click();
 await poll(()=>receipt().some(item=>item.name===doc.name&&item.state==='complete'),'Document retry did not finish');
 const docRow=rows().find(item=>item.id===key),document=docRow.documentContext.rows[0];assert.equal(docRow.documentContext.rows.length,1);assert.equal(document.sourceSha256,doc.sha256);
 assert.equal(await sha(path.join(plan.recordingDirectory,document.file)),doc.sha256);assert.equal(await sha(doc.path),doc.sha256);protect();
 steps.push({step:'warm-document-expiry-and-original-target-retry',oneDocument:true,sourceAndStoredOriginalIdentical:true});write();
 openFile(plan.incomingImage);await card(plan.incomingImage).waitFor();await card(plan.incomingImage).getByRole('combobox').selectOption({label:savedAudio.title});await card(plan.incomingImage).getByRole('button',{name:'保存到所选会议',exact:true}).click();
 await poll(()=>receipt().some(item=>item.name===path.basename(plan.incomingImage)&&item.state==='complete'),'Image reception did not finish');
 const imageRow=rows().find(item=>item.id===key),image=imageRow.meetingNotes[0].image;assert.equal(imageRow.meetingNotes.length,1);assert.equal(image.sha256,plan.incomingImageSha256);assert.equal(await sha(path.join(plan.recordingDirectory,image.file)),plan.incomingImageSha256);protect();
 steps.push({step:'warm-image-explicit-ownership',oneImage:true,originalBytesIdentical:true});write();
 await page.screenshot({path:path.join(out,'incoming-files-native.png'),fullPage:true});
 await card(plan.incomingImage).getByRole('button',{name:'打开所属录音',exact:true}).click();await page.locator('#ct-saved-recording-workspace').waitFor();await poll(async()=>await page.locator('#ct-saved-recording-workspace .ct-title-editor input').inputValue()===savedAudio.title,'Delivered record title/input did not match the saved target');
 steps.push({step:'ordinary-open-delivered-record',correctRecord:true});write();
 openFile(plan.incomingBad);await card(plan.incomingBad).waitFor();await card(plan.incomingBad).getByRole('button',{name:'存为新录音',exact:true}).click();await poll(()=>receipt().some(item=>item.name===path.basename(plan.incomingBad)&&item.state==='failed'),'Invalid audio was not rejected');
 assert.equal(rows().length,original.length+1);assert.equal(await sha(plan.incomingBad),plan.incomingBadSha256);protect();steps.push({step:'bad-file-rejected',noNewRecord:true,sourceUnchanged:true});write();
 openFile(plan.incomingLong);await card(plan.incomingLong).waitFor();const start=card(plan.incomingLong).getByRole('button',{name:'存为新录音',exact:true});await start.click();
 await poll(()=>{const item=receipt().find(item=>item.name===path.basename(plan.incomingLong));if(!item||item.state!=='attempting')return false;const staged=path.join(plan.recordingDirectory,'import-'+item.id.replaceAll('-','')+'.original.wav');return fs.existsSync(staged)&&fs.statSync(staged).size>65536;},'Long import never entered the original copy operation');
 await card(plan.incomingLong).getByRole('button',{name:'取消此次导入',exact:true}).click();
 await poll(()=>receipt().some(item=>item.name===path.basename(plan.incomingLong)&&item.state==='failed'),'Cancelled import did not retire');
 const cancelled=receipt().find(item=>item.name===path.basename(plan.incomingLong));assert(cancelled.message.includes('取消'),cancelled.message);assert(!rows().some(row=>row.id===cancelled.key));assert.equal(await sha(plan.incomingLong),plan.incomingLongSha256);assert(!fs.readdirSync(plan.recordingDirectory).some(name=>name.startsWith('import-'+cancelled.id.replaceAll('-',''))));protect();
 steps.push({step:'actual-two-hour-public-pcm-import-cancel',noSavedCancelledRecording:true,exactPartialFilesRetired:true,sourceUnchanged:true,notAsrOrMeetingQualityTest:true});write();
 for(const item of receipt()){
  const match=page.locator('.incoming-file').filter({hasText:item.name});await match.getByRole('button',{name:item.state==='complete'?'收起此条记录':'移除待接收项',exact:true}).click();
  await poll(()=>!receipt().some(row=>row.id===item.id),'Receipt dismissal did not finish');
 }
 assert.equal(receipt().length,0);assert.equal(rows().length,original.length+1);assert.equal(await sha(originalChunk.path),plan.incomingAudioSha256);assert.equal(await sha(path.join(plan.recordingDirectory,document.file)),doc.sha256);assert.equal(await sha(path.join(plan.recordingDirectory,image.file)),plan.incomingImageSha256);protect();
 write('REAL_TAURI_OS_INCOMING_COLD_WARM_CONFIRM_DOCUMENT_IMAGE_RETRY_CANCEL_AND_ORIGINALS_PASSED');
 return {state:'REAL_TAURI_OS_INCOMING_COLD_WARM_CONFIRM_DOCUMENT_IMAGE_RETRY_CANCEL_AND_ORIGINALS_PASSED',steps,warm,originalRowsRetained:original.length,sourceAndSavedOriginalsByteIdentical:true,modelOrCloudCalls:0};
};
