import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

const snapshot=createCompanionV1Fixture();snapshot.source='firmware';snapshot.connected=false;
snapshot.device.mode='windowsNative';snapshot.device.connected=false;snapshot.device.deviceId='synthetic-device';
snapshot.host.persistence={status:'ready'};
const calls:any[]=[];
const text=(node:any):string=>node==null||typeof node==='boolean'?'':typeof node==='string'||typeof node==='number'?String(node):(node.children??[]).map(text).join('');
const render=(state:any,surface:'windows'|'mobile'='windows',busyAction:any=null)=><CompanionDashboard snapshot={state} surface={surface} busyAction={busyAction} error={null}
  onRefresh={()=>{}} onControl={request=>calls.push(request)} onImportAudio={async()=>null}/>;
let tree:any;act(()=>{tree=create(render(snapshot));});
const page=()=>tree.root.findByProps({'id':'ct-device-recording-page'});
const button=(name:string)=>page().findAllByType('button').find((item:any)=>text(item)===name);
const labels=()=>page().findAll((node:any)=>['在卡片上录音','录制电脑会议','导入已有音频','录前准备'].includes(node.props['aria-label'])).map((node:any)=>node.props['aria-label']);
const emptyEntry=tree.root.findAllByType('button').find((item:any)=>text(item)==='连接录音卡');assert.ok(emptyEntry);
act(()=>emptyEntry.props.onClick());assert.equal(page().props.hidden,false,'empty library opens the real connection entry directly');
assert.deepEqual(calls,[],'navigating to the connection page must not start capture or connect by itself');
assert.deepEqual(labels(),['录前准备','在卡片上录音','录制电脑会议','导入已有音频']);
const importEntry=tree.root.findAllByType('button').find((item:any)=>text(item)==='导入已有音频');
act(()=>importEntry.props.onClick());assert.equal(tree.root.findByProps({'className':'ct-alternative-recording'}).props.open,true,'import shortcut opens its destination instead of scrolling to a hidden control');
assert.deepEqual(calls,[]);
assert.equal(button('远程开始录音').props.disabled,true);
assert.equal(button('连接设备').props.disabled,false);
act(()=>button('连接设备').props.onClick());assert.equal(calls.at(-1).action,'deviceConnect');assert.equal(calls.at(-1).deviceId,'synthetic-device');
act(()=>tree.update(render(snapshot,'windows','deviceConnect')));assert.equal(button('连接设备').props.disabled,true);
const connected=structuredClone(snapshot);connected.connected=true;connected.device.connected=true;
act(()=>tree.update(render(connected)));assert.equal(Boolean(button('连接设备')),false);
assert.equal(button('远程开始录音').props.disabled,false);
act(()=>button('远程开始录音').props.onClick());assert.equal(calls.at(-1).action,'meetingStart');assert.equal(calls.at(-1).meetingMode,'offlineStore');
for(const source of ['lastKnown','unavailable'] as const){
  const stale=structuredClone(connected);stale.source=source;
  act(()=>tree.update(render(stale)));assert.equal(button('远程开始录音').props.disabled,true,'stale reports cannot enable recording');
  assert.equal(button('连接设备').props.disabled,false,'stale reports offer a live reconnect');
  assert.equal(text(page()).includes('设备空间详情与同步建议'),false,'stale report does not offer live capacity actions');
}
const blocked=structuredClone(connected);blocked.host.persistence={status:'blocked'};
act(()=>tree.update(render(blocked)));assert.equal(button('远程开始录音').props.disabled,true);assert.equal(button('开始录电脑会议').props.disabled,true);
act(()=>tree.update(render(snapshot,'mobile')));
assert.equal(page().findByProps({'aria-label':'在卡片上录音'}).findAllByType('button').some((item:any)=>text(item)==='连接 Companion'),false);
assert.ok(labels().indexOf('录前准备')<labels().indexOf('在卡片上录音'),'mobile retains its original order');
act(()=>tree.unmount());
console.log('PASS Windows recording choices: order, connect routing, busy/disconnected/storage guards, mobile order');
