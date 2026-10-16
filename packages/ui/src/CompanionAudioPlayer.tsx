import { useEffect, useRef, useState, type RefObject, type MutableRefObject } from 'react';
import { loadPlaybackMemory, savePlaybackMemory, playbackSpeeds } from './playbackMemory';

export interface CompanionPauseTimeline {
  capturedDurationMs: number;
  gaps: Array<{ audioPositionMs: number; pausedAtMs: number; resumedAtMs: number | null;
    durationMs: number | null; endedDuringPause: boolean }>;
}

const time = (seconds: number) => {
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60).toString().padStart(2, '0')}:${(value % 60).toString().padStart(2, '0')}`;
};

/** Playback changes only this authorized original; it never edits the recording. */
interface PlayerProps {
  src: string;
  sourceIdentity?: string;
  playerRef: RefObject<HTMLAudioElement>;
  onError: () => void;
  pauseTimeline?: CompanionPauseTimeline | null;
  externalSeekRef?: MutableRefObject<(() => void) | null>;
  onFinished?: () => void;
  autoPlay?: boolean;
}
export function CompanionAudioPlayer(props: PlayerProps) {
  // Reset all transient controls even when the parent omits a key. The native
  // fingerprint isolates replaced same-path/same-length originals as well.
  return <SourcePlayer key={JSON.stringify([props.sourceIdentity ?? '', props.src])} {...props} />;
}
function SourcePlayer({ src, sourceIdentity, playerRef, onError, pauseTimeline, externalSeekRef, onFinished, autoPlay }: PlayerProps) {
  const [memory] = useState(() => loadPlaybackMemory(sourceIdentity));
  const [duration, setDuration] = useState(0);
  const [position, setPosition] = useState(0);
  const [speed, setSpeed] = useState(memory.value?.speed ?? 1);
  const savedSpeed = useRef(speed);
  const metadataReady = useRef(false);
  const completed = useRef(false);
  const lastSave = useRef(0);
  const [memoryFailed, setMemoryFailed] = useState(memory.failed);
  const [start, setStart] = useState<number | null>(null);
  const [end, setEnd] = useState<number | null>(null);
  const [loop, setLoop] = useState(false);
  const [repeat,setRepeat]=useState(false);
  const repeatActive=useRef(repeat);repeatActive.current=repeat;
  const loopActive = useRef(loop);
  loopActive.current = loop;
  const [message, setMessage] = useState('');
  const ready = Number.isFinite(duration) && duration > 0;
  const validRange = start != null && end != null && end - start >= 0.2 && end <= duration;

  const remember = (player: HTMLAudioElement | null, force: boolean) => {
    if (!metadataReady.current || !player || !Number.isFinite(player.duration) || player.duration <= 0
      || !Number.isFinite(player.currentTime)) return;
    const now = Date.now(); if (!force && now-lastSave.current < 2000) return;
    lastSave.current = now;
    const ok = savePlaybackMemory(sourceIdentity, {version:1,
      position:completed.current ? 0 : Math.min(player.duration, Math.max(0, player.currentTime)),
      duration:player.duration, speed:savedSpeed.current, completed:completed.current});
    setMemoryFailed(!ok);
  };

  useEffect(() => {
    const player = playerRef.current;
    const save = () => remember(player, true);
    const hidden = () => { if (document.visibilityState === 'hidden') save(); };
    if (typeof window !== 'undefined') window.addEventListener?.('pagehide', save);
    if (typeof document !== 'undefined') document.addEventListener?.('visibilitychange', hidden);
    return () => {
      save(); player?.pause();
      if (typeof window !== 'undefined') window.removeEventListener?.('pagehide', save);
      if (typeof document !== 'undefined') document.removeEventListener?.('visibilitychange', hidden);
    };
  }, [src, playerRef]);
  useEffect(() => {
    if (!externalSeekRef) return;
    const reset = () => { loopActive.current = false; setLoop(false); };
    externalSeekRef.current = reset;
    return () => { if (externalSeekRef.current === reset) externalSeekRef.current = null; };
  }, [src, externalSeekRef]);

  const current = () => {
    const player = playerRef.current;
    if (!ready || !player || player.readyState < 1 || !Number.isFinite(player.currentTime)) return null;
    return Math.min(duration, Math.max(0, player.currentTime));
  };
  const skip = (seconds: number) => {
    const value = current();
    if (value == null) return;
    setLoop(false);
    playerRef.current!.currentTime = Math.min(duration, Math.max(0, value + seconds));
    setPosition(playerRef.current!.currentTime);
  };
  const mark = (which: 'start' | 'end') => {
    const value = current();
    if (value == null) return;
    if (which === 'start') {
      setStart(value); setEnd(null); setLoop(false); setMessage('已设起点，定位到片段末尾后设置终点。');
    } else if (start == null || value - start < 0.2) {
      setMessage('终点须比起点至少晚 0.2 秒，请重新定位。');
    } else {
      setEnd(value); setLoop(false); setMessage('片段已选好，可开启循环；点击播放后回听。');
    }
  };
  const rewindLoop = () => {
    const player = playerRef.current;
    if (!player || !loopActive.current || !validRange || start == null || end == null) return;
    if (player.currentTime >= end || player.currentTime < start) {
      player.currentTime = start;
      setPosition(start);
    }
  };

  return <div className="ct-audio-player">
    <audio ref={playerRef} controls preload="metadata" src={src}
      onLoadedMetadata={() => {
        const player = playerRef.current;
        const value = player?.duration;
        if (!player || value == null || !Number.isFinite(value) || value <= 0) return;
        setDuration(value); player.playbackRate = savedSpeed.current; player.preservesPitch = true;
        if (metadataReady.current) return;
        metadataReady.current = true;
        const prior = memory.value;
        if (prior && !prior.completed && Math.abs(prior.duration-value) <= 0.25 && prior.position < value-0.25) {
          player.currentTime = prior.position; setPosition(prior.position);
          if (prior.position > 0) setMessage(`已恢复到 ${time(prior.position)}，点击播放即可继续。`);
        }
        if (autoPlay) void player.play().catch(() => setMessage('连续播放已暂停，请点击播放继续。'));
      }}
      onTimeUpdate={() => {
        const value = playerRef.current?.currentTime;
        if (value != null && Number.isFinite(value)) setPosition(value);
        if (!playerRef.current?.paused) rewindLoop();
        remember(playerRef.current, false);
      }}
      onPlay={() => { completed.current = false; rewindLoop(); }}
      onPause={() => remember(playerRef.current, true)}
      onSeeked={() => { completed.current = false; remember(playerRef.current, true); }}
      onEnded={() => {
        const player = playerRef.current;
        if (!player) return;
        if(repeatActive.current){
          completed.current=false;player.currentTime=0;setPosition(0);
          void player.play().catch(()=>{setRepeat(false);setMessage('单场循环已暂停，请点击播放继续。');});return;
        }
        if (!loopActive.current || !validRange || start == null) {
          completed.current = true; remember(player, true); onFinished?.(); return;
        }
        player.currentTime = start;
        void player.play().catch(() => { setLoop(false); setMessage('循环播放已暂停，请点击播放继续。'); });
      }}
      onError={() => { setLoop(false); remember(playerRef.current, true); onError(); }}>你的系统无法播放这段音频。</audio>
    <div className="ct-audio-tools">
      <button type="button" className="ct-action" disabled={!ready} onClick={() => skip(-10)}>后退 10 秒</button>
      <button type="button" className="ct-action" disabled={!ready} onClick={() => skip(10)}>前进 10 秒</button>
      <label>回听速度 <select aria-label="回听速度" value={speed} disabled={!ready}
        onChange={(event) => {
          const value = Number(event.target.value);
          const player = playerRef.current;
          if (!player || !playbackSpeeds.includes(value)) return;
          savedSpeed.current = value; player.preservesPitch = true; player.playbackRate = value; setSpeed(value);
          remember(player, true);
        }}>{playbackSpeeds.map((value) => <option key={value} value={value}>{value}×</option>)}</select></label>
      <span>{time(position)} / {time(duration)}</span>
      <button type="button" className="ct-action" disabled={!ready} aria-pressed={repeat} onClick={()=>{
        setLoop(false);setRepeat(value=>!value);setMessage('');
      }}>{repeat?'关闭单场循环':'开启单场循环'}</button>
      <button type="button" className="ct-action" disabled={!ready} onClick={() => {
        const player=playerRef.current; if (!player) return;
        completed.current=false; setLoop(false); player.currentTime=0; setPosition(0); remember(player,true);
      }}>从头回听</button>
    </div>
    {pauseTimeline && pauseTimeline.gaps.length > 0 ? <section aria-label="录音暂停记录">
      <strong>暂停记录</strong>
      <p>原音只保留实际录到的声音；暂停间隔单独记录，回听时会接着播放。</p>
      <div className="ct-audio-tools">{pauseTimeline.gaps.map((gap, index) => <button
        key={`${gap.pausedAtMs}:${index}`} type="button" className="ct-action" disabled={!ready}
        title="定位到原音中的暂停位置，不自动播放" onClick={() => {
          const player = playerRef.current;
          if (!player || !ready) return;
          setLoop(false); player.currentTime = Math.min(duration, Math.max(0, gap.audioPositionMs / 1000));
          setPosition(player.currentTime);
        }}>
        {time(gap.audioPositionMs / 1000)} · {gap.durationMs == null ? '暂停后未确认继续'
          : `暂停 ${(Math.round(gap.durationMs / 10) / 100).toFixed(2)} 秒${gap.endedDuringPause ? '后结束' : '后继续'}`}
      </button>)}</div>
    </section> : null}
    <div className="ct-audio-tools" aria-label="片段循环回听">
      <button type="button" className="ct-action" disabled={!ready} onClick={() => mark('start')}>设为起点 A</button>
      <button type="button" className="ct-action" disabled={!ready || start == null} onClick={() => mark('end')}>设为终点 B</button>
      <button type="button" className="ct-action" disabled={!validRange} aria-pressed={loop}
        onClick={() => {
          if (!validRange) return;
          if (!loop && start != null && end != null && playerRef.current
            && (playerRef.current.currentTime < start || playerRef.current.currentTime >= end)) playerRef.current.currentTime = start;
          setRepeat(false); setLoop((value) => !value); setMessage('');
        }}>{loop ? '关闭 A–B 循环' : '开启 A–B 循环'}</button>
      <button type="button" className="ct-action" disabled={start == null} onClick={() => {
        setLoop(false); setStart(null); setEnd(null); setMessage('');
      }}>清除片段</button>
      {start != null ? <span>A {time(start)} · B {end == null ? '未设置' : time(end)}</span> : null}
    </div>
    {message ? <p role="status">{message}</p> : null}
    {memoryFailed ? <p role="status">本机未能保存回听位置；仍可播放，下次可能需要重新定位。</p> : null}
  </div>;
}
