// Developer-only adapter. No native export, network, model calls, or acceptance promotion.
import assert from 'node:assert/strict';
import {readFileSync,existsSync,readdirSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
const dir=process.env.COMPANION_PUBLIC_RUN_DIR;
if(!dir){console.log('SKIP cloud preview: set COMPANION_PUBLIC_RUN_DIR');process.exit(0);}
const json=(name:string)=>JSON.parse(readFileSync(join(dir,name),'utf8'));
const receipt=json('receipt.json');
const segments=json('transcript.json') as {id:string,start:number,end:number,text:string}[];
assert(segments.length&&segments.every(s=>typeof s.text==='string'&&Number.isFinite(s.start)&&Number.isFinite(s.end)&&s.start>=0&&s.end>=s.start));
const title='公开录音 · 云电脑离线结果预览';
const snap=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo',title,transcriptText:segments.map(s=>s.text).join('\n'),durationMs:Math.round(receipt.audio_seconds*1000)});
snap.host.persistence={status:'ready'};
const session=snap.host.sessions[0];
session.utterances=segments.map(s=>({text:s.text,startMs:Math.round(s.start*1000),endMs:Math.round(s.end*1000),approximateTiming:true}));
session.audioStored=false;
session.audioPath=null;
// Remove the synthetic fixture's cached audio/export provenance before showing real text.
session.chunks=[];
session.exportMarkdown='';
session.exportedAt=null;
const prior=session.minutesByMode?.offlineStore; assert(prior);
const blocks=existsSync(join(dir,'minutes-blocks.json'))?json('minutes-blocks.json'):[];
const groups=['decisions','actions','open_questions'] as const;
const bySource=new Map(segments.map(s=>[s.id,s.text]));
assert.equal(bySource.size,segments.length);
const hasMatchedOutput=receipt.status==='source_quotes_validated'&&blocks.length>0&&blocks.every((b:any)=>b.quotes_ok===true&&typeof b.candidate?.overview==='string'&&groups.every(k=>Array.isArray(b.candidate[k])&&b.candidate[k].every((x:any)=>typeof x?.text==='string'&&typeof x.quote==='string'&&x.quote.trim()&&bySource.get(x.support_id)?.includes(x.quote))));
const safe=(s:unknown)=>String(s??'').replace(/[\r\n]+/g,' ').trim();
const parts=(key:string)=>blocks.flatMap((b:any)=>b.candidate?.[key]??[]).map((x:any)=>'- '+safe(x.text)+(key==='actions'?
  (x.owner?' (owner: '+safe(x.owner)+')':'')+(x.deadline?' (due: '+safe(x.deadline)+')':'')+(x.condition?'；条件：'+safe(x.condition):''):''));
if(hasMatchedOutput){
  const evidence=blocks.flatMap((b:any)=>['decisions','actions','open_questions'].flatMap(k=>(b.candidate[k]??[]).map((x:any)=>`- [${safe(x.support_id)}] 「${safe(x.quote)}」`)));
  const markdown=['# '+title,'## Summary',...blocks.map((b:any)=>'- '+safe(b.candidate.overview)),'## Decisions',...parts('decisions'),'## Action Items',...parts('actions'),'## Open Questions',...parts('open_questions'),'## 原话核对',...evidence].join('\n');
  const draft={...prior,markdown,quality:'draft' as const,source:'llm_deepseek' as const,processing:undefined};
  session.minutes=draft;session.minutesByMode={...session.minutesByMode,offlineStore:draft};
}else{
  session.minutes=null;session.minutesByMode={};session.status='transcriptReady';session.exportMarkdown='';
}
const exportDir=process.env.COMPANION_PREVIEW_EXPORT_DIR;
if(exportDir)assert.deepEqual(readdirSync(exportDir),[], 'use a fresh isolated empty directory');
const exportName='meeting-minutes-review-draft.md';
let writes:string[]=[];let tree:any;
let reopenedBytes=0;
const render=()=> <CompanionDashboard surface="windows" snapshot={snap} busyAction={null} error={null}
  onRefresh={()=>{}} onControl={()=>{}} onExportMeeting={async request=>{
    writes.push(request.format);
    assert.equal(request.format,'markdown');
    assert.equal(request.sessionId,session.id);
    assert.equal(request.meetingMode,'offlineStore');
    // React sends request metadata, not bytes. Read the exact saved snapshot field
    // consumed by the original React minutes renderer; this is not the Tauri formatter.
    const markdown=snap.host.sessions.find(row=>row.id===request.sessionId)?.minutesByMode?.[request.meetingMode]?.markdown;
    assert(markdown);
    if(exportDir)writeFileSync(join(exportDir,exportName),markdown,{encoding:'utf8',flag:'wx'});
    return null;
  }}/>;
act(()=>{tree=create(render());});
const text=(n:any):string=>n==null||typeof n==='boolean'?'':typeof n==='string'?n:(n.children??[]).map(text).join('');
const by=(n:any,label:string)=>n.findAllByType('button').find((b:any)=>text(b)===label);
const nav=tree.root.findByProps({'aria-label':'主要功能'});
const library=tree.root.findByProps({'aria-label':'录音历史'});
act(()=>by(library,'全部').props.onClick());
const card=library.findAllByType('button').find((b:any)=>String(b.props.className??'').includes('ct-library-card')&&text(b).includes(title));
assert(card,'public artifact appears in the original library');
act(()=>card.props.onClick());
const meetingNav=tree.root.findByProps({'aria-label':'会议工作区'});
act(()=>by(meetingNav,'文字').props.onClick());
const sourcePane=tree.root.findByProps({id:'ct-recording-text'});
assert.equal(sourcePane.props.hidden,false);
assert(text(sourcePane).includes(segments[0].text.slice(0,20)), 'public ASR text visible in original transcript pane');
if(hasMatchedOutput){
  act(()=>by(meetingNav,'纪要').props.onClick());
  const result=tree.root.findByProps({id:'ct-recording-result'});
  assert.match(text(result),/待核/);
  assert(text(result).includes(safe(blocks[0].candidate.overview)));
}
act(()=>by(nav,'设置').props.onClick());
const settings=tree.root.findByProps({'aria-label':'设置与工具内容'});
assert.equal(by(settings,'清单 TXT').props.disabled,true);
assert.equal(by(settings,'日历待办 (.ics)').props.disabled,true);
if(hasMatchedOutput){
  assert.equal(by(settings,'Markdown').props.disabled,false);
  await act(async()=>by(settings,'Markdown').props.onClick());
  assert.deepEqual(writes,['markdown']);
} else assert.deepEqual(writes,[]);
if(exportDir&&hasMatchedOutput){
  assert.deepEqual(readdirSync(exportDir),[exportName],'no executable task or calendar files were written');
  const reopened=readFileSync(join(exportDir,exportName),'utf8');
  assert.equal(reopened,session.minutesByMode?.offlineStore?.markdown);
  assert(reopened.includes(safe(blocks[0].candidate.overview)));
  assert(reopened.includes('## 原话核对'));
  reopenedBytes=Buffer.byteLength(reopened);
}else if(exportDir)assert.deepEqual(readdirSync(exportDir),[]);
act(()=>tree.unmount());
console.log(JSON.stringify({receipt:receipt.status,segments:segments.length,blocks:blocks.length,renderedReviewDraft:hasMatchedOutput,validatedExportCallbackFormats:writes,reopenedBytes,scope:'original React UI and optional local test file via simulated bridge; no Tauri/device/semantic validation'}));
