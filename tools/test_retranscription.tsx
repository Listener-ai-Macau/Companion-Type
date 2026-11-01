import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};
const session=snapshot.host.sessions[0];snapshot.host.selectedSessionId=session.id;
session.status='transcribed';session.source='importedAudio';session.audioPath='C:/test/meeting.wav';session.audioStored=true;session.audioBytes=10000;session.retention.audioCached=true;
session.transcriptText='第一次识别';session.transcriptFinal=true;session.utterances=[{text:'第一次识别',startMs:0,endMs:1200,speaker:null}];
let captured:any=null;let tree:any;let previews=0;let unsaved=false;
const content=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(content).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>content(n)===label);
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
 onUnsavedChange={value=>{unsaved=value;}} onPreviewRetranscription={async id=>{assert.equal(id,session.id);previews++;return '第二次识别';}}
 onSaveMeeting={async req=>{captured=req;return snapshot;}}/>);});
const open=tree.root.findAllByType('button').find((n:any)=>content(n).includes('更多录音与处理操作'));
act(()=>open.props.onClick());assert.ok(button('重新转写并对比'));assert.equal(button('重新转写并对比').props.disabled,false);
await act(async()=>button('重新转写并对比').props.onClick());assert.equal(previews,1);assert.equal(unsaved,true);
assert.equal(tree.root.findByProps({'aria-label':'新转写结果'}).props.value,'第二次识别');assert.equal(session.transcriptText,'第一次识别');
await act(async()=>button('采用新文字').props.onClick());assert.equal(captured.sessionId,session.id);assert.equal(captured.transcriptReview.text,'第二次识别');
assert.equal(captured.transcriptReview.expectedTranscriptText,'第一次识别');assert.deepEqual(captured.transcriptReview.expectedUtterances,session.utterances);
assert.equal(session.transcriptText,'第一次识别');assert.equal(tree.root.findAllByProps({'aria-label':'新转写结果'}).length,0);
act(()=>tree.unmount());
session.transcriptReview={revision:1,editedAt:'now',sourceTranscriptText:session.transcriptText,
 sourceUtterances:structuredClone(session.utterances),text:'用户已有修订',utteranceEdits:[],speakerNames:[]};
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
 onPreviewRetranscription={async()=> '另一份文字'} onSaveMeeting={async req=>{captured=req;return snapshot;}}/>);});
act(()=>tree.root.findAllByType('button').find((n:any)=>content(n).includes('更多录音与处理操作')).props.onClick());
await act(async()=>button('重新转写并对比').props.onClick());
assert.equal(button('采用新文字').props.disabled,true,'existing human corrections cannot be silently replaced');
assert.ok(content(tree.toJSON()).includes('已有人工修订'));
assert.equal(session.transcriptReview.text,'用户已有修订');
act(()=>tree.unmount());console.log('PASS retranscription preview and explicit adoption preserve original input');
