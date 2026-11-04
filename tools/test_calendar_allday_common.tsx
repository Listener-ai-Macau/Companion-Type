import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {CalendarAllDayReminders} from '../packages/ui/src/CalendarAllDayReminders';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});snapshot.host.persistence={status:'ready'};
const markdown='## Summary\n条件保持。\n\n## Action Items\n- [ ] 包装 (due: 2026-11-07)\n- [ ] 签字，未完成不要写通过 (due: 2026-11-09前)\n- [ ] 不需通知 (due: 2026-11-10)\n- [ ] 尺寸 (due: 2026-11-08T15:00:00+08:00前)\n- [x] 历史事项 (due: 2026-11-06)';
Object.assign(snapshot.host.sessions[0].minutesByMode.offlineStore!,{markdown,source:'userAuthored',quality:'final',status:'minutesReady'});
const items:any[]=[
 {uid:'a',text:'包装 (due: 2026-11-07)',title:'包装',deadline:'2026-11-07',status:'allDay'},
 {uid:'b',text:'签字，未完成不要写通过 (due: 2026-11-09前)',title:'签字，未完成不要写通过',deadline:'2026-11-09前',status:'allDay'},
 {uid:'c',text:'不需通知 (due: 2026-11-10)',title:'不需通知',deadline:'2026-11-10',status:'allDay'},
 {uid:'d',text:'尺寸 (due: 2026-11-08T15:00:00+08:00前)',title:'尺寸',deadline:'2026-11-08T15:00:00+08:00前',status:'timed'},
 {uid:'e',text:'[x] 历史事项',title:'历史事项',deadline:'2026-11-06',status:'completed'}];
const original=JSON.stringify(snapshot),exports:any[]=[],requests:any[]=[],dirty:boolean[]=[],pending:any[]=[];let hold=false,tree:any;
const hash=(request:any)=>createHash('sha256').update(JSON.stringify(request.calendarReminders??[])).digest('hex');
const preview=async(request:any)=>{requests.push(request);return hold?new Promise(resolve=>pending.push({request,resolve})):({contentHash:hash(request),calendarItems:items});};
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label),field=(label:string)=>tree.root.findByProps({'aria-label':label});
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
 onSaveMeeting={async()=>{throw Error('reminder must not edit deadline');}} onUnsavedChange={value=>dirty.push(value)} onPreviewMeetingExport={preview} onExportMeeting={async request=>{exports.push(request);return null;}}/>);});
await act(async()=>button('导出到日历').props.onClick());
await act(async()=>field('日历事项 3 提醒').props.onChange({currentTarget:{value:'none'}}));
await act(async()=>field('日历事项 4 提醒').props.onChange({currentTarget:{value:'60'}}));
const beforeRequests=requests.length;
const open=()=>act(()=>button('全天事项：一次设置当天提醒时刻').props.onClick());
const fill=()=>{act(()=>field('全天统一提醒时刻').props.onChange({target:{value:'09:00'}}));act(()=>field('全天统一提醒时区').props.onChange({target:{value:'offset'}}));act(()=>field('全天统一提醒 UTC 偏移').props.onChange({target:{value:'+08:00'}}));};
open();assert.equal(field('全天统一提醒时刻').props.value,'','no invented personal default');assert.equal(button('应用到这2项全天事项').props.disabled,true);assert.equal(dirty.at(-1),true);
fill();assert.match(text(tree.toJSON()),/2026年11月7日 09:00/);assert.match(text(tree.toJSON()),/2026年11月9日 09:00/);assert.equal(button('保存日历文件（含提醒）').props.disabled,true);
act(()=>button('取消').props.onClick());assert.equal(dirty.at(-1),false);assert.equal(requests.length,beforeRequests);assert.equal(JSON.stringify(snapshot),original);
open();fill();hold=true;await act(async()=>button('应用到这2项全天事项').props.onClick());assert.equal(pending.length,1);assert.equal(button('保存日历文件（含提醒）').props.disabled,true);
assert.deepEqual(pending[0].request.calendarReminders,[{uid:'c',reminder:{kind:'none'}},{uid:'d',reminder:{kind:'before',minutes:60}},{uid:'a',reminder:{kind:'at',at:'2026-11-07T09:00:00+08:00'}},{uid:'b',reminder:{kind:'at',at:'2026-11-09T09:00:00+08:00'}}]);
await act(async()=>field('日历事项 2 提醒').props.onChange({currentTarget:{value:'none'}}));assert.equal(pending.length,2);
await act(async()=>pending[0].resolve({contentHash:hash(pending[0].request),calendarItems:items}));assert.equal(button('保存日历文件（含提醒）').props.disabled,true,'late common preview cannot authorize changed individual choice');
await act(async()=>pending[1].resolve({contentHash:hash(pending[1].request),calendarItems:items}));hold=false;assert.equal(button('保存日历文件（含提醒）').props.disabled,false);
open();assert.ok(button('应用到这0项全天事项').props.disabled,'all explicit choices retained');act(()=>field('替换全天事项已有提醒').props.onChange({target:{checked:true}}));fill();assert.equal(button('应用到这3项全天事项').props.disabled,false);act(()=>button('取消').props.onClick());
await act(async()=>button('保存日历文件（含提醒）').props.onClick());assert.equal(exports.length,1);assert.deepEqual(exports[0].calendarReminders,pending[1].request.calendarReminders);assert.equal(exports[0].expectedContentHash,hash(pending[1].request));assert.equal(JSON.stringify(snapshot),original);act(()=>tree.unmount());
// Each date is validated in the chosen zone; a DST gap or fold must refuse
// the entire application. Explicit offsets remain an intentional alternative.
const priorTZ=process.env.TZ;process.env.TZ='America/New_York';let applied:any[]=[];
const dates:any[]=[{uid:'gap',title:'春季跳时',deadline:'2026-03-08',status:'allDay'},{uid:'fold',title:'秋季重复',deadline:'2026-11-01',status:'allDay'}];
act(()=>{tree=create(<CalendarAllDayReminders items={dates} choice={{}} disabled={false} onApply={value=>applied.push(value)} onClose={()=>{}}/>);});
act(()=>field('全天统一提醒时刻').props.onChange({target:{value:'02:30'}}));assert.equal(button('应用到这2项全天事项').props.disabled,true);assert.match(text(tree.toJSON()),/不存在/);
act(()=>field('全天统一提醒时刻').props.onChange({target:{value:'01:30'}}));assert.equal(button('应用到这2项全天事项').props.disabled,true);assert.match(text(tree.toJSON()),/两个时间/);
act(()=>field('全天统一提醒时区').props.onChange({target:{value:'offset'}}));act(()=>field('全天统一提醒 UTC 偏移').props.onChange({target:{value:'+08:00'}}));assert.equal(button('应用到这2项全天事项').props.disabled,false);act(()=>button('应用到这2项全天事项').props.onClick());assert.equal(applied.length,1);act(()=>tree.unmount());
act(()=>{tree=create(<CalendarAllDayReminders items={[dates[0],{...dates[1],uid:'gap'}]} choice={{}} disabled={false} onApply={value=>applied.push(value)} onClose={()=>{}}/>);});act(()=>field('全天统一提醒时刻').props.onChange({target:{value:'09:00'}}));assert.equal(button('应用到这2项全天事项').props.disabled,true);assert.match(text(tree.toJSON()),/标识有重复/);act(()=>tree.unmount());
if(priorTZ===undefined)delete process.env.TZ;else process.env.TZ=priorTZ;
console.log('PASS one explicit all-day clock on distinct authored dates, existing none/timed/individual choices preserved, cancel/pending/export hashes, stale preview refusal, source untouched, DST gap/fold and duplicate identity rejected');
