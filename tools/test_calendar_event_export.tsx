import assert from 'node:assert/strict';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {savedExportPreview,SavedPreviewInterrupted} from '../packages/ui/src/savedExportPreview';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};
const row=snapshot.host.sessions[0];row.minutesByMode.offlineStore!.markdown='## 行动项\n- [ ] 带身份证 (due: 2026-10-28 晚上)';
row.minutesByMode.offlineStore!.quality='final';row.minutesByMode.offlineStore!.status='minutesReady';
row.minutes=row.minutes?{...row.minutes,markdown:row.minutesByMode.offlineStore!.markdown}:row.minutes;
const original=JSON.stringify(snapshot),hash='a'.repeat(64),exports:any[]=[],previews:any[]=[];
let warn=true,tree:any,releasePreview:any;
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
 onSaveMeeting:async()=>snapshot,
 onExportMeeting:async(request:any)=>{exports.push(request);return null;},
 onPreviewMeetingExport:async(request:any)=>{previews.push(request);if(releasePreview&&request.format==='calendar')return new Promise<any>(resolve=>{releasePreview=resolve;});return{contentHash:hash,warning:warn?'Unconfirmed saved time':null};}});
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label);
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});
await act(async()=>button('导出到日历').props.onClick());
assert.equal(exports.length,0,'unconfirmed native calendar time is disclosed before opening a save dialog');
assert.equal(previews[0].sessionId,row.id);assert.equal(previews[0].meetingMode,'offlineStore');
assert.match(text(tree.toJSON()),/Unconfirmed saved time/);
await act(async()=>button('取消导出').props.onClick());assert.equal(exports.length,0);
await act(async()=>button('导出到日历').props.onClick());
await act(async()=>button('先核对时间').props.onClick());
assert.ok(tree.root.findAllByProps({className:'ct-minutes-editor'}).length);assert.equal(exports.length,0);
act(()=>tree.unmount());
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});
await act(async()=>button('导出到日历').props.onClick());
await act(async()=>button('导出日程').props.onClick());
assert.deepEqual(exports[0],{sessionId:row.id,meetingMode:'offlineStore',format:'calendar',expectedContentHash:hash});
assert.match(text(tree.toJSON()),/已取消保存/);
warn=false;await act(async()=>button('导出到日历').props.onClick());assert.equal(exports.length,1);
await act(async()=>button('导出日程').props.onClick());assert.equal(exports.length,2);
assert.equal(exports[1].expectedContentHash,hash,'a fully confirmed result also binds the reviewed native content');
releasePreview=true;
await act(async()=>{button('导出到日历').props.onClick();button('导出到日历').props.onClick();});
const count=previews.length;assert.equal(exports.length,2);
await act(async()=>releasePreview({contentHash:hash,warning:null}));
assert.deepEqual(previews.slice(count).map(x=>x.format),['calendarreminder','calendarreminder30','calendarreminder60']);assert.equal(exports.length,2,'double-click cannot save before the reviewed choice');
await act(async()=>button('导出日程').props.onClick());assert.equal(exports.length,3);
releasePreview=true;
await act(async()=>{button('导出到日历').props.onClick();});
assert.ok(button('取消等待'));
await act(async()=>button('取消等待').props.onClick());
assert.match(text(tree.toJSON()),/已停止等待/);
assert.equal(button('导出到日历').props.disabled,false,'a stopped read-only wait releases the UI');
await act(async()=>releasePreview({contentHash:hash,warning:null}));
assert.equal(exports.length,3,'a late reply after cancellation must not open a save dialog');
const timed=savedExportPreview(()=>new Promise(()=>{}),15);
await assert.rejects(timed.result,(e:unknown)=>e instanceof SavedPreviewInterrupted&&/尚未开始保存或复制/.test(e.message));
act(()=>tree.unmount());assert.equal(JSON.stringify(snapshot),original);
console.log('PASS calendar pre-save review: parser/fingerprint, cancellation/timeout releases UI, late reply cannot export, duplicates and original preserved');

import {seedCalendarTime,confirmedCalendarTime} from '../packages/ui/src/calendarTime';
for(const value of ['2026年11月5日16:30','2026年11月5日 16:30']){
 const draft=seedCalendarTime(value);assert.equal(draft.expected,value);assert.equal(draft.date,'2026-11-05');assert.equal(draft.time,'16:30');
 assert.equal(draft.zone,'local');const chosen=confirmedCalendarTime({...draft,zone:'offset',offset:'+08:00'});
 assert.deepEqual(chosen,{ok:true,value:'2026-11-05T16:30:00+08:00',label:'2026-11-05 16:30（UTC+08:00）'});
}
const day=seedCalendarTime('2026年11月5日');assert.equal(day.timed,false);assert.equal(confirmedCalendarTime(day).ok,true);
for(const text of ['周五','下个月','11月5日','2026年2月29日','2026年11月5日25:00','2026年11月5日或6日','2026年11月5日之后再定'])assert.equal(seedCalendarTime(text).date,'');
console.log('PASS P636 calendar event route and explicit Chinese draft seeding; no guessed relative date or saved conversion');
