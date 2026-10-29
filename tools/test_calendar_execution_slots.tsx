import assert from 'node:assert/strict';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {retainCalendarSlots} from '../packages/ui/src/calendarSlotCarryover';
import {calendarCopyDetailsText} from '../packages/ui/src/CompanionCalendarCopies';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});snapshot.host.persistence={status:'ready'};
const row=snapshot.host.sessions[0];const markdown='## Action Items\n- [ ] 核对尺寸 (due: 2026-11-08T15:00:00+08:00前)\n- [ ] 核对包装 (due: 2026-11-07)';
Object.assign(row.minutesByMode.offlineStore!,{markdown,source:'userAuthored',quality:'final',status:'minutesReady'});
const original=JSON.stringify(snapshot),items=[{uid:'timed',title:'核对尺寸',text:'核对尺寸 (due: 2026-11-08T15:00:00+08:00前)',deadline:'2026-11-08T15:00:00+08:00前',status:'timed' as const},{uid:'day',title:'核对包装',text:'核对包装 (due: 2026-11-07)',deadline:'2026-11-07',status:'allDay' as const}];
const pending:{request:any;resolve:(x:any)=>void}[]=[],exports:any[]=[],unsaved:boolean[]=[];let tree:any;
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const buttons=(label:string)=>tree.root.findAllByType('button').filter((n:any)=>text(n)===label);
const button=(label:string)=>buttons(label)[0],field=(label:string)=>tree.root.findByProps({'aria-label':label});
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
 onSaveMeeting={async()=>{throw Error('execution slot must not alter the checklist');}} onUnsavedChange={value=>unsaved.push(value)}
 onPreviewMeetingExport={request=>request.calendarSlots?.length?new Promise(resolve=>pending.push({request,resolve})):Promise.resolve({contentHash:'a'.repeat(64),calendarItems:items})}
 onExportMeeting={async request=>{exports.push(request);return null;}}/>);});
await act(async()=>button('导出到日历').props.onClick());
act(()=>buttons('预留执行时段')[0].props.onClick());
assert.equal(field('日历事项 1 时段开始时刻').props.value,'');assert.equal(field('日历事项 1 时段结束时刻').props.value,'');assert.equal(button('使用此执行时段').props.disabled,true);assert.equal(unsaved.at(-1),true);
assert.match(text(tree.toJSON()),/旧版本 Type 不能保留执行时段/);
act(()=>button('取消').props.onClick());assert.equal(unsaved.at(-1),false);assert.equal(pending.length,0);
act(()=>buttons('预留执行时段')[0].props.onClick());
act(()=>field('日历事项 1 时段开始时刻').props.onChange({target:{value:'09:00'}}));
act(()=>field('日历事项 1 时段结束时刻').props.onChange({target:{value:'08:00'}}));
assert.equal(button('使用此执行时段').props.disabled,true,'end before start is refused');
act(()=>field('日历事项 1 时段结束时刻').props.onChange({target:{value:'16:00'}}));
assert.match(text(tree.toJSON()),/执行时段结束晚于清单截止时间/,'a valid but late arrangement warns rather than being silently changed');
act(()=>field('日历事项 1 时段结束时刻').props.onChange({target:{value:'10:00'}}));
assert.equal(button('使用此执行时段').props.disabled,false);
await act(async()=>button('使用此执行时段').props.onClick());
assert.equal(pending.length,1);assert.equal(button('保存日历文件').props.disabled,true,'pending preview cannot be saved');
assert.deepEqual(pending[0].request.calendarSlots,[{uid:'timed',slot:{start:'2026-11-08T09:00:00+08:00',end:'2026-11-08T10:00:00+08:00'}}]);
assert.match(text(tree.toJSON()),/清单截止：2026年11月8日 15:00前/);assert.match(text(tree.toJSON()),/执行时段：2026年11月8日 09:00/);
await act(async()=>pending[0].resolve({contentHash:'b'.repeat(64),calendarItems:items}));assert.equal(button('保存日历文件').props.disabled,false);
await act(async()=>button('保存日历文件').props.onClick());assert.equal(exports[0].expectedContentHash,'b'.repeat(64));assert.deepEqual(exports[0].calendarSlots,pending[0].request.calendarSlots);assert.equal(JSON.stringify(snapshot),original,'cancelled save cannot mutate deadline or persisted source');
assert.equal(button('修改执行时段').props.disabled,false,'cancelled native save returns exact draft');
act(()=>button('恢复仅按截止导出').props.onClick());assert.ok(buttons('预留执行时段').length===2);
const copy:any={schema:1,privacyEpoch:0,meetingMode:'offlineStore',savedAt:'2026-10-29',fileName:'测试.ics',fileSha256:'a'.repeat(64),contentHash:'b'.repeat(64),sourceTitle:row.title,sourceMarkdown:markdown,entries:[]};
const slot:any={uid:'timed',slot:{start:'2026-11-08T09:00:00+08:00',end:'2026-11-08T10:00:00+08:00'}};
const saved:any={...row,calendarCopyEpoch:0,calendarCopies:[copy],calendarSlotCopies:[{privacyEpoch:0,meetingMode:'offlineStore',contentHash:copy.contentHash,selections:[slot]}]};
copy.entries=[{uid:'timed',title:'核对尺寸',deadline:items[0].deadline,reminderMinutes:60}];
assert.match(calendarCopyDetailsText(copy,saved.calendarSlotCopies),/清单截止：2026年11月8日 15:00前/);
assert.match(calendarCopyDetailsText(copy,saved.calendarSlotCopies),/执行时段：2026年11月8日 09:00/);
assert.deepEqual(retainCalendarSlots(saved,'offlineStore',items)?.selections,[slot]);assert.equal(retainCalendarSlots({...saved,calendarCopyEpoch:1},'offlineStore',items),undefined);
assert.equal(retainCalendarSlots(saved,'onlineLive',items),undefined);assert.equal(retainCalendarSlots(saved,'offlineStore',[{...items[0],uid:'changed'},items[1]])?.notCarried,1);
assert.equal(retainCalendarSlots(saved,'offlineStore',[items[0],items[0],items[1]])?.notCarried,1);
act(()=>tree.unmount());const reopened=structuredClone(snapshot);Object.assign(reopened.host.sessions[0],saved);let carriedPreview:any;
act(()=>{tree=create(<CompanionDashboard snapshot={reopened} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}} onSaveMeeting={async()=>{throw Error('no source mutation');}}
 onPreviewMeetingExport={async request=>{if(request.calendarSlots?.length)carriedPreview=request;return {contentHash:'c'.repeat(64),calendarItems:items};}}
 onExportMeeting={async request=>{exports.push(request);return null;}}/>);});
await act(async()=>button('导出到日历').props.onClick());assert.deepEqual(carriedPreview.calendarSlots,[slot]);assert.match(text(tree.toJSON()),/执行时段：2026年11月8日 09:00/);
await act(async()=>button('保存日历文件（含提醒）').props.onClick());assert.deepEqual(exports.at(-1).calendarSlots,[slot]);assert.equal(exports.at(-1).expectedContentHash,'c'.repeat(64));
act(()=>tree.unmount());console.log('PASS explicit separate slot, invalid range/cancel, preserved deadline, reviewed export hash, reopened saved-slot carryover, snapshot detail, epoch and ambiguity protection');
