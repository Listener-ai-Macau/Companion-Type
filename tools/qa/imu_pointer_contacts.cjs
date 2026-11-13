// Angular-only component contract. Fake commands; no native/BLE/OS proof.
// Previous experimental contact flow is retained in Git history.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {build}=require('esbuild');const {chromium}=require('@playwright/test');
const root=path.resolve(__dirname,'../..'),out=path.resolve(process.argv[2]);fs.mkdirSync(out,{recursive:true});
const entry=`import React from 'react';import {createRoot} from 'react-dom/client';import {DesktopPointer} from ${JSON.stringify(path.join(root,'apps/windows/src/DesktopPointer.tsx'))};
window.calls=[];window.model={enabled:false,ready:false,controlsCursor:false,message:'',deviceId:'card-a',metrics:{samples:100,missing:0,sensorHz:100,calibrated:true,dragging:false,paused:false}};
window.fakeInvoke=async(cmd,args)=>{window.calls.push({cmd,args});let s=window.model;
 if(cmd==='start_companion_pointer')s={...s,enabled:true,ready:true,settings:args.settings};
 if(cmd==='control_companion_pointer'){
  if(args.action==='pause'||args.action==='resume')s={...s,metrics:{...s.metrics,paused:args.action==='pause'}};
  if(args.action==='stop')s={...s,enabled:false,ready:false};
 }
 window.model=s;return structuredClone(s);
};createRoot(document.getElementById('root')).render(<DesktopPointer connected={true} blocked={false}/>);`;
(async()=>{
 await build({stdin:{contents:entry,resolveDir:root,loader:'tsx'},bundle:true,jsx:'automatic',format:'iife',outfile:path.join(out,'ui.js'),plugins:[{name:'fake-command-boundary',setup(b){b.onResolve({filter:/^@tauri-apps\/api\/core$/},()=>({path:'commands',namespace:'fixture'}));b.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:'export const invoke=(...args)=>window.fakeInvoke(...args);',loader:'js'}));}}]});
 const server=http.createServer((req,res)=>{if(req.url==='/ui.js'){res.setHeader('content-type','application/javascript');res.end(fs.readFileSync(path.join(out,'ui.js')));}else{res.setHeader('content-type','text/html; charset=utf-8');res.end('<!doctype html><meta charset="utf-8"><div id="root"></div><script src="/ui.js"></script>');}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
 try{
  const executable=process.env.COMPANION_TEST_BROWSER||['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(p=>fs.existsSync(p));
  assert.ok(executable);browser=await chromium.launch({headless:true,executablePath:executable});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{if(!localStorage.getItem('test-seeded')){
   localStorage.setItem('companion-pointer-contact-v1',JSON.stringify({mapping:'relative',desktopMotion:true,sensitivity:1.3,contactDevice:'card-a',contactProfile:{left:[0,0,0,1,0,0],right:[0,0,0,-1,0,0]}}));localStorage.setItem('test-seeded','1');
  }});
  await page.goto('http://127.0.0.1:'+server.address().port);await page.getByText('空中鼠标 · 转动卡片移动光标',{exact:true}).click();
  await page.getByText(/将Type-C接口朝向屏幕/).waitFor();
  assert.equal(await page.getByLabel('桌面平移和转动一起控制').count(),0);
  assert.equal(await page.getByRole('button',{name:'开始左侧校准',exact:true}).count(),0);
  const backup=await page.evaluate(()=>JSON.parse(localStorage.getItem('companion-pointer-contact-v1-planar-paused')));
  assert.equal(backup.desktopMotion,true);assert.equal(backup.contactDevice,'card-a');
  const mapping=page.getByLabel('空中鼠标移动方式');await mapping.selectOption('laser');
  await page.getByRole('button',{name:'启用空中鼠标',exact:true}).click();assert.equal(await mapping.isDisabled(),true);
  const requests=await page.evaluate(()=>window.calls.filter(v=>v.cmd==='start_companion_pointer'));
  assert.equal(requests.length,1);assert.equal(requests[0].args.settings.desktopMotion,false);assert.equal(requests[0].args.settings.contactProfile,null);assert.equal(requests[0].args.settings.mapping,'laser');assert.equal(requests[0].args.settings.sensitivity,1.3);
  await page.getByRole('button',{name:'暂停控制',exact:true}).click();await page.getByRole('button',{name:'继续控制',exact:true}).click();
  await page.getByRole('button',{name:'以当前握姿居中',exact:true}).click();await page.getByRole('button',{name:'退出并回到录音',exact:true}).click();
  const actions=await page.evaluate(()=>window.calls.filter(v=>v.cmd==='control_companion_pointer').map(v=>v.args.action));assert.deepEqual(actions,['pause','resume','recenter','stop']);
  await page.reload();await page.getByText('空中鼠标 · 转动卡片移动光标',{exact:true}).click();
  const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('companion-pointer-contact-v1')));assert.equal(saved.desktopMotion,false);assert.equal(saved.contactProfile,null);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS_ANGULAR_UI_CONTRACT_FAKE_COMMANDS',fixedTypeCGuide:true,oldPlanarSettingsCannotReactivate:true,oldContactExamplesPreserved:true,singleMappingWhileActive:true,pauseResumeRecenterStopWired:true,actualNativeBackend:false,physicalRecognition:false,osInput:false,microphone:false},null,2));
  console.log('PASS_ANGULAR_UI_CONTRACT_FAKE_COMMANDS; native/physical qualification separate');
 }finally{if(browser)await browser.close();server.close();}
})().catch(e=>{fs.writeFileSync(path.join(out,'failure.txt'),String(e.stack||e));console.error(e);process.exitCode=1;});
