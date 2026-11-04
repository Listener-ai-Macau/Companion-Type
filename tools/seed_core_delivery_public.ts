import {readFileSync,writeFileSync,statSync} from 'node:fs';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src';
const base='E:/CodexData/Companion/pretrained-route-selection-20261104';
const cases=JSON.parse(readFileSync(base+'/inference-audio-only.json','utf8'));
const records=Array.isArray(cases)?cases:cases.meetings??cases.cases;
const input=records.find((row:any)=>row.meeting==='20200708_L_R002S01C01');
if(!input)throw Error('Frozen public input unavailable');
const output=JSON.parse(readFileSync(base+'/cpu-new-meeting-baseline-r1/native/model-output.json','utf8'));
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
const row=snapshot.host.sessions[0];
Object.assign(row,{id:'public-core36',title:'公开会议 · 核对与保存测试',source:'hostMicrophone',
  status:'transcribed',durationMs:Math.round(input.audioSeconds*1000),audioPath:input.audio,
  audioBytes:statSync(input.audio).size,audioStored:true,chunks:[],sourceDeviceId:null,deviceRecordingId:null,
  deviceRecordingKey:null,recorderControl:null,recorderControlUncertain:false,captureIncomplete:false,
  transcriptText:output.text,transcriptFinal:true,utterances:output.utterances.map((item:any)=>({...item,approximateTiming:true})),
  transcriptReview:null,minutes:null,minutesByMode:{},pendingReason:null,exportMarkdown:'',
  recovery:{intent:'none',stage:'idle',attemptCount:0,maxAttempts:3,requestedMeetingMode:'',retryStage:'',lastError:null}});
row.retention.audioCached=true;row.retention.transcriptCached=true;row.retention.minutesCached=false;
writeFileSync('E:/CodexData/Companion/core-meeting-delivery-20261104/public-sessions.json',JSON.stringify([row],null,2));
console.log('Prepared public model output for an isolated software check; no inference, score reference or user recording used.');
