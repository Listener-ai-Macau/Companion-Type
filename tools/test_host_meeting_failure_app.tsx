import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {App} from '../apps/windows/src/App';
(window as any).setTimeout = setTimeout; (window as any).clearTimeout = clearTimeout;
function snapshot(){const s=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});const row=s.host.sessions[0];Object.assign(row,{id:'failed-host-session',source:'hostMeeting',status:'recording',meetingTracks:{root:'C:/recordings/session',state:'recording',microphone:[],system:[],issue:'fake stream error',discontinuity:false}});s.meeting.active=true;s.host.activeSessionId=row.id;s.host.selectedSessionId=row.id;s.host.persistence={status:'ready'};return s;}
for (const fail of [false,true]) {
 const fake:any={snapshot:snapshot(),calls:[],fail};(globalThis as any).__meetingFailureMock=fake;let view:any;
 await act(async()=>{view=create(<App/>);await new Promise(setImmediate);await new Promise(setImmediate);await new Promise(setImmediate);});
 assert.deepEqual(fake.calls,[{action:'meetingStop',sessionId:'failed-host-session'}]);
 await act(async()=>{view.update(<App/>);await new Promise(setImmediate);});assert.equal(fake.calls.length,1,'must not repeat a failed or completed stop');
 await act(async()=>view.unmount());
}
console.log('Meeting failure App: one automatic stop on stream failure; no automatic retry after failed stop.');
