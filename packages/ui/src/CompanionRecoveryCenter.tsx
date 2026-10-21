import { useState } from 'react';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { type CompanionV1ControlRequest, type CompanionV1HostSession, type CompanionV1Snapshot } from '@companion-type/core';
import { meetingHasFinalMinutes, meetingJourney } from './CompanionJourney';

/** A complete capture-only recording does not require transcription/minutes. */
export function manualRecordingIsSaved(session: CompanionV1HostSession): boolean {
  return session.processingPolicy === 'manual' && session.status !== 'recording'
    && session.audioStored && session.retention.audioCached && session.audioBytes > 0
    && Boolean(session.audioPath && !/^(board|device|host):\/\//i.test(session.audioPath))
    && !session.captureIncomplete && !session.recorderControlUncertain
    && (!session.pendingReason || session.pendingReason === 'needs_transcription')
    && !session.recovery?.lastError
    && (!session.recovery || session.recovery.intent === 'none' || session.recovery.stage === 'complete');
}

export function CompanionRecoveryCenter({ snapshot, blocked, savingBusy, asrReady, minutesReady, onControl, onSettings, onWorkflow, onSelectSession }: {
  snapshot: CompanionV1Snapshot; blocked: boolean; savingBusy: boolean; asrReady: boolean; minutesReady: boolean;
  onSelectSession?: (sessionId: string) => void;
  onControl: (request: CompanionV1ControlRequest) => void; onSettings: () => void; onWorkflow: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const pending = snapshot.host.sessions.filter(session => !session.organization?.trashedAt && session.status !== 'recording'
    && !manualRecordingIsSaved(session)
    && (!meetingHasFinalMinutes(session) || (session.recovery?.intent === 'processMeeting' && session.recovery.stage !== 'complete')));
  const storage = snapshot.host.persistence;
  const storageBlocked = Boolean(storage && storage.status !== 'ready');
  if (!pending.length && !storageBlocked) return null;
  const selected = pending.find(session => session.id === snapshot.host.selectedSessionId);
  const other = pending.filter(session => session.id !== selected?.id);
  const visible = expanded ? other : other.slice(0, 3);
  const recording = (session: CompanionV1HostSession) => {
    const next = meetingJourney(session, {connected: snapshot.device.connected, deviceId: snapshot.device.deviceId, asrReady, minutesReady});
    return <li key={session.id} data-session-id={session.id}>
      <div><strong>{session.title.trim() || '未命名录音'}</strong><span>{next.title}</span><p>{next.detail}</p>
        {session.captureIncomplete ? <p role="alert">录制曾中断，只恢复了已保存的片段，末尾可能缺失。</p> : null}</div>
      <div className="ct-recovery-actions">
        <button type="button" className="ct-text-button" disabled={savingBusy}
          onClick={() => onSelectSession ? onSelectSession(session.id) : onControl({action:'meetingSelectSession', sessionId:session.id})}>查看录音</button>
        {next.label ? <button type="button" className="ct-action" disabled={Boolean(next.request) && (blocked || storageBlocked)} onClick={() => {
          if (next.request) onControl(next.request);
          else if (next.destination === 'settings') onSettings();
          else onWorkflow();
        }}>{next.label}<ArrowRight size={14} /></button> : next.processing ? <span role="status">正在处理，请稍候</span> : null}
      </div>
    </li>;
  };
  return <section className="ct-recovery-center ct-recovery-compact" aria-label="恢复中心">
    {storageBlocked && storage ? <div className="ct-recovery-storage" role="alert" aria-label="会议保存状态">
      <strong>{storage.status === 'blocked' ? '会议库需要恢复' : '当前修改尚未安全保存'}</strong>
      <p>{storage.message ?? '自动处理已暂停，请保留当前窗口并重试。'}</p>
      <button type="button" className="ct-action" disabled={savingBusy} onClick={() => onControl({action:'hostRetrySave'})}>
        {storage.status === 'blocked' ? '重试恢复' : '重试保存'}</button>
    </div> : null}
    {selected ? <div className="ct-recovery-current"><strong>当前录音需要处理</strong><ul>{recording(selected)}</ul></div> : null}
    {other.length ? <details className="ct-recovery-history">
      <summary>其他待处理录音 <span>{other.length}</span></summary>
      <p>已有内容仍在原来的录音里，按需继续处理。</p>
      <ul>{visible.map(recording)}</ul>
      {other.length > 3 ? <button type="button" className="ct-text-button" aria-expanded={expanded}
        onClick={() => setExpanded(value => !value)}>{expanded ? '收起' : `查看全部 ${other.length} 条`}<ChevronDown size={14} /></button> : null}
    </details> : null}
  </section>;
}
