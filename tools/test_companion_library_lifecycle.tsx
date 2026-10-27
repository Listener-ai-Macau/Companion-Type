import assert from 'node:assert/strict';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
const a=structuredClone(snapshot.host.sessions[0]);a.id='life-a';a.organization={revision:0,folder:'工作',tags:['重点'],favorite:true};
const b=structuredClone(a);b.id='life-b';b.title='另一场录音';snapshot.host.sessions=[a,b];snapshot.host.selectedSessionId=a.id;
let tree:any;const calls:any[]=[];const purges:any[]=[];
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
 onSaveLibraryLifecycle:async(request:any)=>{
  calls.push(request);if(request.action==='trash'&&request.targets.some((t:any)=>snapshot.host.sessions.find(s=>s.id===t.sessionId)?.organization?.protected))throw Error('所选内容含受保护录音，整批未移入回收站；请先解除保护。');
  snapshot=structuredClone(snapshot);for(const target of request.targets){const row=snapshot.host.sessions.find(s=>s.id===target.sessionId)!;assert.equal(row.organization?.revision,target.expectedRevision);
   row.organization!.revision++;if(request.action==='protect')row.organization!.protected=true;if(request.action==='unprotect')row.organization!.protected=false;
   if(request.action==='trash')row.organization!.trashedAt='2026-10-16T14:00:00+08:00';if(request.action==='restore')delete row.organization!.trashedAt;}
  tree.update(<CompanionDashboard {...props()}/>);return snapshot;
 },
 onPurgeLibrary:async(request:any)=>{purges.push(request);const deleted=[request.targets[0].sessionId];snapshot=structuredClone(snapshot);snapshot.host.sessions=snapshot.host.sessions.filter(s=>!deleted.includes(s.id));tree.update(<CompanionDashboard {...props()}/>);
  return {snapshot,deleted,failures:[{sessionId:request.targets[1].sessionId,message:'文件被占用，未完成'}]};}});
const text=(n:any):string=>typeof n==='string'?n:(n.children??[]).map(text).join('');
const button=(s:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===s);
const select=()=>act(()=>tree.root.findAllByType('button').find((n:any)=>text(n).startsWith('选择当前筛选结果')).props.onClick());
const click=async(s:string)=>{await act(async()=>button(s).props.onClick());};
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});select();await click('保护所选录音');
assert.deepEqual(calls[0],{targets:[{sessionId:a.id,expectedRevision:0},{sessionId:b.id,expectedRevision:0}],action:'protect'});
select();await click('移入回收站');assert.equal(calls.length,1,'trash needs explicit in-app confirmation');await click('确认移入回收站');assert.match(text(tree.toJSON()),/整批未移入回收站；请先解除保护/);
assert.equal(tree.root.findAllByProps({className:'ct-library-entry'}).length,2);await click('解除所选保护');
select();await click('移入回收站');await click('确认移入回收站');assert.equal(tree.root.findAllByProps({className:'ct-library-entry'}).length,0);
await click('回收站（2）');assert.equal(tree.root.findAllByProps({className:'ct-library-entry'}).length,2);assert.equal(tree.root.findAllByProps({'aria-label':'当前会议'}).length,0,'trash cannot expose stale active workspace/audio');
select();await click('恢复所选录音');assert.match(text(tree.toJSON()),/不会自动重新转写/);assert.match(text(tree.toJSON()),/回收站为空/);
await click('返回录音库');assert.equal(tree.root.findAllByProps({className:'ct-library-entry'}).length,2);assert.equal(snapshot.host.sessions[0].organization?.folder,'工作');
select();await click('移入回收站');await click('确认移入回收站');await click('回收站（2）');select();await click('永久清除所选录音');assert.equal(purges.length,0);await click('确认永久清除');
assert.equal(purges.length,1);assert.equal(purges[0].targets.length,2);assert.match(text(tree.toJSON()),/已永久清除 1 场本机录音/);assert.match(text(tree.toJSON()),/1 场未完成/);
assert.equal(tree.root.findAllByProps({className:'ct-library-entry'}).length,1);assert.match(text(tree.toJSON()),/已选 1 场/);
act(()=>tree.unmount());
const reset=applyCompanionV1ControlFixture(snapshot,{action:'meetingResetSession'});assert.deepEqual(reset.host.sessions,snapshot.host.sessions);
console.log('PASS library lifecycle UI: exact versions, protected batch rejection, explicit trash/purge confirmations, hidden trashed workspace, restore/classification continuity, partial purge selection retention and non-destructive new workspace; component only');
