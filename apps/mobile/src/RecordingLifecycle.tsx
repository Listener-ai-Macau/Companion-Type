import {useEffect,useRef,useState} from 'react';
import {Shield,Trash2,RotateCcw,ChevronDown} from 'lucide-react';

export type RecordingLife={key:string;revision:number;protected:boolean;trashedAt:number;purging:boolean;title?:string};
export type RecordingLifeRequest={key:string;revision:number;libraryToken:string;action:'protect'|'unprotect'|'trash'|'restore'|'purge'};
export type RecordingLifeResult=Partial<RecordingLife>&{cancelled?:boolean;purged?:boolean;retainedUnassigned?:number;cleanupWarning?:boolean};
export type RecordingTrash={rows:RecordingLife[];problems:number;libraryToken:string};

export function RecordingManagement({life,libraryToken,title,busy,onChange}:{life:RecordingLife;libraryToken:string;title:string;busy:boolean;onChange:(request:RecordingLifeRequest)=>Promise<RecordingLifeResult>}){
 const [message,setMessage]=useState(''),[pending,setPending]=useState(false);const active=useRef(false),alive=useRef(true);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const change=async(action:'protect'|'unprotect'|'trash')=>{
  if(active.current||busy)return;
  if(action==='trash'&&!window.confirm(`将“${title}”移入本机回收站？\n原音与会议资料仍保留，可恢复；不会删除录音卡内容。`))return;
  active.current=true;setPending(true);setMessage('');
  try{await onChange({key:life.key,revision:life.revision,libraryToken,action});if(alive.current)setMessage(action==='protect'?'已保护，解除前不能移入回收站或永久清除。':action==='unprotect'?'已解除保护。':'已移入本机回收站，可恢复。');}
  catch(error){if(alive.current)setMessage(error instanceof Error?error.message:String(error));}
  finally{active.current=false;if(alive.current)setPending(false);}
 };
 return <details className="recording-management"><summary><span>录音管理{life.protected?' · 已保护':''}</span><ChevronDown size={15} aria-hidden="true"/></summary>
  <p className="hint">保护可防止误删。移入回收站保留原音、转写、纪要和材料，不释放存储空间。</p>
  <div className="buttons"><button className="secondary" disabled={busy||pending} onClick={()=>void change(life.protected?'unprotect':'protect')}><Shield size={15}/>{life.protected?'解除保护':'保护录音'}</button>
   <button className="secondary" disabled={busy||pending||life.protected} onClick={()=>void change('trash')}><Trash2 size={15}/>移入本机回收站</button></div>
  {message&&<p role="status" className="hint">{message}</p>}
 </details>;
}

export function RecordingRecycleBin({busy,revision,onLoad,onChange}:{busy:boolean;revision:unknown;onLoad:()=>Promise<RecordingTrash>;onChange:(request:RecordingLifeRequest)=>Promise<RecordingLifeResult>}){
 const [opened,setOpened]=useState(false),[value,setValue]=useState<RecordingTrash|null>(null),[loading,setLoading]=useState(false),[working,setWorking]=useState(false),[message,setMessage]=useState('');
 const generation=useRef(0),active=useRef(false),alive=useRef(true),loadRef=useRef(onLoad);loadRef.current=onLoad;
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;generation.current++;};},[]);
 async function load(){const id=++generation.current;setLoading(true);try{const result=await loadRef.current();if(alive.current&&id===generation.current)setValue(result);}catch(error){if(alive.current&&id===generation.current)setMessage(error instanceof Error?error.message:String(error));}finally{if(alive.current&&id===generation.current)setLoading(false);}}
 useEffect(()=>{if(opened){setValue(null);setMessage('');void load();}return()=>{generation.current++;};},[opened,revision]);
 async function change(row:RecordingLife,action:'restore'|'purge'){
  if(!value||active.current||busy||loading)return;active.current=true;setWorking(true);setMessage('');
  try{
   const result=await onChange({key:row.key,revision:row.revision,libraryToken:value.libraryToken,action});
   if(!alive.current)return;
   await load();
   if(alive.current)setMessage(result.cancelled?'已取消，回收站资料仍保留。':action==='restore'?'已恢复到录音库，原音与会议资料保留。':`已清除当前资料库中可确认归属的录音与会议资料。${result.retainedUnassigned?'无法确认归属的损坏副本仍保留。':''}${result.cleanupWarning?'清除记录尚未整理完成，请刷新核对。':''}`);
  }catch(error){if(alive.current){await load();if(alive.current)setMessage(error instanceof Error?error.message:String(error));}}
  finally{active.current=false;if(alive.current)setWorking(false);}
 }
 return <details className="recording-recycle-bin" onToggle={event=>setOpened(event.currentTarget.open)}>
  <summary><Trash2 size={16}/>本机回收站</summary>
  <p className="hint">移入后仍占用空间，可恢复。永久清除会再次核对并弹出确认；录音卡、其他资料库、已导出副本和应用临时缓存不在范围内。</p>
  <button className="text-button" disabled={busy||loading||working} onClick={()=>void load()}>刷新回收站</button>
  {loading&&<p role="status" className="hint">正在读取回收站…</p>}
  {value&&!loading&&value.rows.length===0&&<p className="hint">回收站为空。</p>}
  {!!value?.problems&&<p role="alert" className="message error">有 {value.problems} 项管理资料无法读取，原文件仍保留，请先备份并检查。</p>}
  {value?.rows.map(row=><article className="recycle-item" key={row.key}><strong>{row.title||'未命名录音'}</strong><p className="hint">{new Date(row.trashedAt).toLocaleString()}{row.purging?' · 上次清除未完成，部分文件可能已移除，不能再恢复。':''}</p>
   <div className="buttons"><button className="secondary" disabled={busy||loading||working||row.purging} onClick={()=>void change(row,'restore')}><RotateCcw size={15}/>恢复录音</button>
    <button className="secondary" disabled={busy||loading||working} onClick={()=>void change(row,'purge')}>{row.purging?'继续核对清除':'永久清除…'}</button></div></article>)}
  {message&&<p role="status" className="hint">{message}</p>}
 </details>;
}
