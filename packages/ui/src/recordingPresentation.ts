import {companionReviewedTranscript,companionSessionHasFinalTranscript,type CompanionV1HostSession} from '@companion-type/core';

// Display projections only: never rename the saved record or invent a topic.
export function hasGeneratedRecordingName(session:CompanionV1HostSession):boolean {
  return !session.title.trim() || /^(?:Companion device recording|Companion 录音|设备分段录音|未命名会议|(?:设备|会议)录音\s*#\d+)$/i.test(session.title.trim());
}

export function recordingDate(value:string|null|undefined):Date|null {
  if(!value)return null;
  const date=new Date(/^\d+$/.test(value)?Number(value):value);
  return Number.isFinite(date.getTime())?date:null;
}

export function recordingDisplayTitle(session:CompanionV1HostSession):string {
  if(!hasGeneratedRecordingName(session))return session.title;
  const text=companionSessionHasFinalTranscript(session)?companionReviewedTranscript(session).trim():'';
  const opening=text.split(/[\r\n。！？!?]/u).find(line=>line.trim())?.trim();
  if(opening){const characters=Array.from(opening);return characters.slice(0,28).join('')+(characters.length>28?'…':'');}
  const date=recordingDate(session.startedAt);
  if(date)return new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(date)+' 的录音';
  return session.deviceRecordingId!=null?`卡片录音 ${session.deviceRecordingId}`:'录音 · 时间未记录';
}

export function recordingDateGroup(session:CompanionV1HostSession,now=new Date()):string {
  const date=recordingDate(session.startedAt);
  if(!date)return '时间未记录';
  const key=(value:Date)=>`${value.getFullYear()}-${value.getMonth()}-${value.getDate()}`;
  if(key(date)===key(now))return '今天';
  const yesterday=new Date(now);yesterday.setDate(yesterday.getDate()-1);
  if(key(date)===key(yesterday))return '昨天';
  return new Intl.DateTimeFormat('zh-CN',{year:date.getFullYear()===now.getFullYear()?undefined:'numeric',month:'long',day:'numeric'}).format(date);
}

/** Describe actual saved state; absence of text is not a running job. */
export function recordingTextState(session:CompanionV1HostSession,options?:{automatic:boolean;localReady:boolean}):{label:string;hint:string;tone:string}|null {
  if(session.status==='recording')return {label:'录音中',hint:'结束录音后，文字会留在这条记录里。',tone:'active'};
  if(['needs_device_sync','needs_segments','needs_pull'].includes(session.pendingReason??''))return {label:'音频待收齐',hint:'连接来源录音卡后自动继续，已有内容会保留。',tone:'pending'};
  if(companionSessionHasFinalTranscript(session))return null;
  if(session.recovery?.lastError||session.recovery?.stage==='paused')return {label:'文字未生成',hint:'原音保留，打开录音查看原因并重试。',tone:'attention'};
  if(session.recovery?.stage==='transcribing')return {label:'正在转文字',hint:'正在处理已保存的音频，完成后可在这里阅读。',tone:'active'};
  if(session.captureIncomplete)return {label:'片段待核对',hint:'录音曾中断，打开后先核对已保存的片段。',tone:'attention'};
  if(session.processingPolicy==='localTranscription'&&options){
    if(!options.localReady)return {label:'需准备本机转写',hint:'音频已保存；打开录音后可准备本机中文模型。',tone:'attention'};
    if(!options.automatic)return {label:'可手动转文字',hint:'自动转写已关闭；打开录音可回听或转文字。',tone:'neutral'};
    return {label:'等待转文字',hint:'音频已保存，本机空闲后会自动处理；可先打开回听。',tone:'pending'};
  }
  if(session.audioStored||session.audioPath)return {label:'可回听',hint:'打开录音，可回听或按需转成文字。',tone:'neutral'};
  return null;
}
