import {useEffect,useRef,useState} from 'react';
import {ArrowUpCircle,ChevronDown,FileArchive,RefreshCw} from 'lucide-react';
import './deviceUpdate.css';
export type UpdatePackage={id:string;firmwareVersion:number;resourceVersion:number;bytes:number;authentication:string;consistencyChecked:boolean};
type UpdateStatus={running:boolean;phase:string;address:string;name:string;accepted:number;total:number;message:string;canCancel:boolean;canVerify:boolean;prepared?:UpdatePackage;packageError?:string;cancelled?:boolean};
export function DeviceUpdate({address,busy,onCall,onPick,onRun,onRunningChange}:{address:string;busy:boolean;onCall:<T>(method:string,args?:object)=>Promise<T>;onPick:()=>Promise<UpdatePackage|null>;onRun:<T>(label:string,work:()=>Promise<T>)=>Promise<T|undefined>;onRunningChange:(running:boolean)=>void}){
 const [status,setStatus]=useState<UpdateStatus|null>(null),[error,setError]=useState(''),[notice,setNotice]=useState('');const alive=useRef(true),active=useRef(false),poll=useRef(false),notify=useRef(onRunningChange);notify.current=onRunningChange;
 const apply=(next:UpdateStatus)=>{if(!alive.current)return;setStatus(next);notify.current(next.running);};
 useEffect(()=>{alive.current=true;const read=async()=>{if(poll.current)return;poll.current=true;try{const next=await onCall<UpdateStatus>('deviceUpdateStatus');if(alive.current)apply(next);}catch(e){if(alive.current)setError(e instanceof Error?e.message:String(e));}finally{poll.current=false;}};void read();const timer=window.setInterval(()=>void read(),2000);return()=>{alive.current=false;window.clearInterval(timer);};},[onCall]);
 const perform=async(kind:'pick'|'start'|'cancel'|'verify')=>{
  if(active.current||busy)return;active.current=true;setError('');setNotice('');
  try{await onRun(kind==='pick'?'正在读取升级包':kind==='start'?'正在准备录音卡升级':kind==='cancel'?'正在停止传入':'正在核对升级结果',async()=>{
   try{
    if(kind==='pick'){const pack=await onPick();if(alive.current){if(pack){apply(await onCall<UpdateStatus>('deviceUpdateStatus'));setNotice('升级包已读取。确认设备和版本后，再开始升级。');}else setNotice('已取消选择，没有开始升级。');}}
    else{const next=await onCall<UpdateStatus>(kind==='start'?'startDeviceUpdate':kind==='verify'?'verifyDeviceUpdate':'cancelDeviceUpdate',{address,id:status?.prepared?.id});apply(next);if(next.cancelled&&alive.current)setNotice('已取消，没有开始升级。');}
   }catch(e){if(alive.current)setError(e instanceof Error?e.message:String(e));throw e;}
  });}finally{active.current=false;}
 };
 const pack=status?.prepared,percent=status?.total?Math.min(100,Math.floor(status.accepted*100/status.total)):0;
 return <details className="device-update"><summary><span><ArrowUpCircle size={16}/>录音卡升级</span><span className="update-summary-status">{status?.running?'进行中':status?.phase==='complete'?'已完成':'固件与资源'}<ChevronDown size={15}/></span></summary>
  <p>选择官方完整升级包。升级时保持录音卡供电，手机与录音卡保持靠近。</p>
  <button type="button" className="secondary" disabled={busy||!status||status.running} onClick={()=>void perform('pick')}><FileArchive size={15}/>选择升级包</button>
  {pack&&<div className="update-package"><span className="update-kicker">已选升级包</span><strong>程序 {pack.firmwareVersion} <span>／</span> 资源 {pack.resourceVersion}</strong><small>{(pack.bytes/1024/1024).toFixed(2)} MB · 完整固件与资源</small><p>文件完整性已核对，录音卡会在安装前验证签名。</p><button type="button" className="primary" disabled={busy||!!status?.running||!address} onClick={()=>void perform('start')}>开始升级</button>{!address&&<p>请先在上方连接要升级的录音卡。</p>}</div>}
  {status&&status.phase!=='idle'&&<div className="update-progress" role="status"><strong>{status.running?'当前任务':'上次任务'} · {status.name}</strong><p>{status.message||'结果待确认，请核对实际运行版本。'}</p>{status.phase==='transferring'&&<><progress value={status.accepted} max={status.total||1}/><small>{percent}% · 设备已确认接收 {(status.accepted/1024/1024).toFixed(2)} MB</small></>}{status.phase==='interrupted'&&<p>不会自动继续传入或重复安装。先核对实际版本，再决定下一步。</p>}
   {status.canCancel&&<button type="button" className="text-button" disabled={busy} onClick={()=>void perform('cancel')}>停止传入</button>}
   {status.canVerify&&<><button type="button" className="secondary" disabled={busy||!address||address!==status.address} onClick={()=>void perform('verify')}><RefreshCw size={14}/>核对上次升级结果</button>{address!==status.address&&<p>请先连接原录音卡：{status.name} · {status.address}</p>}</>}
  </div>}
  {(error||status?.packageError)&&<p role="alert" className="maintenance-error">{error||status?.packageError}</p>}{notice&&<p role="status" className="maintenance-notice">{notice}</p>}
  <p className="update-footnote">原录音保留。传入中断后需从头重试；设备已经开始安装时，请等待结果核对。</p>
 </details>;
}
