import { Pause, Play, RefreshCw, Square } from 'lucide-react';
import type { CompanionV1ControlRequest, CompanionV1HostSession } from '@companion-type/core';

export function CompanionRecorderControl({ session, busy, onControl }: {
  session: CompanionV1HostSession | null;
  busy: boolean;
  onControl: (request: CompanionV1ControlRequest) => void;
}) {
  const control = session?.recorderControl;
  if (!session || !control) return null;
  const uncertain = Boolean(session.recorderControlUncertain || control.pending || !control.confirmed);
  const state = control.confirmed?.state;
  const active = Boolean(control.pending || state !== 2);
  const retryPendingStart = control.pending?.command === 1 && !control.confirmed
    && session.deviceRecordingId == null && session.deviceRecordingKey == null;
  if (!active && !uncertain) return null;
  const send = (action: CompanionV1ControlRequest['action']) => onControl({ action,
    sessionId: session.id, deviceId: session.sourceDeviceId ?? undefined });
  return <section className="ct-recording-activity" aria-label="设备录音控制" aria-live="polite">
    <div><strong>{uncertain ? '录音状态待核对' : state === 3 ? '录音已暂停' : 'Companion 正在录音'}</strong>
      <p>{retryPendingStart ? '这次开始尚未确认。可先核对设备；明确重试会再次发送原来的开始请求，仍保留同一场记录。'
        : uncertain ? '原录音已保留。核对设备结果后继续，不会自动新开一场录音。'
        : state === 3 ? '继续后仍是同一场录音，暂停期间不计入音频时长。'
          : '声音由 Companion 采集，断开蓝牙仍会继续录音。'}</p></div>
    <div className="ct-button-row">
      {retryPendingStart ? <button type="button" className="ct-action" disabled={busy}
        onClick={() => send('meetingStart')}><Play size={15} />重试原开始</button> : null}
      {uncertain ? <button type="button" className="ct-action" disabled={busy}
        onClick={() => send('meetingRecoverControl')}><RefreshCw size={15} />核对原录音</button>
        : state === 3 ? <button type="button" className="ct-action" disabled={busy}
          onClick={() => send('meetingResume')}><Play size={15} />继续录音</button>
          : state === 1 ? <button type="button" className="ct-action" disabled={busy}
            onClick={() => send('meetingPause')}><Pause size={15} />暂停录音</button> : null}
      {active ? <button type="button" className="ct-action" disabled={busy}
        onClick={() => send('meetingStop')}><Square size={15} />停止并保存</button> : null}
    </div>
  </section>;
}
