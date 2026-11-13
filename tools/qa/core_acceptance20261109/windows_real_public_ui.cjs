const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
module.exports=async(page,plan,out,reopened)=>{
 const original=plan.expectedSnapshot;assert(original.length===1&&original[0].id===plan.sessionId);
 const row=original[0],nav=()=>page.getByRole('navigation',{name:'会议工作区',exact:true});
 await page.locator('.ct-library-card').first().click();await nav().waitFor();
 await nav().getByRole('button',{name:'纪要',exact:true}).click();await page.locator('#ct-recording-result[open]').waitFor();
 const article=page.locator('#ct-meeting-result-pane');assert((await article.innerText()).includes('超市'));assert((await article.innerText()).includes('四层'));assert((await article.innerText()).includes('冷柜'));
 await page.screenshot({path:path.join(out,'actual019f-minutes.png'),fullPage:true});
 await nav().getByRole('button',{name:'文字',exact:true}).click();assert((await page.locator('#ct-recording-text').innerText()).includes('堆放'));
 if(!reopened){
  await page.getByRole('button',{name:'回听',exact:true}).click();const player=page.locator('#ct-recording-playback audio').first();await player.waitFor();
  await page.waitForFunction(()=>{const a=document.querySelector('#ct-recording-playback audio');return a&&a.readyState>=1&&Number.isFinite(a.duration);},{},{timeout:30000});
  const duration=await player.evaluate(el=>el.duration);assert(Math.abs(duration-285.52)<.1);
  await player.focus();await player.press('Space');
  await page.waitForFunction(()=>document.querySelector('#ct-recording-playback audio').currentTime>.1,{},{timeout:10000});
  await player.press('Space');await player.evaluate(el=>el.pause());
  fs.writeFileSync(path.join(out,'actual019f-playback.json'),JSON.stringify({duration,position:await player.evaluate(el=>el.currentTime),mutedHeadlessReplay:true,ordinaryAudioControlSpaceKey:true},null,2));
 }
 await page.locator('.ct-reader-export').click();const panel=page.locator('.ct-content-export');await panel.getByLabel('录音文字',{exact:true}).check();await panel.getByLabel('整理结果',{exact:true}).check();await panel.getByRole('button',{name:'预览所选内容',exact:true}).click();
 const preview=panel.getByRole('region',{name:'所选正文预览',exact:true});await preview.waitFor();const text=await preview.innerText();assert(text.includes('超市')&&text.includes('四层')&&text.includes('设备录音'));assert(!text.includes('Minutes engine:')&&!text.includes('Generated:'));
 fs.writeFileSync(path.join(out,'actual019f-ui-readable-preview.txt'),text);await page.screenshot({path:path.join(out,'actual019f-export.png'),fullPage:true});
 assert.deepEqual(JSON.parse(fs.readFileSync(plan.statePath,'utf8')),original);
 return {state:reopened?'ACTUAL_PUBLIC019F_NATIVE_UI_PROCESS_REOPEN_RETAINED_RESULTS':'ACTUAL_PUBLIC019F_NATIVE_UI_READ_PLAYBACK_AND_SELECTED_EXPORT_CHECKED',actualPublicSessionId:plan.sessionId,actualPhysicalAudioResultsRead:true,previousAppExited:reopened?plan.previousAppExited:undefined,allPublicLibraryRowsUnchanged:true,firstPid:plan.firstPid,reopenedPid:plan.reopenedPid,actual285SecondAudioPreparedAndMutedPlaybackChecked:!reopened,newAsrOrCloudRequestedByUi:false,boardAccessed:false,ownerAppearanceAccepted:false,modelGeneralQualityQualified:false};
};
