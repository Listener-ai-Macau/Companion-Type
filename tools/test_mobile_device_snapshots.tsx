import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
const g=globalThis as any;
g.document={querySelectorAll:()=>[],querySelector:()=>null,getElementById:()=>null};
g.localStorage={getItem:()=>null,setItem:()=>{}};
g.window={setTimeout,clearTimeout,setInterval,clearInterval,requestAnimationFrame:(fn:any)=>{fn();return 0;},matchMedia:()=>({matches:false})};
const {App}=await import('../apps/mobile/src/App');
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const old={index:0,session:'41',segment:0,segments:1,bytes:2000,durationMs:1000,complete:true};
const fresh={...old,index:1,session:'42'};
async function scenario(combined:boolean,followFailure=false,stopFailure=false){
 const calls:{method:string;args:any}[]=[];let current='stopped';
 const inventory=()=>({sessions:current==='stopped'?[]:[{hostSession:'owned-capture',state:current,pendingCommand:null,maxSeconds:0,durationMs:1000}],unreadableCount:0});
 window.CompanionNative={permissions(){},cancelTranscription(){},cancelMinutes(){},finishApp(){},openBluetoothSettings(){},exportDocument(){},exportAudio(){},call(id,method,input){
  const a=JSON.parse(input);calls.push({method,args:a});let result:any=null,error:string|null=null;
  switch(method){
   case'library':result={rows:[],problems:0};break;
   case'status':result={running:false,state:'stopped',detail:'',hasSavedTask:false};break;
   case'aiServiceStatus':result={configured:false,saved:false};break;
   case'deviceUpdateStatus':result={running:false,phase:'idle'};break;
   case'devices':result=[{index:0,name:'Companion',address:'C8:ED:45:EB:95:B4',bonded:true}];break;
   case'connectDevice':result={connected:true,address:a.address,...(combined?{recordings:[old]}:{})};break;
   case'catalog':result=[old];break;
   case'pendingConfirmation':result={pending:false,invalid:false,deferred:[],unreadableCount:0};break;
   case'controlInventory':result=inventory();break;
   case'control':
    if(a.action==='STOP'&&stopFailure){error='连接中断，操作未确认';break;}
    current=a.action==='STOP'?'stopped':'recording';result={state:current};
    if(combined){
     if(a.action==='STOP'&&followFailure)Object.assign(result,{inventoryRefreshFailed:true,recordingsRefreshFailed:true});
     else Object.assign(result,{inventory:inventory(),...(a.action==='STOP'?{recordings:[old,fresh]}:{})});
    }
    break;
   default:error='Unexpected test bridge operation '+method;
  }
  queueMicrotask(()=>window.companionReply({id,result,error}));
 }};
 let tree:any;await act(async()=>{tree=create(<App/>);await new Promise(setImmediate);});
 const click=async(name:string,contains=false)=>{const b=tree.root.findAllByType('button').find((n:any)=>contains?text(n).includes(name):text(n)===name);assert.ok(b,name);await act(async()=>{b.props.onClick();await new Promise(setImmediate);});};
 try{
  await click('设备');await click('读取已配对设备');await click('95:B4',true);
  assert.equal(calls.filter(c=>c.method==='connectDevice').length,1);
  assert.equal(calls.filter(c=>c.method==='catalog').length,combined?0:1,'current connection supplies the catalogue; legacy still supported');
  assert.equal(tree.root.findAllByProps({'data-device-session':'41'}).length,1);
  await click('读取状态');const before=calls.filter(c=>c.method==='controlInventory').length;
  await click('开始录音');assert.match(text(tree.toJSON()),/设备返回：正在录音/);
  assert.equal(calls.filter(c=>c.method==='controlInventory').length,before+(combined?0:1));
  await click('停止录音');assert.equal(calls.filter(c=>c.method==='control'&&c.args.action==='STOP').length,1,'never replay STOP for a failed refresh');
  if(stopFailure){assert.match(text(tree.toJSON()),/连接中断，操作未确认/);assert.doesNotMatch(text(tree.toJSON()),/设备返回：已停止/);}
  else {
   assert.match(text(tree.toJSON()),/设备返回：已停止/);
   if(followFailure){assert.match(text(tree.toJSON()),/目录暂未刷新/);assert.equal(tree.root.findAllByProps({'data-device-session':'41'}).length,0);}
   else if(combined){assert.equal(tree.root.findAllByProps({'data-device-session':'42'}).length,1,'new recording available without reconnect/refresh');}
  }
  if(combined)assert.equal(calls.filter(c=>c.method==='controlInventory').length,before+(stopFailure?1:0),'no post-ACK inventory reconnect');
 }finally{await act(async()=>tree.unmount());}
}
await scenario(true);await scenario(true,true);await scenario(true,false,true);await scenario(false);
async function completionScenario(state:string,address:string,identity:string,legacy=false){
 const expected='uid:epoch:42',other='different-uid:epoch:42',source=[{...old,identity:'uid:epoch:41'},{...fresh,identity:legacy?undefined:expected},{...fresh,index:2,identity:other}];
 let receiving=false,finished=false,tick:(()=>void)|undefined;const indices:number[]=[];
 const previousInterval=window.setInterval,previousClear=window.clearInterval;
 window.setInterval=((fn:any,ms:number)=>{if(ms===3000)tick=fn;return 1;})as any;window.clearInterval=(()=>{})as any;
 window.CompanionNative={permissions(){},cancelTranscription(){},cancelMinutes(){},finishApp(){},openBluetoothSettings(){},exportDocument(){},exportAudio(){},call(id,method,input){
  const a=JSON.parse(input);let result:any=null,error:string|null=null;
  switch(method){
   case'library':result={rows:[],problems:0};break;
   case'status':result=finished?{running:false,state,detail:'done',hasSavedTask:true,completedDeviceRecording:{address,identity}}:{running:receiving,state:receiving?'syncing':'idle',detail:'',hasSavedTask:receiving};break;
   case'aiServiceStatus':result={configured:false,saved:false};break;
   case'deviceUpdateStatus':result={running:false,phase:'idle'};break;
   case'devices':result=[{index:0,name:'Companion',address:'C8:ED:45:EB:95:B4',bonded:true}];break;
   case'connectDevice':result={connected:true,address:a.address,recordings:source};break;
   case'pendingConfirmation':result={pending:false,invalid:false,deferred:[],unreadableCount:0};break;
   case'sync':receiving=true;indices.push(a.index);result={running:true,state:'syncing',detail:'receiving',hasSavedTask:true};break;
   default:error='Unexpected completion bridge operation '+method;
  }
  queueMicrotask(()=>window.companionReply({id,result,error}));
 }};
 let tree:any;await act(async()=>{tree=create(<App/>);await new Promise(setImmediate);});
 const click=async(name:string,contains=false)=>{const b=tree.root.findAllByType('button').find((n:any)=>contains?text(n).includes(name):text(n)===name);assert.ok(b,name);await act(async()=>{b.props.onClick();await new Promise(setImmediate);});};
 try{
  await click('设备');await click('读取已配对设备');await click('95:B4',true);
  const target=tree.root.findAllByProps({'data-device-session':'42'})[0].findAllByType('button').find((n:any)=>text(n)==='接收这场');
  await act(async()=>{target.props.onClick();await new Promise(setImmediate);});assert.ok(tick);finished=true;
  await act(async()=>{tick!();await new Promise(setImmediate);});await click('设备');
  const removed=state==='complete'&&address==='C8:ED:45:EB:95:B4'&&identity===expected&&!legacy;
  assert.equal(tree.root.findAllByProps({'data-device-session':'41'}).length,1,'unrelated session retained');
  assert.equal(tree.root.findAllByProps({'data-device-session':'42'}).length,removed?1:2,'exact UID/epoch/session only, matching selected device and completed state');
  if(removed){const next=tree.root.findAllByProps({'data-device-session':'42'})[0].findAllByType('button').find((n:any)=>text(n)==='接收这场');finished=false;await act(async()=>{next.props.onClick();await new Promise(setImmediate);});assert.deepEqual(indices,[1,2],'hiding consumed row never renumbers native catalogue indices');}
 }finally{await act(async()=>tree.unmount());window.setInterval=previousInterval;window.clearInterval=previousClear;}
}
await completionScenario('complete','C8:ED:45:EB:95:B4','uid:epoch:42');
await completionScenario('stopped','C8:ED:45:EB:95:B4','uid:epoch:42');
await completionScenario('complete','another-device','uid:epoch:42');
await completionScenario('complete','C8:ED:45:EB:95:B4','uid:another-epoch:42');
await completionScenario('complete','C8:ED:45:EB:95:B4','uid:epoch:42',true);
async function controlReplyAcrossCompletion(deferred:boolean){
 let receiving=false,finished=false,tick:(()=>void)|undefined,answer:(()=>void)|undefined;
 const oldInterval=window.setInterval,oldClear=window.clearInterval;
 window.setInterval=((fn:any,ms:number)=>{if(ms===3000)tick=fn;return 1;})as any;window.clearInterval=(()=>{})as any;
 window.CompanionNative={permissions(){},cancelTranscription(){},cancelMinutes(){},finishApp(){},openBluetoothSettings(){},exportDocument(){},exportAudio(){},call(id,method,input){
  const a=JSON.parse(input);let result:any=null;
  switch(method){
   case'library':result={rows:[],problems:0};break;
   case'status':result={running:receiving&&!finished,state:finished?'complete':receiving?'syncing':'idle',detail:'',hasSavedTask:receiving};break;
   case'aiServiceStatus':result={configured:false,saved:false};break;
   case'deviceUpdateStatus':result={running:false,phase:'idle'};break;
   case'devices':result=[{index:0,name:'Companion',address:'C8:ED:45:EB:95:B4',bonded:true},{index:1,name:'Other',address:'C8:ED:45:EB:95:B5',bonded:true}];break;
   case'connectDevice':result={connected:true,address:a.address,recordings:[old]};break;
   case'pendingConfirmation':result={pending:false,invalid:false,deferred:[],unreadableCount:0};break;
   case'sync':receiving=true;result={running:true,state:'syncing',detail:'',hasSavedTask:true};break;
   case'controlInventory':result={sessions:[],unreadableCount:0};break;
   default:throw Error('Unexpected control completion bridge operation '+method);
  }
  const reply=()=>window.companionReply({id,result,error:null});
  if(method==='controlInventory'&&deferred)answer=reply;else queueMicrotask(reply);
 }};
 let tree:any;await act(async()=>{tree=create(<App/>);await new Promise(setImmediate);});
 const buttons=(name:string)=>tree.root.findAllByType('button').filter((n:any)=>text(n)===name);
 const click=async(name:string,contains=false)=>{const b=tree.root.findAllByType('button').find((n:any)=>contains?text(n).includes(name):text(n)===name);assert.ok(b,name);await act(async()=>{b.props.onClick();await new Promise(setImmediate);});};
 try{
  await click('设备');await click('读取已配对设备');await click('95:B4',true);
  await click('接收这场');await click('设备');await click('读取状态');assert.ok(tick);
  if(!deferred)assert.equal(buttons('开始录音').length,1,'successful query is shown while receive remains active');
  finished=true;await act(async()=>{tick!();await new Promise(setImmediate);});
  if(deferred){assert.ok(answer);await act(async()=>{answer!();await new Promise(setImmediate);});}
  assert.equal(buttons('开始录音').length,1,'late receive-complete status must not erase a successful selected-device query');
  assert.equal(buttons('开始录音')[0].props.disabled,false,'completed receiver leaves queried controls usable');
  await click('95:B5',true);assert.equal(buttons('开始录音').length,0,'switching device still clears prior device controls');
 }finally{await act(async()=>tree.unmount());window.setInterval=oldInterval;window.clearInterval=oldClear;}
}
await controlReplyAcrossCompletion(false);await controlReplyAcrossCompletion(true);
console.log('PASS_CONTROL_REPLY_SURVIVES_BOTH_COMPLETION_ORDERINGS_OTHER_DEVICE_STILL_CLEARS');
console.log('PASS_REAL_MOBILE_COMPONENT_COMBINED_CATALOG_CONTROL_ACK_FOLLOWUP_FAILURE_NO_REPLAY_AND_LEGACY_BRIDGE');
console.log('PASS_COMPLETED_EXACT_DEVICE_UID_EPOCH_SESSION_ROW_REMOVED_PAUSE_OTHER_DEVICE_EPOCH_LEGACY_RETAINED_NATIVE_INDICES_UNCHANGED');
