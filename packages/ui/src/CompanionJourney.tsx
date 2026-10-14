import { ArrowRight, Check, FileText, LoaderCircle } from 'lucide-react';
import {
  companionSessionHasFinalTranscript,
  companionMinutesMatchTranscript,
  companionMinutesProcessingComplete,
  describeCompanionMeetingRecovery,
  type CompanionV1ControlRequest,
  type CompanionV1HostSession,
} from '@companion-type/core';

export type MeetingJourney = {
  stage: number;
  title: string;
  detail: string;
  label?: string;
  request?: CompanionV1ControlRequest;
  destination?: 'settings' | 'workflow';
  processing?: boolean;
};

export function meetingHasFinalMinutes(session: CompanionV1HostSession): boolean {
  const variants = Object.values(session.minutesByMode ?? {}).filter((v) => v != null);
  if (variants.length) return variants.every((item) => item?.status === 'minutesReady' && item.quality === 'final'
    && companionMinutesProcessingComplete(item.processing)
    && companionMinutesMatchTranscript(session, item.sourceReviewRevision));
  return Boolean(session.minutes?.quality === 'final' && companionMinutesProcessingComplete(session.minutes.processing)
    && companionMinutesMatchTranscript(session, session.minutes.sourceReviewRevision));
}

export function meetingJourney(session: CompanionV1HostSession, context: {
  connected: boolean; deviceId?: string | null; asrReady: boolean; minutesReady: boolean;
}): MeetingJourney {
  const recovery = describeCompanionMeetingRecovery(session);
  const finalText = companionSessionHasFinalTranscript(session);
  const variants = Object.values(session.minutesByMode ?? {}).filter(Boolean);
  const finalMinutes = meetingHasFinalMinutes(session);
  const draft = variants.some((item) => item?.markdown.trim()) || Boolean(session.minutes?.markdown.trim());
  const localAudio = session.pendingReason !== 'needs_device_sync'
    && Boolean(session.audioPath || (session.audioStored && session.audioBytes > 0));
  const stage = finalMinutes ? 3 : finalText ? 2 : localAudio ? 1 : 0;
  if (session.status === 'recording') return { stage: 0, title: '这场会议正在录音', detail: '结束后再整理；当前文字可能仍是未完成片段。', processing: true };
  if (session.pendingReason === 'needs_device_sync') {
    const sameDevice = context.connected && Boolean(session.sourceDeviceId)
      && session.sourceDeviceId?.replace(/[:-]/g, '').toLowerCase() === context.deviceId?.replace(/[:-]/g, '').toLowerCase();
    return { stage: 0, title: '先把录音带回电脑', detail: '这场录音还没有收齐，先同步来源设备，再继续转写。',
      label: session.sourceDeviceId ? sameDevice ? '同步这台设备' : '连接来源设备' : '查看同步步骤',
      request: session.sourceDeviceId ? { action: sameDevice ? 'deviceSyncRecordings' : 'deviceConnect', deviceId: session.sourceDeviceId } : undefined,
      destination: session.sourceDeviceId ? undefined : 'workflow' };
  }
  if (session.captureIncomplete && !session.recovery?.captureReviewConfirmed && session.audioStored && !finalMinutes) {
    const detail = `录音曾意外中断，已保存 ${Math.floor(session.durationMs / 1000)} 秒。可先回听或导出；转写和纪要只覆盖这些片段。`;
    return { stage, title: '录音中断，已保存的内容还在', detail,
      label: finalText ? '整理已保存片段的纪要' : context.asrReady ? '转写已保存的片段' : '配置转写服务',
      request: finalText ? { action:'meetingGenerateMinutes',sessionId:session.id }
        : context.asrReady ? { action:'meetingTranscribeAudio',sessionId:session.id } : undefined,
      destination: !finalText && !context.asrReady ? 'settings' : undefined };
  }
  if (recovery && !recovery.retryAction) return { stage, title: recovery.label, detail: recovery.message, processing: recovery.isProcessing };
  if (session.pendingReason === 'no_speech_detected' && localAudio && recovery) {
    return { stage: 1, title: recovery.label, detail: recovery.message,
      label: context.asrReady ? '检查后重试转写' : '配置转写服务',
      request: context.asrReady ? { action: 'meetingTranscribeAudio', sessionId: session.id } : undefined,
      destination: context.asrReady ? undefined : 'settings' };
  }
  if (finalMinutes && !recovery) return { stage: 3, title: '整理好了', detail: '文字和纪要已保存在本机。可以继续查看、核对并导出。' };
  if (finalText) {
    if (draft && !context.minutesReady) return { stage: 2, title: '文字已保存，草稿可查看', detail: '当前为基础草稿。配置智能纪要服务后，可以继续整理。', label: '配置智能纪要', destination: 'settings' };
    return { stage: 2, title: recovery ? '继续整理这场会议' : '文字齐了，整理重点',
      detail: context.minutesReady ? '使用已保存的完整转写生成纪要，无需再次连接设备或重新上传录音。' : '尚未启用智能纪要，可先生成本机基础草稿；之后再配置服务精修。',
      label: context.minutesReady ? recovery ? '继续生成纪要' : '生成智能纪要' : '生成基础草稿',
      request: { action: 'meetingGenerateMinutes', sessionId: session.id } };
  }
  if (localAudio) return context.asrReady
    ? { stage: 1, title: '录音已在电脑，开始转写', detail: '转写会将这场录音发送到你配置的服务。设备离线也可以继续处理。', label: recovery ? '继续转写' : '转写这场录音', request: { action: 'meetingTranscribeAudio', sessionId: session.id } }
    : { stage: 1, title: '录音已保存，先准备转写服务', detail: '不用重新录音。配置服务后，回来继续处理这场会议。', label: '配置转写服务', destination: 'settings' };
  return { stage: 0, title: '还没有可处理的录音', detail: '当前记录没有本机音频或完整文字，请先同步录音，也可以在处理步骤中导入文本。', label: '查看处理步骤', destination: 'workflow' };
}

export function CompanionJourney({ journey, blocked, onControl, onSettings, onWorkflow }: {
  journey: MeetingJourney; blocked: boolean;
  onControl: (request: CompanionV1ControlRequest) => void;
  onSettings: () => void; onWorkflow: () => void;
}) {
  return <section className="ct-journey" aria-label="这场会议的下一步">
    <ol className="ct-journey-progress" aria-label="会议处理进度">
      {['内容已保存', '完整转写', '智能纪要'].map((label, index) => <li key={label}
        className={index < journey.stage ? 'done' : index === journey.stage ? 'current' : ''}
        aria-current={index === journey.stage ? 'step' : undefined}>
        <span>{index < journey.stage ? <Check size={12} /> : index + 1}</span>{label}
      </li>)}
    </ol>
    <div className="ct-journey-body">
      <div><h3>{journey.processing ? <LoaderCircle size={18} /> : <FileText size={18} />}{journey.title}</h3><p>{journey.detail}</p></div>
      {journey.label ? <button type="button" className="ct-action ct-action-primary"
        disabled={blocked && Boolean(journey.request)} onClick={() => {
          if (journey.request) onControl(journey.request);
          else if (journey.destination === 'settings') onSettings();
          else onWorkflow();
        }}>{journey.label}<ArrowRight size={15} /></button> : null}
    </div>
  </section>;
}
