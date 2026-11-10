import { invoke, convertFileSrc } from '@tauri-apps/api/core';
import {templatesForBackup,mergeRestoredCustomTemplates,type CustomTemplateDraft} from '../../../packages/ui/src/customTemplateBackup';
import type {PetFindRequest,PetFindReport} from '../../../packages/ui/src/CompanionPetFind';
export const controlCompanionPetFind=(request:PetFindRequest)=>invoke<PetFindReport>('control_companion_pet_find',{request});
import { listen } from '@tauri-apps/api/event';
export const cancelCompanionMeetingProcessing = (sessionId: string, jobId: string) =>
  invoke<boolean>('cancel_companion_meeting_processing', { sessionId, jobId });
export const watchCompanionSnapshotUpdates = (changed: () => void) =>
  listen<null>('companion-cache-updated', () => changed());
import type { RecordingSyncStatus } from '../../../packages/ui/src/CompanionRecordingSync';
export const getRecordingSyncStatus = () => invoke<RecordingSyncStatus>('get_companion_recording_sync_status');
export const pauseRecordingSync = (jobId: string) => invoke<boolean>('pause_companion_recording_sync', { jobId });
export const repairRecordingSyncSettings = () => invoke<RecordingSyncStatus>('repair_companion_recording_sync_settings');
export const watchRecordingSync = (onStatus: (status: RecordingSyncStatus) => void) =>
  listen<RecordingSyncStatus>('companion-recording-sync', (event) => onStatus(event.payload));
import type { CompanionDesktopUpdateStatus } from '../../../packages/ui/src/CompanionDesktopUpdate';
export const getDesktopUpdateStatus = () => invoke<CompanionDesktopUpdateStatus>('get_companion_type_update');
export const checkDesktopUpdate = () => invoke<CompanionDesktopUpdateStatus>('check_companion_type_update');
export const downloadDesktopUpdate = () => invoke<CompanionDesktopUpdateStatus>('download_companion_type_update');
export const cancelDesktopUpdate = () => invoke<void>('cancel_companion_type_update');
export const installDesktopUpdate = () => invoke<void>('install_companion_type_update');

import {
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
  type CompanionBookmarkRequest,
  type CompanionMeetingNoteRequest,
  applyCompanionV1ControlFixture,
  createCompanionV1Fixture,
} from '@companion-type/core';

export const askCompanionMeetings = (question:string,sessionIds:string[],jobId:string,resume?:import('@companion-type/core').MeetingQaResumeRequest) =>
  invoke<import('@companion-type/core').MeetingQaResult>('ask_companion_meetings',{question,sessionIds,jobId,resume});
export const cancelCompanionMeetingQuestion = (jobId:string) => invoke<boolean>('cancel_companion_meeting_question',{jobId});
export function companionDocumentAdapter(sessionId:string):import('../../../packages/document-context/src/storageTypes').DocumentContextAdapter{
 const command=<T,>(action:string,value?:import('../../../packages/document-context/src/storageTypes').ContextDocuments,id?:string,extra:object={})=>invoke<T>('read_companion_document_context',{action,request:{sessionId,revision:value?.revision??0,documentId:id,...extra}});
 return {load:()=>command('list'),
  import:async(value,id)=>await invoke<import('../../../packages/document-context/src/storageTypes').ContextDocuments|null>('import_companion_document',{sessionId,documentId:id,revision:value.revision})??{cancelled:true},
  chunk:(value,id,offset)=>command('chunk',value,id,{offset}),read:(value,id)=>command('read',value,id),
  commit:(value,id,extraction)=>command('commit',value,id,{extraction}),remove:(value,id)=>command('remove',value,id),
  saveOriginal:(value,id)=>invoke<boolean>('save_companion_document_original',{sessionId,documentId:id,revision:value.revision}),
 };
}

let fixtureSnapshot: CompanionV1Snapshot = createCompanionV1Fixture();
export const refineCompanionMeetingSpeakers = (sessionId:string) =>
  invoke<CompanionV1Snapshot>('refine_companion_meeting_speakers',{sessionId});
export const previewCompanionMeetingTranscription = (sessionId:string,jobId:string) =>
  invoke<{text:string;unrecognized:{startMs:number;endMs:number;source?:string|null}[]}>('preview_companion_meeting_transcription',{sessionId,jobId});
export const previewCompanionMeetingGap = (sessionId:string,jobId:string,range:{startMs:number;endMs:number}) =>
  invoke<{text:string;unrecognized:{startMs:number;endMs:number;source?:string|null}[]}>('preview_companion_meeting_gap',{sessionId,jobId,range});

export type CompanionProductSettingsPublic = {
  defaultMeetingMode: string;
  asrProvider: string;
  localAsrAvailable?: boolean;
  volcAppKeySet: boolean;
  volcAccessKeySet: boolean;
  volcResourceId: string;
  openaiAsrEndpoint: string;
  openaiAsrApiKeySet: boolean;
  openaiAsrModel: string;
  deepseekApiKeySet: boolean;
  deepseekBaseUrl: string;
  deepseekModel: string;
  deepseekMinutesEnabled: boolean;
  bleCompress: boolean;
  settingsPath: string;
  storageWarning?: string | null;
  storageSaveBlocked?: boolean;
};

export type CompanionProductSettingsPatch = {
  defaultMeetingMode: string;
  asrProvider: string;
  volcAppKey: string;
  volcAccessKey: string;
  volcResourceId: string;
  openaiAsrEndpoint: string;
  openaiAsrApiKey: string;
  openaiAsrModel: string;
  deepseekApiKey: string;
  deepseekBaseUrl: string;
  deepseekModel: string;
  deepseekMinutesEnabled: boolean;
  bleCompress: boolean;
};

const FIXTURE_SETTINGS_KEY = 'companion-type.product-settings.v1';

function defaultSettingsPublic(): CompanionProductSettingsPublic {
  return {
    defaultMeetingMode: 'offlineStore',
    asrProvider: 'local-paraformer',
    volcAppKeySet: false,
    volcAccessKeySet: false,
    volcResourceId: 'volc.bigasr.sauc.duration',
    openaiAsrEndpoint: 'https://api.openai.com/v1/audio/transcriptions',
    openaiAsrApiKeySet: false,
    openaiAsrModel: 'gpt-4o-transcribe',
    deepseekApiKeySet: false,
    deepseekBaseUrl: 'https://api.deepseek.com/v1',
    deepseekModel: 'deepseek-v4-flash',
    deepseekMinutesEnabled: true,
    bleCompress: false,
    settingsPath: 'browser-fixture:localStorage',
  };
}

export async function getCompanionSnapshot(): Promise<CompanionV1Snapshot> {
  if (isTauriRuntime()) {
    return invoke<CompanionV1Snapshot>('get_companion_v1_snapshot');
  }
  return fixtureSnapshot;
}

export async function applyCompanionControl(
  request: CompanionV1ControlRequest,
): Promise<CompanionV1Snapshot> {
  if (isTauriRuntime()) {
    return invoke<CompanionV1Snapshot>('apply_companion_v1_control', { request });
  }
  fixtureSnapshot = applyCompanionV1ControlFixture(fixtureSnapshot, request);
  return fixtureSnapshot;
}

export async function listDeviceRecordings():Promise<import('../../../packages/ui/src/CompanionDeviceRecordings').DeviceRecording[]> {
  return invoke('list_companion_device_recordings');
}
export async function syncDeviceRecording(key:import('../../../packages/ui/src/CompanionDeviceRecordings').DeviceRecordingKey):Promise<CompanionV1Snapshot> {
  return invoke('sync_companion_device_recording',{key});
}
export async function deleteDeviceRecording(key:import('../../../packages/ui/src/CompanionDeviceRecordings').DeviceRecordingKey):Promise<{status:string;message:string}> {
  return invoke('delete_companion_device_recording',{key});
}
export async function discardOldestDeviceRecording(requiredSeconds: number): Promise<{
  status: 'deleted' | 'cancelled' | 'noCandidate'; message: string;
}> {
  if (!isTauriRuntime()) throw new Error('请在 Windows Companion Type 中连接真实设备，浏览器演示不删除录音。');
  if (!Number.isInteger(requiredSeconds) || requiredSeconds < 1 || requiredSeconds > 65535) {
    throw new Error('请填写有效录音时长后再查看可释放空间。');
  }
  return invoke('discard_oldest_companion_recording', { requiredSeconds });
}

export async function previewCompanionMeetingExport(request: import('../../../packages/ui/src/CompanionDashboard').CompanionMeetingExportRequest): Promise<{contentHash:string;warning?:string|null;textContent?:string|null;calendarItems?:import('../../../packages/ui/src/CalendarExportItems').CalendarExportItem[]|null}> {
  if(!isTauriRuntime())throw Error('请在 Windows Companion Type 中核对日历导出。');
  return invoke('preview_companion_meeting_export',{request});
}

import type {CalendarOpenResult} from '../../../packages/ui/src/CompanionExportFeedback';
export const openCompanionSavedCalendar=(token:string,choiceId?:string,chooseApplication=false)=>invoke<CalendarOpenResult>('open_companion_saved_calendar',{token,choiceId:choiceId??null,chooseApplication});

export async function exportCompanionMeeting(request: import('../../../packages/ui/src/CompanionDashboard').CompanionMeetingExportRequest): Promise<{ path: string; bytes: number; warning?: string | null; calendarOpenToken?:string;calendarFileUri?:string } | null> {
  if (!isTauriRuntime()) throw new Error('请在 Windows Companion Type 中选择位置并保存会议文件。');
  return invoke('export_companion_meeting', { request });
}

export const shareCompanionAudio=(sessionId:string,format?:'original'|'mp3',destination?:import('../../../packages/ui/src/shareHandoff').ShareDestination)=>invoke<import('../../../packages/ui/src/shareHandoff').ShareHandoffResult>('share_companion_audio',{sessionId,format:format??'original',destination});
export const copyCompanionMeetingContent=(request:import('../../../packages/ui/src/CompanionDashboard').CompanionMeetingExportRequest)=>invoke<{status:string}>('copy_companion_meeting_content',{request});
export const shareCompanionMeetingContent=(request:import('../../../packages/ui/src/CompanionDashboard').CompanionMeetingExportRequest,destination?:import('../../../packages/ui/src/shareHandoff').ShareDestination)=>invoke<import('../../../packages/ui/src/shareHandoff').ShareHandoffResult>('share_companion_meeting_content',{request,destination});

export const importCompanionAudio = () => invoke<CompanionV1Snapshot | null>('import_companion_audio');
export const cancelCompanionAudioImport = () => invoke<boolean>('cancel_companion_audio_import');

export async function prepareCompanionAudio(sessionId: string): Promise<{sessionId: string; url: string; sourceIdentity: string; pauseTimeline: import('../../../packages/ui/src/CompanionAudioPlayer').CompanionPauseTimeline | null; parts: import('../../../packages/ui/src/recordingParts').RecordingPart[]; meetingTracks?: import('../../../packages/ui/src/meetingTrackPlayback').MeetingPlaybackTracks}> {
  if (!isTauriRuntime()) throw new Error('请在 Windows Companion Type 中回听这场会议的本机录音。浏览器演示没有原音。');
  type Part = {path:string;firstSample:number;samples:number};
  const prepared = await invoke<{path: string; sourceIdentity: string; pauseTimeline: import('../../../packages/ui/src/CompanionAudioPlayer').CompanionPauseTimeline | null; parts?: Part[]; meetingTracks?: {sessionId:string;sourceIdentity:string;microphone:Part[];system:Part[]}}>('prepare_companion_audio_with_timeline', { sessionId });
  if (!/^[a-f0-9]{64}$/.test(prepared.sourceIdentity)) throw new Error('桌面端未能核对这份原音，请重新准备回听。');
  const saved = prepared.meetingTracks;
  if (saved && (saved.sessionId !== sessionId || saved.sourceIdentity !== prepared.sourceIdentity)) throw new Error('会议音轨已变化，请重新准备回听。');
  const convert = (parts:Part[]) => parts.map(part => ({url:convertFileSrc(part.path),firstSample:part.firstSample,samples:part.samples}));
  return { sessionId, url: convertFileSrc(prepared.path), sourceIdentity: prepared.sourceIdentity, pauseTimeline: prepared.pauseTimeline,
    parts: convert(prepared.parts ?? []), meetingTracks: saved ? {microphone:convert(saved.microphone),system:convert(saved.system)} : undefined };
}

export async function previewCompanionDiagnostics():Promise<unknown>{return invoke('preview_companion_diagnostics');}
export async function exportCompanionDiagnostics(includeDevice: boolean): Promise<{path:string;bytes:number;warning?:string|null}|null> {
  if (!isTauriRuntime()) throw new Error('请在 Windows Companion Type 中导出真实诊断日志；浏览器演示不生成设备证据。');
  return invoke('export_companion_diagnostics', { includeDevice });
}

export async function prepareCompanionAudioComponents():Promise<void> {
  if (!isTauriRuntime()) throw new Error('请在 Windows Companion Type 中准备音频组件。');
  return invoke('prepare_companion_audio_components');
}

export async function prepareCompanionLocalAsr():Promise<void> {
  if (!isTauriRuntime()) throw new Error('请在 Windows Companion Type 中准备本地转写模型。');
  return invoke('prepare_companion_local_asr');
}

export async function exportCompanionAudio(sessionId: string, format?:'original'|'mp3'): Promise<{path: string; bytes: number} | null> {
  if (!isTauriRuntime()) throw new Error('请在 Windows Companion Type 中保存真实原音；浏览器演示不能导出录音。');
  return invoke('export_companion_audio', { sessionId, format:format??'original' });
}

export async function checkCompanionService(service: 'asr' | 'minutes'): Promise<{
  service: 'asr' | 'minutes'; status: string; message: string; elapsedMs: number; checkedAtUnixMs: number;
}> {
  if (!isTauriRuntime()) throw new Error('服务测试仅在 Windows Companion Type 中提供。');
  return invoke('check_companion_service', { service });
}

export async function saveCompanionMeetingEdit(request: {
  sessionId: string; title?: string; expectedTitle?: string;
  meetingMode?: 'offlineStore' | 'onlineLive'; markdown?: string; expectedMarkdown?: string;
  restoreHistory?: {index:number; archivedAt:string};
}): Promise<CompanionV1Snapshot> {
  if (!isTauriRuntime()) throw new Error('请在 Windows Companion Type 中保存修改；浏览器演示不写入真实会议库。');
  return invoke('save_companion_meeting_edit', { request });
}

export async function saveCompanionBookmark(request:CompanionBookmarkRequest):Promise<CompanionV1Snapshot> {
  if (!isTauriRuntime()) throw new Error('请在 Companion Type 桌面版保存重点。');
  return invoke('save_companion_bookmark',{request});
}

export async function addCompanionImageNote(request:import('@companion-type/core').CompanionMeetingImageNoteRequest):Promise<CompanionV1Snapshot|null>{
  if(!isTauriRuntime())throw Error('请在桌面版添加本机图片。');return invoke('add_companion_image_note',{request});
}
export async function previewCompanionNoteImage(sessionId:string,noteId:string):Promise<string>{
  if(!isTauriRuntime())throw Error('请在桌面版查看本机图片。');return invoke('preview_companion_note_image',{sessionId,noteId});
}
export async function saveCompanionMeetingNote(request:CompanionMeetingNoteRequest):Promise<CompanionV1Snapshot> {
  if (!isTauriRuntime()) throw new Error('请在 Companion Type 桌面版保存备注。');
  return invoke('save_companion_meeting_note',{request});
}
export async function saveCompanionLibraryOrganization(request:import('../../../packages/core/src/libraryOrganization').CompanionLibraryOrganizationRequest):Promise<CompanionV1Snapshot>{
  if(!isTauriRuntime())throw new Error('请在 Windows Companion Type 中保存真实录音分类。');
  return invoke('save_companion_library_organization',{request});
}
export async function exportCompanionLibrary(request:import('../../../packages/core/src/libraryOrganization').CompanionLibraryExportRequest):Promise<import('../../../packages/core/src/libraryOrganization').CompanionLibraryExportResult|null>{
  if(!isTauriRuntime())throw new Error('请在 Windows Companion Type 中导出本机录音。');
  return invoke('export_companion_library',{request});
}
export async function backupCompanionLibrary(draft?:CustomTemplateDraft):Promise<{path:string;sessions:number;files:number;bytes:number;templateWarning?:string}|null>{
 if(!isTauriRuntime())throw new Error('请在 Windows Companion Type 中备份会议库。');
 let templates:CustomTemplateDraft[]=[];let templateWarning:string|undefined;
 try{templates=templatesForBackup(localStorage);}catch{templateWarning='部分已保存的自定义模板无法读取，因此没有包含在备份中。';}
 if(draft&&(draft.name||draft.instructions)&&!templates.some(item=>item.name===draft.name&&item.instructions===draft.instructions))templates.unshift(draft);
 const result=await invoke<{path:string;sessions:number;files:number;bytes:number}|null>('backup_companion_library_with_templates',{templates});
 return result?{...result,templateWarning}:null;
}
export async function restoreCompanionLibraryBackup():Promise<(CompanionV1Snapshot&{templateRestoreWarning?:string;templateRestoreOnly?:boolean})|null>{
 if(!isTauriRuntime())throw new Error('请在 Windows Companion Type 中恢复会议备份。');
 const result=await invoke<{snapshot:CompanionV1Snapshot;templates:CustomTemplateDraft[];templateWarning:string|null;templatesOnly:boolean}|null>('restore_companion_library_backup_with_templates');
 if(!result)return null;
 let warning=result.templateWarning??undefined;
 if(result.templates.length)try{mergeRestoredCustomTemplates(localStorage,result.templates);}catch{warning='自定义模板未能保存到本机；原备份文件仍保留，解决本机存储问题后可重新选择该备份。';}
 return {...result.snapshot,templateRestoreWarning:warning,templateRestoreOnly:result.templatesOnly};
}
export async function saveCompanionLibraryState(request:import('../../../packages/core/src/libraryOrganization').CompanionLibraryStateRequest):Promise<CompanionV1Snapshot>{
 if(!isTauriRuntime())throw new Error('请在 Windows Companion Type 中操作真实资料库。');
 return invoke('save_companion_library_lifecycle',{request});
}
export async function purgeCompanionLibrary(request:import('../../../packages/core/src/libraryOrganization').CompanionLibraryPurgeRequest):Promise<import('../../../packages/core/src/libraryOrganization').CompanionLibraryPurgeResult>{
 if(!isTauriRuntime())throw new Error('请在 Windows Companion Type 中清理回收站。');
 return invoke('purge_companion_library',{request});
}

export async function getProductSettings(): Promise<CompanionProductSettingsPublic> {
  if (isTauriRuntime()) {
    return invoke<CompanionProductSettingsPublic>('get_companion_product_settings');
  }
  try {
    const raw = localStorage.getItem(FIXTURE_SETTINGS_KEY);
    if (!raw) return defaultSettingsPublic();
    const parsed = JSON.parse(raw) as CompanionProductSettingsPublic;
    return { ...defaultSettingsPublic(), ...parsed, settingsPath: 'browser-fixture:localStorage' };
  } catch {
    return defaultSettingsPublic();
  }
}

export type CompanionOtaPackageRequest = {
  manifestPath: string;
  firmwarePath: string;
  deviceId?: string | null;
};

export type CompanionOtaPackageValidation = {
  ok: boolean;
  packageType: string;
  versionNote: string;
  payloadBytes: number;
  chunkBytes: number;
  payloadSha256: string;
  message: string;
};

export type CompanionFirmwareOtaReport = {
  protocol: string;
  deviceId: string;
  packageType: string;
  firmwareBytes: number;
  dataWrites: number;
  statusReads: number;
  recoveredOffsets: number;
  activeLinkConfirmed: boolean;
  elapsedMs: number;
};

export type CompanionBoardOnlineLiveStartRequest = {
  title?: string;
  deviceId?: string | null;
  maxDurationSeconds?: number;
  partialIntervalMs?: number;
  disconnectAfterSeconds?: number | null;
  reconnectAfterSeconds?: number | null;
};

export type CompanionBoardOnlineLiveStatus = {
  state: 'idle' | 'starting' | 'recording' | 'stopping' | 'finalizing' | 'completed' | 'pending' | 'failed';
  sessionId: string | null;
  deviceId: string | null;
  recordingId: number | null;
  partialCount: number;
  durationMs: number;
  maxDurationSeconds?: number | null;
  disconnectResume: boolean;
  finalRecordingPath: string | null;
  error: string | null;
};

const IDLE_BOARD_ONLINE_LIVE: CompanionBoardOnlineLiveStatus = {
  state: 'idle',
  sessionId: null,
  deviceId: null,
  recordingId: null,
  partialCount: 0,
  durationMs: 0,
  disconnectResume: false,
  finalRecordingPath: null,
  error: null,
};

export async function getBoardOnlineLiveStatus(): Promise<CompanionBoardOnlineLiveStatus> {
  if (!isTauriRuntime()) return IDLE_BOARD_ONLINE_LIVE;
  return invoke<CompanionBoardOnlineLiveStatus>('get_companion_board_online_live_status');
}

export async function startBoardOnlineLive(
  request: CompanionBoardOnlineLiveStartRequest,
): Promise<CompanionBoardOnlineLiveStatus> {
  if (!isTauriRuntime()) {
    throw new Error('板端在线会议仅在 Windows Companion Type 应用内可用');
  }
  return invoke<CompanionBoardOnlineLiveStatus>('start_companion_board_online_live', { request });
}

export async function stopBoardOnlineLive(): Promise<CompanionBoardOnlineLiveStatus> {
  if (!isTauriRuntime()) {
    throw new Error('板端在线会议仅在 Windows Companion Type 应用内可用');
  }
  return invoke<CompanionBoardOnlineLiveStatus>('stop_companion_board_online_live');
}

/** Host-only: validate firmware or resource OTA package (no BLE). */
export async function validateCompanionOtaPackage(
  request: CompanionOtaPackageRequest,
): Promise<CompanionOtaPackageValidation> {
  if (!isTauriRuntime()) {
    throw new Error('资源 OTA 校验仅在 Windows Companion Type 应用内可用');
  }
  return invoke<CompanionOtaPackageValidation>('validate_companion_ota_package', { request });
}

/** Transfer OTA payload over BLE (resource packages blocked until device installer ships). */
export async function transferCompanionFirmwareOta(
  request: CompanionOtaPackageRequest,
): Promise<CompanionFirmwareOtaReport> {
  if (!isTauriRuntime()) {
    throw new Error('OTA 传输仅在 Windows Companion Type 应用内可用');
  }
  return invoke<CompanionFirmwareOtaReport>('transfer_companion_firmware_ota', { request });
}

export async function saveProductSettings(
  patch: CompanionProductSettingsPatch,
): Promise<CompanionProductSettingsPublic> {
  if (isTauriRuntime()) {
    return invoke<CompanionProductSettingsPublic>('save_companion_product_settings', {
      settings: patch,
    });
  }
  const prev = await getProductSettings();
  const next: CompanionProductSettingsPublic = {
    ...prev,
    defaultMeetingMode: patch.defaultMeetingMode || prev.defaultMeetingMode,
    asrProvider: patch.asrProvider || prev.asrProvider,
    volcAppKeySet: Boolean(patch.volcAppKey) || prev.volcAppKeySet,
    volcAccessKeySet: Boolean(patch.volcAccessKey) || prev.volcAccessKeySet,
    volcResourceId: patch.volcResourceId || prev.volcResourceId,
    openaiAsrEndpoint: patch.openaiAsrEndpoint || prev.openaiAsrEndpoint,
    openaiAsrApiKeySet: Boolean(patch.openaiAsrApiKey) || prev.openaiAsrApiKeySet,
    openaiAsrModel: patch.openaiAsrModel || prev.openaiAsrModel,
    deepseekApiKeySet: Boolean(patch.deepseekApiKey) || prev.deepseekApiKeySet,
    deepseekBaseUrl: patch.deepseekBaseUrl || prev.deepseekBaseUrl,
    deepseekModel: patch.deepseekModel || prev.deepseekModel,
    deepseekMinutesEnabled: patch.deepseekMinutesEnabled,
    bleCompress: patch.bleCompress,
    settingsPath: 'browser-fixture:localStorage',
  };
  localStorage.setItem(FIXTURE_SETTINGS_KEY, JSON.stringify(next));
  return next;
}

export function isTauriRuntime(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}
