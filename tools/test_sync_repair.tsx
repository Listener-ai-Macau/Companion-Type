import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionRecordingSync,type RecordingSyncStatus} from '../packages/ui/src/CompanionRecordingSync';

const damaged:RecordingSyncStatus={jobId:null,deviceId:null,phase:'blocked',recordingId:0,receivedBytes:0,totalBytes:0,pauseRequested:false,
  error:'录音同步设置暂时不可读取，自动同步已暂停；可以手动同步当前设备，原录音保留。'};
let calls=0, fail=true;
const repair=async()=>{calls++;if(fail)throw new Error('同步设置尚未修复，请检查本机文件权限或占用后重试；原录音和设置均保留。');};
const props={status:damaged,pauseBusy:false,resumeBlocked:false,onResume:()=>{},onRepair:repair};
let view:any;act(()=>{view=create(<CompanionRecordingSync {...props}/>);});
const body=()=>JSON.stringify(view.toJSON());
const button=(name:string)=>view.root.findAllByType('button').find((n:any)=>n.children.includes(name));
assert.match(body(),/清除所有设备之前的同步暂停选择/);
await act(async()=>{await button('修复设置并恢复自动同步').props.onClick();});
assert.match(body(),/同步设置尚未修复/);assert.equal(calls,1);
fail=false;
await act(async()=>{await button('修复设置并恢复自动同步').props.onClick();});
act(()=>view.update(<CompanionRecordingSync {...props} status={{...damaged,phase:'idle',error:undefined}}/>));
assert.match(body(),/自动同步设置已修复/);assert.equal(calls,2);
act(()=>button('知道了').props.onClick());assert.equal(view.toJSON(),null);
act(()=>view.update(<CompanionRecordingSync {...props} status={{...damaged,phase:'paused',deviceId:'AA:BB:CC:DD:EE:01',error:undefined}}/>));
assert.equal(button('修复设置并恢复自动同步'),undefined,'normal intentional pause is never offered as corruption');
console.log('PASS sync repair is explicit, reports failure and success, and leaves ordinary pause unchanged');
