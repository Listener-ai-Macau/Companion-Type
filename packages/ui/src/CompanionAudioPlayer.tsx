import { useEffect, useState, type RefObject } from 'react';

const time = (seconds: number) => {
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60).toString().padStart(2, '0')}:${(value % 60).toString().padStart(2, '0')}`;
};

/** Playback changes only this authorized original; it never edits the recording. */
export function CompanionAudioPlayer({ src, playerRef, onError }: {
  src: string;
  playerRef: RefObject<HTMLAudioElement>;
  onError: () => void;
}) {
  const [duration, setDuration] = useState(0);
  const [position, setPosition] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [start, setStart] = useState<number | null>(null);
  const [end, setEnd] = useState<number | null>(null);
  const [loop, setLoop] = useState(false);
  const [message, setMessage] = useState('');
  const ready = Number.isFinite(duration) && duration > 0;
  const validRange = start != null && end != null && end - start >= 0.2 && end <= duration;

  useEffect(() => {
    const player = playerRef.current;
    return () => { player?.pause(); };
  }, [src, playerRef]);

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
    if (!player || !loop || !validRange || start == null || end == null) return;
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
        setDuration(value); player.playbackRate = speed; player.preservesPitch = true;
      }}
      onTimeUpdate={() => {
        const value = playerRef.current?.currentTime;
        if (value != null && Number.isFinite(value)) setPosition(value);
        if (!playerRef.current?.paused) rewindLoop();
      }}
      onPlay={rewindLoop}
      onEnded={() => {
        const player = playerRef.current;
        if (!player || !loop || !validRange || start == null) return;
        player.currentTime = start;
        void player.play().catch(() => { setLoop(false); setMessage('循环播放已暂停，请点击播放继续。'); });
      }}
      onError={() => { setLoop(false); onError(); }}>你的系统无法播放这段音频。</audio>
    <div className="ct-audio-tools">
      <button type="button" className="ct-action" disabled={!ready} onClick={() => skip(-10)}>后退 10 秒</button>
      <button type="button" className="ct-action" disabled={!ready} onClick={() => skip(10)}>前进 10 秒</button>
      <label>回听速度 <select aria-label="回听速度" value={speed} disabled={!ready}
        onChange={(event) => {
          const value = Number(event.target.value);
          const player = playerRef.current;
          if (!player || ![0.5, 0.75, 1, 1.25, 1.5, 2].includes(value)) return;
          player.preservesPitch = true; player.playbackRate = value; setSpeed(value);
        }}>{[0.5, 0.75, 1, 1.25, 1.5, 2].map((value) => <option key={value} value={value}>{value}×</option>)}</select></label>
      <span>{time(position)} / {time(duration)}</span>
    </div>
    <div className="ct-audio-tools" aria-label="片段循环回听">
      <button type="button" className="ct-action" disabled={!ready} onClick={() => mark('start')}>设为起点 A</button>
      <button type="button" className="ct-action" disabled={!ready || start == null} onClick={() => mark('end')}>设为终点 B</button>
      <button type="button" className="ct-action" disabled={!validRange} aria-pressed={loop}
        onClick={() => {
          if (!validRange) return;
          if (!loop && start != null && end != null && playerRef.current
            && (playerRef.current.currentTime < start || playerRef.current.currentTime >= end)) playerRef.current.currentTime = start;
          setLoop((value) => !value); setMessage('');
        }}>{loop ? '关闭 A–B 循环' : '开启 A–B 循环'}</button>
      <button type="button" className="ct-action" disabled={start == null} onClick={() => {
        setLoop(false); setStart(null); setEnd(null); setMessage('');
      }}>清除片段</button>
      {start != null ? <span>A {time(start)} · B {end == null ? '未设置' : time(end)}</span> : null}
    </div>
    {message ? <p role="status">{message}</p> : null}
  </div>;
}
