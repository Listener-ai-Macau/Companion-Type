import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionDeviceRecordings,type DeviceRecording} from '../packages/ui/src/CompanionDeviceRecordings';
import {DeviceRecordingList} from '../apps/mobile/src/DeviceRecordingList';
const text=(x:any):string=>typeof x==='string'?x:(x?.children??[]).map(text).join('');
const key={deviceUid:'120011000d50335754363720',formatEpoch:'5a6584e1707422bb',sessionId:'00000000000000e0'};
const row:DeviceRecording={key,startedAtUnixSeconds:null,durationMs:3060,bytes:6986,segments:1,complete:true};
let listing=[row],deletes=0,syncs=0,approved=false;
let tree:any;
await act(async()=>{tree=create(<CompanionDeviceRecordings deviceId="C8:ED:45:EB:95:B4" busy={false} actions={{
 list:async()=>listing,sync:async selected=>{assert.deepEqual(selected,key);syncs++;},
 delete:async selected=>{assert.deepEqual(selected,key);deletes++;if(approved)listing=[];return {status:approved?'deleted':'cancelled',message:approved?'已删除':'已取消'};},
}}/>);});
const button=(name:string)=>tree.root.findAllByType('button').find((b:any)=>text(b)===name)!;
await act(async()=>{await button('刷新设备录音').props.onClick();});
assert.match(text(tree.toJSON()),/录音日期未知/);assert.doesNotMatch(text(tree.toJSON()),/1970|e0|5a6584/);
await act(async()=>{await button('接收这场').props.onClick();});assert.equal(syncs,1);
await act(async()=>{await button('删除设备副本').props.onClick();});assert.equal(deletes,1);assert.match(text(tree.toJSON()),/已取消/);assert.equal(tree.root.findAllByProps({'data-device-session':key.sessionId}).length,1);
approved=true;await act(async()=>{await button('删除设备副本').props.onClick();});assert.equal(deletes,2);assert.match(text(tree.toJSON()),/设备上没有待接收/);
let selected:any=null;
await act(async()=>{tree=create(<DeviceRecordingList rows={[{index:7,session:'224',segment:0,segments:1,bytes:6986,startedAtUnixSeconds:null,durationMs:3060,complete:true}]} busy={false} refresh={()=>{}} sync={r=>{selected=r;}} remove={()=>{}}/>);});
await act(async()=>{tree.root.findAllByType('button').find((b:any)=>text(b)==='接收这场')!.props.onClick();});
assert.equal(selected.index,7);assert.match(text(tree.toJSON()),/录音日期未知/);assert.doesNotMatch(text(tree.toJSON()),/录音 224|分段 0/);
console.log('PASS_DEVICE_RECORDINGS_COMPONENTS_EXACT_SELECTION_CANCEL_REFRESH_AND_UNKNOWN_DATE_SOFTWARE_ONLY');
