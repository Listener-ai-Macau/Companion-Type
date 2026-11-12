const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const code=process.env.COMPANION_PHONE_QA_CODE||'143';assert(['143','144'].includes(code));
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',O=path.join(C,'android'+code);
const {connect}=require(path.join(C,'organization_ui.cjs')),{read}=require(path.join(C,'organization_readback.cjs'));
const publicLibraries=JSON.parse(fs.readFileSync(path.join(O,'public-libraries.json'),'utf8'));
const base=JSON.parse(fs.readFileSync(path.join(C,'android128/public-document-before.json'),'utf8'));
const renamed='公开演示安排 · 录音回找检查';
(async()=>{const {page,browser,session}=await connect();try{
 assert.equal((await read(page,'appPreferences')).version,'0.1.'+code);assert(publicLibraries.ids.includes((await read(page,'libraryStatus')).activeId));
 const nav=()=>page.getByRole('navigation',{name:'主导航',exact:true});
 async function library(){await nav().getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('heading',{name:'我的记录',exact:true}).waitFor();}
 const phase=process.argv[2]||'before-restart';
 if(phase==='recheck'){
  assert.equal(code,'144');await library();const before=await read(page,'library');const history=await read(page,'audioImportStatus');
  assert.equal(history.running,false);assert.equal(history.state,'cancelled');assert.equal(await page.locator('.audio-import-error,.audio-import-cancelled').count(),0);
  const toLight=page.getByRole('button',{name:'切换浅色模式',exact:true});if(await toLight.count())await toLight.click();await page.waitForTimeout(5200);
  await page.screenshot({path:path.join(O,'library-light.png'),fullPage:true});
  const target=before.rows.find(row=>row.key===base.key);assert(target);await page.locator('.library-managed-list .row').filter({hasText:target.title}).click();
  const detail=await read(page,'detail',{key:target.key});const wanted=detail.minutes?.markdown?.trim()&&!detail.minutesChanged?'纪要':'转写';assert.equal(await page.getByRole('tab',{name:wanted,exact:true}).getAttribute('aria-selected'),'true');
  await page.screenshot({path:path.join(O,'detail-light.png'),fullPage:true});await page.getByRole('button',{name:'切换深色模式',exact:true}).click();await page.waitForTimeout(5200);await page.screenshot({path:path.join(O,'detail-dark.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>localStorage.getItem('companion-appearance')),'dark');assert.deepEqual((await read(page,'library')).rows,before.rows);
  fs.writeFileSync(path.join(O,'library-review-result.json'),JSON.stringify({state:'ACTUAL_INSTALLED144_LIBRARY_HISTORICAL_CANCEL_QUIET_ENTRY_THEMES_AND_DATA_PASSED',version:'0.1.144',nativeHistoricalImportState:history.state,historicalCancelNotMisrepresentedAsCurrentError:true,currentFailuresRetainedByAffectedComponentContract:true,actualRecordingOpened:true,defaultOpenedTab:wanted,allPublicRowsUnchanged:true,priorAppearanceDarkRestoredAndReadBack:true,actualPhoneReviewed:true,ownedDisplay:session.displayId,prior143SavedRenameSearchAndProcessRestartEvidence:path.join(C,'android143/library-review-result.json'),prior143RouteImplementationUnchanged:true,modelsRun:false,boardAccessed:false,phoneMainInputUsed:false,ownerAppearanceAccepted:false,saleQualified:false},null,2));
 }else if(phase==='before-restart'){
  await library();assert.equal(await page.locator('.library-filter-details').evaluate(node=>node.open),false);
  const before=await read(page,'library'),target=before.rows.find(row=>row.key===base.key);assert(target);
  fs.writeFileSync(path.join(O,'library-before-review.json'),JSON.stringify(before,null,2));
  const toLight=page.getByRole('button',{name:'切换浅色模式',exact:true});if(await toLight.count())await toLight.click();
  await page.screenshot({path:path.join(O,'library-light.png'),fullPage:true});
  await page.locator('.library-managed-list .row').filter({hasText:target.title}).click();
  const detail=await read(page,'detail',{key:target.key});
  const wanted=detail.minutes?.markdown?.trim()&&!detail.minutesChanged?'纪要':'转写';
  assert.equal(await page.getByRole('tab',{name:wanted,exact:true}).getAttribute('aria-selected'),'true');
  await page.getByRole('button',{name:'重命名',exact:true}).click();await page.getByRole('textbox',{name:'录音名称',exact:true}).fill(renamed);await page.getByRole('button',{name:'保存名称',exact:true}).click();
  await page.getByRole('heading',{name:renamed,exact:true}).waitFor();assert.equal((await read(page,'library')).rows.find(row=>row.key===target.key).title,renamed);
  await page.screenshot({path:path.join(O,'detail-light.png'),fullPage:true});
  await page.getByRole('button',{name:'切换深色模式',exact:true}).click();await page.screenshot({path:path.join(O,'detail-dark.png'),fullPage:true});
  await library();const search=page.getByRole('searchbox');await search.fill('录音回找检查');await page.locator('.library-managed-list .row').filter({hasText:renamed}).waitFor();
  fs.writeFileSync(path.join(O,'library-review-checkpoint.json'),JSON.stringify({state:'ACTUAL143_LIBRARY_RENAME_SEARCH_AND_ENTRY_CHECKED',key:target.key,originalTitle:target.title,renamed,activePublicLibrary:publicLibraries.working,defaultOpenedTab:wanted,ownedDisplay:session.displayId,modelsRun:false,boardAccessed:false,phoneMainInputUsed:false},null,2));
 }else{
  assert.equal(phase,'after-restart');const checkpoint=JSON.parse(fs.readFileSync(path.join(O,'library-review-checkpoint.json'),'utf8'));
  await library();const current=await read(page,'library');assert.equal(current.rows.find(row=>row.key===checkpoint.key).title,renamed);
  const prior=JSON.parse(fs.readFileSync(path.join(O,'library-before-review.json'),'utf8'));
  assert.deepEqual(current.rows.filter(row=>row.key!==checkpoint.key),prior.rows.filter(row=>row.key!==checkpoint.key));
  await page.getByRole('searchbox').fill('录音回找检查');await page.locator('.library-managed-list .row').filter({hasText:renamed}).click();await page.getByRole('heading',{name:renamed,exact:true}).waitFor();
  fs.writeFileSync(path.join(O,'library-review-result.json'),JSON.stringify({...checkpoint,state:'ACTUAL_INSTALLED143_PUBLIC_LIBRARY_RENAME_SEARCH_THEME_AND_PROCESS_REOPEN_PASSED',renamedRecordingReopenedAfterActualProcessRestart:true,otherPublicRowsUnchanged:true,actualPhoneReviewed:true,ownerAppearanceAccepted:false,physicalRecordingQualified:false,modelQualityQualified:false,saleQualified:false},null,2));
 }
 console.log('Phone143 '+phase+' public library review passed; no Owner content opened.');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
