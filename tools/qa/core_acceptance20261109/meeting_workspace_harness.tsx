import React,{useState} from 'react';
import publicRecorded019f from './fixtures/public-recorded019f.json';
import {createRoot} from 'react-dom/client';
import {CompanionDashboard} from '../../../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../../../packages/core/src/companionV1';
import '../../../packages/ui/src/companionUi.css';
import '../../../packages/ui/src/notebookFoundation.css';

const original=createCompanionV1Fixture();
const row={id:'public-weekly-meeting',title:'产品周会 · 发布准备',status:'minutesReady',source:'importedTranscript',startedAt:'2026-11-12T01:00:00Z',durationMs:600000,
 meetingMode:'offlineStore',audioStored:false,audioPath:null,audioBytes:0,chunks:[],deviceRecordingId:null,deviceRecordingKey:null,sourceDeviceId:null,deviceTotalLength:null,deviceSha256:null,recorderControl:null,recorderControlUncertain:false,captureIncomplete:false,transcriptFinal:true,transcriptText:'林悦：这周先完成会议详情，再集中检查从录音到交接的完整流程。\n陈明：交接文件要能看见范围，预算尚未确认。',
 retention:{audioCached:false,transcriptCached:true,minutesCached:true},bookmarks:[],noteRevision:1,meetingNotes:[
 {id:'one',kind:'followup',text:'我的发布跟进\n- [ ] 核对交接文件范围\n- [ ] 确认预算依据',bookmarkId:null,createdAt:'2026-11-12T01:00:00Z',updatedAt:'2026-11-12T01:00:00Z'},
 {id:'private-other',kind:'note',text:'另一次沟通的个人草稿，不应出现在单张交接中',bookmarkId:null,createdAt:'2026-11-12T01:00:00Z',updatedAt:'2026-11-12T01:00:00Z'}],
 minutes:{status:'minutesReady',quality:'final',source:'userEdited',generatedAt:'2026-11-12T01:00:00Z',markdown:'## Summary\n\n本周聚焦会议详情和完整交接，预算仍待确认。\n\n## Decisions\n\n- 先完成完整流程，再集中验收。\n\n## Action Items\n\n- [ ] 核对交接文件范围\n- [ ] 确认预算依据\n\n## Open Questions\n\n- 预算尚未确认。'},minutesByMode:{offlineStore:null,onlineLive:null},pendingReason:null};
if(new URLSearchParams(location.search).has('without-minutes'))(row as any).minutes=null;
const initial={...original,host:{...original.host,selectedSessionId:row.id,sessions:[row as any],persistence:{status:'ready'}}} as any;
if(new URLSearchParams(location.search).has('notebook-library'))initial.host.sessions.push({...structuredClone(row),id:'public-other-meeting',title:'客户讨论 · 文字示例'});
if(new URLSearchParams(location.search).has('actual-public-019f')){initial.host.sessions=[structuredClone(publicRecorded019f)];initial.host.selectedSessionId=publicRecorded019f.id;}
if(new URLSearchParams(location.search).has('empty-library')){initial.host.sessions=[];initial.host.selectedSessionId=null;}
const connectionFixture=new URLSearchParams(location.search).get('connection');
if(connectionFixture){
 initial.source=connectionFixture==='stale'?'lastKnown':'firmware';initial.connected=initial.device.connected=['connected','stale','storage'].includes(connectionFixture);initial.device.mode='windowsNative';
 initial.device.connectionPhase=({connecting:'checking',reconnecting:'reconnecting',pairing:'pairingRequired',connected:'ready',stale:'ready',storage:'ready',failed:'idle'}as any)[connectionFixture]??'idle';
 if(connectionFixture==='failed')initial.lastControl={action:'deviceConnect',accepted:false,message:'public connection failed',payloadHex:'',characteristicUuid:''};
 if(connectionFixture==='storage')initial.host.persistence={status:'blocked'};
}
function View(){
 const[snapshot,setSnapshot]=useState(initial);
 const[fail,setFail]=useState(false);
 const[syncPhase,setSyncPhase]=useState('receiving');
 const[syncRecording,setSyncRecording]=useState(1);
 const withSync=new URLSearchParams(location.search).has('with-sync');
 return <><p style={{padding:'8px 28px',margin:0,fontSize:11,background:'#eee5f5',color:'#49345e'}}>公开虚构会议 · 完整界面源码预演 · 不是原生/实卡或模型验收</p>
 {withSync?<div id="fixture-sync-controls" aria-label="公开同步状态夹具" style={{position:'fixed',top:2,right:2,zIndex:10000,background:'#fff',color:'#111',fontSize:11}}>
   {['receiving','saving','reclaiming','paused','idle','blocked'].map(phase=><button key={phase} onClick={()=>setSyncPhase(phase)}>{phase}</button>)}
   <button onClick={()=>setSyncRecording(value=>value+1)}>next-recording</button>
 </div>:null}
 <CompanionDashboard surface="windows" snapshot={snapshot} busyAction={null} error={null}
 recordingSync={withSync?{jobId:['receiving','saving','reclaiming'].includes(syncPhase)?'public-sync':null,deviceId:'public-card',phase:syncPhase,recordingId:syncRecording,receivedBytes:25,totalBytes:100,pauseRequested:false,error:syncPhase==='blocked'?'公开同步故障':undefined} as any:null}
 onPauseSync={()=>setSyncPhase('paused')}
 productSettings={{asrProvider:'local-paraformer',localAsrAvailable:true,deepseekMinutesEnabled:false,deepseekApiKeySet:false,autoLocalCardTranscription:true,openaiAsrEndpoint:'',openaiAsrModel:'',deepseekBaseUrl:'',deepseekModel:'',bleCompress:false} as any}
 onControl={request=>setSnapshot(s=>applyCompanionV1ControlFixture(s,request))} onRefresh={()=>{}}
 onSaveMeeting={async request=>{if(fail)throw Error('公开故障用例：保存失败，修改保留。');const next=structuredClone(snapshot);const current=next.host.sessions.find(row=>row.id===request.sessionId);if(request.title!==undefined)current.title=request.title;setSnapshot(next);return next;}}
 onSaveNote={async request=>{if(fail)throw Error('公开故障用例：保存失败，修改保留。');const next=structuredClone(snapshot),current=next.host.sessions.find(row=>row.id===request.sessionId);current.noteRevision=(current.noteRevision??0)+1;const note={id:request.noteId,text:request.text??'',kind:request.kind??'note',references:request.references??[],bookmarkId:request.bookmarkId,createdAt:'2026-11-12T01:00:00Z',updatedAt:'2026-11-12T01:30:00Z'};current.meetingNotes=request.action==='delete'?current.meetingNotes?.filter(n=>n.id!==request.noteId):[...(current.meetingNotes??[]).filter(n=>n.id!==request.noteId),note];setSnapshot(next);return next;}}
 onPreviewMeetingExport={async request=>{const selection=request.contentSections;const current=snapshot.host.sessions.find(row=>row.id===request.sessionId);let text='';if(selection?.minutes)text+=current.minutes?.markdown??'';if(selection?.transcript)text+='\n'+current.transcriptText;for(const id of selection?.noteIds??[])text+='\n'+(current.meetingNotes??[]).find(n=>n.id===id)?.text;return{contentHash:'a'.repeat(64),textContent:text};}}
 onExportMeeting={async()=>{if(fail)throw Error('公开故障用例：文件保存失败，可重试。');return null;}}
 onCopyMeetingContent={async()=>({status:'copied'})}
 onShareMeetingContent={async()=>({status:'fileCopied',bytes:20,fileName:'公开会议.pdf'}) as any}
 />
 <button id="fixture-failure" style={{position:'fixed',bottom:4,right:4,fontSize:10}} onClick={()=>setFail(v=>!v)}>公开保存故障：{fail?'开':'关'}</button></>;
}
createRoot(document.getElementById('app')!).render(<View/>);
