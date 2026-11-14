const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),crypto=require('crypto');
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',P=path.join(C,'android158');
const{connect}=require(C+'/organization_ui.cjs'),{read}=require(C+'/organization_readback.cjs');
const key=JSON.parse(fs.readFileSync(C+'/android128/public-document-before.json','utf8')).key,folder='界面自验/会议',tag='界面自验';
const digest=s=>crypto.createHash('sha256').update(s).digest('hex');
(async()=>{const{page,browser,session}=await connect();const phase=process.argv[2];let record={phase,modelsRun:false,cloudCalls:0,boardAccessed:false,ownerMainDisplayUsed:false,ownedDisplay:session.displayId};
try{
 assert.equal((await read(page,'appPreferences')).version,'0.1.158');
 const own=JSON.parse(fs.readFileSync(P+'/public-libraries.json','utf8'));assert(own.ids.includes((await read(page,'libraryStatus')).activeId));
 const nav=page.getByRole('navigation',{name:'主导航',exact:true});await nav.getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('heading',{name:'我的录音',exact:true}).waitFor();
 const before=await read(page,'library'),target=before.rows.find(r=>r.key===key);assert(target);const detail=await read(page,'detail',{key});assert(detail.minutes?.markdown);
 record={...record,key,title:target.title,transcriptSha256:digest(detail.transcript),minutesSha256:digest(detail.minutes.markdown),initialRows:before.rows.length};
 if(phase==='before-restart'){
  const row=page.locator('.library-managed-row').filter({hasText:target.title});assert.equal(await row.count(),1);
  await page.getByRole('button',{name:'选择',exact:true}).click();await row.locator('.library-row-check input').check();
  const panel=page.locator('.library-management-panel');assert.equal(await panel.evaluate(e=>e.open),false);assert.equal(await page.getByLabel('目标文件夹',{exact:true}).isVisible(),false);
  await page.locator('main').evaluate(e=>e.scrollTop=0);
  record.compactSelection=await page.evaluate(()=>{const p=document.querySelector('.library-management-panel'),r=document.querySelector('.library-managed-row'),m=document.querySelector('main');return{panelHeight:p.getBoundingClientRect().height,firstRowBottom:r.getBoundingClientRect().bottom,mainBottom:m.getBoundingClientRect().bottom};});
  assert(record.compactSelection.panelHeight<=70);assert(record.compactSelection.firstRowBottom<=record.compactSelection.mainBottom);
  await page.screenshot({path:P+'/library-one-selected.png'});
  await panel.locator(':scope>summary').click();await page.getByLabel('目标文件夹',{exact:true}).fill(folder);await page.getByRole('button',{name:'应用文件夹',exact:true}).click();await page.locator('.library-management-result').filter({hasText:'归入'}).waitFor();
  await page.getByLabel('批量标签',{exact:true}).fill(tag);await page.getByRole('button',{name:'添加标签',exact:true}).click();await page.locator('.library-management-result').filter({hasText:'添加'}).waitFor();
  const saved=await read(page,'library'),updated=saved.rows.find(r=>r.key===key);assert.equal(updated.organization.folder,folder);assert(updated.organization.tags.includes(tag));
  for(const row of before.rows.filter(r=>r.key!==key))assert.deepEqual(saved.rows.find(r=>r.key===row.key).organization,row.organization);
  await page.getByRole('button',{name:'完成',exact:true}).click();const filters=page.locator('.library-filter-details');await filters.locator(':scope>summary').click();await page.getByLabel('按文件夹筛选',{exact:true}).selectOption(folder);await page.getByLabel('按标签筛选',{exact:true}).selectOption(tag);await filters.locator(':scope>summary').click();
  const chips=page.getByRole('group',{name:'当前筛选',exact:true});assert((await chips.innerText()).includes(folder));assert.equal(await page.locator('.library-managed-row').count(),1);await page.locator('main').evaluate(e=>e.scrollTop=0);await page.screenshot({path:P+'/library-visible-scope.png'});
  await chips.getByRole('button',{name:'取消文件夹筛选',exact:true}).click();assert.equal(await page.locator('.library-managed-row').count(),1);await chips.getByRole('button',{name:'清除筛选',exact:true}).click();assert.equal(await page.locator('.library-managed-row').count(),before.rows.length);
  await page.locator('.library-managed-list .row').filter({hasText:target.title}).click();await page.getByRole('tab',{name:'纪要',exact:true}).click();await page.getByRole('button',{name:'前往导出',exact:true}).click();await page.getByRole('button',{name:'预览所选正文',exact:true}).click();const preview=page.getByRole('region',{name:'所选正文预览',exact:true});await preview.waitFor();assert((await preview.innerText()).includes('超市'));await page.screenshot({path:P+'/library-to-real-export-preview.png'});await page.locator('.export-card>summary').click();
  record.actualOnlySelectedPublicRecordingOrganized=true;record.otherPublicRowsUnchanged=true;record.actualPreparedExportPreview=true;record.filterResetRetainsAllRows=true;
 }else{
  assert.equal(phase,'after-restart');const checkpoint=JSON.parse(fs.readFileSync(P+'/library-before-restart.json','utf8'));assert.equal(target.organization.folder,folder);assert(target.organization.tags.includes(tag));assert.equal(record.transcriptSha256,checkpoint.transcriptSha256);assert.equal(record.minutesSha256,checkpoint.minutesSha256);assert.equal(await page.locator('.library-selection-bar').count(),0);record.organizationPersistedAfterTrueProcessRestart=true;
 }
 const after=await read(page,'detail',{key});assert.equal(digest(after.transcript),record.transcriptSha256);assert.equal(digest(after.minutes.markdown),record.minutesSha256);record.trueProcessReopenChecked=phase==='after-restart';record.state=phase==='after-restart'?'ACTUAL158_PUBLIC_LIBRARY_ORGANIZATION_TRUE_REOPEN_PASSED':'ACTUAL158_PUBLIC_LIBRARY_SCOPE_SELECTION_ORGANIZE_EXPORT_PASSED_REOPEN_PENDING';record.sourceTextAndMinutesUnchanged=true;
}catch(e){record.error=String(e);await page.screenshot({path:P+'/library-failure-'+phase+'.png'}).catch(()=>{});throw e;}
finally{fs.writeFileSync(P+'/library-'+phase+'.json',JSON.stringify(record,null,2));await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
