import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { CompanionRecoveryCenter } from '../packages/ui/src/CompanionRecoveryCenter';
const snapshot = applyCompanionV1ControlFixture(createCompanionV1Fixture(), { action: 'meetingLoadDemo' });
const base = snapshot.host.sessions[0];
const raw = { ...structuredClone(base), id:'saved',title:'已保存音频',status:'captured' as const,
  transcriptText:'',transcriptFinal:false,minutes:null,minutesByMode:{offlineStore:null,onlineLive:null},
  pendingReason:'needs_transcription' as const,audioPath:'C:/fixture/audio.wav',audioStored:true,audioBytes:1000,
  recovery:{intent:'none' as const,stage:'idle' as const,requestedMeetingMode:'offlineStore' as const,attemptCount:0,maxAttempts:3} };
const waiting = { ...structuredClone(raw),id:'pending',title:'等设备录音',source:'boardDevice' as const,audioPath:null,audioStored:false,audioBytes:0,
  pendingReason:'needs_device_sync' as const,sourceDeviceId:'AA:BB:CC:DD:EE:FF' };
snapshot.host.sessions=[raw,waiting]; snapshot.device.connected=false;
snapshot.host.sessions[0].captureIncomplete=true;
const requests:any[]=[];
const props:any={snapshot,blocked:false,savingBusy:false,asrReady:true,minutesReady:true,
  onControl:(r:any)=>requests.push(r),onSettings:()=>{},onWorkflow:()=>{}};
let renderer:any; act(()=> { renderer=create(<CompanionRecoveryCenter {...props} />); });
assert.ok(renderer.root.findAll(n=>n.props.role==='alert').some(n=>n.children.join('').includes('末尾可能缺失')));
const text=(n:any):string=>typeof n==='string'?n:(n.children??[]).map(text).join('');
const button=(label:string)=> { const n=renderer.root.findAllByType('button').find((n:any)=>text(n)===label || text(n).startsWith(label)); assert.ok(n,label); return n; };
act(()=>button('转写已保存的片段').props.onClick());
assert.deepEqual(requests.pop(),{action:'meetingTranscribeAudio',sessionId:'saved'});
act(()=>button('连接来源设备').props.onClick());
assert.deepEqual(requests.pop(),{action:'deviceConnect',deviceId:waiting.sourceDeviceId});
snapshot.device.connected=true;snapshot.device.deviceId=waiting.sourceDeviceId;
act(()=>renderer.update(<CompanionRecoveryCenter {...props} snapshot={structuredClone(snapshot)} />));
act(()=>button('同步这台设备').props.onClick());
assert.deepEqual(requests.pop(),{action:'deviceSyncRecordings',deviceId:waiting.sourceDeviceId});
snapshot.host.persistence={status:'unsaved',message:'受控保存失败',recoveryPath:null};
act(()=>renderer.update(<CompanionRecoveryCenter {...props} snapshot={structuredClone(snapshot)} />));
assert.equal(button('转写已保存的片段').props.disabled,true);
act(()=>button('重试保存').props.onClick());assert.deepEqual(requests.pop(),{action:'hostRetrySave'});
snapshot.host.persistence={status:'ready',message:null,recoveryPath:null};
const noSpeech={...structuredClone(raw),id:'no-speech',captureIncomplete:false,pendingReason:'no_speech_detected' as const,
  recovery:{intent:'processMeeting' as const,stage:'paused' as const,requestedMeetingMode:'offlineStore' as const,
    attemptCount:1,maxAttempts:3,retryStage:'transcription' as const}};
snapshot.host.sessions=[noSpeech];
act(()=>renderer.update(<CompanionRecoveryCenter {...props} snapshot={structuredClone(snapshot)} />));
assert.match(text(renderer.toJSON()),/未识别到人声.*原录音已保留/);
act(()=>button('检查后重试转写').props.onClick());
assert.deepEqual(requests.pop(),{action:'meetingTranscribeAudio',sessionId:'no-speech'});
snapshot.host.sessions=[raw,waiting];
snapshot.host.sessions=[...snapshot.host.sessions, {...raw,id:'third'}, {...raw,id:'fourth'}];
act(()=>renderer.update(<CompanionRecoveryCenter {...props} snapshot={structuredClone(snapshot)} blocked />));
assert.equal(button('转写已保存的片段').props.disabled,true);
assert.equal(renderer.root.findAllByType('li').length,3);
act(()=>button('查看全部 4 条').props.onClick());assert.equal(renderer.root.findAllByType('li').length,4);
act(()=>renderer.unmount());
console.log('PASS React recovery-center state and exact action routing; GUI/device NOT_RUN');
