import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
const snapshot=createCompanionV1Fixture();snapshot.connected=true;snapshot.source='firmware';snapshot.device.connected=true;snapshot.device.deviceId='synthetic-card';snapshot.host.persistence={status:'ready'};
const calls:any[]=[];let sync:any={jobId:'one',deviceId:'synthetic-card',phase:'receiving',recordingId:10,receivedBytes:12,totalBytes:100,pauseRequested:false};let view:any;
const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
const render=()=> <CompanionDashboard surface="windows" snapshot={snapshot} busyAction={null} error={null} recordingSync={sync} onRefresh={()=>{}} onControl={r=>calls.push(r)}/>;
const button=(label:string)=>view.root.findAllByType('button').find((n:any)=>text(n)===label);
const syncPanels=()=>view.root.findAllByProps({'aria-label':'录音同步进度'});
act(()=>{view=create(render());});assert.equal(syncPanels().length,0);assert.equal(view.root.findAllByType('progress').length,0);assert.deepEqual(calls,[]);
act(()=>button('设备与同步').props.onClick());assert.equal(syncPanels().length,0);assert.equal(button('接收设备录音'),undefined,'normal connected card requires no manual receive step');
const details=()=>view.root.findByProps({className:'ct-device-options ct-sync-details'});
act(()=>details().props.onToggle({currentTarget:{open:true}}));assert.equal(syncPanels().length,1);assert.equal(view.root.findAllByType('progress').length,1);
for(const phase of ['saving','reclaiming','receiving']){sync={...sync,phase,recordingId:11};act(()=>view.update(render()));assert.equal(details().props.open,true);assert.equal(syncPanels().length,1);}
act(()=>details().props.onToggle({currentTarget:{open:false}}));
for(const phase of ['receiving','saving','reclaiming','paused','idle']){sync={...sync,phase};act(()=>view.update(render()));assert.equal(syncPanels().length,0);assert.equal(view.root.findAllByType('progress').length,0);}
sync={...sync,jobId:null,phase:'blocked',error:'公开故障：本机保存未确认'};act(()=>view.update(render()));assert.equal(syncPanels().length,0);assert.equal(view.root.findAllByType('progress').length,0);assert.match(text(view.toJSON()),/录音收取需要处理/);
act(()=>button('查看同步详情').props.onClick());assert.equal(syncPanels().length,1);assert.match(text(view.toJSON()),/自动同步已暂停/);assert.match(text(view.toJSON()),/设备操作尚未确认/);assert.deepEqual(calls,[],'querying the status must not start, stop, pause, acknowledge or delete anything');
act(()=>view.unmount());console.log('PASS quiet Windows background receive: no automatic progress; explicit inspect; stable open across records/phases; close stays quiet; actionable failure without hidden data loss');
