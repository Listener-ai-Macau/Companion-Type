import {useEffect, useRef, useState, type MutableRefObject, type RefObject} from 'react';
import {loadPlaybackMemory, playbackSpeeds, savePlaybackMemory} from './playbackMemory';
import {recordingPartAt, recordingPartsDuration, type RecordingPart} from './recordingParts';
import type {CompanionPauseTimeline} from './CompanionAudioPlayer';

export interface SegmentedPlaybackControl { sessionId:string; seek(seconds:number):Promise<void>; position():number }
interface Props {
  parts:RecordingPart[]; sourceIdentity?:string; sessionId:string;
  playerRef:RefObject<HTMLAudioElement>; controlRef:MutableRefObject<SegmentedPlaybackControl|null>;
  pauseTimeline?:CompanionPauseTimeline|null; autoPlay?:boolean; onFinished?:()=>void; onError:()=>void;
}
const time=(seconds:number)=>`${Math.floor(Math.max(0,seconds)/60).toString().padStart(2,'0')}:${Math.floor(Math.max(0,seconds)%60).toString().padStart(2,'0')}`;

/** One player and one meeting-wide timeline, even when the WAV is split. */
export function CompanionSegmentedAudioPlayer({parts,sourceIdentity,sessionId,playerRef,controlRef,pauseTimeline,autoPlay,onFinished,onError}:Props) {
  const duration=recordingPartsDuration(parts);
  const [memory]=useState(()=>loadPlaybackMemory(sourceIdentity,sessionId));
  const [position,setPosition]=useState(0), positionRef=useRef(0);
  const [playing,setPlaying]=useState(false), playingRef=useRef(false);
  const [speed,setSpeed]=useState(memory.value?.speed??1), speedRef=useRef(speed);
  const [start,setStart]=useState<number|null>(null), [end,setEnd]=useState<number|null>(null);
  const [loop,setLoop]=useState(false), [repeat,setRepeat]=useState(false);
  const loopRef=useRef(loop), repeatRef=useRef(repeat), startRef=useRef(start), endRef=useRef(end);
  const [message,setMessage]=useState(''), [memoryFailed,setMemoryFailed]=useState(memory.failed);
  const active=useRef(0), epoch=useRef(0), moving=useRef(false), completed=useRef(false), lastSave=useRef(0);
  speedRef.current=speed;loopRef.current=loop;repeatRef.current=repeat;startRef.current=start;endRef.current=end;
  const setCurrent=(value:number)=>{positionRef.current=value;setPosition(value);};
  const remember=(force:boolean)=>{
    const now=Date.now();if(!force&&now-lastSave.current<2000)return;lastSave.current=now;
    setMemoryFailed(!savePlaybackMemory(sourceIdentity,{version:1,position:completed.current?0:positionRef.current,
      duration,speed:speedRef.current,completed:completed.current},sessionId,memory.generation,memory.epoch));
  };
  const move=async (seconds:number,play:boolean)=>{
    const player=playerRef.current;if(!player)throw new Error('原音尚未准备完成。');
    const target=recordingPartAt(parts,seconds), token=++epoch.current;moving.current=true;
    player.pause();playingRef.current=false;setPlaying(false);
    try {
      if(active.current!==target.index || player.readyState<1) {
        await new Promise<void>((resolve,reject)=>{
          const clean=()=>{player.removeEventListener('loadedmetadata',ready);player.removeEventListener('error',failed);};
          const ready=()=>{clean();resolve();};const failed=()=>{clean();reject(new Error('录音分段无法播放。'));};
          player.addEventListener('loadedmetadata',ready);player.addEventListener('error',failed);
          if(active.current!==target.index) {active.current=target.index;player.src=parts[target.index].url;player.load();}
          if(player.readyState>=1)ready();
        });
      }
      if(token!==epoch.current)return;
      player.currentTime=target.offset;player.playbackRate=speedRef.current;player.preservesPitch=true;
      setCurrent(seconds);completed.current=false;moving.current=false;
      if(play && seconds<duration) {
        try {await player.play();} catch {if(token===epoch.current)setMessage('播放已暂停，请点击播放继续。');return;}
        if(token!==epoch.current)return;playingRef.current=true;setPlaying(true);
      }
      remember(true);
    } catch(error) {if(token===epoch.current){moving.current=false;playingRef.current=false;setPlaying(false);}throw error;}
  };
  useEffect(()=>{
    const previous=memory.value;
    const initial=previous&&!previous.completed&&Math.abs(previous.duration-duration)<=0.25&&previous.position<duration-0.25?previous.position:0;
    const control:SegmentedPlaybackControl={sessionId,seek:async(seconds)=>{setLoop(false);await move(seconds,false);},position:()=>positionRef.current};
    controlRef.current=control;
    void move(initial,Boolean(autoPlay)).catch(()=>onError());
    const save=()=>remember(true);
    const hidden=()=>{if(document.visibilityState==='hidden')save();};
    window.addEventListener('pagehide',save);document.addEventListener('visibilitychange',hidden);
    return()=>{epoch.current++;remember(true);playerRef.current?.pause();if(controlRef.current===control)controlRef.current=null;
      window.removeEventListener('pagehide',save);document.removeEventListener('visibilitychange',hidden);};
  },[sourceIdentity,sessionId]);
  const go=(seconds:number,play=playingRef.current)=>{void move(Math.max(0,Math.min(duration,seconds)),play).catch(()=>onError());};
  const valid=start!=null&&end!=null&&end-start>=0.2;
  return <div className="ct-audio-player">
    <audio ref={playerRef} preload="metadata" src={parts[0].url}
      onTimeUpdate={()=>{const player=playerRef.current;if(!player||moving.current)return;
        const value=Math.min(duration,parts[active.current].firstSample/16000+player.currentTime);setCurrent(value);
        if(loopRef.current&&startRef.current!=null&&endRef.current!=null&&value>=endRef.current){go(startRef.current,true);return;}remember(false);}}
      onPause={()=>{if(!moving.current){playingRef.current=false;setPlaying(false);remember(true);}}}
      onPlay={()=>{if(!moving.current){playingRef.current=true;setPlaying(true);}}}
      onEnded={()=>{if(moving.current)return;const next=(parts[active.current].firstSample+parts[active.current].samples)/16000;
        if(loopRef.current&&startRef.current!=null&&endRef.current!=null&&next>=endRef.current){go(startRef.current,true);return;}
        if(next<duration){go(next,true);return;}if(repeatRef.current){go(0,true);return;}
        completed.current=true;setCurrent(duration);remember(true);onFinished?.();}}
      onError={()=>{if(!moving.current)onError();}} />
    <div className="ct-audio-tools">
      <button type="button" className="ct-action" onClick={()=>{if(playingRef.current){playerRef.current?.pause();}else go(positionRef.current>=duration?0:positionRef.current,true);}}>{playing?'暂停':'播放'}</button>
      <button type="button" className="ct-action" onClick={()=>{setLoop(false);go(positionRef.current-10);}}>后退 10 秒</button>
      <button type="button" className="ct-action" onClick={()=>{setLoop(false);go(positionRef.current+10);}}>前进 10 秒</button>
      <label>回听速度 <select aria-label="回听速度" value={speed} onChange={event=>{const value=Number(event.target.value);if(!playbackSpeeds.includes(value))return;
        speedRef.current=value;setSpeed(value);if(playerRef.current)playerRef.current.playbackRate=value;remember(true);}}>{playbackSpeeds.map(value=><option key={value} value={value}>{value}×</option>)}</select></label>
      <span>{time(position)} / {time(duration)}</span>
      <button type="button" className="ct-action" aria-pressed={repeat} onClick={()=>{setLoop(false);setRepeat(!repeat);}}>{repeat?'关闭单场循环':'开启单场循环'}</button>
      <button type="button" className="ct-action" onClick={()=>{setLoop(false);go(0);}}>从头回听</button>
    </div>
    <label>回听位置 <input aria-label="回听位置" type="range" min={0} max={duration} step={0.01} value={position} onChange={event=>{setLoop(false);go(Number(event.target.value));}} /></label>
    {pauseTimeline?.gaps.length ? <section aria-label="录音暂停记录"><strong>暂停记录</strong><div className="ct-audio-tools">{pauseTimeline.gaps.map((gap,index)=><button type="button" className="ct-action" key={`${gap.pausedAtMs}:${index}`} onClick={()=>{setLoop(false);go(gap.audioPositionMs/1000,false);}}>{time(gap.audioPositionMs/1000)} · {gap.durationMs==null?'暂停后未确认继续':`暂停 ${(gap.durationMs/1000).toFixed(2)} 秒`}</button>)}</div></section>:null}
    <div className="ct-audio-tools" aria-label="片段循环回听">
      <button type="button" className="ct-action" onClick={()=>{setStart(positionRef.current);setEnd(null);setLoop(false);setMessage('已设起点，定位到片段末尾后设置终点。');}}>设为起点 A</button>
      <button type="button" className="ct-action" disabled={start==null} onClick={()=>{if(start==null||positionRef.current-start<0.2){setMessage('终点须比起点至少晚 0.2 秒。');return;}setEnd(positionRef.current);setMessage('片段已选好，可开启循环。');}}>设为终点 B</button>
      <button type="button" className="ct-action" disabled={!valid} aria-pressed={loop} onClick={()=>{setRepeat(false);setLoop(!loop);if(!loop&&start!=null&&end!=null&&(positionRef.current<start||positionRef.current>=end))go(start);}}>{loop?'关闭 A–B 循环':'开启 A–B 循环'}</button>
      <button type="button" className="ct-action" disabled={start==null} onClick={()=>{setLoop(false);setStart(null);setEnd(null);setMessage('');}}>清除片段</button>
      {start!=null?<span>A {time(start)} · B {end==null?'未设置':time(end)}</span>:null}
    </div>
    {message?<p role="status">{message}</p>:null}{memoryFailed?<p role="status">本机未能保存回听位置；仍可播放。</p>:null}
  </div>;
}
