import {useEffect,useRef,useState} from 'react';
import type {CompanionV1HostSession,CompanionV1Snapshot} from '../../core/src/companionV1';
import type {CompanionLibraryStateRequest,CompanionLibraryPurgeRequest,CompanionLibraryPurgeResult} from '../../core/src/libraryOrganization';

export function CompanionLibraryLifeActions({sessions,selection,setSelection,trash,blocked,draft,onSave,onPurge,onBusyChange}:{
 sessions:CompanionV1HostSession[];selection:Record<string,number>;setSelection:(v:Record<string,number>)=>void;
 trash:boolean;blocked:boolean;draft:boolean;onSave?:(request:CompanionLibraryStateRequest)=>Promise<CompanionV1Snapshot>;
 onPurge?:(request:CompanionLibraryPurgeRequest)=>Promise<CompanionLibraryPurgeResult>;onBusyChange?:(busy:boolean)=>void;
}){
 const [busy,setBusy]=useState(false);const active=useRef(false);const [message,setMessage]=useState('');
 const [pending,setPending]=useState<'trash'|'purge'|null>(null);
 const targets=Object.entries(selection).map(([sessionId,expectedRevision])=>({sessionId,expectedRevision}));
 const key=JSON.stringify(targets);useEffect(()=>setPending(null),[key,trash]);
 const ready=targets.length>0&&targets.length<=1000&&!blocked&&!busy&&!draft;
 const save=async(action:CompanionLibraryStateRequest['action'])=>{
  if(!ready||active.current||!onSave)return;active.current=true;setBusy(true);onBusyChange?.(true);setMessage('');setPending(null);
  try{await onSave({targets,action});setSelection({});setMessage(action==='trash'?`已将 ${targets.length} 场移入本机回收站，原音和设备数据保留，可恢复。`:action==='restore'?`已恢复 ${targets.length} 场录音；不会自动重新转写或生成纪要。`:action==='protect'?`已保护 ${targets.length} 场录音；解除前不能删除音频、文字或整场。`:`已解除 ${targets.length} 场录音的保护。`);}
  catch(e){setMessage(`未完成，选择仍保留：${e instanceof Error?e.message:String(e)}`);}
  finally{active.current=false;setBusy(false);onBusyChange?.(false);}
 };
 const purge=async()=>{
  if(!ready||active.current||!onPurge)return;active.current=true;setBusy(true);onBusyChange?.(true);setPending(null);setMessage('');
  try{const result=await onPurge({targets});
   setSelection(Object.fromEntries(targets.filter(t=>!result.deleted.includes(t.sessionId)).map(t=>[t.sessionId,t.expectedRevision])));
   setMessage(`已永久清除 ${result.deleted.length} 场本机录音。${result.failures.length?` ${result.failures.length} 场未完成，仍需核对：${result.failures.map(f=>f.message).join('；')}`:'设备上的录音未访问。'}${result.warning??''}`);
  }catch(e){setMessage(`永久清除未完成，选择仍保留：${e instanceof Error?e.message:String(e)}`);}
  finally{active.current=false;setBusy(false);onBusyChange?.(false);}
 };
 return <section aria-label="录音保护与回收站">
  <fieldset disabled={!ready}><legend>{trash?'回收站操作':'保护与删除所选录音'}</legend>
   {trash?<><button type="button" className="ct-action" disabled={!onSave} onClick={()=>void save('restore')}>恢复所选录音</button>
    <button type="button" className="ct-action ct-action-danger" disabled={!onPurge} onClick={()=>setPending('purge')}>永久清除所选录音</button></>:<>
    <button type="button" className="ct-action" disabled={!onSave} onClick={()=>void save('protect')}>保护所选录音</button>
    <button type="button" className="ct-action" disabled={!onSave} onClick={()=>void save('unprotect')}>解除所选保护</button>
    <button type="button" className="ct-action" disabled={!onSave} onClick={()=>setPending('trash')}>移入回收站</button></>}
  </fieldset>
  <p>{trash?'回收站仍占本机空间，恢复会保留原来的分类、重点、笔记和原音；永久清除无法撤销，另存的导出文件需自行管理。':'保护防止本机误删，不是音频加密。移入回收站只隐藏本机资料，不删除文件，也不确认消费设备录音。'}</p>
  {draft?<p>请先保存或撤销分类修改，再操作保护与回收站。</p>:null}
  {pending?<div role="alertdialog" aria-label={pending==='trash'?'确认移入回收站':'确认永久清除回收站录音'}>
   <strong>{pending==='trash'?`将所选 ${targets.length} 场移入本机回收站？`:`永久清除所选 ${targets.length} 场本机录音？`}</strong>
   <ul>{targets.slice(0,5).map(t=><li key={t.sessionId}>{sessions.find(s=>s.id===t.sessionId)?.title??t.sessionId}</li>)}</ul>
   {targets.length>5?<p>另有 {targets.length-5} 场已选录音。</p>:null}
   <p>{pending==='trash'?'可以恢复，设备上的录音保持不变。':'本机音频、文字、纪要、重点和笔记将永久清除，不能恢复。逐场失败会明确列出，不宣称整批成功；不连接或删除设备数据。'}</p>
   <button type="button" className="ct-action" disabled={busy} onClick={()=>setPending(null)}>保留内容</button>
   <button type="button" className="ct-action ct-action-danger" disabled={!ready} onClick={()=>pending==='trash'?void save('trash'):void purge()}>{pending==='trash'?'确认移入回收站':'确认永久清除'}</button>
  </div>:null}
  {message?<p role="status">{message}</p>:null}
 </section>;
}
