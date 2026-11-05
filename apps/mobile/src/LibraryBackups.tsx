import {useEffect,useState} from 'react';
import {Archive,Download,RotateCcw} from 'lucide-react';
export type LibraryStatus={version:number;activeId:string;previousId?:string;token:string;libraries:Array<{id:string;restoredAt:number}>};
export function LibraryBackups({busy,receiving,onLoad,onArchive,onActivate}:{busy:boolean;receiving:boolean;onLoad:()=>Promise<LibraryStatus>;onArchive:(kind:'backup'|'restore',token:string)=>Promise<LibraryStatus|undefined>;onActivate:(id:string,token:string)=>Promise<LibraryStatus|undefined>}){
 const [state,setState]=useState<LibraryStatus|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
 const valid=(v:LibraryStatus)=>{if(v.version!==1||!v.token||!Array.isArray(v.libraries)||!v.libraries.some(x=>x.id===v.activeId))throw new Error('当前资料信息未能确认，请重新读取。');return v;};
 const load=async()=>{setLoading(true);setError('');try{setState(valid(await onLoad()));}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setLoading(false);}};
 useEffect(()=>{let active=true;void onLoad().then(value=>{if(active)setState(valid(value));}).catch(e=>{if(active)setError(e instanceof Error?e.message:String(e));}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[]);
 const label=(item:{id:string;restoredAt:number})=>item.id==='original'?'原有资料':`${new Intl.DateTimeFormat('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(item.restoredAt))} 恢复的资料`;
 const disabled=busy||loading||receiving||!state||!!error;
 const archive=async(kind:'backup'|'restore')=>{if(!state||disabled)return;const result=await onArchive(kind,state.token);if(result)setState(valid(result));};
 const activate=async(id:string)=>{if(!state||disabled)return;const result=await onActivate(id,state.token);if(result)setState(valid(result));};
 return <section className="library-backups" aria-label="本机资料备份与恢复"><div className="library-backups-heading"><span className="library-backups-icon"><Archive size={19}/></span><div><h2>让资料留在你手里</h2><p>本机备份与恢复</p></div></div>
  <p className="library-backups-intro">备份原录音、转写、纪要、人工事项、译文及历史版本。不包含模型、服务密钥和设备配对信息。</p>
  {loading&&<p role="status">正在读取本机资料…</p>}{error&&<div className="library-backups-error" role="alert"><p>{error}</p><button type="button" disabled={busy||loading} onClick={()=>void load()}>重新读取资料信息</button></div>}
  {state&&!error&&<p className="library-backups-current">当前：{label(state.libraries.find(x=>x.id===state.activeId)!)}</p>}
  {receiving&&<p className="library-backups-wait" role="status">正在接收录音。请等接收完成或暂停后再备份、恢复或切换资料。</p>}
  <div className="library-backups-actions"><button type="button" className="primary" disabled={disabled} onClick={()=>void archive('backup')}><Download size={16}/>保存整份备份</button><button type="button" className="secondary" disabled={disabled} onClick={()=>void archive('restore')}><RotateCcw size={16}/>从备份恢复</button></div>
  <p className="library-backups-note">备份文件包含录音和会议文字，请保存到你信任的位置。恢复会先校验文件，保留手机原有资料，不会自动连接录音卡。</p>
  {state&&state.libraries.length>1&&<details className="library-backups-retained"><summary>已保留的资料 · {state.libraries.length} 份</summary><p>每次恢复都保留原有资料，可在这里切回；切换不会删除内容。</p>{state.libraries.map(item=><div key={item.id}><span>{label(item)}</span>{item.id===state.activeId?<small>正在使用</small>:<button type="button" disabled={disabled} onClick={()=>void activate(item.id)}>打开这份资料</button>}</div>)}</details>}
 </section>;
}
