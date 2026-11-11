import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {cardRecordingStatus} from '../packages/ui/src/cardRecordingStatus';
import {meetingJourney} from '../packages/ui/src/CompanionJourney';
import {CompanionHelp} from '../packages/ui/src/CompanionHelp';
import {CompanionSetup} from '../packages/ui/src/CompanionSetup';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

// Affected software state and real callback contracts only; no hardware claims.
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
const row=structuredClone(snapshot.host.sessions[0]);
Object.assign(row,{processingPolicy:'localTranscription',status:'captured',source:'boardDevice',
  transcriptFinal:false,transcriptText:'',audioStored:true,audioPath:'unit-card.wav',audioBytes:16044,
  pendingReason:'needs_transcription',captureIncomplete:false});
row.recovery={intent:'processMeeting',stage:'pendingTranscription',requestedMeetingMode:'offlineStore',attemptCount:0,maxAttempts:3};
const ready={saved:true,modelReady:true,automatic:true};
const context={connected:false,deviceId:null,asrReady:false,minutesReady:false,localAsrReady:true,autoLocalCard:true};
assert.equal(cardRecordingStatus(row,ready),'已接收，等待转写');
assert.equal(meetingJourney(row,context).request,undefined,'automatic card jobs do not require another generate click');
assert.equal(meetingJourney(row,{...context,localAsrReady:false}).destination,'settings');
assert.equal(cardRecordingStatus(row,{...ready,modelReady:false}),'已接收，待准备本机模型');
assert.equal(cardRecordingStatus(row,{...ready,automatic:false}),'已接收，自动转写已关闭');
assert.equal(meetingJourney(row,{...context,autoLocalCard:false}).request?.action,'meetingTranscribeAudio');
row.recovery.stage='transcribing';
assert.equal(cardRecordingStatus(row,{...ready,automatic:false}),'正在本机转写','a running task is not falsely shown as stopped');
assert.equal(meetingJourney(row,{...context,autoLocalCard:false}).destination,undefined);
row.recovery.stage='paused';row.recovery.lastError='test recognition failure';
assert.equal(cardRecordingStatus(row,ready),'转写未完成');
assert.equal(meetingJourney(row,context).request?.action,'meetingTranscribeAudio','a failed job keeps a useful explicit retry');
row.recovery.lastError=null;row.recovery.stage='complete';row.transcriptFinal=true;row.transcriptText='可以直接查看的文字';
assert.equal(cardRecordingStatus(row,ready),'文字已经准备好');
assert.equal(cardRecordingStatus(row,{...ready,saved:false}),'保存待确认');
row.processingPolicy='manual';assert.equal(cardRecordingStatus(row,ready),null,'existing manual rows keep their own lifecycle');

snapshot.source='firmware';snapshot.device.mode='windowsNative';snapshot.device.boardId=0x57424155;snapshot.device.firmwareVersion=66791;
const setup=renderToStaticMarkup(<CompanionSetup snapshot={snapshot} settings={{autoLocalCardTranscription:true,localAsrAvailable:false} as any}
  busy={false} recording={false} checking={false} onControl={()=>{throw new Error('reading starts nothing');}} onSettings={()=>{}}/>);
assert.match(setup,/准备一次，之后自动本机转写/);
assert.match(setup,/短按卡片实体键一次并松开，开始录音/);
assert.doesNotMatch(setup,/我已完成试录|我已找到并回听/);
let settings=0,library=0,device=0;
let tree:any;
act(()=>{tree=create(<CompanionHelp device={snapshot.device} onClose={()=>{}} onDevice={()=>device++} onLibrary={()=>library++} onDiagnostics={()=>{}} onSettings={()=>settings++}/>);});
const text=(node:any):string=>typeof node==='string'?node:(node.children??[]).map(text).join('');
for(const label of ['连接我的卡片','准备转写','查看我的记录']){
  const button=tree.root.findAllByType('button').find((node:any)=>text(node)===label);
  assert.ok(button,label);act(()=>button.props.onClick());
}
assert.deepEqual({settings,library,device},{settings:1,library:1,device:1});
const rendered=renderToStaticMarkup(<CompanionHelp device={snapshot.device} onClose={()=>{}} onDevice={()=>{}} onLibrary={()=>{}} onDiagnostics={()=>{}}/>);
for(const capability of ['重点列表','导出原音','MCP','按住说话','电脑会议','固件升级','备份恢复'])assert.ok(rendered.includes(capability),capability);
assert.match(rendered,/有疑问再回听/);
act(()=>tree.unmount());
for(const surface of ['windows','mobile'] as const){
  let dashboard:any;
  act(()=>{dashboard=create(<CompanionDashboard snapshot={snapshot} surface={surface} busyAction={null} error={null}
    productSettings={{asrProvider:'volcengine',autoLocalCardTranscription:true} as any} onControl={()=>{}} onRefresh={()=>{}} onSaveProductSettings={async()=>{}}/>);});
  const settingsButton=dashboard.root.findAllByType('button').find((node:any)=>text(node)==='设置与工具');
  act(()=>settingsButton.props.onClick());
  assert.equal(text(dashboard.toJSON()).includes('接收卡片录音后，自动在这台电脑转写'),surface==='windows',
    'desktop-only processing does not become a non-working mobile switch');
  act(()=>dashboard.unmount());
}
console.log('PASS_CARD_TO_TEXT: local-only lifecycle, model readiness, opt-out, retry, physical guide and real help destinations');
