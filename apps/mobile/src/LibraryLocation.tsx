import {useEffect,useRef,useState} from 'react';
import {Archive,ArrowLeft,ChevronRight} from 'lucide-react';
import {libraryLabel,validateLibraryStatus,type LibraryStatus} from './libraryStatus';
import './libraryLocation.css';

/** Read-only location indicator; switching keeps the native library token guard. */
export function LibraryLocation({compact=false,revision,busy,receiving,onLoad,onActivate,onManage}:{compact?:boolean;revision:unknown;busy:boolean;receiving:boolean;onLoad:()=>Promise<LibraryStatus>;onActivate:(id:string,token:string)=>Promise<LibraryStatus|undefined>;onManage:()=>void}){
 const [state,setState]=useState<LibraryStatus|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[switching,setSwitching]=useState(false),[retry,setRetry]=useState(0);
 const request=useRef(0),acting=useRef(false),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;request.current++;};},[]);
 useEffect(()=>{
  const id=++request.current;setLoading(true);setError('');setState(null);
  void onLoad().then(value=>{if(id===request.current)setState(validateLibraryStatus(value));})
   .catch(e=>{if(id===request.current)setError(e instanceof Error?e.message:String(e));})
   .finally(()=>{if(id===request.current)setLoading(false);});
  return()=>{request.current++;};
 },[revision,retry]);
 const disabled=busy||receiving||loading||switching;
 const restore=async()=>{
  if(disabled||acting.current||!state||state.activeId==='original'||!state.libraries.some(item=>item.id==='original'))return;
  acting.current=true;setSwitching(true);setError('');const id=++request.current;
  try{const result=await onActivate('original',state.token);if(result&&id===request.current){const next=validateLibraryStatus(result);if(next.activeId!=='original')throw new Error('原有资料尚未打开，请重新读取后检查。');setState(next);}}
  catch(e){if(id===request.current)setError(e instanceof Error?e.message:String(e));}
  finally{acting.current=false;if(mounted.current)setSwitching(false);}
 };
 if(loading)return <div className="library-location-loading" role="status">正在确认当前资料…</div>;
 if(error)return <section className="library-location-error" aria-label="当前资料位置"><p role="alert">{error}</p><button type="button" disabled={busy||receiving||switching} onClick={()=>setRetry(value=>value+1)}>重新读取资料信息</button></section>;
 if(!state)return null;
 const current=state.libraries.find(item=>item.id===state.activeId)!;
 if(state.activeId==='original'&&state.libraries.length===1)return null;
 const restored=state.activeId!=='original';
 return <section className={`library-location${restored?' library-location-restored':''}${compact?' library-location-compact':''}`} aria-label="当前资料位置">
  <div className="library-location-heading"><span className="library-location-icon" aria-hidden="true"><Archive size={18}/></span><div><span>当前资料</span><strong>{libraryLabel(current)}</strong></div></div>
  {restored&&<p>你正在查看恢复的备份，手机原有资料仍单独保留。</p>}
  <div className="library-location-actions">{restored&&state.libraries.some(item=>item.id==='original')&&<button type="button" className="library-return-original" disabled={disabled} onClick={()=>void restore()}><ArrowLeft size={15} aria-hidden="true"/>{switching?'正在打开原有资料…':'返回原有资料'}</button>}<button type="button" className="library-manage-backups" disabled={busy||switching} onClick={onManage}>备份与恢复<ChevronRight size={14} aria-hidden="true"/></button></div>
  {restored&&receiving&&<small role="status">正在接收录音，完成或暂停接收后可切换资料。</small>}
 </section>;
}
