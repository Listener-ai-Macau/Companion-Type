import assert from 'node:assert/strict';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {calendarExportNeedsTime,operationErrorText} from '../packages/ui/src/operationFailure';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
const code='CALENDAR_TIME_REQUIRED:internal file C:/private/example.json api_key=not-public';
assert.equal(calendarExportNeedsTime(code),true);assert.equal(calendarExportNeedsTime(new Error(code)),true);
for(const text of ['Unrelated '+code,'CALENDAR_TIME_REQUIRED_WRONG:','os error 112','permission denied'])assert.equal(calendarExportNeedsTime(text),false);
assert.match(operationErrorText(code,'export'),/先确认.*日历日期/);
assert.doesNotMatch(operationErrorText(code,'export'),/private|api_key|example|磁盘|服务配置/);
assert.match(operationErrorText('os error 112','export'),/磁盘空间不足/);
assert.match(operationErrorText('CALENDAR_NO_PENDING_ACTIONS:private detail','export'),/事项均已完成/);
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};const row=snapshot.host.sessions[0];
row.minutesByMode.offlineStore!.markdown='## Action Items\n- [x] 已处理的旧事 (due: 2026-10-30)\n- [ ] 采购条件必须保留 (due: 本周六上午出门前)';
row.minutesByMode.offlineStore!.source='userAuthored';
row.minutesByMode.offlineStore!.quality='final';row.minutesByMode.offlineStore!.status='minutesReady';
row.minutes=row.minutes?{...row.minutes,markdown:row.minutesByMode.offlineStore!.markdown}:row.minutes;
const original=JSON.stringify(snapshot);let tree:any,previewCalls=0,exportCalls=0,dirty:boolean[]=[],rejectLater:((e:unknown)=>void)|null=null;
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
 onUnsavedChange:(value:boolean)=>dirty.push(value),onSaveMeeting:async()=>snapshot,
 onExportMeeting:async()=>{exportCalls++;return null;},
 onPreviewMeetingExport:async()=>{previewCalls++;if(rejectLater)return new Promise<never>((_,reject)=>{rejectLater=reject;});throw Error(code);}});
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label);
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});
await act(async()=>button('导出到日历').props.onClick());
assert.equal(previewCalls,1);assert.equal(exportCalls,0);
const dialogs=tree.root.findAllByType('dialog');assert.equal(dialogs.length,1);
assert.equal(dialogs[0].props['aria-label'],'待办 2 日历时间','Do not offer a completed task as the repair target');
assert.match(text(dialogs[0]),/本周六上午出门前/);
assert.equal(tree.root.findByProps({'aria-label':'待办 2 日历日期'}).props.value,'','No invented Saturday date');
assert.equal(tree.root.findByProps({'aria-label':'待办 2 日历时刻'}).props.value,'','No invented morning hour');
assert.doesNotMatch(text(tree.toJSON()),/保存未完成|检查保存位置|不要用导出文件覆盖原音|api_key|C:\/private/);
assert.equal(dirty.at(-1),true,'Open confirmation participates in the existing unsaved/close guard');
act(()=>dialogs[0].props.onCancel({preventDefault(){}}));assert.equal(tree.root.findAllByType('dialog').length,0);
assert.equal(dirty.at(-1),false,'Cancelled untouched time releases unsaved guard');
assert.equal(button('保存修改').props.disabled,true,'No saved value changes merely by entering this repair path');
act(()=>button('取消').props.onClick());assert.equal(JSON.stringify(snapshot),original);
// A late capability response for a changed source cannot open an old editor.
rejectLater=()=>{};await act(async()=>{button('导出到日历').props.onClick();});
const replacement=structuredClone(snapshot);replacement.host.sessions[0].title='同记录新标题';snapshot=replacement;
act(()=>tree.update(<CompanionDashboard {...props()}/>));
await act(async()=>rejectLater!(Error(code)));
assert.equal(tree.root.findAllByType('dialog').length,0);assert.equal(exportCalls,0);
act(()=>tree.unmount());
console.log('PASS P637 direct pending-task calendar confirmation, no guessed time/file dialog/state mutation, cancel/source fence and safe coded guidance');
