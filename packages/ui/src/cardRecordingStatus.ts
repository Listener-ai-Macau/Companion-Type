import {companionSessionHasFinalTranscript,type CompanionV1HostSession} from '@companion-type/core';

/** Shared library wording for the real card-to-local-text lifecycle. */
export function cardRecordingStatus(session:CompanionV1HostSession,options:{saved:boolean;modelReady:boolean;automatic:boolean}):string|null {
  if(session.processingPolicy!=='localTranscription')return null;
  if(!options.saved)return '保存待确认';
  if(session.status==='recording')return '卡片正在录音';
  if(session.captureIncomplete&&!session.recovery?.captureReviewConfirmed)return '录音片段待核对';
  if(companionSessionHasFinalTranscript(session))return '文字已经准备好';
  if(!session.audioStored||['needs_device_sync','needs_segments','needs_pull'].includes(session.pendingReason??''))return '正在接收原音';
  if(session.recovery?.lastError||session.recovery?.stage==='paused')return '转写未完成';
  if(session.recovery?.stage==='transcribing')return '正在本机转写';
  if(!options.automatic)return '已接收，自动转写已关闭';
  if(!options.modelReady)return '已接收，待准备本机模型';
  return '已接收，等待转写';
}
