import {useEffect,useRef,useState} from 'react';
import {ChevronDown,RefreshCw,Settings2} from 'lucide-react';
import './deviceMaintenance.css';

export type MaintenanceStatus={address:string;name:string;operation:string;cancelled?:boolean;settingsSaved:boolean;defaultSettings:boolean;radioEnabled:boolean;bondCountValid:boolean;bonds:number};
export function DeviceMaintenance({address,name,busy,onCall,onRun,onPairingsCleared}:{address:string;name:string;busy:boolean;onCall:<T>(method:string,args?:object)=>Promise<T>;onRun:<T>(label:string,work:()=>Promise<T>)=>Promise<T|undefined>;onPairingsCleared:()=>void}){
 const [status,setStatus]=useState<MaintenanceStatus|null>(null),[notice,setNotice]=useState(''),[error,setError]=useState('');const active=useRef(false),epoch=useRef(0);
 useEffect(()=>{epoch.current++;setStatus(null);setNotice('');setError('');return()=>{epoch.current++;};},[address]);
 const perform=async(operation:'query'|'openPairing'|'restoreSettings'|'clearPairings')=>{
  if(busy||active.current)return;active.current=true;const generation=epoch.current;setError('');setNotice('');
  try{await onRun(operation==='query'?'正在读取设备状态':operation==='restoreSettings'?'正在恢复录音卡设置':operation==='clearPairings'?'正在处理录音卡配对':'正在打开配对窗口',async()=>{
   try{const result=await onCall<MaintenanceStatus>('deviceMaintenance',{address,operation});
    if(generation!==epoch.current)return;
    if(result.address!==address)throw Error('设备已变化，请重新选择录音卡。');
    if(result.cancelled){setNotice('已取消，设备设置和录音保持。');return;}
    setStatus(result);
    if(operation==='clearPairings'){setNotice('录音卡的配对信息已清除。请在系统蓝牙中忘记旧配对，再搜索连接；原录音保留。');onPairingsCleared();}
    else if(operation==='restoreSettings')setNotice('设备设置已恢复，原录音保留。');
    else if(operation==='openPairing')setNotice('配对窗口已打开，请在另一台手机上搜索并确认配对。');
    else setNotice('设备状态已更新。');
   }catch(e){if(generation===epoch.current)setError(e instanceof Error?e.message:String(e));throw e;}
  });}finally{active.current=false;}
 };
 return <details className="device-maintenance"><summary><span><Settings2 size={16}/>录音卡维护</span><ChevronDown size={15}/></summary>
  <p>当前设备：{name}。这些操作针对录音卡；手机里已保存的资料保留。</p>
  <button type="button" className="secondary" disabled={busy} onClick={()=>void perform('query')}><RefreshCw size={14}/>读取设备状态</button>
  {status&&<dl><div><dt>设备设置</dt><dd>{status.defaultSettings?'默认设置':'已保存的设置'}{!status.settingsSaved?' · 保存状态待确认':''}</dd></div><div><dt>已保存配对</dt><dd>{status.bondCountValid?`${status.bonds} 台设备`:'暂不可确认'}</dd></div></dl>}
  <div className="maintenance-actions"><button type="button" disabled={busy} onClick={()=>void perform('openPairing')}>连接另一台手机</button><button type="button" disabled={busy} onClick={()=>void perform('restoreSettings')}>恢复设备设置</button><button type="button" className="maintenance-destructive" disabled={busy} onClick={()=>void perform('clearPairings')}>清除录音卡配对</button></div>
  <p className="maintenance-help">恢复设置和清除配对前会显示确认。录音或接收正在进行时，请先完成当前任务。</p>
  {notice&&<p role="status" className="maintenance-notice">{notice}</p>}{error&&<p role="alert" className="maintenance-error">{error}<button type="button" disabled={busy} onClick={()=>void perform('query')}>重新读取状态</button></p>}
 </details>;
}
