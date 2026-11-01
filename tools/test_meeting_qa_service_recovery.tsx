import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';

(globalThis as any).document={activeElement:null,getElementById:()=>null};
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;}};
(globalThis as any).HTMLElement=class {};(globalThis as any).HTMLButtonElement=class extends HTMLElement {};
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};
const row=snapshot.host.sessions[0];Object.assign(row,{id:'qa-recovery',title:'虚构会议',source:'importedTranscript',
  status:'transcribed',transcriptText:'张三周五发报价。',transcriptFinal:true,audioPath:null,audioBytes:0,audioStored:false,
  sourceDeviceId:null,deviceRecordingId:null,deviceRecordingKey:null,recorderControl:null,recorderControlUncertain:false,
  chunks:[],pendingReason:null,captureIncomplete:false});row.retention.audioCached=false;
snapshot.host.sessions=[row];snapshot.host.selectedSessionId=row.id;
let sent:any;const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');let tree:any;
await act(async()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null}
  onRefresh={()=>{}} onControl={()=>{}} onAskMeetings={async(question,ids)=>{sent={question,ids};return {
    items:[{text:'张三周五发报价',citation:{sessionId:row.id,title:row.title,quote:'张三周五发报价'}}],
    totalChunks:3,completedChunks:1,incomplete:true,cancelled:false,stopReason:'AI 服务暂时不可用，请检查网络或稍后重试。',
  };}}/>);});
act(()=>tree.root.findAllByType('button').find((n:any)=>n.props.className?.includes('ct-library-card')).props.onClick());
const question=tree.root.findByProps({'aria-label':'录音问题'});
act(()=>question.props.onChange({target:{value:'谁发报价？'}}));
const ask=tree.root.findAllByType('button').find((n:any)=>text(n)==='提问');assert.equal(ask.props.disabled,false);
await act(async()=>{await ask.props.onClick();});
assert.deepEqual(sent,{question:'谁发报价？',ids:['qa-recovery']});
const result=tree.root.findByProps({'aria-label':'录音问答结果'});const rendered=text(result);
assert.match(rendered,/AI 服务暂时不可用/);assert.match(rendered,/已查询 1\/3 段/);
assert.match(rendered,/张三周五发报价/);assert.match(rendered,/查看原文/);
act(()=>tree.unmount());console.log('PASS partial meeting answer, source and actionable service error remain visible');
