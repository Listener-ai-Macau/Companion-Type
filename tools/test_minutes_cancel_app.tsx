import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {App} from '../apps/windows/src/App';
import {minutesStoppedMessage} from '../packages/ui/src/knownOperationErrors';

let timer=0;const timers=new Map<number,()=>void>();
(globalThis as any).window={setTimeout:(fn:()=>void)=>{timers.set(++timer,fn);return timer;},clearTimeout:(id:number)=>timers.delete(id)};
const snapshot=createCompanionV1Fixture();snapshot.host.persistence={status:'ready'};
let release!:()=>void;const pending=new Promise<void>(resolve=>{release=resolve;});
let request:any;let snapshotReads=0;const cancellations:any[]=[];
(globalThis as any).__companionAppTest={
  snapshot:async()=>{snapshotReads++;return structuredClone(snapshot);},
  control:async(value:any)=>{request=value;await pending;throw new Error(minutesStoppedMessage);},
  cancelMeetingProcessing:async(session:string,job:string)=>{cancellations.push({session,job});return cancellations.length>1;},
};
let view:any;await act(async()=>{view=create(<App/>);});
await act(async()=>{view.root.findByType(CompanionDashboard).props.onControl({action:'meetingGenerateMinutes',sessionId:'meeting-A'});await Promise.resolve();});
assert.equal(request.sessionId,'meeting-A');assert.match(request.promptId,/^__meeting_job__/);
const label=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(label).join('');
const stop=view.root.findAllByType('button').find((n:any)=>label(n)==='停止整理');assert.ok(stop);
await act(async()=>{stop.props.onClick();await Promise.resolve();});
assert.deepEqual(cancellations,[{session:'meeting-A',job:request.promptId}]);
assert.ok(view.root.findAllByType('button').some((n:any)=>label(n)==='停止中…' && n.props.disabled));
const retry=[...timers.values()].at(-1);assert.ok(retry);
await act(async()=>{retry();await Promise.resolve();await Promise.resolve();});
assert.deepEqual(cancellations,[{session:'meeting-A',job:request.promptId},{session:'meeting-A',job:request.promptId}]);
snapshot.host.persistence.message='后台停止状态已更新';
await act(async()=>{release();await pending;await Promise.resolve();});
assert.equal(view.root.findAllByType('button').some((n:any)=>label(n)==='停止整理'),false);
assert.match(label(view.toJSON()),/已停止整理，原始文字保留/);
assert.equal(view.root.findByType(CompanionDashboard).props.error,null);
assert.ok(snapshotReads>=2,'stopping minutes re-reads the durable backend state');
assert.equal(view.root.findByType(CompanionDashboard).props.snapshot.host.persistence.message,'后台停止状态已更新');
await act(async()=>view.unmount());console.log('PASS_MINUTES_CANCEL_APP: stop runs outside busy action with exact session and job');
