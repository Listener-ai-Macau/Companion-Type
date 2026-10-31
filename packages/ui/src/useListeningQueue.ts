import {useEffect,useRef,useState} from 'react';
import type {CompanionPauseTimeline} from './CompanionAudioPlayer';
export interface PreparedListening {sessionId:string;url:string;sourceIdentity?:string;pauseTimeline?:CompanionPauseTimeline|null;meetingTracks?:import('./meetingTrackPlayback').MeetingPlaybackTracks}
interface Row {id:string;title:string;identity:string;ready:boolean}
interface Entry extends Row {sourceIdentity:string}
interface Active {entry:Entry;from:string;token:number;phase:'selecting'|'preparing'|'playing'}
interface Config {
  rows:Row[];selectedId:string;disabled:boolean;hardBlocked:boolean;
  prepare?: (id:string)=>Promise<PreparedListening>;
  select:(id:string)=>void;
  ready:(entry:Entry,audio:PreparedListening,epoch:number)=>void;
  pause:()=>void;
}
/** Transient, explicit listening queue. URLs are never queued or persisted;
 * each original is re-authorized and hash-matched when its turn arrives. */
export function useListeningQueue(config:Config) {
  const live=useRef(config);live.current=config;
  const [items,setItems]=useState<Entry[]>([]);const itemRef=useRef(items);itemRef.current=items;
  const [active,setActive]=useState<Active|null>(null);const activeRef=useRef(active);activeRef.current=active;
  const generation=useRef(0);const adding=useRef(false);const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const stop=(note='连续播放已停止。')=>{
    generation.current++;activeRef.current=null;setActive(null);live.current.pause();setMessage(note);
  };
  const start=(entry:Entry)=>{
    const c=live.current;const row=c.rows.find(r=>r.id===entry.id);
    if(c.disabled||c.hardBlocked||!c.prepare||!row?.ready||row.identity!==entry.identity) {
      stop('这份原音已变化或暂不可回听；请核对后重新加入队列。');return;
    }
    const next:Active={entry,from:c.selectedId,token:++generation.current,phase:'selecting'};
    c.pause();activeRef.current=next;setActive(next);setMessage('正在准备队列中的原音…');
    if(c.selectedId!==entry.id)c.select(entry.id);
  };
  const add=async()=>{
    const c=live.current;const row=c.rows.find(r=>r.id===c.selectedId);
    if(adding.current||c.disabled||c.hardBlocked||!c.prepare||!row?.ready)return;
    if(itemRef.current.length>=50){setMessage('队列最多放50份原音，请先移除部分条目。');return;}
    adding.current=true;setBusy(true);setMessage('正在核对原音…');
    try {
      const audio=await c.prepare(row.id);const current=live.current;
      if(current.hardBlocked||current.selectedId!==row.id||current.rows.find(r=>r.id===row.id)?.identity!==row.identity)return;
      if(audio.sessionId!==row.id||!audio.url||!/^[a-f0-9]{64}$/.test(audio.sourceIdentity??''))throw new Error('没有取得这份原音的内容校验，请重新准备。');
      const entry={...row,sourceIdentity:audio.sourceIdentity!};
      if(itemRef.current.some(e=>e.id===row.id)) {setMessage('这场录音已在队列中；更换原音时请先移除旧条目。');return;}
      setItems(old=>[...old,entry]);setMessage('已加入队列；点击“开始连续播放”后才会出声。');
    } catch(e){setMessage(`未加入队列：${e instanceof Error?e.message:String(e)}`);}
    finally {adding.current=false;setBusy(false);}
  };
  useEffect(()=>{
    if(!active)return;
    const c=live.current;const row=c.rows.find(r=>r.id===active.entry.id);
    if(c.hardBlocked||!row?.ready||row.identity!==active.entry.identity) {stop('原音暂不可回听，连续播放已停止。');return;}
    if(c.selectedId!==active.entry.id) {
      if(active.phase!=='selecting'||c.selectedId!==active.from)stop('已切换会议，连续播放已停止。');
      return;
    }
    if(active.phase!=='selecting'||c.disabled||!c.prepare)return;
    const next={...active,phase:'preparing' as const};activeRef.current=next;setActive(next);
    void c.prepare(active.entry.id).then(audio=>{
      const latest=live.current;const current=latest.rows.find(r=>r.id===active.entry.id);
      if(generation.current!==active.token)return;
      if(latest.hardBlocked||latest.selectedId!==active.entry.id||!current?.ready||current.identity!==active.entry.identity
        ||audio.sessionId!==active.entry.id||audio.sourceIdentity!==active.entry.sourceIdentity||!audio.url) {
        stop('原音内容或选择已变化，未播放替换后的文件；请重新加入队列。');return;
      }
      const playing={...active,phase:'playing' as const};activeRef.current=playing;setActive(playing);
      latest.ready(active.entry,audio,active.token);setMessage(`正在连续回听：${current.title}`);
    }).catch(e=>{if(generation.current===active.token)stop(`连续播放已停止：${e instanceof Error?e.message:String(e)}`);});
  },[active?.phase,active?.token,config.selectedId,config.disabled,config.hardBlocked,config.rows.map(r=>`${r.id}:${r.identity}:${r.ready}`).join('\0')]);
  useEffect(()=>{
    if(!active||active.phase!=='selecting')return;
    const timer=setTimeout(()=>{if(generation.current===active.token)stop('没有切换到队列中的会议，请稍后重新播放。');},10000);
    return()=>clearTimeout(timer);
  },[active?.phase,active?.token]);
  useEffect(()=>()=>{generation.current++;},[]);
  useEffect(()=>{
    const ids=new Set(live.current.rows.map(r=>r.id));
    setItems(old=>{const remaining=old.filter(e=>ids.has(e.id));return remaining.length===old.length?old:remaining;});
  },[config.rows.map(r=>r.id).join('\0')]);
  return {items,active,busy,message,add,stop,
    start:()=>{if(itemRef.current[0])start(itemRef.current[0]);},
    remove:(id:string)=>{if(activeRef.current?.entry.id===id)stop();setItems(old=>old.filter(e=>e.id!==id));},
    clear:()=>{stop();setItems([]);},
    finished:(identity?:string)=>{
      const a=activeRef.current;if(!a||a.phase!=='playing'||identity!==a.entry.sourceIdentity)return;
      const remaining=itemRef.current.filter(e=>e.id!==a.entry.id);setItems(remaining);itemRef.current=remaining;
      if(remaining[0])start(remaining[0]);else stop('队列已播放完毕。');
    }};
}
