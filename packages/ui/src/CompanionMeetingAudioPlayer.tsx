import {useEffect, useRef, useState, type MutableRefObject} from 'react';
import {MeetingTrackPlayback, type MeetingPlaybackState, type MeetingPlaybackTracks} from './meetingTrackPlayback';
import {playbackSpeeds} from './playbackMemory';

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
export function CompanionMeetingAudioPlayer({tracks, controlRef, autoPlay, onFinished}: {
  tracks: MeetingPlaybackTracks;
  controlRef: MutableRefObject<MeetingAudioControl | null>;
  autoPlay?: boolean;
  onFinished?: () => void;
}) {
  const microphone = useRef<HTMLAudioElement>(null), system = useRef<HTMLAudioElement>(null);
  const controller = useRef<MeetingTrackPlayback | null>(null);
  const finish = useRef(onFinished); finish.current = onFinished;
  const [state, setState] = useState<MeetingPlaybackState>({position:0,duration:0,playing:false,error:null});
  const [speed, setSpeed] = useState(1);
  useEffect(() => {
    if (!microphone.current || !system.current) return;
    let completed = false, wasPlaying = false;
    try {
      const player = new MeetingTrackPlayback(tracks, microphone.current, system.current, next => {
        setState(next);
        if (next.duration > 0 && next.position >= next.duration && !next.playing) {
          if (!completed && wasPlaying) {completed = true; finish.current?.();}
        } else if (next.position < next.duration) completed = false;
        wasPlaying = next.playing;
      });
      controller.current = player;
      const controls: MeetingAudioControl = {pause:()=>player.pause(),seek:(seconds)=>player.seek(seconds),
        position:()=>player.getPosition(),duration:()=>Math.max(0, ...[tracks.microphone,tracks.system].map(parts => {
          const last=parts[parts.length-1];return last?(last.firstSample+last.samples)/16_000:0;
        }))};
      controlRef.current = controls;
      if (autoPlay) void player.play();
      return () => {if (controlRef.current === controls) controlRef.current = null; controller.current = null; player.dispose();};
    } catch (error) {
      setState({position:0,duration:0,playing:false,error:error instanceof Error?error.message:'无法准备会议回听。'});
    }
  }, [tracks,controlRef,autoPlay]);
  const ready=state.duration>0;
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
        setSpeed(value);controller.current?.setSpeed(value);
      }}>{playbackSpeeds.map(value=><option key={value} value={value}>{value}×</option>)}</select></label>
      <span>{time(state.position)} / {time(state.duration)}</span>
    </div>
    <label>回听位置 <input aria-label="回听位置" type="range" min={0} max={state.duration||0} step={0.01}
      value={Math.min(state.duration,state.position)} disabled={!ready}
      onChange={event=>void controller.current?.seek(Number(event.target.value)).catch(()=>{})}/></label>
    {state.error ? <p role="status">{state.error}</p> : null}
  </div>;
}
