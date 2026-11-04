import {operationErrorText} from './operationFailure';
import { Pause, RefreshCw } from 'lucide-react';
import {useRef,useState} from 'react';

export type RecordingSyncStatus = {
  jobId: string | null;
  deviceId: string | null;
  phase: 'idle' | 'receiving' | 'saving' | 'reclaiming' | 'paused' | 'blocked';
  recordingId: number;
  receivedBytes: number;
  totalBytes: number;
  pauseRequested: boolean;
  error?: string;
};

export function CompanionRecordingSync({ status, pauseBusy, resumeBlocked, recoveryDeviceId, onPause, onResume, onRepair }: {
  status: RecordingSyncStatus | null;
  pauseBusy: boolean;
  resumeBlocked: boolean;
  recoveryDeviceId?: string | null;
  onPause?: (jobId: string) => void;
  onResume: (deviceId: string) => void;
  onRepair?: () => Promise<void>;
}) {
  const [repairBusy,setRepairBusy]=useState(false);
  const repairActive=useRef(false);
  const [repairError,setRepairError]=useState<string|null>(null);
  const [repairSuccess,setRepairSuccess]=useState(false);
  if (!status) return null;
  if (status.phase === 'idle') return repairSuccess ? <section className="ct-recording-activity" aria-label="同步设置修复结果">
    <p role="status">自动同步设置已修复，所有设备的暂停选择已清除。若没有开始同步，可手动同步录音。</p>
    <button type="button" className="ct-text-button" onClick={()=>setRepairSuccess(false)}>知道了</button>
  </section> : null;
  const paused = status.phase === 'paused';
  const blocked = status.phase === 'blocked';
  const saving = status.phase === 'saving' || status.phase === 'reclaiming';
  const resumeDevice = paused ? status.deviceId : blocked ? (recoveryDeviceId || status.deviceId) : null;
  const title = blocked ? '自动同步已暂停' : paused ? '录音同步已暂停' : status.pauseRequested ? '正在暂停同步'
    : status.phase === 'saving' ? '正在保存录音'
      : status.phase === 'reclaiming' ? '正在释放已同步的设备空间' : '正在同步录音';
  return <section className="ct-recording-activity" aria-label="录音同步进度">
    <div><strong role="status">{title}</strong>
      <p role={status.error ? 'alert' : undefined}>{status.error ? operationErrorText(status.error,'device') : paused ? '未收齐的设备录音和接收断点保留。重开软件仍保持暂停，点击继续同步可恢复；不影响设备继续录音。'
        : status.pauseRequested ? saving ? '本条录音保存和回收完成后，暂停后续同步。' : '正在保存已收到的断点，设备原录音保留。'
          : saving ? '先完成本机保存和校验，再释放设备空间。暂停会在安全位置生效。'
            : '可以暂停本次同步，稍后继续；不会删除未收齐的录音。'}</p>
      {!paused && status.totalBytes > 0 ? <>
        <progress aria-label="本条录音接收进度" value={Math.min(status.receivedBytes, status.totalBytes)} max={status.totalBytes} />
        <span> {Math.floor(Math.min(status.receivedBytes, status.totalBytes) / status.totalBytes * 100)}%</span>
      </> : null}
      {blocked && onRepair ? <div>
        <p>修复会恢复自动同步，并清除所有设备之前的同步暂停选择；原录音保留；如旧设置文件存在，会保留副本。</p>
        <button type="button" className="ct-text-button" disabled={repairBusy} onClick={async()=>{
          if(repairActive.current)return;
          repairActive.current=true;setRepairBusy(true);setRepairError(null);
          try {await onRepair();setRepairSuccess(true);}
          catch(error){setRepairError(operationErrorText(error,'device'));}
          finally {repairActive.current=false;setRepairBusy(false);}
        }}>{repairBusy?'正在修复…':'修复设置并恢复自动同步'}</button>
        {repairError?<p role="alert">{repairError}</p>:null}
      </div>:null}
    </div>
    {resumeDevice ? <button type="button" className="ct-action" disabled={resumeBlocked || repairBusy}
      onClick={() => onResume(resumeDevice)}><RefreshCw size={15} />{blocked ? '手动同步录音' : '继续同步'}</button>
      : status.jobId && onPause ? <button type="button" className="ct-action"
        disabled={pauseBusy || status.pauseRequested} onClick={() => onPause(status.jobId!)}>
        <Pause size={15} />{pauseBusy || status.pauseRequested ? '正在暂停…' : '暂停同步'}</button> : null}
  </section>;
}
