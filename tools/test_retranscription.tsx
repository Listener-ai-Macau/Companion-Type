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
session.transcriptUnrecognized=[{startMs:20000,endMs:35000}];
let captured:any=null;let tree:any;let previews=0;let unsaved=false;
const content=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(content).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>content(n)===label);
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
 onUnsavedChange={value=>{unsaved=value;}} onPreviewRetranscription={async id=>{assert.equal(id,session.id);previews++;return {text:'第二次识别',unrecognized:[{startMs:20000,endMs:35000}]};}}
 onSaveMeeting={async req=>{captured=req;return snapshot;}}/>);});
assert.ok(button('重新转写并对比'),'the action must be available in the main recording view');assert.equal(button('重新转写并对比').props.disabled,false);
assert.ok(content(tree.toJSON()).includes('部分时段未识别出文字'));assert.ok(content(tree.toJSON()).includes('20 秒–35 秒'));
await act(async()=>button('重新转写并对比').props.onClick());assert.equal(previews,1);assert.equal(unsaved,true);
assert.equal(tree.root.findByProps({'aria-label':'新转写结果'}).props.value,'第二次识别');assert.equal(session.transcriptText,'第一次识别');
assert.ok(content(tree.toJSON()).includes('新转写有部分时段没有识别出文字'));
await act(async()=>button('采用新文字').props.onClick());assert.equal(captured.sessionId,session.id);assert.equal(captured.transcriptReview.text,'第二次识别');
assert.equal(captured.transcriptReview.expectedTranscriptText,'第一次识别');assert.deepEqual(captured.transcriptReview.expectedUtterances,session.utterances);
assert.deepEqual(captured.transcriptReview.unrecognized,[{startMs:20000,endMs:35000}]);
assert.equal(session.transcriptText,'第一次识别');assert.equal(tree.root.findAllByProps({'aria-label':'新转写结果'}).length,0);
act(()=>tree.unmount());
session.transcriptReview={revision:1,editedAt:'now',sourceTranscriptText:session.transcriptText,
 sourceUtterances:structuredClone(session.utterances),text:'用户已有修订',utteranceEdits:[],speakerNames:[]};
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
 onPreviewRetranscription={async()=> ({text:'另一份文字',unrecognized:[]})} onSaveMeeting={async req=>{captured=req;return snapshot;}}/>);});
const timelineLabel=tree.root.findAllByType('label').find((n:any)=>content(n).includes('分段时间与说话人'));
const pdfTranscript=tree.root.findAllByType('label').find((n:any)=>content(n)==='录音文字');
act(()=>pdfTranscript.findByType('input').props.onChange({currentTarget:{checked:true}}));
assert.equal(timelineLabel.findByType('input').props.disabled,true,'an alternative transcript must not offer the previous timeline');
await act(async()=>button('重新转写并对比').props.onClick());
assert.equal(button('采用新文字').props.disabled,true,'existing human corrections cannot be silently replaced');
assert.ok(content(tree.toJSON()).includes('已有人工修订'));
assert.equal(session.transcriptReview.text,'用户已有修订');
act(()=>tree.unmount());console.log('PASS retranscription preview and explicit adoption preserve original input');
