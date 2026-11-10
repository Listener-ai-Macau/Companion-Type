const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),cp=require('node:child_process');
const {chromium}=require('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055/node_modules/@playwright/test');
const root='E:/CodexData/Companion/.build-cache/actions-followup20261110/phone116',out=path.join(__dirname,'android116');
const adb='C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';
(async()=>{
 const session=JSON.parse(fs.readFileSync(path.join(root,'cdp.json'),'utf8'));assert.equal(session.displayId,7);
 const browser=await chromium.connectOverCDP('http://127.0.0.1:'+session.cdpPort);let page,publicOpened=false;
 const record={at:new Date().toISOString(),versionCode:116,ownVirtualDisplay:session.displayId,physicalMainDisplayOperated:false,newAsrOrCloudCalls:0,externalSend:false,ownerRecordOpened:false};
 try{
  const targets=await (await fetch('http://127.0.0.1:'+session.cdpPort+'/json/list')).json(),attached=targets.filter(t=>JSON.parse(t.description).attached);assert.equal(attached.length,1);
  for(const candidate of browser.contexts()[0].pages()){
   const channel=await browser.contexts()[0].newCDPSession(candidate),info=await channel.send('Target.getTargetInfo');await channel.detach();if(info.targetInfo.targetId===attached[0].id)page=candidate;
  }assert(page);page.setDefaultTimeout(10000);page.on('dialog',dialog=>{
   assert.equal(dialog.type(),'confirm');assert.equal(dialog.message(),'打开这份保留的资料？当前资料也会保留，不会删除录音或连接录音卡。');
   const action=cp.spawnSync('C:/Users/Billy/AppData/Local/Programs/Python/Python311/python.exe',[path.join(__dirname,'phone_native116.py'),'click','id:android:id/button1'],{encoding:'utf8',windowsHide:true,timeout:20000});
   assert.equal(action.status,0,action.stderr);record.ownedLibraryConfirmations=(record.ownedLibraryConfirmations||0)+1;
  });
  await page.getByRole('button',{name:'设置',exact:true}).first().click();const retained=page.locator('.library-backups-retained');await retained.locator(':scope > summary').click();
  const libraries=retained.locator(':scope > div');assert.equal(await libraries.count(),2,'Only original and the previously verified public QA library are allowed');
  if(await libraries.first().getByText('正在使用',{exact:true}).count())await libraries.last().getByRole('button',{name:'打开这份资料',exact:true}).click();
  else await libraries.last().getByText('正在使用',{exact:true}).waitFor();
  await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'录音',exact:true}).click();await page.getByRole('button',{name:'返回原有资料',exact:true}).waitFor();publicOpened=true;
  const list=page.locator('.list .row');assert.equal(await list.count(),1);assert.match(await list.innerText(),/S_R004S03C01/);await list.click();
  assert.match(await page.locator('.detail-title h1').innerText(),/S_R004S03C01/);await page.getByRole('tab',{name:/纪要/}).click();
  const tools=page.getByLabel('事项筛选与跟进',{exact:true}),rows=()=>page.locator('.mobile-action-card');await tools.waitFor();const total=await rows().count();assert.equal(total,21);
  await tools.locator('.action-review-filters > summary').click();await tools.getByLabel('筛选待补信息',{exact:true}).selectOption('review');assert.equal(await rows().count(),20);
  await tools.getByRole('button',{name:'整理当前事项为跟进草稿',exact:true}).click();const draft=tools.getByLabel('当前筛选事项的跟进文字',{exact:true});assert.match(await draft.inputValue(),/待核对事项/);
  await tools.getByLabel('查找事项',{exact:true}).fill('ZERO_RESULT_ACTION_REVIEW_20261110');assert.equal(await rows().count(),0);
  await tools.getByRole('button',{name:'清除筛选',exact:true}).click();assert.equal(await rows().count(),21);
  await tools.getByLabel('查找事项',{exact:true}).fill('标签');assert.equal(await rows().count(),1);const original=await rows().innerText();assert.match(original,/标签/);
  const body=await draft.inputValue();assert.match(body,/标签/);assert.doesNotMatch(body,/小推车|厂家申请|试用装/);
  await tools.getByRole('button',{name:'复制跟进文字',exact:true}).click();await tools.getByText('当前筛选事项的跟进文字已复制，尚未发送。',{exact:true}).waitFor();
  fs.writeFileSync(path.join(root,'filtered-followup.txt'),body);record.copyNativeCallbackConfirmed=true;
  await page.screenshot({path:path.join(out,'public-filtered-followup.png'),fullPage:false});
  await rows().getByRole('checkbox').check();await page.waitForFunction(()=>document.querySelector('.mobile-action-card input[type=checkbox]')?.checked===true);
  assert.match(await draft.inputValue(),/已标记完成/);assert.match(await draft.inputValue(),/仍保留待核对标记/);
  await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'录音',exact:true}).click();await page.locator('.list .row').click();await page.getByRole('tab',{name:/纪要/}).click();
  assert.equal(await rows().count(),21);const completed=rows().filter({hasText:'标签'});assert.equal(await completed.getByRole('checkbox').isChecked(),true);assert.equal(await rows().getByRole('checkbox').evaluateAll(ns=>ns.filter(n=>n.checked).length),1);
  await completed.getByRole('checkbox').uncheck();await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'录音',exact:true}).click();await page.locator('.list .row').click();await page.getByRole('tab',{name:/纪要/}).click();
  assert.equal(await rows().getByRole('checkbox').evaluateAll(ns=>ns.filter(n=>n.checked).length),0);record.durableCompletionAndOriginalIndexPassed=true;
  await rows().filter({hasText:'标签'}).getByRole('button',{name:'查找原文核对',exact:true}).click();await page.getByRole('tabpanel',{name:/原文|转写/}).waitFor();record.filteredOriginalSourceOpened=true;
  // A normal, unsent question field is the clipboard receiver. No generated DOM,
  // native-call substitution, inference or external recipient is involved.
  await page.getByRole('tab',{name:/纪要/}).click();
  const ask=page.getByRole('button',{name:'问这场会议',exact:true});if(await ask.count())await ask.click();
  const receiver=page.getByLabel('会议AI问题',{exact:true});await receiver.waitFor();await receiver.fill('');await receiver.click();
  const paste=cp.spawnSync(adb,['-s','d6bd213d','shell','input','-d',String(session.displayId),'keyevent','279'],{encoding:'utf8',windowsHide:true});assert.equal(paste.status,0);
  await page.waitForFunction(expected=>document.querySelector('textarea[aria-label="会议AI问题"]')?.value===expected,body,{timeout:8000});record.actualAndroidClipboardPastedIntoUnsentQuestion=true;await receiver.fill('');
  record.state='ANDROID116_REAL_PHONE_ACTION_FILTER_FOLLOWUP_NATIVE_COPY_AND_REOPEN_PASSED';record.savedActions=21;record.pendingFilterActions=20;
 }catch(error){record.state='ANDROID116_ACTION_UI_NOT_QUALIFIED_FAILURE_RETAINED';record.error=String(error);if(publicOpened){try{await page.screenshot({path:path.join(out,'public-ui-failure.png'),fullPage:false});fs.writeFileSync(path.join(root,'public-ui-failure-body.txt'),await page.locator('body').innerText());}catch{}}process.exitCode=1;}
 finally{
  if(page){try{
   await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'录音',exact:true}).click();
   await page.getByRole('region',{name:'当前资料位置',exact:true}).waitFor();
   const restore=page.getByRole('button',{name:'返回原有资料',exact:true});if(await restore.count())await restore.click();
   await page.getByRole('region',{name:'当前资料位置',exact:true}).getByText('原有资料',{exact:true}).waitFor();record.originalLibraryRestored=true;
  }catch(error){record.originalLibraryRestored=false;record.restoreError=String(error);process.exitCode=1;}}
  fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify(record,null,2)+'\n');await browser.close();
 }
 console.log(JSON.stringify(record));
})().catch(error=>{console.error(String(error));process.exitCode=1;});
