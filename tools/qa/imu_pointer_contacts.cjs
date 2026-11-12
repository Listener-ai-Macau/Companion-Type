// Source-component interaction only. No Tauri, BLE, microphone or OS input.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {build}=require('esbuild');const {chromium}=require('@playwright/test');
const root=path.resolve(__dirname,'../..');const out=path.resolve(process.argv[2]);fs.mkdirSync(out,{recursive:true});
const entry=`import React from 'react';import {createRoot} from 'react-dom/client';import {DesktopPointer} from ${JSON.stringify(path.join(root,'apps/windows/src/DesktopPointer.tsx'))};
const contacts=()=>({learning:null,leftSamples:0,rightSamples:0,calibrated:false,missedWindows:0,uncertain:0,lastSide:null});
window.calls=[];window.model={enabled:false,ready:false,controlsCursor:false,message:'',deviceId:'card-a',contacts:contacts(),metrics:{samples:100,missing:0,sensorHz:100,calibrated:true,dragging:false,paused:false}};
window.fakeInvoke=async(cmd,args)=>{window.calls.push({cmd,args});let s=window.model;
 if(cmd==='start_companion_pointer')s={...s,enabled:true,ready:true,settings:args.settings};
 if(cmd==='control_companion_pointer'){
  if(args.action==='contact-left')s={...s,contacts:{...contacts(),learning:'left'}};
  if(args.action==='contact-right')s={...s,contacts:{...s.contacts,learning:'right'}};
  if(args.action==='contact-save')s={...s,settings:{...s.settings,contactProfile:{left:[0,0,0,1,0,0],right:[0,0,0,-1,0,0]},contactDevice:'card-a'},contacts:{...s.contacts,calibrated:true,learning:null}};
  if(args.action==='contact-cancel')s={...s,contacts:{...s.contacts,learning:null}};
  if(args.action==='contact-clear')s={...s,contacts:contacts(),settings:{...s.settings,contactProfile:null,contactDevice:null}};
 }
 window.model=s;return structuredClone(s);
};
createRoot(document.getElementById('root')).render(<DesktopPointer connected={true} blocked={false}/>);`;
(async()=>{
 await build({stdin:{contents:entry,resolveDir:root,loader:'tsx'},bundle:true,jsx:'automatic',format:'iife',outfile:path.join(out,'ui.js'),plugins:[{name:'fake-command-boundary',setup(b){b.onResolve({filter:/^@tauri-apps\/api\/core$/},()=>({path:'commands',namespace:'fixture'}));b.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:'export const invoke=(...args)=>window.fakeInvoke(...args);',loader:'js'}));}}]});
 const server=http.createServer((req,res)=>{if(req.url==='/ui.js'){res.setHeader('content-type','application/javascript');res.end(fs.readFileSync(path.join(out,'ui.js')));}else{res.setHeader('content-type','text/html; charset=utf-8');res.end('<!doctype html><meta charset="utf-8"><div id="root"></div><script src="/ui.js"></script>');}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
 try{
  // Use an existing installed browser; do not download another browser tree.
  const executable=process.env.COMPANION_TEST_BROWSER||['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(p=>fs.existsSync(p));
  assert.ok(executable,'No installed browser available');browser=await chromium.launch({headless:true,executablePath:executable});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:'+server.address().port);await page.getByText('空中鼠标 · 转动卡片移动光标',{exact:true}).click();
  await page.getByLabel('桌面平移和转动一起控制').check();await page.getByRole('button',{name:'启用空中鼠标',exact:true}).click();
  const right=page.getByRole('button',{name:'继续右侧校准',exact:true});const save=page.getByRole('button',{name:'保存左右校准',exact:true});
  assert.equal(await right.isDisabled(),true);assert.equal(await save.isDisabled(),true);
  await page.getByRole('button',{name:'开始左侧校准',exact:true}).click();
  await page.getByText('请轻敲左侧 · 已收到左侧0次、右侧0次',{exact:true}).waitFor();
  await page.evaluate(()=>window.model.contacts.leftSamples=3);await right.waitFor();await page.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='继续右侧校准').disabled);
  await right.click();await page.getByText('请轻敲右侧 · 已收到左侧3次、右侧0次',{exact:true}).waitFor();
  assert.equal(await save.isDisabled(),true);await page.evaluate(()=>window.model.contacts.rightSamples=3);
  await page.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='保存左右校准').disabled);await save.click();
  await page.getByText('已保存这张卡片的左右轻敲校准：左侧左击、右侧右击，连续两次为双击。',{exact:true}).waitFor();
  let persisted=await page.evaluate(()=>JSON.parse(localStorage.getItem('companion-pointer-contact-v1')));assert.equal(persisted.contactDevice,'card-a');assert.equal(persisted.contactProfile.right[3],-1);
  await page.reload();await page.getByText('空中鼠标 · 转动卡片移动光标',{exact:true}).click();
  assert.equal(await page.getByLabel('桌面平移和转动一起控制').isChecked(),true);
  await page.getByRole('button',{name:'清除已保存的左右校准',exact:true}).click();
  persisted=await page.evaluate(()=>JSON.parse(localStorage.getItem('companion-pointer-contact-v1')));assert.equal(persisted.contactProfile,null);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS_SOURCE_COMPONENT_FAKE_COMMANDS',leftThenRightCounts:true,saveStateAndPersistence:true,clearWithoutActiveSession:true,consoleErrors:errors,actualNativeBackend:false,actualPhysicalRecognition:false,osInput:false,microphone:false},null,2));
  console.log('PASS_SOURCE_COMPONENT_FAKE_COMMANDS left/right count steps, save persistence, reload/clear; no native or hardware qualification');
 }finally{if(browser)await browser.close();server.close();}
})().catch(e=>{fs.writeFileSync(path.join(out,'failure.txt'),String(e.stack||e));console.error(e);process.exitCode=1;});
