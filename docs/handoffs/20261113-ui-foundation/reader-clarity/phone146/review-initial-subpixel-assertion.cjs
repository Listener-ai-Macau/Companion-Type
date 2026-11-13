const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const C='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import',O=path.join(C,'android146');
const {connect}=require(C+'/organization_ui.cjs'),{read}=require(C+'/organization_readback.cjs');
const base=JSON.parse(fs.readFileSync(C+'/android128/public-document-before.json','utf8'));
const libraries=JSON.parse(fs.readFileSync(O+'/public-libraries.json','utf8'));
const renamed='公开演示安排 · 随身笔记回找';
const appended='工程公开补充：这里只检查文字保存，不代表录音识别。';
(async()=>{const{page,browser,session}=await connect();try{
 assert.equal((await read(page,'appPreferences')).version,'0.1.146');assert(libraries.ids.includes((await read(page,'libraryStatus')).activeId));
 const nav=()=>page.getByRole('navigation',{name:'主导航',exact:true});
 async function library(){await nav().getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('heading',{name:'我的录音',exact:true}).waitFor();}
 async function theme(value){await nav().getByRole('button',{name:'设置',exact:true}).click();await page.getByRole('radio',{name:value==='light'?'浅色':'深色',exact:true}).check();await library();}
 const phase=process.argv[2]||'before-restart';
 if(phase==='before-restart'){
  await library();const before=await read(page,'library'),target=before.rows.find(row=>row.key===base.key);assert(target);fs.writeFileSync(O+'/library-before-review.json',JSON.stringify(before,null,2));
  assert.equal(await page.locator('#library-import-panel').isVisible(),false);assert.equal(await page.locator('.library-filter-details').evaluate(el=>el.open),false);
  await theme('light');await page.screenshot({path:O+'/library-light.png',fullPage:true});
  await page.locator('.library-managed-list .row').filter({hasText:target.title}).click();await page.getByRole('tablist',{name:'录音内容',exact:true}).waitFor();assert.equal(await page.getByRole('tablist',{name:'录音内容',exact:true}).getByRole('tab').count(),3);
  const geometry=await page.getByRole('tablist',{name:'录音内容',exact:true}).getByRole('tab').evaluateAll(nodes=>nodes.map(n=>{const range=document.createRange();range.selectNodeContents(n);const b=n.getBoundingClientRect(),r=range.getBoundingClientRect();return {text:n.textContent,boxWidth:b.width,textWidth:r.width,textInside:r.left>=b.left&&r.right<=b.right};}));assert.deepEqual(geometry.map(x=>x.text),['纪要','文字','笔记']);assert(geometry.every(x=>x.textInside&&x.boxWidth>=44));fs.writeFileSync(O+'/actual-tab-geometry.json',JSON.stringify(geometry,null,2));
  assert(await page.locator('.recording-content-navigation').evaluate(node=>!!(node.compareDocumentPosition(document.querySelector('.meeting-recording-tools'))&Node.DOCUMENT_POSITION_FOLLOWING)),'Reading before management');
  const initial=await read(page,'detail',{key:target.key});const wanted=initial.minutes?.markdown?.trim()&&!initial.minutesChanged?'纪要':'文字';assert.equal(await page.getByRole('tab',{name:wanted,exact:true}).getAttribute('aria-selected'),'true');
  await page.getByRole('button',{name:'重命名',exact:true}).click();await page.getByRole('textbox',{name:'录音名称',exact:true}).fill(renamed);await page.getByRole('button',{name:'保存名称',exact:true}).click();await page.getByRole('heading',{name:renamed,exact:true}).waitFor();
  await page.getByRole('tab',{name:'文字',exact:true}).click();await page.getByRole('button',{name:'编辑',exact:true}).click();const editor=page.getByRole('dialog',{name:'编辑转写',exact:true});await editor.getByRole('textbox',{name:'转写文字',exact:true}).fill(initial.transcript+'\n'+appended);await editor.getByRole('button',{name:'保存',exact:true}).click();await editor.waitFor({state:'hidden'});
  const updated=await read(page,'detail',{key:target.key});assert.equal(updated.transcript,initial.transcript+'\n'+appended);assert(updated.revision>initial.revision);
  await page.getByRole('button',{name:'前往导出',exact:true}).click();await page.getByLabel('导出文件格式').waitFor();assert(await page.locator('.export-card').evaluate(el=>el.open));
  await page.getByRole('tab',{name:'文字',exact:true}).click();await page.locator('main').evaluate(el=>el.scrollTop=0);await page.screenshot({path:O+'/detail-light.png',fullPage:true});
  await theme('dark');await page.getByRole('searchbox').fill('随身笔记回找');await page.locator('.library-managed-list .row').filter({hasText:renamed}).click();await page.locator('main').evaluate(el=>el.scrollTop=0);await page.screenshot({path:O+'/detail-dark.png',fullPage:true});
  const latest=await read(page,'library');assert.equal(latest.rows.find(row=>row.key===target.key).title,renamed);assert.deepEqual(latest.rows.filter(row=>row.key!==target.key),before.rows.filter(row=>row.key!==target.key));
  fs.writeFileSync(O+'/notebook-review-checkpoint.json',JSON.stringify({key:target.key,title:renamed,transcript:updated.transcript,revision:updated.revision,ownedDisplay:session.displayId,defaultTab:wanted,actualFixedExportEntryOpened:true,modelsRun:false,boardAccessed:false},null,2));
 }else{
  assert.equal(phase,'after-restart');const checkpoint=JSON.parse(fs.readFileSync(O+'/notebook-review-checkpoint.json','utf8'));await library();await page.getByRole('searchbox').fill('随身笔记回找');await page.locator('.library-managed-list .row').filter({hasText:renamed}).click();await page.getByRole('heading',{name:renamed,exact:true}).waitFor();
  const detail=await read(page,'detail',{key:checkpoint.key});assert.equal(detail.transcript,checkpoint.transcript);assert.equal(detail.revision,checkpoint.revision);assert.equal(await page.getByRole('tab',{name:detail.minutesChanged?'文字':'纪要',exact:true}).getAttribute('aria-selected'),'true');
  fs.writeFileSync(O+'/library-review-result.json',JSON.stringify({...checkpoint,state:'ACTUAL_INSTALLED146_READER_CLARITY_CONTINUOUS_LIBRARY_RENAME_TRANSCRIPT_SAVE_EXPORT_ENTRY_THEMES_AND_PROCESS_REOPEN_PASSED',actualPhoneReviewed:true,actualProcessRestartPassed:true,unrelatedPublicRowsUnchanged:true,ownerMainDisplayOperated:false,ownerAppearanceAccepted:false,hardwareQualified:false,saleQualified:false},null,2));
 }
 console.log('Actual phone146 '+phase+' notebook UI checked on public library only');
}catch(error){fs.writeFileSync(O+'/review-failure.json',JSON.stringify({at:new Date().toISOString(),phase:process.argv[2],error:String(error)},null,2));await page.screenshot({path:O+'/review-failure.png',fullPage:true});throw error;}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
