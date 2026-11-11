import {useEffect,useRef,useState} from 'react';
import {FileInput,CheckCircle2,ChevronDown} from 'lucide-react';
import './incomingFiles.css';

export type IncomingFile={id:string;name:string;mime:string;bytes:number;kind:'media'|'document'|'image'|'unsupported';state:'ready'|'attempting'|'complete'|'failed';message?:string;key?:string;libraryId?:string;targetTitle?:string};
export type IncomingFilesStatus={rows:IncomingFile[];libraryId:string;libraryToken:string;libraryLabel:string;running:boolean};
export type IncomingTarget={key:string;title:string};
export function IncomingFilesPanel({busy,adapter,onChanged,onOpen}:{busy:boolean;adapter:{list:()=>Promise<IncomingFilesStatus>;targets:()=>Promise<IncomingTarget[]>;import:(request:{id:string;key?:string;libraryToken:string})=>Promise<IncomingFilesStatus>;remove:(id:string)=>Promise<IncomingFilesStatus>;cancel?:(id:string)=>Promise<void>};onChanged:(status:IncomingFilesStatus)=>void;onOpen:(key:string)=>void}){
 const [value,setValue]=useState<IncomingFilesStatus|null>(null),[expanded,setExpanded]=useState(true),[targets,setTargets]=useState<IncomingTarget[]>([]),[choices,setChoices]=useState<Record<string,string>>({}),[working,setWorking]=useState(''),[cancelling,setCancelling]=useState(''),[error,setError]=useState(''),[targetError,setTargetError]=useState(''),[refresh,setRefresh]=useState(0);
 const current=useRef(adapter),changed=useRef(onChanged),previous=useRef('');current.current=adapter;changed.current=onChanged;
 useEffect(()=>{let alive=true,timer:number|undefined;const poll=async()=>{try{const next=await current.current.list();if(!alive)return;setValue(next);const complete=next.rows.filter(row=>row.state==='complete').map(row=>row.id).join('|');if(previous.current&&complete!==previous.current)changed.current(next);previous.current=complete||'none';}catch(e){if(alive)setError(e instanceof Error?e.message:String(e));}finally{if(alive)timer=window.setTimeout(()=>void poll(),2000);}};const receive=()=>{window.clearTimeout(timer);void poll();};window.addEventListener('companion-incoming',receive);void poll();return()=>{alive=false;window.clearTimeout(timer);window.removeEventListener('companion-incoming',receive);};},[refresh]);
 const completedKey=value?.rows.filter(row=>row.state==='complete').map(row=>row.id).join('|');
 const token=value?.libraryToken,hasAttachments=!!value?.rows.some(row=>(row.kind==='document'||row.kind==='image')&&row.state!=='complete');
 useEffect(()=>{let alive=true;setTargets([]);setTargetError('');if(hasAttachments)void current.current.targets().then(rows=>{if(alive)setTargets(rows);}).catch(e=>{if(alive)setTargetError(e instanceof Error?e.message:String(e));});return()=>{alive=false;};},[token,hasAttachments,completedKey,refresh]);
 useEffect(()=>setChoices({}),[token]);
 async function act(row:IncomingFile,remove=false){
  if(!value||busy||working)return;setWorking(row.id);setError('');
  try{const next=remove?await current.current.remove(row.id):await current.current.import({id:row.id,key:row.key||choices[row.id]||undefined,libraryToken:value.libraryToken});setValue(next);onChanged(next);}
  catch(e){setError(e instanceof Error?e.message:String(e));}finally{setWorking('');}
 }
 useEffect(()=>{if(!value?.running)setCancelling('');},[value?.running]);
 async function cancel(row:IncomingFile){if(!adapter.cancel||cancelling)return;setCancelling(row.id);try{await adapter.cancel(row.id);}catch(e){setError(e instanceof Error?e.message:String(e));setCancelling('');}}
 if(!value?.rows.length&&!error)return null;
 const pending=value?.rows.filter(row=>row.state!=='complete').length||0,saved=(value?.rows.length||0)-pending;
 return <section className="incoming-files" aria-label="接收外部文件">
  <div className="incoming-files-heading"><FileInput size={20} aria-hidden="true"/><div><strong>从其他应用收到文件</strong><p>{pending?pending+' 项待接收'+(saved?' · '+saved+' 项已保存':'')+' · 确认去向后保存原件':saved+' 项已保存 · 可打开所属录音'}</p></div><button type="button" className="text-button" aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)}><ChevronDown size={17}/>{expanded?'收起':'展开'}</button></div>
  {expanded&&<>
   {pending>0&&<p className="incoming-files-policy">保存至：<strong>{value?.libraryLabel||'待读取资料库'}</strong>。音视频存为新录音，文档和图片需选择所属会议。待接收文件尚未保存；来源权限失效时请重新分享。不自动转写或上传。</p>}
   {value?.rows.map(row=>{
    const wrongLibrary=!!row.libraryId&&row.libraryId!==value.libraryId,complete=row.state==='complete';
    const active=working===row.id||row.state==='attempting'&&value.running,needTarget=row.kind==='document'||row.kind==='image';
    return <article className={'incoming-file'+(complete?' incoming-file-complete':'')} key={row.id}>
     <div className="incoming-file-content">
      <div className="incoming-file-title">{complete&&<CheckCircle2 size={17} aria-hidden="true"/>}<strong>{row.name}</strong><span>{row.kind==='media'?'音视频':row.kind==='document'?'文档':row.kind==='image'?'图片':'暂不支持'}{row.bytes>=0?' · '+(row.bytes/1024/1024>=1?(row.bytes/1024/1024).toFixed(1)+' MB':Math.ceil(row.bytes/1024)+' KB'):''}</span></div>
      {row.targetTitle&&<p className="incoming-file-destination">{complete?'已保存至：':'已指定：'}{row.targetTitle}</p>}
      {wrongLibrary&&<p role="status">此项属于另一资料库，请先在备份设置中切回原资料库继续。</p>}
      {needTarget&&!row.key&&!complete&&<label className="incoming-file-target">所属会议<select aria-label={'为'+row.name+'选择所属会议'} value={choices[row.id]||''} disabled={busy||!!working} onChange={e=>setChoices(old=>({...old,[row.id]:e.target.value}))}><option value="">选择一场会议…</option>{targets.map(target=><option key={target.key} value={target.key}>{target.title}</option>)}</select>{targets.length===0&&!targetError&&<span>当前资料库没有可用录音，请先导入音视频或接收录音，再附加材料。</span>}</label>}
      {!complete&&row.message&&<p className={row.state==='failed'?'incoming-file-error':''} role="status">{row.message}</p>}
      {row.kind==='unsupported'&&<p>支持常见音视频、PDF、DOCX、XLSX、PPTX、TXT、MD、CSV，以及JPEG、PNG、WebP。</p>}
     </div>
     <div className="incoming-file-actions">
      {active&&row.kind==='media'&&adapter.cancel&&<button type="button" className="secondary" disabled={!!cancelling} onClick={()=>void cancel(row)}>{cancelling===row.id?'正在取消…':'取消此次导入'}</button>}
      {complete?<button type="button" className="secondary" aria-label="打开所属录音" disabled={busy||!!working||wrongLibrary||!row.key} onClick={()=>row.key&&onOpen(row.key)}>打开录音</button>:row.kind!=='unsupported'&&<button type="button" className="primary" disabled={busy||!!working||active||value.running||wrongLibrary||needTarget&&!row.key&&!choices[row.id]} onClick={()=>void act(row)}>{active?'正在接收…':row.state==='failed'?'在原目标核对并重试':row.kind==='media'?'存为新录音':'保存到所选会议'}</button>}
      <button type="button" className="text-button" aria-label={complete?'收起此条记录':'移除待接收项'} disabled={busy||!!working||active} onClick={()=>void act(row,true)}>{complete?'收起':'移除待接收项'}</button>
     </div>
    </article>;
   })}
   {hasAttachments&&<button type="button" className="text-button" disabled={!!working} onClick={()=>setRefresh(v=>v+1)}>重新读取资料库与所属会议</button>}
   {targetError&&<p className="incoming-file-error" role="alert">{targetError}</p>}{error&&<p className="incoming-file-error" role="alert">{error}</p>}{(error||targetError)&&<button type="button" className="secondary" disabled={!!working} onClick={()=>{setError('');setRefresh(v=>v+1);}}>重新读取接收清单</button>}
   <p className="incoming-files-footnote">{pending?'移除这里只清理接收清单，不删除来源文件或已保存内容。音视频导入进度也可在资料库或系统通知中查看。':'收起记录不会删除已保存内容。来源应用中的原文件保持不变。'}</p>
  </>}
 </section>;
}
