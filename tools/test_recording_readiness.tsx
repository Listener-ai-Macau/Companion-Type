import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {renderToStaticMarkup} from 'react-dom/server';
import {CompanionRecordingReadiness,fragmentedSpaceMayFit} from '../packages/ui/src/CompanionRecordingReadiness';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {CompanionHelp} from '../packages/ui/src/CompanionHelp';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';

const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const snapshot=createCompanionV1Fixture();snapshot.source='firmware';snapshot.connected=true;
snapshot.device.mode='windowsNative';snapshot.device.connected=true;snapshot.device.deviceId='fictional-readiness';
snapshot.host.persistence={status:'ready'};
snapshot.device.recordingCapacity={layoutVersion:1,busy:false,usedEntries:1,maxEntries:7,catalogGeneration:1,
 dataBytes:4000000,freeBytes:3000000,largestFreeExtent:3000000,protectedBytes:1000000,consumedBytes:0,
 bytesPerSecond:10000,reserveHeadroom:0,localLimitSeconds:120,unsyncedEntries:1,writingEntries:0,consumedEntries:0};
const calls:string[]=[];let tree:any;
const render=(s:any=snapshot,recording=false,duration=600,settings:any=null)=><CompanionRecordingReadiness snapshot={s} settings={settings}
 recording={recording} busy={false} durationSeconds={duration} onConnect={()=>calls.push('connect')}
 onCheck={()=>calls.push('check')} onRefresh={()=>calls.push('refresh')} onSettings={()=>calls.push('settings')}/>;
act(()=>{tree=create(render());});
assert.deepEqual(calls,[],'opening advice has no automatic device, recording or service activity');
assert.match(text(tree.toJSON()),/空间不够本次时长/);assert.match(text(tree.toJSON()),/约可录 5分钟/);
assert.match(text(tree.toJSON()),/实体键单次上限 2分钟/);assert.match(text(tree.toJSON()),/没有可靠电量读数/);
assert.match(text(tree.toJSON()),/不需要转写服务或离线识别模型/);
assert.match(text(tree.toJSON()),/电脑本地转写不上传录音；选择云端转写时会发送录音/);
const localSettings={asrProvider:'local-paraformer',localAsrAvailable:true,deepseekMinutesEnabled:false};
act(()=>tree.update(render(snapshot,false,600,localSettings)));
assert.match(text(tree.toJSON()),/电脑本地转写不会上传录音/);
assert.doesNotMatch(text(tree.toJSON()),/云端转写会把录音发送给所选服务/);
const cloudSettings={asrProvider:'volcengine',volcAppKeySet:true,volcAccessKeySet:true,volcResourceId:'configured',deepseekMinutesEnabled:false};
act(()=>tree.update(render(snapshot,false,600,cloudSettings)));
assert.match(text(tree.toJSON()),/云端转写会把录音发送给所选服务/);
assert.match(text(tree.toJSON()),/智能纪要会把选定的文字发送给配置的纪要服务/);
const fragmented=structuredClone(snapshot);Object.assign(fragmented.device.recordingCapacity,{
 freeBytes:540672,largestFreeExtent:270336,segmentExtentBytes:270336,segmentFrames:6209,maxEntries:64});
const fragmentedCapacity=fragmented.device.recordingCapacity!;
assert.equal(fragmentedSpaceMayFit(fragmentedCapacity,200),true,'total space only indicates a possibility');
assert.equal(fragmentedSpaceMayFit({...fragmentedCapacity,freeBytes:300000},200),false,'insufficient total space');
assert.equal(fragmentedSpaceMayFit({...fragmentedCapacity,largestFreeExtent:100000},200),false,'no complete extent');
assert.equal(fragmentedSpaceMayFit({...fragmentedCapacity,maxEntries:2},200),false,'not enough directory slots');
assert.equal(fragmentedSpaceMayFit({...fragmentedCapacity,busy:true},200),false,'busy report is not usable advice');
assert.equal(fragmentedSpaceMayFit(snapshot.device.recordingCapacity!,200),false,'legacy report does not imply segmented support');
act(()=>tree.update(render(fragmented,false,200)));
assert.match(text(tree.toJSON()),/分散空间可能可用/);
assert.match(text(tree.toJSON()),/开始时会核对分散空间/);
assert.doesNotMatch(text(tree.toJSON()),/空间不够本次时长/);
act(()=>tree.update(render()));
act(()=>tree.root.findAllByType('button').find((b:any)=>text(b)==='重新检查设备').props.onClick());assert.deepEqual(calls,['check']);
const stale=structuredClone(snapshot);stale.source='lastKnown';act(()=>tree.update(render(stale)));
assert.match(text(tree.toJSON()),/上次设备结果仅供参考/);assert.doesNotMatch(text(tree.toJSON()),/约可录 5分钟/);
act(()=>tree.root.findAllByType('button').find((b:any)=>text(b)==='连接设备').props.onClick());assert.equal(calls.at(-1),'connect');
const broken=structuredClone(snapshot);broken.host.persistence={status:'unsaved'};
broken.oobe.checks=[{id:'boardMicrophone',label:'板端录音链路',status:'fail',message:'missing'}];
act(()=>tree.update(render(broken)));assert.match(text(tree.toJSON()),/先恢复本机保存/);assert.match(text(tree.toJSON()),/若仍提示接口缺失/);
act(()=>tree.root.findAllByType('button').find((b:any)=>text(b)==='刷新保存状态').props.onClick());assert.equal(calls.at(-1),'refresh');
act(()=>tree.update(render(snapshot,true)));assert.ok(tree.root.findAllByType('button').filter((b:any)=>text(b)!=='查看服务设置').every((b:any)=>b.props.disabled));
act(()=>tree.unmount());
const controls:any[]=[];
act(()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null}
 onRefresh={()=>calls.push('dashboard-refresh')} onControl={r=>controls.push(r)}/>);});
const find=(label:string)=>tree.root.findAllByType('button').find((b:any)=>text(b)===label);
act(()=>find('设备与同步').props.onClick());
const start=()=>find('开始录音');assert.equal(start().props.disabled,false,'missing ASR is not a record-only gate');
act(()=>tree.update(<CompanionDashboard snapshot={fragmented} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={r=>controls.push(r)}/>));
assert.match(text(tree.toJSON()),/一块连续空间/);assert.match(text(tree.toJSON()),/分散空间能否合用由开始时核对/);
assert.equal(start().props.disabled,false,'fragmented advice does not gate the authoritative start check');
act(()=>start().props.onClick());assert.equal(controls.length,1);assert.equal(controls[0].action,'meetingStart');assert.equal(controls[0].meetingMode,'offlineStore');
const readonly=structuredClone(snapshot);readonly.host.persistence={status:'blocked'};
act(()=>tree.update(<CompanionDashboard snapshot={readonly} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={r=>controls.push(r)}/>));
assert.equal(start().props.disabled,true,'existing local save safety gate remains');
act(()=>tree.unmount());
const noop=()=>{};
const help=renderToStaticMarkup(<CompanionHelp onClose={noop} onDevice={noop} onLibrary={noop} onDiagnostics={noop}/>);
assert.match(help,/长会议怎样录、怎样看重点/);
assert.match(help,/电脑本地转写和云端整理有什么区别/);
assert.match(help,/换电脑前怎样备份和恢复/);
assert.match(help,/设备同步不是跨电脑云备份/);
console.log('PASS readiness and ordinary action wiring: no automatic work, stale capacity suppressed, duration/slot advice, power unknown, interface failure, saved-only recording without ASR, busy/recovery safeguards. Controlled software cases, no device or cloud.');
