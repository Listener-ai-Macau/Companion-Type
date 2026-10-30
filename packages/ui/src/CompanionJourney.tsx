import {operationErrorText} from './operationFailure';
import { ArrowRight, Check, FileText, LoaderCircle } from 'lucide-react';
import {
  companionSessionHasFinalTranscript,
  companionMinutesMatchTranscript,
  companionMinutesNotesCurrent,
  companionMinutesProcessingComplete,
  describeCompanionMeetingRecovery,
  type CompanionV1ControlRequest,
  type CompanionV1HostSession,
} from '@companion-type/core';

export function hostRecordingAudioConfirmed(session: CompanionV1HostSession): boolean {
  return Boolean(session.audioStored && session.retention.audioCached && session.audioPath && session.audioBytes > 44);
}

export type MeetingJourney = {
  stage: number;
  title: string;
  detail: string;
  label?: string;
  request?: CompanionV1ControlRequest;
  destination?: 'settings' | 'workflow';
  processing?: boolean;
  optional?: boolean;
  handlesFailure?: boolean;
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
  if(recovery&&session.recovery?.lastError&&recovery.message.includes(session.recovery.lastError))
    recovery.message=recovery.message.replace(session.recovery.lastError,operationErrorText(session.recovery.lastError));
  const finalText = companionSessionHasFinalTranscript(session);
  const variants = Object.values(session.minutesByMode ?? {}).filter(Boolean);
  const finalMinutes = meetingHasFinalMinutes(session);
  const optionalOrganization = !recovery || (session.recovery?.stage === 'pendingMinutes' && !session.recovery.lastError);
  const draft = variants.some((item) => item?.markdown.trim()) || Boolean(session.minutes?.markdown.trim());
  const localAudio = session.pendingReason !== 'needs_device_sync'
    && (session.source === 'hostMicrophone'
      ? hostRecordingAudioConfirmed(session)
      : session.deviceRecordingKey
        ? Boolean(session.audioStored && session.retention.audioCached && session.audioPath && session.audioBytes > 0)
        : Boolean(session.audioPath || (session.audioStored && session.audioBytes > 0)));
  const stage = finalMinutes ? 3 : finalText ? 2 : localAudio ? 1 : 0;
  if (session.status === 'recording') return { stage: 0, title: '这场会议正在录音', detail: '结束后再整理；当前文字可能仍是未完成片段。', processing: true };
  if (session.source === 'hostMicrophone' && !localAudio && !finalText && !finalMinutes) return {
    stage: 0, title: '录音保存尚未确认',
    detail: '本机录音未确认保存，暂不能提交转写。已保留原文件路径，请先保留原文件。',
  };
  if (session.pendingReason === 'needs_local_audio') return {
    stage: 1, title: '原音已收齐，生成回听文件',
    detail: '原音已保存在电脑。若此前保存失败，请先释放磁盘空间或解除文件占用，再生成回听文件。',
    label: '生成回听文件', request: {action:'meetingRestoreAudio',sessionId:session.id},
  };
  if (session.pendingReason === 'needs_device_sync' || session.pendingReason === 'needs_segments') {
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
  // A failed explicit context request is paused by the native host. Offer
  // one explicit retry with that same still-current consent, never silently
  // substitute original-only processing. Changed material needs a new choice.
  const failedMode=session.recovery?.requestedMeetingMode==='onlineLive'?'onlineLive':'offlineStore';
  const failedProduct=session.minutesByMode?.[failedMode]
    ?? (session.meetingMode===failedMode?session.minutes:undefined);
  const noteContext=failedProduct?.sourceNoteContext;
  if (finalText && noteContext && failedProduct?.quality!=='final'
      && session.recovery?.stage==='paused') {
    const current=companionMinutesNotesCurrent(session,noteContext)
      && companionMinutesMatchTranscript(session,failedProduct.sourceReviewRevision);
    return {stage:2,title:'整理未完成',handlesFailure:true,
      detail:current?'原话和补充仍保存在本机。重试会参考上次明确选择的原话与补充。'
        :'原话或补充已变化，已有内容仍保留。重试时请重新选择这次要整理的内容。',
      label:'重试整理',request:{action:'meetingGenerateMinutes',sessionId:session.id,meetingMode:failedMode,
        ...(current?{contextNoteRevision:noteContext.noteRevision}:{})}};
  }
  if (recovery && !recovery.retryAction) return { stage, title: recovery.label, detail: recovery.message, processing: recovery.isProcessing };
  if (session.pendingReason === 'no_speech_detected' && localAudio && recovery) {
    return { stage: 1, title: recovery.label, detail: recovery.message, handlesFailure: true,
      label: context.asrReady ? '检查后重试转写' : '配置转写服务',
      request: context.asrReady ? { action: 'meetingTranscribeAudio', sessionId: session.id } : undefined,
      destination: context.asrReady ? undefined : 'settings' };
  }
  if (finalMinutes && !recovery) return { stage: 3, optional: true, title: '整理好了', detail: '文字和纪要已保存在本机。可以继续查看、核对并导出。' };
  if (finalText) {
    if (draft && !context.minutesReady) return { stage: 2, optional: optionalOrganization, title: '原句摘录已生成', detail: '已从文字中摘录原句，供你核对、补充。原音和文字仍保留。' };
    // Once text is complete, organizing it is optional. Requested recovery stays visible.
    return { stage: 2, optional: optionalOrganization, title: recovery ? '继续整理这条内容' : '文字已保存，可按需整理',
      detail: context.minutesReady ? '按已保存的文字提取重点与待办，原文保留。无需再次连接设备。' : '从文字中摘录原句作为草稿，供你核对、补充。原音和文字仍保留。',
      label: context.minutesReady ? recovery ? '继续整理' : '整理重点' : '生成基础草稿',
      request: { action: 'meetingGenerateMinutes', sessionId: session.id } };
  }
  if (localAudio && session.processingPolicy === 'manual' && !recovery) return {
    stage: 1, optional: true,
    title: context.asrReady ? '需要文字时，可以手动转写' : '需要文字时，再配置转写服务',
    detail: '原音已保存，可以直接回听或导出。转写与纪要按需手动启动，使用你配置的服务。',
    label: context.asrReady ? '转写这条录音' : '配置转写服务',
    request: context.asrReady ? { action: 'meetingTranscribeAudio', sessionId: session.id } : undefined,
    destination: context.asrReady ? undefined : 'settings',
  };
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
  return <section className="ct-journey" aria-label="这条录音的下一步">
    {journey.optional ? <p className="ct-optional-processing">可选 · 转写与纪要</p> : <ol className="ct-journey-progress" aria-label="录音处理进度">
      {['原音已保存', '转成文字', '整理重点'].map((label, index) => <li key={label}
        className={index < journey.stage ? 'done' : index === journey.stage ? 'current' : ''}
        aria-current={index === journey.stage ? 'step' : undefined}>
        <span>{index < journey.stage ? <Check size={12} /> : index + 1}</span>{label}
      </li>)}
    </ol>}
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
