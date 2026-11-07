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
console.log('PASS_REAL_MOBILE_COMPONENT_COMBINED_CATALOG_CONTROL_ACK_FOLLOWUP_FAILURE_NO_REPLAY_AND_LEGACY_BRIDGE');
