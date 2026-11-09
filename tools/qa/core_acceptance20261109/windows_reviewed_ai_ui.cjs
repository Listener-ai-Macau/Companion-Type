const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
module.exports=async function reviewedAiJourney(page,plan,out){
 assert.ok(plan.requireGroupedUi,'Use the inspected new candidate, not a relabeled old binary');
 await page.locator('.ct-library-card').filter({hasText:plan.title}).click();
 const workspace=page.locator('#ct-saved-recording-workspace');await workspace.waitFor({state:'visible'});
 await workspace.getByRole('button',{name:'会议纪要',exact:true}).click();
 const minutes=workspace.locator('#ct-recording-result');
 await minutes.getByRole('heading',{name:'会中问题',exact:true}).waitFor();
 assert.equal(await minutes.getByRole('heading',{name:'待解问题',exact:true}).count(),0);
 const summary=minutes.getByText(new RegExp('长会议已整理全部 '+plan.aiChunks+' 段'));await summary.waitFor();
 const full=minutes.getByText('查看完整摘要和关键词',{exact:true});
 if(await full.count() && !await minutes.getByText(/周一至周五人流量稍少/).isVisible())await full.click();
 if(plan.wholeMeetingDelivery)assert.ok((await minutes.innerText()).includes(plan.expectedExportContains));
 else assert.match(await minutes.innerText(),/周一至周五/);
 if(plan.wholeMeetingDelivery){
  await workspace.getByRole('button',{name:'回听',exact:true}).click();const audio=workspace.locator('#ct-recording-playback audio');await audio.waitFor();
  await page.waitForFunction(()=>document.querySelector('#ct-recording-playback audio')?.duration>2300);
  await audio.press('Space');await page.waitForFunction(()=>document.querySelector('#ct-recording-playback audio')?.currentTime>.4);await audio.press('Space');
 }
 await page.screenshot({path:path.join(out,'reviewed-ai-minutes-reading.png'),fullPage:true});
 await workspace.getByRole('button',{name:'导出分享',exact:true}).click();
 const panel=workspace.locator('#ct-meeting-export');
 await panel.getByLabel('所选内容文件格式').waitFor({state:'visible'});
 assert.equal(await panel.evaluate(node=>node.open),true,'Top export must reveal the selected-content panel');
 await panel.getByLabel('整理结果',{exact:true}).check();await panel.getByLabel('录音文字',{exact:true}).uncheck();
 await panel.getByLabel('所选内容文件格式').selectOption('docx');
 await panel.locator('.ct-content-share-alternative > summary').click();
 await panel.getByRole('button',{name:'复制所选文件',exact:true}).click();
 const feedback=panel.getByLabel('所选内容操作结果');await feedback.getByText(/文件已复制：/).waitFor({timeout:60000});
 const message=await feedback.innerText();assert.match(message,/文件尚未发送/);
 const fileName=message.match(/文件已复制：(.+?)。可在/s)?.[1];assert.ok(fileName?.endsWith('.docx'));
 const request=path.join(out,'handoff-request-ai-docx.json');fs.writeFileSync(request+'.tmp',JSON.stringify({fileName}));fs.renameSync(request+'.tmp',request);
 const reply=path.join(out,'handoff-reply-ai-docx.json'),until=Date.now()+60000;
 while(!fs.existsSync(reply)&&Date.now()<until)await new Promise(resolve=>setTimeout(resolve,100));
 assert.ok(fs.existsSync(reply),'Actual Windows Shell must receive the reviewed AI document');
 const received=JSON.parse(fs.readFileSync(reply,'utf8'));assert.ok(received.actualFileReceived&&received.selectedContentsVerified);
 const attachmentReceipts=[received];
 if(plan.browserAttachments){
  async function receiveAttachment(id,scope,copy){
   await copy.click();const feedback=scope.getByText(/文件已复制：/);await feedback.waitFor({timeout:120000});
   const message=await feedback.innerText();assert.match(message,/文件尚未发送/);const fileName=message.match(/文件已复制：(.+?)。可在/s)?.[1];assert.ok(fileName);
   const request=path.join(out,'handoff-request-'+id+'.json');fs.writeFileSync(request+'.tmp',JSON.stringify({fileName}));fs.renameSync(request+'.tmp',request);
   const reply=path.join(out,'handoff-reply-'+id+'.json'),until=Date.now()+60000;while(!fs.existsSync(reply)&&Date.now()<until)await new Promise(resolve=>setTimeout(resolve,100));
   assert.ok(fs.existsSync(reply),'Actual browser and Shell must receive '+id);const result=JSON.parse(fs.readFileSync(reply,'utf8'));
   assert.ok(result.actualFileReceived&&result.browserAttachment?.trustedNativePaste);assert.equal(result.sha256,result.browserAttachment.sha256);attachmentReceipts.push(result);
  }
  for(const format of ['txt','pdf']){
   await panel.getByLabel('所选内容文件格式').selectOption(format);
   await receiveAttachment('ai-'+format,panel.getByLabel('所选内容操作结果'),panel.getByRole('button',{name:'复制所选文件',exact:true}));
  }
  await workspace.getByRole('button',{name:'导出录音',exact:true}).click();const audio=workspace.locator('.ct-recording-audio-export');
  const copy=audio.getByRole('button',{name:'复制录音文件',exact:true});
  if(!await copy.isVisible())await audio.locator(':scope > details > summary').click();
  for(const format of ['original','mp3']){
   await audio.getByLabel('音频副本格式').selectOption(format);await receiveAttachment('audio-'+format,audio,copy);
  }
 }
 await workspace.getByRole('button',{name:'问这场会议',exact:true}).click();
 await page.getByRole('region',{name:'会议AI助手',exact:true}).waitFor({state:'visible'});
 await page.screenshot({path:path.join(out,'reviewed-ai-workbench-and-export.png'),fullPage:true});
 return {state:plan.wholeMeetingDelivery?'ACTUAL_SAME_AUDIO_ASR_AI_READING_PLAYBACK_WORD_HANDOFF_PASSED':'ACTUAL_REVIEWED_AI_READING_MAIN_EXPORT_AND_SHELL_HANDOFF_PASSED',sourceMeeting:plan.sourceMeeting,
  cachedRealCloudAi:true,manualSourceReviewDeclared:!plan.wholeMeetingDelivery,sameAudioAndActualAsrLineage:!!plan.wholeMeetingDelivery,newCloudCalls:0,newAsrRun:false,neutralQuestionHeading:true,
  completeTwoChunkNotice:true,topExportOpensSelectedContent:true,received,attachmentReceipts,aiWorkbenchAvailableAfterFinalText:true,
  customerOrBusinessFactQualityQualified:false};
};
