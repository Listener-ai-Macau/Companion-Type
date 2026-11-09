const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
module.exports=async function audioJourney(page,plan,out){
 const checkpoints=[];const save=()=>fs.writeFileSync(path.join(out,'audio-checkpoints.json'),JSON.stringify(checkpoints,null,2));
 async function dialog(id,action,file,hash,trigger){
  const request=path.join(out,'dialog-request-'+id+'.json');fs.writeFileSync(request,JSON.stringify({action,path:file,sha256:hash}));
  await trigger();const reply=path.join(out,'dialog-reply-'+id+'.json'),until=Date.now()+120000;
  while(!fs.existsSync(reply)&&Date.now()<until)await wait(100);
  assert.ok(fs.existsSync(reply),'Actual native picker action must complete: '+id);
  const result=JSON.parse(fs.readFileSync(reply,'utf8'));assert.equal(result.state,'OWNED_NATIVE_FILE_PICKER_ACTION_COMPLETED');
  checkpoints.push({step:id,nativePicker:result.action});save();
 }
 async function openAudio(id,file,hash,title){
  await page.getByRole('button',{name:'设备与同步',exact:true}).click();
  await dialog(id,'open',file,hash,()=>page.getByRole('button',{name:'选择音频文件',exact:true}).click());
  const status=page.getByRole('region',{name:'导入已有音频'}).getByRole('status');
  await status.getByText('音频已保存，可在录音资料中回听和转写。',{exact:true}).waitFor({timeout:90000});
  await page.getByRole('button',{name:'我的记录',exact:true}).click();
  await page.locator('.ct-library-card').filter({hasText:title}).click();
  await page.locator('#ct-saved-recording-workspace').waitFor({state:'visible'});
 }
 async function playback(id){
  await page.getByRole('button',{name:'回听',exact:true}).click();
  const player=page.getByRole('region',{name:'本机原音回听'}),audio=player.locator('audio');
  await audio.waitFor();await page.waitForFunction(()=>document.querySelector('#ct-recording-playback audio')?.duration>2300);
  const duration=await audio.evaluate(a=>a.duration);assert.ok(Math.abs(duration-plan.audioSeconds)<.6,'Whole meeting duration must be playable');
  const probes=[];
  for(const seconds of [0,plan.audioSeconds/2,plan.audioSeconds-8]){
   await audio.evaluate((a,time)=>{a.currentTime=time;},seconds);await wait(250);
   await audio.press('Space');
   await page.waitForFunction(()=>{const audio=document.querySelector('#ct-recording-playback audio');return audio&&!audio.paused&&audio.currentTime>.2&&!audio.error;},{},{timeout:15000});
   const first=await player.locator('audio').evaluate(audio=>({time:audio.currentTime,src:audio.currentSrc,duration:audio.duration,error:audio.error?.code??null}));
   await wait(700);const after=await player.locator('audio').evaluate(audio=>audio.currentTime);assert.ok(after>first.time+.2,'Decoded playback time must advance');
   await audio.press('Space');probes.push({meetingPosition:seconds,decodedTimeAdvanced:true,mediaError:first.error});
  }
  checkpoints.push({step:id,duration,probes,playControl:'native audio Space key',seekProbe:'HTMLMediaElement.currentTime; native seek UI not qualified',mutedByTestRuntime:true,physicalListeningQualified:false});save();
 }
 async function receive(id){
  const copy=page.getByRole('button',{name:'复制录音文件',exact:true});if(!await copy.isVisible())await page.locator('.ct-recording-audio-export > details > summary').click();
  await copy.click();
  await page.getByText(/文件已复制：/).waitFor({timeout:120000});
  const message=await page.getByText(/文件已复制：/).innerText();const fileName=message.match(/文件已复制：(.+?)。可在/s)?.[1];assert.ok(fileName);assert.match(message,/文件尚未发送/);
  fs.writeFileSync(path.join(out,'handoff-request-'+id+'.json'),JSON.stringify({fileName}));
  const reply=path.join(out,'handoff-reply-'+id+'.json'),until=Date.now()+30000;while(!fs.existsSync(reply)&&Date.now()<until)await wait(100);
  assert.ok(fs.existsSync(reply),'Windows Shell must actually receive '+id);const result=JSON.parse(fs.readFileSync(reply,'utf8'));checkpoints.push({step:id,...result});save();return result;
 }
 await openAudio('import-real-public-wav',plan.audioInput,plan.audioSha256,plan.audioTitle);
 if(plan.requireGroupedUi){
  assert.ok(await page.getByRole('button',{name:'导出录音',exact:true}).isVisible());
  assert.ok(await page.getByRole('button',{name:'转文字',exact:true}).isVisible());
  assert.equal(await page.getByRole('region',{name:'会议AI助手',exact:true}).count(),0);
  checkpoints.push({step:'audio-only-next-step',directAudioExportVisible:true,transcribeVisible:true,inapplicableAiWorkbenchAbsent:true});save();
 }
 await playback('play-whole-public-wav');
 // The public audio controls are inside the existing More disclosure.
 const format=page.getByLabel('音频副本格式');
 if(!await format.isVisible()){
  const direct=page.getByRole('button',{name:'导出录音',exact:true});
  if(await direct.count())await direct.click();
  else await page.locator('#ct-saved-recording-workspace details').filter({has:format}).last().locator(':scope > summary').click();
 }
 await format.selectOption('original');
 await dialog('save-original-wav','save',path.join(plan.exportDirectory,'original.wav'),null,()=>page.getByRole('button',{name:'保存原音',exact:true}).click());
 await page.getByText('录音已保存：original.wav',{exact:true}).waitFor({timeout:30000});
 await receive('audio-original');
 await format.selectOption('mp3');
 await dialog('save-mp3','save',path.join(plan.exportDirectory,'compatible.mp3'),null,()=>page.getByRole('button',{name:'保存 MP3 副本',exact:true}).click());
 await page.getByText('录音已保存：compatible.mp3',{exact:true}).waitFor({timeout:120000});
 const mp3=await receive('audio-mp3');
 await openAudio('decode-exported-mp3',path.join(plan.receivedDirectory,mp3.fileName),mp3.sha256,path.parse(mp3.fileName).name);
 await playback('play-decoded-exported-mp3');
 await page.screenshot({path:path.join(out,'native-real-audio-roundtrip.png'),fullPage:true});
 return {state:'REAL_NATIVE_PUBLIC_AUDIO_IMPORT_PLAYBACK_EXPORT_AND_SHELL_HANDOFF_PASSED',checkpoints,modelsRun:false,aiCalls:0,captureOrAcousticQualityQualified:false};
};
