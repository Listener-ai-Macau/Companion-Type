// Engineering-only check after a proven native process exit and relaunch.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
module.exports=async function reopenJourney(page,plan,out){
 assert(plan.previousAppExited&&plan.firstPid!==plan.reopenedPid);
 await page.getByRole('button',{name:'录音',exact:true}).click();
 await page.locator('.ct-library-card').filter({hasText:plan.title}).click();
 const nav=page.getByRole('navigation',{name:'会议工作区',exact:true});await nav.waitFor();
 await page.locator('#ct-recording-result[open]').waitFor();
 await nav.getByRole('button',{name:/笔记/}).click();
 const expected=plan.expectedSnapshot.find(row=>row.id===plan.sessionId);
 const note=expected.meetingNotes.find(row=>row.text.includes('本次人工跟进'));
 assert(note&&note.references.length>0);
 const card=page.locator('#ct-recording-notes .ct-notes-list > li').filter({has:page.getByRole('button',{name:'编辑备注 '+note.id,exact:true})});
 assert(await card.getByRole('checkbox',{name:'核对采购清单',exact:true}).isChecked());
 await card.getByRole('button',{name:'查看当前依据',exact:true}).click();
 await page.getByRole('region',{name:'待核对的补充依据',exact:true}).waitFor();
 const visibleQuote=await page.getByRole('region',{name:'待核对的补充依据',exact:true}).innerText();
 // HTML renders source newlines as spaces. Check visible words with whitespace
 // normalization; exact stored quote and all rows are checked separately below.
 const visible=text=>text.replace(/\s+/g,' ').trim();
 assert(visible(visibleQuote).includes(visible(note.references[0].quote)));
 await page.getByRole('button',{name:/返回.*备注|返回.*补充/}).first().click();
 await card.getByRole('button',{name:'导出这张清单',exact:true}).click();
 const panel=page.locator('.ct-content-export');await panel.getByRole('button',{name:'预览所选内容',exact:true}).click();
 const preview=panel.getByRole('region',{name:'所选正文预览',exact:true});await preview.waitFor();
 const text=await preview.innerText();assert(text.includes('本次人工跟进')&&text.includes('尚未批准')&&!text.includes('EXCLUDED_CORE_NOTE_20261109'));
 assert.deepEqual(JSON.parse(fs.readFileSync(plan.statePath,'utf8')),plan.expectedSnapshot);
 await page.screenshot({path:path.join(out,'self-acceptance-after-process-restart.png'),fullPage:true});
 return {state:'ACTUAL_NATIVE_PROCESS_RESTART_RESTORED_SAVED_SOURCE_FOLLOWUP_AND_EXPORT',firstPid:plan.firstPid,reopenedPid:plan.reopenedPid,previousAppExited:true,visibleSavedChecklistRestored:true,literalReferenceVisible:true,selectedExportScopeRetained:true,allPublicLibraryRowsUnchanged:true,modelsRun:false,physicalQualified:false};
};
