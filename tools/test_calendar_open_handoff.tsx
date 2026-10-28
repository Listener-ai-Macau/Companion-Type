import assert from 'node:assert/strict';import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionExportFeedback} from '../packages/ui/src/CompanionExportFeedback';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const saved={kind:'saved' as const,format:'calendar',path:'C:\\fictional\\样品.ics',message:'已保存：样品.ics',calendarOpenToken:'opaque-one'};
let calls:string[]=[],resolve!:()=>void,reject!:(e:unknown)=>void,tree:any;
const open=(token:string)=>{calls.push(token);return new Promise<void>((a,b)=>{resolve=a;reject=b;});};
const render=(feedback=saved)=> <CompanionExportFeedback feedback={feedback} onOpenSavedCalendar={open}/>;
act(()=>{tree=create(render());});assert.equal(calls.length,0,'save never automatically opens an external app');
const button=()=>tree.root.findByType('button');
act(()=>{button().props.onClick();button().props.onClick();});assert.deepEqual(calls,['opaque-one']);assert.equal(button().props.disabled,true);
await act(async()=>reject('没有默认日历应用；文件仍保留。'));
assert.match(text(tree.toJSON()),/没有默认日历应用/);assert.match(text(tree.toJSON()),/C:\\fictional\\样品.ics/);assert.equal(button().props.disabled,false);
act(()=>button().props.onClick());await act(async()=>resolve());assert.equal(calls.length,2);
assert.match(text(tree.toJSON()),/已请求默认应用打开/);assert.match(text(tree.toJSON()),/请在接收应用中确认导入/);assert.doesNotMatch(text(tree.toJSON()),/已导入成功|提醒已生效/);
act(()=>{tree.update(render({...saved,calendarOpenToken:'opaque-two'}));});assert.equal(text(button()),'打开日历文件');
act(()=>button().props.onClick());act(()=>tree.update(render({...saved,calendarOpenToken:'opaque-three'})));
await act(async()=>resolve());assert.equal(text(button()),'打开日历文件','old request does not affect newly saved file');
for(const feedback of [{...saved,kind:'cancelled' as const},{...saved,kind:'error' as const},{...saved,format:'json'},{...saved,calendarOpenToken:undefined}]) {
 act(()=>tree.update(<CompanionExportFeedback feedback={feedback} onOpenSavedCalendar={open}/>));assert.equal(tree.root.findAllByType('button').length,0);
}
act(()=>tree.update(<CompanionExportFeedback feedback={saved}/>));assert.equal(tree.root.findAllByType('button').length,0);
act(()=>tree.unmount());
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});snapshot.host.persistence={status:'ready'};
const handed:string[]=[];
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
  onExportMeeting={async()=>({path:saved.path,bytes:123,calendarOpenToken:'native-receipt'})} onOpenSavedCalendar={async token=>{handed.push(token);}}/>);});
await act(async()=>tree.root.findAllByType('button').find((n:any)=>text(n)==='导出到日历').props.onClick());
assert.equal(handed.length,0);
await act(async()=>tree.root.findAllByType('button').find((n:any)=>text(n)==='打开日历文件').props.onClick());
assert.deepEqual(handed,['native-receipt'],'dashboard carries the native token into the explicit handoff');
act(()=>tree.unmount());console.log('PASS explicit opaque-token handoff and Dashboard wiring; no save auto-open; duplicate/pending guard; failure retains saved path; retry; accurate requested-only status; stale completion isolated; no unsupported or cancelled entry');
