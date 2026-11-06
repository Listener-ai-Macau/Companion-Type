const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root='C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055',cache='E:/CodexData/Companion/.build-cache/device-phone055/ui';
const out='C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-device-phone-closure055';
const {build}=require(root+'/node_modules/esbuild'),{chromium}=require(root+'/node_modules/playwright');
(async()=>{
 fs.mkdirSync(cache,{recursive:true});const entry=cache+'/preview.tsx';fs.writeFileSync(entry,`
 import React from 'react';import{createRoot}from'react-dom/client';import{App}from'${root}/apps/mobile/src/App';
 const address='C8:ED:45:EB:95:B4',pack={id:'a'.repeat(64),firmwareVersion:66685,resourceVersion:85,bytes:1359700,authentication:'Boot在安装前验证签名',consistencyChecked:true};
 const fixture=window.fixture={calls:[],pairFail:true,catalogFail:true,clearCancelled:true,startCancelled:true,update:{running:false,phase:'idle',address:'',name:'Companion',accepted:0,total:0,message:'',canCancel:false,canVerify:false}};
 window.CompanionNative={permissions(){},openBluetoothSettings(){},setAppearance(){},finishApp(){},cancelMinutes(){},cancelTranscription(){},exportDocument(){},exportAudio(){},pickDeviceUpdate(id){fixture.update.prepared=pack;setTimeout(()=>window.companionReply({id,result:pack,error:null}),0);},call(id,method,json){const args=JSON.parse(json);fixture.calls.push({method,args});let result=null,error=null;switch(method){
 case'library':result={rows:[],problems:0};break;case'status':result={state:'idle',detail:'',running:false,hasSavedTask:false};break;
 case'discoverDevices':case'devices':result=[{index:0,address,name:'Companion · 公开测试录音卡',bonded:false}];break;
 case'pairDevice':if(fixture.pairFail)error='配对已取消，请重新选择录音卡。';else result={paired:true,address};break;
 case'connectDevice':result={connected:true,address};break;
 case'catalog':if(fixture.catalogFail)error='测试：连接已验证，但本次录音列表暂不可读。';else result=[];break;
 case'pendingConfirmation':result={pending:false,invalid:false,deferred:[],unreadableCount:0};break;
 case'deviceMaintenance':result={address,name:'Companion',operation:args.operation,cancelled:args.operation==='clearPairings'&&fixture.clearCancelled,settingsSaved:true,defaultSettings:true,radioEnabled:true,bondCountValid:true,bonds:args.operation==='clearPairings'?0:1};break;
 case'deviceUpdateStatus':result=structuredClone(fixture.update);break;
 case'startDeviceUpdate':if(fixture.startCancelled)result={...fixture.update,cancelled:true};else{fixture.update={...fixture.update,running:true,phase:'transferring',name:'Companion',address,accepted:64000,total:pack.bytes,canCancel:true,message:'正在传入完整升级包'};result=fixture.update;}break;
 case'cancelDeviceUpdate':fixture.update={...fixture.update,running:false,phase:'cancelled',canCancel:false,message:'已停止传入，原录音保留。'};result=fixture.update;break;
 default:error='Unsupported controlled call: '+method;
 }setTimeout(()=>window.companionReply({id,result,error}),0);}};
 createRoot(document.getElementById('root')).render(<App/>);`);
 await build({entryPoints:[entry],outfile:cache+'/view.js',bundle:true,nodePaths:[root+'/node_modules'],platform:'browser',format:'iife',jsx:'automatic',tsconfig:root+'/apps/mobile/tsconfig.json',loader:{'.css':'css'}});
 fs.writeFileSync(cache+'/view.html','<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="view.css"><div id="root"></div><script src="view.js"></script></html>');
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});const page=await browser.newPage({viewport:{width:393,height:852},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(String(e)));await page.goto('file:///'+cache+'/view.html');await page.getByRole('button',{name:'设备',exact:true}).click();
 await page.getByRole('button',{name:'搜索录音卡',exact:true}).click();await page.getByRole('button',{name:/公开测试录音卡/}).click();await page.getByRole('alert').filter({hasText:'配对已取消'}).waitFor();assert.equal(await page.evaluate(()=>window.fixture.calls.filter(x=>x.method==='connectDevice').length),0);
 await page.evaluate(()=>window.fixture.pairFail=false);await page.getByRole('button',{name:/公开测试录音卡/}).click();await page.getByText('设备录音列表尚未读取成功，已有录音保留。可重新读取列表，或在维护区域检查设备状态。',{exact:true}).waitFor();
 await page.locator('.device-maintenance>summary').click();await page.getByRole('button',{name:'读取设备状态',exact:true}).click();await page.getByText('1 台设备',{exact:true}).waitFor();
 await page.getByRole('button',{name:'清除录音卡配对',exact:true}).click();await page.getByText('已取消，设备设置和录音保持。',{exact:true}).waitFor();assert.equal(await page.locator('.device-maintenance').count(),1);
 await page.evaluate(()=>window.fixture.catalogFail=false);await page.getByRole('button',{name:'重新读取录音列表',exact:true}).click();await page.getByText('设备录音列表尚未读取成功，已有录音保留。可重新读取列表，或在维护区域检查设备状态。',{exact:true}).waitFor({state:'detached'});
 await page.locator('.device-update>summary').click();await page.getByRole('button',{name:'选择升级包',exact:true}).click();await page.getByRole('button',{name:'开始升级',exact:true}).click();await page.getByText('已取消，没有开始升级。',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'搜索录音卡',exact:true}).isEnabled(),true);
 await page.evaluate(()=>window.fixture.startCancelled=false);await page.getByRole('button',{name:'开始升级',exact:true}).click();await page.getByRole('button',{name:'停止传入',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'搜索录音卡',exact:true}).isDisabled(),true);
 await page.getByRole('button',{name:'停止传入',exact:true}).click();await page.getByText('已停止传入，原录音保留。',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'搜索录音卡',exact:true}).isEnabled(),true);
 const widths=[];for(const width of [360,393,430]){await page.setViewportSize({width,height:852});widths.push(await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth})));assert.equal(widths.at(-1).scroll,width);}
 await page.setViewportSize({width:393,height:852});await page.locator('.device-update').scrollIntoViewIfNeeded();await page.screenshot({path:out+'/device-update-light.png'});await page.locator('.mobile-app').evaluate(el=>el.setAttribute('data-theme','dark'));await page.screenshot({path:out+'/device-update-dark.png'});
 await page.locator('.mobile-app').evaluate(el=>el.setAttribute('data-theme','light'));await page.locator('.device-maintenance').scrollIntoViewIfNeeded();await page.screenshot({path:out+'/device-maintenance-light.png'});
 await page.evaluate(()=>window.fixture.clearCancelled=false);await page.getByRole('button',{name:'清除录音卡配对',exact:true}).click();await page.getByText('录音卡配对信息已清除。请在系统蓝牙中忘记旧配对，再搜索连接；原录音和手机已保存资料保留。',{exact:true}).waitFor();assert.equal(await page.locator('.device-maintenance').count(),0);
 const calls=await page.evaluate(()=>window.fixture.calls);await browser.close();assert.deepEqual(errors,[]);fs.writeFileSync(out+'/device-ui-verification.json',JSON.stringify({result:'PASS_CONTROLLED_ACTUAL_APP_UI',scope:'Production App and components, synthetic native bridge; no OS pairing dialog, clipboard, real radio or physical OTA.',cases:['Pair cancellation never connects','Verified selection remains maintainable when catalog fails','Catalog retry','Maintenance exact device/cancel/clear reset','Package choice and explicit start cancellation','Update start blocks device operations','Stop transfer releases device controls','360/393/430 no horizontal overflow','light/dark production CSS'],widths,pageErrors:errors,calls},null,2));console.log('PASS ordinary device UI, catalog failure recovery, pairing cancellation, maintenance, update select/start/cancel and light/dark responsive layouts; controlled bridge only.');
})().catch(e=>{console.error(e);process.exitCode=1;});
