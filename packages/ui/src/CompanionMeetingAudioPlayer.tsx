import {useEffect, useRef, useState, type MutableRefObject} from 'react';
import {MeetingTrackPlayback, type MeetingPlaybackState, type MeetingPlaybackTracks} from './meetingTrackPlayback';
import {loadPlaybackMemory, playbackSpeeds, savePlaybackMemory} from './playbackMemory';

export interface MeetingAudioControl {
  pause(): void;
  seek(seconds: number): Promise<void>;
  position(): number;
  duration(): number;
}
const time = (seconds: number) => {
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60).toString().padStart(2, '0')}:${(value % 60).toString().padStart(2, '0')}`;
};

/** Plays the saved microphone and computer tracks together without copying them. */
export function CompanionMeetingAudioPlayer({tracks, controlRef, autoPlay, onFinished, sourceIdentity, sessionId}: {
  tracks: MeetingPlaybackTracks;
  controlRef: MutableRefObject<MeetingAudioControl | null>;
  autoPlay?: boolean;
  onFinished?: () => void;
  sourceIdentity?: string;
  sessionId?: string;
}) {
  const microphone = useRef<HTMLAudioElement>(null), system = useRef<HTMLAudioElement>(null);
  const controller = useRef<MeetingTrackPlayback | null>(null);
  const finish = useRef(onFinished); finish.current = onFinished;
  const [state, setState] = useState<MeetingPlaybackState>({position:0,duration:0,playing:false,error:null});
  const [memory] = useState(()=>loadPlaybackMemory(sourceIdentity,sessionId));
  const [memoryFailed,setMemoryFailed]=useState(memory.failed);
  const [message,setMessage]=useState('');
  const [preparing,setPreparing]=useState(true);
  const [speed, setSpeed] = useState(memory.value?.speed ?? 1);
  const savedSpeed=useRef(speed);
  const lastSave=useRef(0);
  useEffect(() => {
    if (!microphone.current || !system.current) return;
    let completed = false, wasPlaying = false, alive = true, restoring = true;
    const duration=Math.max(0, ...[tracks.microphone,tracks.system].map(parts => {
      const last=parts[parts.length-1];return last?(last.firstSample+last.samples)/16_000:0;
    }));
    const remember=(position:number,force:boolean) => {
      if (restoring || !Number.isFinite(position) || duration <= 0) return;
      const now=Date.now();if(!force && now-lastSave.current<2000)return;lastSave.current=now;
      const ok=savePlaybackMemory(sourceIdentity,{version:1,position:completed?0:Math.min(duration,Math.max(0,position)),
        duration,speed:savedSpeed.current,completed},sessionId,memory.generation,memory.epoch);
      if(alive)setMemoryFailed(!ok);
    };
    try {
      const player = new MeetingTrackPlayback(tracks, microphone.current, system.current, next => {
        setState(next);
        if (next.duration > 0 && next.position >= next.duration && !next.playing) {
          if (!completed && wasPlaying) {completed = true; finish.current?.();}
        } else if (next.position < next.duration) completed = false;
        const stopped=wasPlaying&&!next.playing;wasPlaying=next.playing;
        remember(next.position,stopped||completed);
      });
      controller.current = player;player.setSpeed(savedSpeed.current);
      const controls: MeetingAudioControl = {pause:()=>player.pause(),seek:(seconds)=>player.seek(seconds),
        position:()=>player.getPosition(),duration:()=>duration};
      const saveOnHide=()=>remember(player.getPosition(),true);
      window.addEventListener?.('pagehide',saveOnHide);
      void (async()=>{
        const prior=memory.value;
        if(prior && !prior.completed && Math.abs(prior.duration-duration)<=0.25 && prior.position<duration-0.25) {
          try {await player.seek(prior.position);if(alive && prior.position>0)setMessage(`已恢复到 ${time(prior.position)}${autoPlay?'。':'，点击播放即可继续。'}`);} catch {/* Error is shown by the player. */}
        }
        restoring=false;if(!alive)return;controlRef.current=controls;setPreparing(false);remember(player.getPosition(),true);
        if(autoPlay)await player.play();
      })();
      return () => {alive=false;remember(player.getPosition(),true);window.removeEventListener?.('pagehide',saveOnHide);
        if (controlRef.current === controls) controlRef.current = null; controller.current = null; player.dispose();};
    } catch (error) {
      setState({position:0,duration:0,playing:false,error:error instanceof Error?error.message:'无法准备会议回听。'});
    }
  }, [tracks,controlRef]);
  const ready=state.duration>0 && !preparing;
  return <div className="ct-audio-player">
    <audio ref={microphone} preload="metadata" aria-label="会议麦克风音轨" />
    <audio ref={system} preload="metadata" aria-label="会议电脑声音音轨" />
    <div className="ct-audio-tools">
      <button type="button" className="ct-action" disabled={!ready} onClick={()=>{
        if (state.playing) controller.current?.pause(); else void controller.current?.play();
      }}>{state.playing?'暂停':'播放'}</button>
      <button type="button" className="ct-action" disabled={!ready} onClick={()=>void controller.current?.seek(Math.max(0,state.position-10)).catch(()=>{})}>后退 10 秒</button>
      <button type="button" className="ct-action" disabled={!ready} onClick={()=>void controller.current?.seek(Math.min(state.duration,state.position+10)).catch(()=>{})}>前进 10 秒</button>
      <label>回听速度 <select aria-label="回听速度" value={speed} disabled={!ready} onChange={event=>{
        const value=Number(event.target.value);if (!playbackSpeeds.includes(value)) return;
        savedSpeed.current=value;setSpeed(value);controller.current?.setSpeed(value);
      }}>{playbackSpeeds.map(value=><option key={value} value={value}>{value}×</option>)}</select></label>
      <span>{time(state.position)} / {time(state.duration)}</span>
    </div>
    <label>回听位置 <input aria-label="回听位置" type="range" min={0} max={state.duration||0} step={0.01}
      value={Math.min(state.duration,state.position)} disabled={!ready}
      onChange={event=>void controller.current?.seek(Number(event.target.value)).catch(()=>{})}/></label>
    {state.error ? <p role="status">{state.error}</p> : message ? <p role="status">{message}</p> : null}
    {memoryFailed ? <p role="status">本机未能保存回听位置；仍可播放，下次可能需要重新定位。</p> : null}
  </div>;
}
