import assert from 'node:assert/strict';
import {MeetingTrackPlayback} from '../packages/ui/src/meetingTrackPlayback.ts';
class FakeAudio extends EventTarget {
  src=''; readyState=0; currentTime=0; playbackRate=1; preservesPitch=true; paused=true; fail=false;
  load(){if (!this.src) {this.readyState=0;return;} if(this.fail){this.dispatchEvent(new Event('error'));return;}this.readyState=1;this.dispatchEvent(new Event('loadedmetadata'));}
  async play(){this.paused=false;} pause(){this.paused=true;} removeAttribute(name){if(name==='src')this.src='';}
}
const segment=(url,firstSample,samples)=>({url,firstSample,samples});
const tracks={microphone:[segment('mic-1',0,16000),segment('mic-2',16000,16000)],system:[segment('sys-1',0,8000),segment('sys-2',8000,24000)]};
const mic=new FakeAudio(), system=new FakeAudio(), states=[];
const player=new MeetingTrackPlayback(tracks,mic,system,state=>states.push(state));
await player.play();assert.equal(mic.src,'mic-1');assert.equal(system.src,'sys-1');assert.equal(mic.paused,false);assert.equal(system.paused,false);
mic.currentTime=0.5;system.currentTime=0.5;system.dispatchEvent(new Event('ended'));await new Promise(setImmediate);
assert.equal(system.src,'sys-2');assert.equal(mic.src,'mic-1');assert.equal(system.currentTime,0);assert.equal(mic.paused,false);
mic.currentTime=1;system.currentTime=0.5;mic.dispatchEvent(new Event('ended'));await new Promise(setImmediate);
assert.equal(mic.src,'mic-2');assert.equal(mic.currentTime,0);assert.equal(system.currentTime,0.5);
await player.seek(1.5);assert.equal(mic.currentTime,0.5);assert.equal(system.currentTime,1);
system.currentTime=0.2;player.synchronize();assert.equal(system.currentTime,1);
player.setSpeed(1.5);assert.equal(mic.playbackRate,1.5);assert.equal(system.playbackRate,1.5);
system.dispatchEvent(new Event('waiting'));assert.equal(mic.paused,true);assert.equal(system.paused,true);assert.equal(states.at(-1).playing,false);
system.dispatchEvent(new Event('canplay'));await new Promise(setImmediate);assert.equal(mic.paused,false);assert.equal(system.paused,false);
player.pause();assert.equal(mic.paused,true);assert.equal(system.paused,true);assert.equal(states.at(-1).playing,false);
await player.play();mic.currentTime=1;system.currentTime=1.5;mic.dispatchEvent(new Event('ended'));
assert.equal(states.at(-1).position,2);assert.equal(states.at(-1).playing,false);assert.equal(system.paused,true);
await player.play();assert.equal(player.getPosition(),0);assert.equal(mic.src,'mic-1');
system.dispatchEvent(new Event('waiting'));player.pause();system.dispatchEvent(new Event('canplay'));await new Promise(setImmediate);
assert.equal(mic.paused,true);assert.equal(system.paused,true);
player.dispose();assert.equal(mic.src,'');assert.equal(system.src,'');
assert.throws(()=>new MeetingTrackPlayback({microphone:[segment('bad',1,100)],system:[]},new FakeAudio(),new FakeAudio(),()=>{}),/不连续/);
const failing=new FakeAudio();failing.fail=true;const errors=[];const broken=new MeetingTrackPlayback({microphone:[segment('bad',0,16000)],system:[]},failing,new FakeAudio(),s=>errors.push(s));
await broken.play();assert.match(errors.at(-1).error,/无法播放/);assert.equal(errors.at(-1).playing,false);broken.dispose();
console.log('Meeting track playback: boundaries, seeking, drift, buffering, cancellation, completion, invalid data and load failure passed.');
