import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};
const selected=snapshot.host.sessions[0];
snapshot.host.selectedSessionId=selected.id;
const calls:string[]=[];
const props={snapshot,surface:'windows' as const,busyAction:'meetingTranscribeAudio' as const,error:null,
  transcribingSessionId:selected.id,onCancelTranscription:(id:string)=>calls.push(id),onRefresh:()=>{},onControl:()=>{}};
let tree:any;act(()=>{tree=create(<CompanionDashboard {...props}/>);});
const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
const stop=tree.root.findAllByType('button').find((b:any)=>text(b)==='停止转写');
assert.ok(stop);assert.equal(stop.props.disabled,false);act(()=>stop.props.onClick());assert.deepEqual(calls,[selected.id]);
act(()=>tree.update(<CompanionDashboard {...props} cancelTranscriptionPending/>));
const pending=tree.root.findAllByType('button').find((b:any)=>text(b)==='停止中…');
assert.ok(pending);assert.equal(pending.props.disabled,true);
assert.match(text(tree.toJSON()),/等待当前请求或音频片段结束；原录音保留/);
act(()=>tree.update(<CompanionDashboard {...props} busyAction={null}/>));
assert.equal(tree.root.findAllByType('button').some((b:any)=>text(b)==='停止转写'),false);
act(()=>tree.unmount());console.log('PASS_TRANSCRIPTION_CANCEL_UI: independent stop button, exact session, pending and completion');
