import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture,describeCompanionMeetingRecovery} from '../packages/core/src/companionV1';
import {meetingJourney} from '../packages/ui/src/CompanionJourney';
import {CompanionRecoveryCenter} from '../packages/ui/src/CompanionRecoveryCenter';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

// Component/action routing only. No real files, browser, device or service.
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
const row=structuredClone(snapshot.host.sessions[0]);
Object.assign(row,{id:'local-wav-pending',title:'本机等待恢复',source:'boardDevice',status:'captured',
 pendingReason:'needs_local_audio',audioStored:false,audioBytes:27,audioPath:'C:/fixture/planned.wav',
 transcriptText:'',transcriptFinal:false,minutes:null,minutesByMode:{offlineStore:null,onlineLive:null},
 deviceReclaimed:false,sourceDeviceId:'C8:92:FF:DD:3B:CA',deviceRecordingId:null,
 deviceRecordingKey:{deviceUid:'070707070707070707070707',formatEpoch:'000000000000000b',sessionId:'000000000000000d'},
 processingPolicy:'manual',recovery:{intent:'none',stage:'idle',requestedMeetingMode:'offlineStore',attemptCount:0,maxAttempts:3},
 chunks:[{id:'segment-0',path:'C:/fixture/original.opus',bytes:27,status:'sealed',durationMs:60,startedAt:null,stoppedAt:null}]});
const context={connected:false,deviceId:null,asrReady:true,minutesReady:true};
const expected={action:'meetingRestoreAudio',sessionId:row.id} as const;
assert.deepEqual(meetingJourney(row,context).request,expected);
assert.match(meetingJourney(row,context).title,/原音已收齐/);
assert.equal(describeCompanionMeetingRecovery(row)?.retryAction,null,'local wait never suggests ASR');
assert.equal(meetingJourney({...row,pendingReason:'needs_segments'},context).request?.action,'deviceConnect');
assert.throws(()=>applyCompanionV1ControlFixture(snapshot,expected),/本机原音与校验记录/,'fixture cannot pretend to rebuild audio');

snapshot.host.sessions=[row];snapshot.host.selectedSessionId=row.id;snapshot.host.activeSessionId=null;
snapshot.host.persistence={status:'ready'};snapshot.connected=false;snapshot.device.connected=false;snapshot.device.recording=false;snapshot.meeting.active=false;
const calls:any[]=[];const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const props:any={snapshot,blocked:false,savingBusy:false,asrReady:true,minutesReady:true,
 onControl:(request:any)=>calls.push(request),onSettings:()=>{},onWorkflow:()=>{}};
let view:any;act(()=>{view=create(<CompanionRecoveryCenter {...props}/>);});
const button=view.root.findAllByType('button').find((b:any)=>text(b)==='生成回听文件');assert.ok(button);
act(()=>button.props.onClick());assert.deepEqual(calls.pop(),expected);assert.deepEqual(calls,[]);
const trashed=structuredClone(snapshot);trashed.host.sessions[0].organization={revision:1,folder:'',tags:[],favorite:false,trashedAt:'2026-10-16T22:00:00+08:00'};
act(()=>view.update(<CompanionRecoveryCenter {...props} snapshot={trashed}/>));assert.equal(view.toJSON(),null);
act(()=>view.unmount());
act(()=>{view=create(<CompanionDashboard {...props} surface="windows" busyAction={null} error={null} onRefresh={()=>{}}/>);});
assert.match(text(view.toJSON()),/原音已保存，回听待生成/);
assert.match(text(view.toJSON()),/分段回收待确认/);
act(()=>view.root.findByProps({className:'ct-workflow-toggle'}).props.onClick());
const transcribe=view.root.findAllByType('button').find((b:any)=>text(b)==='转写');
assert.ok(transcribe&&transcribe.props.disabled,'a planned WAV path is not playable or transcribable audio');
assert.deepEqual(calls,[],'rendering never connects or processes audio');act(()=>view.unmount());
console.log('R65_LOCAL_AUDIO_COMPONENT_ROUTE: local recovery action, no premature ASR, honest raw/reclaim state, trash excluded; no GUI/device/cloud qualification');
