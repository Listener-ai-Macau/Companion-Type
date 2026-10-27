import assert from 'node:assert/strict';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};
const row=snapshot.host.sessions[0];row.minutesByMode.offlineStore!.markdown='## 行动项\n- [ ] 咖啡豆不要深烘 (due: 2026-10-31T09:00:00+08:00)';
row.minutesByMode.offlineStore!.quality='final';row.minutesByMode.offlineStore!.status='minutesReady';
row.minutes=row.minutes?{...row.minutes,markdown:row.minutesByMode.offlineStore!.markdown}:row.minutes;
const original=JSON.stringify(snapshot),plainHash='a'.repeat(64),reminderHash='b'.repeat(64),hash30='c'.repeat(64),hash60='d'.repeat(64),exports:any[]=[],previews:any[]=[];
let dateOnly=false,tree:any,releasePreview:any,saveResult:any=null;
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
 onSaveMeeting:async()=>snapshot,
 onExportMeeting:async(request:any)=>{exports.push(request);return saveResult;},
 onPreviewMeetingExport:async(request:any)=>{
   previews.push(request);
   if(releasePreview)return new Promise<any>(resolve=>{releasePreview=resolve;});
   if(dateOnly&&request.format==='calendarreminder')throw Error('CALENDAR_TIME_REQUIRED:提醒需要具体时刻');
   return{contentHash:({calendarreminder:reminderHash,calendarreminder30:hash30,calendarreminder60:hash60}as Record<string,string>)[request.format]??plainHash,warning:dateOnly?'只有日期，保留全天日程':null};
 }});
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label);
const reminder=()=>tree.root.findAllByType('input').find((n:any)=>n.props.type==='checkbox'&&n.parent?.type==='label'&&text(n.parent).includes('提醒我'));
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});
await act(async()=>button('导出到日历').props.onClick());
assert.equal(exports.length,0,'no native dialog or reminder before reviewed choice');
assert.deepEqual(previews.map(x=>x.format),['calendar','calendarreminder','calendarreminder30','calendarreminder60']);
assert.equal(reminder().props.checked,false,'plain event remains default');
await act(async()=>button('导出日程').props.onClick());
assert.deepEqual(exports[0],{sessionId:row.id,meetingMode:'offlineStore',format:'calendar',expectedContentHash:plainHash});
await act(async()=>button('导出到日历').props.onClick());
act(()=>reminder().props.onChange({currentTarget:{checked:true}}));
await act(async()=>button('导出并设置提醒').props.onClick());
assert.deepEqual(exports[1],{sessionId:row.id,meetingMode:'offlineStore',format:'calendarreminder30',expectedContentHash:hash30});
assert.match(text(tree.toJSON()),/已取消保存/);
// Each explicitly selected lead uses the native hash for that exact alarm.
for(const [format,hash]of [['calendarreminder',reminderHash],['calendarreminder60',hash60]]as const){
 await act(async()=>button('导出到日历').props.onClick());
 act(()=>reminder().props.onChange({currentTarget:{checked:true}}));
 act(()=>tree.root.findByProps({'aria-label':'日历提醒时间'}).props.onChange({currentTarget:{value:format}}));
 await act(async()=>button('导出并设置提醒').props.onClick());
 assert.deepEqual(exports.at(-1),{sessionId:row.id,meetingMode:'offlineStore',format,expectedContentHash:hash});
}

await act(async()=>button('导出到日历').props.onClick());
await act(async()=>button('取消导出').props.onClick());assert.equal(exports.length,4);
dateOnly=true;await act(async()=>button('导出到日历').props.onClick());
assert.equal(reminder().props.disabled,true);assert.equal(reminder().props.checked,false);
assert.match(text(tree.toJSON()),/提醒需要具体时刻/);
await act(async()=>button('导出日程').props.onClick());assert.equal(exports[4].format,'calendar');
dateOnly=false;releasePreview=true;
await act(async()=>{button('导出到日历').props.onClick();button('导出到日历').props.onClick();});
const count=previews.length;assert.equal(exports.length,5);assert.ok(button('取消等待'));
await act(async()=>button('取消等待').props.onClick());
await act(async()=>releasePreview({contentHash:plainHash,warning:null}));
assert.equal(previews.length,count,'cancelled late preview never starts second preview');assert.equal(exports.length,5);
releasePreview=undefined;
await act(async()=>button('导出到日历').props.onClick());
const changed=structuredClone(snapshot);changed.host.sessions[0].minutesByMode.offlineStore!.markdown+='\n- [ ] 核对灯座';
act(()=>{tree.update(<CompanionDashboard {...props()} snapshot={changed}/>);});
assert.equal(button('导出并设置提醒'),undefined);assert.equal(button('导出日程'),undefined,'stale reviewed choice cannot be used with changed saved source');

act(()=>tree.unmount());saveResult={path:'C:/fictional-only/checklist.ics'};
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});
await act(async()=>button('导出到日历').props.onClick());
act(()=>reminder().props.onChange({currentTarget:{checked:true}}));
await act(async()=>button('导出并设置提醒').props.onClick());
assert.match(text(tree.toJSON()),/核对是否已导入/);
assert.doesNotMatch(text(tree.toJSON()),/文件尚未导入/);
assert.match(text(tree.toJSON()),/把日程文件放进常用日历/);
act(()=>tree.unmount());assert.equal(JSON.stringify(snapshot),original);

console.log('PASS explicit calendar/reminder choice, independent native hashes, date-only no guessed alarm, cancelled/late duplicate guard, stale saved source and original unchanged');
