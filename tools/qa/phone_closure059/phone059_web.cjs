const fs=require('fs'),{spawnSync}=require('child_process'),assert=require('assert/strict');
const root='C:/Users/Billy/Desktop/Denzic/Companion',cache='E:/CodexData/Companion/.build-cache/device-phone055/acceptance059';
const {chromium}=require(root+'/recovered-software050/node_modules/playwright-core');
const adb=root+'/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe',serial='6LCAPVHE9PBE45DU';
const lease='Companion第1-2项059控制与公开资料导出验收';
fs.mkdirSync(cache,{recursive:true});
function run(args){const p=spawnSync(adb,['-s',serial,...args],{encoding:'utf8',windowsHide:true,timeout:20000});if(p.status!==0)throw Error(p.error||p.stderr);return p.stdout;}
function guard(){
 const line=fs.readFileSync(root+'/docs/board_operations.md','utf8').split('\n').find(x=>x.startsWith('- **占用中**'))||'';assert.ok(line.includes(lease),'Exact phone/board item not held');
 const activities=run(['shell','dumpsys','activity','activities']);
 const virtualFile=cache+'/virtual-session.json';
 const display=fs.existsSync(virtualFile)?JSON.parse(fs.readFileSync(virtualFile,'utf8')).displayId:null;
 if(display){
  const ownDisplay=run(['shell','dumpsys','display']).split('\n').find(s=>s.includes('DisplayDeviceInfo{"scrcpy"'))||'';
  assert.ok(ownDisplay.includes('FLAG_OWN_CONTENT_ONLY')&&ownDisplay.includes('FLAG_OWN_FOCUS')&&ownDisplay.includes('state ON'),'Own virtual display not available');
  const sections=activities.split(/(?=Display #\d+ \(activities from top to bottom\):)/);
  const own=sections.find(s=>s.startsWith('Display #'+display+' '));
  const main=sections.find(s=>s.startsWith('Display #0 '));
  assert.ok(own&&main,'Virtual and physical display metadata required');
  const top=own.split('\n').find(s=>s.includes('topResumedActivity='))||'';
  assert.ok(top.includes('com.denzic.companion.app/.MainActivity'),'Companion not resumed on own virtual display');
  const physical=main.split('\n').find(s=>s.includes('topResumedActivity='))||'';
  assert.ok(!/com\.denzic\.companion|com\.android\.documentsui|com\.google\.android\.documentsui|ChooserActivity/.test(physical),'Test window appeared on main display; no input');
 }else{
  const policy=run(['shell','dumpsys','window','policy']);const keyguard=policy.slice(policy.indexOf('KeyguardServiceDelegate'));
  assert.ok(keyguard.includes('screenState=SCREEN_STATE_ON')&&!/\b(showing|mIsShowing|inputRestricted|mInputRestricted)=true\b/.test(keyguard),'Locked/screen off; no input');
  const active=activities.split('\n').filter(s=>s.includes('topResumedActivity='));
  assert.equal(active.length,1);assert.ok(active[0].includes('com.denzic.companion.app/.MainActivity'),'Companion is not foreground; no input');
 }
}
let browser,port;
(async()=>{
 guard();const pid=run(['shell','pidof','com.denzic.companion.app']).trim();assert.match(pid,/^\d+$/);
 port=Number(run(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).trim());assert.ok(port>0);
 const url='http://127.0.0.1:'+port;
 const targets=await(await fetch(url+'/json/list',{signal:AbortSignal.timeout(5000)})).json();
 const displaySession=fs.existsSync(cache+'/virtual-session.json')?JSON.parse(fs.readFileSync(cache+'/virtual-session.json','utf8')):null;
 const visible=targets.filter(t=>{const d=JSON.parse(t.description||'{}');return d.visible===true&&d.attached!==false&&t.url.startsWith('https://appassets.androidplatform.net/')&&(!displaySession?.displayId||(d.width===1080&&d.height===1920));});
 assert.equal(visible.length,1,'Expected one visible product WebView');
 browser=await chromium.connectOverCDP(url,{timeout:8000});let page;
 for(const p of browser.contexts().flatMap(c=>c.pages())){const session=await p.context().newCDPSession(p);const info=(await session.send('Target.getTargetInfo')).targetInfo;await session.detach();if(info.targetId===visible[0].id)page=p;}
 assert.ok(page);page.setDefaultTimeout(10000);
 const action=process.argv[2]||'inspect',arg=process.argv[3],arg2=process.argv[4];
 let publicRestoreDialogAccepted=false;
 if(action==='restore-public')page.on('dialog',async dialog=>{assert.ok(dialog.message().includes('将校验你选择的备份'));publicRestoreDialogAccepted=true;await dialog.accept();});
 if(action==='click'){guard();let button=page.getByRole('button',{name:arg,exact:true});if(await button.count()>1){const nav=page.locator('.bottom-nav').getByRole('button',{name:arg,exact:true});assert.equal(await nav.count(),1,'Ambiguous UI control');button=nav;}await button.click();}
 else if(action==='restore-public'){guard();await page.getByRole('button',{name:'从备份恢复',exact:true}).click();}
 else if(action==='expand'){const summary=page.locator('summary').filter({hasText:arg});assert.equal(await summary.count(),1);if(!await summary.evaluate(s=>s.closest('details').open)){guard();await summary.click();}}
 else if(action==='select-device'){guard();await page.getByRole('button').filter({hasText:/C8:ED:45:EB:95:B4/i}).click();}
 else if(action==='open-own'){
  const allowed=JSON.parse(fs.readFileSync(cache+'/allowed-sessions.json','utf8'));assert.ok(allowed.some(s=>String(s.session)===arg));
  const row=page.getByRole('button').filter({hasText:new RegExp('未命名录音\\s*·\\s*'+arg+'\\b')});assert.equal(await row.count(),1);guard();await row.click();
 }else if(action==='open-public'){
  const row=page.getByRole('button').filter({hasText:'公开虚构导出验收056 · 非真实会议'});assert.equal(await row.count(),1);guard();await row.click();
 }else if(action==='format'){guard();await page.getByLabel('导出文件格式',{exact:true}).selectOption(arg);}
 else if(action==='select-public-content'){
  assert.ok(await page.getByRole('heading',{name:'公开虚构导出验收056 · 非真实会议',exact:true}).isVisible());
  for(const name of ['会议纪要','会议转写','补充与事项']){guard();await page.getByRole('checkbox',{name:new RegExp(name)}).setChecked(true);}
  const summary=page.locator('.export-materials summary');assert.equal(await summary.count(),1);if(!await summary.evaluate(s=>s.closest('details').open))await summary.click();
  const material=page.locator('[aria-label="选择AI材料"] input');assert.equal(await material.count(),1);guard();await material.setChecked(true);
 }
 else if(action==='transcript-only'){
  assert.ok(await page.getByRole('heading',{name:'公开虚构导出验收056 · 非真实会议',exact:true}).isVisible());
  for(const name of ['会议纪要','补充与事项']){guard();await page.getByRole('checkbox',{name:new RegExp(name)}).setChecked(false);}
  const material=page.locator('[aria-label="选择AI材料"] input');if(await material.count()){guard();await material.setChecked(false);}
  guard();await page.getByRole('checkbox',{name:/会议转写/}).setChecked(true);
 }
 else if(action==='section'){
  const checkbox=page.getByRole('checkbox',{name:new RegExp(arg)});assert.equal(await checkbox.count(),1);guard();await checkbox.setChecked(arg2==='true');
 }else if(action==='device-row'){
  const allowed=JSON.parse(fs.readFileSync(cache+'/allowed-sessions.json','utf8'));assert.ok(allowed.some(s=>String(s.session)===arg));
  guard();await page.locator(`[data-device-session="${arg}"]`).getByRole('button',{name:arg2,exact:true}).click();
 }else if(action==='scroll-backups'){
  guard();await page.locator('.library-backups').scrollIntoViewIfNeeded();
 }else if(action==='scroll-original'){
  const retained=page.locator('.library-backups-retained');assert.equal(await retained.count(),1);
  guard();if(!await retained.evaluate(node=>node.open))await retained.locator('summary').click();
  const original=retained.locator(':scope > div').filter({has:page.locator('span').filter({hasText:/^原有资料$/})});assert.equal(await original.count(),1);
  guard();await original.scrollIntoViewIfNeeded();
 }else if(action==='copy-public'){
  assert.ok(await page.getByRole('heading',{name:'公开虚构导出验收056 · 非真实会议',exact:true}).isVisible());
  guard();await page.getByRole('button',{name:'复制所选文字',exact:true}).click();
  await page.getByText('所选文字已复制，包含必要的来源与核对提示。',{exact:true}).waitFor({timeout:15000});
 }else if(action!=='inspect')throw Error('Unsupported action');
 await page.waitForTimeout(300);
 const exportFormatField=page.getByLabel('导出文件格式',{exact:true}),libraryField=page.locator('.library-backups-current'),playerField=page.locator('.player-card');
 const result={at:new Date().toISOString(),action,publicRestoreDialogAccepted,
  buttons:(await page.getByRole('button').evaluateAll(nodes=>nodes.filter(n=>!n.classList.contains('row')||n.innerText.includes('公开虚构导出验收')).map(n=>n.innerText))).filter(t=>!/(?:[\dA-F]{2}:){5}[\dA-F]{2}/i.test(t)||t.includes('C8:ED:45:EB:95:B4')),
  alerts:await page.locator('[role=status],[role=alert]').allTextContents(),
  deviceSessions:await page.locator('[data-device-session]').evaluateAll(rows=>rows.map(r=>r.getAttribute('data-device-session'))),
  selectedSections:await page.locator('.content-export input:checked').evaluateAll(nodes=>nodes.map(n=>n.closest('label').innerText)),
  exportFormat:await exportFormatField.count()?await exportFormatField.inputValue():null,
  library:await libraryField.count()?await libraryField.textContent():null,
  publicFixtureOpen:await page.getByRole('heading',{name:'公开虚构导出验收056 · 非真实会议',exact:true}).isVisible().catch(()=>false),
  player:await playerField.count()?await playerField.innerText():null};
 // Suppress original-library title buttons in persisted state, retaining app
 // controls and only this batch's explicitly public/new-test rows.
 const allowedSessions=fs.existsSync(cache+'/allowed-sessions.json')?JSON.parse(fs.readFileSync(cache+'/allowed-sessions.json','utf8')):[];
 result.buttons=result.buttons.filter(t=>!t.includes('未命名录音')||allowedSessions.some(s=>new RegExp('未命名录音\\s*·\\s*'+String(s.session)+'\\b').test(t)));
 fs.writeFileSync(cache+`/web-${Date.now()}-${action}.json`,JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1;}).finally(async()=>{
 if(browser)await Promise.race([browser.close(),new Promise(r=>setTimeout(r,1200))]);if(port)run(['forward','--remove','tcp:'+port]);
 // The completed ordinary action is already persisted. End only this driver
 // if Android's detached WebView CDP session delays transport cleanup.
 setTimeout(()=>process.exit(process.exitCode||0),100).unref();
});
