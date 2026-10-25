import {operationErrorText} from './operationFailure';
import { useEffect, useRef, useState } from 'react';
export type CompanionDesktopUpdateStatus = { phase:string;message:string;currentVersion:string;availableVersion?:string|null;downloadedBytes:number;totalBytes?:number|null };
export function CompanionDesktopUpdate({ blocked, unsaved, onStatus, onCheck, onDownload, onCancel, onInstall }: {
  blocked:boolean;unsaved:boolean;onStatus:()=>Promise<CompanionDesktopUpdateStatus>;
  onCheck:()=>Promise<CompanionDesktopUpdateStatus>;onDownload:()=>Promise<CompanionDesktopUpdateStatus>;
  onCancel:()=>Promise<void>;onInstall:()=>Promise<void>;
}) {
  const [status,setStatus]=useState<CompanionDesktopUpdateStatus|null>(null);
  const [busy,setBusy]=useState(false);const [error,setError]=useState<string|null>(null);
  const [confirmed,setConfirmed]=useState(false);const active=useRef(false);
  useEffect(()=>{setConfirmed(false);},[unsaved,status?.availableVersion]);
  useEffect(()=>{let gone=false;void onStatus().then(s=>{if(!gone)setStatus(s);}).catch(()=>{});return()=>{gone=true;};},[onStatus]);
  const progressing=status?.phase==='downloading'||status?.phase==='checking';
  useEffect(()=>{
    if(!busy&&!progressing)return;
    let gone=false,timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{const s=await onStatus();if(!gone)setStatus(s);}catch{}finally{if(!gone)timer=setTimeout(()=>void poll(),750);}};
    timer=setTimeout(()=>void poll(),750);return()=>{gone=true;clearTimeout(timer);};
  },[busy,progressing,onStatus]);
  const run=async(work:()=>Promise<CompanionDesktopUpdateStatus|void>)=>{
    if(active.current)return;active.current=true;setBusy(true);setError(null);setConfirmed(false);
    try{const result=await work();if(result)setStatus(result);}catch(error){setError(operationErrorText(error,'update'));try{setStatus(await onStatus());}catch{}}
    finally{active.current=false;setBusy(false);}
  };
  const percent=status?.totalBytes?Math.min(100,Math.floor(status.downloadedBytes/status.totalBytes*100)):null;
  return <section className="ct-desktop-update" aria-label="Companion Type 软件更新">
    <div><strong>Companion Type 更新</strong><p>{status?.phase==='failed'||status?.phase==='error'?operationErrorText(status.message,'update'):status?.message??'可手动检查正式软件更新。'}{status?.currentVersion?` 当前版本 ${status.currentVersion}。`:''}</p>
      {status?.availableVersion?<p>可用版本 {status.availableVersion}</p>:null}
      {progressing?<p role="status">{status?.phase==='downloading'?`正在下载${percent!==null?` ${percent}%`:''}`:'正在检查发布'}</p>:null}
      {error?<p role="alert">{error}</p>:null}
      {unsaved?<p>先保存或取消尚未保存的编辑，再安装更新。</p>:blocked&&!busy?<p>结束当前录音或操作后，再下载和安装更新。</p>:null}
    </div>
    <div className="ct-update-actions">
      <button type="button" className="ct-action" disabled={busy} onClick={()=>void run(onCheck)}>检查软件更新</button>
      {status?.availableVersion&&status.phase!=='ready'&&!progressing?<button type="button" className="ct-action" disabled={busy||blocked}
        onClick={()=>void run(onDownload)}>下载更新</button>:null}
      {status?.phase==='downloading'?<button type="button" className="ct-text-button" onClick={()=>void onCancel().catch(()=>setError('取消请求未完成，请重试。'))}>取消下载</button>:null}
      {status?.phase==='ready'?<><label><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)} disabled={busy||blocked||unsaved}/>
        我已保存修改，安装时允许软件关闭</label>
        <button type="button" className="ct-action" disabled={!confirmed||busy||blocked||unsaved} onClick={()=>void run(onInstall)}>安装更新</button></>:null}
    </div>
  </section>;
}
