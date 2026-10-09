import { useState } from 'react';
import { ArrowRight, ChevronDown, RefreshCw } from 'lucide-react';
import { type CompanionV1ControlRequest, type CompanionV1Snapshot } from '@companion-type/core';
import { meetingHasFinalMinutes, meetingJourney } from './CompanionJourney';

export function CompanionRecoveryCenter({ snapshot, blocked, savingBusy, asrReady, minutesReady, onControl, onSettings, onWorkflow }: {
  snapshot: CompanionV1Snapshot; blocked: boolean; savingBusy: boolean; asrReady: boolean; minutesReady: boolean;
  onControl: (request: CompanionV1ControlRequest) => void; onSettings: () => void; onWorkflow: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const pending = snapshot.host.sessions.filter(session => session.status !== 'recording'
    && (!meetingHasFinalMinutes(session) || (session.recovery?.intent === 'processMeeting' && session.recovery.stage !== 'complete')));
  const storage = snapshot.host.persistence;
  const storageBlocked = Boolean(storage && storage.status !== 'ready');
  if (!pending.length && !storageBlocked) return null;
  const visible = expanded ? pending : pending.slice(0, 3);
  return <section className="ct-recovery-center" aria-label="恢复中心">
    <header><div><p className="ct-section-eyebrow">CONTINUE WHERE YOU LEFT OFF</p><h3>继续未完成的事</h3>
      <p>{pending.length ? `${pending.length} 场会议等待继续。已有内容保留在原来的会议里。` : '先恢复本机保存，再继续处理。'}</p></div><RefreshCw size={19} /></header>
    {storageBlocked && storage ? <div className="ct-recovery-storage" role="alert" aria-label="会议保存状态">
      <strong>{storage.status === 'blocked' ? '会议库需要恢复' : '当前修改尚未安全保存'}</strong>
      <p>{storage.message ?? '自动处理已暂停，请保留当前窗口并重试。'}</p>
      <button type="button" className="ct-action" disabled={savingBusy} onClick={() => onControl({action:'hostRetrySave'})}>
        {storage.status === 'blocked' ? '重试恢复' : '重试保存'}</button>
    </div> : null}
    <ul>{visible.map(session => {
      const next = meetingJourney(session, {connected: snapshot.device.connected, deviceId: snapshot.device.deviceId, asrReady, minutesReady});
      return <li key={session.id} data-session-id={session.id}>
        <div><strong>{session.title.trim() || '未命名会议'}</strong><span>{next.title}</span><p>{next.detail}</p>
          {session.captureIncomplete ? <p role="alert">录制曾中断，只恢复了已保存的片段，末尾可能缺失。</p> : null}</div>
        <div className="ct-recovery-actions">
          <button type="button" className="ct-text-button" disabled={savingBusy}
            onClick={() => onControl({action:'meetingSelectSession', sessionId:session.id})}>查看会议</button>
          {next.label ? <button type="button" className="ct-action" disabled={Boolean(next.request) && (blocked || storageBlocked)} onClick={() => {
            if (next.request) onControl(next.request);
            else if (next.destination === 'settings') onSettings();
            else onWorkflow();
          }}>{next.label}<ArrowRight size={14} /></button> : next.processing ? <span role="status">正在处理，请稍候</span> : null}
        </div>
      </li>;
    })}</ul>
    {pending.length > 3 ? <button type="button" className="ct-text-button" aria-expanded={expanded}
      onClick={() => setExpanded(value => !value)}>{expanded ? '收起' : `查看全部 ${pending.length} 场`}<ChevronDown size={14} /></button> : null}
  </section>;
}
