import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {lastSavedCalendarReminders,retainCalendarReminders} from '../packages/ui/src/calendarReminderCarryover';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});snapshot.host.persistence={status:'ready'};
const markdown='## Action Items\n- [ ] 尺寸 (due: 2026-11-08T15:00:00+08:00前)\n- [ ] 包装 (due: 2026-11-07)\n- [ ] 不通知 (due: 2026-11-09T09:00:00+08:00)\n- [ ] 新增 (due: 2026-11-10T10:00:00+08:00)';
const row=snapshot.host.sessions[0];Object.assign(row.minutesByMode.offlineStore!,{markdown,source:'userAuthored',quality:'final',status:'minutesReady'});
const firstItems:any[]=[{uid:'timed',text:'尺寸 (due: 2026-11-08T15:00:00+08:00前)',title:'尺寸',deadline:'2026-11-08T15:00:00+08:00前',status:'timed'},
 {uid:'day',text:'包装 (due: 2026-11-07)',title:'包装',deadline:'2026-11-07',status:'allDay'},
 {uid:'none',text:'不通知 (due: 2026-11-09T09:00:00+08:00)',title:'不通知',deadline:'2026-11-09T09:00:00+08:00',status:'timed'},
 {uid:'new',text:'新增 (due: 2026-11-10T10:00:00+08:00)',title:'新增',deadline:'2026-11-10T10:00:00+08:00',status:'timed'}];
const copy:any={schema:2,privacyEpoch:0,meetingMode:'offlineStore',savedAt:'2026-10-29T05:18:53Z',fileName:'上次确认的文件.ics',fileSha256:'a'.repeat(64),contentHash:'b'.repeat(64),sourceTitle:row.title,sourceMarkdown:markdown,entries:[
 {uid:'timed',title:'尺寸',deadline:firstItems[0].deadline,reminderMinutes:1440},
 {uid:'day',title:'包装',deadline:'2026-11-07',reminderMinutes:null,reminderAt:'2026-11-07T09:00:00+08:00'},
 {uid:'none',title:'不通知',deadline:firstItems[2].deadline,reminderMinutes:null},
 {uid:'removed',title:'旧事项',deadline:'2026-11-01',reminderMinutes:30}]};
row.calendarCopies=[copy];const original=JSON.stringify(snapshot);let items=firstItems,tree:any;const requests:any[]=[],exports:any[]=[];
const hash=(r:any)=>createHash('sha256').update(JSON.stringify([r.format,r.calendarReminders])).digest('hex');
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label),field=(label:string)=>tree.root.findByProps({'aria-label':label});
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
 onPreviewMeetingExport:async(r:any)=>{requests.push(r);return {contentHash:hash(r),calendarItems:items,warning:'原生日历时间说明'};},
 onExportMeeting:async(r:any)=>{exports.push(r);return null;}});
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});await act(async()=>button('导出到日历').props.onClick());
assert.equal(field('日历事项 1 提醒').props.value,'1440');assert.equal(field('日历事项 2 提醒').props.value,'at');assert.equal(field('日历事项 3 提醒').props.value,'none');assert.equal(field('日历事项 4 提醒').props.value,'default','new item never receives old global defaults');
assert.match(text(tree.toJSON()),/最近保存记录带入3项逐项设置/);assert.match(text(tree.toJSON()),/上次文件中有1项提醒对应的事项已改变或不再导出/,'source notice survives completed native preview warning');
assert.match(text(tree.toJSON()),/2026年11月7日 09:00/);assert.equal(JSON.stringify(snapshot),original);
await act(async()=>button('保存日历文件（含提醒）').props.onClick());assert.equal(exports.length,1);assert.equal(exports[0].expectedContentHash,hash(exports[0]));assert.deepEqual(exports[0].calendarReminders,[
 {uid:'timed',reminder:{kind:'before',minutes:1440}},{uid:'day',reminder:{kind:'at',at:'2026-11-07T09:00:00+08:00'}},{uid:'none',reminder:{kind:'none'}}]);
assert.equal(field('日历事项 2 提醒').props.value,'at','native cancel returns exact inherited choice');
await act(async()=>field('日历事项 2 提醒').props.onChange({currentTarget:{value:'none'}}));await act(async()=>button('保存日历文件（含提醒）').props.onClick());assert.deepEqual(exports[1].calendarReminders?.find((s:any)=>s.uid==='day')?.reminder,{kind:'none'},'explicit current choice takes precedence over saved copy');
assert.equal(JSON.stringify(snapshot),original,'saving cancelled and manual reminder edits do not rewrite stored receipt');
snapshot=structuredClone(snapshot);snapshot.host.sessions[0].minutesByMode.offlineStore!.markdown=markdown.replace('2026-11-07)','2026-11-07T11:00:00+08:00)');
items=firstItems.map(i=>i.uid==='day'?{...i,uid:'changed-day',deadline:'2026-11-07T11:00:00+08:00',text:'包装 (due: 2026-11-07T11:00:00+08:00)',status:'timed'}:i);
act(()=>tree.update(<CompanionDashboard {...props()}/>));await act(async()=>button('导出到日历').props.onClick());
assert.equal(field('日历事项 1 提醒').props.value,'1440');assert.equal(field('日历事项 2 提醒').props.value,'default','same title/position with changed UID does not inherit absolute alarm');assert.equal(field('日历事项 3 提醒').props.value,'none');assert.match(text(tree.toJSON()),/上次文件中有2项提醒/);
const latest=requests.filter(r=>r.calendarReminders?.length).at(-1);assert.ok(!latest.calendarReminders.some((s:any)=>s.uid==='day'||s.uid==='changed-day'));
act(()=>tree.unmount());snapshot=JSON.parse(original);items=firstItems;act(()=>{tree=create(<CompanionDashboard {...props()}/>);});await act(async()=>button('导出到日历').props.onClick());assert.equal(field('日历事项 2 提醒').props.value,'at','fresh UI lifetime reads durable receipt, not temporary preview state');act(()=>tree.unmount());
assert.equal(lastSavedCalendarReminders({...row,calendarCopyEpoch:1},'offlineStore'),undefined);
assert.equal(lastSavedCalendarReminders(row,'onlineLive'),undefined);
const latestNone={...copy,entries:[{...copy.entries[0],reminderMinutes:null}]};assert.deepEqual(lastSavedCalendarReminders({...row,calendarCopies:[latestNone,copy]},'offlineStore')!.selections,[{uid:'timed',reminder:{kind:'none'}}],'latest explicit no alarm never falls back to older alarm');
const saved=lastSavedCalendarReminders(row,'offlineStore')!;assert.ok(!retainCalendarReminders({...saved,selections:[...saved.selections,saved.selections[0]]},firstItems)!.selections.some(s=>s.uid==='timed'),'ambiguous old UID never guessed');assert.ok(!retainCalendarReminders(saved,[...firstItems,firstItems[0]])!.selections.some(s=>s.uid==='timed'),'ambiguous current UID never guessed');assert.equal(JSON.stringify(row.calendarCopies),JSON.stringify([copy]));
console.log('PASS durable exact-UID reminder carryover across fresh UI, day absolute/1day/none retained, new/changed/removed/ambiguous/mode/epoch isolated, current edit wins, separate warning survives native re-preview, precise export hash and cancellation/source intact');
