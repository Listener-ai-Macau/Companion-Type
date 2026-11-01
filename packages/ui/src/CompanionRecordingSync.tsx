import {operationErrorText} from './operationFailure';
import { Pause, RefreshCw } from 'lucide-react';

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

export function CompanionRecordingSync({ status, pauseBusy, resumeBlocked, recoveryDeviceId, onPause, onResume }: {
  status: RecordingSyncStatus | null;
  pauseBusy: boolean;
  resumeBlocked: boolean;
  recoveryDeviceId?: string | null;
  onPause?: (jobId: string) => void;
  onResume: (deviceId: string) => void;
}) {
  if (!status || status.phase === 'idle') return null;
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
    </div>
    {resumeDevice ? <button type="button" className="ct-action" disabled={resumeBlocked}
      onClick={() => onResume(resumeDevice)}><RefreshCw size={15} />{blocked ? '手动同步录音' : '继续同步'}</button>
      : status.jobId && onPause ? <button type="button" className="ct-action"
        disabled={pauseBusy || status.pauseRequested} onClick={() => onPause(status.jobId!)}>
        <Pause size={15} />{pauseBusy || status.pauseRequested ? '正在暂停…' : '暂停同步'}</button> : null}
  </section>;
}
