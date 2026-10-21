import {useEffect,useRef,useState} from 'react';

export type PetFindRequest={action:'start'|'stop'|'status';deviceId:string;token:string};
export type PetFindReport={deviceId:string;token:string;phase:'active'|'ended'|'stopped'|'rejected'|'other';volumePercent:number;message:string};
export function CompanionPetFind({deviceId,supported,blocked,muted,onFind}: {
  deviceId:string|null;supported:boolean;blocked:boolean;muted:boolean;
  onFind:(request:PetFindRequest)=>Promise<PetFindReport>;
}) {
  const [request,setRequest]=useState<{deviceId:string;token:string}|null>(null);
  const [report,setReport]=useState<PetFindReport|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const active=useRef(false);
  const epoch=useRef(0);
  useEffect(()=>{epoch.current++;setRequest(null);setReport(null);setError('');},[deviceId]);
  useEffect(()=>()=>{epoch.current++;},[]);
  const pending=Boolean(request && (!report || report.phase==='active'||report.phase==='other'));
  const send=async(action:PetFindRequest['action'],fresh=false)=>{
    if(active.current || !deviceId)return;
    const bound=(!fresh&&request)?request:{deviceId,token:crypto.randomUUID()};
    if(bound.deviceId!==deviceId)return;
    active.current=true;setBusy(true);setError('');
    const generation=epoch.current;
    // Preserve the same token after an uncertain send. Retrying cannot extend it.
    if(action==='start')setRequest(bound);
    if(fresh)setReport(null);
    try {
      const next=await onFind({...bound,action});
      if(generation!==epoch.current)return;
      if(next.deviceId!==deviceId || next.token!==bound.token)throw new Error('寻找结果与当前设备不一致，请重新读取设备状态。');
      setReport(next);
    } catch(e) {if(generation===epoch.current)setError(e instanceof Error?e.message:String(e));}
    finally {active.current=false;setBusy(false);}
  };
  return <section className="ct-pet-find" aria-label="找宠物">
    <div><strong>找宠物</strong><p>在附近发出几声短音，约 6 秒自动结束，保留设备原音量。</p></div>
    {!supported?<p className="ct-step-meta">连接支持寻找的联合固件后可用。</p>:<>
      {!pending?<button type="button" className="ct-action" disabled={busy||blocked||muted} onClick={()=>void send('start',true)}>{busy?'正在发送…':'让宠物响一下'}</button>:<div className="ct-action-row">
        <button type="button" className="ct-action" disabled={busy} onClick={()=>void send('stop')}>停止寻找</button>
        <button type="button" className="ct-action secondary" disabled={busy||blocked} onClick={()=>void send('status')}>查看状态</button>
        {error?<button type="button" className="ct-action secondary" disabled={busy||blocked||muted} onClick={()=>void send('start')}>重试本次寻找</button>:null}
      </div>}
      {muted&&!pending?<p className="ct-step-meta">宠物当前静音，请先在设备上调整音量。</p>:null}
      {blocked&&!pending?<p className="ct-step-meta">请先结束当前录音或设备操作。</p>:null}
    </>}
    {report?<p role="status">{report.message}</p>:null}
    {error?<p role="alert" className="ct-step-warn">{error}</p>:null}
  </section>;
}
