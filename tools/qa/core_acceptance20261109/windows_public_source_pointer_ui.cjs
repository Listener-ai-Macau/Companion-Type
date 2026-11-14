const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
module.exports=async(page,plan,out,reopened)=>{
 await page.locator('.ct-library-card').first().click();
 const nav=page.getByRole('navigation',{name:'会议工作区',exact:true});
 if(!reopened){
  await nav.getByRole('button',{name:'文字',exact:true}).click();
  await page.getByRole('button',{name:'引用转写到备注',exact:true}).click();
  const expected=plan.expectedSnapshot[0].transcriptText;
  await page.getByRole('searchbox',{name:'查找可引用的原文',exact:true}).fill(expected.slice(0,12));
  const quote=await page.locator('.manual-quote-options blockquote').first().textContent();assert(expected.includes(quote));
  await page.evaluate(()=>{
   window.__quotePointerEvents=[];
   document.addEventListener('click',event=>{const e=event.target instanceof Element?event.target:null;window.__quotePointerEvents.push({tag:e?.tagName,aria:e?.closest('button')?.getAttribute('aria-label'),text:e?.textContent?.slice(0,60),trusted:event.isTrusted,scrollY});},{capture:true});
  });
  const button=page.getByRole('button',{name:'引用原文片段 1',exact:true});
  await button.scrollIntoViewIfNeeded();
  // Observe settled scroll geometry, rather than race a previous smooth reveal.
  await page.waitForFunction(()=>{
   const e=document.querySelector('[aria-label="引用原文片段 1"]');if(!e)return false;
   const r=e.getBoundingClientRect(),key=[r.x,r.y,r.width,r.height,scrollY].join(',');
   if(window.__quoteGeometry?.key!==key){window.__quoteGeometry={key,at:performance.now()};return false;}
   return performance.now()-window.__quoteGeometry.at>250&&r.top>=0&&r.bottom<=innerHeight;
  },{},{polling:50});
  await button.click();
  const notes=page.locator('#ct-meeting-materials-pane');
  try{await notes.waitFor({state:'visible',timeout:10000});}
  finally{fs.writeFileSync(path.join(out,'source-pointer-input.json'),JSON.stringify({events:await page.evaluate(()=>window.__quotePointerEvents),buttonDisabled:await button.isDisabled(),materialsVisible:await notes.isVisible(),ordinaryInput:'Playwright pointer click after observed geometry settled',quoteExactInOriginal:expected.includes(quote)},null,2));}
  const composer=page.locator('#ct-recording-notes .ct-note-composer');await composer.waitFor();
  assert((await composer.innerText()).includes(quote));
  await composer.getByRole('button',{name:'移除此引用',exact:true}).click();
  assert.equal(await composer.getByRole('button',{name:'移除此引用',exact:true}).count(),0);
  await page.screenshot({path:path.join(out,'source-pointer-note-draft-discarded.png')});
 }
 assert.deepEqual(JSON.parse(fs.readFileSync(plan.statePath,'utf8')),plan.expectedSnapshot);
 return {state:reopened?'ACTUAL_SOURCE_POINTER_PROBE_REOPEN_WORDS_RETAINED':'ACTUAL_SOURCE_POINTER_CAPTURE_AND_DRAFT_DISCARD_PASSED',allPublicLibraryRowsUnchanged:true,actualPublicSessionId:plan.sessionId,previousAppExited:reopened?plan.previousAppExited:undefined,newAsrOrCloudRequestedByUi:false,boardAccessed:false,ownerAppearanceAccepted:false};
};
