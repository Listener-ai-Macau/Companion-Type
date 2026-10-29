import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});snapshot.host.persistence={status:'ready'};
const row=snapshot.host.sessions[0];const actions=['未测完不要写通过 (due: 2026-11-08T15:00:00+08:00前)','核对包装 (due: 2026-11-07)'];
Object.assign(row.minutesByMode.offlineStore!,{markdown:'## Summary\n条件保留。\n\n## Action Items\n'+actions.map(a=>'- [ ] '+a).join('\n'),source:'userAuthored',quality:'final',status:'minutesReady'});
const before=JSON.stringify(snapshot),exports:any[]=[],previews:any[]=[],dirty:boolean[]=[];
const items=actions.map((text,index)=>({uid:'original-'+index,text,title:text.split(' (')[0],deadline:index?'2026-11-07':'2026-11-08T15:00:00+08:00前',status:index?'allDay' as const:'timed' as const}));
const hash=(request:any)=>createHash('sha256').update(JSON.stringify([request.format,request.calendarReminders??[]])).digest('hex');
const onPreviewMeetingExport=async(request:any)=>{previews.push(request);return{contentHash:hash(request),calendarItems:items};};
let tree:any;const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label),field=(label:string)=>tree.root.findByProps({'aria-label':label});
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
  onPreviewMeetingExport={onPreviewMeetingExport} onUnsavedChange={value=>dirty.push(value)}
  onSaveMeeting={async()=>{throw Error('cancel must not save');}} onExportMeeting={async request=>{exports.push(request);return null;}}/>);});
await act(async()=>button('导出到日历').props.onClick());
await act(async()=>field('日历事项 1 提醒').props.onChange({currentTarget:{value:'1440'}}));
act(()=>field('日历事项 2 提醒').props.onChange({currentTarget:{value:'at'}}));
for(const[label,value]of[['日历事项 2 提醒日期','2026-11-06'],['日历事项 2 提醒时刻','18:00'],['日历事项 2 提醒时区','offset'],['日历事项 2 提醒 UTC 偏移','+08:00']]){
  act(()=>field(label).props.onChange({target:{value}}));
}
await act(async()=>button('使用此提醒时刻').props.onClick());
const selections=structuredClone(previews.at(-1).calendarReminders);
const retained=()=>{assert.equal(field('日历事项 1 提醒').props.value,'1440');assert.equal(field('日历事项 2 提醒').props.value,'at');assert.match(text(tree.toJSON()),/2026年11月7日 · 全天日程 · 提醒：2026年11月6日 18:00/);assert.equal(JSON.stringify(snapshot),before);assert.equal(exports.length,0);};
await act(async()=>button('编辑并确认日历时间').props.onClick());
assert.equal(tree.root.findAllByType('dialog').length,0,'generic edit must not open an arbitrary item');
await act(async()=>button('取消修改并返回日历预览').props.onClick());retained();
// Even an accepted, unsaved deadline draft can be discarded without discarding
// the independent alarm selections associated with the unchanged saved source.
await act(async()=>field('日历事项 2 补充具体时刻').props.onClick());
act(()=>field('待办 2 日历时刻').props.onChange({target:{value:'10:30'}}));
await act(async()=>button('确认这个截止时间').props.onClick());assert.equal(dirty.at(-1),true);
await act(async()=>button('取消修改并返回日历预览').props.onClick());retained();assert.equal(dirty.at(-1),false);
assert.deepEqual(previews.at(-1).calendarReminders,selections,'re-preview binds original settings again');
await act(async()=>button('保存日历文件（含提醒）').props.onClick());
assert.equal(exports.length,1);assert.deepEqual(exports[0].calendarReminders,selections);assert.equal(exports[0].expectedContentHash,hash(exports[0]));
assert.equal(JSON.stringify(snapshot),before);
act(()=>tree.unmount());console.log('PASS explicit edit label/no arbitrary dialog; cancel untouched and changed deadline drafts restores per-item alarms through native re-preview without save/export; explicit final export binds preserved choices');
