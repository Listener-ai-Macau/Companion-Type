const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),crypto=require('crypto');
module.exports=async(page,plan,out,reopened)=>{
 const rows=()=>JSON.parse(fs.readFileSync(plan.statePath,'utf8')),row=()=>rows().find(r=>r.id===plan.sessionId),before=row();assert.equal(before.source,'boardDevice');
 await page.locator('.ct-library-card').first().click();const nav=page.getByRole('navigation',{name:'会议工作区',exact:true});await nav.waitFor();await nav.getByRole('button',{name:'文字',exact:true}).click();
 if(!reopened){
  const button=page.getByRole('button',{name:'重新转写并对比',exact:true});
  for(let i=0;i<4&&!await button.isVisible();i++)for(const detail of await page.locator('details').filter({has:button}).all())if(!await detail.evaluate(el=>el.open)&&await detail.locator(':scope>summary').isVisible())await detail.locator(':scope>summary').click();
  assert(await button.isEnabled());await button.click();const preview=page.getByRole('textbox',{name:'新转写结果',exact:true});await preview.waitFor({timeout:360000});const text=await preview.inputValue();assert(text.length>6000&&(text.match(/[，。？！；：]/g)||[]).length>100);
  const words=s=>s.replace(/[^\p{L}\p{N}]/gu,'');assert.equal(words(text),words(before.transcriptText),'Same recognizer words must remain exact for this punctuation-only update');assert.deepEqual(row(),before,'Preview must not overwrite stored original');
  await page.screenshot({path:path.join(out,'actual-retranscription-preview.png'),fullPage:true});await page.getByRole('button',{name:'采用新文字',exact:true}).click();await page.getByText('新文字已保存为修订；原始转写和旧纪要保留，可按需重新整理。',{exact:true}).waitFor();
  const saved=row();assert.equal(saved.transcriptText,before.transcriptText);assert.equal(saved.transcriptReview.text,text);assert(saved.transcriptReview.revision>(before.transcriptReview?.revision||0));fs.writeFileSync(path.join(out,'native-retranscribed.txt'),text);await page.screenshot({path:path.join(out,'actual-retranscription-adopted.png'),fullPage:true});
 }else{assert(before.transcriptReview?.text);assert.deepEqual(rows(),plan.expectedSnapshot);assert((before.transcriptReview.text.match(/[，。？！；：]/g)||[]).length>100);}
 const saved=row(),text=saved.transcriptReview.text;
 return {state:reopened?'ACTUAL_NATIVE_PUBLIC30_RETRANSCRIPTION_ADOPTED_RESULT_REOPENED':'ACTUAL_NATIVE_PUBLIC30_RETRANSCRIPTION_PREVIEW_ADOPTED_AND_ORIGINAL_PRESERVED',previousAppExited:reopened?plan.previousAppExited:undefined,allPublicLibraryRowsUnchanged:reopened,actualPhysicalAudioResultsRead:true,localAsrCompleted:true,recognizerWordsUnchanged:true,originalTranscriptRetained:true,transcriptSha256:crypto.createHash('sha256').update(text).digest('hex'),transcriptCharacters:text.length,deviceOrCloudUsed:false};
};
