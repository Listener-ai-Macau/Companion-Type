import {useEffect,useMemo,useRef,useState} from 'react';
import {invoke} from '@tauri-apps/api/core';
import {AudioDerivationEditor,type AudioEditAdapter,type AudioEditHostProps,type AudioEditStatus} from '../../../packages/ui/src/AudioDerivationEditor';
import './audioEditing.css';
const changed=()=>window.dispatchEvent(new Event('companion-audio-edit-changed'));
const command=<T,>(action:string,request:object={})=>invoke<T>('control_companion_audio_edit',{action,request});
export function WindowsAudioEditor(p:AudioEditHostProps){
 const [token,setToken]=useState(''),[error,setError]=useState(''),[dirty,setDirty]=useState(false),[reset,setReset]=useState(0),job=useRef('');
 useEffect(()=>{let active=true;void command<{libraryToken:string}>('context').then(r=>{if(active)setToken(r.libraryToken);}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;p.onDirty?.(false);};},[p.contextId,reset]);
 const adapter=useMemo<AudioEditAdapter>(()=>({
  sources:keys=>command('sources',{keys}),start:async request=>{const r=await command<{id:string}>('start',request);job.current=r.id;changed();return r;},
  status:async()=>{const s=await command<AudioEditStatus>('status');job.current=s.id||'';return s;},
  retry:async id=>{const r=await command('retry',{id});changed();return r;},
  cancel:()=>{void command('cancel',{id:job.current}).then(changed).catch(e=>setError(String(e)));},
  provenance:()=>command('provenance',{sessionId:p.contextId}),
  playSource:async index=>{const target=await command<{sessionId:string;positionMs:number}>('sourceTarget',{sessionId:p.contextId,index});await p.onSource(target.sessionId,target.positionMs);}
 }),[p.contextId,p.onSource]);
 return <div className="ct-audio-edit-panel">
  {token?<AudioDerivationEditor key={p.contextId+':'+reset} {...p} libraryToken={token} adapter={adapter} onDirty={value=>{setDirty(value);p.onDirty?.(value);}}/>:<p role="status">{error||'正在准备本机录音编辑…'}</p>}
  {dirty?<div className="ct-audio-edit-draft" role="status"><p>录音编辑尚未保存。请先另存成品，或放弃本次编辑后离开。</p><button type="button" className="ct-action" onClick={()=>{p.onDirty?.(false);setDirty(false);setReset(v=>v+1);}}>放弃本次编辑</button></div>:null}
  {token&&error?<p role="alert">{error}</p>:null}
 </div>;
}
export function WindowsAudioEditNotice({onChanged}:{onChanged:()=>void}){
 const [status,setStatus]=useState<AudioEditStatus|null>(null),[error,setError]=useState(''),wasRunning=useRef(false),refresh=useRef(onChanged);refresh.current=onChanged;
 useEffect(()=>{let active=true,timer:number|undefined;const poll=async()=>{try{const s=await command<AudioEditStatus>('status');if(!active)return;setStatus(s);
   if(s.running){wasRunning.current=true;timer=window.setTimeout(()=>void poll(),700);}else if(wasRunning.current){wasRunning.current=false;refresh.current();}
  }catch(e){if(active)setError(String(e));}};
  const update=()=>{window.clearTimeout(timer);void poll();};window.addEventListener('companion-audio-edit-changed',update);void poll();
  return()=>{active=false;window.clearTimeout(timer);window.removeEventListener('companion-audio-edit-changed',update);};
 },[]);
 if(!status?.id||!status.running&&!status.retryAvailable)return error?<p className="ct-step-meta" role="alert">{error}</p>:null;
 return <aside className="ct-audio-edit-notice" aria-label="录音整理任务"><div><strong>{status.running?'正在本机整理录音':'录音整理可以继续'}</strong><p>{status.message}</p><small>已保存 {status.completed||0} / {status.totalOutputs||0} 份；原录音保留。</small>{error?<p role="alert">{error}</p>:null}</div>
  <button type="button" className="ct-action" onClick={()=>void command(status.running?'cancel':'retry',{id:status.id}).then(changed).catch(e=>setError(String(e)))}>{status.running?(status.state==='committing'?'本份保存后停止':'取消剩余处理'):'核对并继续剩余片段'}</button>
  {!status.running?<button type="button" className="ct-action" onClick={()=>void command('dismiss',{id:status.id}).then(()=>{setStatus(null);changed();}).catch(e=>setError(String(e)))}>结束这项整理</button>:null}
 </aside>;
}
