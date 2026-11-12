import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {CompanionDashboard} from '../../../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../../../packages/core/src/companionV1';
import '../../../packages/ui/src/companionUi.css';
import '../../../packages/ui/src/companionDesign.css';
import '../../../packages/ui/src/companionDark.css';
import '../../../apps/windows/src/workspaceRefinement.css';

const original=createCompanionV1Fixture();
const row={id:'public-weekly-meeting',title:'产品周会 · 发布准备',status:'minutesReady',source:'importedTranscript',startedAt:'2026-11-12T01:00:00Z',durationMs:600000,
 meetingMode:'offlineStore',audioStored:false,audioBytes:0,chunks:[],transcriptFinal:true,transcriptText:'林悦：这周先完成会议详情，再集中检查从录音到交接的完整流程。\n陈明：交接文件要能看见范围，预算尚未确认。',
 retention:{audioCached:false,transcriptCached:true,minutesCached:true},bookmarks:[],noteRevision:1,meetingNotes:[
 {id:'one',kind:'followup',text:'我的发布跟进\n- [ ] 核对交接文件范围\n- [ ] 确认预算依据',bookmarkId:null,createdAt:'2026-11-12T01:00:00Z',updatedAt:'2026-11-12T01:00:00Z'},
 {id:'private-other',kind:'note',text:'另一次沟通的个人草稿，不应出现在单张交接中',bookmarkId:null,createdAt:'2026-11-12T01:00:00Z',updatedAt:'2026-11-12T01:00:00Z'}],
 minutes:{status:'minutesReady',quality:'final',source:'userEdited',generatedAt:'2026-11-12T01:00:00Z',markdown:'## Summary\n\n本周聚焦会议详情和完整交接，预算仍待确认。\n\n## Decisions\n\n- 先完成完整流程，再集中验收。\n\n## Action Items\n\n- [ ] 核对交接文件范围\n- [ ] 确认预算依据\n\n## Open Questions\n\n- 预算尚未确认。'},minutesByMode:{offlineStore:null,onlineLive:null},pendingReason:null};
const initial=createCompanionV1Fixture({...original,host:{...original.host,selectedSessionId:row.id,sessions:[row as any],persistence:{status:'ready'}} as any});
function View(){
 const[snapshot,setSnapshot]=useState(initial);
 const[fail,setFail]=useState(false);
 return <><p style={{padding:'8px 28px',margin:0,fontSize:11,background:'#eee5f5',color:'#49345e'}}>公开虚构会议 · 完整界面源码预演 · 不是原生/实卡或模型验收</p>
 <CompanionDashboard surface="windows" snapshot={snapshot} busyAction={null} error={null}
 productSettings={{asrProvider:'local-paraformer',localAsrAvailable:true,deepseekMinutesEnabled:false,deepseekApiKeySet:false,autoLocalCardTranscription:true,openaiAsrEndpoint:'',openaiAsrModel:'',deepseekBaseUrl:'',deepseekModel:'',bleCompress:false} as any}
 onControl={request=>setSnapshot(s=>applyCompanionV1ControlFixture(s,request))} onRefresh={()=>{}}
 onSaveMeeting={async request=>{if(fail)throw Error('公开故障用例：保存失败，修改保留。');const next=structuredClone(snapshot);const current=next.host.sessions[0];if(request.title!==undefined)current.title=request.title;setSnapshot(next);return next;}}
 onSaveNote={async request=>{if(fail)throw Error('公开故障用例：保存失败，修改保留。');const next=structuredClone(snapshot),current=next.host.sessions[0];current.noteRevision=(current.noteRevision??0)+1;const note={id:request.noteId,text:request.text??'',kind:request.kind??'note',references:request.references??[],bookmarkId:request.bookmarkId,createdAt:'2026-11-12T01:00:00Z',updatedAt:'2026-11-12T01:30:00Z'};current.meetingNotes=request.action==='delete'?current.meetingNotes?.filter(n=>n.id!==request.noteId):[...(current.meetingNotes??[]).filter(n=>n.id!==request.noteId),note];setSnapshot(next);return next;}}
 onPreviewMeetingExport={async request=>{const selection=request.contentSections;const current=snapshot.host.sessions[0];let text='';if(selection?.minutes)text+=current.minutes?.markdown??'';if(selection?.transcript)text+='\n'+current.transcriptText;for(const id of selection?.noteIds??[])text+='\n'+(current.meetingNotes??[]).find(n=>n.id===id)?.text;return{contentHash:'a'.repeat(64),textContent:text};}}
 onExportMeeting={async()=>{if(fail)throw Error('公开故障用例：文件保存失败，可重试。');return null;}}
 onCopyMeetingContent={async()=>({status:'copied'})}
 onShareMeetingContent={async()=>({status:'fileCopied',bytes:20,fileName:'公开会议.pdf'}) as any}
 />
 <button id="fixture-failure" style={{position:'fixed',bottom:4,right:4,fontSize:10}} onClick={()=>setFail(v=>!v)}>公开保存故障：{fail?'开':'关'}</button></>;
}
createRoot(document.getElementById('app')!).render(<View/>);
