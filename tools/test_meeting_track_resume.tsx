import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionMeetingAudioPlayer,type MeetingAudioControl} from '../packages/ui/src/CompanionMeetingAudioPlayer';
import {clearSessionPlaybackMemory} from '../packages/ui/src/playbackMemory';
class FakeAudio extends EventTarget {src='';readyState=0;currentTime=0;playbackRate=1;preservesPitch=true;paused=true;load(){if(this.src){this.readyState=1;this.dispatchEvent(new Event('loadedmetadata'));}}async play(){this.paused=false;}pause(){this.paused=true;}removeAttribute(name:string){if(name==='src')this.src='';}}
const items=new Map<string,string>();(window as any).localStorage={getItem:(k:string)=>items.get(k)??null,setItem:(k:string,v:string)=>items.set(k,v),removeItem:(k:string)=>items.delete(k),key:(i:number)=>[...items.keys()][i]??null,get length(){return items.size;}};
const tracks={microphone:[{url:'mic',firstSample:0,samples:32000}],system:[{url:'sys',firstSample:0,samples:32000}]};
const control:{current:MeetingAudioControl|null}={current:null};let elements:FakeAudio[]=[];let view:any;
const mount=async()=>{elements=[];await act(async()=>{view=create(<CompanionMeetingAudioPlayer tracks={tracks} controlRef={control} sourceIdentity={'a'.repeat(64)} sessionId="resume-test"/>,{createNodeMock:(e:any)=>{if(e.type==='audio'){const f=new FakeAudio();elements.push(f);return f;}return null;}});await new Promise(setImmediate);});};
await mount();assert.ok(control.current);await act(async()=>{await control.current!.seek(1.2);view.root.findByType('select').props.onChange({target:{value:'1.5'}});});
await act(async()=>view.unmount());assert.equal(control.current,null);
await mount();assert.ok(control.current);assert.ok(Math.abs(control.current!.position()-1.2)<0.001);assert.equal(elements[0].paused,true);assert.equal(elements[1].paused,true);assert.equal(elements[0].playbackRate,1.5);assert.equal(elements[1].playbackRate,1.5);
assert.ok(clearSessionPlaybackMemory('resume-test'));await act(async()=>view.unmount());
const record=JSON.parse(items.get('companion.playback.v2:resume-test')!);assert.equal(record.cleared,true,'unmount must not restore cleared progress');
await mount();assert.equal(control.current!.position(),0);await act(async()=>view.unmount());
console.log('Meeting playback resume: restore saved position without autoplay; deletion prevents stale player from resurrecting progress.');
