import assert from 'node:assert/strict';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {savedActions} from '../packages/ui/src/savedActions';
import {nativeActionParts} from '../packages/ui/src/actionMetadata';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};
const row=snapshot.host.sessions[0],id=row.id;
row.minutesByMode.offlineStore!.markdown='## Summary\n样品条件保持原文。\n\n## Action Items\n- [ ] 核对尺寸，未测完不要写通过 (due: 2026-11-08T15:00:00+08:00前)\n- [ ] 核对包装 (due: 2026-11-07)';
row.minutesByMode.offlineStore!.source='userAuthored';row.minutesByMode.offlineStore!.quality='final';row.minutesByMode.offlineStore!.status='minutesReady';
const original=row.minutesByMode.offlineStore!.markdown,originalTranscript=row.transcriptText,otherMode=JSON.stringify(row.minutesByMode.onlineLive);
let tree:any,failSave=false;const exports:any[]=[],saves:any[]=[];
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label);
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
 onPreviewMeetingExport:async(request:any)=>({contentHash:(request.format==='calendarreminder60'?'d':'a').repeat(64),calendarItems:savedActions(snapshot.host.sessions[0].minutesByMode.offlineStore!.markdown).map(a=>{
   const {body,metadata}=nativeActionParts(a.text);const deadline=metadata.find(m=>m.key==='due')!.value;
   return {text:a.text,title:body,deadline,status:deadline.includes('T')?'timed' as const:'allDay' as const};
 })}),
 onExportMeeting:async(request:any)=>{exports.push(request);return null;},
 onSaveMeeting:async(request:any)=>{
   saves.push(request);if(failSave)throw Error('保存冲突');
   assert.equal(request.expectedMarkdown,snapshot.host.sessions[0].minutesByMode.offlineStore!.markdown);
   snapshot=structuredClone(snapshot);snapshot.host.sessions[0].minutesByMode.offlineStore!.markdown=request.markdown;
   tree.update(<CompanionDashboard {...props()}/>);return snapshot;
 }});
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});
await act(async()=>button('导出到日历').props.onClick());
assert.match(text(tree.toJSON()),/将导出2项日程：0项附提醒，2项不提醒/);
const reminder=()=>tree.root.findAllByType('input').find((n:any)=>n.props.type==='checkbox'&&n.parent?.type==='label'&&text(n.parent).includes('提醒我'));
act(()=>reminder().props.onChange({currentTarget:{checked:true}}));
act(()=>tree.root.findByProps({'aria-label':'日历提醒时间'}).props.onChange({currentTarget:{value:'calendarreminder60'}}));
assert.match(text(tree.toJSON()),/将导出2项日程：1项附提醒，1项不提醒/);
await act(async()=>tree.root.findByProps({'aria-label':'日历事项 2 补充具体时刻'}).props.onClick());
assert.ok(tree.root.findByProps({'aria-label':'待办 2 日历时间'}));
assert.equal(tree.root.findByProps({'aria-label':'待办 2 日历日期'}).props.value,'2026-11-07');
assert.equal(tree.root.findByProps({'aria-label':'待办 2 指定时刻'}).props.checked,true);
assert.equal(tree.root.findByProps({'aria-label':'待办 2 日历时刻'}).props.value,'','no invented time');
act(()=>tree.root.findByProps({'aria-label':'待办 2 日历时刻'}).props.onChange({target:{value:'10:30'}}));
await act(async()=>button('使用此日历时间').props.onClick());
assert.equal(saves.length,0,'time confirmation remains an explicit unsaved draft');
failSave=true;await act(async()=>button('保存修改并返回日历预览').props.onClick());
assert.equal(exports.length,0);assert.equal(snapshot.host.sessions[0].minutesByMode.offlineStore!.markdown,original);
assert.match(text(tree.toJSON()),/未保存，草稿仍在/);
failSave=false;await act(async()=>button('保存修改并返回日历预览').props.onClick());
assert.match(text(tree.toJSON()),/将导出2项日程：2项附提醒，0项不提醒/);
assert.equal(tree.root.findByProps({'aria-label':'日历提醒时间'}).props.value,'calendarreminder60');
assert.equal(exports.length,0,'return re-previews; never silently exports');
assert.equal(savedActions(snapshot.host.sessions[0].minutesByMode.offlineStore!.markdown)[0].text,savedActions(original)[0].text);
assert.ok(snapshot.host.sessions[0].minutesByMode.offlineStore!.markdown.startsWith('## Summary\n样品条件保持原文。\n\n'));
assert.match(snapshot.host.sessions[0].minutesByMode.offlineStore!.markdown,/2026-11-07T10:30:00/);
await act(async()=>button('导出并设置提醒').props.onClick());
assert.deepEqual(exports[0],{sessionId:id,meetingMode:'offlineStore',format:'calendarreminder60',expectedContentHash:'d'.repeat(64)});
assert.equal(snapshot.host.sessions[0].transcriptText,originalTranscript);
assert.equal(JSON.stringify(snapshot.host.sessions[0].minutesByMode.onlineLive),otherMode);
act(()=>tree.unmount());
console.log('PASS native preview rows, exact second-item time edit, no guessed clock, failed-save draft retained, return with reminder choice, explicit export and source preservation');
