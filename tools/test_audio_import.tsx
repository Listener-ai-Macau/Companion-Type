import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';
const snapshot=createCompanionV1Fixture();snapshot.host.persistence={status:'ready'};
let finish:(v:typeof snapshot|null)=>void=()=>{};let started=0,cancelled=0;
const importing=new Promise<typeof snapshot|null>(resolve=>{finish=resolve;});
let tree:any;const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label);
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
  onImportAudio={()=>{started++;return importing;}} onCancelImportAudio={async()=>{cancelled++;return true;}}/>);});
assert.ok(button('选择音频文件'));act(()=>button('选择音频文件').props.onClick());
assert.equal(started,1);assert.equal(button('正在导入…').props.disabled,true);assert.ok(button('取消导入'));
await act(async()=>button('取消导入').props.onClick());assert.equal(cancelled,1);
await act(async()=>finish(null));assert.ok(button('选择音频文件'));assert.equal(button('取消导入'),undefined);
act(()=>tree.unmount());console.log('audio import action and cancellation UI passed');
