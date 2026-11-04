import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';

const store=new Map<string,string>();let scrolled=0;
(globalThis as any).window={localStorage:{getItem:(k:string)=>store.get(k)??null,setItem:(k:string,v:string)=>store.set(k,v),
  removeItem:(k:string)=>store.delete(k),key:(i:number)=>[...store.keys()][i]??null,get length(){return store.size;}}};
(globalThis as any).document={getElementById:()=>({scrollIntoView:()=>{scrolled++;}})};
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};snapshot.meeting.active=false;
const session=snapshot.host.sessions[0];snapshot.host.selectedSessionId=session.id;
session.status='transcribed';session.source='importedAudio';session.audioPath='C:/test/long.wav';
session.audioStored=true;session.audioBytes=10000;session.retention.audioCached=true;
session.transcriptText='会议文字';session.transcriptFinal=true;
session.transcriptUnrecognized=Array.from({length:22},(_,i)=>({startMs:i*10000,endMs:i*10000+4000}));
const player={duration:300,currentTime:0,readyState:1,paused:true,playbackRate:1,preservesPitch:false,plays:0,
  pause(){this.paused=true;},play(){this.paused=false;this.plays++;return Promise.resolve();},removeAttribute(){},load(){}};
let requested=0;let tree:any;
await act(async()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null}
  onRefresh={()=>{}} onControl={()=>{}} onPrepareAudio={async id=>{requested++;return {sessionId:id,url:'asset://long',sourceIdentity:'a'.repeat(64)};}}/>,
  {createNodeMock:(node:any)=>node.type==='audio'?player:null});});
const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
assert.match(text(tree.toJSON()),/查看全部 22 处未识别时段/);
const buttons=tree.root.findAllByType('button').filter((n:any)=>String(n.props['aria-label']??'').startsWith('定位第 '));
assert.equal(buttons.length,22,'every unrecognized range must remain accessible');
assert.equal(buttons[21].props.disabled,false);
await act(async()=>{buttons[21].props.onClick();await new Promise(resolve=>setTimeout(resolve,150));});
assert.equal(requested,1);assert.equal(player.currentTime,210);assert.equal(player.plays,0,'seek must not start unrequested playback');
assert.match(text(tree.toJSON()),/已定位到未识别的时段/);assert.equal(scrolled,1);
act(()=>tree.unmount());
let finishPreparation:((result:any)=>void)|undefined;
player.currentTime=0;
const other=structuredClone(session);other.id='different-meeting';other.audioPath='C:/test/other.wav';
snapshot.host.sessions.push(other);
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
  onPrepareAudio:(id:string)=>new Promise<any>(resolve=>{finishPreparation=value=>resolve({...value,sessionId:id});})});
await act(async()=>{tree=create(<CompanionDashboard {...props()}/>,{createNodeMock:(node:any)=>node.type==='audio'?player:null});});
act(()=>tree.root.findAllByType('button').find((n:any)=>String(n.props['aria-label']??'').startsWith('定位第 22 处')).props.onClick());
assert.ok(finishPreparation,'the original preparation should be in progress');
snapshot=structuredClone(snapshot);snapshot.host.selectedSessionId=other.id;
act(()=>tree.update(<CompanionDashboard {...props()}/>));
await act(async()=>{finishPreparation!({url:'asset://old',sourceIdentity:'a'.repeat(64)});await new Promise(resolve=>setTimeout(resolve,80));});
assert.equal(player.currentTime,0,'late preparation must not seek the newly selected meeting');
act(()=>tree.unmount());
console.log('PASS all 22 ranges, preparation and last-range seek on the correct original');
