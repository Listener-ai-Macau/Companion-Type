import assert from 'node:assert/strict';
import React from 'react';
import {create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
function make(configured:boolean, incomplete:boolean, hasAudio=true, failure=false, noSpeech=false){
 const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingStart',sessionId:'fictional'}); snapshot.host.persistence={status:'ready'}; snapshot.meeting.active=false;
 const row=snapshot.host.sessions.find(x=>x.id==='fictional')!;
 Object.assign(row,{source:'hostMicrophone',status:'captured',audioPath:'E:/fictional.wav',audioBytes:hasAudio?32044:0,audioStored:hasAudio,captureIncomplete:incomplete,processingPolicy:'manual',pendingReason:noSpeech?'no_speech_detected':failure?'recovery_paused':'needs_transcription',transcriptText:'',transcriptFinal:false,minutes:null,minutesByMode:{}}); row.retention.audioCached=true;
 row.recovery={intent:'processMeeting',requestedMeetingMode:'offlineStore',stage:failure?'paused':'idle',attemptCount:1,maxAttempts:3,lastError:failure?'ASR provider returned 503 Service Unavailable':null,captureReviewConfirmed:failure};
 const requests:any[]=[];
 const settings:any={asrProvider:'openai',openaiAsrApiKeySet:configured,openaiAsrEndpoint:'',openaiAsrModel:'',deepseekBaseUrl:'',deepseekModel:'',deepseekMinutesEnabled:false,bleCompress:false,defaultMeetingMode:'offlineStore'};
 const tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} productSettings={settings} onRefresh={()=>{}} onControl={x=>requests.push(x)}/>);
 return {tree,requests};
}
for(const failure of [false,true]){
 const {tree,requests}=make(true,true,true,failure); const area=tree.root.findByProps({id:'ct-saved-recording-workspace'}); const journey=area.findByProps({'aria-label':'这条录音的下一步'});
 assert.equal(journey.findAllByType('button').length,0,'the same transcription action should be offered once');
 const buttons=area.findAllByType('button').filter(b=>text(b).includes('片段转文字')); assert.equal(buttons.length,1); assert.equal(buttons[0].props.disabled,false); buttons[0].props.onClick(); assert.equal(requests.at(-1).action,'meetingTranscribeAudio');
 assert.match(text(journey),failure?/发送到你配置的服务/:/录音曾意外中断/); tree.unmount();
}
{
 const {tree}=make(false,true); const area=tree.root.findByProps({id:'ct-saved-recording-workspace'}); const journey=area.findByProps({'aria-label':'这条录音的下一步'}); assert.match(text(journey),/配置转写服务/); assert.equal(journey.findAllByType('button').length,1);tree.unmount();
}
{
 const {tree}=make(true,true,false); const area=tree.root.findByProps({id:'ct-saved-recording-workspace'}); const journey=area.findByProps({'aria-label':'这条录音的下一步'}); assert.match(text(journey),/尝试恢复录音/); assert.equal(journey.findAllByType('button').length,1);tree.unmount();
}
{
 const {tree,requests}=make(true,false); const area=tree.root.findByProps({id:'ct-saved-recording-workspace'}); const main=area.findAllByType('button').find(b=>text(b)==='转文字'); assert.ok(main); main.props.onClick(); assert.equal(requests.at(-1).action,'meetingTranscribeAudio'); tree.unmount();
}
{
 const {tree,requests}=make(true,false,true,true,true); const area=tree.root.findByProps({id:'ct-saved-recording-workspace'}); const journey=area.findByProps({'aria-label':'这条录音的下一步'}); const retry=journey.findAllByType('button'); assert.equal(retry.length,1); assert.match(text(retry[0]),/检查后重试转写/); retry[0].props.onClick(); assert.equal(requests.at(-1).action,'meetingTranscribeAudio'); tree.unmount();
}
console.log('PASS single transcription entry; configuration, failure and recovery retained');


