const fs=require('fs'),{spawnSync}=require('child_process'),assert=require('assert/strict');
const root='C:/Users/Billy/Desktop/Denzic/Companion',cache='E:/CodexData/Companion/.build-cache/device-phone055/acceptance059';
const {chromium}=require(root+'/recovered-software050/node_modules/playwright-core');
const adb=root+'/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe',serial='6LCAPVHE9PBE45DU';
const lease='Companion第1-2项059控制与公开资料导出验收';
fs.mkdirSync(cache,{recursive:true});
function run(args){const p=spawnSync(adb,['-s',serial,...args],{encoding:'utf8',windowsHide:true,timeout:20000});if(p.status!==0)throw Error(p.error||p.stderr);return p.stdout;}
function guard(){
 const line=fs.readFileSync(root+'/docs/board_operations.md','utf8').split('\n').find(x=>x.startsWith('- **占用中**'))||'';assert.ok(line.includes(lease),'Exact phone/board item not held');
 const policy=run(['shell','dumpsys','window','policy']);const keyguard=policy.slice(policy.indexOf('KeyguardServiceDelegate'));
 assert.ok(keyguard.includes('screenState=SCREEN_STATE_ON')&&!/\b(showing|mIsShowing|inputRestricted|mInputRestricted)=true\b/.test(keyguard),'Locked/screen off; no input');
 const active=run(['shell','dumpsys','activity','activities']).split('\n').filter(s=>s.includes('topResumedActivity='));
 assert.equal(active.length,1);assert.ok(active[0].includes('com.denzic.companion.app/.MainActivity'),'Companion is not foreground; no input');
}
let browser,port;
(async()=>{
 guard();const pid=run(['shell','pidof','com.denzic.companion.app']).trim();assert.match(pid,/^\d+$/);
 port=Number(run(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).trim());assert.ok(port>0);
 const url='http://127.0.0.1:'+port;
 const targets=await(await fetch(url+'/json/list',{signal:AbortSignal.timeout(5000)})).json();
 const visible=targets.filter(t=>JSON.parse(t.description||'{}').visible===true&&t.url.startsWith('https://appassets.androidplatform.net/'));
 assert.equal(visible.length,1,'Expected one visible product WebView');
 browser=await chromium.connectOverCDP(url,{timeout:8000});let page;
 for(const p of browser.contexts().flatMap(c=>c.pages())){const session=await p.context().newCDPSession(p);const info=(await session.send('Target.getTargetInfo')).targetInfo;await session.detach();if(info.targetId===visible[0].id)page=p;}
 assert.ok(page);page.setDefaultTimeout(10000);
 const action=process.argv[2]||'inspect',arg=process.argv[3],arg2=process.argv[4];
 if(action==='click'){guard();await page.getByRole('button',{name:arg,exact:true}).click();}
 else if(action==='expand'){const summary=page.locator('summary').filter({hasText:arg});assert.equal(await summary.count(),1);if(!await summary.evaluate(s=>s.closest('details').open)){guard();await summary.click();}}
 else if(action==='select-device'){guard();await page.getByRole('button').filter({hasText:/C8:ED:45:EB:95:B4/i}).click();}
 else if(action==='open-own'){
  const allowed=JSON.parse(fs.readFileSync(cache+'/allowed-sessions.json','utf8'));assert.ok(allowed.some(s=>String(s.session)===arg));
  const row=page.getByRole('button').filter({hasText:new RegExp('未命名录音\\s*·\\s*'+arg+'\\b')});assert.equal(await row.count(),1);guard();await row.click();
 }else if(action==='open-public'){
  const row=page.getByRole('button').filter({hasText:'公开虚构导出验收056 · 非真实会议'});assert.equal(await row.count(),1);guard();await row.click();
 }else if(action==='format'){guard();await page.getByLabel('导出文件格式',{exact:true}).selectOption(arg);}
 else if(action==='section'){
  const checkbox=page.getByRole('checkbox',{name:new RegExp(arg)});assert.equal(await checkbox.count(),1);guard();await checkbox.setChecked(arg2==='true');
 }else if(action==='device-row'){
  const allowed=JSON.parse(fs.readFileSync(cache+'/allowed-sessions.json','utf8'));assert.ok(allowed.some(s=>String(s.session)===arg));
  guard();await page.locator(`[data-device-session="${arg}"]`).getByRole('button',{name:arg2,exact:true}).click();
 }else if(action==='copy-public'){
  assert.ok(await page.getByRole('heading',{name:'公开虚构导出验收056 · 非真实会议',exact:true}).isVisible());
  guard();await page.getByRole('button',{name:'复制所选文字',exact:true}).click();
  await page.getByText('所选文字已复制，包含必要的来源与核对提示。',{exact:true}).waitFor({timeout:15000});
 }else if(action!=='inspect')throw Error('Unsupported action');
 await page.waitForTimeout(300);
 const result={at:new Date().toISOString(),action,
  buttons:(await page.getByRole('button').allTextContents()).filter(t=>!/(?:[\dA-F]{2}:){5}[\dA-F]{2}/i.test(t)||t.includes('C8:ED:45:EB:95:B4')),
  alerts:await page.locator('[role=status],[role=alert]').allTextContents(),
  deviceSessions:await page.locator('[data-device-session]').evaluateAll(rows=>rows.map(r=>r.getAttribute('data-device-session'))),
  selectedSections:await page.locator('.content-export input:checked').evaluateAll(nodes=>nodes.map(n=>n.closest('label').innerText)),
  exportFormat:await page.getByLabel('导出文件格式',{exact:true}).inputValue().catch(()=>null),
  library:await page.locator('.library-backups-current').textContent().catch(()=>null),
  publicFixtureOpen:await page.getByRole('heading',{name:'公开虚构导出验收056 · 非真实会议',exact:true}).isVisible().catch(()=>false),
  player:await page.locator('.player-card').innerText().catch(()=>null)};
 // Suppress original-library title buttons in persisted state, retaining app
 // controls and only this batch's explicitly public/new-test rows.
 result.buttons=result.buttons.filter(t=>!t.includes('未命名录音')||/未命名录音\s*·\s*(?:23\d|24\d)\b/.test(t));
 fs.writeFileSync(cache+`/web-${Date.now()}-${action}.json`,JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1;}).finally(async()=>{
 if(browser)await browser.close();if(port)run(['forward','--remove','tcp:'+port]);
});
