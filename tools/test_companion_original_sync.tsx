import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';

// The user can resume a restored board original without inventing a START,
// STOP, connection acknowledgement or a replacement meeting. Software only.
let snapshot = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {action:'meetingStart',sessionId:'original-long'});
const row=snapshot.host.sessions[0];row.source='boardDevice';row.sourceDeviceId='C8:92:FF:DD:3B:CA';
row.deviceRecordingId=32;row.deviceRecordingKey={deviceUid:'180010000d50335754363720',formatEpoch:'1f59b27acf4936e1',sessionId:'000000000000000c'};
snapshot.connected=false;snapshot.device.connected=false;snapshot.device.deviceId=null;
snapshot.host.persistence={status:'ready'};
const calls:any[]=[];let renderer:any;
let pausedDevice=row.sourceDeviceId;let busyAction:any=null;let boardOnlineLive:any=null;
const props=()=>({snapshot,surface:'windows' as const,busyAction,error:null,onRefresh:()=>{},onControl:(r:any)=>calls.push(r),boardOnlineLive,
 recordingSync:{phase:'paused' as const,jobId:null,deviceId:pausedDevice,recordingId:32,receivedBytes:0,totalBytes:0,pauseRequested:false}});
const text=(n:any):string=>typeof n==='string'?n:(n.children??[]).map(text).join('');
const button=(label:string)=>renderer.root.findAllByType('button').find((n:any)=>text(n)===label);
act(()=>{renderer=create(<CompanionDashboard {...props()} />);});
assert.equal(button('继续同步').props.disabled,false,'the paused original can resume while its board capture continues');
act(()=>button('继续同步').props.onClick());
assert.equal(calls.at(-1).action,'deviceSyncRecordings');assert.equal(calls.at(-1).sessionId,'original-long');
assert.equal(calls.at(-1).deviceId,row.sourceDeviceId);
const baseline=snapshot;
for(const failure of ['host','missing_key','another_device','multiple','different_paused_device','storage_blocked','busy','online_owner']) {
 snapshot=structuredClone(baseline);pausedDevice=row.sourceDeviceId;busyAction=null;boardOnlineLive=null;
 if(failure==='host')snapshot.host.sessions[0].source='hostMicrophone';
 if(failure==='missing_key')snapshot.host.sessions[0].deviceRecordingKey=null;
 if(failure==='another_device')snapshot.device.deviceId='00:11:22:33:44:55';
 if(failure==='multiple'){const other=structuredClone(snapshot.host.sessions[0]);other.id='another-active';snapshot.host.sessions.push(other);}
 if(failure==='different_paused_device')pausedDevice='00:11:22:33:44:55';
 if(failure==='storage_blocked')snapshot.host.persistence.status='blocked';
 if(failure==='busy')busyAction='deviceConnect';
 if(failure==='online_owner')boardOnlineLive={state:'recording',durationMs:1000};
 act(()=>renderer.update(<CompanionDashboard {...props()} />));
 assert.equal(button('继续同步').props.disabled,true,failure);
}
snapshot=baseline;pausedDevice=row.sourceDeviceId;busyAction=null;boardOnlineLive=null;
act(()=>renderer.update(<CompanionDashboard {...props()} />));
act(()=>renderer.root.findAllByType('button').find((n:any)=>text(n).includes('采集与处理')).props.onClick());
assert.equal(button('同步原录音').props.disabled,false,'restored original has a usable entry before a cached native connection exists');
act(()=>button('同步原录音').props.onClick());
assert.equal(calls.at(-1).action,'deviceSyncRecordings');assert.equal(calls.at(-1).sessionId,'original-long');
assert.equal(calls.at(-1).deviceId,row.sourceDeviceId);assert.equal(row.status,'recording','a sync click never invents closure');
for(const failure of ['host','missing_key','another_device','multiple']) {
 const good=snapshot;snapshot=structuredClone(snapshot);
 if(failure==='host')snapshot.host.sessions[0].source='hostMicrophone';
 if(failure==='missing_key')snapshot.host.sessions[0].deviceRecordingKey=null;
 if(failure==='another_device')snapshot.device.deviceId='00:11:22:33:44:55';
 if(failure==='multiple'){const other=structuredClone(snapshot.host.sessions[0]);other.id='another-active';snapshot.host.sessions.push(other);}
 act(()=>renderer.update(<CompanionDashboard {...props()} />));
 assert.equal(button('同步原录音'),undefined,failure);assert.equal(button('同步录音库').props.disabled,true,failure);
 snapshot=good;
}
act(()=>renderer.unmount());
console.log('ORIGINAL_SYNC_UI_SOFTWARE_ONLY: restored same-device original entry and identity; host, missing key, foreign device and multiple active rows rejected');
