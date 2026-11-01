import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

(globalThis as any).document={activeElement:null,getElementById:()=>null};
(globalThis as any).HTMLElement=class {};
(globalThis as any).HTMLButtonElement=class extends HTMLElement {};
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;}};
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
const session=structuredClone(snapshot.host.sessions[0]);
Object.assign(session,{id:'damaged-device-audio',title:'合成损坏录音',source:'boardDevice',status:'captured',
  pendingReason:'needs_transcription',audioStored:true,audioBytes:32044,audioPath:'C:/synthetic/recording.wav',
  retention:{...session.retention,audioCached:true},deviceReclaimed:false,sourceDeviceId:'C8:92:FF:DD:3B:CA',deviceRecordingId:null,
  deviceRecordingKey:{deviceUid:'070707070707070707070707',formatEpoch:'000000000000000b',sessionId:'000000000000000d'},
  processingPolicy:'manual',transcriptText:'',transcriptFinal:false,minutes:null,minutesByMode:{offlineStore:null,onlineLive:null},
  recovery:{intent:'none',stage:'idle',requestedMeetingMode:'offlineStore',attemptCount:0,maxAttempts:3}});
snapshot.host.sessions=[session];snapshot.host.selectedSessionId=session.id;
const calls:any[]=[];const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const props:any={snapshot,surface:'windows',busyAction:null,error:null,onRefresh:()=>{},onControl:(request:any)=>calls.push(request),
  onPrepareAudio:async()=>{throw new Error('录音文件不完整或格式暂不支持，无法回听；已有文字和纪要仍可查看。');}};
let view:any;await act(async()=>{view=create(<CompanionDashboard {...props}/>);});
const playback=view.root.findAllByType('button').find((b:any)=>b.props['aria-controls']==='ct-recording-playback');
assert.ok(playback&&!playback.props.disabled,'saved synthetic recording should offer playback');
await act(async()=>{playback.props.onClick();await Promise.resolve();});
assert.match(text(view.toJSON()),/无法回听/);
const repair=view.root.findAllByType('button').find((b:any)=>text(b)==='尝试恢复回听文件');
assert.ok(repair,'damaged device playback must offer the existing local repair action');
act(()=>repair.props.onClick());assert.deepEqual(calls.pop(),{action:'meetingRestoreAudio',sessionId:session.id});
act(()=>view.unmount());
const host=structuredClone(session);host.id='synthetic-host-audio';host.source='hostMicrophone';host.deviceRecordingKey=null;host.sourceDeviceId=null;
snapshot.host.sessions=[host];snapshot.host.selectedSessionId=host.id;
await act(async()=>{view=create(<CompanionDashboard {...props}/>);});
const hostPlayback=view.root.findAllByType('button').find((b:any)=>b.props['aria-controls']==='ct-recording-playback');
await act(async()=>{hostPlayback.props.onClick();await Promise.resolve();});
assert.match(text(view.toJSON()),/无法回听/);
assert.equal(view.root.findAllByType('button').some((b:any)=>text(b)==='尝试恢复回听文件'),false,'host audio must not offer device-segment recovery');
act(()=>view.unmount());
console.log('PASS damaged device playback exposes targeted local audio recovery');
