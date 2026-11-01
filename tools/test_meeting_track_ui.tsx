import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionMeetingAudioPlayer,type MeetingAudioControl} from '../packages/ui/src/CompanionMeetingAudioPlayer';
class FakeAudio extends EventTarget {
  src=''; readyState=0; currentTime=0; playbackRate=1; preservesPitch=true; paused=true;
  load(){if(!this.src){this.readyState=0;return;}this.readyState=1;this.dispatchEvent(new Event('loadedmetadata'));}
  async play(){this.paused=false;}pause(){this.paused=true;}removeAttribute(name:string){if(name==='src')this.src='';}
}
const elements:FakeAudio[]=[];const control:{current:MeetingAudioControl|null}={current:null};let finished=0;
const tracks={microphone:[{url:'mic-1',firstSample:0,samples:16000},{url:'mic-2',firstSample:16000,samples:16000}],system:[{url:'system',firstSample:0,samples:32000}]};
let view:any;await act(async()=>{view=create(<CompanionMeetingAudioPlayer tracks={tracks} controlRef={control} onFinished={()=>finished++}/>,{createNodeMock:(element:any)=>{if(element.type==='audio'){const f=new FakeAudio();elements.push(f);return f;}return null;}});});
assert.equal(elements.length,2);assert.ok(control.current);const buttons=()=>view.root.findAllByType('button');
await act(async()=>{buttons().find((x:any)=>x.children.includes('播放')).props.onClick();await new Promise(setImmediate);});
assert.equal(elements[0].src,'mic-1');assert.equal(elements[1].src,'system');assert.equal(elements[0].paused,false);
await act(async()=>{control.current!.pause();await control.current!.seek(1.5);});
assert.equal(elements[0].src,'mic-2');assert.equal(elements[0].currentTime,0.5);assert.equal(elements[1].currentTime,1.5);assert.equal(finished,0);
await act(async()=>{buttons().find((x:any)=>x.children.includes('播放')).props.onClick();await new Promise(setImmediate);});
elements[0].currentTime=1;elements[1].currentTime=2;await act(async()=>{elements[0].dispatchEvent(new Event('ended'));});
assert.equal(finished,1);await act(async()=>{view.unmount();});assert.equal(control.current,null);assert.equal(elements[0].paused,true);
console.log('Meeting track UI: mount, play, cross-part seek, completion and cleanup passed with fake audio.');
