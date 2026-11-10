const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
module.exports=async function actionsJourney(page,plan,out){
 assert.ok(plan.requireGroupedUi);
 await page.bringToFront();
 async function open(){
  await page.locator('.ct-library-card').filter({hasText:plan.title}).click();
  const workspace=page.locator('#ct-saved-recording-workspace');await workspace.waitFor({state:'visible'});
  await workspace.getByRole('button',{name:'会议纪要',exact:true}).click();return workspace;
 }
 let workspace=await open();let tools=workspace.getByLabel('事项筛选与跟进',{exact:true});
 await tools.waitFor();await tools.locator('.action-review-filters > summary').click();
 const rows=()=>workspace.locator('.ct-minutes-action-item');const count=await rows().count();assert.equal(count,plan.savedActionCount);assert.ok(count>5);
 await tools.getByLabel('筛选待补信息',{exact:true}).selectOption('owner');assert.equal(await rows().count(),count,'No owner may be invented from a role mentioned in speech');
 await tools.getByLabel('筛选待补信息',{exact:true}).selectOption('review');assert.equal(await rows().count(),count);
 await tools.getByLabel('查找事项',{exact:true}).fill('ZERO_RESULT_ACTION_REVIEW_20261110');assert.equal(await rows().count(),0);await tools.getByText('没有符合当前条件的事项，可清除筛选查看全部。',{exact:true}).waitFor();
 await tools.getByRole('button',{name:'清除筛选',exact:true}).click();assert.equal(await rows().count(),count);
 await tools.getByLabel('查找事项',{exact:true}).fill('广告宣传海报');await tools.getByLabel('筛选完成状态',{exact:true}).selectOption('open');assert.equal(await rows().count(),1);
 const selectedText=await rows().innerText();assert.match(selectedText,/广告宣传海报/);
 await tools.getByRole('button',{name:'整理当前事项为跟进草稿',exact:true}).click();
 const draft=tools.getByLabel('当前筛选事项的跟进文字',{exact:true});const body=await draft.inputValue();assert.match(body,/待核对事项/);assert.match(body,/广告宣传海报/);assert.doesNotMatch(body,/厂家申请试用装|小推车|各部门分析新项目/);
 await tools.getByRole('button',{name:'复制跟进文字',exact:true}).click();await tools.getByText('当前筛选事项的跟进文字已复制，尚未发送。',{exact:true}).waitFor();
 const request=path.join(out,'text-clipboard-request.json');fs.writeFileSync(request+'.tmp',JSON.stringify({expected:body}));fs.renameSync(request+'.tmp',request);
 const reply=path.join(out,'text-clipboard-reply.json'),deadline=Date.now()+15000;while(!fs.existsSync(reply)&&Date.now()<deadline)await new Promise(r=>setTimeout(r,100));assert.ok(fs.existsSync(reply),'Native clipboard readback required');
 const clipboard=JSON.parse(fs.readFileSync(reply,'utf8'));assert.equal(clipboard.actualWindowsUnicodeClipboardMatched,true);
 await page.screenshot({path:path.join(out,'actions-filtered-followup.png'),fullPage:true});
 await rows().getByRole('checkbox').check();await page.waitForFunction(()=>document.querySelectorAll('.ct-minutes-action-item').length===0);
 await tools.getByLabel('筛选完成状态',{exact:true}).selectOption('done');assert.equal(await rows().count(),1);assert.equal(await rows().getByRole('checkbox').isChecked(),true);assert.match(await draft.inputValue(),/已标记完成/);assert.match(await draft.inputValue(),/仍保留待核对标记/);
 // Reload proves native persistence, rather than a React-only optimistic toggle.
 await page.reload();await page.locator('.ct-shell').waitFor();workspace=await open();tools=workspace.getByLabel('事项筛选与跟进',{exact:true});assert.equal(await rows().count(),count,'Record reload must reset the ephemeral filter');
 assert.equal(await rows().getByRole('checkbox').count(),count);
 const completed=rows().filter({hasText:'广告宣传海报'});assert.equal(await completed.getByRole('checkbox').isChecked(),true);
 assert.equal(await rows().getByRole('checkbox').evaluateAll(nodes=>nodes.filter(node=>node.checked).length),1,'Only the selected original action may change');
 await completed.getByRole('checkbox').uncheck();
 await page.reload();await page.locator('.ct-shell').waitFor();workspace=await open();tools=workspace.getByLabel('事项筛选与跟进',{exact:true});assert.equal(await rows().count(),count);assert.equal(await rows().getByRole('checkbox').evaluateAll(nodes=>nodes.filter(node=>node.checked).length),0);
 await tools.locator('.action-review-filters > summary').click();await tools.getByLabel('查找事项',{exact:true}).fill('广告宣传海报');assert.equal(await rows().count(),1);
 const source=rows().getByRole('button').first();assert.ok(await source.isVisible());assert.match(await source.innerText(),/原文|原话/);await source.click();
 await workspace.locator('#ct-recording-text-review').waitFor({state:'visible'});
 await page.screenshot({path:path.join(out,'actions-original-source.png'),fullPage:true});
 return {state:'REAL_TAURI_SAVED_ACTION_FILTER_FOLLOWUP_NATIVE_COPY_AND_DURABLE_COMPLETION_PASSED',publicMeeting:'S_R004S03C01',savedActionCount:count,missingOwnerNotInferred:true,pendingContentPreserved:true,zeroResultAndClearPassed:true,scopeOnlySelectedAction:true,completionSurvivedReload:true,completionRestoredAfterReload:true,sourceButtonUsedFromFilteredOriginal:true,nativeClipboard:clipboard,newAsrOrCloudCalls:0,externalSend:false,ownerDataUsed:false,modelQualityQualified:false};
};
