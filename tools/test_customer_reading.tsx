import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {CompanionTranscriptReview} from '../packages/ui/src/CompanionTranscriptReview';
import {CalendarTimeEditor} from '../packages/ui/src/CalendarTimeEditor';
import {seedCalendarTime,confirmedCalendarTime} from '../packages/ui/src/calendarTime';
import {libraryPreview} from '../packages/ui/src/libraryPreview';

// Customer-reported reading and navigation contracts. IPC is deliberately not
// provided: this suite cannot write a recording, call a provider or touch a board.
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};
const row=structuredClone(snapshot.host.sessions[0]);row.id='reading-fixture';row.source='importedTranscript';
row.title='出差准备';row.transcriptText='出发前检查身份证。';row.transcriptFinal=true;row.pendingReason=null;
row.meetingNotes=[{id:'note-one',text:'酒店在火车站附近',createdAt:'2026-10-27T00:00:00Z'}] as any;
const markdown='# 出差准备\n\n## 行动项\n- [ ] 随身包放充电线 (due: 2026-10-28 晚上)\n';
row.minutes={...row.minutes!,source:'userAuthored',quality:'final',markdown};
row.minutesByMode={offlineStore:{...row.minutesByMode.offlineStore!,source:'userAuthored',quality:'final',markdown}};
row.meetingMode='offlineStore';snapshot.host.sessions=[row];snapshot.host.selectedSessionId=row.id;
const before=JSON.stringify(snapshot);
assert.deepEqual(libraryPreview(row,'酒店'),{text:'酒店在火车站附近',label:'补充',target:'source'});
assert.match(libraryPreview(row,'随身包').text,/注明时间：2026-10-28 晚上/);
assert.doesNotMatch(libraryPreview(row,'随身包').text,/due:/);
assert.match(libraryPreview(row,'due:').text,/due:/,'literal stored syntax remains searchable');
assert.equal(libraryPreview(row,'出差准备').target,undefined,'title matches do not force a source detour');

const ambiguous=seedCalendarTime('2026-10-28 晚上');
assert.equal(ambiguous.date,'2026-10-28');assert.equal(ambiguous.time,'');
assert.equal(confirmedCalendarTime(ambiguous).ok,false,'prose must not acquire a guessed hour');
assert.equal(confirmedCalendarTime({...ambiguous,time:'20:00',zone:'offset',offset:'+08:00'}).ok,true);
assert.equal(seedCalendarTime('2026-10-28T20:00:00+08:00').time,'20:00');
assert.equal(confirmedCalendarTime(seedCalendarTime('2026-10-28')).ok,true,'date-only arrangements remain date-only');
let tree:any;const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(name:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===name);
act(()=>{tree=create(<CalendarTimeEditor value="2026-10-28 晚上" label="待办 1" disabled={false} onConfirm={()=>{throw Error('No time selected');}}/>);});
act(()=>button('确认日历时间').props.onClick());
assert.equal(tree.root.findByProps({'aria-label':'待办 1 日历时刻'}).props.value,'');
assert.equal(button('使用此日历时间').props.disabled,true);act(()=>tree.unmount());
act(()=>{tree=create(<CompanionTranscriptReview session={row} visible blocked={false} onUnsavedChange={()=>{}}/>);});
assert.match(text(tree.toJSON()),/导入原文/);assert.doesNotMatch(text(tree.toJSON()),/可对照原音|回听位置/);act(()=>tree.unmount());
act(()=>{tree=create(<CompanionTranscriptReview session={{...row,source:'boardDevice'}} visible blocked={false} onUnsavedChange={()=>{}}/>);});
assert.match(text(tree.toJSON()),/可对照原音/);act(()=>tree.unmount());
(globalThis as any).HTMLButtonElement=class {};
(globalThis as any).document={activeElement:null};
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>fn()};
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{}});
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});
assert.match(text(tree.toJSON()),/手写清单已保存/);
act(()=>tree.root.findByProps({'aria-label':'搜索标题、转写、补充或整理结果'}).props.onChange({target:{value:'酒店'}}));
act(()=>tree.root.findAllByType('button').find((n:any)=>n.props.className?.includes('ct-library-card')).props.onClick());
assert.equal(tree.root.findByProps({id:'ct-recording-text-review'}).props.hidden,false,'note result opens the source reading area');
act(()=>tree.unmount());assert.equal(JSON.stringify(snapshot),before,'reading does not rewrite durable source');
console.log('PASS customer reading: imported text identity, native-audio identity, authored checklist label, note-hit navigation, localized preview, literal search, explicit calendar time and unchanged durable input');

// A direct checklist copy uses saved native-prepared text, not another export
// dialog or a provider. Clipboard here is an isolated test endpoint.
const payload='- [ ] 随身包放充电线（注明时间：2026-10-28 晚上）';
let copied:string[]=[];
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{clipboard:{writeText:async(value:string)=>{copied.push(value);}}}});
const openCopy=async(preview:()=>Promise<any>)=>{
  act(()=>{tree=create(<CompanionDashboard {...props()} onPreviewMeetingExport={preview} onExportMeeting={async()=>{throw Error('Copy must not open a file dialog');}}/>);});
  act(()=>tree.root.findAllByType('button').find((n:any)=>n.props.className?.includes('ct-library-card')).props.onClick());
};
await openCopy(async()=>({contentHash:'a'.repeat(64),textContent:payload}));
await act(async()=>{await button('复制清单').props.onClick();});
assert.deepEqual(copied,[payload]);assert.match(text(tree.toJSON()),/清单已复制/);act(()=>tree.unmount());
(navigator as any).clipboard.writeText=async()=>{throw Error('Clipboard unavailable');};copied=[];
await openCopy(async()=>({contentHash:'a'.repeat(64),textContent:payload}));
await act(async()=>{await button('复制清单').props.onClick();});
assert.match(text(tree.toJSON()),/自动复制未完成/);assert.doesNotMatch(text(tree.toJSON()),/清单已复制/);
assert.equal(tree.root.findByProps({'aria-label':'已保存的清单文字'}).props.value,payload);act(()=>tree.unmount());
(navigator as any).clipboard.writeText=async(value:string)=>{copied.push(value);};
let finishPreview:(value:any)=>void=()=>{};
await openCopy(()=>new Promise(resolve=>{finishPreview=resolve;}));
act(()=>{button('复制清单').props.onClick();});
const updated=structuredClone(snapshot);updated.host.sessions[0].minutes!.markdown+='\n- [ ] 另一项';updated.host.sessions[0].minutesByMode.offlineStore!.markdown+='\n- [ ] 另一项';
act(()=>tree.update(<CompanionDashboard {...props()} snapshot={updated} onPreviewMeetingExport={async()=>({contentHash:'b'.repeat(64),textContent:'new'})}/>));
await act(async()=>{finishPreview({contentHash:'a'.repeat(64),textContent:payload});await Promise.resolve();});
assert.deepEqual(copied,[],'a changed source cannot write the previously prepared payload');act(()=>tree.unmount());
assert.equal(JSON.stringify(snapshot),before,'copy and fallback do not rewrite durable source');
console.log('PASS direct copy: native text/no file dialog, explicit unavailable fallback, changed-source exclusion and unchanged original');
