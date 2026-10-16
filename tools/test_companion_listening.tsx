import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionAudioPlayer} from '../packages/ui/src/CompanionAudioPlayer';
import {useListeningQueue} from '../packages/ui/src/useListeningQueue';
import {clearPlaybackMemory} from '../packages/ui/src/playbackMemory';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
const records=new Map<string,string>();let fail=false;
(globalThis as any).window={localStorage:{get length(){return records.size;},key:(i:number)=>[...records.keys()][i]??null,
  removeItem:(k:string)=>records.delete(k),getItem:(k:string)=>records.get(k)??null,setItem:(k:string,v:string)=>{if(fail)throw Error('disk');records.set(k,v);}}};
const makePlayer=()=>({duration:300,currentTime:0,readyState:1,paused:true,playbackRate:1,preservesPitch:false,
  plays:0,removeAttribute(){},load(){},pause(){this.paused=true;},play(){this.paused=false;this.plays++;return Promise.resolve();}});
const ref=React.createRef<HTMLAudioElement>();let player=makePlayer();let view:any;
const props=(id:string,src='asset://same-path')=>({src,sourceIdentity:id,playerRef:ref,onError:()=>{}});
const mount=(id:string)=>act(()=>{view=create(<CompanionAudioPlayer {...props(id)}/>,{createNodeMock:e=>e.type==='audio'?player:null});});
const audio=()=>view.root.findByType('audio');
const text=(n:any):string=>typeof n==='string'?n:(n.children??[]).map(text).join('');
const button=(label:string)=>view.root.findAllByType('button').find((n:any)=>text(n).includes(label));
mount('a'.repeat(64));act(()=>audio().props.onLoadedMetadata());player.currentTime=72.5;
act(()=>view.root.findByProps({'aria-label':'回听速度'}).props.onChange({target:{value:'1.5'}}));
act(()=>audio().props.onPause());act(()=>view.unmount());
player=makePlayer();mount('a'.repeat(64));act(()=>audio().props.onLoadedMetadata());
assert.equal(player.currentTime,72.5);assert.equal(player.playbackRate,1.5);assert.equal(player.plays,0);
assert.match(text(view.toJSON()),/已恢复到 01:12/);
// No parent key: replaced content at exactly the same URL resets every control.
act(()=>button('设为起点 A').props.onClick());
player=makePlayer();act(()=>view.update(<CompanionAudioPlayer {...props('b'.repeat(64))}/>));
act(()=>audio().props.onLoadedMetadata());assert.equal(player.currentTime,0);assert.equal(player.playbackRate,1);
assert.equal(button('开启 A–B 循环').props.disabled,true);assert.equal(player.plays,0);
player.currentTime=300;act(()=>audio().props.onEnded());act(()=>view.unmount());
player=makePlayer();mount('b'.repeat(64));act(()=>audio().props.onLoadedMetadata());assert.equal(player.currentTime,0);
player.currentTime=10;fail=true;act(()=>audio().props.onPause());assert.match(text(view.toJSON()),/未能保存回听位置/);
fail=false;act(()=>audio().props.onPause());assert.doesNotMatch(text(view.toJSON()),/未能保存回听位置/);act(()=>view.unmount());
console.log('PASS listening memory: source fingerprint, exit/reopen, speed, same-URL replacement, completed reset, no autoplay and visible storage failure; software DOM only');

let api:ReturnType<typeof useListeningQueue>;let selected='a';let disabled=false,hardBlocked=false;
let rows=[{id:'a',title:'A',identity:'meta-a',ready:true},{id:'b',title:'B',identity:'meta-b',ready:true}];
let changed=false;let deferred:((v:any)=>void)|null=null;let waits=false;const ready:any[]=[];const selectedCalls:string[]=[];let pauses=0;
const prepare=async(id:string)=> waits?new Promise<any>(resolve=>{deferred=resolve;}):{sessionId:id,url:`asset://${id}`,sourceIdentity:(changed?'f':id).repeat(64)};
const config=()=>({rows,selectedId:selected,disabled,hardBlocked,prepare,select:(id:string)=>{selectedCalls.push(id);},
  ready:(...args:any[])=>ready.push(args),pause:()=>{pauses++;}});
function Harness(){api=useListeningQueue(config());return null;}
let q:any;act(()=>{q=create(<Harness/>);});
const render=()=>act(()=>q.update(<Harness/>));
await act(async()=>{await api.add();});selected='b';render();await act(async()=>{await api.add();});
assert.equal(api.items.length,2);assert.equal(ready.length,0,'enqueuing cannot play');
act(()=>api.start());assert.equal(selectedCalls.at(-1),'a');assert.equal(ready.length,0,'must select the actual queued meeting first');
selected='a';await act(async()=>{q.update(<Harness/>);});assert.equal(ready.length,1);assert.equal(api.active?.phase,'playing');
act(()=>api.finished('a'.repeat(64)));assert.equal(selectedCalls.at(-1),'b');
selected='b';await act(async()=>{q.update(<Harness/>);});assert.equal(ready.length,2);
act(()=>api.finished('a'.repeat(64)));assert.equal(api.items.length,1,'late old-source ended callback cannot finish the next original');
hardBlocked=true;render();assert.equal(api.active,null);assert.ok(pauses>0);
hardBlocked=false;render();changed=true;await act(async()=>api.start());
assert.equal(ready.length,2);assert.equal(api.active,null);assert.match(api.message,/原音内容/);
changed=false;waits=true;act(()=>api.start());assert.equal(api.active?.phase,'preparing');act(()=>api.stop());
await act(async()=>deferred!({sessionId:'b',url:'late',sourceIdentity:'b'.repeat(64)}));assert.equal(ready.length,2);
waits=false;await act(async()=>api.start());assert.equal(ready.length,3);act(()=>api.finished('b'.repeat(64)));
assert.equal(api.items.length,0);assert.match(api.message,/播放完毕/);act(()=>q.unmount());
console.log('PASS listening queue: explicit start, two originals, source revalidation, stale completion/cancellation, recording gate and terminal drain; software hook only');

let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});const first=structuredClone(snapshot.host.sessions[0]);
first.id='listen-a';first.title='录音 A';first.status='recorded';first.pendingReason=undefined;
first.audioPath='C:/original-a.wav';first.audioBytes=9600044;first.audioStored=true;first.retention.audioCached=true;
first.recovery={intent:'none',requestedMeetingMode:'offlineStore',stage:'idle',attemptCount:0,maxAttempts:3};
const second=structuredClone(first);second.id='listen-b';second.title='录音 B';second.audioPath='C:/original-b.wav';
snapshot.meeting.active=false;snapshot.host.sessions=[first,second];snapshot.host.selectedSessionId=first.id;
const nativeCalls:string[]=[];let tree:any;const fakePlayer=makePlayer();
const dashboardProps=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},
  onControl:(request:any)=>{if(request.action==='meetingSelectSession'){
    snapshot=structuredClone(snapshot);snapshot.host.selectedSessionId=request.sessionId;tree.update(<CompanionDashboard {...dashboardProps()}/>);
  }},onPrepareAudio:async(id:string)=>{nativeCalls.push(id);return {sessionId:id,url:`asset://${id}`,sourceIdentity:(id===first.id?'c':'d').repeat(64)};}});
act(()=>{tree=create(<CompanionDashboard {...dashboardProps()}/>,{createNodeMock:e=>e.type==='audio'?fakePlayer:null});});
const click=async(label:string)=>act(async()=>{
  const b=tree.root.findAllByType('button').find((n:any)=>text(n).includes(label));assert.ok(b,label);assert.equal(b.props.disabled,false,label);await b.props.onClick();
});
await click('将当前录音加入队列');
snapshot=structuredClone(snapshot);snapshot.host.selectedSessionId=second.id;act(()=>tree.update(<CompanionDashboard {...dashboardProps()}/>));
await click('将当前录音加入队列');assert.equal(fakePlayer.plays,0);
await click('开始连续播放');assert.equal(snapshot.host.selectedSessionId,first.id);
await act(async()=>tree.root.findByType('audio').props.onLoadedMetadata());assert.equal(fakePlayer.plays,1);
assert.equal(tree.root.findByType('audio').props.src,`asset://${first.id}`);
await act(async()=>tree.root.findByType('audio').props.onEnded());assert.equal(snapshot.host.selectedSessionId,second.id);
await act(async()=>tree.root.findByType('audio').props.onLoadedMetadata());assert.equal(fakePlayer.plays,2);
assert.equal(tree.root.findByType('audio').props.src,`asset://${second.id}`);
await act(async()=>tree.root.findByType('audio').props.onEnded());assert.match(text(tree.toJSON()),/队列已播放完毕/);
assert.deepEqual(nativeCalls,[first.id,second.id,first.id,second.id]);act(()=>tree.unmount());
records.set('other-setting','keep');assert.ok(clearPlaybackMemory());assert.deepEqual([...records.keys()],['other-setting']);
console.log('PASS dashboard listening: enqueue/select/re-authorize/play/advance both originals and explicit local privacy cleanup; software component only, not native speaker evidence');
