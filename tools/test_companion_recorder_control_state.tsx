import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { CompanionRecorderControl } from '../packages/ui/src/CompanionRecorderControl';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';

// Local UI state contract only: a click cannot manufacture a device ACK.
const started = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {action:'meetingStart',sessionId:'original'});
const session=structuredClone(started.host.sessions[0]);session.source='boardDevice';session.sourceDeviceId='C8:92:FF:DD:3B:CA';
session.recorderControl={hostSession:session.id,deviceId:session.sourceDeviceId,startRequest:101,maxSeconds:300,
  confirmed:{command:1,sequence:0,state:1,durationMs:80},pending:null};
const calls:any[]=[];let renderer:any;
const render=(busy=false)=>act(()=>{const view=<CompanionRecorderControl session={session} busy={busy} onControl={r=>calls.push(r)} />;
  if(renderer)renderer.update(view);else renderer=create(view);});
const text=(node:any):string=>typeof node==='string'?node:(node.children??[]).map(text).join('');
const button=(label:string)=>renderer.root.findAllByType('button').find((b:any)=>text(b)===label);
render();act(()=>button('暂停录音').props.onClick());
assert.deepEqual(calls.pop(),{action:'meetingPause',sessionId:'original',deviceId:session.sourceDeviceId});
assert.ok(button('暂停录音'));assert.equal(button('继续录音'),undefined,'click alone cannot confirm paused');
session.recorderControl.pending={command:4,request:110,sequence:1};render();
assert.equal(button('暂停录音'),undefined);assert.equal(button('继续录音'),undefined);
act(()=>button('核对原录音').props.onClick());assert.equal(calls.pop().action,'meetingRecoverControl');
assert.ok(button('停止并保存'),'STOP remains available while the old intent is being reconciled');
session.recorderControl.pending=null;session.recorderControl.confirmed={command:4,sequence:1,state:3,durationMs:80};render();
assert.ok(button('继续录音'));assert.match(text(renderer.toJSON()),/同一场录音/);
act(()=>button('继续录音').props.onClick());assert.equal(calls.pop().sessionId,'original');
session.recorderControlUncertain=true;render();assert.equal(button('继续录音'),undefined);
assert.ok(button('核对原录音'));render(true);assert.ok(button('核对原录音').props.disabled);
session.recorderControlUncertain=false;session.recorderControl.confirmed={command:1,sequence:0,state:2,durationMs:80,finishedLocally:true};render();
assert.equal(renderer.toJSON(),null,'a verified local seal cannot be presented as an active capture');
assert.throws(()=>applyCompanionV1ControlFixture(started,{action:'meetingPause',sessionId:'original'}),/正式后端/);
act(()=>renderer.unmount());console.log('Recorder control UI: original identity, no optimistic ACK, uncertain recovery and local seal passed (software only)');

// Pure board recording is discoverable without cloud credentials or opening
// the advanced/online workflow. An absent device must never select a host mic.
let snapshot=createCompanionV1Fixture();snapshot.connected=true;snapshot.device.connected=true;
snapshot.device.deviceId='C8:92:FF:DD:3B:CA';snapshot.device.mode='windowsNative';
calls.length=0;
const entryProps=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,
  productSettings:null,onRefresh:()=>{},onControl:(request:any)=>calls.push(request)});
act(()=>{renderer=create(<CompanionDashboard {...entryProps()} />);});
assert.equal(button('开始录音').props.disabled,false,'missing ASR settings cannot block local audio capture');
act(()=>button('开始录音').props.onClick());
assert.deepEqual(calls.pop(),{action:'meetingStart',meetingMode:'offlineStore',deviceId:snapshot.device.deviceId,
  title:'Companion 录音',durationMs:1800000});
snapshot=structuredClone(snapshot);snapshot.connected=false;snapshot.device.connected=false;
act(()=>renderer.update(<CompanionDashboard {...entryProps()} />));
assert.equal(button('开始录音').props.disabled,true,'disconnection cannot fall back to the host microphone');
snapshot=structuredClone(snapshot);snapshot.connected=true;snapshot.device.connected=true;
snapshot.meeting.active=true;
act(()=>renderer.update(<CompanionDashboard {...entryProps()} />));
assert.equal(button('开始录音'),undefined,'an existing capture cannot be replaced from the entry');
act(()=>renderer.unmount());
console.log('Recorder entry UI: visible without cloud, exact board START, no host fallback or replacement (software only)');
