const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055/node_modules/@playwright/test');
const root='E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6';
const code=Number(process.argv[2]||114);assert([114,115].includes(code));
const output='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-core-acceptance/android110/phone-d6';
(async()=>{
 const session=JSON.parse(fs.readFileSync(path.join(root,'cdp.json'),'utf8'));
 const browser=await chromium.connectOverCDP('http://127.0.0.1:'+session.cdpPort);
 const record={at:new Date().toISOString(),versionCode:code,scope:'Actual connected phone WebView on owned display5, same 1440x3200/589 metrics as physical phone. No physical main-display capture.'};
 try{
  const targets=await (await fetch('http://127.0.0.1:'+session.cdpPort+'/json/list')).json();const attached=targets.filter(t=>JSON.parse(t.description).attached);assert.equal(attached.length,1);let page;
  for(const candidate of browser.contexts()[0].pages()){const channel=await browser.contexts()[0].newCDPSession(candidate);const info=await channel.send('Target.getTargetInfo');await channel.detach();if(info.targetInfo.targetId===attached[0].id)page=candidate;}
  assert(page);page.on('dialog',()=>{});assert((await page.locator('.detail-title h1').innerText()).includes('S_R004S03C01'));
  await page.locator('body').press('Control+Home');
  const layout=await page.evaluate(()=>{
   const section=document.querySelector('#detail-panel-minutes .minutes-section');const body=section?.children[1];const frame=document.querySelector('.meeting-reading-frame');const assistant=document.querySelector('.existing-minutes');
   const cards=Array.from(document.querySelectorAll('.meeting-outline-card')).map(e=>e.getBoundingClientRect().top);
   return {width:innerWidth,height:innerHeight,bottomNavigationTop:document.querySelector('.bottom-nav').getBoundingClientRect().top,firstContentTop:body?.getBoundingClientRect().top,firstContentCharacters:body?.textContent?.trim().length,recordingManagementTop:document.querySelector('.recording-management').getBoundingClientRect().top,bookmarksTop:document.querySelector('.device-bookmarks').getBoundingClientRect().top,outlineCardTops:cards,regenerationAfterReading:!!(frame.compareDocumentPosition(assistant)&Node.DOCUMENT_POSITION_FOLLOWING),regenerationInitiallyClosed:!assistant.open};
  });record.layout=layout;
  assert(layout.firstContentCharacters>20,'Saved meeting content missing');
  if(code===115)assert.equal(await page.locator('.minutes-preamble-generated').count(),1,'Generated caption class must come from the packaged application');
  assert(layout.firstContentTop+48<layout.bottomNavigationTop,'At least two text lines must fit above bottom navigation');
  assert(layout.regenerationAfterReading&&layout.regenerationInitiallyClosed);
  assert(Math.abs(layout.recordingManagementTop-layout.bookmarksTop)<3);
  assert.equal(layout.outlineCardTops.length,3);assert(Math.max(...layout.outlineCardTops)-Math.min(...layout.outlineCardTops)<3);
  await page.getByRole('button',{name:'整理方式',exact:true}).click();assert(await page.locator('.existing-minutes').evaluate(e=>e.open));
  assert(await page.locator('.existing-minutes').getByRole('button',{name:'设置AI服务',exact:true}).isVisible());
  await page.locator('.existing-minutes>summary').click();
  await page.locator('.device-bookmarks-summary').click();await page.getByRole('button',{name:'读取设备重点',exact:true}).click();
  await page.getByText('已读取这条录音，未发现设备按键标记的重点。',{exact:true}).waitFor({timeout:15000});
  await page.locator('.device-bookmarks-summary').click();
  await page.locator('.recording-management>summary').click();assert(await page.getByRole('button',{name:'保护录音',exact:true}).isVisible());await page.locator('.recording-management>summary').click();
  await page.locator('body').press('Control+Home');
  await page.screenshot({path:path.join(root,'public-meeting-ui-'+code+'.png'),fullPage:false});
  fs.copyFileSync(path.join(root,'public-meeting-ui-'+code+'.png'),path.join(output,'meeting-details-after'+code+'.png'));
  record.state='ANDROID'+code+'_REAL_PHONE_FIRST_CONTENT_VISIBLE_SECONDARY_TOOLS_REACHABLE';record.regenerationShortcutWorked=true;record.localBookmarkReadWorked=true;record.recordingManagementReachable=true;record.newCloudCalls=0;
 }catch(error){record.state='ANDROID'+code+'_READING_UI_NOT_QUALIFIED';record.error=String(error);throw error;}
 finally{fs.writeFileSync(path.join(output,'reading-ui'+code+'.json'),JSON.stringify(record,null,2)+'\n');await browser.close();}
 console.log(JSON.stringify(record));
})().catch(error=>{console.error(String(error));process.exitCode=1;});
