import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { CompanionSetup } from './CompanionSetup';
import {CompanionPetFind,type PetFindRequest,type PetFindReport} from './CompanionPetFind';
import { CompanionTranscriptReview } from './CompanionTranscriptReview';
import { CompanionBookmarks } from './CompanionBookmarks';
import { CompanionAudioPlayer, type CompanionPauseTimeline } from './CompanionAudioPlayer';
import {useListeningQueue} from './useListeningQueue';
import {CompanionLibraryTools,type LibraryFilters} from './CompanionLibraryTools';
import {recordingInDates} from './libraryDates';
import type {CompanionLibraryExportRequest,CompanionLibraryExportResult} from '../../core/src/libraryOrganization';
import type {CompanionLibraryStateRequest,CompanionLibraryPurgeRequest,CompanionLibraryPurgeResult} from '../../core/src/libraryOrganization';
import type {CompanionLibraryOrganizationRequest} from '../../core/src/libraryOrganization';
import { companionMinutesNotesCurrent, type CompanionMinutesNoteContext } from '@companion-type/core';
import { CompanionMeetingNotes } from './CompanionMeetingNotes';
import { CompanionExportFeedback, exportFileName } from './CompanionExportFeedback';
import { briefMinutes } from './briefMinutes';
import {savedActions,markSavedAction,commonActionSupplement,splitActionSupplement,type SavedAction} from './savedActions';
import { seekBookmarkAudio } from './bookmarkAudio';
import { CompanionJourney, meetingHasFinalMinutes, meetingJourney } from './CompanionJourney';
import { CompanionRecoveryCenter } from './CompanionRecoveryCenter';
import { CompanionRecordingSync } from './CompanionRecordingSync';
import { CompanionRecorderControl } from './CompanionRecorderControl';
import { CompanionBehaviorPreview } from './CompanionBehaviorPreview';
import {
  Bluetooth,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  Eraser,
  FileText,
  HardDrive,
  Headphones,
  Link2,
  Mic,
  Pencil,
  Play,
  RefreshCw,
  Search,
  Shield,
  Square,
  Trash2,
  Unlink,
  Upload,
} from 'lucide-react';

import {
  COMPANION_CAPTURE_ONLY_PROMPT,
  type CompanionV1ControlAction,
  type CompanionV1ControlRequest,
  type CompanionV1MeetingMode,
  type CompanionV1HostSession,
  type CompanionV1Snapshot,
  type CompanionTranscriptReviewEdit,
  type CompanionBookmarkRequest,
  type CompanionMeetingNoteRequest,
  companionBookmarkAudioPosition,
  companionCanChangeOfflineRecordingLink,
  companionMinutesMatchTranscript,
  companionMinutesReferencedSources,
  companionTranscriptSources,
  companionTranscriptSourceIsCurrent,
  type CompanionTranscriptSource,
  companionMinutesProcessingComplete,
  companionReviewedTranscript,
  companionTranscriptReviewRevision,
  companionTranscriptReviewIsStale,
  companionBleNameIsValid,
  companionSessionHasFinalTranscript,
  describeCompanionMeetingRecovery,
  selectedCompanionHostSession,
} from '@companion-type/core';

export type CompanionProductSettingsPublic = {
  defaultMeetingMode: string;
  asrProvider: string;
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

const listeningIdentity = (session:CompanionV1HostSession) => JSON.stringify([session.id,session.audioPath??'',
  session.audioBytes,session.deviceSha256??'',session.deviceRecordingKey??'',session.audioStored,session.retention.audioCached]);

function recordingTimeLabel(value?: string | null) {
  const date = value ? new Date(value) : null;
  return date && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false }).format(date)
    : '时间未记录';
}

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
  clearCredentials?: Array<'volcAppKey' | 'volcAccessKey' | 'openaiAsrApiKey' | 'deepseekApiKey'>;
};

export type CompanionOtaPackageValidationUi = {
  ok: boolean;
  packageType: string;
  versionNote: string;
  payloadBytes: number;
  chunkBytes: number;
  payloadSha256: string;
  message: string;
};

export type CompanionBoardOnlineLiveUiStatus = {
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

export type CompanionMeetingExportRequest = {
  sessionId: string;
  meetingMode: CompanionV1MeetingMode;
  format: 'markdown' | 'txt' | 'json' | 'srt' | 'todo' | 'ics';
};

export type CompanionMeetingSaveRequest = {
  sessionId: string;
  title?: string;
  expectedTitle?: string;
  meetingMode?: CompanionV1MeetingMode;
  markdown?: string;
  expectedMarkdown?: string;
  transcriptReview?: CompanionTranscriptReviewEdit;
};

export interface CompanionDashboardProps {
  settingsFooter?: ReactNode;
  onFindPet?: (request:PetFindRequest)=>Promise<PetFindReport>;
  recordingSync?: import('./CompanionRecordingSync').RecordingSyncStatus | null;
  pauseSyncBusy?: boolean;
  onPauseSync?: (jobId: string) => void;
  onUnsavedChange?: (unsaved: boolean) => void;
  snapshot: CompanionV1Snapshot | null;
  busyAction: CompanionV1ControlAction | 'refresh' | null;
  error: string | null;
  surface: 'windows' | 'mobile';
  productSettings?: CompanionProductSettingsPublic | null;
  boardOnlineLive?: CompanionBoardOnlineLiveUiStatus | null;
  boardOnlineBusy?: boolean;
  onRefresh: () => void;
  onControl: (request: CompanionV1ControlRequest) => void;
  onStartBoardOnlineLive?: (request: {
    title?: string;
    deviceId?: string | null;
    maxDurationSeconds?: number;
    partialIntervalMs?: number;
  }) => void | Promise<void>;
  onStopBoardOnlineLive?: () => void | Promise<void>;
  onSaveProductSettings?: (patch: CompanionProductSettingsPatch) => void | Promise<void>;
  onExportMeeting?: (request: CompanionMeetingExportRequest) => Promise<{ path: string; bytes: number; warning?: string | null } | null>;
  onExportDiagnostics?: (includeDevice: boolean) => Promise<{path:string;bytes:number;warning?:string|null}|null>;
  onPrepareAudioComponents?: () => Promise<void>;
  onCheckService?: (service: 'asr' | 'minutes') => Promise<{ service: 'asr' | 'minutes'; status: string; message: string; elapsedMs: number; checkedAtUnixMs: number }>;
  /** Returns a short-lived, session-bound desktop asset URL. Raw paths are never placed in the browser. */
  onPrepareAudio?: (sessionId: string) => Promise<{ sessionId: string; url: string; sourceIdentity?: string; pauseTimeline?: CompanionPauseTimeline | null }>;
  onExportAudio?: (sessionId: string) => Promise<{ path: string; bytes: number } | null>;
  /** Native host obtains a concrete device proposal and its confirmation dialog. */
  onDiscardOldestRecording?: (requiredSeconds: number) => Promise<{
    status: 'deleted' | 'cancelled' | 'noCandidate'; message: string;
  }>;
  /** Conflict-aware metadata/minutes edit. The host persists before returning its next snapshot. */
  onSaveMeeting?: (request: CompanionMeetingSaveRequest) => Promise<CompanionV1Snapshot>;
  onRefineSpeakers?: (sessionId:string) => Promise<CompanionV1Snapshot>;
  onSaveBookmark?: (request:CompanionBookmarkRequest) => Promise<CompanionV1Snapshot>;
  onSaveNote?: (request:CompanionMeetingNoteRequest) => Promise<CompanionV1Snapshot>;
  onSaveLibraryOrganization?:(request:CompanionLibraryOrganizationRequest)=>Promise<CompanionV1Snapshot>;
  onExportLibrary?:(request:CompanionLibraryExportRequest)=>Promise<CompanionLibraryExportResult|null>;
  onSaveLibraryLifecycle?:(request:CompanionLibraryStateRequest)=>Promise<CompanionV1Snapshot>;
  onPurgeLibrary?:(request:CompanionLibraryPurgeRequest)=>Promise<CompanionLibraryPurgeResult>;
  /** Host-only resource/firmware package validation (Windows Tauri). */
  onValidateOtaPackage?: (paths: {
    manifestPath: string;
    firmwarePath: string;
  }) => Promise<CompanionOtaPackageValidationUi>;
  /** BLE OTA transfer; resource packages blocked until device installer ships. */
  onTransferOtaPackage?: (paths: {
    manifestPath: string;
    firmwarePath: string;
    deviceId?: string | null;
  }) => Promise<{ packageType: string; firmwareBytes: number; elapsedMs: number; deviceId: string }>;
}

// Present the existing local rule draft without its generated diagnostic metadata.
// Stored/exported text stays intact; empty extraction is explicit, never a task invented by the UI.
function localDraftForDisplay(markdown: string, source: string | undefined): string {
  if ((source !== 'rules_l0' && !(source === 'userEdited' && basicMinutesFields(markdown))) || !markdown.includes('## Summary')) return markdown;
  const parts = markdown.split(/^## /m);
  const intro = (parts.shift() ?? '').split('\n')
    .filter(line => !/^(Generated:|Duration:|Source:|Minutes engine:)/.test(line)).join('\n').trim();
  const labels: Record<string, string> = { Summary: '摘要', Decisions: '已明确的决定', 'Action Items': '待办', Questions: '待确认', Keywords: '关键词' };
  const sections = parts.flatMap(part => {
    const [heading, ...lines] = part.split('\n');
    const body = lines.join('\n').trim();
    if (!body || body === 'None captured' || body === '- None captured') {
      return heading === 'Action Items' ? ['## 待办\n\n尚未自动提取待办，请对照原文核对。'] : [];
    }
    return [`## ${labels[heading] ?? heading}\n\n${body}`];
  });
  return [intro, ...sections].filter(Boolean).join('\n\n');
}

function minutesSourceEnvelope(context: CompanionMinutesNoteContext): string {
  let prefix = `> 本次依据录音文字＋用户明确选择的补充整理（补充版本${context.noteRevision}）。补充不是原始录音识别，原话单独保留。\n\n## 本次使用的用户补充\n`;
  context.notes.forEach((note, index) => {
    prefix += `\n补充${index + 1}：\n`;
    note.text.split('\n').forEach(line => { prefix += `> ${line}\n`; });
  });
  return prefix + '\n\n';
}

// Only exact native canonical templates have a safe field projection.
// Keep the stored header and every other section byte-for-byte while changing
// one field. Unknown Markdown keeps its existing text editor.
function basicMinutesFields(markdown: string, noteContext?: CompanionMinutesNoteContext | null): Array<{ key: string; label: string; value: string; start: number; end: number }> | null {
  const labels: Record<string, string> = { Summary: '摘要', Decisions: '决定', 'Action Items': '待办', Questions: '待确认', Keywords: '关键词' };
  const headings = [...markdown.matchAll(/^## (Summary|Decisions|Action Items|Questions|Keywords)\r?$/gm)];
  if (headings.map(match => match[1]).join('|') !== Object.keys(labels).join('|')) return null;
  const envelope = noteContext ? minutesSourceEnvelope(noteContext) : '';
  if (!markdown.startsWith(envelope)) return null;
  const prefix = markdown.slice(envelope.length, headings[0].index);
  if (!/^# [^\r\n]+\r?\n\r?\nGenerated: [^\r\n]+\r?\nDuration: [^\r\n]+\r?\nSource: [^\r\n]+\r?\nMinutes engine: (?:rules_l0 \(draft\)|llm_deepseek \(final\))\r?\n\r?\n$/.test(prefix)) return null;
  // Unexpected sections must stay visible in the full-text editor.
  if ([...markdown.slice(envelope.length).matchAll(/^## /gm)].length !== headings.length) return null;
  return headings.map((match, index) => {
    const start = match.index! + match[0].length;
    const end = headings[index + 1]?.index ?? markdown.length;
    const lines = markdown.slice(start, end).trim().split(/\r?\n/);
    const body = lines.length === 1 && /^(?:- )?None captured$/.test(lines[0]) ? ''
      : lines.map(line => line.replace(/^- /, '')).join('\n');
    return { key: match[1], label: labels[match[1]], value: body, start, end };
  });
}

function MinutesContentEditor({ markdown, onChange, disabled, label, noteContext }: {
  markdown: string; onChange: (value: string) => void; disabled: boolean; label: string; noteContext?: CompanionMinutesNoteContext | null;
}) {
  const fields = basicMinutesFields(markdown, noteContext);
  if (!fields) return <textarea value={markdown} onChange={event => onChange(event.target.value)}
    aria-label={label} spellCheck={false} disabled={disabled} />;
  const field = (item: typeof fields[number]) => <label key={item.key} className="ct-basic-minutes-field">
    <span>{item.label}{item.key === 'Action Items' ? '（每行一项）' : ''}</span>
    <textarea aria-label={`编辑${item.label}`} aria-describedby={item.key === 'Action Items' ? 'ct-minutes-action-help' : undefined}
      value={item.value} spellCheck={false}
      disabled={disabled} placeholder={item.key === 'Action Items' ? '一行一件事，填写你确认的待办' : '暂无内容，可自行补充'}
      onChange={event => {
        const newline = markdown.includes('\r\n') ? '\r\n' : '\n';
        const lines = event.target.value.split(/\r?\n/);
        const body = lines.map(line => item.key === 'Keywords' || !line.trim() ? line : `- ${line}`).join(newline);
        onChange(markdown.slice(0, item.start) + newline + body + newline + newline + markdown.slice(item.end));
      }} />
    {item.key === 'Action Items' ? <small id="ct-minutes-action-help" className="ct-action-item-help">
      当前 {item.value.split(/\r?\n/).filter(line => line.trim()).length} 项。按回车换行，每一行会单独导出为一个待办。
    </small> : null}
  </label>;
  return <div className="ct-basic-minutes-editor">
    {fields.filter(item => item.key === 'Summary' || item.key === 'Action Items').map(field)}
    <details><summary>更多整理内容</summary>
      {fields.filter(item => item.key !== 'Summary' && item.key !== 'Action Items').map(field)}
    </details>
    <p className="ct-step-meta">只修改整理结果，原录音文字和补充备注仍分别保留。</p>
  </div>;
}

export function CompanionDashboard({
  settingsFooter,
  onFindPet,
  recordingSync = null,
  pauseSyncBusy = false,
  onPauseSync,
  onUnsavedChange,
  snapshot,
  busyAction,
  error,
  surface,
  productSettings = null,
  boardOnlineLive = null,
  boardOnlineBusy = false,
  onRefresh,
  onControl,
  onStartBoardOnlineLive,
  onStopBoardOnlineLive,
  onSaveProductSettings,
  onExportMeeting,
  onExportDiagnostics,
  onPrepareAudioComponents,
  onCheckService,
  onPrepareAudio,
  onExportAudio,
  onDiscardOldestRecording,
  onSaveMeeting,
  onRefineSpeakers,
  onSaveBookmark,
  onSaveNote,
  onSaveLibraryOrganization,
  onExportLibrary,
  onSaveLibraryLifecycle,
  onPurgeLibrary,
  onValidateOtaPackage,
  onTransferOtaPackage,
}: CompanionDashboardProps) {
  const [draftName, setDraftName] = useState('companion');
  const [draftTitle, setDraftTitle] = useState('设备会议');
  const [newMeetingTitle, setNewMeetingTitle] = useState('');
  const [draftMinutes, setDraftMinutes] = useState('30');
  const [transcriptDraft, setTranscriptDraft] = useState('');
  const transcriptEditor = useRef<{ sessionId?: string; dirty: boolean }>({ dirty: false });
  const [pendingDelete, setPendingDelete] = useState<{ request: CompanionV1ControlRequest; title: string; detail: string } | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showWorkflow, setShowWorkflow] = useState(false);
  const [pageView, setPageView] = useState<'library' | 'device' | 'settings'>('library');
  const [onlyPendingSessions, setOnlyPendingSessions] = useState(false);
  const [libraryQuery, setLibraryQuery] = useState('');
  const [libraryFilters,setLibraryFilters]=useState<LibraryFilters>({folder:'*',tag:'',favorites:false});
  const [librarySelection,setLibrarySelection]=useState<Record<string,number>>({});
  const [libraryBusy,setLibraryBusy]=useState(false);
  const [libraryCurrentMessage,setLibraryCurrentMessage]=useState('');
  const [libraryUnsaved,setLibraryUnsaved]=useState(false);
  const [openSavedRecordingId, setOpenSavedRecordingId] = useState<string | null>(null);
  const savedRecordingWorkspace = useRef<HTMLElement | null>(null);
  const [detailSessionId,setDetailSessionId]=useState<string|null>(null);
  const [recordingResultOpen, setRecordingResultOpen] = useState(false);
  const [recordingToolsOpen, setRecordingToolsOpen] = useState(false);
  const [libraryToolsOpen, setLibraryToolsOpen] = useState(false);
  const [playbackOpen, setPlaybackOpen] = useState(false);
  const [transcribePromptSession, setTranscribePromptSession] = useState<string | null>(null);
  const [meetingMode, setMeetingMode] = useState<CompanionV1MeetingMode>('offlineStore');
  const [minutesSelection, setMinutesSelection] = useState<{ sessionId: string; mode: CompanionV1MeetingMode } | null>(null);
  const [settingsMsg, setSettingsMsg] = useState<string | null>(null);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const settingsActive = useRef(false);
  const [clearCredentials, setClearCredentials] = useState<NonNullable<CompanionProductSettingsPatch['clearCredentials']>>([]);
  const [serviceBusy, setServiceBusy] = useState<'asr' | 'minutes' | null>(null);
  const [discardBusy, setDiscardBusy] = useState(false);
  const [discardMessage, setDiscardMessage] = useState<string | null>(null);
  const discardActive = useRef(false);
  const currentDiscardDevice = useRef<string | null>(null);
  const serviceActive = useRef(false);
  const [serviceResults, setServiceResults] = useState<Partial<Record<'asr' | 'minutes', string>>>({});
  const [resourceManifestPath, setResourceManifestPath] = useState('');
  const [resourceMsg, setResourceMsg] = useState<string | null>(null);
  const [diagnosticMsg, setDiagnosticMsg] = useState<string | null>(null);
  const [diagnosticBusy, setDiagnosticBusy] = useState(false);
  const diagnosticActive = useRef(false);
  const [resourceBusy, setResourceBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const exportActive = useRef(false);
  const [organizationChoiceId,setOrganizationChoiceId]=useState<string|null>(null);
  const [exportResult, setExportResult] = useState<{ sessionId: string; message: string; path?: string; format?: CompanionMeetingExportRequest['format']; kind?: 'saved' | 'cancelled' | 'pending' | 'error'; origin?:'text'|'notes'|'document' } | null>(null);
  const [meetingDrafts, setMeetingDrafts] = useState<Record<string, {
    title?: { value: string; expected: string };
    minutes?: Partial<Record<CompanionV1MeetingMode, { value: string; expected: string }>>;
  }>>({});
  const [editingMinutes, setEditingMinutes] = useState(false);
  const [saveMeetingBusy, setSaveMeetingBusy] = useState(false);
  const actionSaveActive=useRef(false);
  const [bookmarkBusy,setBookmarkBusy]=useState(false);
  const [bookmarkUnsaved,setBookmarkUnsaved]=useState(false);
  const [noteBusy,setNoteBusy]=useState(false);
  const [noteUnsaved,setNoteUnsaved]=useState(false);
  const [saveMeetingResult, setSaveMeetingResult] = useState<{ sessionId: string; part?: 'title' | 'minutes'; message: string; kind: 'saved' | 'error' } | null>(null);
  const [audioBusy, setAudioBusy] = useState(false);
  const [audioSources, setAudioSources] = useState<Record<string, { url: string; identity: string; sourceIdentity?: string; pauseTimeline?: CompanionPauseTimeline | null }>>({});
  const [audioResult, setAudioResult] = useState<{ sessionId: string; message: string } | null>(null);
  const audioElement = useRef<HTMLAudioElement | null>(null);
  const audioRequestId = useRef(0);
  const [listeningEpoch,setListeningEpoch]=useState(0);
  const [formAsrProvider, setFormAsrProvider] = useState('volcengine');
  const [formVolcApp, setFormVolcApp] = useState('');
  const [formVolcAccess, setFormVolcAccess] = useState('');
  const [formVolcResource, setFormVolcResource] = useState('volc.bigasr.sauc.duration');
  const [formOpenAiEndpoint, setFormOpenAiEndpoint] = useState('https://api.openai.com/v1/audio/transcriptions');
  const [formOpenAiKey, setFormOpenAiKey] = useState('');
  const [formOpenAiModel, setFormOpenAiModel] = useState('gpt-4o-transcribe');
  const [formDeepseekKey, setFormDeepseekKey] = useState('');
  const [formDeepseekBase, setFormDeepseekBase] = useState('https://api.deepseek.com/v1');
  const [formDeepseekModel, setFormDeepseekModel] = useState('deepseek-v4-flash');
  const [formDeepseekEnabled, setFormDeepseekEnabled] = useState(true);
  const [formBleCompress, setFormBleCompress] = useState(false);
  const [formDefaultMode, setFormDefaultMode] = useState<CompanionV1MeetingMode>('offlineStore');

  useEffect(() => {
    if (!productSettings || productSettings.storageSaveBlocked) return;
    setFormAsrProvider(productSettings.asrProvider || 'volcengine');
    setFormVolcResource(productSettings.volcResourceId || 'volc.bigasr.sauc.duration');
    setFormOpenAiEndpoint(productSettings.openaiAsrEndpoint);
    setFormOpenAiModel(productSettings.openaiAsrModel);
    setFormDeepseekBase(productSettings.deepseekBaseUrl);
    setFormDeepseekModel(productSettings.deepseekModel);
    setFormDeepseekEnabled(productSettings.deepseekMinutesEnabled);
    setFormBleCompress(productSettings.bleCompress);
    const mode = productSettings.defaultMeetingMode === 'onlineLive' ? 'onlineLive' : 'offlineStore';
    setFormDefaultMode(mode);
    setMeetingMode(mode);
  }, [productSettings?.asrProvider, productSettings?.volcResourceId,
    productSettings?.openaiAsrEndpoint, productSettings?.openaiAsrModel,
    productSettings?.deepseekBaseUrl, productSettings?.deepseekModel,
    productSettings?.deepseekMinutesEnabled, productSettings?.bleCompress,
    productSettings?.defaultMeetingMode, Boolean(productSettings?.storageSaveBlocked)]);

  const [transcriptReviewUnsaved, setTranscriptReviewUnsaved] = useState(false);
  const selectedSession = useMemo(
    () => {const row=snapshot?selectedCompanionHostSession(snapshot):null;return row&&!row.organization?.trashedAt&&!libraryFilters.trash?row:null;},
    [snapshot,libraryFilters.trash],
  );
  const savedDetailOpen=Boolean(selectedSession&&detailSessionId===selectedSession.id);
  const device = snapshot?.device;
  const controlledRecorder = snapshot?.host.sessions.find((row) => row.recorderControl
    && (row.status === 'recording' || row.recorderControlUncertain)) ?? null;
  const activeRecorders = snapshot?.host.sessions.filter((row) => row.status === 'recording') ?? [];
  const originalSyncRecorder = activeRecorders.length === 1
    && activeRecorders[0].source === 'boardDevice' && activeRecorders[0].deviceRecordingKey
    && activeRecorders[0].deviceRecordingId && activeRecorders[0].sourceDeviceId
    && (!device?.deviceId || device.deviceId.replace(/[:-]/g, '').toLowerCase()
      === activeRecorders[0].sourceDeviceId.replace(/[:-]/g, '').toLowerCase())
    ? activeRecorders[0] : null;
  const pausedSyncRecorder = originalSyncRecorder && recordingSync?.deviceId
    && recordingSync.deviceId.replace(/[:-]/g, '').toLowerCase()
      === originalSyncRecorder.sourceDeviceId!.replace(/[:-]/g, '').toLowerCase()
    ? originalSyncRecorder : null;
  const privacy = snapshot?.privacy;
  const allLibrarySessions = snapshot?.host.sessions ?? [];
  const localSaveConfirmed = snapshot?.host.persistence?.status === 'ready';
  const recentSavedRecording = useMemo(() => allLibrarySessions
    .filter(session => !session.organization?.trashedAt && session.status !== 'recording'
      && session.audioStored && session.retention.audioCached && session.audioPath && session.audioBytes > 0
      && !/^(host|device|board):\/\//i.test(session.audioPath)
      && !['needs_local_audio', 'needs_device_sync', 'needs_segments'].includes(session.pendingReason ?? ''))
    .reduce<CompanionV1HostSession | null>((latest, session) => {
      if (!latest) return session;
      const time = Date.parse(session.startedAt ?? '');
      const previous = Date.parse(latest.startedAt ?? '');
      return Number.isFinite(time) && (!Number.isFinite(previous) || time > previous) ? session : latest;
    }, null), [allLibrarySessions]);
  const recordingLibrary = allLibrarySessions.filter(s=>Boolean(s.organization?.trashedAt)===Boolean(libraryFilters.trash));
  const readableLibrary = useMemo(
    () => recordingLibrary.filter((session) => (
      session.status === 'minutesReady'
      || Boolean(session.transcriptText?.trim())
      || Boolean(session.meetingNotes?.length)
      || Boolean(session.minutesByMode?.offlineStore || session.minutesByMode?.onlineLive)
      || Boolean(session.recovery?.intent === 'processMeeting')
    )),
    [recordingLibrary],
  );
  const pendingLibrary = recordingLibrary.filter((session) => !meetingHasFinalMinutes(session)
    || Boolean(describeCompanionMeetingRecovery(session)));
  const visibleLibrary = useMemo(() => {
    const base = (onlyPendingSessions ? pendingLibrary : recordingLibrary).filter(s=>{
      const org=s.organization;const folder=org?.folder??'';
      return (libraryFilters.folder==='*'||folder===libraryFilters.folder||Boolean(libraryFilters.folder)&&folder.startsWith(libraryFilters.folder+'/'))
        &&(!libraryFilters.tag||org?.tags.some(t=>t.toLocaleLowerCase()===libraryFilters.tag.toLocaleLowerCase()))
        &&(!libraryFilters.favorites||org?.favorite)
        &&recordingInDates(s,libraryFilters.from,libraryFilters.to);
    });
    const query = libraryQuery.trim().toLocaleLowerCase();
    if (!query) return base;
    return base.filter((session) => (meetingSearchText(session)+' '+(session.organization?.folder??'')+' '+(session.organization?.tags.join(' ')??'')).toLocaleLowerCase().includes(query));
  }, [onlyPendingSessions, pendingLibrary, recordingLibrary, libraryQuery,libraryFilters]);
  const connected = Boolean(snapshot?.connected || device?.connected);

  useEffect(() => {
    if(libraryFilters.trash)return;
    if (readableLibrary.length === 0) return;
    if (selectedSession) return;
    onControl({ action: 'meetingSelectSession', sessionId: readableLibrary[0].id });
  }, [selectedSession?.id, readableLibrary[0]?.id,libraryFilters.trash]);

  useEffect(() => {
    if (!openSavedRecordingId || selectedSession?.id !== openSavedRecordingId) return;
    setDetailSessionId(selectedSession.id);
    setOpenSavedRecordingId(null);
  }, [openSavedRecordingId, selectedSession?.id]);

  useEffect(()=>{if(savedDetailOpen)savedRecordingWorkspace.current?.scrollIntoView({block:'start'});},[savedDetailOpen,selectedSession?.id]);

  const openRecentSavedRecording = () => {
    if (!recentSavedRecording || controlsBusy) return;
    setPageView('library');
    setLibraryFilters({ folder: '*', tag: '', favorites: false });
    setLibraryQuery('');
    setOnlyPendingSessions(false);
    setOpenSavedRecordingId(recentSavedRecording.id);
    onControl({ action: 'meetingSelectSession', sessionId: recentSavedRecording.id });
  };

  useEffect(() => {
    if (snapshot) setDraftName(snapshot.bleName.stagedName);
  }, [snapshot?.bleName.stagedName]);

  useEffect(() => {
    if (transcriptEditor.current.sessionId !== selectedSession?.id) {
      transcriptEditor.current = { sessionId: selectedSession?.id, dirty: false };
    }
    if (!transcriptEditor.current.dirty) setTranscriptDraft(selectedSession?.transcriptText ?? '');
  }, [selectedSession?.id, selectedSession?.transcriptText]);

  useEffect(() => {
    setPendingDelete(null);
    setEditingMinutes(false);
    setSaveMeetingResult(null);
    setAudioResult(null);
    if (!selectedSession) return;
    setDraftTitle(selectedSession.title);
    if (selectedSession.meetingMode === 'onlineLive' || selectedSession.meetingMode === 'offlineStore') {
      setMeetingMode(selectedSession.meetingMode);
    }
    setRecordingResultOpen(Boolean(selectedSession.minutes?.markdown?.trim()
      || selectedSession.minutesByMode?.offlineStore?.markdown?.trim()
      || selectedSession.minutesByMode?.onlineLive?.markdown?.trim()));
    setPlaybackOpen(false);
    setTranscribePromptSession(null);
  }, [selectedSession?.id]);

  const nameError = draftName.length > 0 && !companionBleNameIsValid(draftName)
    ? 'BLE 名称不合法'
    : null;

  useEffect(()=>{
    // Deleting the last meeting unmounts its editor. Clear only its aggregate
    // flag; switching between existing meetings still preserves every draft.
    if (!selectedSession) {setBookmarkUnsaved(false);setBookmarkBusy(false);}
  },[selectedSession?.id]);

  const offlineMinutes = selectedSession?.minutesByMode?.offlineStore ?? null;
  const onlineMinutes = selectedSession?.minutesByMode?.onlineLive ?? null;
  const preferredMinutesMode = minutesSelection?.sessionId === selectedSession?.id
    ? minutesSelection?.mode : selectedSession?.meetingMode;
  // A recovering recording may have a transcript before either minutes variant
  // exists. Keep exports on its capture mode, then use only an available variant.
  const minutesViewMode: CompanionV1MeetingMode = preferredMinutesMode === 'onlineLive'
    ? (onlineMinutes || !offlineMinutes ? 'onlineLive' : 'offlineStore')
    : (offlineMinutes || !onlineMinutes ? 'offlineStore' : 'onlineLive');
  const setMinutesViewMode = (mode: CompanionV1MeetingMode) => {
    if (selectedSession) setMinutesSelection({ sessionId: selectedSession.id, mode });
    setEditingMinutes(false);
  };
  const selectedMinutesVariant = minutesViewMode === 'onlineLive' ? onlineMinutes : offlineMinutes;
  const recoveryView = selectedSession ? describeCompanionMeetingRecovery(selectedSession) : null;
  const finalTranscript = selectedSession ? companionSessionHasFinalTranscript(selectedSession) : false;
  const offlineReady = offlineMinutes?.status === 'minutesReady' && offlineMinutes.quality === 'final'
    && companionMinutesProcessingComplete(offlineMinutes.processing)
    && Boolean(selectedSession && companionMinutesMatchTranscript(selectedSession, offlineMinutes.sourceReviewRevision));
  const onlineReady = onlineMinutes?.status === 'minutesReady' && onlineMinutes.quality === 'final'
    && companionMinutesProcessingComplete(onlineMinutes.processing)
    && Boolean(selectedSession && companionMinutesMatchTranscript(selectedSession, onlineMinutes.sourceReviewRevision));
  const legacyMinutes = !offlineMinutes && !onlineMinutes && selectedSession?.meetingMode === minutesViewMode
    ? selectedSession.minutes : null;
  const selectedMinutesStale = Boolean(selectedSession && (selectedMinutesVariant || legacyMinutes)
    && (!companionMinutesMatchTranscript(selectedSession, (selectedMinutesVariant || legacyMinutes)?.sourceReviewRevision)
      || !companionMinutesNotesCurrent(selectedSession,(selectedMinutesVariant || legacyMinutes)?.sourceNoteContext)));
  const minutesMarkdown = selectedMinutesVariant?.markdown || legacyMinutes?.markdown || '';
  const minutesProcessing = (selectedMinutesVariant || legacyMinutes)?.processing;
  const recordingMode = selectedSession?.meetingMode === 'onlineLive' ? 'onlineLive' : 'offlineStore';
  const recordingModeMinutes = recordingMode === 'onlineLive' ? onlineMinutes : offlineMinutes;
  const legacyRecordingMinutes = !offlineMinutes && !onlineMinutes ? selectedSession?.minutes : null;
  const recordingMinutesUserEdited = recordingModeMinutes?.source === 'userEdited'
    || String(legacyRecordingMinutes?.source ?? '') === 'userEdited';
  const recordingModeLabel = recordingMode === 'onlineLive' ? '在线速记' : '先录后整理';
  const selectedDraft = selectedSession ? meetingDrafts[selectedSession.id] : undefined;
  const titleDraft = selectedSession
    ? selectedDraft?.title?.value ?? meetingTitle(selectedSession) : '';
  const minutesDraft = selectedSession
    ? selectedDraft?.minutes?.[minutesViewMode]?.value ?? minutesMarkdown : '';
  const titleDirty = Boolean(selectedSession && selectedDraft?.title);
  const minutesDirty = Boolean(selectedSession && selectedDraft?.minutes?.[minutesViewMode]);
  const hasMinutes = Boolean(minutesMarkdown.trim());
  const hasSyncedAudio = Boolean(
    selectedSession
    && selectedSession.status !== 'recording'
    && !['needs_device_sync','needs_segments','needs_local_audio'].includes(selectedSession.pendingReason ?? '')
    && (selectedSession.deviceRecordingKey ? selectedSession.audioStored && selectedSession.retention.audioCached
      && selectedSession.audioPath && selectedSession.audioBytes > 0
      : (selectedSession.audioPath || (selectedSession.audioStored && selectedSession.audioBytes > 0))),
  );
  const unimportedTranscriptDraft = Boolean(transcriptEditor.current.dirty && selectedSession
    && transcriptDraft.trim() !== (selectedSession.transcriptText ?? '').trim());
  const canGenerate = finalTranscript && !recoveryView?.isProcessing && !unimportedTranscriptDraft;
  const hasOriginalAudio = Boolean(hasSyncedAudio && selectedSession?.audioStored && selectedSession.retention.audioCached
    && selectedSession.audioPath && !/^(host|device|board):\/\//i.test(selectedSession.audioPath));
  const textOnlyImport = Boolean(selectedSession && isTextOnlyImport(selectedSession));
  const savedOriginalReady = Boolean(hasOriginalAudio && snapshot?.host.persistence?.status === 'ready'
    && !selectedSession?.captureIncomplete && !selectedSession?.recorderControlUncertain);
  const canTranscribe = Boolean(
    selectedSession
    && selectedSession.status !== 'recording'
    && !recoveryView?.isProcessing
    && hasSyncedAudio,
  );
  const canEraseAudio = !selectedSession?.organization?.protected&&Boolean(selectedSession?.audioPath || selectedSession?.audioBytes);
  const canEraseTranscript = !selectedSession?.organization?.protected&&Boolean(selectedSession?.transcriptText || selectedSession?.minutes || offlineMinutes || onlineMinutes || selectedSession?.meetingNotes?.length);
  const hasVerifiedBoardCopy = Boolean(selectedSession?.deviceRecordingId != null
    && selectedSession.sourceDeviceId && selectedSession.deviceTotalLength
    && /^[0-9a-f]{64}$/i.test(selectedSession.deviceSha256 ?? '') && !selectedSession.deviceReclaimed);
  const requestedDurationMs = Number(draftMinutes) * 60000;
  const boardMaxDurationSeconds = requestedDurationMs / 1000;
  const durationValid = draftMinutes.trim() !== '' && Number.isSafeInteger(requestedDurationMs)
    && requestedDurationMs > 0 && (!connected || boardMaxDurationSeconds <= 65535);
  const onlineDurationValid = durationValid && boardMaxDurationSeconds >= 12 && boardMaxDurationSeconds <= 2580;
  const durationError = !durationValid ? '请输入有效的录音时长，实际可录时间以设备空间为准。'
    : !onlineDurationValid ? '在线转写单次最多 43 分钟，请修改时长；不会自动截短。' : null;
  const capacity = connected ? device?.recordingCapacity : null;
  currentDiscardDevice.current = connected ? device?.deviceId ?? null : null;
  useEffect(() => { setDiscardMessage(null); }, [device?.deviceId, connected]);
  const capacitySeconds = capacity && capacity.usedEntries < capacity.maxEntries
    ? Math.max(0, Math.floor((capacity.largestFreeExtent - capacity.reserveHeadroom) / capacity.bytesPerSecond)) : 0;
  const capacityHint = !capacity ? '尚未取得设备容量，无法预估剩余时长；开始时由设备检查空间。'
    : capacity.busy ? '设备上次报告正在录音、回收或升级；开始前会重新检查。'
      : capacity.usedEntries >= capacity.maxEntries ? '设备录音目录已满，请同步并回收录音。'
        : `${formatBytes(capacity.freeBytes)} 空闲 · 连续可用约 ${formatDuration(capacitySeconds * 1000)} · 目录 ${capacity.usedEntries}/${capacity.maxEntries}`;
  const boardLiveActive = Boolean(
    boardOnlineLive
    && ['starting', 'recording', 'stopping', 'finalizing'].includes(boardOnlineLive.state),
  );
  const oobeBlockedByRecording = Boolean(
    snapshot?.meeting.active
    || device?.recording
    || recordingLibrary.some((session) => session.status === 'recording')
    || boardLiveActive,
  );
  const controlsBusy = busyAction !== null || Boolean(recordingSync?.jobId) || resourceBusy || boardOnlineBusy || exportBusy || saveMeetingBusy || bookmarkBusy || noteBusy || diagnosticBusy || serviceBusy !== null || discardBusy ||libraryBusy;
  const lossBudgetSeconds = Math.ceil(boardMaxDurationSeconds + (meetingMode === 'onlineLive' ? 120 : 0));
  const lossBudgetValid = durationValid && lossBudgetSeconds <= 65535 && (meetingMode !== 'onlineLive' || onlineDurationValid);
  const captureBudgetBytes = capacity && lossBudgetValid
    ? Math.ceil((lossBudgetSeconds * capacity.bytesPerSecond + capacity.reserveHeadroom) / 4096) * 4096 : null;
  const capacityInsufficient = Boolean(capacity && lossBudgetValid && (capacity.usedEntries >= capacity.maxEntries
    || (captureBudgetBytes ?? 0) > capacity.largestFreeExtent));
  const inspectRecordingLoss = async () => {
    if (!onDiscardOldestRecording || !capacity?.confirmedDiscardSupported || !capacityInsufficient
      || capacity.busy || !capacity.unsyncedEntries || controlsBusy || settingsBusy || oobeBlockedByRecording || discardActive.current) return;
    discardActive.current = true; setDiscardBusy(true); setDiscardMessage(null);
    const expectedDevice = currentDiscardDevice.current;
    try {
      const result = await onDiscardOldestRecording(lossBudgetSeconds);
      if (currentDiscardDevice.current === expectedDevice) setDiscardMessage(result.message);
    }
    catch (err) {
      if (currentDiscardDevice.current === expectedDevice) setDiscardMessage(err instanceof Error ? err.message : '操作未完成，请重新读取设备状态。');
    }
    finally { discardActive.current = false; setDiscardBusy(false); }
  };
  const serviceConfigKey = JSON.stringify([formAsrProvider, formVolcApp, formVolcAccess, formVolcResource,
    formOpenAiEndpoint, formOpenAiKey, formOpenAiModel, formDeepseekKey, formDeepseekBase, formDeepseekModel, formDeepseekEnabled,
    clearCredentials,
    productSettings?.volcAppKeySet, productSettings?.volcAccessKeySet, productSettings?.openaiAsrApiKeySet, productSettings?.deepseekApiKeySet]);
  const currentServiceConfig = useRef(serviceConfigKey);
  currentServiceConfig.current = serviceConfigKey;
  useEffect(() => { setServiceResults({}); }, [serviceConfigKey]);
  const serviceConfigDirty = !productSettings || clearCredentials.length > 0 || !!(formVolcApp || formVolcAccess || formOpenAiKey || formDeepseekKey)
    || formAsrProvider !== productSettings.asrProvider || formVolcResource !== productSettings.volcResourceId
    || formOpenAiEndpoint !== productSettings.openaiAsrEndpoint || formOpenAiModel !== productSettings.openaiAsrModel
    || formDeepseekBase !== productSettings.deepseekBaseUrl || formDeepseekModel !== productSettings.deepseekModel
    || formDeepseekEnabled !== productSettings.deepseekMinutesEnabled;
  const checkService = async (service: 'asr' | 'minutes') => {
    if (!onCheckService || controlsBusy || settingsBusy || oobeBlockedByRecording || productSettings?.storageSaveBlocked || serviceConfigDirty || serviceActive.current) return;
    serviceActive.current = true; setServiceBusy(service);
    const config = serviceConfigKey;
    setServiceResults(previous => ({ ...previous, [service]: undefined }));
    try {
      const result = await onCheckService(service);
      if (currentServiceConfig.current === config) setServiceResults(previous => ({...previous,
        [service]: `${result.message}（${Math.max(0, result.elapsedMs / 1000).toFixed(1)} 秒）`}));
    } catch {
      if (currentServiceConfig.current === config) setServiceResults(previous => ({...previous, [service]: '测试未完成，请确认录音已结束后重试。'}));
    } finally { serviceActive.current = false; setServiceBusy(null); }
  };
  const storageBlocked = Boolean(snapshot?.host.persistence && snapshot.host.persistence.status !== 'ready');
  const asrConfigured = productSettings?.asrProvider === 'volcengine'
    ? Boolean(productSettings.volcAppKeySet && productSettings.volcAccessKeySet)
    : Boolean(productSettings?.openaiAsrApiKeySet);
  useEffect(() => {
    onUnsavedChange?.(Boolean(productSettings && serviceConfigDirty) || Object.keys(meetingDrafts).length > 0 || transcriptEditor.current.dirty || transcriptReviewUnsaved || bookmarkUnsaved || noteUnsaved ||libraryUnsaved);
  }, [onUnsavedChange, serviceConfigDirty, productSettings, meetingDrafts, transcriptDraft, transcriptReviewUnsaved,bookmarkUnsaved,noteUnsaved,libraryUnsaved]);
  const missingServiceFields = [
    ...(formAsrProvider === 'volcengine'
      ? [!formVolcResource.trim() ? '火山 Resource ID' : '', clearCredentials.includes('volcAppKey') || !(formVolcApp.trim() || productSettings?.volcAppKeySet) ? '火山 App Key' : '', clearCredentials.includes('volcAccessKey') || !(formVolcAccess.trim() || productSettings?.volcAccessKeySet) ? '火山 Access Key' : '']
      : [!formOpenAiEndpoint.trim() ? '兼容服务 Endpoint' : '', !formOpenAiModel.trim() ? '兼容服务模型' : '', clearCredentials.includes('openaiAsrApiKey') || !(formOpenAiKey.trim() || productSettings?.openaiAsrApiKeySet) ? '兼容服务 Key' : '']),
    ...(formDeepseekEnabled
      ? [!formDeepseekBase.trim() ? 'DeepSeek Base URL' : '', !formDeepseekModel.trim() ? 'DeepSeek 模型' : '', clearCredentials.includes('deepseekApiKey') || !(formDeepseekKey.trim() || productSettings?.deepseekApiKeySet) ? 'DeepSeek Key' : ''] : []),
  ].filter(Boolean);
  const credentialField = (kind: NonNullable<CompanionProductSettingsPatch['clearCredentials']>[number], label: string,
    value: string, setValue: (value: string) => void, configured: boolean | undefined) => {
    const pending = clearCredentials.includes(kind);
    const blocked = controlsBusy || settingsBusy || oobeBlockedByRecording || !productSettings || productSettings.storageSaveBlocked;
    return <div className="ct-field" key={kind}>
      <label htmlFor={`ct-key-${kind}`}>{label} {pending ? '（待清空）' : configured ? '（已配置）' : ''}</label>
      <input id={`ct-key-${kind}`} type="password" autoComplete="off" value={pending ? '' : value}
        onChange={e => setValue(e.target.value)} disabled={blocked || pending} placeholder={pending ? '保存后清空' : '留空=保持原值'} spellCheck={false} />
      <button type="button" className="ct-text-button" aria-label={`${pending ? '撤销清空' : '清空'}${label}`}
        disabled={blocked || (!configured && !value && !pending)} onClick={() => {
          if (blocked || settingsActive.current) return;
          setClearCredentials(previous => pending ? previous.filter(key => key !== kind) : [...previous, kind]);
          setSettingsMsg(null);
        }}>{pending ? '撤销清空' : '清空密钥'}</button>
    </div>;
  };
  const openSettings = () => {
    setPageView('settings');
    setShowAdvanced(true);
    window.setTimeout(() => document.getElementById('ct-service-settings')?.scrollIntoView({ block: 'start', behavior: 'instant' }), 0);
  };
  const returnToRecording = () => {
    setPageView('library');
    if (selectedSession) setOpenSavedRecordingId(selectedSession.id);
  };
  const openDeviceRecording = () => {
    setPageView('device');
    setShowWorkflow(false);
    window.setTimeout(() => document.getElementById('ct-device-recording-page')?.scrollIntoView({ block: 'start' }), 0);
  };
  const openWorkflow = () => {
    setPageView('device');
    setShowWorkflow(true);
    window.setTimeout(() => document.getElementById('ct-workflow')?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 0);
  };
  const journey = selectedSession ? meetingJourney(selectedSession, {
    connected, deviceId: device?.deviceId, asrReady: asrConfigured,
    minutesReady: Boolean(productSettings?.deepseekMinutesEnabled && productSettings.deepseekApiKeySet),
  }) : null;
  const actualRecordingDurationMs = boardOnlineLive?.state === 'recording' ? boardOnlineLive.durationMs : 0;
  const recordingLimitMs = (boardOnlineLive?.maxDurationSeconds ?? 0) * 1000;
  const recordingRemainingMs = Math.max(0, recordingLimitMs - actualRecordingDurationMs);
  const nearRecordingLimit = recordingLimitMs > 0 && actualRecordingDurationMs > 0 && recordingRemainingMs <= 5 * 60 * 1000;
  const audioBlockedReason = !selectedSession ? '请先选择一场会议'
    : selectedSession.status === 'recording' || oobeBlockedByRecording ? '录音进行中，结束并保存后才能回听'
      : recoveryView?.isProcessing ? '正在处理这场会议，完成后才能回听'
        : !hasSyncedAudio ? '这场会议还没有可回听的本机原音'
          : !onPrepareAudio ? '原音回听仅在 Companion Type 桌面版可用'
            : null;
  const audioIdentity = selectedSession ? listeningIdentity(selectedSession) : '';
  const [sourceSelection, setSourceSelection] = useState<CompanionTranscriptSource | null>(null);
  const transcriptSources = useMemo(() => selectedSession ? companionTranscriptSources(selectedSession) : [], [selectedSession]);
  const sourceContext = useRef({ session: selectedSession, blocked: false });
  sourceContext.current = { session: selectedSession,
    blocked: controlsBusy || oobeBlockedByRecording || storageBlocked || transcriptReviewUnsaved };
  const externalAudioSeek = useRef<(() => void) | null>(null);
  const audioContext = useRef({ sessionId: selectedSession?.id ?? '', identity: audioIdentity, blocked: Boolean(audioBlockedReason) });
  audioContext.current = { sessionId: selectedSession?.id ?? '', identity: audioIdentity, blocked: Boolean(audioBlockedReason) };
  const preparedAudio = selectedSession && audioSources[selectedSession.id]?.identity === audioIdentity && !audioBlockedReason
    ? audioSources[selectedSession.id] : null;
  const listeningQueue=useListeningQueue({
    rows:allLibrarySessions.filter(row=>!row.organization?.trashedAt).map(row=>({id:row.id,title:`${meetingTitle(row)} · ${formatDuration(row.durationMs)} · ${row.deviceRecordingId!=null?`#${row.deviceRecordingId}`:'录音'} · ${row.startedAt??row.id.slice(-8)}`,identity:listeningIdentity(row),
      ready:row.status!=='recording'&&row.pendingReason!=='needs_device_sync'&&row.audioStored&&row.retention.audioCached
        &&Boolean(row.audioPath)&&!describeCompanionMeetingRecovery(row)?.isProcessing})),
    selectedId:selectedSession?.id??'',
    disabled:controlsBusy||audioBusy||titleDirty||minutesDirty||transcriptReviewUnsaved||bookmarkUnsaved||noteUnsaved||libraryUnsaved,
    hardBlocked:oobeBlockedByRecording||storageBlocked||Boolean(libraryFilters.trash),prepare:onPrepareAudio,
    select:id=>onControl({action:'meetingSelectSession',sessionId:id}),
    pause:()=>audioElement.current?.pause(),
    ready:(entry,audio,epoch)=>{
      setAudioSources(sources=>({...sources,[entry.id]:{url:audio.url,identity:entry.identity,
        sourceIdentity:audio.sourceIdentity,pauseTimeline:audio.pauseTimeline}}));
      setListeningEpoch(epoch); setPlaybackOpen(true);
    },
  });

  useEffect(() => {
    audioRequestId.current += 1;
    const sessionId = selectedSession?.id;
    if (!sessionId) return;
    setAudioSources((current) => {
      const source = current[sessionId];
      if (!source || (!audioBlockedReason && source.identity === audioIdentity)) return current;
      const next = { ...current }; delete next[sessionId]; return next;
    });
  }, [selectedSession?.id, audioIdentity, audioBlockedReason]);

  useEffect(() => {
    const player = audioElement.current;
    return () => {
      if (!player) return;
      player.pause();
      player.removeAttribute('src');
      player.load();
    };
  }, [preparedAudio?.url, audioIdentity]);
  const openRecordingResult = () => {
    setPageView('library');
    setRecordingResultOpen(true);
    window.setTimeout(() => document.getElementById('ct-recording-result')?.scrollIntoView({ block: 'start' }), 0);
  };
  const runOrganizationControl = (request: CompanionV1ControlRequest, explicitSource?:'original') => {
    const targetId = request.sessionId ?? selectedSession?.id;
    if (request.action === 'meetingGenerateMinutes' && targetId === selectedSession?.id) {
      if(snapshot?.minutesContextSupported && selectedSession?.meetingNotes?.length
          && request.contextNoteRevision==null && explicitSource!=='original') {
        setOrganizationChoiceId(selectedSession.id);
        window.requestAnimationFrame(()=>document.getElementById('ct-organization-source-choice')?.scrollIntoView({block:'nearest'}));
        return;
      }
      if (unimportedTranscriptDraft && targetId) {
        setSaveMeetingResult({ sessionId: targetId, kind: 'error',
          message: '尚有未导入的文字。请先在录音与同步中导入，或还原为已保存的转写；本次没有开始整理。' });
        setPageView('library');
        setOpenSavedRecordingId(targetId);
        return;
      }
      openRecordingResult();
    }
    if(request.action==='meetingGenerateMinutes' && targetId===selectedSession?.id && selectedSession) {
      if(noteUnsaved || minutesDirty || titleDirty || transcriptReviewUnsaved) {
        setSaveMeetingResult({sessionId:selectedSession.id,kind:'error',message:'还有未保存的修改，请先保存或取消，再整理。本次未提交。'});
        return;
      }
      if(request.contextNoteRevision!=null && !snapshot?.minutesContextSupported) {
        setSaveMeetingResult({sessionId:selectedSession.id,kind:'error',message:'当前整理程序尚未支持补充来源，请更新桌面 Type 后再试。本次未提交。'});
        return;
      }
      request={...request,meetingMode:request.meetingMode??minutesViewMode};
    }
    onControl(request);
  };
  const exportMeeting = async (format: CompanionMeetingExportRequest['format'], origin:'text'|'notes'|'document'='document') => {
    if (!selectedSession || !onExportMeeting || controlsBusy || oobeBlockedByRecording || exportActive.current) return;
    const sessionId = selectedSession.id;
    const unsavedForExport = titleDirty || transcriptReviewUnsaved
      || (format !== 'txt' && format !== 'srt' && minutesDirty)
      || ((format === 'json' || format === 'txt' || format === 'markdown') && (noteUnsaved || bookmarkUnsaved));
    if (unsavedForExport) {
      setExportResult({ sessionId, format, origin, kind: 'error', message: '还有未保存的修改。请先保存或取消修改，再导出；本次没有生成文件。' });
      return;
    }
    exportActive.current = true;
    setExportBusy(true);
    setExportResult({ sessionId, format, origin, kind: 'pending', message: '正在保存文件…' });
    try {
      const result = await onExportMeeting({ sessionId, meetingMode: minutesViewMode, format });
      setExportResult({ sessionId, format, origin, path: result?.path, kind: result ? 'saved' : 'cancelled', message: result ? `已保存：${exportFileName(result.path)}${result.warning ? `（${result.warning}）` : ''}${format === 'ics' ? '。请导入日历后核对日期与提醒；导出文件不会自动创建提醒。' : ''}` : '已取消保存，录音内容保持不变。' });
    } catch (error) {
      setExportResult({ sessionId, format, origin, kind: 'error', message: `保存未完成：${error instanceof Error ? error.message : String(error)}` });
    } finally { exportActive.current = false; setExportBusy(false); }
  };
  const exportAudio = async () => {
    if (!selectedSession || !onExportAudio || !hasOriginalAudio || controlsBusy || oobeBlockedByRecording || exportActive.current) return;
    const sessionId = selectedSession.id;
    exportActive.current = true; setExportBusy(true); setExportResult(null);
    try {
      const result = await onExportAudio(sessionId);
      setExportResult({ sessionId, message: result ? `原音已保存：${result.path}` : '已取消保存，原音保持不变。' });
    } catch (error) {
      setExportResult({ sessionId, message: `原音保存未完成：${error instanceof Error ? error.message : String(error)}` });
    } finally { exportActive.current = false; setExportBusy(false); }
  };
  const changeCurrentLibraryState=async(action:'protect'|'unprotect'|'trash')=>{
    if(!selectedSession||!onSaveLibraryLifecycle||controlsBusy||oobeBlockedByRecording||storageBlocked||libraryUnsaved||exportActive.current)return;
    exportActive.current=true;setLibraryBusy(true);setLibraryCurrentMessage('');
    try{await onSaveLibraryLifecycle({targets:[{sessionId:selectedSession.id,expectedRevision:selectedSession.organization?.revision??0}],action});
      setLibraryCurrentMessage(action==='trash'?'当前录音已移入本机回收站，可恢复；原音与设备数据保留。':action==='protect'?'当前录音已受保护，解除前不能删除音频、文字或整场。':'已解除当前录音保护。');
    }catch(e){setLibraryCurrentMessage(`未完成：${e instanceof Error?e.message:String(e)}`);}
    finally{exportActive.current=false;setLibraryBusy(false);}
  };
  const updateTitleDraft = (value: string) => {
    setSaveMeetingResult(null);
    if (!selectedSession) return;
    const sessionId = selectedSession.id;
    setMeetingDrafts((current) => ({
      ...current,
      [sessionId]: {
        ...current[sessionId],
        title: { value, expected: current[sessionId]?.title?.expected ?? selectedSession.title },
      },
    }));
  };
  const updateMinutesDraft = (value: string) => {
    setSaveMeetingResult(null);
    if (!selectedSession) return;
    const sessionId = selectedSession.id;
    const mode = minutesViewMode;
    setMeetingDrafts((current) => ({
      ...current,
      [sessionId]: {
        ...current[sessionId],
        minutes: {
          ...current[sessionId]?.minutes,
          [mode]: { value, expected: current[sessionId]?.minutes?.[mode]?.expected ?? minutesMarkdown },
        },
      },
    }));
  };
  const cancelMeetingDraft = (part: 'title' | 'minutes') => {
    if (!selectedSession) return;
    const sessionId = selectedSession.id;
    setMeetingDrafts((current) => {
      const session = current[sessionId];
      if (!session) return current;
      const nextSession = { ...session };
      if (part === 'title') delete nextSession.title;
      else nextSession.minutes = { ...nextSession.minutes, [minutesViewMode]: undefined };
      return { ...current, [sessionId]: nextSession };
    });
    if (part === 'minutes') setEditingMinutes(false);
    setSaveMeetingResult(null);
  };
  const saveMeetingDraft = async () => {
    if (!selectedSession || !onSaveMeeting || saveMeetingBusy || (!titleDirty && !minutesDirty)) return;
    const sessionId = selectedSession.id;
    const mode = minutesViewMode;
    const title = selectedDraft?.title;
    const minutes = selectedDraft?.minutes?.[mode];
    const resultPart = minutes ? 'minutes' : 'title';
    const submittedTitle = title ? title.value.trim() : undefined;
    const submittedMinutes = minutes ? minutes.value.trim() : undefined;
    setSaveMeetingBusy(true);
    setSaveMeetingResult(null);
    try {
      const next = await onSaveMeeting({
        sessionId,
        ...(title ? { title: submittedTitle, expectedTitle: title.expected } : {}),
        ...(minutes ? { meetingMode: mode, markdown: submittedMinutes, expectedMarkdown: minutes.expected } : {}),
      });
      const savedSession = next.host.sessions.find((item) => item.id === sessionId);
      if (next.host.persistence?.status !== 'ready') {
        // The host may have updated its in-memory snapshot before durable storage
        // failed. Rebase only an unchanged submitted draft so retry remains
        // idempotent instead of conflicting with that same value.
        setMeetingDrafts((current) => {
          const currentSession = current[sessionId];
          if (!currentSession) return current;
          const nextSession = { ...currentSession };
          if (title && currentSession.title?.value === title.value && currentSession.title.expected === title.expected
            && savedSession?.title === submittedTitle) nextSession.title = { ...currentSession.title, expected: submittedTitle ?? '' };
          const currentMinutes = currentSession.minutes?.[mode];
          if (minutes && currentMinutes?.value === minutes.value && currentMinutes.expected === minutes.expected
            && savedSession && meetingMinutesMarkdown(savedSession, mode) === submittedMinutes) {
            nextSession.minutes = { ...currentSession.minutes, [mode]: { ...currentMinutes, expected: submittedMinutes ?? '' } };
          }
          return { ...current, [sessionId]: nextSession };
        });
        setSaveMeetingResult({ sessionId, part: resultPart, kind: 'error', message: next.host.persistence?.message ?? '修改尚未安全保存，草稿已保留，请重试。' });
        return;
      }
      setMeetingDrafts((current) => {
        const session = current[sessionId];
        if (!session) return current;
        const currentTitle = session.title;
        const currentMinutes = session.minutes?.[mode];
        return { ...current, [sessionId]: {
          ...session,
          title: title && currentTitle?.value === title.value && currentTitle.expected === title.expected ? undefined : currentTitle,
          minutes: minutes && currentMinutes?.value === minutes.value && currentMinutes.expected === minutes.expected
            ? { ...session.minutes, [mode]: undefined } : session.minutes,
        } };
      });
      setEditingMinutes(false);
      setSaveMeetingResult({ sessionId, part: resultPart, kind: 'saved', message: '修改已保存。' });
    } catch (saveError) {
      setSaveMeetingResult({ sessionId, part: resultPart, kind: 'error', message: `未保存，草稿仍在：${saveError instanceof Error ? saveError.message : String(saveError)}` });
    } finally {
      setSaveMeetingBusy(false);
    }
  };
  const markAction = async (lineIndex:number,completed:boolean) => {
    if(!selectedSession||!onSaveMeeting||actionSaveActive.current||controlsBusy||oobeBlockedByRecording
      ||storageBlocked||selectedMinutesStale||Boolean(minutesProcessing&&!companionMinutesProcessingComplete(minutesProcessing))||editingMinutes||minutesDirty||titleDirty
      ||noteUnsaved||transcriptReviewUnsaved||unimportedTranscriptDraft)return;
    const original=minutesMarkdown;
    const updated=markSavedAction(original,lineIndex,completed);
    if(updated===null)return;
    const sessionId=selectedSession.id;const mode=minutesViewMode;
    actionSaveActive.current=true;setSaveMeetingBusy(true);setSaveMeetingResult(null);
    try {
      const next=await onSaveMeeting({sessionId,meetingMode:mode,markdown:updated,expectedMarkdown:original});
      const row=next.host.sessions.find(item=>item.id===sessionId);
      if(next.host.persistence?.status!=='ready'||!row||meetingMinutesMarkdown(row,mode)!==updated.trim())
        throw new Error(next.host.persistence?.message??'尚未确认清单已安全保存，请先核对本机保存状态。');
      setSaveMeetingResult({sessionId,part:'minutes',kind:'saved',message:completed?'已完成并保存。':'已恢复为待办并保存。'});
    } catch(error) {
      setSaveMeetingResult({sessionId,part:'minutes',kind:'error',message:`未确认保存：${error instanceof Error?error.message:String(error)}`});
    } finally {actionSaveActive.current=false;setSaveMeetingBusy(false);}
  };
  const prepareAudio = async () => {
    if (!selectedSession || !onPrepareAudio || audioBusy || audioBlockedReason) return;
    if(listeningQueue.active)listeningQueue.stop();
    const sessionId = selectedSession.id;
    const requestedIdentity = audioIdentity;
    const requestId = ++audioRequestId.current;
    setAudioBusy(true);
    setAudioResult(null);
    try {
      const prepared = await onPrepareAudio(sessionId);
      if (prepared.sessionId !== sessionId || !prepared.url) throw new Error('桌面端没有返回这场会议的授权音频');
      const current = audioContext.current;
      if (requestId !== audioRequestId.current || current.sessionId !== sessionId
        || current.identity !== requestedIdentity || current.blocked) return;
      setAudioSources((sources) => ({ ...sources, [sessionId]: { url: prepared.url, identity: requestedIdentity, sourceIdentity: prepared.sourceIdentity, pauseTimeline: prepared.pauseTimeline } }));
    } catch (prepareError) {
      setAudioResult({ sessionId, message: `无法回听：${prepareError instanceof Error ? prepareError.message : String(prepareError)}` });
    } finally {
      setAudioBusy(false);
    }
  };
  const seekBookmark = async (sessionId:string,bookmarkId:string,positionMs:number) => {
    setPlaybackOpen(true);
    const point=selectedSession?.bookmarks?.find((b)=>b.id===bookmarkId);
    if (!selectedSession||selectedSession.id!==sessionId||!point
      ||companionBookmarkAudioPosition(selectedSession,point)!==positionMs) throw new Error('重点所属原音已变化，请重新核对。');
    const identity=audioIdentity;
    await seekBookmarkAudio(positionMs,async()=>{if(!preparedAudio) await prepareAudio();},()=>audioElement.current,
      ()=>audioContext.current.sessionId===sessionId&&audioContext.current.identity===identity&&!audioContext.current.blocked,
      () => externalAudioSeek.current?.());
    setAudioResult({sessionId,message:'已定位到重点。点击原音播放器的播放按钮即可回听。'});
  };
  const openTranscriptSource = (source: CompanionTranscriptSource) => {
    if (!selectedSession || selectedMinutesStale || transcriptReviewUnsaved || controlsBusy
      || !companionTranscriptSourceIsCurrent(selectedSession, source)) return;
    // A fresh selection also re-locates the same source after manual scrolling.
    setSourceSelection({ ...source }); setRecordingToolsOpen(true);
  };
  const seekTranscriptSource = async (source: CompanionTranscriptSource) => {
    const valid = () => Boolean(sourceContext.current.session && !sourceContext.current.blocked
      && companionTranscriptSourceIsCurrent(sourceContext.current.session, source));
    setPlaybackOpen(true);
    if (!valid() || audioBlockedReason || controlsBusy || transcriptReviewUnsaved)
      throw new Error('这段转写或原音尚不可回听，请结束处理并重新核对。');
    const identity = audioIdentity;
    await seekBookmarkAudio(source.startMs, async () => { if (!preparedAudio) await prepareAudio(); }, () => audioElement.current,
      () => valid() && audioContext.current.sessionId === source.sessionId
        && audioContext.current.identity === identity && !audioContext.current.blocked, () => externalAudioSeek.current?.());
    setAudioResult({ sessionId: source.sessionId, message: '已定位到这段原音。点击播放器的播放按钮即可回听。' });
  };
  const requestErase = (action: CompanionV1ControlAction, title: string, detail: string) => {
    setPendingDelete({
      request: { action, sessionId: selectedSession?.id, deviceId: device?.deviceId ?? undefined },
      title, detail,
    });
  };

  // Product path: board required for primary minutes flow.
  let step = 1;
  if (connected) step = 2;
  if (hasSyncedAudio) step = 3;
  if (finalTranscript) step = 4;
  if (hasMinutes && !selectedMinutesStale) step = 5;

  // Global status describes the device/library. A previously selected
  // recording's processing result belongs to its own detail panel.
  const simpleStatus = boardLiveActive ? 'Companion 正在录音'
    : oobeBlockedByRecording ? '录音进行中'
      : pageView === 'library' ? recordingLibrary.length ? '已有内容可直接查看' : '从 Companion 录下第一条想法'
        : !connected ? '连接 Companion 后可录制新内容' : '设备已识别，可以开始录音';

  const footer = useMemo(() => {
    if (error) return error;
    if (nameError) return nameError;
    if (recoveryView) return recoveryView.message;
    if (selectedMinutesStale) return '原始文字和修订已保留。请重新生成或核对当前纪要，再导出待办。';
    if (hasMinutes) return (selectedMinutesVariant?.quality ?? selectedSession?.minutes?.quality) === 'final'
      ? '纪要已保存，可以核对并导出。' : '纪要草稿已保存，可以查看或继续整理。';
    if (!connected) return recordingLibrary.length
      ? '可先查看录音库里的内容；连接设备后可继续同步。'
      : '连接 Companion，同步录音后在这里查看。';
    return '在 Companion 上录音，回到电脑同步并整理。';
  }, [error, nameError, connected, recordingLibrary.length, hasMinutes, selectedMinutesStale, recoveryView?.message, selectedMinutesVariant?.quality, selectedSession?.minutes?.quality]);

  return (
    <main className={`ct-shell ct-simple ct-${surface}${pageView==='library'&&!savedDetailOpen?' ct-library-overview':''}`}>
      <header className="ct-topbar">
        <div>
          <p className="ct-kicker">Companion Type</p>
          <h1>{pageView === 'library' ? savedDetailOpen?'录音详情':'我的录音' : pageView === 'device' ? '设备与同步' : '设置与工具'}</h1>
        </div>
        <button
          className="ct-icon-button"
          type="button"
          onClick={onRefresh}
          disabled={busyAction !== null}
          title="刷新"
          aria-label="刷新"
        >
          <RefreshCw size={18} />
        </button>
      </header>

      <nav className="ct-page-navigation" aria-label="主要功能">
        <button type="button" aria-current={pageView === 'library' ? 'page' : undefined}
          onClick={() => {setPageView('library');setDetailSessionId(null);}}><Headphones size={16} />我的录音</button>
        <button type="button" aria-current={pageView === 'device' ? 'page' : undefined}
          onClick={() => setPageView('device')}><Bluetooth size={16} />设备与同步</button>
        <button type="button" aria-current={pageView === 'settings' ? 'page' : undefined}
          onClick={() => { setPageView('settings'); setShowAdvanced(true); }}><ChevronDown size={16} />设置与工具</button>
      </nav>

      <section className="ct-simple-status" aria-live="polite">
        <span className={`ct-simple-dot ${connected ? 'ok' : 'idle'}`} />
        <strong>{simpleStatus}</strong>
        <span className="ct-simple-sub">
          {connected
            ? '设备已识别 · 使用时连接'
            : '设备不在身边也能查看本机内容'}
        </span>
      </section>

      <div className="ct-page-panel" hidden={pageView !== 'library'}>
      {recentSavedRecording && !oobeBlockedByRecording && !savedDetailOpen ? <section className="ct-recent-recording" aria-label={localSaveConfirmed ? '最近保存的录音' : '最近录音，保存状态待确认'}>
        <div>
          <span className="ct-section-eyebrow">{localSaveConfirmed ? '最近保存的录音' : '最近录音 · 保存待确认'}</span>
          <strong>{meetingTitle(recentSavedRecording)}</strong>
          {companionReviewedTranscript(recentSavedRecording).trim() ? <p className="ct-recent-preview">
            {!companionSessionHasFinalTranscript(recentSavedRecording)?<span className="ct-library-text-partial">片段 · </span>:null}
            {companionReviewedTranscript(recentSavedRecording).trim()}</p> : null}
          <small><time dateTime={recentSavedRecording.startedAt ?? undefined}>{recordingTimeLabel(recentSavedRecording.startedAt)}</time>
            {' · '}{formatDuration(recentSavedRecording.durationMs)}</small>
          {!localSaveConfirmed ? <p className="ct-step-warn" role="alert">本机保存尚未确认，请打开这条录音查看保存状态。</p> : null}
          {recentSavedRecording.captureIncomplete ? <p>已保存的录音片段可回听，完整录音仍待核对。</p> : null}
        </div>
        <button type="button" className="ct-action ct-action-primary" disabled={controlsBusy}
          onClick={openRecentSavedRecording}><Headphones size={16} />打开这条录音</button>
      </section> : null}

      </div>

      {error ? (
        <section className="ct-pending-banner" role="alert">{error}</section>
      ) : null}
      {!error && snapshot?.lastControl?.accepted === false ? (
        <section className="ct-pending-banner" role="alert">{snapshot.lastControl.message}</section>
      ) : null}

      <CompanionRecordingSync status={recordingSync} pauseBusy={pauseSyncBusy}
        resumeBlocked={controlsBusy || storageBlocked || boardLiveActive || (oobeBlockedByRecording && !pausedSyncRecorder)} onPause={onPauseSync}
        onResume={(deviceId) => onControl({ action: 'deviceSyncRecordings', deviceId, title: draftTitle,
          ...(pausedSyncRecorder ? { sessionId: pausedSyncRecorder.id } : {}) })} />

      {!boardLiveActive ? <CompanionRecorderControl session={controlledRecorder} busy={controlsBusy} onControl={onControl} /> : null}

      {boardLiveActive && boardOnlineLive ? <section className="ct-recording-activity" aria-label="当前录音" aria-live="polite">
        <div><strong>{boardOnlineLive.state === 'starting' ? '正在准备录音'
          : boardOnlineLive.state === 'recording' ? '正在录音'
            : boardOnlineLive.state === 'stopping' ? '正在收齐录音' : '录音已结束，正在整理'}</strong>
          <p>{boardOnlineLive.state === 'recording' ? '声音正在由 Companion 采集，结束后继续转写与整理。'
            : '请保持设备在附近，当前录音还在处理中。'}
            {boardOnlineLive.durationMs > 0 ? ` · ${formatDuration(boardOnlineLive.durationMs)}` : ''}
            {nearRecordingLimit ? ` · 距本次设定结束约 ${formatDuration(recordingRemainingMs)}` : ''}</p></div>
        <button type="button" className="ct-action" disabled={controlsBusy || boardOnlineLive.state !== 'recording' || !onStopBoardOnlineLive}
          onClick={() => onStopBoardOnlineLive?.()}><Square size={15} />结束录音并整理</button>
      </section> : null}

      {!boardLiveActive && !controlledRecorder && oobeBlockedByRecording ? <section className="ct-recording-activity" aria-label="当前录音">
        <div><strong>{device?.recording ? '设备录音中 · 上次读取' : '正在录音'}</strong>
          <p>{device?.recording && !snapshot?.meeting.active ? '在 Companion 上结束录音后，读取设备状态，再同步到电脑。' : '结束当前录音后，再整理文字与纪要。'}设备检查、提示音和更新暂时停用。</p></div>
        {snapshot?.meeting.active ? <button type="button" className="ct-action" disabled={controlsBusy}
          onClick={() => onControl({ action: 'meetingStop', sessionId: snapshot.host.activeSessionId ?? undefined })}><Square size={15} />结束录音</button>
          : <button type="button" className="ct-action" disabled={controlsBusy}
            onClick={() => onControl({ action: 'deviceConnect', deviceId: device?.deviceId ?? undefined })}><RefreshCw size={15} />读取设备状态</button>}
      </section> : null}

      <div className="ct-page-panel" hidden={pageView !== 'library'}>
      {snapshot ? <CompanionRecoveryCenter snapshot={snapshot} blocked={controlsBusy || oobeBlockedByRecording}
        savingBusy={controlsBusy} asrReady={asrConfigured}
        minutesReady={Boolean(productSettings?.deepseekMinutesEnabled && productSettings.deepseekApiKeySet)}
        onSelectSession={sessionId=>{setOpenSavedRecordingId(sessionId);onControl({action:'meetingSelectSession',sessionId});}}
        onControl={runOrganizationControl} onSettings={openSettings} onWorkflow={openWorkflow} /> : null}
      <section className="ct-library" aria-label="录音历史" hidden={savedDetailOpen}>
        <div className="ct-library-head">
          <div>
            <p className="ct-section-eyebrow">RECORDING LIBRARY</p>
            <strong>{libraryFilters.trash?'回收站':'录音库'}</strong>
            <p>{recordingLibrary.length} 条录音{libraryFilters.trash?' · 回收站':''}</p>
          </div>
          <div className="ct-button-row">
          <button type="button" className="ct-action ct-action-primary" onClick={openDeviceRecording}>
            <Mic size={15} />用 Companion 录音</button>
          <button type="button" className="ct-library-filter" aria-pressed={onlyPendingSessions}
            onClick={() => setOnlyPendingSessions((value) => !value)}>{onlyPendingSessions ? '显示全部录音' : '只看待整理'}</button>
          </div>
        </div>
        <label className="ct-library-search"><Search size={15} /><span className="ct-sr-only">搜索录音全文</span>
          <input value={libraryQuery} onChange={(event) => setLibraryQuery(event.target.value)}
            placeholder="搜索录音和补充" aria-label="搜索标题、转写、补充或整理结果" />
          {libraryQuery ? <button type="button" onClick={() => setLibraryQuery('')}>清除</button> : null}
        </label>
        <details className="ct-library-more" open={libraryToolsOpen}
          onToggle={event=>setLibraryToolsOpen(event.currentTarget.open)}>
          <summary>筛选与整理{libraryFilters.folder!=='*'||libraryFilters.tag||libraryFilters.favorites||libraryFilters.from||libraryFilters.to||libraryFilters.trash?' · 已筛选':''}{Object.keys(librarySelection).length?` · 已选 ${Object.keys(librarySelection).length} 条`:''}</summary>
        <CompanionLibraryTools sessions={allLibrarySessions} visible={visibleLibrary} selection={librarySelection} setSelection={setLibrarySelection}
          filters={libraryFilters} setFilters={setLibraryFilters} blocked={controlsBusy||oobeBlockedByRecording||storageBlocked}
          onSave={onSaveLibraryOrganization} onExport={onExportLibrary} onSaveLifecycle={onSaveLibraryLifecycle} onPurge={onPurgeLibrary} onBusyChange={setLibraryBusy} onUnsavedChange={setLibraryUnsaved}/>
        </details>
        {libraryCurrentMessage?<p role="status">{libraryCurrentMessage}</p>:null}
        {visibleLibrary.length===0&&(libraryFilters.folder!=='*'||libraryFilters.tag||libraryFilters.favorites||libraryFilters.from||libraryFilters.to)?<div className="ct-library-empty">
          <strong>当前筛选没有录音</strong><p>文件夹、标签、收藏、日期与搜索会同时筛选。清除筛选后可查看已有录音。</p>
          <button type="button" className="ct-action" onClick={()=>{setLibraryFilters({folder:'*',tag:'',favorites:false,trash:libraryFilters.trash});setLibraryQuery('');setOnlyPendingSessions(false);}}>清除分类筛选</button>
        </div>:visibleLibrary.length === 0 ? (
          <div className="ct-library-empty"><FileText size={26} /><strong>{libraryQuery ? '没有找到相关录音或补充' : libraryFilters.trash?'回收站为空':onlyPendingSessions && recordingLibrary.length ? '暂时没有待整理的录音' : '把值得记住的事，留在这里'}</strong>
            <p>{libraryQuery ? '搜索会检查标题、完整转写、已保存的补充和整理结果。' : libraryFilters.trash?'移入回收站的录音会保留原音和资料，直到你恢复或明确永久清除。':onlyPendingSessions && recordingLibrary.length ? '切回全部录音，可以查看已完成的内容。' : '在 Companion 上长按实体键约 1 秒开始或停止录音，睡着时先短按唤醒。结束后连接电脑同步；转写与纪要按需使用已配置的服务。'}</p>
            <button type="button" className="ct-action" onClick={libraryQuery ? () => setLibraryQuery('') : libraryFilters.trash?()=>setLibraryFilters({folder:'*',tag:'',favorites:false}):onlyPendingSessions && recordingLibrary.length ? () => setOnlyPendingSessions(false) : openWorkflow}>{libraryQuery ? '清除搜索' : libraryFilters.trash?'回到录音库':onlyPendingSessions && recordingLibrary.length ? '查看全部会议' : '查看录音与同步步骤'}</button></div>
        ) : (
          <div className="ct-library-list">
            {visibleLibrary.map((session) => {
              const selected = session.id === snapshot?.host.selectedSessionId;
              const boardId = session.deviceRecordingId;
              // Preview only saved text. Bound work per row and preserve the full original.
              const query = libraryQuery.trim().toLocaleLowerCase();
              const matchedNote = query ? session.meetingNotes?.find(note => note.text.toLocaleLowerCase().includes(query)) : undefined;
              const previewText = (matchedNote?.text ?? companionReviewedTranscript(session)).replace(/\s+/g, ' ').trim();
              const matchPosition = matchedNote ? previewText.toLocaleLowerCase().indexOf(query) : -1;
              const previewStart = Math.max(0, matchPosition - 24);
              const previewChars = Array.from(previewText.slice(previewStart, previewStart + 400));
              const textPreview = (previewStart ? '…' : '') + previewChars.slice(0, 96).join('') + (previewChars.length > 96 ? '…' : '');
              const statusLabel = session.organization?.trashedAt ? '回收站'
                : session.status === 'recording' ? '录制中'
                : session.pendingReason === 'needs_device_sync' ? '待同步'
                : session.pendingReason === 'needs_segments' ? '同步未完成'
                : !localSaveConfirmed ? '保存待确认'
                : describeCompanionMeetingRecovery(session)?.label ?? (meetingHasFinalMinutes(session)
                ? '纪要完成'
                : session.minutes?.markdown || session.minutesByMode?.offlineStore || session.minutesByMode?.onlineLive ? '纪要草稿'
                : session.status === 'transcribed'
                  ? session.source === 'importedTranscript' ? '已导入' : '已转写'
                  : session.pendingReason === 'needs_transcription'
                    ? '待转写'
                    : '已保存');
              return (
                <div className="ct-library-entry" key={session.id}>
                {libraryToolsOpen&&(onSaveLibraryOrganization||onExportLibrary||onSaveLibraryLifecycle)?<input type="checkbox" aria-label={`选择整理 ${meetingTitle(session)} ${formatDuration(session.durationMs)}`}
                  checked={Object.hasOwn(librarySelection,session.id)} disabled={controlsBusy||oobeBlockedByRecording||storageBlocked}
                  onChange={e=>setLibrarySelection(old=>{const next={...old};if(e.target.checked)next[session.id]=session.organization?.revision??0;else delete next[session.id];return next;})}/>:null}
                <button
                  type="button"
                  key={session.id}
                  className={`ct-library-card ${selected ? 'selected' : ''}`}
                  onClick={() => {setOpenSavedRecordingId(session.id); onControl({ action: 'meetingSelectSession', sessionId: session.id });}}
                  disabled={busyAction !== null||Boolean(libraryFilters.trash)}
                  aria-pressed={selected}
                  title={session.sourceDeviceId ? `来源设备：${session.sourceDeviceId}` : undefined}
                >
                  <span className="ct-library-icon"><FileText size={17} /></span>
                  <span className="ct-library-card-main">
                    <strong>{meetingTitle(session)}</strong>
                    <small><time dateTime={session.startedAt ?? undefined}>{recordingTimeLabel(session.startedAt)}</time></small>
                    {textPreview ? <span className="ct-library-text-preview">
                      {matchedNote ? <span className="ct-library-text-partial">补充 · </span> : !companionSessionHasFinalTranscript(session) ? <span className="ct-library-text-partial">片段 · </span> : null}{textPreview}
                    </span> : null}
                    {session.organization?.protected?<small>已保护</small>:null}
                    {session.organization?.trashedAt?<small>移入时间：{session.organization.trashedAt}</small>:null}
                    {session.organization&&(session.organization.favorite||session.organization.folder||session.organization.tags.length)?<small>
                      {session.organization.favorite?'★ 收藏 · ':''}{session.organization.folder||'未分类'}{session.organization.tags.length?' · '+session.organization.tags.join(' · '):''}
                    </small>:null}
                    <small>
                      {meetingSource(session)}{boardId != null ? ` #${boardId}` : ''}
                      {' · '}{formatDuration(session.durationMs)}
                      {' · '}{formatBytes(session.audioBytes)}
                      {session.sourceDeviceId ? ` · 设备 ${session.sourceDeviceId.replace(/[:-]/g, '').slice(-4).toUpperCase()}` : ''}
                    </small>
                  </span>
                  <span className={`ct-library-status ct-library-status-${session.status}`}>{statusLabel}</span>
                </button>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {surface==='windows'&&onPrepareAudio ? <details className="ct-library-more ct-listening-more" hidden={savedDetailOpen&&!listeningQueue.active}>
        <summary>连续回听{listeningQueue.active?' · 正在播放':''}</summary>
        <section className="ct-audio-card" aria-label="原音播放队列">
        <strong>原音播放队列</strong>
        <p>加入要回听的录音，再开始连续播放。切换会议、开始录音或原音发生变化时会停止；队列仅用于本次打开的软件。</p>
        <div className="ct-audio-tools">
          <button type="button" className="ct-action" disabled={Boolean(audioBlockedReason)||controlsBusy||audioBusy||listeningQueue.busy}
            onClick={()=>void listeningQueue.add()}>将当前录音加入队列</button>
          <button type="button" className="ct-action" disabled={!listeningQueue.items.length||Boolean(listeningQueue.active)||controlsBusy||oobeBlockedByRecording||storageBlocked||listeningQueue.busy||titleDirty||minutesDirty||transcriptReviewUnsaved||bookmarkUnsaved||noteUnsaved||libraryUnsaved}
            onClick={listeningQueue.start}>开始连续播放</button>
          <button type="button" className="ct-action" disabled={!listeningQueue.active} onClick={()=>listeningQueue.stop()}>停止连续播放</button>
          <button type="button" className="ct-action" disabled={!listeningQueue.items.length||listeningQueue.busy} onClick={listeningQueue.clear}>清空播放队列</button>
        </div>
        {listeningQueue.items.length ? <ol>{listeningQueue.items.map(item=><li key={item.id}>
          <span>{item.title}{listeningQueue.active?.entry.id===item.id?' · 当前回听':''}</span>{' '}
          <button type="button" className="ct-text-button" onClick={()=>listeningQueue.remove(item.id)} aria-label={`从队列移除${item.title}`}>移除</button>
        </li>)}</ol> : <p>队列为空。</p>}
        {listeningQueue.message?<p role="status">{listeningQueue.message}</p>:null}
      </section></details>:null}
      {selectedSession ? (
        <section ref={savedRecordingWorkspace} className="ct-meeting-workspace" aria-label="当前录音" hidden={!savedDetailOpen}>
          <button type="button" className="ct-text-button ct-recording-back" disabled={controlsBusy}
            onClick={()=>{setDetailSessionId(null);window.scrollTo({top:0});}}>← 返回录音库</button>
          <header className="ct-meeting-hero">
            <div>
              <p className="ct-section-eyebrow">{textOnlyImport ? '导入文字' : '录音内容'}</p>
              <label className="ct-title-editor"><span className="ct-sr-only">录音标题</span><Pencil size={15} />
                <input value={titleDraft} maxLength={120} aria-label="录音标题"
                  readOnly={!onSaveMeeting || saveMeetingBusy} title={!onSaveMeeting ? '请在桌面版编辑标题' : undefined}
                  onChange={(event) => updateTitleDraft(event.target.value)} /></label>
              <p>{recordingTimeLabel(selectedSession.startedAt)} · {formatDuration(selectedSession.durationMs)}</p>
              {titleDirty ? <div className="ct-inline-edit-actions">
                <button type="button" className="ct-text-button" disabled={saveMeetingBusy || !titleDraft.trim()} onClick={() => void saveMeetingDraft()} aria-busy={saveMeetingBusy}>{saveMeetingBusy ? '正在保存…' : '保存标题'}</button>
                <button type="button" className="ct-text-button" disabled={saveMeetingBusy} onClick={() => cancelMeetingDraft('title')}>取消</button>
              </div> : null}
            </div>
            <div className="ct-meeting-badges">
              {finalTranscript ? <span className="ct-pill ct-pill-good">{selectedSession.source === 'importedTranscript' ? '已导入文字' : '转写完成'}</span>
                : <span className="ct-pill">{selectedSession.transcriptText ? '片段转写'
                  : selectedSession.processingPolicy === 'manual' && savedOriginalReady ? '原音已保存' : '尚未转写'}</span>}
              {offlineMinutes ? <span className="ct-pill">{offlineReady ? '先录后整理' : '整理草稿'}</span> : null}
              {onlineMinutes ? <span className="ct-pill">{onlineReady ? '在线纪要' : '在线草稿'}</span> : null}
            </div>
          </header>
          {saveMeetingResult?.sessionId === selectedSession.id ? <p className={saveMeetingResult.kind === 'error' ? 'ct-recording-notice ct-step-warn ct-save-result' : 'ct-recording-notice ct-step-ok ct-save-result'} role="status">{saveMeetingResult.message}</p> : null}
          {!savedOriginalReady ? <RecordingSafetyCard session={selectedSession} persistence={snapshot?.host.persistence} recoveryProcessing={Boolean(recoveryView?.isProcessing)} /> : null}
          <div className="ct-recording-primary-actions">
            {!finalTranscript ? <button type="button" className="ct-action ct-action-primary"
              disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !canTranscribe || transcriptReviewUnsaved || minutesDirty || transcriptEditor.current.dirty}
              onClick={() => {
                if (!canTranscribe || controlsBusy || oobeBlockedByRecording || storageBlocked || transcriptReviewUnsaved || minutesDirty || transcriptEditor.current.dirty) return;
                if (!asrConfigured) {setTranscribePromptSession(selectedSession.id); return;}
                setTranscribePromptSession(null);
                onControl({action:'meetingTranscribeAudio',sessionId:selectedSession.id});
              }}><FileText size={16}/>{recoveryView?.isProcessing?'正在处理…':selectedSession.captureIncomplete?'片段转文字':'转文字'}</button> : null}
            {!textOnlyImport ? <button type="button" className="ct-action" aria-expanded={playbackOpen} aria-controls="ct-recording-playback"
              disabled={Boolean(audioBlockedReason) || audioBusy} title={audioBlockedReason ?? undefined}
              onClick={() => {
                if (playbackOpen) {audioElement.current?.pause(); setPlaybackOpen(false); return;}
                setPlaybackOpen(true); if (!preparedAudio) void prepareAudio();
              }}><Headphones size={16}/>{audioBusy?'正在准备…':playbackOpen?'收起回听':'回听'}</button> : null}
          </div>
          {transcribePromptSession===selectedSession.id && !asrConfigured ? <p className="ct-recording-notice" role="status">
            转文字需要先配置转写服务，原音已保留。<button type="button" className="ct-text-button" onClick={openSettings}>去配置</button>
          </p> : null}
          {recoveryView?.isProcessing ? <p className="ct-recording-notice" role="status">{recoveryView.label}，完成后文字会显示在这里。</p> : null}
          {journey && !journey.optional && !recoveryView?.isProcessing ? <CompanionJourney journey={journey}
            blocked={controlsBusy || oobeBlockedByRecording || storageBlocked} onControl={runOrganizationControl} onSettings={openSettings} onWorkflow={openWorkflow}/> : null}
          {selectedSession.recovery?.lastError && !journey?.handlesFailure ? <p className="ct-recording-notice ct-step-warn" role="status">处理未完成：{selectedSession.recovery.lastError}</p> : null}
          {audioResult?.sessionId===selectedSession.id ? <p className="ct-recording-notice ct-step-warn" role="status">{audioResult.message}</p> : null}
          <div id="ct-recording-playback" hidden={!playbackOpen}>
          <section className="ct-audio-card" aria-label="本机原音回听">
            <div><strong>原音回听</strong></div>
            {preparedAudio ? <CompanionAudioPlayer key={`${preparedAudio.identity}:${preparedAudio.url}:${listeningEpoch}`} playerRef={audioElement} src={preparedAudio.url} pauseTimeline={preparedAudio.pauseTimeline}
              sourceIdentity={preparedAudio.sourceIdentity}
              sessionId={selectedSession.id}
              autoPlay={listeningQueue.active?.phase==='playing'&&listeningQueue.active.entry.id===selectedSession.id}
              onFinished={()=>listeningQueue.finished(preparedAudio.sourceIdentity)}
              externalSeekRef={externalAudioSeek}
              onError={() => {
                if (audioContext.current.sessionId !== selectedSession.id || audioContext.current.identity !== preparedAudio.identity) return;
                if(listeningQueue.active)listeningQueue.stop('原音无法播放，连续播放已停止。');
                const player = audioElement.current;
                player?.pause();
                if (player) { player.removeAttribute('src'); player.load(); }
                setAudioSources((current) => {
                  const next = { ...current }; delete next[selectedSession.id]; return next;
                });
                setAudioResult({ sessionId: selectedSession.id, message: '无法回听：音频可能已移动、删除或损坏，请刷新后重试。' });
              }} />
              : <button type="button" className="ct-action" disabled={Boolean(audioBlockedReason) || audioBusy}
                title={audioBlockedReason ?? undefined} onClick={() => void prepareAudio()}>{audioBusy ? '正在准备…' : '重试回听'}</button>}
          </section>
          </div>
          {hasMinutes || busyAction === 'meetingGenerateMinutes' ? <details id="ct-recording-result" className="ct-recording-result"
            open={recordingResultOpen} onToggle={event=>setRecordingResultOpen(event.currentTarget.open)}>
            <summary>整理结果{minutesDirty ? ' · 有未保存的修改' : ''}</summary>
            <div className="ct-meeting-document">
              {offlineMinutes && onlineMinutes ? <div className="ct-minutes-mode-tabs" role="tablist" aria-label="双模式纪要">
                <button type="button" role="tab" aria-label={`先录后整理纪要 ${offlineReady ? '✓' : offlineMinutes ? '草稿' : '未生成'}`} aria-selected={minutesViewMode === 'offlineStore'} className={`ct-mode-chip ${minutesViewMode === 'offlineStore' ? 'active' : ''}`} disabled={!offlineMinutes} onClick={() => setMinutesViewMode('offlineStore')}>先录后整理 {offlineReady ? '✓' : offlineMinutes ? '草稿' : ''}</button>
                <button type="button" role="tab" aria-label={`在线纪要 ${onlineReady ? `✓ · ${onlineMinutes?.partialCount} 次片段` : onlineMinutes ? '草稿' : '未生成'}`} aria-selected={minutesViewMode === 'onlineLive'} className={`ct-mode-chip ${minutesViewMode === 'onlineLive' ? 'active' : ''}`} disabled={!onlineMinutes} onClick={() => setMinutesViewMode('onlineLive')}>在线速记 {onlineReady ? `✓ · ${onlineMinutes?.partialCount} 段` : onlineMinutes ? '草稿' : ''}</button>
              </div> : null}
              {(selectedMinutesVariant??legacyMinutes)?.sourceNoteContext?<p className="ct-minutes-mode-meta">{(selectedMinutesVariant??legacyMinutes)?.source==='rules_l0'&&(selectedMinutesVariant??legacyMinutes)?.quality==='draft'
                ? '整理未完成。下方是基础草稿，尚未应用本次补充；原话和补充均已保存。'
                : '本次依据原话＋你选择的补充整理；补充不是录音识别。'}</p>:null}
              {minutesProcessing ? <div className={companionMinutesProcessingComplete(minutesProcessing) ? 'ct-minutes-mode-meta' : 'ct-step-warn'} role="status">
                {companionMinutesProcessingComplete(minutesProcessing)
                  ? `长会议已整理全部 ${minutesProcessing.totalChunks} 段；各段原文依据已保留，内容请核对。`
                  : `部分纪要：已整理 ${minutesProcessing.completedChunks}/${minutesProcessing.totalChunks} 段，原文与已完成分段都已保留。`}
                {!companionMinutesProcessingComplete(minutesProcessing) ? <button type="button" className="ct-action"
                  disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !finalTranscript || transcriptReviewUnsaved || editingMinutes || selectedMinutesStale}
                  onClick={() => runOrganizationControl({ action: 'meetingGenerateMinutes', sessionId: selectedSession.id, meetingMode: minutesViewMode })}>继续整理当前纪要</button> : null}
              </div> : null}
              {selectedMinutesStale ? <div className="ct-step-warn" role="status">转写或本次使用的补充已变化。这版结果已保留，请重新整理后使用。
                <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || transcriptReviewUnsaved || editingMinutes}
                  onClick={() => runOrganizationControl({ action: 'meetingGenerateMinutes', sessionId: selectedSession.id, meetingMode: minutesViewMode })}>重新选择内容并整理</button>
              </div> : selectedMinutesVariant ? <p className="ct-minutes-mode-meta">{selectedMinutesVariant.source === 'userEdited' ? '手动整理' : selectedMinutesVariant.quality === 'final' ? '整理已生成 · 内容请核对' : selectedMinutesVariant.source === 'rules_l0' ? '本机基础草稿' : '速记草稿'}{companionTranscriptReviewRevision(selectedSession) !== null ? ' · 基于人工修订' : ''}</p> : null}
              <div className="ct-inline-edit-actions">
                {!editingMinutes && hasMinutes ? <button type="button" className="ct-action"
                  disabled={controlsBusy||oobeBlockedByRecording||!onExportMeeting||selectedMinutesStale}
                  onClick={()=>void exportMeeting(savedActions(minutesMarkdown).length>0?'todo':'markdown')}><Download size={15}/>
                  {savedActions(minutesMarkdown).length>0?'导出清单':'导出整理'}</button> : null}
                {!editingMinutes ? <button type="button" className="ct-text-button" disabled={!hasMinutes || !onSaveMeeting || oobeBlockedByRecording}
                  title={!onSaveMeeting ? '请在桌面版编辑纪要' : undefined} onClick={() => setEditingMinutes(true)}><Pencil size={14} />编辑整理内容</button> : null}
              </div>
              {exportResult?.sessionId === selectedSession.id && exportResult.origin==='document' ?
                <CompanionExportFeedback feedback={exportResult} className={exportResult.kind === 'error' ? 'ct-document-export-result ct-step-warn' : 'ct-document-export-result ct-step-ok'}/> : null}
              {editingMinutes ? <div className="ct-minutes-editor">
                <div className="ct-minutes-savebar" aria-label="整理内容保存">
                  <span>{minutesDirty ? '修改尚未保存' : '编辑整理内容'}</span>
                <div className="ct-button-row"><button type="button" className="ct-action ct-action-primary"
                  disabled={!minutesDirty || saveMeetingBusy || !minutesDraft.trim()} onClick={() => void saveMeetingDraft()}>{saveMeetingBusy ? '正在保存…' : '保存修改'}</button>
                  <button type="button" className="ct-action" disabled={saveMeetingBusy} onClick={() => cancelMeetingDraft('minutes')}>取消</button></div>
                  {saveMeetingResult?.sessionId === selectedSession.id && saveMeetingResult.part === 'minutes' ?
                    <p className={saveMeetingResult.kind === 'error' ? 'ct-step-warn' : 'ct-step-ok'}
                      role={saveMeetingResult.kind === 'error' ? 'alert' : 'status'}>{saveMeetingResult.message}</p> : null}
                </div>
                <MinutesContentEditor markdown={minutesDraft} onChange={updateMinutesDraft} noteContext={(selectedMinutesVariant??legacyMinutes)?.sourceNoteContext}
                  label={`编辑${minutesViewMode === 'offlineStore' ? '先录后整理' : '在线速记'}纪要`} disabled={saveMeetingBusy} />

                {offlineMinutes && onlineMinutes ? <p className="ct-step-meta">只修改当前版本，另一份整理结果保持不变。</p> : null}
              </div> : hasMinutes ? <MinutesReadingView markdown={localDraftForDisplay(minutesMarkdown, (selectedMinutesVariant ?? legacyMinutes)?.source)}
                transcript={companionReviewedTranscript(selectedSession)} durationMs={selectedSession.durationMs}
                compactAllowed={!selectedMinutesStale && !transcriptReviewUnsaved && !minutesProcessing}
                savedMarkdown={minutesMarkdown} noteContext={(selectedMinutesVariant??legacyMinutes)?.sourceNoteContext}
                onToggleAction={onSaveMeeting?(lineIndex,completed)=>void markAction(lineIndex,completed):undefined}
                actionsBlocked={controlsBusy||oobeBlockedByRecording||storageBlocked||selectedMinutesStale||Boolean(minutesProcessing&&!companionMinutesProcessingComplete(minutesProcessing))
                  ||minutesDirty||titleDirty||noteUnsaved||transcriptReviewUnsaved||unimportedTranscriptDraft}
                sources={selectedMinutesStale || transcriptReviewUnsaved ? [] : transcriptSources}
                blocked={controlsBusy} onOpenSource={openTranscriptSource} />
                : <p className="ct-step-meta" role="status">{busyAction === 'meetingGenerateMinutes' || recoveryView?.isProcessing
                  ? '正在整理已保存的文字…' : '点“整理重点”整理录音文字，原话保留。'}</p>}
              {!editingMinutes && saveMeetingResult?.sessionId === selectedSession.id && saveMeetingResult.part === 'minutes' ?
                <p className={saveMeetingResult.kind === 'error' ? 'ct-step-warn ct-editor-save-result' : 'ct-step-ok ct-editor-save-result'}
                  role={saveMeetingResult.kind === 'error' ? 'alert' : 'status'}>{saveMeetingResult.message}</p> : null}
              <textarea className="ct-minutes-output ct-machine-minutes" value={minutesMarkdown} readOnly aria-hidden="true" tabIndex={-1} />
            </div>
            <details className="ct-result-tools">
              <summary>其它导出选项</summary>
          <div className="ct-document-actions">
            <span>保存正在查看的整理结果</span>
            <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !hasMinutes || !onExportMeeting}
              title={!onExportMeeting ? '请在 Windows Companion Type 中保存文件' : undefined}
              onClick={() => void exportMeeting('markdown')}><Download size={15} />{exportBusy ? '正在导出…' : '导出完整整理'}</button>

            <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !hasMinutes || !onExportMeeting || selectedMinutesStale}
              title="导出文件后需导入日历，再核对日期与提醒" onClick={() => void exportMeeting('ics')}>导出日历待办</button>
            <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||!hasMinutes||!onExportMeeting}
              onClick={()=>void exportMeeting('txt')}>{selectedSession.meetingNotes?.length?'导出原话与补充':'导出原话'}</button>
            <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||!hasMinutes||!onExportMeeting}
              onClick={()=>void exportMeeting('json')}>保存完整数据（JSON）</button>
          </div>

          {journey?.optional ? <CompanionJourney journey={journey} blocked={controlsBusy || oobeBlockedByRecording || storageBlocked}
            onControl={runOrganizationControl} onSettings={openSettings} onWorkflow={openWorkflow} /> : null}
            </details>
          </details> : null}
          <section className="ct-recording-text" aria-label="录音文字">
            <div className="ct-recording-text-heading"><h3>{hasMinutes?'原话与补充':'文字'}</h3>
              <div className="ct-button-row">
                {finalTranscript ? <button type="button" className="ct-text-button"
                  disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || (!hasMinutes && !canGenerate)}
                  title={hasMinutes?'重新整理，已有结果保留':'整理已保存的文字'}
                  onClick={() => {
                    if(snapshot?.minutesContextSupported && selectedSession.meetingNotes?.length)setOrganizationChoiceId(selectedSession.id);
                    else runOrganizationControl({action:'meetingGenerateMinutes',sessionId:selectedSession.id});
                  }}>{hasMinutes?'重新整理':'整理重点'}</button> : null}
                {finalTranscript && !hasMinutes ? <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !onExportMeeting || transcriptReviewUnsaved}
                  onClick={() => void exportMeeting('txt','text')}><Download size={15} />{exportBusy ? '正在导出…' : '导出文字'}</button> : null}
              </div>
            </div>
            {organizationChoiceId===selectedSession.id?<div id="ct-organization-source-choice" className="ct-organization-choice" role="group" aria-label="本次整理内容">
              <strong>这次整理用哪些内容？</strong>
              <p>原话和补充仍分开保留。选择补充时，只将当前已保存的内容用于这次整理；暂支持两分钟内的短备忘。</p>
              <div className="ct-button-row">
                <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||storageBlocked||noteUnsaved||minutesDirty||transcriptReviewUnsaved}
                  onClick={()=>{setOrganizationChoiceId(null);runOrganizationControl({action:'meetingGenerateMinutes',sessionId:selectedSession.id,meetingMode:minutesViewMode},'original');}}>仅原话</button>
                <button type="button" className="ct-action ct-action-primary" disabled={controlsBusy||oobeBlockedByRecording||storageBlocked||noteUnsaved||minutesDirty||transcriptReviewUnsaved||!selectedSession.meetingNotes?.length}
                  onClick={()=>{setOrganizationChoiceId(null);runOrganizationControl({action:'meetingGenerateMinutes',sessionId:selectedSession.id,meetingMode:minutesViewMode,
                    contextNoteRevision:selectedSession.noteRevision??0});}}>原话＋已保存补充</button>
                <button type="button" className="ct-text-button" disabled={controlsBusy} onClick={()=>setOrganizationChoiceId(null)}>取消</button>
              </div>
            </div>:null}
            {exportResult?.sessionId===selectedSession.id&&exportResult.origin==='text'?<CompanionExportFeedback feedback={exportResult}/>:null}
            {companionReviewedTranscript(selectedSession).trim() ? <>
              {!finalTranscript ? <p className="ct-step-warn">当前为片段文字，尚未完成整条转写。</p> : null}
              {companionTranscriptReviewIsStale(selectedSession) ? <p className="ct-step-warn">原始转写已更新，当前显示新文字；旧修订保留在“更多”中供核对。</p> : null}
              {transcriptReviewUnsaved ? <p className="ct-step-warn">有尚未保存的文字修订，请在“更多”中继续编辑。</p> : null}
              <p className="ct-recording-transcript">{companionReviewedTranscript(selectedSession)}</p>
            </> : <p className="ct-recording-text-empty">{recoveryView?.isProcessing?'正在转成文字，请稍候。':'还没有文字，点“转文字”即可。原音会保留，随时可以回听。'}</p>}
          <CompanionMeetingNotes compact session={selectedSession} blocked={controlsBusy} anyRecording={oobeBlockedByRecording}
            persistenceReady={!storageBlocked} onSave={onSaveNote} onBusyChange={setNoteBusy} onUnsavedChange={setNoteUnsaved}
            onOrganizeSaved={snapshot?.minutesContextSupported && finalTranscript && Number.isFinite(selectedSession.durationMs)
              && selectedSession.durationMs>=0 && selectedSession.durationMs<=120000 ? ()=>runOrganizationControl({
                action:'meetingGenerateMinutes',sessionId:selectedSession.id,meetingMode:minutesViewMode,
                contextNoteRevision:selectedSession.noteRevision??0}) : undefined}
            organizeSavedBlocked={controlsBusy||oobeBlockedByRecording||storageBlocked||noteUnsaved||minutesDirty||titleDirty
              ||transcriptReviewUnsaved||unimportedTranscriptDraft}
            onSeek={seekBookmark} onExport={onExportMeeting&&!hasMinutes?(format)=>exportMeeting(format,'notes'):undefined}
            exportFeedback={exportResult?.sessionId===selectedSession.id&&exportResult.origin==='notes'?exportResult:null}/>
          {finalTranscript && selectedSession.meetingNotes?.length ? <p className="ct-step-meta">
            {snapshot?.minutesContextSupported?'补充单独保存；整理时可选择仅用原话，或一起参考已保存补充。':'补充已单独保存；当前整理程序仅使用原话。'}
          </p> : null}
          </section>
          {exportResult?.sessionId === selectedSession.id && !exportResult.origin ? <CompanionExportFeedback feedback={exportResult}
            className={exportResult.kind === 'error' ? 'ct-export-result ct-step-warn' : 'ct-export-result'}/> : null}
          <details className="ct-recording-more" open={recordingToolsOpen} onToggle={event=>setRecordingToolsOpen(event.currentTarget.open)}>
            <summary>更多{titleDirty||minutesDirty||transcriptReviewUnsaved||bookmarkUnsaved||noteUnsaved?' · 有未保存的修改':''}</summary>
            {savedOriginalReady ? <RecordingSafetyCard session={selectedSession} persistence={snapshot?.host.persistence} recoveryProcessing={Boolean(recoveryView?.isProcessing)} /> : null}
            <div className="ct-recording-audio-export">
            <button type="button" className="ct-action" disabled={!onExportAudio || !hasOriginalAudio || controlsBusy || oobeBlockedByRecording}
              onClick={() => void exportAudio()}><Download size={15} />保存原音</button>
            <p>保存一份原始 WAV 到你选择的位置，可单独备份或使用其他播放器打开。此副本由你自行保管，删除录音不会删除它。</p>
            </div>
          <CompanionBookmarks session={selectedSession} blocked={controlsBusy} anyRecording={oobeBlockedByRecording}
            persistenceReady={!storageBlocked} onSave={onSaveBookmark} onBusyChange={setBookmarkBusy} onUnsavedChange={setBookmarkUnsaved}
            playbackPosition={()=>audioElement.current&&audioElement.current.readyState>=1&&Number.isFinite(audioElement.current.currentTime)
              ? Math.round(audioElement.current.currentTime*1000):null}
            onSeek={seekBookmark} onShowOriginal={()=>setRecordingToolsOpen(true)}
            onExport={onExportMeeting?()=>exportMeeting('json'):undefined}/>
          {selectedSession.recovery?.lastError ? <details className="ct-recovery-detail">
            <summary>查看处理失败的详情</summary><p>{selectedSession.recovery.lastError}</p>
            <small>已尝试 {selectedSession.recovery.attemptCount} / {selectedSession.recovery.maxAttempts} 次；已有内容仍保留在本机。</small>
          </details> : null}
          <div className="ct-document-actions">
            <span>保存当前转写；完整记录包含原始识别结果</span>
            <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !finalTranscript || !selectedSession.utterances?.length || !onExportMeeting || transcriptReviewUnsaved}
              onClick={() => void exportMeeting('srt')}>保存字幕</button>
            <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !finalTranscript || !onExportMeeting || transcriptReviewUnsaved}
              onClick={() => void exportMeeting('json')}>保存完整记录</button>
          </div>
          <CompanionTranscriptReview session={selectedSession} visible={recordingToolsOpen}
            blocked={controlsBusy || oobeBlockedByRecording || storageBlocked}
            sourceSelection={sourceSelection} onSeekSource={seekTranscriptSource}
            audioSeekBlocked={Boolean(audioBlockedReason) || audioBusy}
            onSave={onSaveMeeting} onUnsavedChange={setTranscriptReviewUnsaved} />
          </details>
        </section>
      ) : null}

      </div>

      <section id="ct-device-recording-page" className="ct-page-panel" hidden={pageView !== 'device'} aria-label="设备与同步内容">
      <CompanionSetup snapshot={snapshot} settings={productSettings} busy={controlsBusy}
        recording={oobeBlockedByRecording} checking={busyAction === 'oobeRunChecks'} onControl={onControl}
        onSettings={openSettings} onWorkflow={openWorkflow} onLibrary={() => {setPageView('library');setDetailSessionId(null);}} />
      {onFindPet && connected && device?.deviceId ? <CompanionPetFind
        deviceId={device.deviceId} supported={snapshot?.source==='firmware' && snapshot.speaker.findSupported===true}
        blocked={controlsBusy||oobeBlockedByRecording} muted={snapshot?.speaker.muted!==false||snapshot.speaker.volume===0}
        onFind={onFindPet} /> : null}

      {connected ? <section className="ct-pending-banner" aria-label="设备录音容量">
        <strong>设备录音空间 · 上次读取</strong><p>{capacityHint}</p>
        {capacity ? <p>未同步 {capacity.unsyncedEntries} 段，未封口 {capacity.writingEntries} 段，共占用 {formatBytes(capacity.protectedBytes)}；待回收（已同步或已确认删除）{capacity.consumedEntries} 段，{formatBytes(capacity.consumedBytes)}。
          设备独立开录：{capacity.localLimitSeconds ? `${capacity.localLimitSeconds / 60} 分钟` : '无时间上限，空间仍有限'}。</p> : null}
        {capacity && capacity.writingEntries>0 && !oobeBlockedByRecording ? <p role="alert">
          设备仍保留未封口录音；校验不足的内容不会自动覆盖。请先同步可恢复的片段，剩余占用需要设备诊断后处理。
        </p> : null}
        <p>{capacity ? '电脑开录使用下方填写的时长，开始前重新核对完整空间。空间不足会拒绝开录；不会自动覆盖未同步录音。'
          : '旧固件或未读到容量时，无法承诺完整时长；请重新读取，或升级到配套固件。'}</p>
        <button type="button" className="ct-text-button" disabled={controlsBusy || oobeBlockedByRecording}
          onClick={() => onControl({action:'oobeRunChecks'})}>重新读取设备容量</button>
        {onDiscardOldestRecording && capacity?.confirmedDiscardSupported && capacityInsufficient ? <>
          <p>优先同步保存录音。也可查看最旧未同步录音的具体时间、大小和风险，再决定是否删除这一条。</p>
          <button type="button" className="ct-text-button" disabled={controlsBusy || settingsBusy || oobeBlockedByRecording || capacity.busy || !capacity.unsyncedEntries}
            onClick={() => void inspectRecordingLoss()}>{discardBusy ? '正在核对确认与回收…' : '查看可释放的最旧录音'}</button>
        </> : null}
        {discardMessage ? <p role="status">{discardMessage}</p> : null}
      </section> : null}
      {!oobeBlockedByRecording ? <section className="ct-recording-activity" aria-label="开始设备录音">
        <div><strong>用 Companion 录音</strong>
          <p>{connected
            ? `只保存原音，转写与纪要稍后手动启动。无需网络或转写配置。当前最长 ${draftMinutes || '—'} 分钟，可在录音与同步中调整。`
            : '设备离线也能录：长按实体键约 1 秒开始，再长按约 1 秒停止；睡着时先短按唤醒。'}</p>
          {!durationValid ? <p role="alert">请输入有效的录音时长。</p> : null}
        </div>
        <div className="ct-button-row">
          <button type="button" className="ct-action ct-action-primary"
            disabled={controlsBusy || storageBlocked || !connected || !device?.deviceId || !durationValid}
            onClick={() => onControl({ action: 'meetingStart', meetingMode: 'offlineStore',
              promptId: COMPANION_CAPTURE_ONLY_PROMPT,
              deviceId: device?.deviceId ?? undefined, title: newMeetingTitle.trim() || 'Companion 录音', durationMs: requestedDurationMs })}>
            <Mic size={16} /><span>开始录音</span>
          </button>
          <button type="button" className="ct-action" disabled={controlsBusy} onClick={openWorkflow}>录音与同步</button>
        </div>
      </section> : null}

      <button type="button" className="ct-workflow-toggle" onClick={() => setShowWorkflow((value) => !value)}>
        <span><HardDrive size={16} />更多录音与处理操作</span><span>{showWorkflow ? '收起' : '录音 · 同步 · 整理'}</span>
      </button>

      {showWorkflow ? <section className="ct-steps" id="ct-workflow" aria-label="主路径步骤">
        <div className={`ct-step ${step >= 1 ? 'active' : ''} ${connected ? 'done' : ''}`}>
          <span className="ct-step-n">1</span>
          <div className="ct-step-body">
            <strong>连接 Companion</strong>
            <p>扫描并连接 Companion</p>
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action"
                disabled={controlsBusy || oobeBlockedByRecording}
                onClick={() => onControl({ action: 'deviceScan' })}
              >
                <Search size={16} />
                <span>扫描</span>
              </button>
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={controlsBusy || (oobeBlockedByRecording && !companionCanChangeOfflineRecordingLink(snapshot,
                  { action: 'deviceConnect', deviceId: device?.deviceId ?? undefined }))}
                onClick={() => onControl({
                  action: 'deviceConnect',
                  deviceId: device?.deviceId ?? undefined,
                })}
              >
                <Link2 size={16} />
                <span>连接</span>
              </button>
              {connected ? (
                <button
                  type="button"
                  className="ct-icon-button"
                  disabled={controlsBusy || (oobeBlockedByRecording && !companionCanChangeOfflineRecordingLink(snapshot,
                    { action: 'deviceDisconnect' }))}
                  onClick={() => onControl({ action: 'deviceDisconnect' })}
                  title="断开"
                >
                  <Unlink size={17} />
                </button>
              ) : null}
            </div>
            <p className="ct-step-meta">
              {device?.message ?? '尚未扫描'}
              {device?.hardwareRevision
                ? ` · ${device.hardwareRevision} · FW 0x${(device.firmwareVersion ?? 0).toString(16).padStart(8, '0')}`
                : (connected ? ' · 设备身份未读出' : '')}
              {device?.recordingsAvailable != null
                ? ` · 设备录音 ${device.recordingsAvailable} 条`
                : ''}
            </p>
          </div>
        </div>

        <div className={`ct-step ${step >= 2 ? 'active' : ''} ${hasSyncedAudio ? 'done' : ''}`}>
          <span className="ct-step-n">2</span>
          <div className="ct-step-body">
            <strong>板端采集 / 同步录音库</strong>
            <p>
              使用 Companion 录音，电脑同步显示转写。停止后自动收齐录音并整理纪要；也可以先在设备上录好，再同步到电脑。
            </p>
            <div className="ct-meeting-grid">
              <label className="ct-field"><span>这次会议的名称（可选）</span><input value={newMeetingTitle}
                placeholder="例如：周会、一次灵感" maxLength={120} disabled={oobeBlockedByRecording || controlsBusy}
                onChange={(event) => setNewMeetingTitle(event.target.value)} /></label>
              <label className="ct-field ct-duration-field"><span>最长录制时间（分钟）</span><input value={draftMinutes}
                inputMode="numeric" disabled={oobeBlockedByRecording || controlsBusy}
                onChange={(event) => setDraftMinutes(event.target.value.replace(/[^0-9]/g, ''))} /></label>
            </div>
            <p className="ct-step-meta">在线转写单次最多 43 分钟，另预留 2 分钟收尾空间；纯录音按设备空间和设定时长保存。支持连续物理分段的设备仍保留为同一场录音，完整收齐后才确认回收。</p>
            {captureBudgetBytes !== null ? <p className="ct-step-meta" role={capacityInsufficient ? 'alert' : undefined}>
              本次需预留约 {formatBytes(captureBudgetBytes)}{meetingMode === 'onlineLive' ? '（含收尾空间）' : ''}；
              设备上次报告连续可录约 {formatDuration(capacitySeconds * 1000)}。
              {capacityInsufficient ? '当前容量不足，请先同步已有录音或缩短时长；不会自动缩短或覆盖录音。' : '开始前会重新核对容量。'}
            </p> : null}
            {durationError ? <p className="ct-step-meta" role="alert">{durationError}</p> : null}
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !connected || !asrConfigured || !onStartBoardOnlineLive || !onlineDurationValid}
                onClick={() => onStartBoardOnlineLive?.({
                  title: newMeetingTitle.trim() || 'Companion 会议',
                  deviceId: device?.deviceId,
                  maxDurationSeconds: boardMaxDurationSeconds,
                  partialIntervalMs: 8_000,
                })}
                title={!connected ? '请先连接 Companion' : !asrConfigured ? '请先配置转写服务；也可以直接在设备上录音' : '使用 Companion 麦克风开始在线会议'}
              >
                <Mic size={16} />
                <span>开始在线会议</span>
              </button>
              <button
                type="button"
                className="ct-action"
                disabled={controlsBusy || boardOnlineLive?.state !== 'recording' || !onStopBoardOnlineLive}
                onClick={() => onStopBoardOnlineLive?.()}
              >
                <Square size={16} />
                <span>停止并生成纪要</span>
              </button>
            </div>
            {!asrConfigured ? <p className="ct-step-meta">在线转写需要服务配置。你也可以先在设备上录音，稍后同步。<button type="button" className="ct-text-button" onClick={openSettings}>配置转写服务</button></p> : null}
            {boardOnlineLive && boardOnlineLive.state !== 'idle' ? (
              <div className="ct-live-box" aria-live="polite" aria-label="板端在线会议状态">
                <strong>
                  {boardOnlineLive.state === 'starting' ? '正在连接并启动板端录音'
                    : boardOnlineLive.state === 'recording' ? 'Companion 正在录音 / 在线转写'
                      : boardOnlineLive.state === 'stopping' ? '正在停止并拉齐板端录音'
                        : boardOnlineLive.state === 'finalizing' ? '正在做最终转写与双模式纪要'
                          : boardOnlineLive.state === 'completed' ? '板端在线会议已完成'
                            : boardOnlineLive.state === 'pending' ? '录音已保存，等待联网转写'
                            : '板端在线会议失败'}
                </strong>
                <div>
                  {boardOnlineLive.recordingId != null ? `录音 #${boardOnlineLive.recordingId} · ` : ''}
                  已出 {boardOnlineLive.partialCount} 个在线片段
                  {boardOnlineLive.durationMs > 0 ? ` · ${formatDuration(boardOnlineLive.durationMs)}` : ''}
                  {nearRecordingLimit ? ` · 距上限约 ${formatDuration(recordingRemainingMs)}` : ''}
                  {boardOnlineLive.disconnectResume ? ' · 已从断线处继续同步' : ''}
                  {boardOnlineLive.error ? ` · ${boardOnlineLive.error}` : ''}
                </div>
              </div>
            ) : null}
            <p className="ct-step-meta">这次实时转写上限 {Math.ceil(boardMaxDurationSeconds / 60)} 分钟；可以提前停止，设备设置或空间不足也可能更早结束。已有板端录音仍可单独同步：</p>
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action"
                disabled={controlsBusy || storageBlocked || boardLiveActive || (!originalSyncRecorder && (oobeBlockedByRecording || !connected))}
                onClick={() => onControl({ action: 'deviceSyncRecordings', title: draftTitle,
                  deviceId: originalSyncRecorder?.sourceDeviceId ?? device?.deviceId ?? undefined,
                  ...(originalSyncRecorder ? { sessionId: originalSyncRecorder.id } : {}) })}
                title={originalSyncRecorder ? '连接原设备，继续同步同一场录音；采音不会停止' : !connected ? '请先连接板子' : '同步设备录音'}
              >
                <HardDrive size={16} />
                <span>{originalSyncRecorder ? '同步原录音' : '同步录音库'}</span>
              </button>
            </div>
            {!connected && originalSyncRecorder ? <p className="ct-step-meta">会连接这场录音的原设备，继续收取已保存的片段。不会重新开录或停止采音。</p> : !connected ? (
              <p className="ct-step-warn">未连接板子，无法同步</p>
            ) : hasSyncedAudio ? (
              <p className="ct-step-ok">
                已同步
                {selectedSession?.audioBytes
                  ? ` · ${(selectedSession.audioBytes / 1024).toFixed(0)} KB`
                  : ''}
                {selectedSession?.source === 'deviceFlash' ? ' · Companion 录音' : ''}
              </p>
            ) : (
              <p className="ct-step-meta">
                设备录音：{device?.recordingsAvailable ?? 0} 条
                {(device?.recordingsAvailable ?? 0) === 0
                  ? '，可以先在 Companion 上录一段'
                  : '，可同步到本机'}
              </p>
            )}
          </div>
        </div>

        <div className={`ct-step ${step >= 3 ? 'active' : ''} ${selectedSession?.transcriptText ? 'done' : ''}`}>
          <span className="ct-step-n">3</span>
          <div className="ct-step-body">
            <strong>转写</strong>
            <p>正在处理：{selectedSession?.title ?? '请先选择一条录音'}。可转写原音，或粘贴替代文字后导入到这条录音；此处不会新建录音。</p>
            <textarea
              className="ct-textarea ct-step-textarea"
              value={transcriptDraft}
              onChange={(event) => {
                transcriptEditor.current.dirty = true;
                setTranscriptDraft(event.target.value);
              }}
              spellCheck={false}
              placeholder="转写文本…"
              disabled={!hasSyncedAudio && !selectedSession}
            />
            {(() => {
              const utterances = selectedSession?.utterances ?? [];
              const taggedLines = (selectedSession?.transcriptText || transcriptDraft || '')
                .split(/\r?\n/)
                .map((line) => line.trim())
                .filter((line) => /^说话人\d+[:：]/.test(line) || /^说话人\?[:：]/.test(line));
              const speakerCount = new Set(
                taggedLines
                  .map((line) => line.match(/^说话人(\d+|\?)/)?.[1])
                  .filter(Boolean),
              ).size;
              if (utterances.length === 0 && taggedLines.length === 0) {
                return null;
              }
              return (
                <div className="ct-speaker-panel" aria-label="说话人分离">
                  <div className="ct-speaker-head">
                    <strong>说话人</strong>
                    <span className="ct-pill ct-pill-good">
                      {speakerCount > 0 ? `${speakerCount} 人` : `${utterances.length} 段`}
                    </span>
                  </div>
                  <ul className="ct-speaker-list">
                    {(taggedLines.length > 0 ? taggedLines : utterances.map((u) => {
                      const label = u.speaker == null ? '说话人?' : `说话人${u.speaker + 1}`;
                      return `${label}: ${u.text}`;
                    })).map((line, index) => (
                      <li key={`spk-${index}`} className="ct-speaker-line">{line}</li>
                    ))}
                  </ul>
                </div>
              );
            })()}
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action"
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !canTranscribe}
                onClick={() => onControl({ action: 'meetingTranscribeAudio', sessionId: selectedSession?.id })}
              >
                <FileText size={16} />
              <span>{selectedSession?.captureIncomplete ? '转写已保存的片段' : '转写'}</span>
              </button>
              {onRefineSpeakers ? <button type="button" className="ct-action"
                title="只用已保存原音在电脑本地区分，不重新转写或上传；旧纪要保留为待更新草稿。"
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !selectedSession?.audioStored
                  || !selectedSession.transcriptFinal || !selectedSession.utterances?.length
                  || titleDirty || minutesDirty || transcriptEditor.current.dirty}
                onClick={async()=>{
                  if (!selectedSession) return;
                  const sessionId=selectedSession.id;setSaveMeetingBusy(true);setSaveMeetingResult(null);
                  try {await onRefineSpeakers(sessionId);setSaveMeetingResult({sessionId,kind:'saved',message:'已在本机重新区分说话人；原音、文字和时间轴保留，之前的纪要可按需重新生成。'});}
                  catch (e) {setSaveMeetingResult({sessionId,kind:'error',message:`本地分组未完成：${e instanceof Error?e.message:String(e)}`});}
                  finally {setSaveMeetingBusy(false);}
                }}>重新区分说话人（本地）</button>:null}
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !transcriptDraft.trim() || !hasSyncedAudio}
                onClick={() => onControl({
                  action: 'meetingImportTranscript',
                  sessionId: selectedSession?.id,
                  title: draftTitle,
                  transcriptText: transcriptDraft,
                })}
              >
                <Upload size={16} />
                <span>导入到这条录音</span>
              </button>
            </div>
          </div>
        </div>

        <div className={`ct-step ${step >= 4 ? 'active' : ''} ${hasMinutes ? 'done' : ''}`}>
          <span className="ct-step-n">4</span>
          <div className="ct-step-body">
            <strong>生成纪要</strong>
            <p>整理“{selectedSession?.title ?? '当前录音'}”已保存的转写（{recordingModeLabel}）。</p>
            {unimportedTranscriptDraft ? <div className="ct-step-warn" role="status">
              <p>刚输入的文字尚未导入。为避免整理成旧内容，请先导入，或还原为已保存的转写。</p>
              <button type="button" className="ct-text-button" disabled={controlsBusy} onClick={() => {
                if (!selectedSession) return;
                transcriptEditor.current.dirty = false;
                setTranscriptDraft(selectedSession.transcriptText ?? '');
              }}>还原为已保存的转写</button>
            </div> : null}
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !canGenerate}
                onClick={() => runOrganizationControl({ action: 'meetingGenerateMinutes', sessionId: selectedSession?.id })}
              >
                <FileText size={16} />
              <span>{selectedSession?.captureIncomplete ? '整理片段的纪要' : '生成纪要'}</span>
              </button>
              <button
                type="button"
                className="ct-action"
                disabled={controlsBusy || oobeBlockedByRecording || !hasMinutes || !onExportMeeting}
                onClick={() => void exportMeeting('markdown')}
              >
                <Download size={16} />
                <span>导出 Markdown</span>
              </button>
            </div>
            {recordingMinutesUserEdited ? <p className="ct-step-warn">录制模式（{recordingModeLabel}）纪要含人工修改。再次生成会替换这一版，建议先导出保存。</p> : null}
          </div>
        </div>
      </section> : null}

      </section>

      <section className="ct-page-panel" hidden={pageView !== 'settings'} aria-label="设置与工具内容">
      <button
        type="button"
        className="ct-advanced-toggle"
        onClick={() => setShowAdvanced((value) => !value)}
      >
        {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        <span>{showAdvanced ? '收起高级功能' : '展开设置与工具'}</span>
      </button>

      {showAdvanced ? (
        <div className="ct-advanced">
          <CompanionBehaviorPreview recording={oobeBlockedByRecording} />
          <section className="ct-panel">
            <div className="ct-panel-title">
              <Mic size={18} />
              <span>{connected ? 'Companion 录音' : '本机麦克风录音'}</span>
            </div>
            <p className="ct-meeting-hint">
              先录后整理：先安全保存录音，稍后转写。在线转写：录音期间显示文字，结束后继续整理。转写与智能纪要使用你配置的服务。
            </p>
            <div className="ct-mode-row" role="group" aria-label="会议模式">
              <button
                type="button"
                className={`ct-mode-chip ${meetingMode === 'offlineStore' ? 'active' : ''}`}
                onClick={() => setMeetingMode('offlineStore')}
              >
                先录后整理
              </button>
              <button
                type="button"
                className={`ct-mode-chip ${meetingMode === 'onlineLive' ? 'active' : ''}`}
                onClick={() => setMeetingMode('onlineLive')}
              >
                在线转写
              </button>
            </div>
            <div className="ct-meeting-grid">
              <label className="ct-field">
                <span>标题</span>
                <input
                  value={draftTitle}
                  onChange={(event) => setDraftTitle(event.target.value)}
                  spellCheck={false}
                />
              </label>
              <label className="ct-field ct-duration-field">
                <span>{connected ? '最长录音(分)' : '预计时长(分)'}</span>
                <input
                  value={draftMinutes}
                  onChange={(event) => setDraftMinutes(event.target.value.replace(/[^0-9]/g, ''))}
                  inputMode="numeric"
                />
              </label>
            </div>
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked
                  || !durationValid || (connected && meetingMode === 'onlineLive' && !onlineDurationValid)
                  || (connected && meetingMode === 'onlineLive' && (!asrConfigured || !onStartBoardOnlineLive))}
                onClick={() => {
                  if (connected && meetingMode === 'onlineLive') {
                    void onStartBoardOnlineLive?.({
                      title: draftTitle.trim() || 'Companion 会议',
                      deviceId: device?.deviceId,
                      maxDurationSeconds: boardMaxDurationSeconds,
                      partialIntervalMs: 8_000,
                    });
                  } else {
                    onControl({
                      action: 'meetingStart',
                      title: draftTitle,
                      meetingMode,
                      durationMs: requestedDurationMs,
                    });
                  }
                }}
              >
                <Play size={16} /><span>{connected ? '板端开始录音' : '本机开始录音'}</span>
              </button>
              <button
                type="button"
                className="ct-action"
                disabled={controlsBusy || !snapshot?.meeting.active || boardLiveActive}
                onClick={() => onControl({
                  action: 'meetingStop',
                  title: draftTitle,
                  durationMs: requestedDurationMs,
                })}
              >
                <Square size={16} /><span>停止</span>
              </button>
              <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording} onClick={() => onControl({ action: 'meetingLoadDemo', title: '调试演示纪要' })}>
                <FileText size={16} /><span>调试：无板演示</span>
              </button>
            </div>
            <p className="ct-step-meta">{connected
              ? `${meetingMode === 'onlineLive' ? `实时转写单次最多 43 分钟，另预留 2 分钟收尾空间。${nearRecordingLimit ? ` 距本次设定结束约 ${formatDuration(recordingRemainingMs)}。` : ''}` : '先录后整理按填写时长检查完整空间，不会自动截短。'} 当前不支持无缝连续分段。在线模式需要配置转写服务。`
              : '本机录音需要手动停止，保存后按实际音频长度显示时长。'}</p>
            {!durationValid || (connected && meetingMode === 'onlineLive' && !onlineDurationValid)
              ? <p className="ct-step-meta" role="alert">{durationError}</p> : null}
            {(selectedSession?.status === 'recording' || selectedSession?.liveTranscriptText) ? (
              <div className="ct-live-box" aria-live="polite">
                <strong>
                  {selectedSession?.meetingMode === 'onlineLive' ? '在线 live / 转写' : '会话文本'}
                  {selectedSession?.status === 'recording' ? ' · 录制中' : ''}
                </strong>
                <div>
                  {selectedSession?.liveTranscriptText
                    || selectedSession?.transcriptText
                    || (meetingMode === 'onlineLive'
                      ? '（在线模式：录制中推送 live partial；无密钥时停会 batch 回落）'
                      : '（离线模式：停会后点转写）')}
                </div>
              </div>
            ) : null}
          </section>

          <section className="ct-panel" aria-label="更新资源">
            <div className="ct-panel-title">
              <Upload size={18} />
              <span>设备更新</span>
            </div>
            <p className="ct-meeting-hint">
              填写更新包清单路径，程序和屏幕资源会一起更新。下载中断后可重新开始；设备正常启动并确认新版本后才显示成功。录音期间无法更新。
            </p>
            <div className="ct-settings-grid">
              <label className="ct-field">
                <span>更新清单路径</span>
                <input
                  value={resourceManifestPath}
                  onChange={(e) => setResourceManifestPath(e.target.value)}
                  placeholder="…\ota_manifest.json"
                  spellCheck={false}
                />
              </label>
            </div>
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={controlsBusy || oobeBlockedByRecording || !onValidateOtaPackage || !resourceManifestPath.trim()}
                onClick={() => {
                  setResourceMsg(null);
                  setResourceBusy(true);
                  void Promise.resolve(
                    onValidateOtaPackage?.({
                      manifestPath: resourceManifestPath.trim(),
                      firmwarePath: '',
                    }),
                  )
                    .then((report) => {
                      if (!report) return;
                      setResourceMsg(
                        `${report.ok ? '校验通过' : '校验失败'} · ${report.packageType} · ${report.payloadBytes} B · ${report.message}`,
                      );
                    })
                    .catch((err: unknown) => {
                      setResourceMsg(err instanceof Error ? err.message : String(err));
                    })
                    .finally(() => setResourceBusy(false));
                }}
              >
                <Check size={16} />
                <span>校验更新包</span>
              </button>
              <button
                type="button"
                className="ct-action"
                disabled={
                  controlsBusy
                  || oobeBlockedByRecording
                  || !connected
                  || !onTransferOtaPackage
                  || !resourceManifestPath.trim()
                }
                title="校验匹配当前设备的更新包后传输"
                onClick={() => {
                  setResourceMsg(null);
                  setResourceBusy(true);
                  void Promise.resolve(
                    onTransferOtaPackage?.({
                      manifestPath: resourceManifestPath.trim(),
                      firmwarePath: '',
                      deviceId: device?.deviceId ?? null,
                    }),
                  )
                    .then((report) => {
                      if (!report) return;
                      setResourceMsg(
                        report.packageType==='companion-system-ota'
                          ? `固件与资源已更新，设备重启确认成功 · ${report.firmwareBytes} B`
                          : `数据传输完成 · ${report.firmwareBytes} B；尚未确认整套升级。`,
                      );
                    })
                    .catch((err: unknown) => {
                      setResourceMsg(err instanceof Error ? err.message : String(err));
                    })
                    .finally(() => setResourceBusy(false));
                }}
              >
                <Upload size={16} />
                <span>传输到设备</span>
              </button>
            </div>
            {resourceMsg ? (
              <p className="ct-step-meta" role="status">{resourceMsg}</p>
            ) : null}
            <div className="ct-section-title"><FileText size={18} /><span>日志与诊断</span></div>
            <p className="ct-meeting-hint">保存连接、升级和音频处理的阶段记录，方便排查问题。不包含密钥、会议正文或原始录音。设备日志只保留最近的运行事件，重启会清空；本机日志按大小轮换。</p>
            <div className="ct-button-row">
              {[false, true].map((includeDevice) => <button key={String(includeDevice)} type="button" className="ct-action"
                disabled={controlsBusy || oobeBlockedByRecording || !onExportDiagnostics || (includeDevice && !connected)}
                onClick={() => {
                  if (diagnosticActive.current || !onExportDiagnostics) return;
                  diagnosticActive.current=true; setDiagnosticBusy(true); setDiagnosticMsg(null);
                  void onExportDiagnostics(includeDevice).then((result) => {
                    setDiagnosticMsg(result ? `已保存：${result.path}${result.warning ? `。${result.warning}` : ''}` : '已取消，未导出日志。');
                  }).catch((error) => setDiagnosticMsg(String(error))).finally(() => { diagnosticActive.current=false; setDiagnosticBusy(false); });
                }}><Download size={15}/>{includeDevice ? '读取设备并导出日志' : '导出本机日志'}</button>)}
            </div>
            {!onExportDiagnostics ? <p className="ct-step-meta">真实日志导出仅在 Windows 应用中提供。</p> : null}
            {diagnosticMsg ? <p className="ct-step-meta" role="status">{diagnosticMsg}</p> : null}
            <p className="ct-meeting-hint">设备录音解码已随应用提供。可另外准备本地说话人区分组件：首次约下载 46 MB，只下载模型与运行库，不上传录音。说话人区分用于会议中的不同发言者，不识别真实身份。</p>
            <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !onPrepareAudioComponents}
              onClick={() => {
                if (diagnosticActive.current || !onPrepareAudioComponents) return;
                diagnosticActive.current=true; setDiagnosticBusy(true); setDiagnosticMsg('正在准备音频组件，请稍候…');
                void onPrepareAudioComponents().then(() => setDiagnosticMsg('音频组件已校验并成功加载；后续会议可以使用本地说话人区分。'))
                  .catch((error) => setDiagnosticMsg(String(error))).finally(() => {diagnosticActive.current=false;setDiagnosticBusy(false);});
              }}>准备说话人区分组件</button>
          </section>

          <section className="ct-panel" id="ct-service-settings">
            <button type="button" className="ct-text-button ct-return-recording" onClick={returnToRecording}>← 返回录音</button>
            <div className="ct-panel-title">
              <Shield size={18} />
              <span>转写与纪要服务</span>
            </div>
            {productSettings?.storageWarning ? <p className="ct-step-warn" role="alert">
              {productSettings.storageWarning}
            </p> : null}
            <p className="ct-secret-hint">
              正式桌面版使用系统凭据管理器保存密钥。转写会把录音发送到所选 ASR 服务，智能纪要会把转写文字发送到 DeepSeek；空密钥保存不会覆盖已有值。
            </p>
            <p className="ct-service-boundary">使用自备或兼容服务时，数据会离开 Companion Type 并交给你填写的服务地址；该服务的保留期限、访问控制与可用性由服务提供者或你的部署负责。</p>
            <div className="ct-mode-row">
              <button
                type="button"
                className={`ct-mode-chip ${formDefaultMode === 'offlineStore' ? 'active' : ''}`}
                onClick={() => setFormDefaultMode('offlineStore')}
              >
                默认先录后整理
              </button>
              <button
                type="button"
                className={`ct-mode-chip ${formDefaultMode === 'onlineLive' ? 'active' : ''}`}
                onClick={() => setFormDefaultMode('onlineLive')}
              >
                默认在线
              </button>
            </div>
            <div className="ct-settings-grid">
              <label className="ct-field">
                <span>ASR 提供商</span>
                <select value={formAsrProvider} onChange={(e) => setFormAsrProvider(e.target.value)}>
                  <option value="volcengine">火山 Volcengine</option>
                  <option value="openai-compatible">OpenAI 兼容</option>
                </select>
              </label>
              {formAsrProvider === 'volcengine' ? <>
                <label className="ct-field"><span>火山 Resource ID</span><input value={formVolcResource} onChange={(e) => setFormVolcResource(e.target.value)} spellCheck={false} /></label>
                {credentialField('volcAppKey', '火山 App Key', formVolcApp, setFormVolcApp, productSettings?.volcAppKeySet)}
                {credentialField('volcAccessKey', '火山 Access Key', formVolcAccess, setFormVolcAccess, productSettings?.volcAccessKeySet)}
              </> : <>
                <label className="ct-field"><span>兼容服务 Endpoint</span><input value={formOpenAiEndpoint} onChange={(e) => setFormOpenAiEndpoint(e.target.value)} spellCheck={false} /></label>
                {credentialField('openaiAsrApiKey', '兼容服务 Key', formOpenAiKey, setFormOpenAiKey, productSettings?.openaiAsrApiKeySet)}
                <label className="ct-field"><span>兼容服务模型</span><input value={formOpenAiModel} onChange={(e) => setFormOpenAiModel(e.target.value)} spellCheck={false} /></label>
              </>}
              {formDeepseekEnabled ? <>
                {credentialField('deepseekApiKey', 'DeepSeek Key', formDeepseekKey, setFormDeepseekKey, productSettings?.deepseekApiKeySet)}
                <label className="ct-field"><span>DeepSeek Base URL</span><input value={formDeepseekBase} onChange={(e) => setFormDeepseekBase(e.target.value)} spellCheck={false} /></label>
                <label className="ct-field"><span>DeepSeek 模型</span><input value={formDeepseekModel} onChange={(e) => setFormDeepseekModel(e.target.value)} spellCheck={false} /></label>
              </> : null}
            </div>
            <label className="ct-field-check">
              <input type="checkbox" checked={formDeepseekEnabled} onChange={(e) => setFormDeepseekEnabled(e.target.checked)} />
              启用 DeepSeek 智能纪要，整理摘要、决定与行动项
            </label>
            <label className="ct-field-check">
              <input type="checkbox" checked={formBleCompress} onChange={(e) => setFormBleCompress(e.target.checked)} />
              旧设备的节省流量模式（可能降低音质）
            </label>
            <p className="ct-step-meta">新版设备录音已压缩，会直接同步原始压缩音频。本开关仅适用于旧设备的未压缩录音，不会再次压缩已有的 Opus 录音。</p>
            {missingServiceFields.length ? <p className="ct-step-warn" aria-label="服务配置缺项">
              还缺：{missingServiceFields.join('、')}。可以先保存并使用“先录后整理”，但缺项会阻止对应的转写或智能纪要。
            </p> : <p className="ct-step-meta" aria-label="服务配置完整性">必填项已提供，但实际服务调用仍需用一次真实转写/纪要验证。</p>}
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={controlsBusy || settingsBusy || oobeBlockedByRecording || !productSettings || productSettings.storageSaveBlocked || !onSaveProductSettings}
                onClick={() => {
                  if (controlsBusy || settingsBusy || oobeBlockedByRecording || !productSettings || productSettings.storageSaveBlocked || !onSaveProductSettings || settingsActive.current) return;
                  settingsActive.current = true;
                  setSettingsMsg(null);
                  setSettingsBusy(true);
                  void Promise.resolve().then(() => onSaveProductSettings?.({
                    defaultMeetingMode: formDefaultMode,
                    asrProvider: formAsrProvider,
                    volcAppKey: clearCredentials.includes('volcAppKey') ? '' : formVolcApp,
                    volcAccessKey: clearCredentials.includes('volcAccessKey') ? '' : formVolcAccess,
                    volcResourceId: formVolcResource,
                    openaiAsrEndpoint: formOpenAiEndpoint,
                    openaiAsrApiKey: clearCredentials.includes('openaiAsrApiKey') ? '' : formOpenAiKey,
                    openaiAsrModel: formOpenAiModel,
                    deepseekApiKey: clearCredentials.includes('deepseekApiKey') ? '' : formDeepseekKey,
                    deepseekBaseUrl: formDeepseekBase,
                    deepseekModel: formDeepseekModel,
                    deepseekMinutesEnabled: formDeepseekEnabled,
                    bleCompress: formBleCompress,
                    clearCredentials,
                  })).then(() => {
                    setSettingsMsg('配置已保存，实际服务调用尚未验证。');
                    setClearCredentials([]);
                    setFormVolcApp('');
                    setFormVolcAccess('');
                    setFormOpenAiKey('');
                    setFormDeepseekKey('');
                  }).catch((err: unknown) => {
                    setSettingsMsg(err instanceof Error ? err.message : String(err));
                  }).finally(() => { settingsActive.current = false; setSettingsBusy(false); });
                }}
              >
                {settingsBusy ? '正在保存…' : '保存设置'}
              </button>
            </div>
            {clearCredentials.length ? <p className="ct-step-warn" role="status">保存后将清空所选密钥，并停止对应服务。保存前可撤销清空；重新填写密钥后可恢复使用。</p>
              : <p className="ct-step-meta">密钥留空会保持原值；需要删除时点“清空密钥”，再保存设置。</p>}
            {settingsMsg ? <p className="ct-step-meta">{settingsMsg}</p> : null}
            <div className="ct-button-row">
              {(['asr', 'minutes'] as const).map(service => <button key={service} type="button" className="ct-action"
                disabled={controlsBusy || settingsBusy || oobeBlockedByRecording || productSettings?.storageSaveBlocked || serviceConfigDirty || !onCheckService || (service === 'minutes' && !formDeepseekEnabled)}
                onClick={() => void checkService(service)}>{serviceBusy === service ? '正在测试…' : service === 'asr' ? '测试转写服务' : '测试纪要服务'}</button>)}
            </div>
            <p className="ct-step-meta">按已保存配置发送一秒静音或固定测试文字，不读取会议或麦克风，服务商可能计费。测试通过不代表识别或纪要准确率通过。{serviceConfigDirty ? '设置有修改，请先保存再测试。' : ''}</p>
            {(['asr', 'minutes'] as const).map(service => serviceResults[service] ? <p key={service} className="ct-step-meta" role="status">{service === 'asr' ? '转写' : '纪要'}：{serviceResults[service]}</p> : null)}
          </section>

          <section className="ct-panel">
            <div className="ct-panel-title">
              <Download size={18} />
              <span>多格式导出</span>
            </div>
            <div className="ct-button-row">
              {(['markdown', 'txt', 'json', 'srt', 'todo', 'ics'] as const).map((format) => <button key={format} type="button" className="ct-action"
                disabled={controlsBusy || oobeBlockedByRecording || !onExportMeeting || (['markdown', 'todo', 'ics'].includes(format) ? !hasMinutes : !finalTranscript)}
                onClick={() => void exportMeeting(format)}>{format === 'markdown' ? 'Markdown' : format === 'todo' ? '待办清单' : format === 'ics' ? '日历待办 (.ics)' : format.toUpperCase()}</button>)}
            </div>
            <p className="ct-step-meta">选择保存位置；导出只使用已保存的内容，不会重新调用转写或纪要服务。SRT 需要真实时间戳。</p>
            <p className="ct-step-meta">待办取自当前纪要的“行动项 / Action Items”列表；修改后请先保存。日历文件使用 VTODO，需支持待办的日历应用；仅明确的日期或带时区时间设为截止时间，“周五”等保留原文供核对，不自动猜日期。</p>
          </section>

          <section className="ct-ops-grid">
            <section className="ct-panel">
              <div className="ct-panel-title"><Shield size={18} /><span>隐私</span></div>
              <div className="ct-metric-grid">
                <InfoMetric label="音频" value={privacy ? formatBytes(privacy.audioCacheBytes) : '0'} />
                <InfoMetric label="文本" value={privacy ? formatBytes(privacy.transcriptBytes + privacy.minutesBytes) : '0'} />
                <InfoMetric label="自动删除" value="未启用" />
              </div>
              <p className="ct-step-meta">会议与原音保存在本机，直到你主动删除。另存的原音和导出文件由你自行保管，不会随会议删除。</p>
              <p className="ct-step-meta">{selectedSession?.organization?.protected?'当前录音已受保护，解除前不能删除音频、文字或整场。':'普通删除先进入本机回收站，可恢复；永久清除在回收站单独确认。保护防误删，不是加密。'}</p>
              <div className="ct-button-row">
                <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||!selectedSession||!onSaveLibraryLifecycle||libraryUnsaved} onClick={()=>void changeCurrentLibraryState(selectedSession?.organization?.protected?'unprotect':'protect')}>{selectedSession?.organization?.protected?'解除当前录音保护':'保护当前录音'}</button>
                <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !canEraseAudio} onClick={() => requestErase('privacyEraseAudio', '删除这场会议的本机音频？', '保留已有文字和纪要，取消尚未完成的自动处理。设备上的原始录音不受影响。')}>
                  <Eraser size={16} /><span>删音频</span>
                </button>
                <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !canEraseTranscript} onClick={() => requestErase('privacyEraseTranscript', '删除这场会议的文字、纪要和备注？', '保留录音，取消尚未完成的自动处理。用户备注也会删除，重新转写不会恢复这些备注；请先保存需要的内容。')}>
                  <FileText size={16} /><span>删文本</span>
                </button>
                <button
                  type="button"
                  className="ct-action ct-action-danger"
                  disabled={controlsBusy || oobeBlockedByRecording || !selectedSession||!onSaveLibraryLifecycle||Boolean(selectedSession?.organization?.protected)||libraryUnsaved}
                  onClick={() => void changeCurrentLibraryState('trash')}
                  title="移入本机回收站，可恢复；不删除或确认消费设备录音"
                >
                  <Trash2 size={16} /><span>移入回收站</span>
                </button>
                <button type="button" className="ct-action ct-action-danger" disabled={controlsBusy || oobeBlockedByRecording || allLibrarySessions.length === 0||allLibrarySessions.some(s=>s.organization?.protected)} onClick={() => requestErase('privacyEraseAll', '永久清除全部本机会议与回收站？', `将永久清除 ${allLibrarySessions.length} 场会议（含回收站）的本机音频、文字和纪要，并取消自动处理，不能恢复。设备上的录音需在设备菜单中另行清除。`)}>
                  <Trash2 size={17} />清除全部本机会议
                </button>
              </div>
              {pendingDelete ? <div className="ct-delete-confirm" role="alertdialog" aria-label={pendingDelete.title} aria-describedby="ct-delete-description">
                <strong>{pendingDelete.title}</strong>
                {pendingDelete.request.action !== 'privacyEraseAll' ? <p>当前录音：{selectedSession?.title}</p> : null}
                <p id="ct-delete-description">{pendingDelete.detail}</p>
                <div className="ct-button-row">
                  <button type="button" className="ct-action" autoFocus onClick={() => setPendingDelete(null)}>保留内容</button>
                  <button type="button" className="ct-action ct-action-danger" disabled={controlsBusy || oobeBlockedByRecording} onClick={() => {
                    const request = pendingDelete.request;
                    setPendingDelete(null);
                    onControl(request);
                  }}>确认删除</button>
                </div>
              </div> : null}
            </section>
          </section>

          <section className="ct-panel">
            <div className="ct-panel-title"><Bluetooth size={18} /><span>设备名称</span></div>
            <div className="ct-name-row">
              <input aria-label="Companion 设备名称" value={draftName} onChange={(event) => setDraftName(event.target.value)} spellCheck={false} />
              <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !connected || !draftName.trim() || Boolean(nameError)} onClick={() => onControl({ action: 'applyBleName', bleName: draftName })}>保存到设备</button>
              <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !connected} onClick={() => onControl({ action: 'resetBleName' })}>恢复默认名称</button>
            </div>
            <p className="ct-step-meta">{nameError ? '名称不符合设备要求，请缩短名称，并避免中文、引号、分号等字符。' : `当前名称：${snapshot?.bleName.activeName ?? '尚未读取'}。保存后会读取设备确认结果。`}</p>
          </section>
        </div>
      ) : null}

      </section>

      <div className="ct-page-panel" hidden={pageView !== 'settings'}>{settingsFooter}</div>
      <footer className="ct-footer">{titleDirty || minutesDirty || transcriptReviewUnsaved || bookmarkUnsaved || noteUnsaved || libraryUnsaved ? '有尚未保存的修改。' : footer}</footer>
    </main>
  );
}

// Source alone is insufficient: imported text can accompany a real recording.
// Preserve all capture/sync/audio warnings whenever such evidence remains.
function isTextOnlyImport(session: CompanionV1HostSession): boolean {
  return session.source === 'importedTranscript'
    && companionSessionHasFinalTranscript(session) && Boolean(session.transcriptText.trim())
    && session.status !== 'recording' && !session.captureIncomplete
    && !session.recorderControlUncertain && !session.recorderControl
    && session.deviceRecordingId == null && !session.deviceRecordingKey
    && !session.sourceDeviceId && !session.deviceTotalLength && !session.deviceSha256
    && !session.audioStored && !session.retention.audioCached
    && !session.audioPath && session.audioBytes === 0
    && !session.chunks.some(chunk => Boolean(chunk.path) || chunk.bytes > 0)
    && !['needs_pull', 'needs_device_sync', 'needs_segments', 'needs_local_audio',
      'device_control_pending', 'capture_interrupted'].includes(session.pendingReason ?? '');
}

function RecordingSafetyCard({ session, persistence, recoveryProcessing }: {
  session: CompanionV1HostSession;
  persistence: CompanionV1Snapshot['host']['persistence'];
  recoveryProcessing: boolean;
}) {
  if (isTextOnlyImport(session)) {
    const saved = persistence?.status === 'ready';
    const failed = persistence?.status === 'blocked' || persistence?.status === 'unsaved';
    return <section className="ct-safety-card" aria-label="文字保存状态">
      <header><strong>文字保存状态</strong><span>{saved ? '文字已保存在本机'
        : failed ? '文字保存失败' : '保存状态待确认'}</span></header>
      <p>这条记录来自导入文字，没有原录音；无需等待设备同步或转写。</p>
      {!saved ? <p role="alert">{persistence?.message
        ?? '本机保存尚未确认，请先在保存提示中重试。'}</p> : null}
    </section>;
  }
  const captureOngoing = session.status === 'recording';
  const wholeReclaimed = Boolean(session.deviceReclaimed && !captureOngoing);
  const savedSegments = session.source === 'boardDevice' && session.deviceRecordingKey
    ? session.chunks.filter((chunk) => chunk.status === 'sealed' && chunk.path && chunk.bytes > 0).length : 0;
  const rawComplete=session.pendingReason==='needs_local_audio'&&!captureOngoing;
  const transferPending = ['needs_device_sync', 'needs_segments', 'needs_pull'].includes(session.pendingReason ?? '');
  const cachedAudio = Boolean(session.audioStored && session.audioPath && session.audioBytes > 0);
  const localAudio = !transferPending
    && !captureOngoing && (session.deviceRecordingKey
      ? Boolean(session.audioStored && session.audioPath && session.audioBytes > 0)
      : Boolean(session.audioPath || (session.audioStored && session.audioBytes > 0)));
  const partialAudio = !localAudio && (savedSegments > 0 || cachedAudio);
  const deviceCopy = Boolean(session.sourceDeviceId && (session.deviceRecordingId != null||session.deviceRecordingKey) && !wholeReclaimed);
  const growingDeviceCapture = captureOngoing && deviceCopy;
  const exactDeviceCopy = Boolean(deviceCopy && session.deviceTotalLength
    && /^[0-9a-f]{64}$/i.test(session.deviceSha256 ?? ''));
  const saveConfirmed = persistence?.status === 'ready';
  const saveFailed = persistence?.status === 'blocked' || persistence?.status === 'unsaved';
  const canReclaim = exactDeviceCopy && localAudio && saveConfirmed
    && !session.captureIncomplete && !session.recorderControlUncertain;
  const steps = [
    {
      label: '设备',
      state: growingDeviceCapture ? session.recorderControlUncertain ? '录音状态待核对'
        : session.recorderControl?.confirmed?.state === 3 ? '录音已暂停' : '录音仍在进行'
        : wholeReclaimed ? '已精确回收' : deviceCopy ? session.deviceRecordingKey ? '分段回收待确认' : '原录音仍保留' : session.pendingReason === 'needs_device_sync' ? '等待来源设备' : '无设备副本',
      kind: growingDeviceCapture ? 'active' : wholeReclaimed || deviceCopy ? 'done' : 'idle',
    },
    {
      label: '传到电脑',
      state: rawComplete ? '原音已收齐' : localAudio ? session.captureIncomplete ? '已收齐恢复片段' : '音频已收齐'
        : partialAudio ? captureOngoing ? savedSegments > 0 ? `已收到${savedSegments}段，继续同步` : '已收到片段，录音仍在进行' : '已收到片段，整条尚未收齐'
        : session.pendingReason === 'needs_device_sync' ? '连接后继续同步' : recoveryProcessing ? '正在处理' : '尚未收齐',
      kind: localAudio || rawComplete ? 'done' : partialAudio || recoveryProcessing ? 'active' : 'idle',
    },
    {
      label: '本机保存',
      state: saveFailed ? '保存失败，可重试' : saveConfirmed && rawComplete ? '原音已保存，回听待生成' : saveConfirmed && localAudio ? '已安全保存'
        : saveConfirmed && partialAudio ? savedSegments > 0 ? `已保存${savedSegments}段，整条尚未收齐` : '已有片段已保存，整条尚未收齐'
        : localAudio || partialAudio || rawComplete ? '已有音频，保存状态待确认' : '等待音频',
      kind: saveFailed ? 'error' : saveConfirmed && (localAudio || partialAudio || rawComplete) ? 'done' : 'idle',
    },
    {
      label: '设备空间',
      state: wholeReclaimed ? '设备副本已回收' : growingDeviceCapture
        ? savedSegments > 0 && saveConfirmed ? '已保存分段可回收，尾段保留'
        : partialAudio ? '已收到片段，回收待确认' : '录音尾段保留'
        : canReclaim ? '可在删除会议时精确回收' : deviceCopy ? '暂不回收' : '无需回收',
      kind: wholeReclaimed ? 'done' : growingDeviceCapture || canReclaim ? 'active' : 'idle',
    },
  ];
  return <section className="ct-safety-card" aria-label="录音安全状态">
    <header><strong>录音安全状态</strong><span>{saveFailed ? '需要处理'
      : !saveConfirmed && (localAudio || partialAudio || rawComplete) ? '保存状态待确认'
      : localAudio ? '电脑已有副本' : partialAudio ? '本机已有片段，仍待收齐' : '内容仍在流转'}</span></header>
    {session.processingPolicy === 'manual' ? <p>这是一份普通录音。转写和纪要由你手动启动，同步原音后不会自动提交云端处理。</p> : null}
    <ol>{steps.map((step) => <li key={step.label} className={`ct-safety-${step.kind}`}><span aria-hidden="true" />
      <div><strong>{step.label}</strong><small>{step.state}</small></div></li>)}</ol>
    {session.pendingReason === 'needs_device_sync' ? <p>录音仍在来源设备；重连同一台 Companion 后会从断点继续。</p> : null}
    {session.pendingReason === 'needs_segments' ? <p>这场录音尚未收齐。已有片段会保留，连接同一台 Companion 后继续同步。</p> : null}
    {session.deviceRecordingEndReason ? <p>{({user: '你已停止设备录音。', storageFull: '设备存储空间不足，录音已安全结束。', durationLimit: '已达到设定时长，设备录音已结束。', lowBattery: '设备因电量低结束了录音。', silence: '已达到设定的静音时长，设备录音已结束。'} as const)[session.deviceRecordingEndReason]} 原音同步和本机保存进度见上方。</p> : null}
    {session.captureIncomplete ? <p role="alert">这场录音曾意外中断，实际保存 {formatDuration(session.durationMs)}，结尾可能缺失。可以回听或导出原音；转写与纪要只覆盖已保存的片段。{!session.recovery?.captureReviewConfirmed ? '选择整理片段后才会继续处理。' : ''}</p> : null}
    {saveFailed ? <p>{persistence?.message ?? '本机索引尚未安全保存，当前不会回收设备副本。'}</p> : null}
  </section>;
}

function InfoMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="ct-metric">
      <span className="ct-metric-label">{label}</span>
      <strong className="ct-metric-value">{value}</strong>
    </div>
  );
}

function meetingSearchText(session: CompanionV1HostSession): string {
  return [
    meetingTitle(session),
    session.transcriptText,
    companionReviewedTranscript(session),
    ...(session.meetingNotes ?? []).map(note => note.text),
    session.minutes?.markdown,
    session.minutesByMode?.offlineStore?.markdown,
    session.minutesByMode?.onlineLive?.markdown,
  ].filter(Boolean).join('\n').toLocaleLowerCase();
}

function meetingMinutesMarkdown(session: CompanionV1HostSession, mode: CompanionV1MeetingMode): string {
  const variant = session.minutesByMode?.[mode];
  if (variant) return variant.markdown;
  return session.meetingMode === mode ? session.minutes?.markdown ?? '' : '';
}

function meetingTitle(session: CompanionV1HostSession): string {
  if (session.title.trim() && session.title !== 'Companion device recording') return session.title;
  return session.deviceRecordingId != null ? `会议录音 #${session.deviceRecordingId}` : '未命名会议';
}

function meetingSource(session: CompanionV1HostSession): string {
  if (session.source === 'deviceFlash' || session.source === 'boardDevice') return 'Companion 录音';
  if (session.source === 'hostMicrophone') return '本机麦克风';
  if (session.source === 'importedTranscript') return '导入文字';
  return '演示记录';
}

function MinutesReadingView({ markdown, savedMarkdown=markdown, transcript, durationMs, compactAllowed, noteContext, onToggleAction, actionsBlocked, ...sourceProps }: {
  markdown: string; transcript: string; durationMs: number; compactAllowed: boolean; noteContext?:CompanionMinutesNoteContext|null;
  onToggleAction?:(lineIndex:number,completed:boolean)=>void;actionsBlocked?:boolean;savedMarkdown?:string;
  sources?: readonly CompanionTranscriptSource[]; blocked?: boolean;
  onOpenSource?: (source: CompanionTranscriptSource) => void;
}) {
  // Only fold the exact native provenance envelope represented by the saved
  // typed source snapshot. Complete saved output remains available below.
  let reading=markdown;
  if(noteContext){
    const envelope = minutesSourceEnvelope(noteContext);
    if(markdown.startsWith(envelope))reading=markdown.slice(envelope.length);
  }
  const actionChecklist=onToggleAction?{items:savedActions(savedMarkdown),onToggle:onToggleAction,blocked:actionsBlocked,compactSources:!!noteContext}:undefined;
  const brief = compactAllowed ? briefMinutes(reading, transcript, durationMs, !!noteContext) : null;
  if (!brief) return <div className="ct-brief-minutes">
    <MarkdownMinutes markdown={reading} actionChecklist={actionChecklist} {...sourceProps} />
    {reading!==markdown?<details className="ct-full-minutes"><summary>查看本次补充来源与完整整理</summary>
      <MarkdownMinutes markdown={reading} actionChecklist={actionChecklist} {...sourceProps}/>
      {noteContext?<details className="ct-full-minutes"><summary>核对本次补充来源</summary>
        <MarkdownMinutes markdown={minutesSourceEnvelope(noteContext)} {...sourceProps}/>
      </details>:null}
    </details>:null}
  </div>;
  // Keep a short personal note focused on its saved checklist. Important
  // questions remain explicitly signposted; complete content is one tap away.
  const contextStart = noteContext && brief.startsWith('## 待办\n\n') ? brief.indexOf('\n\n## 重点\n\n') : -1;
  const checklistOnly = contextStart > 0 && savedActions(brief).length > 0;
  const hasQuestions = checklistOnly && brief.includes('\n\n## 需确认\n\n');
  return <div className="ct-brief-minutes">
    <MarkdownMinutes markdown={checklistOnly ? brief.slice(0, contextStart) : brief} actionChecklist={actionChecklist} {...sourceProps} />
    {hasQuestions ? <p className="ct-step-meta">还有待确认事项，可展开查看。</p> : null}
    <details className="ct-full-minutes"><summary>{checklistOnly ? hasQuestions ? '查看重点与待确认' : '查看重点和完整整理' : '查看完整整理'}</summary>
      <MarkdownMinutes markdown={reading} actionChecklist={actionChecklist} {...sourceProps} />
      {noteContext&&reading!==markdown?<details className="ct-full-minutes"><summary>核对本次补充来源</summary>
        <MarkdownMinutes markdown={minutesSourceEnvelope(noteContext)} {...sourceProps}/>
      </details>:null}
    </details>
  </div>;
}

function MarkdownMinutes({ markdown, sources = [], blocked, onOpenSource, actionChecklist }: { markdown: string;
  actionChecklist?:{items:SavedAction[];onToggle:(lineIndex:number,completed:boolean)=>void;blocked?:boolean;compactSources?:boolean};
  sources?: readonly CompanionTranscriptSource[]; blocked?: boolean;
  onOpenSource?: (source: CompanionTranscriptSource) => void }) {
  if (!markdown.trim()) return <p className="ct-document-empty">这条录音还没有整理结果。</p>;
  const actionRows=new Map(savedActions(markdown).flatMap((row,index)=>{
    const saved=actionChecklist?.items[index];
    return saved&&saved.text===row.text&&saved.completed===row.completed?[[row.lineIndex,saved] as const]:[];
  }));
  const blocks: Array<{ type: 'title' | 'heading' | 'item' | 'text'; text: string;action?:SavedAction }> = [];
  markdown.split(/\r?\n/).forEach((raw,lineIndex) => {
    const line = raw.trim();
    if (!line || /^Generated:|^Duration:|^Source:|^Minutes engine:/i.test(line)) return;
    if (line.startsWith('# ')) blocks.push({ type: 'title', text: line.slice(2) });
    else if (/^#{2,3} /.test(line)) blocks.push({ type: 'heading', text: line.replace(/^#{2,3} /, '') });
    else if (/^[-*+]\s+/.test(line)) blocks.push({ type: 'item', text: line.replace(/^[-*+]\s+/, ''),action:actionRows.get(lineIndex) });
    else if (/^\d+[.)]\s+/.test(line)) blocks.push({ type: 'item', text: line.replace(/^\d+[.)]\s+/, ''),action:actionRows.get(lineIndex) });
    else if (!/^None captured$/i.test(line)) blocks.push({ type: 'text', text: line });
  });
  // A known empty template marker is not content to show a customer. This is
  // display only; saved results, editing, provenance and exports remain intact.
  const contentBlocks=blocks.filter(block=>!['item','text'].includes(block.type)||!/^None captured[.。]?$/i.test(block.text));
  const visibleBlocks = contentBlocks.filter((block, index) => {
    if (block.type !== 'heading') return true;
    const next = contentBlocks[index + 1];
    return next && next.type !== 'heading' && next.type !== 'title';
  });
  const visibleActions = visibleBlocks.flatMap(block => block.action ? [block.action] : []);
  const commonSupplement = actionChecklist?.compactSources && visibleActions.length === actionChecklist.items.length
    ? commonActionSupplement(visibleActions) : null;
  const firstActionIndex = visibleBlocks.findIndex(block => block.action);
  return (
    <article className="ct-minutes-article">
      {visibleBlocks.map((block, index) => {
        if (block.type === 'title') return <h3 key={index}>{formatMinutesTitle(block.text)}</h3>;
        if (block.type === 'heading') return <h4 key={index}>{translateMinutesHeading(block.text)}</h4>;
        const references = companionMinutesReferencedSources(sources, block.text);
        const links = onOpenSource && references.length ? <span className="ct-minutes-source-links">
          {references.map((source) => <button type="button" className="ct-text-button" key={source.index}
            disabled={blocked} aria-label={`核对第${source.index + 1}段原文`}
            onClick={() => onOpenSource(source)}>核对原文 · {Math.floor(source.startMs / 60000)}:{String(Math.floor(source.startMs / 1000) % 60).padStart(2, '0')}</button>)}
        </span> : null;
        if(block.action&&actionChecklist){const action=block.action;
          const actionIndex=visibleActions.indexOf(action);
          const shownText=commonSupplement?commonSupplement.displayTexts[actionIndex]:action.text;
          const supplementary=actionChecklist.compactSources&&shownText.startsWith('用户补充：');
          const displayText=supplementary?shownText.slice('用户补充：'.length):shownText;
          const parts=actionChecklist.compactSources?splitActionSupplement(displayText):null;
          const shownTitle=parts?.title??displayText;
          const conditional=actionChecklist.compactSources&&shownTitle.startsWith('有条件：');
          return <div key={index}>
          {commonSupplement&&index===firstActionIndex?<p className="ct-action-source-legend">{commonSupplement.text.startsWith('共同适用规则：')?'共同适用规则：':'以下事项的共同补充：'}{commonSupplement.text.startsWith('共同适用规则：')?commonSupplement.text.slice('共同适用规则：'.length):commonSupplement.text}</p>:null}
          <div className="ct-minutes-item ct-minutes-action-item">
          <label className={`ct-saved-action${action.completed?' completed':''}`}><input type="checkbox" checked={action.completed}
            disabled={blocked||actionChecklist.blocked} aria-label={`${action.completed?'恢复为待办':'标记完成'}：${action.text}`}
            onChange={event=>actionChecklist.onToggle(action.lineIndex,event.target.checked)}/><span>
              <span>{conditional?shownTitle.slice('有条件：'.length):shownTitle}{conditional?<small className="ct-action-condition-mark">按补充安排</small>:null}{supplementary?<sup className="ct-action-source-mark" title="来自本次补充" aria-label="来自本次补充">＊</sup>:null}</span>
              {parts?<span className="ct-action-supplement"><span className="ct-action-supplement-label">补充</span>{parts.context}</span>:null}
            </span></label>{links}</div></div>;}
        if (block.type === 'item') return <div key={index} className="ct-minutes-item"><span className="ct-minutes-bullet" aria-hidden="true">•</span><span>{block.text}{links}</span></div>;
        return <p key={index}>{block.text}{links}</p>;
      })}
      {actionChecklist?.compactSources&&visibleBlocks.some(block=>block.action?.text.startsWith('用户补充：'))?
        <p className="ct-action-source-legend">＊ 来自本次补充；原话与补充仍分别保留。</p>:null}
    </article>
  );
}

function translateMinutesHeading(value: string): string {
  const headings: Record<string, string> = {
    Summary: '摘要', 摘要: '摘要', Decisions: '关键决定', 决定: '关键决定', 'Action Items': '行动项', Questions: '待确认问题', 问题: '待确认问题', Keywords: '关键词',
  };
  return headings[value] ?? value;
}

function formatMinutesTitle(value: string): string {
  if (/^Recording \d+ onlineLive$/i.test(value)) return '在线会议速记';
  if (/^Companion device recording$/i.test(value)) return '会议纪要';
  return value;
}

function formatTranscript(text: string) {
  if (!text.trim()) return <p className="ct-document-empty">这场会议还没有转写内容。</p>;
  return text.split(/\r?\n/).filter(Boolean).map((line, index) => {
    const match = line.match(/^(说话人(?:\d+|\?))[:：]\s*(.*)$/);
    return (
      <div className="ct-transcript-line" key={index}>
        <span>{match?.[1] ?? '转写'}</span><p>{match?.[2] ?? line}</p>
      </div>
    );
  });
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(durationMs: number): string {
  const seconds = Math.max(0, Math.round(durationMs / 1000));
  const minutes = Math.floor(seconds / 60);
  const remain = seconds % 60;
  return minutes > 0 ? `${minutes}:${String(remain).padStart(2, '0')}` : `${remain} 秒`;
}
