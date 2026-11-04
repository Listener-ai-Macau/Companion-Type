import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

(globalThis as any).document={activeElement:null,getElementById:()=>null};
(globalThis as any).HTMLElement=class {};
(globalThis as any).HTMLButtonElement=class extends HTMLElement {};
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;}};
const text=(node:any):string=>typeof node==='string'?node:(node.children??[]).map(text).join('');
const calls:any[]=[];
const snapshot=createCompanionV1Fixture();
snapshot.source='firmware';snapshot.connected=true;snapshot.device.connected=true;
snapshot.device.mode='windowsNative';snapshot.device.deviceId='C8:92:FF:DD:3B:CA';
snapshot.device.boardId=0x57424155;snapshot.device.firmwareVersion=0x00010421;
snapshot.device.recordingCapacity={layoutVersion:3,busy:false,confirmedDiscardSupported:false,usedEntries:0,maxEntries:64,
  catalogGeneration:1,dataBytes:15695872,freeBytes:15695872,largestFreeExtent:15695872,protectedBytes:0,
  consumedBytes:0,bytesPerSecond:2100,reserveHeadroom:4108,segmentFrames:6211,segmentExtentBytes:270336,
  localLimitSeconds:0,unsyncedEntries:0,writingEntries:0,consumedEntries:0};
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:(value:unknown)=>calls.push(value)});
let renderer:any;act(()=>{renderer=create(<CompanionDashboard {...props()}/>);});
const start=()=>renderer.root.findByProps({id:'ct-device-recording-page'}).findAllByType('button')
  .find((button:any)=>text(button)==='开始录音');
assert.ok(start());assert.equal(start().props.disabled,false);
act(()=>start().props.onClick());
assert.equal(calls.at(-1)?.durationMs,0,'new firmware should start without preset limit');
snapshot.device.firmwareVersion=0x00010420;
act(()=>renderer.update(<CompanionDashboard {...props()}/>));
act(()=>start().props.onClick());
assert.equal(calls.at(-1)?.durationMs,1800000,'old firmware must not interpret zero as unlimited');
snapshot.device.firmwareVersion=0x00010421;snapshot.device.boardId=0x1234;
act(()=>renderer.update(<CompanionDashboard {...props()}/>));
act(()=>start().props.onClick());
assert.equal(calls.at(-1)?.durationMs,1800000,'unknown board must not use new WBA contract');
snapshot.device.boardId=0x57424155;delete snapshot.device.recordingCapacity!.segmentFrames;
act(()=>renderer.update(<CompanionDashboard {...props()}/>));
act(()=>start().props.onClick());
assert.equal(calls.at(-1)?.durationMs,1800000,'missing segmented capability must not enable zero');
console.log('PASS unlimited recording UI preserves old firmware behavior');
