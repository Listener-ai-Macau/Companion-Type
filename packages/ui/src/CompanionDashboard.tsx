import {meetingReadingSources} from './meetingReadingSources';
import {LibraryPanel} from './LibraryPanel';
import {LibraryScopeChips,type LibraryScopeChip} from './LibraryScopeChips';
import {ContentExportPanel,type ContentExportTarget} from './ContentExportPanel';
import {MeetingWorkspaceNav,meetingPaneForTarget,type MeetingPane} from './MeetingWorkspaceNav';
import {ActionReviewTools,useActionReview} from './ActionReviewTools';
import {savedActionReview} from './actionReview';
import {shareHandoffMessage,type ShareDestination,type ShareHandoffResult} from './shareHandoff';
import { cleanHesitations, transcriptParagraphs } from './transcriptReading';
import { MeetingTopic } from './MeetingTopic';
import { CompanionCalendarCopies } from './CompanionCalendarCopies';
import {readRestoredCustomTemplates} from './customTemplateBackup';
import {CalendarCopyComparison} from './CalendarCopyComparison';
import {lastSavedCalendarReminders,retainCalendarReminders,carryRelativeReminderAfterSingleDeadlineEdit} from './calendarReminderCarryover';
import {retainCalendarSlots} from './calendarSlotCarryover';
import {operationErrorText,calendarExportNeedsTime} from './operationFailure';
import {cardRecordingStatus} from './cardRecordingStatus';
import {savedExportPreview,SavedPreviewInterrupted} from './savedExportPreview';
import {nativeActionParts,actionReadingParts} from './actionMetadata';
import {readableCalendarTime} from './calendarTime';
import { recordingCapacityAvailableSeconds, recordingCapacityRequiredBytes, recordingCapacityCanFit } from '@companion-type/core';
import {CompanionDeviceRecordings,type DeviceRecordingActions} from './CompanionDeviceRecordings';
import { Fragment, useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';
import {isGeneratedReadingNotice,splitGeneratedMeetingMetadata} from './meetingReading';
import './overviewTopics.css';
import './meetingNoteDocument.css';
import { CompanionSetup } from './CompanionSetup';
import { CompanionRecordingReadiness, fragmentedSpaceMayFit, recordingRoomLabel } from './CompanionRecordingReadiness';
import {deviceConnectionStatus} from './deviceConnectionStatus';
import { CompanionHelp } from './CompanionHelp';
import {recorderKeyGuide} from './recorderKeyGuide';
import { CompanionPrivacyCleanup } from './CompanionPrivacyCleanup';
import { MinutesModeTabs } from './MinutesModeTabs';
import { MeetingReadingFrame } from './MeetingReadingFrame';
import { DeleteConfirmation } from './DeleteConfirmation';
import {CompanionDiagnosticsPreview} from './CompanionDiagnosticsPreview';
import {CompanionPetFind,type PetFindRequest,type PetFindReport} from './CompanionPetFind';
import { CompanionTranscriptReview } from './CompanionTranscriptReview';
import { CompanionBookmarks } from './CompanionBookmarks';
import { CompanionAudioPlayer, type CompanionPauseTimeline } from './CompanionAudioPlayer';
import { CompanionSegmentedAudioPlayer, type SegmentedPlaybackControl } from './CompanionSegmentedAudioPlayer';
import type {RecordingPart} from './recordingParts';
import { CompanionMeetingAudioPlayer, type MeetingAudioControl } from './CompanionMeetingAudioPlayer';
import type { MeetingPlaybackTracks } from './meetingTrackPlayback';
import {useListeningQueue} from './useListeningQueue';
import {CompanionLibraryTools,type LibraryFilters} from './CompanionLibraryTools';
import {recordingInDates} from './libraryDates';
import {libraryPreview,latestSavedResult} from './libraryPreview';
import {recordingDisplayTitle,recordingDateGroup,recordingTextState} from './recordingPresentation';
import {NotebookNavigation} from './NotebookNavigation';
import type {CompanionLibraryExportRequest,CompanionLibraryExportResult} from '../../core/src/libraryOrganization';
import type {CompanionLibraryStateRequest,CompanionLibraryPurgeRequest,CompanionLibraryPurgeResult} from '../../core/src/libraryOrganization';
import type {CompanionLibraryOrganizationRequest} from '../../core/src/libraryOrganization';
import { companionMinutesNotesCurrent, type CompanionMinutesNoteContext } from '@companion-type/core';
import { CompanionMeetingNotes } from './CompanionMeetingNotes';
import { CompanionExportFeedback, exportFileName, type OpenSavedCalendar } from './CompanionExportFeedback';
import { CompanionChecklistPhone, type ChecklistPhoneResult } from './CompanionChecklistPhone';
import { checklistPhoneCode } from './checklistPhone';
import { briefMinutes, splitLongMinutesEvidence, splitShortMinutesEvidence, splitShortMinutesOverview } from './briefMinutes';
import { savedCustomMinutesTemplates } from './minutesTemplateLibrary';
import {MeetingReferenceWorkspace,type ReferenceView} from './MeetingReferenceWorkspace';
import {MeetingAiWorkbench} from './MeetingAiWorkbench';
import {TranscriptQuoteCapture} from './TranscriptQuoteCapture';
import type {ManualEvidenceDraft} from '../../core/src/manualNoteContext';
import type {DocumentSourceRequest} from './DocumentContextPanel';
import {DocumentContextPanel} from './DocumentContextPanel';
import {materialNote,readMaterialNote} from './aiMaterialNote';
import {ActionListEditor} from './ActionListEditor';

type MeetingExportOrigin = 'pdf' | 'text' | 'notes' | 'document' | 'documentTools' | 'bookmarks' | 'recordingTools' | 'audio' | 'workflow' | 'settings';
import {CalendarExportItems,effectiveCalendarAlarm,type CalendarExportItem,type CalendarReminderChoice} from './CalendarExportItems';
import {savedActions,markSavedAction,commonActionSupplement,splitActionSupplement,compactActionSource,type SavedAction} from './savedActions';
import { seekBookmarkAudio } from './bookmarkAudio';
import { companionTranscriptUnmappedEdges } from '@companion-type/core';
import { CompanionJourney, hostRecordingAudioConfirmed, meetingHasFinalMinutes, meetingJourney } from './CompanionJourney';
import { CompanionRecoveryCenter } from './CompanionRecoveryCenter';
import { CompanionRecordingSync } from './CompanionRecordingSync';
import { CompanionCard } from './CompanionCard';
import { CompanionRecorderControl } from './CompanionRecorderControl';
import { CompanionBehaviorPreview } from './CompanionBehaviorPreview';
import {
  Bluetooth,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  Eraser,
  Ellipsis,
  FileText,
  HardDrive,
  Headphones,
  Heart,
  Link2,
  ListFilter,
  Mic,
  Moon,
  Pencil,
  Play,
  RefreshCw,
  Search,
  Shield,
  Square,
  SquareCheck,
  Sun,
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
  companionReviewedUtterances,
  companionTranscriptReviewRevision,
  companionTranscriptReviewIsStale,
  normalizeCompanionNoteText,
  companionBleNameIsValid,
  companionSessionHasFinalTranscript,
  describeCompanionMeetingRecovery,
  selectedCompanionHostSession,
} from '@companion-type/core';

export type CompanionProductSettingsPublic = {
  autoLocalCardTranscription?: boolean;
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

const listeningIdentity = (session:CompanionV1HostSession) => JSON.stringify([session.id,session.audioPath??'',
  session.audioBytes,session.deviceSha256??'',session.deviceRecordingKey??'',session.audioStored,session.retention.audioCached,session.meetingTracks??null]);

function recordingTimeLabel(value?: string | number | null) {
  const date = value !== undefined && value !== null && value !== '' ? new Date(value) : null;
  return date && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false }).format(date)
    : '时间未记录';
}

// Native lifecycle timestamps use Unix milliseconds; older imported rows may use ISO dates.
// Interpret only for display; keep the original organization value untouched.
function trashTimeLabel(value: string) {
  return recordingTimeLabel(/^\d+$/.test(value) ? Number(value) : value);
}

export type CompanionProductSettingsPatch = {
  autoLocalCardTranscription?: boolean;
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
  format: 'markdown' | 'docx' | 'mindmap' | 'pdf' | 'txt' | 'json' | 'srt' | 'xlsx' | 'pptx' | 'png' | 'bundle' | 'todo' | 'todotxt' | 'ics' | 'calendar' | 'calendarreminder' | 'calendarreminder30' | 'calendarreminder60';
  pdfSections?: {minutes:boolean;transcript:boolean;highlights:boolean;timeline:boolean};
  contentSections?: import('./ContentExportPanel').ContentSelection;
  expectedContentHash?:string;
  calendarReminders?:CalendarReminderChoice['calendarReminders'];
  calendarSlots?:CalendarReminderChoice['calendarSlots'];
  calendarSaveToken?:string;
  calendarSavedName?:boolean;
};

export type CompanionMeetingSaveRequest = {
  sessionId: string;
  title?: string;
  expectedTitle?: string;
  meetingMode?: CompanionV1MeetingMode;
  markdown?: string;
  expectedMarkdown?: string;
  restoreHistory?: {index: number; archivedAt: string};
  createManual?: {
    expectedTranscriptText: string;
    expectedReviewRevision: number | null;
    expectedNoteRevision: number;
  };
  transcriptReview?: CompanionTranscriptReviewEdit;
};

export interface CompanionDashboardProps {
  renderAudioEditor?:(props:import('./AudioDerivationEditor').AudioEditHostProps)=>ReactNode;
  audioEditNotice?:ReactNode;
  renderIncomingFiles?:(onOpen:(id:string)=>void)=>ReactNode;
  documentAdapter?:(sessionId:string)=>import('../../document-context/src/storageTypes').DocumentContextAdapter;
  readingPreview?:boolean;
  onAskMeetings?: (question:string,sessionIds:string[],jobId:string,resume?:import('@companion-type/core').MeetingQaResumeRequest) => Promise<import('@companion-type/core').MeetingQaResult>;
  onCancelMeetingQuestion?: (jobId:string) => Promise<boolean>;
  onReadLicenses?: () => Promise<string>;
  settingsFooter?: ReactNode;
  deviceExtra?: ReactNode;
  petPanel?: ReactNode;
  onFindPet?: (request:PetFindRequest)=>Promise<PetFindReport>;
  recordingSync?: import('./CompanionRecordingSync').RecordingSyncStatus | null;
  pauseSyncBusy?: boolean;
  onPauseSync?: (jobId: string) => void;
  onRepairSync?: () => Promise<void>;
  processingSessionId?: string | null;
  cancelProcessingPending?: boolean;
  processingNotice?: string | null;
  onCancelMeetingProcessing?: (sessionId: string) => void;
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
  onOpenSavedCalendar?: OpenSavedCalendar;
  onExportMeeting?: (request: CompanionMeetingExportRequest) => Promise<{ path: string; bytes: number; warning?: string | null; calendarOpenToken?:string;calendarFileUri?:string } | null>;
  onPreviewMeetingExport?:(request:CompanionMeetingExportRequest)=>Promise<{contentHash:string;warning?:string|null;textContent?:string|null;calendarItems?:CalendarExportItem[]|null}>;
  onCopyMeetingContent?:(request:CompanionMeetingExportRequest)=>Promise<{status:string}>;
  onShareMeetingContent?:(request:CompanionMeetingExportRequest,destination?:ShareDestination)=>Promise<ShareHandoffResult>;
  onPreviewDiagnostics?:()=>Promise<unknown>;
  onExportDiagnostics?: (includeDevice: boolean) => Promise<{path:string;bytes:number;warning?:string|null}|null>;
  onPrepareAudioComponents?: () => Promise<void>;
  onPrepareLocalAsr?: () => Promise<void>;
  onCheckService?: (service: 'asr' | 'minutes') => Promise<{ service: 'asr' | 'minutes'; status: string; message: string; elapsedMs: number; checkedAtUnixMs: number }>;
  /** Returns a short-lived, session-bound desktop asset URL. Raw paths are never placed in the browser. */
  onPrepareAudio?: (sessionId: string) => Promise<{ sessionId: string; url: string; sourceIdentity?: string; pauseTimeline?: CompanionPauseTimeline | null; parts?:RecordingPart[]; meetingTracks?: MeetingPlaybackTracks }>;
  onExportAudio?: (sessionId: string,format?:'original'|'mp3') => Promise<{ path: string; bytes: number } | null>;
  onShareAudio?: (sessionId:string,format?:'original'|'mp3',destination?:ShareDestination)=>Promise<ShareHandoffResult>;
  onImportAudio?: () => Promise<CompanionV1Snapshot | null>;
  onCancelImportAudio?: () => Promise<boolean>;
  /** Native host obtains a concrete device proposal and its confirmation dialog. */
  onDiscardOldestRecording?: (requiredSeconds: number) => Promise<{
    status: 'deleted' | 'cancelled' | 'noCandidate'; message: string;
  }>;
  deviceRecordingActions?:DeviceRecordingActions;
  /** Conflict-aware metadata/minutes edit. The host persists before returning its next snapshot. */
  onSaveMeeting?: (request: CompanionMeetingSaveRequest) => Promise<CompanionV1Snapshot>;
  onRefineSpeakers?: (sessionId:string) => Promise<CompanionV1Snapshot>;
  onPreviewRetranscription?: (sessionId:string) => Promise<{text:string;unrecognized:{startMs:number;endMs:number;source?:string|null}[]}>;
  onPreviewGap?: (sessionId:string,range:{startMs:number;endMs:number}) => Promise<{text:string;unrecognized:{startMs:number;endMs:number;source?:string|null}[]}>;
  onSaveBookmark?: (request:CompanionBookmarkRequest) => Promise<CompanionV1Snapshot>;
  onAddImageNote?:(request:import('@companion-type/core').CompanionMeetingImageNoteRequest)=>Promise<CompanionV1Snapshot|null>;
  onPreviewNoteImage?:(sessionId:string,noteId:string)=>Promise<string>;
  onCheckNoteEvidence?:(sessionId:string,noteId:string,referenceId:string,revision:number)=>Promise<void>;
  onSaveNote?: (request:CompanionMeetingNoteRequest) => Promise<CompanionV1Snapshot>;
  onSaveLibraryOrganization?:(request:CompanionLibraryOrganizationRequest)=>Promise<CompanionV1Snapshot>;
  onExportLibrary?:(request:CompanionLibraryExportRequest)=>Promise<CompanionLibraryExportResult|null>;
  onBackupLibrary?:(draft?:{name:string;instructions:string})=>Promise<{path:string;sessions:number;files:number;bytes:number;templateWarning?:string}|null>;
  onRestoreLibrary?:()=>Promise<CompanionV1Snapshot|null>;
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
  const labels: Record<string, string> = { Summary: '摘要', Decisions: '讨论结论（需核对）', 'Action Items': '待办', Questions: '会中问题', 'Open Questions': '待确认问题', Keywords: '关键词' };
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

// Project only the exact native diagnostic header. Every body section,
// including unknown provider sections, remains editable without exposing the
// generated transport metadata. Preserve all other sections/header bytes.
function basicMinutesFields(markdown: string, noteContext?: CompanionMinutesNoteContext | null, manual=false): Array<{ key: string; label: string; value: string; start: number; end: number; plain: boolean }> | null {
  const labels: Record<string, string> = { Summary: '摘要', Decisions: '决定', 'Action Items': '待办', Questions: '会中问题', 'Open Questions': '待确认问题', Keywords: '关键词' };
  const envelope = noteContext ? minutesSourceEnvelope(noteContext) : '';
  if (!markdown.startsWith(envelope)) return null;
  const template = /^> 整理视角：[^\r\n]+\r?\n\r?\n/.exec(markdown.slice(envelope.length))?.[0] ?? '';
  const offset = envelope.length + template.length;
  const headings = [...markdown.slice(offset).matchAll(/^## ([^\r\n]+)\r?$/gm)].map(match=>({
    key:match[1], index:offset+match.index!, contentStart:offset+match.index!+match[0].length,
  }));
  if (!headings.length) return null;
  const prefix = markdown.slice(offset, headings[0].index);
  if (!(manual && prefix==='' && headings.some(heading=>heading.key==='Action Items')) && !/^# [^\r\n]+\r?\n\r?\nGenerated: [^\r\n]+\r?\nDuration: [^\r\n]+\r?\nSource: [^\r\n]+\r?\nMinutes engine: (?:rules_l0 \(draft\)|llm_deepseek \(final\))\r?\n\r?\n$/.test(prefix)) return null;
  return headings.map((match, index) => {
    const start = match.contentStart;
    const end = headings[index + 1]?.index ?? markdown.length;
    const raw = markdown.slice(start, end).trim();
    const known = Object.hasOwn(labels,match.key);
    const plain = !known || match.key === 'Keywords';
    const value = known && /^(?:- )?None captured$/.test(raw) ? ''
      : plain ? raw : raw.split(/\r?\n/).map(line=>line.replace(/^- /,'')).join('\n');
    return { key:match.key, label:labels[match.key]??match.key, value, start, end, plain };
  });
}

function MinutesContentEditor({ markdown, onChange, disabled, label, noteContext, manual=false, onCalendarPending, calendarRequestKey, calendarLineIndex, calendarRequestTimed, calendarOnly=false, calendarAll=false, sourceSegments, recordingTime }: {
  markdown: string; onChange: (value: string) => void; disabled: boolean; label: string; noteContext?: CompanionMinutesNoteContext | null; manual?: boolean;onCalendarPending?:(delta:1|-1)=>void;calendarRequestKey?:string;calendarLineIndex?:number;calendarRequestTimed?:boolean;calendarOnly?:boolean;calendarAll?:boolean;sourceSegments?:readonly CompanionTranscriptSource[];recordingTime?:string;
}) {
  const fields = basicMinutesFields(markdown, noteContext, manual);
  if (!fields&&calendarOnly)return <p className="ct-step-warn">清单结构已变化，请取消后重新选择事项；旧输入仍保留。</p>;
  if (!fields) return <textarea value={markdown} onChange={event => onChange(event.target.value)}
    aria-label={label} spellCheck={false} disabled={disabled} />;
  const primary = fields.some(item=>item.key==='Action Items') ? fields.filter(item=>item.key==='Action Items')
    : fields.some(item=>item.key==='Summary') ? fields.filter(item=>item.key==='Summary') : fields.slice(0,1);
  const secondary = fields.filter(item=>!primary.includes(item));
  const requestedOffset=calendarLineIndex===undefined?undefined:markdown.split('\n').slice(0,calendarLineIndex).reduce((count,line)=>count+line.length+1,0);
  const calendarTarget=requestedOffset===undefined?fields.find(item=>item.key==='Action Items'&&item.value.split(/\r?\n/).some(line=>line.trim()&&!/^\s*\[[xX]\]\s/.test(line)))
    :fields.find(item=>item.key==='Action Items'&&item.start<=requestedOffset&&requestedOffset<item.end);
  const requestedRow=requestedOffset!==undefined&&calendarTarget?markdown.slice(calendarTarget.start,requestedOffset).trimStart().split(/\r?\n/).length-1:undefined;
  const field = (item: typeof fields[number]) => <div key={`${item.key}-${fields.indexOf(item)}`} className="ct-basic-minutes-field">
    {!calendarOnly?<span>{item.label}{item.key === 'Action Items' ? '（分别修改）' : ''}</span>:null}
    {item.key==='Action Items'?<ActionListEditor sourceSegments={sourceSegments} recordingTime={recordingTime} calendarOnly={calendarOnly} calendarAll={calendarAll} calendarRequestRow={item===calendarTarget?requestedRow:undefined} calendarRequestTimed={calendarRequestTimed} calendarRequestKey={item===calendarTarget?calendarRequestKey:undefined} onCalendarPending={onCalendarPending} value={item.value} disabled={disabled} onChange={value=>{
      const newline=markdown.includes('\r\n')?'\r\n':'\n';
      const body=value.split(/\r?\n/).map(line=>line.trim()?`- ${line}`:line).join(newline);
      onChange(markdown.slice(0,item.start)+newline+body+newline+newline+markdown.slice(item.end));
    }}/>:<textarea aria-label={`编辑${item.label}`} aria-describedby={item.key === 'Action Items' ? 'ct-minutes-action-help' : undefined}
      value={item.value} spellCheck={false}
      disabled={disabled} placeholder={item.key === 'Action Items' ? '一行一件事，填写你确认的待办' : '暂无内容，可自行补充'}
      onChange={event => {
        const newline = markdown.includes('\r\n') ? '\r\n' : '\n';
        const lines = event.target.value.split(/\r?\n/);
        const body = item.plain ? event.target.value : lines.map(line => !line.trim() ? line : `- ${line}`).join(newline);
        onChange(markdown.slice(0, item.start) + newline + body + newline + newline + markdown.slice(item.end));
      }} />}
    {!calendarOnly&&item.key === 'Action Items' ? <small id="ct-minutes-action-help" className="ct-action-item-help">
      已填写 {item.value.split(/\r?\n/).filter(line => line.trim()).length} 项。修改内容时，已注明的时间和负责人会单独保留。
    </small> : null}
  </div>;
  if(calendarOnly)return <div className="ct-basic-minutes-editor ct-single-calendar-edit">{calendarAll?fields.filter(item=>item.key==='Action Items').map(field):calendarTarget?field(calendarTarget):<p role="alert">找不到所选事项，请取消后重新选择。</p>}<p className="ct-step-meta">{calendarAll?'这里只修改各项截止时间，事项原文、摘要和负责人保留。':'这里只修改所选事项的截止时间。'}确认后请保存，或取消返回原预览。</p></div>;
  return <div className="ct-basic-minutes-editor">
    {primary.map(field)}
    {secondary.length?<details><summary>更多整理内容</summary>
      {secondary.map(field)}
    </details>:null}
    {manual?<><p className="ct-step-meta">保存只保留本机清单，填写时间也不会自动创建日历或提醒。</p><details className="ct-manual-save-help"><summary>保存与提醒说明</summary><p className="ct-step-meta">自己填写的清单仅保存在本机，原话和补充仍保留；不会自动提取或创建提醒。</p></details></>
      :<p className="ct-step-meta">只修改整理结果，原录音文字和补充备注仍分别保留。</p>}
  </div>;
}

export function CompanionDashboard({
  readingPreview=false,
  onReadLicenses,
  settingsFooter,
  deviceExtra,
  petPanel,
  onFindPet,
  recordingSync = null,
  pauseSyncBusy = false,
  onPauseSync,
  onRepairSync,
  processingSessionId = null,
  cancelProcessingPending = false,
  processingNotice = null,
  onCancelMeetingProcessing,
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
  onExportMeeting, onOpenSavedCalendar, onCopyMeetingContent, onShareMeetingContent,
  onPreviewMeetingExport,
  onExportDiagnostics,
  onPreviewDiagnostics,
  onAskMeetings,
  onCancelMeetingQuestion,
  onPrepareAudioComponents,
  onPrepareLocalAsr,
  onCheckService,
  onPrepareAudio,
  onExportAudio, onShareAudio,
  onImportAudio,
  onCancelImportAudio,
  onDiscardOldestRecording,
  deviceRecordingActions,
  onSaveMeeting,
  onRefineSpeakers,
  onPreviewRetranscription,
  onPreviewGap,
  onSaveBookmark,
  onSaveNote,onCheckNoteEvidence,
  onAddImageNote,
  onPreviewNoteImage,
  documentAdapter,renderAudioEditor,audioEditNotice,renderIncomingFiles,
  onSaveLibraryOrganization,
  onExportLibrary,
  onBackupLibrary,
  onRestoreLibrary,
  onSaveLibraryLifecycle,
  onPurgeLibrary,
  onValidateOtaPackage,
  onTransferOtaPackage,
}: CompanionDashboardProps) {
  const [desktopTheme, setDesktopTheme] = useState<'light'|'dark'>(() => {
    if (surface !== 'windows' || typeof window === 'undefined') return 'light';
    try {
      const saved = window.localStorage.getItem('companion.desktop.theme.v1');
      if (saved === 'light' || saved === 'dark') return saved;
      return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } catch { return 'light'; }
  });
  const toggleDesktopTheme = () => {
    const next = desktopTheme === 'dark' ? 'light' : 'dark';
    setDesktopTheme(next);
    try { window.localStorage.setItem('companion.desktop.theme.v1', next); } catch { /* Theme still applies for this session. */ }
  };
  const [draftName, setDraftName] = useState('companion');
  const [draftTitle, setDraftTitle] = useState('设备会议');
  const [newMeetingTitle, setNewMeetingTitle] = useState('');
  const [draftMinutes, setDraftMinutes] = useState('30');
  const [transcriptDraft, setTranscriptDraft] = useState('');
  const [retranscriptionPreview, setRetranscriptionPreview] = useState<{sessionId:string;text:string;unrecognized:{startMs:number;endMs:number;source?:string|null}[];sourceText:string;sourceUtterances:CompanionV1HostSession['utterances'];revision:number}|null>(null);
  const [gapPreview,setGapPreview]=useState<{sessionId:string;startMs:number;endMs:number;text:string;partial:boolean;sourceText:string;sourceReview:string}|null>(null);
  const [gapMessage,setGapMessage]=useState<{sessionId:string;text:string}|null>(null);
  const [gapSaving,setGapSaving]=useState(false);
  const transcriptEditor = useRef<{ sessionId?: string; dirty: boolean }>({ dirty: false });
  const [pendingDelete, setPendingDelete] = useState<{ request: CompanionV1ControlRequest; title: string; detail: string; targetTitle: string; selectedId: string | null; libraryKey: string } | null>(null);
  const deleteSubmitted = useRef(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [settingsReturn, setSettingsReturn] = useState<'recording' | 'device' | null>(null);
  const [showWorkflow, setShowWorkflow] = useState(false);
  const [pageView, setPageView] = useState<'library' | 'device' | 'settings' | 'pet'>('library');
  const pageHeading = useRef<HTMLHeadingElement>(null);
  const navigationEpoch = useRef(0);
  const [helpOpen,setHelpOpen]=useState(false);
  const helpTrigger=useRef<HTMLButtonElement>(null);
  const helpReturnFocus=useRef<HTMLElement|null>(null);
  const openQuickGuide=(event?:{currentTarget:HTMLElement})=>{
    helpReturnFocus.current=event?.currentTarget??(document.activeElement instanceof HTMLElement?document.activeElement:null);
    setHelpOpen(true);window.setTimeout(()=>document.getElementById('ct-use-help')?.scrollIntoView({block:'start'}),0);
  };
  const closeQuickGuide=()=>{setHelpOpen(false);const target=helpReturnFocus.current?.isConnected?helpReturnFocus.current:helpTrigger.current;
    window.requestAnimationFrame(()=>{if(target?.isConnected){target.scrollIntoView({block:'center'});target.focus({preventScroll:true});}});
  };
  const [onlyPendingSessions, setOnlyPendingSessions] = useState(false);
  const [libraryQuery, setLibraryQuery] = useState('');
  const [libraryWindow, setLibraryWindow] = useState({ scope: '', count: 50 });
  const [libraryFilters,setLibraryFilters]=useState<LibraryFilters>({folder:'*',tag:'',favorites:false});
  const [librarySelection,setLibrarySelection]=useState<Record<string,number>>({});
  const [libraryBusy,setLibraryBusy]=useState(false);
  const [libraryCurrentMessage,setLibraryCurrentMessage]=useState('');
  const [importingAudio,setImportingAudio]=useState(false);
  const [importAudioMessage,setImportAudioMessage]=useState('');
  const [recordingAlternativesOpen,setRecordingAlternativesOpen]=useState(false);
  const [libraryUnsaved,setLibraryUnsaved]=useState(false);
  const [openSavedRecordingId, setOpenSavedRecordingId] = useState<string | null>(null);
  const [openSavedRecordingTarget, setOpenSavedRecordingTarget] = useState<'source'|'result'|null>(null);
  const [syncDetailsOpen, setSyncDetailsOpen] = useState(false);
  const savedRecordingWorkspace = useRef<HTMLElement | null>(null);
  const recordingOpener = useRef<HTMLButtonElement | null>(null);
  const recordingLibraryRegion = useRef<HTMLElement | null>(null);
  const [detailSessionId,setDetailSessionId]=useState<string|null>(null);
  const [recordingResultOpen, setRecordingResultOpen] = useState(true);
  const [recordingToolsOpen, setRecordingToolsOpen] = useState(false);
  const [transcriptReviewOpen, setTranscriptReviewOpen] = useState(false);
  const [transcriptCleanView,setTranscriptCleanView]=useState(true);
  const [libraryToolsOpen, setLibraryToolsOpen] = useState(false);
  const [libraryPanel,setLibraryPanel]=useState<'filter'|'manage'|null>(null);
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
  const previewTask=useRef<{cancel:()=>void}|null>(null);
  const [previewWaiting,setPreviewWaiting]=useState(false);
  useEffect(()=>()=>previewTask.current?.cancel(),[]);
  const [calendarExportReview,setCalendarExportReview]=useState<{sessionId:string;mode:CompanionV1MeetingMode;contentHash:string;origin:MeetingExportOrigin;format:'ics'|'calendar';warning:string;sourceKey:string;reminderCarryover?:{fileName:string;retained:number};reminderSourceNote?:string;calendarReminders?:CalendarReminderChoice['calendarReminders'];calendarSlots?:CalendarReminderChoice['calendarSlots'];suggestedAbsolute?:{uid:string;at:string};items?:CalendarExportItem[];reminderContentHash?:string;remindAtTime?:boolean;reminderFormat?:'calendarreminder'|'calendarreminder30'|'calendarreminder60';reminderHashes?:Partial<Record<'calendarreminder'|'calendarreminder30'|'calendarreminder60',string>>}|null>(null);
  const [noteExportTarget,setNoteExportTarget]=useState<ContentExportTarget|null>(null);
  const [manualEvidence,setManualEvidence]=useState<ManualEvidenceDraft|undefined>();
  const [documentSource,setDocumentSource]=useState<DocumentSourceRequest|undefined>();
  const [qaQuestion,setQaQuestion]=useState('');
  const [qaSelected,setQaSelected]=useState<string[]>([]);
  const [qaBusy,setQaBusy]=useState(false);
  const [qaJobId,setQaJobId]=useState<string|null>(null);
  const [qaCancelling,setQaCancelling]=useState(false);
  const [qaAsked,setQaAsked]=useState('');
  const [qaSaveBusy,setQaSaveBusy]=useState(false);
  const [qaSaveMessage,setQaSaveMessage]=useState<string|null>(null);
  const [qaRemovedNotice,setQaRemovedNotice]=useState(false);
  const [qaResult,setQaResult]=useState<import('@companion-type/core').MeetingQaResult|null>(null);
  const [qaError,setQaError]=useState<string|null>(null);
  const [qaSourceSnapshot,setQaSourceSnapshot]=useState<{ids:string[];identity:string}|null>(null);
  const [qaPendingCitation,setQaPendingCitation]=useState<import('@companion-type/core').MeetingQaCitation|null>(null);
  const [organizationChoiceId,setOrganizationChoiceId]=useState<string|null>(null);
  const [pendingMinutesTemplate,setPendingMinutesTemplate]=useState<CompanionV1ControlRequest['minutesTemplate']>();
  const [templateId,setTemplateId]=useState<'meeting'|'interview'|'lecture'|'custom'>('meeting');
  const [templateSaveError,setTemplateSaveError]=useState(false);
  const [customTemplate,setCustomTemplate]=useState<{name:string;instructions:string}>(()=>{
    try {const saved=JSON.parse(localStorage.getItem('companion.minutes.customTemplate.v1')||'null');
      return {name:typeof saved?.name==='string'?saved.name:'',instructions:typeof saved?.instructions==='string'?saved.instructions:''};
    } catch {return {name:'',instructions:''};}
  });
  const updateCustomTemplate=(next:{name:string;instructions:string})=>{
    setCustomTemplate(next);
    try {localStorage.setItem('companion.minutes.customTemplate.v1',JSON.stringify(next));setTemplateSaveError(false);}
    catch {setTemplateSaveError(true);}
  };
  const [calendarSaveTargets,setCalendarSaveTargets]=useState<Record<string,{token:string;name:string}>>({});
  const [audioExportFormat,setAudioExportFormat]=useState<'original'|'mp3'>('original');
  const [pdfSections]=useState({minutes:true,transcript:false,highlights:true,timeline:false});
  const [pdfPreview,setPdfPreview]=useState<{key:string;text?:string;hash?:string;error?:string;pending?:boolean}|null>(null);
  const [exportResult, setExportResult] = useState<{ sessionId: string; message: string; path?: string; calendarOpenToken?:string;calendarFileUri?:string; format?: CompanionMeetingExportRequest['format']; kind?: 'saved' | 'opened' | 'cancelled' | 'pending' | 'error'; hasWarning?:boolean; origin: MeetingExportOrigin } | null>(null);
  const [meetingDrafts, setMeetingDrafts] = useState<Record<string, {
    title?: { value: string; expected: string };
    minutes?: Partial<Record<CompanionV1MeetingMode, { value: string; expected: string; createManual?: CompanionMeetingSaveRequest['createManual'];calendarContext?:CompanionMinutesNoteContext|null }>>;
  }>>({});
  const [editingMinutes, setEditingMinutes] = useState(false);
  const savedMinutesHeading=useRef<HTMLDetailsElement|null>(null);
  const [savedMinutesReveal,setSavedMinutesReveal]=useState<{sessionId:string;mode:CompanionV1MeetingMode}|null>(null);
  const [calendarEditRequest,setCalendarEditRequest]=useState<string|null>(null);
  const [calendarEditLine,setCalendarEditLine]=useState<number|undefined>();
  const [calendarEditAll,setCalendarEditAll]=useState(false);
  const [calendarEditTimed,setCalendarEditTimed]=useState(false);
  const [calendarReturn,setCalendarReturn]=useState<(CalendarReminderChoice&{sessionId:string;mode:CompanionV1MeetingMode;origin:MeetingExportOrigin;expectedMarkdown?:string;fromPreview?:boolean;singleDeadlineChange?:{index:number;before:CalendarExportItem[]}})|null>(null);
  const calendarEditSequence=useRef(0);
  useEffect(()=>{if(!editingMinutes)setCalendarEditRequest(null);},[editingMinutes]);
  const [calendarPendingCount,setCalendarPendingCount]=useState(0);
  const [calendarReminderPending,setCalendarReminderPending]=useState(0);
  const [calendarReminderRetry,setCalendarReminderRetry]=useState(0);
  const [calendarReminderPreview,setCalendarReminderPreview]=useState<{key:string;hash?:string;warning?:string;error?:string}|null>(null);
  const [saveMeetingBusy, setSaveMeetingBusy] = useState(false);
  const actionSaveActive=useRef(false);
  const [bookmarkBusy,setBookmarkBusy]=useState(false);
  const [bookmarkUnsaved,setBookmarkUnsaved]=useState(false);
  const [referenceView,setReferenceView]=useState<ReferenceView>('notes');
  const [meetingPane,setMeetingPane]=useState<MeetingPane>('result');
  const [noteBusy,setNoteBusy]=useState(false);
  const [noteUnsaved,setNoteUnsaved]=useState(false);
  const [audioEditUnsaved,setAudioEditUnsaved]=useState(false);
  const [editSourceSeek,setEditSourceSeek]=useState<{id:string;positionMs:number}|null>(null);
  const [saveMeetingResult, setSaveMeetingResult] = useState<{ sessionId: string; part?: 'title' | 'minutes'; message: string; kind: 'saved' | 'error' } | null>(null);
  const [audioBusy, setAudioBusy] = useState(false);
  const [audioSources, setAudioSources] = useState<Record<string, { url: string; identity: string; sourceIdentity?: string; pauseTimeline?: CompanionPauseTimeline | null; parts?:RecordingPart[]; meetingTracks?: MeetingPlaybackTracks }>>({});
  const [audioResult, setAudioResult] = useState<{ sessionId: string; message: string; playbackFailure?: boolean } | null>(null);
  const audioElement = useRef<HTMLAudioElement | null>(null);
  const meetingAudioControl = useRef<MeetingAudioControl | null>(null);
  const segmentedAudio = useRef<SegmentedPlaybackControl|null>(null);
  const audioRequestId = useRef(0);
  const [listeningEpoch,setListeningEpoch]=useState(0);
  const [formAsrProvider, setFormAsrProvider] = useState('local-paraformer');
  const [formAutoLocalCard,setFormAutoLocalCard]=useState(true);
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
    setFormAsrProvider(productSettings.asrProvider || 'local-paraformer');
    setFormAutoLocalCard(productSettings.autoLocalCardTranscription ?? true);
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
  }, [productSettings?.asrProvider, productSettings?.autoLocalCardTranscription, productSettings?.volcResourceId,
    productSettings?.openaiAsrEndpoint, productSettings?.openaiAsrModel,
    productSettings?.deepseekBaseUrl, productSettings?.deepseekModel,
    productSettings?.deepseekMinutesEnabled, productSettings?.bleCompress,
    productSettings?.defaultMeetingMode, Boolean(productSettings?.storageSaveBlocked)]);

  const [transcriptReviewUnsaved, setTranscriptReviewUnsaved] = useState(false);
  const [transcriptDraftSessions, setTranscriptDraftSessions] = useState<string[]>([]);
  const selectedSession = useMemo(
    () => {const row=snapshot?selectedCompanionHostSession(snapshot):null;return row&&!row.organization?.trashedAt&&!libraryFilters.trash?row:null;},
    [snapshot,libraryFilters.trash],
  );
  useEffect(()=>{
    setReferenceView('notes');setManualEvidence(undefined);setRecordingResultOpen(true);
    const savedMinutes=[selectedSession?.minutes,selectedSession?.minutesByMode?.offlineStore,selectedSession?.minutesByMode?.onlineLive].some(value=>Boolean(value?.markdown?.trim()));
    setMeetingPane(selectedSession&&!savedMinutes?'source':'result');
  },[selectedSession?.id]);
  const savedDetailOpen=Boolean(selectedSession&&detailSessionId===selectedSession.id);
  const notebookInitialSelection=useRef(false);
  useEffect(()=>{
    if(surface!=='windows'||!selectedSession||notebookInitialSelection.current)return;
    notebookInitialSelection.current=true;
    if(window.matchMedia('(min-width:901px)').matches)setDetailSessionId(selectedSession.id);
  },[selectedSession?.id,surface]);
  const qaDefaulted=useRef(false);
  useEffect(()=>{if(selectedSession&&!qaDefaulted.current&&companionSessionHasFinalTranscript(selectedSession)){qaDefaulted.current=true;setQaSelected([selectedSession.id]);}},[selectedSession?.id,selectedSession?.transcriptFinal]);
  const device = snapshot?.device;
  const controlledRecorder = snapshot?.host.sessions.find((row) => row.recorderControl
    && (row.status === 'recording' || row.recorderControlUncertain)) ?? null;
  const activeRecorders = snapshot?.host.sessions.filter((row) => row.status === 'recording') ?? [];
  const activeHostCaptureError = activeRecorders.find((row) => row.id === snapshot?.host.activeSessionId
    && row.source === 'hostMicrophone')?.recovery?.lastError;
  const originalSyncRecorder = activeRecorders.length === 1
    && activeRecorders[0].source === 'boardDevice' && activeRecorders[0].deviceRecordingKey
    && activeRecorders[0].deviceRecordingId && activeRecorders[0].sourceDeviceId
    && (!device?.deviceId || device.deviceId.replace(/[:-]/g, '').toLowerCase()
      === activeRecorders[0].sourceDeviceId.replace(/[:-]/g, '').toLowerCase())
    ? activeRecorders[0] : null;
  const pausedSyncRecorder = originalSyncRecorder && (recordingSync?.phase === 'blocked'
    || Boolean(recordingSync?.deviceId && recordingSync.deviceId.replace(/[:-]/g, '').toLowerCase()
      === originalSyncRecorder.sourceDeviceId!.replace(/[:-]/g, '').toLowerCase())) ? originalSyncRecorder : null;
  const privacy = snapshot?.privacy;
  const allLibrarySessions = snapshot?.host.sessions ?? [];
  useEffect(()=>{
    if(snapshot && gapPreview && !allLibrarySessions.some(row=>row.id===gapPreview.sessionId&&!row.organization?.trashedAt)) {
      setGapPreview(null);setGapMessage(null);
    }
  },[snapshot,gapPreview?.sessionId]);
  const qaEligibleSessions=allLibrarySessions.filter(row=>!row.organization?.trashedAt&&companionSessionHasFinalTranscript(row));
  const qaSelectedEligible=qaSelected.filter(id=>qaEligibleSessions.some(row=>row.id===id));
  const qaSessionsRef=useRef(allLibrarySessions);qaSessionsRef.current=allLibrarySessions;
  const documentScopes=selectedSession&&!selectedSession.organization?.trashedAt?(selectedSession.documentContext?.rows??[]).filter(row=>row.extraction).map(row=>({id:'document:'+selectedSession.id+':'+row.id,title:'补充材料 · '+row.name,kind:'supplement' as const,binding:row.extraction!.sha256})):[];
  const qaIdentity=(ids:string[])=>JSON.stringify(ids.map(id=>{if(id.startsWith('document:'))return documentScopes.find(s=>s.id===id)??null;const row=allLibrarySessions.find(session=>session.id===id);
    return row?[row.id,row.title,row.transcriptText,row.transcriptReview,row.utterances,row.organization?.trashedAt]:null;}));
  const qaStale=Boolean(qaSourceSnapshot&&qaSourceSnapshot.identity!==qaIdentity(qaSourceSnapshot.ids));
  const qaSourceRemoved=Boolean(qaSourceSnapshot&&qaSourceSnapshot.ids.some(id=>!qaEligibleSessions.some(row=>row.id===id)));
  const canResumeQa=Boolean(qaResult?.incomplete && qaResult.resume && qaSourceSnapshot && !qaStale && !qaSourceRemoved
    && qaQuestion.trim()===qaAsked && qaSelectedEligible.length===qaSourceSnapshot.ids.length
    && qaSelectedEligible.every((id,index)=>id===qaSourceSnapshot.ids[index]));
  const askSelectedMeetings=async(resumeExisting:boolean)=>{
    if(!onAskMeetings || (resumeExisting&&!canResumeQa))return;
    const ids=[...qaSelectedEligible],identity=qaIdentity(ids),question=qaQuestion.trim(),jobId=crypto.randomUUID();
    const resume=resumeExisting&&qaResult?.resume?{...qaResult.resume,items:qaResult.items}:undefined;
    setQaJobId(jobId);setQaCancelling(false);setQaAsked(question);setQaSaveMessage(null);setQaRemovedNotice(false);
    setQaBusy(true);setQaError(null);if(!resume&&!canResumeQa)setQaResult(null);setQaSourceSnapshot({ids,identity});
    try{const result=await onAskMeetings(question,ids,jobId,resume);if(ids.every(id=>qaSessionsRef.current.some(row=>row.id===id&&!row.organization?.trashedAt&&companionSessionHasFinalTranscript(row))))setQaResult(result);}
    catch(error){setQaError(operationErrorText(error,'general'));}finally{setQaBusy(false);setQaJobId(null);setQaCancelling(false);}
  };
  useEffect(()=>{if(qaSourceRemoved){setQaResult(null);setQaSaveMessage(null);setQaSourceSnapshot(null);setQaRemovedNotice(true);}},[qaSourceRemoved]);
  const savedCustomTemplates=useMemo(()=>{
    const fromMeetings=savedCustomMinutesTemplates(allLibrarySessions);
    let restored:typeof fromMeetings=[];
    try {restored=readRestoredCustomTemplates(localStorage);} catch { /* Existing meeting templates remain usable. */ }
    const seen=new Set<string>();return [...fromMeetings,...restored].filter(item=>{const key=JSON.stringify([item.name,item.instructions]);
      if(seen.has(key))return false;seen.add(key);return true;});
  },[allLibrarySessions]);
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
  const latestResult=useMemo(()=>latestSavedResult(allLibrarySessions),[allLibrarySessions]);
  const recentSavedResult=latestResult&&(!recentSavedRecording||!Number.isFinite(Date.parse(recentSavedRecording.startedAt??''))||Date.parse(latestResult.at)>=Date.parse(recentSavedRecording.startedAt??''))?latestResult:null;
  const recordingLibrary = useMemo(() => allLibrarySessions.filter(s=>Boolean(s.organization?.trashedAt)===Boolean(libraryFilters.trash)), [allLibrarySessions, libraryFilters.trash]);
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
  const pendingLibrary = useMemo(() => recordingLibrary.filter((session) => !meetingHasFinalMinutes(session)
    || Boolean(describeCompanionMeetingRecovery(session))), [recordingLibrary]);
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
  // Search and bulk tools retain every matching recording; only card rendering is bounded.
  // A different query/filter starts at 50 immediately, while cache refresh retains this view.
  const clearLibraryFilters=()=>setLibraryFilters({folder:'*',tag:'',favorites:false,trash:libraryFilters.trash});
  const libraryActiveChips:LibraryScopeChip[]=[];
  if(libraryFilters.folder!=='*')libraryActiveChips.push({id:'folder',label:`文件夹：${libraryFilters.folder||'未分类'}`,removeLabel:'取消文件夹筛选',onRemove:()=>setLibraryFilters({...libraryFilters,folder:'*'})});
  if(libraryFilters.tag)libraryActiveChips.push({id:'tag',label:`标签：${libraryFilters.tag}`,removeLabel:'取消标签筛选',onRemove:()=>setLibraryFilters({...libraryFilters,tag:''})});
  if(libraryFilters.from||libraryFilters.to)libraryActiveChips.push({id:'dates',label:`日期：${libraryFilters.from||'不限'} — ${libraryFilters.to||'不限'}`,removeLabel:'取消日期筛选',onRemove:()=>setLibraryFilters({...libraryFilters,from:undefined,to:undefined})});
  if(libraryFilters.favorites)libraryActiveChips.push({id:'favorites',label:'只看收藏',removeLabel:'取消收藏筛选',onRemove:()=>setLibraryFilters({...libraryFilters,favorites:false})});
  const chooseLibraryRecordings=()=>{setLibraryPanel(null);setLibraryToolsOpen(true);window.requestAnimationFrame(()=>{const first=recordingLibraryRegion.current?.querySelector<HTMLInputElement>('.ct-library-list .ct-library-entry>input');(first??recordingLibraryRegion.current)?.focus();});};
  const cancelLibrarySelection=()=>{setLibrarySelection({});setLibraryToolsOpen(false);};
  const libraryWindowScope = JSON.stringify([onlyPendingSessions, libraryQuery.trim().toLocaleLowerCase(), libraryFilters]);
  if (libraryWindow.scope !== libraryWindowScope) {
    setLibraryWindow({ scope: libraryWindowScope, count: 50 });
  }
  const libraryVisibleCount = libraryWindow.scope === libraryWindowScope ? libraryWindow.count : 50;
  const renderedLibrary = visibleLibrary.slice(0, libraryVisibleCount);
  const connected = Boolean(snapshot?.connected || device?.connected);
  // A cached report cannot establish a live connection for the Windows recording entry.
  const devicePageConnected = connected && (surface !== 'windows' || (snapshot?.source !== 'lastKnown' && snapshot?.source !== 'unavailable'));
  const connection=deviceConnectionStatus(snapshot,busyAction);

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

  useEffect(()=>{
    if (!savedDetailOpen || pageView !== 'library') return;
    savedRecordingWorkspace.current?.focus({preventScroll:true});
    const reader=savedRecordingWorkspace.current;
    if(surface==='windows'&&reader){
      const chrome=document.querySelector('.ct-notebook-chrome')?.getBoundingClientRect().height??56;
      const navigation=document.querySelector('.ct-page-navigation')?.getBoundingClientRect().height??48;
      window.scrollTo({top:Math.max(0,reader.getBoundingClientRect().top+window.scrollY-chrome-navigation),behavior:'instant'});
    }else reader?.scrollIntoView({block:'start'});
  },[savedDetailOpen,selectedSession?.id,pageView]);
  const rememberRecordingOpener = () => {
    recordingOpener.current = document.activeElement instanceof HTMLButtonElement ? document.activeElement : null;
  };
  const returnToRecordingLibrary = () => {
    setDetailSessionId(null);
    window.requestAnimationFrame(() => {
      const opener = recordingOpener.current;
      const target = opener?.isConnected && opener.getClientRects().length ? opener : recordingLibraryRegion.current;
      target?.focus({preventScroll:true});
      target?.scrollIntoView({block:'nearest'});
    });
  };

  const openRecentSavedRecording = () => {
    if (!recentSavedRecording || controlsBusy) return;
    rememberRecordingOpener();
    setPageView('library');
    setLibraryFilters({ folder: '*', tag: '', favorites: false });
    setLibraryQuery('');
    setOnlyPendingSessions(false);
    setOpenSavedRecordingTarget(null);
    setOpenSavedRecordingId(recentSavedRecording.id);
    onControl({ action: 'meetingSelectSession', sessionId: recentSavedRecording.id });
  };

  const openRecentSavedResult=()=>{
    if(!recentSavedResult||controlsBusy)return;
    rememberRecordingOpener();setPageView('library');
    setLibraryFilters({folder:'*',tag:'',favorites:false});setLibraryQuery('');setOnlyPendingSessions(false);
    setOpenSavedRecordingTarget('result');setOpenSavedRecordingId(recentSavedResult.session.id);
    onControl({action:'meetingSelectSession',sessionId:recentSavedResult.session.id});
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

  useEffect(()=>{
    if(!editingMinutes)return;
    const request=window.requestAnimationFrame(()=>{
      const editor=document.getElementById('ct-active-minutes-editor');
      editor?.scrollIntoView({block:'start'});
      if(!calendarEditRequest)editor?.querySelector<HTMLInputElement>('input[aria-label^="待办 "]')?.focus({preventScroll:true});
    });
    return()=>window.cancelAnimationFrame?.(request);
  },[editingMinutes,selectedSession?.id,calendarEditRequest]);

  useEffect(()=>{
    if(!openSavedRecordingId || selectedSession?.id!==openSavedRecordingId)return;
    if(openSavedRecordingTarget==='source'){
      setMeetingPane('source');setRecordingResultOpen(false);setTranscriptReviewOpen(true);setSourceSelection(null);
    }else if(openSavedRecordingTarget==='result'){
      setMeetingPane('result');setRecordingResultOpen(true);setTranscriptReviewOpen(false);
    }
  },[openSavedRecordingId,selectedSession?.id,openSavedRecordingTarget]);

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
  const describedRecovery = selectedSession ? describeCompanionMeetingRecovery(selectedSession) : null;
  const recoveryError = selectedSession?.recovery?.lastError;
  const recoveryView = describedRecovery && recoveryError && describedRecovery.message.includes(recoveryError)
    ? {...describedRecovery, message: describedRecovery.message.replace(recoveryError, operationErrorText(recoveryError))}
    : describedRecovery;
  const finalTranscript = selectedSession ? companionSessionHasFinalTranscript(selectedSession) : false;
  useEffect(() => {
    if (gapPreview && gapPreview.sessionId === selectedSession?.id && typeof document !== 'undefined')
      document.getElementById('ct-gap-preview')?.scrollIntoView({block:'nearest'});
  }, [gapPreview?.sessionId, gapPreview?.startMs, gapPreview?.endMs, selectedSession?.id]);
  const transcriptUnmappedEdges = selectedSession ? companionTranscriptUnmappedEdges(selectedSession) : [];
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
  const minutesIncomplete = Boolean(minutesProcessing && !companionMinutesProcessingComplete(minutesProcessing));
  const manualMinutes = (selectedMinutesVariant || legacyMinutes)?.source === 'userAuthored';
  const minutesDisplayContext = manualMinutes ? undefined : (selectedMinutesVariant || legacyMinutes)?.sourceNoteContext;
  const recordingMode = selectedSession?.meetingMode === 'onlineLive' ? 'onlineLive' : 'offlineStore';
  const recordingModeMinutes = recordingMode === 'onlineLive' ? onlineMinutes : offlineMinutes;
  const legacyRecordingMinutes = !offlineMinutes && !onlineMinutes ? selectedSession?.minutes : null;
  const recordingMinutesUserEdited = ['userEdited','userAuthored'].includes(String(recordingModeMinutes?.source??legacyRecordingMinutes?.source??''));
  const recordingModeLabel = recordingMode === 'onlineLive' ? '在线速记' : '先录后整理';
  const selectedDraft = selectedSession ? meetingDrafts[selectedSession.id] : undefined;
  const selectedUnrecognized = selectedSession?.transcriptReview?.text && !companionTranscriptReviewIsStale(selectedSession)
    ? selectedSession.transcriptReview.unrecognized ?? selectedSession.transcriptUnrecognized ?? []
    : selectedSession?.transcriptUnrecognized ?? [];
  const titleDraft = selectedSession
    ? selectedDraft?.title?.value ?? meetingTitle(selectedSession) : '';
  const minutesDraft = selectedSession
    ? selectedDraft?.minutes?.[minutesViewMode]?.value ?? minutesMarkdown : '';
  const titleDirty = Boolean(selectedSession && selectedDraft?.title);
  const minutesEntry=selectedDraft?.minutes?.[minutesViewMode];
  const minutesDirty = Boolean(selectedSession && minutesEntry && (minutesEntry.value!==minutesEntry.expected || minutesEntry.createManual));
  const hasMinutes = Boolean(minutesMarkdown.trim());
  const hasPdfHighlights=Boolean(selectedSession?.bookmarks?.length || selectedSession?.meetingNotes?.length);
  const hasReviewedTiming=Boolean(selectedSession && companionReviewedUtterances(selectedSession).length);
  const selectedPdfSections={minutes:pdfSections.minutes&&hasMinutes,transcript:pdfSections.transcript&&finalTranscript,
    highlights:pdfSections.highlights&&hasPdfHighlights,timeline:pdfSections.timeline&&pdfSections.transcript&&finalTranscript&&hasReviewedTiming};
  const hasPdfContent=selectedPdfSections.minutes||selectedPdfSections.transcript||selectedPdfSections.highlights;
  const hasSyncedAudio = Boolean(
    selectedSession
    && selectedSession.status !== 'recording'
    && !['needs_device_sync','needs_segments','needs_local_audio'].includes(selectedSession.pendingReason ?? '')
    && (['hostMicrophone','hostMeeting'].includes(selectedSession.source) ? hostRecordingAudioConfirmed(selectedSession)
      : selectedSession.deviceRecordingKey ? selectedSession.audioStored && selectedSession.retention.audioCached
        && selectedSession.audioPath && selectedSession.audioBytes > 0
        : (selectedSession.audioPath || (selectedSession.audioStored && selectedSession.audioBytes > 0))),
  );
  const unimportedTranscriptDraft = Boolean(transcriptEditor.current.dirty && selectedSession
    && transcriptDraft.trim() !== (selectedSession.transcriptText ?? '').trim());
  const canGenerate = !readingPreview && finalTranscript && !recoveryView?.isProcessing && !unimportedTranscriptDraft;
  const hasOriginalAudio = Boolean(hasSyncedAudio && selectedSession?.audioStored && selectedSession.retention.audioCached
    && (selectedSession.source === 'hostMeeting' ? hostRecordingAudioConfirmed(selectedSession)
      : selectedSession.audioPath && !/^(host|device|board):\/\//i.test(selectedSession.audioPath)));
  const textOnlyImport = Boolean(selectedSession && isTextOnlyImport(selectedSession));
  const savedOriginalReady = Boolean(hasOriginalAudio && snapshot?.host.persistence?.status === 'ready'
    && !selectedSession?.captureIncomplete && !selectedSession?.recorderControlUncertain);
  const canTranscribe = Boolean(
    selectedSession
    && selectedSession.status !== 'recording'
    && !recoveryView?.isProcessing
    && hasSyncedAudio,
  );
  const privacySelectionConfirmed = Boolean(selectedSession && snapshot?.host.selectedSessionId === selectedSession.id);
  const canEraseAudio = privacySelectionConfirmed&&!selectedSession?.organization?.protected&&Boolean(selectedSession?.audioPath || selectedSession?.audioBytes);
  const canEraseTranscript = privacySelectionConfirmed&&!selectedSession?.organization?.protected&&Boolean(selectedSession?.transcriptText || selectedSession?.minutes || offlineMinutes || onlineMinutes || selectedSession?.meetingNotes?.length);
  const hasVerifiedBoardCopy = Boolean(selectedSession?.deviceRecordingId != null
    && selectedSession.sourceDeviceId && selectedSession.deviceTotalLength
    && /^[0-9a-f]{64}$/i.test(selectedSession.deviceSha256 ?? '') && !selectedSession.deviceReclaimed);
  const requestedDurationMs = Number(draftMinutes) * 60000;
  const boardMaxDurationSeconds = requestedDurationMs / 1000;
  const durationValid = draftMinutes.trim() !== '' && Number.isSafeInteger(requestedDurationMs)
    && requestedDurationMs > 0 && (!connected || boardMaxDurationSeconds <= 65535);
  const capacity = connected ? device?.recordingCapacity : null;
  // FW801's segmented recorder defines START=0 as no preset time limit.
  // Older devices may also report localLimitSeconds=0 but use different START semantics.
  const unlimitedDeviceRecording = Boolean(connected && snapshot?.source === 'firmware'
    && device?.mode === 'windowsNative' && device.boardId === 0x57424155
    && device.firmwareVersion != null && device.firmwareVersion >= 0x00010421
    && capacity?.layoutVersion === 3 && capacity.segmentFrames != null
    && capacity.segmentExtentBytes != null && capacity.localLimitSeconds === 0);
  const unlimitedOffline = unlimitedDeviceRecording && meetingMode === 'offlineStore';
  const unlimitedOnline = unlimitedDeviceRecording && meetingMode === 'onlineLive';
  const onlineDurationValid = unlimitedDeviceRecording || (durationValid && boardMaxDurationSeconds >= 12 && boardMaxDurationSeconds <= 2580);
  const durationError = (unlimitedOffline || unlimitedOnline) ? null
    : !durationValid ? '请输入有效的录音时长，实际可录时间以设备空间为准。'
    : connected && meetingMode === 'onlineLive' && !onlineDurationValid ? '当前设备在线转写单次最多 43 分钟，请修改时长。' : null;
  currentDiscardDevice.current = connected ? device?.deviceId ?? null : null;
  useEffect(() => { setDiscardMessage(null); }, [device?.deviceId, connected]);
  const capacitySeconds = capacity && capacity.usedEntries < capacity.maxEntries
    ? recordingCapacityAvailableSeconds(capacity) : 0;
  const capacityHint = !capacity ? '尚未取得设备容量，无法预估剩余时长；开始时由设备检查空间。'
    : capacity.busy ? '设备上次报告正在录音、回收或升级；开始前会重新检查。'
      : capacity.usedEntries >= capacity.maxEntries ? '设备录音目录已满，请同步并回收录音。'
        : `${formatBytes(capacity.freeBytes)} 空闲 · 仅靠设备空间约可录 ${formatDuration(capacitySeconds * 1000)}（上次读取） · 目录 ${capacity.usedEntries}/${capacity.maxEntries}`;
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
  // Native recording controls yield background synchronization at a safe boundary.
  // Keep foreground requests exclusive, but do not strand the current recording
  // behind a background job. New recordings and unrelated actions stay blocked.
  const recordingControlBusy = busyAction !== null || resourceBusy || boardOnlineBusy || exportBusy || saveMeetingBusy || bookmarkBusy || noteBusy || diagnosticBusy || serviceBusy !== null || discardBusy || libraryBusy;
  const controlsBusy = recordingControlBusy || Boolean(recordingSync?.jobId);
  // A completed recording can be edited while a different recording continues.
  const selectedRecordingBeingCaptured = Boolean(selectedSession && (selectedSession.status === 'recording'
    || (snapshot?.host.activeSessionId === selectedSession.id && oobeBlockedByRecording)));
  const lossBudgetSeconds = Math.ceil(boardMaxDurationSeconds + (meetingMode === 'onlineLive' ? 120 : 0));
  const lossBudgetValid = !unlimitedOffline && !unlimitedOnline && durationValid && lossBudgetSeconds <= 65535 && (meetingMode !== 'onlineLive' || onlineDurationValid);
  const captureBudgetBytes = capacity && lossBudgetValid
    ? recordingCapacityRequiredBytes(capacity, lossBudgetSeconds) : null;
  const capacityInsufficient = Boolean(capacity && lossBudgetValid && !recordingCapacityCanFit(capacity, lossBudgetSeconds, captureBudgetBytes ?? Infinity));
  const fragmentedCapacityMaybe = Boolean(capacity && lossBudgetValid && fragmentedSpaceMayFit(capacity, lossBudgetSeconds));
  const fragmentedCapacity = Boolean(capacity?.segmentFrames && capacity.segmentExtentBytes && capacity.freeBytes > capacity.largestFreeExtent);
  // CCQ2 peers retain the old capability bit for wire compatibility. Expose a
  // safe attempt, not a claim of support: the backend must negotiate CDS3 on
  // this connection before it can display an offer or send any confirmation.
  const canInspectRecordingLoss = Boolean(capacity && (capacity.confirmedDiscardSupported || capacity.layoutVersion === 3));
  const inspectRecordingLoss = async () => {
    if (!devicePageConnected || !onDiscardOldestRecording || !capacity || !canInspectRecordingLoss || !capacityInsufficient
      || capacity.busy || !capacity.unsyncedEntries || controlsBusy || settingsBusy || oobeBlockedByRecording || discardActive.current) return;
    discardActive.current = true; setDiscardBusy(true); setDiscardMessage(null);
    const expectedDevice = currentDiscardDevice.current;
    try {
      const result = await onDiscardOldestRecording(lossBudgetSeconds);
      if (currentDiscardDevice.current === expectedDevice) setDiscardMessage(result.message);
    }
    catch (err) {
      if (currentDiscardDevice.current === expectedDevice) setDiscardMessage(operationErrorText(err,'device'));
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
    || formDeepseekEnabled !== productSettings.deepseekMinutesEnabled
    || formAutoLocalCard !== (productSettings.autoLocalCardTranscription ?? true);
  const checkService = async (service: 'asr' | 'minutes') => {
    if (!onCheckService || controlsBusy || settingsBusy || oobeBlockedByRecording || productSettings?.storageSaveBlocked || serviceConfigDirty || serviceActive.current) return;
    serviceActive.current = true; setServiceBusy(service);
    const config = serviceConfigKey;
    setServiceResults(previous => ({ ...previous, [service]: undefined }));
    try {
      const result = await onCheckService(service);
      if (currentServiceConfig.current === config) setServiceResults(previous => ({...previous,
        [service]: `${result.message}（${Math.max(0, result.elapsedMs / 1000).toFixed(1)} 秒）`}));
    } catch (error) {
      if (currentServiceConfig.current === config) setServiceResults(previous => ({...previous, [service]: operationErrorText(error,'serviceCheck')}));
    } finally { serviceActive.current = false; setServiceBusy(null); }
  };
  const storageBlocked = Boolean(snapshot?.host.persistence && snapshot.host.persistence.status !== 'ready');
  const transcriptionRunning = busyAction === 'meetingTranscribeAudio';
  const minutesRunning = busyAction === 'meetingGenerateMinutes';
  const cloudAsrConfigured = productSettings?.asrProvider === 'volcengine'
    ? Boolean(productSettings.volcAppKeySet && productSettings.volcAccessKeySet)
    : Boolean(productSettings?.openaiAsrApiKeySet);
  const asrConfigured = productSettings?.asrProvider === 'local-paraformer'
    ? Boolean(productSettings.localAsrAvailable) : cloudAsrConfigured;
  useEffect(() => {
    onUnsavedChange?.(Boolean(productSettings && serviceConfigDirty) || Object.values(meetingDrafts).some(draft => Boolean(draft.title) || Object.values(draft.minutes ?? {}).some(value=>!!value&&(value.value!==value.expected||!!value.createManual))) || transcriptEditor.current.dirty || Boolean(retranscriptionPreview) || Boolean(gapPreview) || transcriptReviewUnsaved || bookmarkUnsaved || noteUnsaved ||audioEditUnsaved ||libraryUnsaved ||calendarPendingCount>0||calendarReminderPending>0);
  }, [onUnsavedChange, serviceConfigDirty, productSettings, meetingDrafts, transcriptDraft, retranscriptionPreview,gapPreview,transcriptReviewUnsaved,bookmarkUnsaved,noteUnsaved,audioEditUnsaved,libraryUnsaved,calendarPendingCount,calendarReminderPending]);
  const missingServiceFields = [
    ...(formAsrProvider === 'volcengine'
      ? [!formVolcResource.trim() ? '火山 Resource ID' : '', clearCredentials.includes('volcAppKey') || !(formVolcApp.trim() || productSettings?.volcAppKeySet) ? '火山 App Key' : '', clearCredentials.includes('volcAccessKey') || !(formVolcAccess.trim() || productSettings?.volcAccessKeySet) ? '火山 Access Key' : '']
      : formAsrProvider === 'local-paraformer' ? [!productSettings?.localAsrAvailable ? '本地转写模型' : '']
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
  // Only explicit navigation requests focus; polling never calls this helper.
  const navigatePage = (page: 'library' | 'device' | 'settings' | 'pet', destination?: string) => {
    const epoch = ++navigationEpoch.current;
    setHelpOpen(false);
    setPageView(page);
    window.requestAnimationFrame(() => {
      if (epoch !== navigationEpoch.current) return;
      const root = pageHeading.current?.closest('main');
      const section = destination ? root?.querySelector<HTMLElement>(`#${destination}`) : pageHeading.current;
      const target = section?.getClientRects().length ? section : pageHeading.current;
      const focus = target?.tagName === 'DETAILS' ? target.querySelector<HTMLElement>('summary') : target;
      focus?.focus({preventScroll:true});
      target?.scrollIntoView({block:'start',behavior:'auto'});
    });
  };
  const openSettings = () => {
    setSettingsReturn(pageView === 'device' ? 'device' : pageView === 'library' && savedDetailOpen ? 'recording' : null);
    setShowAdvanced(true);
    navigatePage('settings', 'ct-service-settings');
  };
  const returnToRecording = () => {
    navigatePage('library', selectedSession ? 'ct-saved-recording-workspace' : undefined);
    if (selectedSession) setOpenSavedRecordingId(selectedSession.id);
  };
  const openDeviceRecording = () => {
    setShowWorkflow(false);
    navigatePage('device', 'ct-device-recording-page');
  };
  const openAudioImport = () => {setShowWorkflow(false);setRecordingAlternativesOpen(true);navigatePage('device','ct-audio-import');};
  const openContentExport = () => revealMeetingTool('ct-meeting-export');
  const toggleRecordingPlayback = () => {
    if (playbackOpen) {audioElement.current?.pause(); meetingAudioControl.current?.pause(); setPlaybackOpen(false); return;}
    setPlaybackOpen(true); if (!preparedAudio) void prepareAudio();
  };
  const openWorkflow = () => {
    setShowWorkflow(true);
    navigatePage('device', 'ct-workflow');
  };
  const revealMeetingTool = (id:string) => {
    setMeetingPane(meetingPaneForTarget(id));
    if(id==='ct-meeting-export')setNoteExportTarget(null);
    if(id==='ct-meeting-qa')setReferenceView('assistant');else if(id==='ct-document-context')setReferenceView('documents');else if(id==='ct-recording-notes'||id==='ct-recording-references')setReferenceView('notes');
    window.requestAnimationFrame(()=>{
      const target=document.getElementById(id);
      if(!target)return;
      for(let ancestor=target;ancestor&&ancestor!==savedRecordingWorkspace.current;ancestor=ancestor.parentElement!)
        if(ancestor.tagName==='DETAILS')(ancestor as HTMLDetailsElement).open=true;
      const focus=target.tagName==='DETAILS'?target.querySelector<HTMLElement>('summary'):target;
      focus?.focus({preventScroll:true});target.scrollIntoView({block:'start',behavior:'smooth'});
    });
  };
  const journey = selectedSession ? meetingJourney(selectedSession, {
    connected, deviceId: device?.deviceId, asrReady: asrConfigured,
    localAsrReady: Boolean(productSettings?.localAsrAvailable),autoLocalCard: productSettings?.autoLocalCardTranscription===true,
    minutesReady: Boolean(productSettings?.deepseekMinutesEnabled && productSettings.deepseekApiKeySet),
  }) : null;
  const journeyRepeatsPrimaryTranscription = Boolean(selectedSession && !finalTranscript && !journey?.handlesFailure
    && journey?.request?.action === 'meetingTranscribeAudio' && journey.request.sessionId === selectedSession.id);
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
  const [transcriptLookup,setTranscriptLookup]=useState<{id:string;text:string;sessionId:string;returnId?:string}|null>(null);
  const lookupSequence=useRef(0);
  useEffect(()=>setTranscriptLookup(null),[selectedSession?.id]);
  useEffect(()=>{
    if(!qaPendingCitation || selectedSession?.id!==qaPendingCitation.sessionId)return;
    const matches=companionMinutesReferencedSources(companionTranscriptSources(selectedSession),qaPendingCitation.quote);
    setMeetingPane('source');setTranscriptReviewOpen(true);setSourceSelection(matches.length===1?matches[0]:null);setQaPendingCitation(null);
    window.requestAnimationFrame(()=>document.getElementById('ct-recording-text-review')?.scrollIntoView({block:'start'}));
  },[qaPendingCitation,selectedSession]);
  const transcriptSources = useMemo(() => selectedSession ? companionTranscriptSources(selectedSession) : [], [selectedSession]);
  const sourceContext = useRef({ session: selectedSession, blocked: false });
  // Preparing the selected audio itself temporarily makes the app busy.  Once
  // a seek starts, validate the actual source and recording, not that transient
  // busy flag; otherwise every first seek rejects its own preparation.
  sourceContext.current = { session: selectedSession,
    blocked: oobeBlockedByRecording || storageBlocked };
  const externalAudioSeek = useRef<(() => void) | null>(null);
  const audioContext = useRef({ sessionId: selectedSession?.id ?? '', identity: audioIdentity, blocked: Boolean(audioBlockedReason) });
  audioContext.current = { sessionId: selectedSession?.id ?? '', identity: audioIdentity, blocked: Boolean(audioBlockedReason) };
  const preparedAudio = selectedSession && audioSources[selectedSession.id]?.identity === audioIdentity && !audioBlockedReason
    ? audioSources[selectedSession.id] : null;
  const listeningQueue=useListeningQueue({
    rows:allLibrarySessions.filter(row=>!row.organization?.trashedAt).map(row=>({id:row.id,title:`${meetingTitle(row)} · ${isTextOnlyImport(row)?'导入文字':formatDuration(row.durationMs)} · ${row.deviceRecordingId!=null?`#${row.deviceRecordingId}`:isTextOnlyImport(row)?'文字':'录音'} · ${row.startedAt??row.id.slice(-8)}`,identity:listeningIdentity(row),
      ready:row.status!=='recording'&&row.pendingReason!=='needs_device_sync'&&row.audioStored&&row.retention.audioCached
        &&(row.source==='hostMeeting' ? hostRecordingAudioConfirmed(row) : Boolean(row.audioPath))&&!describeCompanionMeetingRecovery(row)?.isProcessing})),
    selectedId:selectedSession?.id??'',
    disabled:controlsBusy||audioBusy||titleDirty||minutesDirty||transcriptReviewUnsaved||bookmarkUnsaved||noteUnsaved||libraryUnsaved,
    hardBlocked:oobeBlockedByRecording||storageBlocked||Boolean(libraryFilters.trash),prepare:onPrepareAudio,
    select:id=>onControl({action:'meetingSelectSession',sessionId:id}),
    pause:()=>{audioElement.current?.pause();meetingAudioControl.current?.pause();},
    ready:(entry,audio,epoch)=>{
      setAudioSources(sources=>({...sources,[entry.id]:{url:audio.url,identity:entry.identity,
        sourceIdentity:audio.sourceIdentity,pauseTimeline:audio.pauseTimeline,parts:audio.parts,meetingTracks:audio.meetingTracks}}));
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
    setMeetingPane('result');setRecordingResultOpen(true);
    navigatePage('library', 'ct-recording-result');
  };
  const runOrganizationControl = (request: CompanionV1ControlRequest, explicitSource?:'original') => {
    const targetId = request.sessionId ?? selectedSession?.id;
    if (request.action === 'meetingGenerateMinutes' && targetId === selectedSession?.id) {
      if(snapshot?.minutesContextSupported && selectedSession?.meetingNotes?.length
          && request.contextNoteRevision==null && explicitSource!=='original') {
        setMeetingPane('source');setPendingMinutesTemplate(request.minutesTemplate);
        setOrganizationChoiceId(selectedSession.id);
        window.requestAnimationFrame(()=>document.getElementById('ct-organization-source-choice')?.scrollIntoView({block:'nearest'}));
        return;
      }
      if (unimportedTranscriptDraft && targetId) {
        setSaveMeetingResult({ sessionId: targetId, kind: 'error',
          message: '尚有未导入的文字。请先在录音与同步中导入，或还原为已保存的转写；本次没有开始整理。' });
        navigatePage('library');
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
  const announcedExport = useRef(exportResult);
  useEffect(() => {
    // Only reveal a newly completed operation. Returning to an old recording,
    // reopening tools, or a background snapshot must not move the viewport.
    if (announcedExport.current === exportResult) return;
    announcedExport.current = exportResult;
    if (!exportResult || exportResult.kind === 'pending' || exportResult.sessionId !== selectedSession?.id) return;
    const frame = window.requestAnimationFrame(() => {
      const element = document.querySelector<HTMLElement>(`[data-ct-export-feedback="${exportResult.origin}"]`);
      if (element?.getClientRects().length) element.scrollIntoView({ block: 'nearest' });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [exportResult, selectedSession?.id]);
  const [copyResult,setCopyResult]=useState<{sessionId:string;sourceKey:string;kind:'pending'|'copied'|'ready'|'error';message:string;text?:string}|null>(null);
  const [copyBusy,setCopyBusy]=useState(false);
  const copySourceKey=JSON.stringify([selectedSession?.id,selectedSession?.title,minutesViewMode,minutesMarkdown,titleDirty,minutesDirty,noteUnsaved,transcriptReviewUnsaved,calendarPendingCount,editingMinutes,selectedMinutesStale,minutesIncomplete]);
  const pdfPreviewKey=JSON.stringify([copySourceKey,selectedSession?.transcriptText,selectedSession?.noteRevision,selectedSession?.bookmarkRevision,selectedSession?.transcriptReview?.revision,selectedPdfSections]);
  const pdfPreviewKeyRef=useRef(pdfPreviewKey);pdfPreviewKeyRef.current=pdfPreviewKey;
  const copySourceRef=useRef(copySourceKey);copySourceRef.current=copySourceKey;
  const [phoneResult,setPhoneResult]=useState<ChecklistPhoneResult|null>(null);
  const [phoneBusy,setPhoneBusy]=useState(false);
  const phoneGeneration=useRef(0);
  useEffect(()=>{phoneGeneration.current++;setPhoneResult(null);},[copySourceKey]);
  const closePhoneChecklist=()=>{
    phoneGeneration.current++;setPhoneResult(null);
    if(phoneBusy)previewTask.current?.cancel();
  };
  const renderSavedReading = () => selectedSession ? (<MinutesReadingView markdown={localDraftForDisplay(minutesMarkdown, (selectedMinutesVariant ?? legacyMinutes)?.source)}
                actionContextKey={`${selectedSession.id}:${minutesViewMode}`}
                transcript={companionReviewedTranscript(selectedSession)} durationMs={selectedSession.durationMs}
                recordingTitle={meetingTitle(selectedSession)} recordingTime={recordingTimeLabel(selectedSession.startedAt)}
                compactAllowed={!selectedMinutesStale && !transcriptReviewUnsaved && !minutesProcessing}
                longEvidenceAllowed={minutesProcessing?.strategy === 'chunkedSourceBacked' && ['llm_deepseek','userEdited'].includes((selectedMinutesVariant ?? legacyMinutes)?.source ?? '')}
                sourceFallbackLabel={manualMinutes?(selectedSession.meetingNotes?.length?'查看原话与补充':'查看原话'):undefined}
                savedMarkdown={minutesMarkdown} noteContext={minutesDisplayContext}
                onToggleAction={onSaveMeeting?(lineIndex,completed)=>void markAction(lineIndex,completed):undefined}
                actionsBlocked={recordingControlBusy||selectedRecordingBeingCaptured||storageBlocked||selectedMinutesStale||Boolean(minutesProcessing&&!companionMinutesProcessingComplete(minutesProcessing))
                  ||minutesDirty||titleDirty||noteUnsaved||transcriptReviewUnsaved||unimportedTranscriptDraft}
                sources={selectedMinutesStale || transcriptReviewUnsaved ? [] : transcriptSources}
                blocked={controlsBusy} onOpenSource={source=>{setTranscriptLookup(null);openTranscriptSource(source);}}
                onShowTranscript={!selectedMinutesStale&&!transcriptReviewUnsaved&&companionReviewedTranscript(selectedSession).trim()?(text,returnId)=>{
                  setMeetingPane('source');setSourceSelection(null);
                  setTranscriptLookup(text?{id:String(++lookupSequence.current),text,sessionId:selectedSession.id,returnId}:null);
                  resumeTranscriptDraft(selectedSession.id);
                  window.requestAnimationFrame(()=>{const region=document.getElementById('ct-recording-text-review');
                    if(region&&!region.hidden){region.scrollIntoView({block:'start'});region.focus({preventScroll:true});}});
                }:undefined} />) : null;
  const renderExportFeedback = (origin: MeetingExportOrigin, className?: string) =>
    exportResult && exportResult.sessionId === selectedSession?.id && exportResult.origin === origin
      ? <div data-ct-export-feedback={origin}><CompanionExportFeedback key={exportResult.calendarOpenToken??exportResult.message} feedback={exportResult} className={className} onOpenSavedCalendar={onOpenSavedCalendar}/></div> : null;
  const readExportPreview = async (request:CompanionMeetingExportRequest) => {
    const task=savedExportPreview(()=>onPreviewMeetingExport!(request));
    previewTask.current=task;setPreviewWaiting(true);
    try{return await task.result;}
    finally{if(previewTask.current===task){previewTask.current=null;setPreviewWaiting(false);}}
  };
  const copyChecklist = async () => {
    if(!selectedSession||!onPreviewMeetingExport||controlsBusy||oobeBlockedByRecording||exportActive.current||selectedMinutesStale||minutesIncomplete)return;
    const sessionId=selectedSession.id,sourceKey=copySourceKey;
    if(titleDirty||minutesDirty||transcriptReviewUnsaved||calendarPendingCount>0){
      setCopyResult({sessionId,sourceKey,kind:'error',message:'还有未保存的修改，请先保存或取消后再复制。'});return;
    }
    exportActive.current=true;setCopyBusy(true);
    setCopyResult({sessionId,sourceKey,kind:'pending',message:'正在准备已保存的清单…'});
    try{
      const preview=await readExportPreview({sessionId,meetingMode:minutesViewMode,format:'todo'});
      if(copySourceRef.current!==sourceKey)return;
      if(!/^[a-f0-9]{64}$/.test(preview.contentHash)||typeof preview.textContent!=='string'||!preview.textContent.trim())throw Error('没有可复制的已保存清单。');
      const text=preview.textContent;
      try{
        if(!navigator.clipboard?.writeText)throw Error('Clipboard unavailable');
        await navigator.clipboard.writeText(text);
        setCopyResult({sessionId,sourceKey,kind:'copied',text,message:'清单已复制，可粘贴到你常用的待办或聊天中；日期与提醒仍需在接收应用确认。'});
      }catch{
        setCopyResult({sessionId,sourceKey,kind:'ready',text,message:'自动复制未完成。可在下方选择已保存的清单，再复制。'});
      }
    }catch(error){setCopyResult({sessionId,sourceKey,kind:'error',message:error instanceof SavedPreviewInterrupted?error.message:`清单未复制：${operationErrorText(error,'export')}`});}
    finally{exportActive.current=false;setCopyBusy(false);}
  };
  const showPhoneChecklist = async () => {
    if(!selectedSession||!onPreviewMeetingExport||controlsBusy||oobeBlockedByRecording||exportActive.current||selectedMinutesStale||minutesIncomplete)return;
    const sessionId=selectedSession.id,sourceKey=copySourceKey,generation=++phoneGeneration.current;
    if(titleDirty||minutesDirty||noteUnsaved||transcriptReviewUnsaved||calendarPendingCount>0){
      setPhoneResult({sessionId,sourceKey,kind:'error',message:'还有未保存的修改，请先保存或取消后再带走。'});return;
    }
    const current=()=>phoneGeneration.current===generation&&copySourceRef.current===sourceKey;
    exportActive.current=true;setPhoneBusy(true);setPhoneResult({sessionId,sourceKey,kind:'pending'});
    window.requestAnimationFrame(()=>document.getElementById('ct-phone-checklist')?.scrollIntoView({block:'nearest'}));
    try{
      const preview=await readExportPreview({sessionId,meetingMode:minutesViewMode,format:'todotxt'});
      if(!current())return;
      if(!/^[a-f0-9]{64}$/.test(preview.contentHash)||typeof preview.textContent!=='string'||!preview.textContent.trim())throw Error('没有可带走的已保存清单。');
      const code=await checklistPhoneCode(preview.textContent);
      if(current())setPhoneResult({sessionId,sourceKey,...code});
    }catch(error){
      if(current())setPhoneResult({sessionId,sourceKey,kind:'error',message:error instanceof SavedPreviewInterrupted?error.message:`清单未带走：${operationErrorText(error,'export')}`});
    }finally{exportActive.current=false;setPhoneBusy(false);}
  };
  const calendarReviewElement=useRef<HTMLDivElement|null>(null);
  const calendarReviewVisible=!!calendarExportReview&&calendarExportReview.sessionId===selectedSession?.id
    &&calendarExportReview.mode===minutesViewMode&&calendarExportReview.sourceKey===copySourceKey&&!editingMinutes;
  useEffect(()=>{
    if(!calendarReviewVisible)return;
    const region=calendarReviewElement.current;
    region?.scrollIntoView({block:'start',behavior:'auto'});
    region?.focus({preventScroll:true});
  },[calendarReviewVisible,calendarExportReview?.sourceKey]);
  const calendarReminderKey=calendarExportReview?.format==='calendar'&&calendarExportReview.sourceKey===copySourceKey&&(calendarExportReview.calendarReminders?.length||calendarExportReview.calendarSlots?.length)
    ?JSON.stringify([calendarExportReview.sourceKey,calendarExportReview.remindAtTime,calendarExportReview.reminderFormat,calendarExportReview.calendarReminders,calendarExportReview.calendarSlots]):'';
  useEffect(()=>{
    const review=calendarExportReview;if(!calendarReminderKey||!review||!onPreviewMeetingExport){setCalendarReminderPreview(null);return;}
    let alive=true;setCalendarReminderPreview(null);
    const task=savedExportPreview(()=>onPreviewMeetingExport({sessionId:review.sessionId,meetingMode:review.mode,
      format:review.remindAtTime?(review.reminderFormat??'calendarreminder30'):'calendar',calendarReminders:review.calendarReminders,...(review.calendarSlots?.length?{calendarSlots:review.calendarSlots}:{})}));
    task.result.then(preview=>{if(alive){if(!/^[a-f0-9]{64}$/.test(preview.contentHash))throw Error('提醒预览无法读取。');
      setCalendarReminderPreview({key:calendarReminderKey,hash:preview.contentHash,warning:preview.warning??''});}},error=>{if(alive)setCalendarReminderPreview({key:calendarReminderKey,error:operationErrorText(error,'export')});})
      .catch(error=>{if(alive)setCalendarReminderPreview({key:calendarReminderKey,error:String(error)});});
    return()=>{alive=false;task.cancel();};
  },[calendarReminderKey,onPreviewMeetingExport,calendarReminderRetry]);
  const calendarReminderReady=!calendarReminderKey||calendarReminderPreview?.key===calendarReminderKey&&!!calendarReminderPreview.hash;
  const changeCalendarReminderPending=(delta:1|-1)=>setCalendarReminderPending(count=>Math.max(0,count+delta));
  const exportMeeting = async (format: CompanionMeetingExportRequest['format'], origin: MeetingExportOrigin='document', confirmedHash?:string,reviewChoice?:CalendarReminderChoice&{singleDeadlineChange?:{index:number;before:CalendarExportItem[]}},calendarSaveToken?:string,calendarSavedName=false) => {
    if (!selectedSession || !onExportMeeting || controlsBusy || oobeBlockedByRecording || exportActive.current) return;
    const sessionId = selectedSession.id,exportSourceKey=copySourceKey;
    const savedCalendarReview=(format==='ics'||format.startsWith('calendar'))?calendarExportReview:null;
    const restoreCalendarReview=()=>{
      if(savedCalendarReview?.sourceKey===exportSourceKey&&copySourceRef.current===exportSourceKey)
        setCalendarExportReview(savedCalendarReview);
    };
    const unsavedForExport = titleDirty || transcriptReviewUnsaved || calendarPendingCount>0 || calendarReminderPending>0
      || (format !== 'txt' && format !== 'srt' && minutesDirty && (format !== 'pdf' || selectedPdfSections.minutes))
      || ((format === 'json' || format === 'txt' || format === 'markdown' || format === 'docx' || format === 'mindmap' || (format === 'pdf' && selectedPdfSections.highlights)) && (noteUnsaved || bookmarkUnsaved));
    if (unsavedForExport) {
      setExportResult({ sessionId, format, origin, kind: 'error', message: '还有未保存的修改。请先保存或取消修改，再导出；本次没有生成文件。' });
      return;
    }
    exportActive.current = true;
    setExportBusy(true);
    setExportResult({ sessionId, format, origin, kind: 'pending', message: '正在保存文件…' });
    try {
      let contentHash=confirmedHash;
      if((format==='ics'||format==='calendar'||format.startsWith('calendarreminder'))&&onPreviewMeetingExport&&!contentHash){
        setExportResult({sessionId,format,origin,kind:'pending',message:'正在核对日历时间…'});
        const preview=await readExportPreview({sessionId,meetingMode:minutesViewMode,format});
        if(!/^[a-f0-9]{64}$/.test(preview.contentHash))throw Error('Invalid export preview');
        contentHash=preview.contentHash;
        if(copySourceRef.current!==exportSourceKey)return;
        if(format==='calendar'){
          let reminderContentHash:string|undefined,warning=preview.warning??'';
          const reminderHashes:Partial<Record<'calendarreminder'|'calendarreminder30'|'calendarreminder60',string>>={};
          for(const reminderFormat of ['calendarreminder','calendarreminder30','calendarreminder60']as const){
            try{
              const reminder=await readExportPreview({sessionId,meetingMode:minutesViewMode,format:reminderFormat});
              if(!/^[a-f0-9]{64}$/.test(reminder.contentHash))throw Error('Invalid reminder preview');
              if(copySourceRef.current!==exportSourceKey)return;
              reminderHashes[reminderFormat]=reminder.contentHash;warning=reminder.warning??warning;
            }catch(error){
              if(!calendarExportNeedsTime(error))throw error;
              break; // Date-only has no alarm for any lead; never guess midnight.
            }
          }
          reminderContentHash=reminderHashes.calendarreminder;
          if(copySourceRef.current!==exportSourceKey)return;
          const carried=reviewChoice===undefined?retainCalendarReminders(lastSavedCalendarReminders(selectedSession,minutesViewMode),preview.calendarItems??[]):undefined;
          const carriedSlots=reviewChoice===undefined?retainCalendarSlots(selectedSession,minutesViewMode,preview.calendarItems??[]):undefined;
          const relativeCarry=carryRelativeReminderAfterSingleDeadlineEdit(reviewChoice?.calendarReminders,reviewChoice?.singleDeadlineChange,preview.calendarItems??[]);
          const priorReminders=relativeCarry.selections??carried?.selections;
          const calendarReminders=priorReminders?.filter(s=>preview.calendarItems?.some(item=>item.uid===s.uid&&(item.status==='timed'||item.status==='allDay')));
          const priorSlots=reviewChoice?.calendarSlots??carriedSlots?.selections;
          const calendarSlots=priorSlots?.filter(s=>preview.calendarItems?.some(item=>item.uid===s.uid&&(item.status==='timed'||item.status==='allDay')));
          const reminderNote=carried?.notCarriedAlarms?`上次文件中有${carried.notCarriedAlarms}项提醒对应的事项已改变或不再导出，未自动套用。请核对本次日期和提醒；未变事项的设置已保留。`:
            (calendarReminders?.length??0)!==(reviewChoice?.calendarReminders?.length??0)&&reviewChoice?(relativeCarry.suggestedAbsolute?'已修改事项的原提醒未自动套用；请核对后选择保留原时刻或重新设置。':'已修改事项的单独提醒未自动套用，请按新截止时间重新设置；其它事项的选择保留。'):undefined;
          const missingSlots=carriedSlots?.notCarried??Math.max(0,(reviewChoice?.calendarSlots?.length??0)-(calendarSlots?.length??0));
          const reminderSourceNote=[reminderNote,relativeCarry.carriedKind==='before'?'这项的提前提醒已按新的截止时间沿用，请核对。':relativeCarry.carriedKind==='none'?'这项仍设为不提醒，请核对。':undefined,missingSlots?`${missingSlots}项原执行时段对应的事项已改变或不再导出，请重新核对；未变事项的时段保留。`:undefined].filter(Boolean).join(' ')||undefined;
          setCalendarExportReview({sessionId,mode:minutesViewMode,contentHash,origin,format,warning,sourceKey:exportSourceKey,reminderSourceNote,reminderCarryover:carried?{fileName:carried.fileName,retained:calendarReminders?.length??0}:undefined,calendarReminders,calendarSlots,suggestedAbsolute:relativeCarry.suggestedAbsolute,reminderContentHash,reminderHashes,reminderFormat:reviewChoice?.reminderFormat??'calendarreminder30',remindAtTime:!!reviewChoice?.remindAtTime&&!!reminderContentHash,items:preview.calendarItems??undefined});
          setPageView('library');setDetailSessionId(sessionId);setRecordingResultOpen(true);setExportResult(null);return;
        }
        if(format==='ics'&&preview.warning){
          setCalendarExportReview({sessionId,mode:minutesViewMode,contentHash,origin,format,warning:preview.warning,sourceKey:exportSourceKey});
          setPageView('library');setDetailSessionId(sessionId);setRecordingResultOpen(true);setExportResult(null);return;
        }
      }
      setCalendarExportReview(null);
      setExportResult({sessionId,format,origin,kind:'pending',message:'请选择文件保存位置；也可在保存窗口取消。'});
      const result = await onExportMeeting({ sessionId, meetingMode: minutesViewMode, format,...(format==='pdf'?{pdfSections:selectedPdfSections}:{}),...(contentHash?{expectedContentHash:contentHash}:{}),...(reviewChoice?.calendarReminders?.length?{calendarReminders:reviewChoice.calendarReminders}:{}),...(reviewChoice?.calendarSlots?.length?{calendarSlots:reviewChoice.calendarSlots}:{}),...(calendarSaveToken?{calendarSaveToken}:{}),...(calendarSavedName?{calendarSavedName:true}:{}) });
      if(!result)restoreCalendarReview();
      if(result?.calendarOpenToken&&format.startsWith('calendar'))setCalendarSaveTargets(current=>({...current,[JSON.stringify([sessionId,minutesViewMode,selectedSession.calendarCopyEpoch??0])]:{token:result.calendarOpenToken!,name:exportFileName(result.path)}}));
      setExportResult({ sessionId, format, origin, path: result?.path, calendarOpenToken:result?.calendarOpenToken,calendarFileUri:result?.calendarFileUri, hasWarning:!!result?.warning, kind: result ? 'saved' : 'cancelled', message: result ? `已保存：${exportFileName(result.path)}${result.warning ? `（${result.warning}）` : ''}${(format === 'ics' || format === 'calendar' || format.startsWith('calendarreminder')) && !(result.calendarOpenToken && (format === 'calendar' || format.startsWith('calendarreminder'))) ? '。请在接收日历核对是否已导入，以及日期和提醒设置。' : ''}` : '已取消保存，录音内容保持不变。' });
    } catch (error) {
      if((format==='calendar'||format.startsWith('calendarreminder'))&&calendarExportNeedsTime(error)&&onSaveMeeting&&copySourceRef.current===exportSourceKey&&basicMinutesFields(minutesMarkdown,minutesDisplayContext,manualMinutes)){
        // Read-only native preflight refused a calendar with no confirmed
        // pending time. Continue the user's intent at that exact saved record,
        // not a fictitious storage failure or a file chooser with empty data.
        setCalendarExportReview(null);setExportResult(null);
        setPageView('library');setDetailSessionId(sessionId);setRecordingResultOpen(true);
        setEditingMinutes(true);
        setCalendarEditLine(undefined);setCalendarEditTimed(false);setCalendarEditAll(false);
        setCalendarReturn({sessionId,mode:minutesViewMode,origin,...reviewChoice});
        setCalendarEditRequest(`${sessionId}:${minutesViewMode}:${++calendarEditSequence.current}`);
      }else {restoreCalendarReview();setExportResult({ sessionId, format, origin, kind: 'error', message: error instanceof SavedPreviewInterrupted?error.message:`保存未完成：${operationErrorText(error,'export')}` });}
    } finally { exportActive.current = false; setExportBusy(false); }
  };
  useEffect(()=>{setCalendarReturn(null);setCalendarEditLine(undefined);setCalendarEditTimed(false);setCalendarEditAll(false);},[selectedSession?.id,minutesViewMode]);
  useEffect(()=>{
    if(!calendarReturn?.expectedMarkdown||editingMinutes||saveMeetingBusy||calendarPendingCount>0||minutesDirty||titleDirty)return;
    const request=calendarReturn;setCalendarReturn(null);
    if(request.sessionId===selectedSession?.id&&request.mode===minutesViewMode&&request.expectedMarkdown===minutesMarkdown&&!minutesDirty&&!titleDirty)
      void exportMeeting('calendar',request.origin,undefined,request);
  },[calendarReturn,editingMinutes,saveMeetingBusy,selectedSession?.id,minutesViewMode,minutesMarkdown,minutesDirty,titleDirty,calendarPendingCount]);
  const editCalendarItem=(index?:number)=>{
    const review=calendarExportReview;if(!selectedSession||!review)return;
    const actions=savedActions(minutesMarkdown);
    if(index!==undefined&&(!review.items||actions.length!==review.items.length||actions.some((a,n)=>a.text!==review.items![n].text)))return;
    setCalendarReturn(review.format==='calendar'?{sessionId:selectedSession.id,mode:minutesViewMode,origin:review.origin,fromPreview:true,remindAtTime:review.remindAtTime,reminderFormat:review.reminderFormat,calendarReminders:review.calendarReminders,calendarSlots:review.calendarSlots,...(index!==undefined&&review.items?{singleDeadlineChange:{index,before:review.items.map(item=>({...item}))}}:{})}:null);
    setCalendarEditAll(index===undefined&&!!basicMinutesFields(minutesMarkdown,minutesDisplayContext,manualMinutes));
    setCalendarEditLine(index===undefined?undefined:actions[index].lineIndex);
    setCalendarEditTimed(index!==undefined&&review.items?.[index].status==='allDay');
    setCalendarExportReview(null);setRecordingResultOpen(true);setEditingMinutes(true);
    setCalendarEditRequest(index===undefined?null:`${selectedSession.id}:${minutesViewMode}:${++calendarEditSequence.current}`);
  };
  const exportAudio = async (format:'original'|'mp3'='original') => {
    if (!selectedSession || !onExportAudio || !hasOriginalAudio || controlsBusy || oobeBlockedByRecording || exportActive.current) return;
    const sessionId = selectedSession.id;
    exportActive.current = true; setExportBusy(true);
    setExportResult({ sessionId, origin: 'audio', kind: 'pending', message: format==='mp3'?'正在生成并保存MP3副本…':selectedSession.source === 'hostMeeting' ? '正在保存会议录音…' : '正在保存原音…' });
    try {
      const result = await onExportAudio(sessionId,format);
      setExportResult({ sessionId, origin: 'audio', path: result?.path, kind: result ? 'saved' : 'cancelled', message: result ? `录音已保存：${exportFileName(result.path)}` : '已取消保存，原音保持不变。' });
    } catch (error) {
      setExportResult({ sessionId, origin: 'audio', kind: 'error', message: `${format==='mp3'?'MP3副本':'原音'}保存未完成：${operationErrorText(error,'export')}` });
    } finally { exportActive.current = false; setExportBusy(false); }
  };
  const shareAudio=async(destination:ShareDestination='system')=>{
    if(!selectedSession||!onShareAudio||!hasOriginalAudio||controlsBusy||oobeBlockedByRecording||exportActive.current)return;
    const sessionId=selectedSession.id;exportActive.current=true;setExportBusy(true);
    setExportResult({sessionId,origin:'audio',kind:'pending',message:destination==='clipboard'?'正在准备并复制录音文件…':'正在准备音频分享文件…'});
    try{const result=await onShareAudio(sessionId,audioExportFormat,destination);
      setExportResult({sessionId,origin:'audio',kind:'opened',message:shareHandoffMessage(result,destination)});
    }catch(error){setExportResult({sessionId,origin:'audio',kind:'error',message:`${destination==='clipboard'?'文件复制':'分享'}未完成：${operationErrorText(error,'export')}`});}
    finally{exportActive.current=false;setExportBusy(false);}
  };
  const changeCurrentLibraryState=async(action:'protect'|'unprotect'|'trash')=>{
    if(!selectedSession||!onSaveLibraryLifecycle||controlsBusy||oobeBlockedByRecording||storageBlocked||libraryUnsaved||exportActive.current)return;
    exportActive.current=true;setLibraryBusy(true);setLibraryCurrentMessage('');
    try{await onSaveLibraryLifecycle({targets:[{sessionId:selectedSession.id,expectedRevision:selectedSession.organization?.revision??0}],action});
      setLibraryCurrentMessage(action==='trash'?'当前录音已移入本机回收站，可恢复；原音与设备数据保留。':action==='protect'?'当前录音已受保护，解除前不能删除音频、文字或整场。':'已解除当前录音保护。');
    }catch(e){setLibraryCurrentMessage(`未完成：${operationErrorText(e,'save')}`);}
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
          [mode]: { ...current[sessionId]?.minutes?.[mode], value, expected: current[sessionId]?.minutes?.[mode]?.expected ?? minutesMarkdown },
        },
      },
    }));
  };
  const startManualChecklist = () => {
    if (!selectedSession || !onSaveMeeting || !finalTranscript || hasMinutes || recordingControlBusy || selectedRecordingBeingCaptured || storageBlocked
      || selectedSession.captureIncomplete || selectedSession.recorderControlUncertain || transcriptReviewUnsaved || noteUnsaved || unimportedTranscriptDraft) return;
    setMeetingPane('result');
    const sessionId=selectedSession.id, mode=minutesViewMode;
    setMeetingDrafts(current=>({...current,[sessionId]:{...current[sessionId],minutes:{...current[sessionId]?.minutes,
      [mode]:current[sessionId]?.minutes?.[mode]??{value:'## Action Items\n\n',expected:'',createManual:{
        expectedTranscriptText:companionReviewedTranscript(selectedSession),
        expectedReviewRevision:companionTranscriptReviewRevision(selectedSession),expectedNoteRevision:selectedSession.noteRevision??0,
      }}}}}));
    setCalendarEditAll(false);setCalendarEditLine(undefined);setCalendarEditRequest(null);setSaveMeetingResult(null);setOrganizationChoiceId(null);setRecordingResultOpen(true);setEditingMinutes(true);
  };
  const changeCalendarPending=useCallback((delta:1|-1)=>{
    setCalendarPendingCount(value=>Math.max(0,value+delta));
    if(!selectedSession)return;
    const sessionId=selectedSession.id,mode=minutesViewMode;
    setMeetingDrafts(current=>{
      const session=current[sessionId],entry=session?.minutes?.[mode];
      if(delta>0)return{...current,[sessionId]:{...session,minutes:{...session?.minutes,[mode]:{
        ...entry,value:entry?.value??minutesMarkdown,expected:entry?.expected??minutesMarkdown,
        calendarContext:minutesDisplayContext,
      }}}};
      if(entry&&!entry.createManual&&entry.value===entry.expected)return{...current,[sessionId]:{
        ...session,minutes:{...session?.minutes,[mode]:undefined},
      }};
      return current;
    });
  },[selectedSession?.id,minutesViewMode,minutesMarkdown,minutesDisplayContext]);
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
    if (part === 'minutes') {
      setEditingMinutes(false);
      setCalendarReturn(current=>current?.fromPreview?{...current,expectedMarkdown:minutesMarkdown}:null);
    }
    setSaveMeetingResult(null);
  };
  const saveMeetingDraft = async () => {
    if (!selectedSession || !onSaveMeeting || saveMeetingBusy || selectedRecordingBeingCaptured || calendarPendingCount>0 || (!titleDirty && !minutesDirty)) return;
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
        ...(minutes ? { meetingMode: mode, markdown: submittedMinutes, expectedMarkdown: minutes.expected, ...(minutes.createManual?{createManual:minutes.createManual}:{}) } : {}),
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
            nextSession.minutes = { ...currentSession.minutes, [mode]: { ...currentMinutes, expected: submittedMinutes ?? '', createManual: undefined } };
          }
          return { ...current, [sessionId]: nextSession };
        });
        setSaveMeetingResult({ sessionId, part: resultPart, kind: 'error', message: next.host.persistence?.message ? operationErrorText(next.host.persistence.message,'save') : '修改尚未安全保存，草稿已保留，请重试。' });
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
      if(minutes&&savedSession&&meetingMinutesMarkdown(savedSession,mode)===submittedMinutes)
        setCalendarReturn(current=>current&&current.sessionId===sessionId&&current.mode===mode?{...current,expectedMarkdown:submittedMinutes}:current);
      setSaveMeetingResult({ sessionId, part: resultPart, kind: 'saved', message: '修改已保存。' });
      if(minutes&&!calendarReturn)setSavedMinutesReveal({sessionId,mode});
    } catch (saveError) {
      setSaveMeetingResult({ sessionId, part: resultPart, kind: 'error', message: `未保存，草稿仍在：${operationErrorText(saveError,'save')}` });
    } finally {
      setSaveMeetingBusy(false);
    }
  };
  const restoreMinutesHistory = async (index:number, archivedAt:string, markdown:string) => {
    if(!selectedSession || !onSaveMeeting || saveMeetingBusy || recordingControlBusy || selectedRecordingBeingCaptured || storageBlocked
      || minutesDirty || titleDirty || noteUnsaved || transcriptReviewUnsaved || editingMinutes) return;
    const sessionId=selectedSession.id,mode=minutesViewMode;
    setSaveMeetingBusy(true);setSaveMeetingResult(null);
    try {
      const next=await onSaveMeeting({sessionId,meetingMode:mode,markdown,expectedMarkdown:meetingMinutesMarkdown(selectedSession,mode),restoreHistory:{index,archivedAt}});
      const saved=next.host.sessions.find(item=>item.id===sessionId);
      if(next.host.persistence?.status!=='ready'||!saved||meetingMinutesMarkdown(saved,mode)!==markdown)throw new Error('历史版本尚未保存，请重试。');
      setSaveMeetingResult({sessionId,part:'minutes',kind:'saved',message:'已切回这个版本，切换前的结果仍在历史中。'});
    } catch(error) {setSaveMeetingResult({sessionId,part:'minutes',kind:'error',message:`恢复未完成：${operationErrorText(error,'save')}`});}
    finally {setSaveMeetingBusy(false);}
  };
  const markAction = async (lineIndex:number,completed:boolean) => {
    if(!selectedSession||!onSaveMeeting||actionSaveActive.current||recordingControlBusy||selectedRecordingBeingCaptured
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
      setSaveMeetingResult({sessionId,part:'minutes',kind:'error',message:`未确认保存：${operationErrorText(error,'save')}`});
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
      setAudioSources((sources) => ({ ...sources, [sessionId]: { url: prepared.url, identity: requestedIdentity, sourceIdentity: prepared.sourceIdentity, pauseTimeline: prepared.pauseTimeline,parts:prepared.parts,meetingTracks:prepared.meetingTracks } }));
    } catch (prepareError) {
      setAudioResult({ sessionId, message: `无法回听：${operationErrorText(prepareError,'playback')}`, playbackFailure: true });
    } finally {
      setAudioBusy(false);
    }
  };
  const seekMeetingAudio = async (positionMs:number, stillCurrent:()=>boolean) => {
    if (!Number.isSafeInteger(positionMs) || positionMs < 0 || !stillCurrent()) throw new Error('重点或原音身份已变化，请重新核对。');
    if (!preparedAudio) await prepareAudio();
    const deadline = Date.now() + 4000;
    while (stillCurrent() && !meetingAudioControl.current && Date.now() < deadline) await new Promise(resolve=>setTimeout(resolve,40));
    const player = meetingAudioControl.current;
    if (!stillCurrent()) throw new Error('已切换会议，未定位其他会议的原音。');
    if (!player || positionMs / 1000 > player.duration()) throw new Error('会议原音尚未准备完成或位置超出范围。');
    player.pause(); await player.seek(positionMs / 1000);
    if (!stillCurrent()) throw new Error('已切换会议，未定位其他会议的原音。');
  };
  const seekBookmark = async (sessionId:string,bookmarkId:string,positionMs:number) => {
    setPlaybackOpen(true);
    const point=selectedSession?.bookmarks?.find((b)=>b.id===bookmarkId);
    if (!selectedSession||selectedSession.id!==sessionId||!point
      ||companionBookmarkAudioPosition(selectedSession,point)!==positionMs) throw new Error('重点所属原音已变化，请重新核对。');
    const identity=audioIdentity;
    const stillCurrent = ()=>audioContext.current.sessionId===sessionId&&audioContext.current.identity===identity&&!audioContext.current.blocked;
    if (selectedSession.source === 'hostMeeting') await seekMeetingAudio(positionMs, stillCurrent);
    else await seekBookmarkAudio(positionMs,async()=>{if(!preparedAudio) await prepareAudio();},()=>audioElement.current,
      stillCurrent, () => externalAudioSeek.current?.(),()=>segmentedAudio.current?.sessionId===sessionId?segmentedAudio.current:null);
    setAudioResult({sessionId,message:'已定位到重点。点击原音播放器的播放按钮即可回听。'});
  };
  const openEditSource=async(id:string,positionMs:number)=>{
    if(audioEditUnsaved)throw Error('请先保存或放弃当前录音编辑。');
    setEditSourceSeek({id,positionMs});setOpenSavedRecordingId(id);setDetailSessionId(id);setPlaybackOpen(true);
    if(selectedSession?.id!==id)onControl({action:'meetingSelectSession',sessionId:id});
  };
  useEffect(()=>{
    if(!editSourceSeek||selectedSession?.id!==editSourceSeek.id||controlsBusy)return;
    const target=editSourceSeek;setMeetingPane('source');setEditSourceSeek(null);setPlaybackOpen(true);
    const identity=audioIdentity;
    const current=()=>audioContext.current.sessionId===target.id&&audioContext.current.identity===identity&&!audioContext.current.blocked;
    void (selectedSession.source==='hostMeeting'?seekMeetingAudio(target.positionMs,current):
      seekBookmarkAudio(target.positionMs,async()=>{if(!preparedAudio)await prepareAudio();},()=>audioElement.current,current,
        ()=>externalAudioSeek.current?.(),()=>segmentedAudio.current?.sessionId===target.id?segmentedAudio.current:null))
      .then(()=>setAudioResult({sessionId:target.id,message:'已定位到这份成品使用的原音位置，可点击播放回听。'}))
      .catch(e=>setAudioResult({sessionId:target.id,message:operationErrorText(e)}));
  },[editSourceSeek,selectedSession?.id,controlsBusy]);
  const resumeTranscriptDraft = (sessionId: string) => {
    setMeetingPane('source');
    if (controlsBusy || !readableLibrary.some(session=>session.id===sessionId)) return;
    setSourceSelection(null);
    setTranscriptReviewOpen(true);
    if (sessionId !== selectedSession?.id) {
      setOpenSavedRecordingId(sessionId);
      onControl({ action: 'meetingSelectSession', sessionId });
    }
  };
  const openTranscriptSource = (source: CompanionTranscriptSource) => {
    setMeetingPane('source');
    if (!selectedSession || selectedMinutesStale || transcriptReviewUnsaved || controlsBusy
      || !companionTranscriptSourceIsCurrent(selectedSession, source)) return;
    // A fresh selection also re-locates the same source after manual scrolling.
    setSourceSelection({ ...source }); setTranscriptReviewOpen(true);
  };
  const seekTranscriptSource = async (source: CompanionTranscriptSource) => {
    setMeetingPane('source');
    const valid = () => Boolean(sourceContext.current.session && !sourceContext.current.blocked
      && companionTranscriptSourceIsCurrent(sourceContext.current.session, source));
    setPlaybackOpen(true);
    if (!valid() || audioBlockedReason || controlsBusy)
      throw new Error('这段转写或原音尚不可回听，请结束处理并重新核对。');
    const identity = audioIdentity;
    const stillCurrent = () => valid() && audioContext.current.sessionId === source.sessionId
      && audioContext.current.identity === identity && !audioContext.current.blocked;
    if (selectedSession?.source === 'hostMeeting') await seekMeetingAudio(source.startMs, stillCurrent);
    else await seekBookmarkAudio(source.startMs, async () => { if (!preparedAudio) await prepareAudio(); }, () => audioElement.current,
      stillCurrent, () => externalAudioSeek.current?.(),()=>segmentedAudio.current?.sessionId===source.sessionId?segmentedAudio.current:null);
    setAudioResult({ sessionId: source.sessionId, message: '已定位到这段原音。点击播放器的播放按钮即可回听。' });
  };
  const seekUnrecognized = async (part:{startMs:number;endMs:number;source?:string|null}) => {
    if (!selectedSession || audioBlockedReason || controlsBusy || storageBlocked) return;
    const sessionId=selectedSession.id, identity=audioIdentity;
    const stillCurrent=()=>{
      const session=sourceContext.current.session;
      if (!session || sourceContext.current.blocked || session.id!==sessionId
        || audioContext.current.sessionId!==sessionId || audioContext.current.identity!==identity || audioContext.current.blocked) return false;
      const current=session.transcriptReview?.text && !companionTranscriptReviewIsStale(session)
        ? session.transcriptReview.unrecognized ?? session.transcriptUnrecognized ?? []
        : session.transcriptUnrecognized ?? [];
      return current.some(item=>item.startMs===part.startMs && item.endMs===part.endMs && (item.source??null)===(part.source??null));
    };
    setPlaybackOpen(true);
    try {
      if (selectedSession.source==='hostMeeting') await seekMeetingAudio(part.startMs,stillCurrent);
      else await seekBookmarkAudio(part.startMs,async()=>{if(!preparedAudio)await prepareAudio();},()=>audioElement.current,
        stillCurrent,()=>externalAudioSeek.current?.(),()=>segmentedAudio.current?.sessionId===sessionId?segmentedAudio.current:null);
      if (!stillCurrent()) return;
      setAudioResult({sessionId,message:'已定位到未识别的时段。点击播放器的播放按钮即可回听。'});
      document.getElementById('ct-recording-playback')?.scrollIntoView({block:'start'});
    } catch(error) {
      if (audioContext.current.sessionId===sessionId) {
        setAudioResult({sessionId,message:`无法定位回听：${operationErrorText(error,'playback')}`});
        document.getElementById('ct-recording-playback')?.scrollIntoView({block:'start'});
      }
    }
  };
  const deleteLibraryKey = allLibrarySessions.map(row => [row.id, Boolean(row.organization?.protected)]).sort((a,b)=>String(a[0]).localeCompare(String(b[0]))).map(row=>JSON.stringify(row)).join('|');
  const deleteContextValid = Boolean(pendingDelete && pageView === 'settings'
    && pendingDelete.selectedId === (selectedSession?.id ?? null)
    && (pendingDelete.request.action === 'privacyEraseAll'
      ? pendingDelete.libraryKey === deleteLibraryKey && !allLibrarySessions.some(row=>row.organization?.protected)
      : pendingDelete.request.action === 'privacyEraseAudio' ? canEraseAudio : canEraseTranscript));
  useEffect(() => {
    if (pendingDelete && !deleteContextValid) setPendingDelete(null);
  }, [pendingDelete, deleteContextValid]);
  const requestErase = (action: CompanionV1ControlAction, title: string, detail: string) => {
    if (controlsBusy || oobeBlockedByRecording) return;
    if (action !== 'privacyEraseAll' && !privacySelectionConfirmed) return;
    deleteSubmitted.current = false;
    setPendingDelete({
      request: { action, sessionId: selectedSession?.id, deviceId: device?.deviceId ?? undefined },
      title, detail, targetTitle: selectedSession?.title ?? '', selectedId: selectedSession?.id ?? null,
      libraryKey: deleteLibraryKey,
    });
  };
  const confirmPendingDelete = () => {
    if (!pendingDelete || !deleteContextValid || deleteSubmitted.current || controlsBusy || oobeBlockedByRecording) return;
    deleteSubmitted.current = true;
    const request = pendingDelete.request;
    setPendingDelete(null);
    onControl(request);
  };

  // Product path: board required for primary minutes flow.
  let step = 1;
  if (connected) step = 2;
  if (hasSyncedAudio) step = 3;
  if (finalTranscript) step = 4;
  if (hasMinutes && !selectedMinutesStale) step = 5;

  // Global status describes the device/library. A previously selected
  // recording's processing result belongs to its own detail panel.
  // Readiness describes the last report, not a promise of battery life or
  // current free space. START still performs the existing authoritative check.
  const capacityUnavailable = Boolean(capacity && !capacity.busy
    && (capacity.usedEntries >= capacity.maxEntries || capacitySeconds <= 0));
  const simpleStatus = boardLiveActive ? 'Companion 正在录音'
    : oobeBlockedByRecording ? '录音进行中'
      : storageBlocked ? '本机保存暂不可用，请先处理存储问题'
        : pageView === 'library' ? recordingLibrary.length ? '已有内容可直接查看' : '还没有录音'
          : pageView === 'pet' ? connected ? 'Companion 已连接' : '连接 Companion 后可与宠物互动'
          : surface === 'windows' && pageView === 'settings' ? '管理转写、纪要与设备设置'
          : !devicePageConnected ? '连接 Companion 后可录制新内容'
            : capacityUnavailable ? '上次读取的录音空间不足，请先同步'
              : '设备已连接，开始前会重新检查空间';
  const configuredTranscription = asrConfigured ? '转文字已配置' : '转文字尚未配置';
  const simpleReadiness = boardLiveActive || oobeBlockedByRecording
    ? '结束后可在“我的记录”查看'
    : storageBlocked ? '先恢复本机保存；已有录音不会因此删除'
      : pageView === 'pet' ? connected ? '可在此查看聊天与档案' : '可在“设备与同步”中连接'
      : surface === 'windows' && pageView === 'settings' ? '可按需要选择服务并调整设置'
      : pageView === 'device' && !devicePageConnected ? '可查看已保存的录音'
      : !connected ? '可查看已保存的录音'
        : !capacity || capacity.busy ? `剩余可录时长待读取 · ${configuredTranscription}`
          : capacityUnavailable ? `同步并确认保存后，设备才会复用空间 · ${configuredTranscription}`
            : `${fragmentedCapacity ? '一块连续空间' : '仅靠设备空间'}约可录 ${recordingRoomLabel(capacitySeconds)}（上次读取）${fragmentedCapacity ? ' · 分散空间能否合用由开始时核对' : ''}${capacity.localLimitSeconds ? ` · 按键单次上限 ${recordingRoomLabel(capacity.localLimitSeconds)}` : ''} · ${configuredTranscription}`;
  useEffect(()=>{
    if(!savedMinutesReveal)return;
    if(savedMinutesReveal.sessionId!==selectedSession?.id||savedMinutesReveal.mode!==minutesViewMode||pageView!=='library'||!savedDetailOpen){setSavedMinutesReveal(null);return;}
    if(editingMinutes||minutesDirty||!hasMinutes)return;
    const region=savedMinutesHeading.current;
    region?.scrollIntoView({block:'start',behavior:'auto'});
    region?.querySelector('summary')?.focus({preventScroll:true});
    setSavedMinutesReveal(null);
  },[savedMinutesReveal,selectedSession?.id,minutesViewMode,pageView,savedDetailOpen,editingMinutes,minutesDirty,hasMinutes]);
  const footer = useMemo(() => {
    if (error) return error;
    if (nameError) return nameError;
    if (recoveryView) return recoveryView.message;
    if (selectedMinutesStale) return '原始文字和修订已保留。请重新生成或核对当前纪要，再导出待办。';
    if (hasMinutes&&manualMinutes)return '手写清单已保存，可以继续编辑或带走。';
    if (hasMinutes) return (selectedMinutesVariant?.quality ?? selectedSession?.minutes?.quality) === 'final'
      ? '纪要已保存，可以核对并导出。' : '纪要草稿已保存，可以查看或继续整理。';
    if (!connected) return recordingLibrary.length
      ? '可先查看记录库里的内容；连接设备后可继续同步。'
      : '连接 Companion，同步录音后在这里查看。';
    return '在 Companion 上录音，回到电脑同步并整理。';
  }, [error, nameError, connected, recordingLibrary.length, hasMinutes, selectedMinutesStale, recoveryView?.message, selectedMinutesVariant?.quality, selectedSession?.minutes?.quality, manualMinutes]);

  const renderRecordingReadiness = () => (<CompanionRecordingReadiness snapshot={snapshot} settings={productSettings} recording={oobeBlockedByRecording} actionsAbove={surface === 'windows'}
        busy={controlsBusy} busyAction={busyAction} onLibrary={()=>{setDetailSessionId(null);navigatePage('library');}} durationSeconds={unlimitedDeviceRecording ? null : durationValid ? boardMaxDurationSeconds : null}
        onConnect={() => onControl({action:'deviceConnect',deviceId:device?.deviceId??undefined})}
        onCheck={() => onControl({action:'oobeRunChecks',deviceId:device?.deviceId??undefined})}
        onSettings={openSettings} onRefresh={onRefresh} capacityDetails={<>
      {devicePageConnected && device?.deviceId && deviceRecordingActions ? <CompanionDeviceRecordings deviceId={device.deviceId} busy={controlsBusy||oobeBlockedByRecording} actions={deviceRecordingActions}/>:null}
      {devicePageConnected ? <details className="ct-readiness-capacity">
        <summary>设备空间详情与同步建议</summary>
        <strong>设备录音空间 · 上次读取</strong><p>{capacityHint}</p>
        {capacity ? <p>未同步 {capacity.unsyncedEntries} 段，未封口 {capacity.writingEntries} 段，共占用 {formatBytes(capacity.protectedBytes)}；待回收（已同步或已确认删除）{capacity.consumedEntries} 段，{formatBytes(capacity.consumedBytes)}。
          设备独立开录：{capacity.localLimitSeconds ? `${capacity.localLimitSeconds / 60} 分钟` : '无时间上限，空间仍有限'}。</p> : null}
        {capacity && capacity.writingEntries>0 && !oobeBlockedByRecording ? <p role="alert">
          设备仍保留未封口录音；校验不足的内容不会自动覆盖。请先同步可恢复的片段，剩余占用需要设备诊断后处理。
        </p> : null}
        <p>{capacity ? (unlimitedDeviceRecording ? '电脑开录没有预设时长，开始前检查可用空间；空间用完会保存已有录音并结束。' : '电脑开录使用下方填写的时长，开始前重新核对完整空间。空间不足会拒绝开录；不会自动覆盖未同步录音。')
          : '旧固件或未读到容量时，无法承诺完整时长；请重新读取，或升级到配套固件。'}</p>
        <button type="button" className="ct-text-button" disabled={controlsBusy || oobeBlockedByRecording}
          onClick={() => onControl({action:'oobeRunChecks'})}>重新读取设备容量</button>
        {onDiscardOldestRecording && capacity && canInspectRecordingLoss && capacityInsufficient ? <>
          <p>{fragmentedCapacityMaybe ? '一块连续空间不足，分散空间是否可用以开始前检查为准。' : ''}优先同步保存录音。也可尝试查看最旧未同步录音的具体时间、大小和风险，再决定是否删除这一条；设备不支持时会提示。</p>
          <button type="button" className="ct-text-button" disabled={controlsBusy || settingsBusy || oobeBlockedByRecording || capacity.busy || !capacity.unsyncedEntries}
            onClick={() => void inspectRecordingLoss()}>{discardBusy ? '正在核对确认与回收…' : '查看可释放的最旧录音'}</button>
        </> : null}
        {discardMessage ? <p role="status">{discardMessage}</p> : null}
      </details> : null}
        </>} />);

  const readBookmarkPosition=()=>!selectedSession?null:selectedSession.source==='hostMeeting'&&meetingAudioControl.current?Math.round(meetingAudioControl.current.position()*1000)
    :segmentedAudio.current?.sessionId===selectedSession.id?Math.round(segmentedAudio.current.position()*1000)
    :audioElement.current&&audioElement.current.readyState>=1&&Number.isFinite(audioElement.current.currentTime)?Math.round(audioElement.current.currentTime*1000):null;
  const renderRecordingSync = () => <CompanionRecordingSync status={recordingSync} pauseBusy={pauseSyncBusy}
    recoveryDeviceId={pausedSyncRecorder?.sourceDeviceId ?? (connected ? device?.deviceId : null)}
    resumeBlocked={controlsBusy || storageBlocked || boardLiveActive || (oobeBlockedByRecording && !pausedSyncRecorder)} onPause={onPauseSync} onRepair={onRepairSync}
    onResume={(deviceId) => onControl({ action: 'deviceSyncRecordings', deviceId, title: draftTitle,
      ...(pausedSyncRecorder ? { sessionId: pausedSyncRecorder.id } : {}) })} />;
  return (
    <main onClickCapture={event=>{
      if(audioEditUnsaved && event.target instanceof Element && event.target.closest('button,a')&&!event.target.closest('.ct-audio-edit-panel')){
        event.preventDefault();event.stopPropagation();document.querySelector('.ct-audio-edit-draft')?.scrollIntoView({block:'nearest'});
      }
    }} className={`ct-shell ct-simple ct-${surface}${surface==='windows'?' ct-notebook':''}${surface==='windows'&&desktopTheme==='dark'?' ct-theme-dark':''}${pageView==='library'&&!savedDetailOpen?' ct-library-overview':''}${pageView==='library'&&savedDetailOpen?' ct-meeting-detail':''}`}>
      {audioEditNotice}
      {renderIncomingFiles?.(id=>{rememberRecordingOpener();setReferenceView('notes');setOpenSavedRecordingTarget(null);setOpenSavedRecordingId(id);navigatePage('library');onControl({action:'meetingSelectSession',sessionId:id});})}
      {previewWaiting?<div className="ct-status-banner" role="status">
        <p>正在核对已保存的内容，尚未开始保存或复制。</p>
        <button type="button" className="ct-action" onClick={()=>previewTask.current?.cancel()}>取消等待</button>
      </div>:null}
      <header className="ct-topbar ct-notebook-chrome">
        <div className="ct-notebook-brand"><span className="ct-brand-mark" aria-hidden="true"><Mic size={18}/></span><strong>Companion</strong></div>
        <h1 ref={pageHeading} className="ct-sr-only" tabIndex={-1}>{pageView==='library'?'我的录音':pageView==='device'?'录音卡':pageView==='pet'?'我的宠物':'设置'}</h1>
        <div className="ct-topbar-actions">
          {surface==='windows'?<button type="button" className={`ct-notebook-device ct-connection-${connection.tone}`}
            aria-label={`录音卡 · ${connection.label}`} title={connection.hint} aria-current={pageView==='device'?'page':undefined}
            onClick={openDeviceRecording}><Bluetooth size={16} aria-hidden="true"/><span>录音卡</span><span className="ct-notebook-device-state" role="status">{connection.label}</span></button>:null}
          {surface==='windows'?<button type="button" className="ct-icon-button" onClick={toggleDesktopTheme} aria-label={desktopTheme==='dark'?'切换至浅色模式':'切换至深色模式'}>{desktopTheme==='dark'?<Sun size={17}/>:<Moon size={17}/>}</button>:null}
          <button ref={helpTrigger} type="button" className="ct-text-button" aria-expanded={helpOpen} aria-controls="ct-use-help" onClick={()=>helpOpen?closeQuickGuide():openQuickGuide()}>帮助</button>
          <button className="ct-icon-button" type="button" onClick={onRefresh} disabled={busyAction!==null} aria-label="刷新"><RefreshCw size={17}/></button>
        </div>
      </header>
      {helpOpen ? <CompanionHelp device={device} onReadLicenses={onReadLicenses} onSettings={()=>{setHelpOpen(false);openSettings();}} onPrivacy={()=>{setSettingsReturn(null);setShowAdvanced(true);navigatePage('settings','ct-privacy');}} onClose={closeQuickGuide}
        onDevice={()=>{setHelpOpen(false);openDeviceRecording();}}
        onLibrary={()=>{setDetailSessionId(null);navigatePage('library');}}
        onDiagnostics={()=>{setSettingsReturn(null);setShowAdvanced(true);navigatePage('settings','ct-log-support');}} onRecording={savedDetailOpen?returnToRecording:undefined} /> : null}

      <div className="ct-app-layout">
      <NotebookNavigation page={pageView} favorites={libraryFilters.favorites} hasPet={surface==='windows'&&!!petPanel}
        onLibrary={()=>{setDetailSessionId(null);setLibraryFilters(value=>({...value,favorites:false}));navigatePage('library');}}
        onFavorites={()=>{setDetailSessionId(null);setLibraryFilters(value=>({...value,favorites:true,trash:false}));navigatePage('library');}}
        onDevice={openDeviceRecording} onPet={()=>navigatePage('pet')}
        onSettings={()=>{setSettingsReturn(null);setShowAdvanced(true);navigatePage('settings');}}/>
      <div className="ct-app-page">

      {oobeBlockedByRecording ? <section className="ct-simple-status" aria-live="polite">
        <span className={`ct-simple-dot ${connected ? 'ok' : 'idle'}`} />
        <strong>{simpleStatus}</strong>
        <span className="ct-simple-sub">{simpleReadiness}</span>
      </section> : null}

      <div className="ct-page-panel" hidden={pageView !== 'library'}>
      {recentSavedResult&&!oobeBlockedByRecording&&!savedDetailOpen&&onlyPendingSessions?<section className="ct-recent-recording" aria-label="最近处理的记录">
        <div><span className="ct-section-eyebrow">{recentSavedResult.manual?'继续上次的清单':'继续上次的整理'}</span>
          <strong>{meetingTitle(recentSavedResult.session)}</strong>
          <small><time dateTime={recentSavedResult.at}>{recordingTimeLabel(recentSavedResult.at)}</time></small>
          {deviceStorageFullNotice(recentSavedResult.session) ? <p className="ct-step-warn" role="status">{deviceStorageFullNotice(recentSavedResult.session)}</p> : null}</div>
        <button type="button" className="ct-action ct-action-primary" disabled={controlsBusy} onClick={openRecentSavedResult}>
          {recentSavedResult.manual?'打开清单':'打开整理结果'}</button>
      </section>:null}
      {recentSavedRecording && onlyPendingSessions && (!recentSavedResult || (recentSavedRecording.processingPolicy==='localTranscription' && recentSavedResult.session.id!==recentSavedRecording.id)) && !oobeBlockedByRecording && !savedDetailOpen ? <section className="ct-recent-recording" aria-label={localSaveConfirmed ? '最近保存的录音' : '最近录音，保存状态待确认'}>
        <div>
          <span className="ct-section-eyebrow">{cardRecordingStatus(recentSavedRecording,{saved:localSaveConfirmed,modelReady:Boolean(productSettings?.localAsrAvailable),automatic:productSettings?.autoLocalCardTranscription===true}) ?? (localSaveConfirmed ? '最近保存的录音' : '最近录音 · 保存待确认')}</span>
          <strong>{meetingTitle(recentSavedRecording)}</strong>
          {companionReviewedTranscript(recentSavedRecording).trim() ? <p className="ct-recent-preview">
            {!companionSessionHasFinalTranscript(recentSavedRecording)?<span className="ct-library-text-partial">片段 · </span>:null}
            {companionReviewedTranscript(recentSavedRecording).trim()}</p> : null}
          <small><time dateTime={recentSavedRecording.startedAt ?? undefined}>{recordingTimeLabel(recentSavedRecording.startedAt)}</time>
            {' · '}{formatDuration(recentSavedRecording.durationMs)}</small>
          {!localSaveConfirmed ? <p className="ct-step-warn" role="alert">本机保存尚未确认，请打开这条录音查看保存状态。</p> : null}
          {deviceStorageFullNotice(recentSavedRecording) ? <p className="ct-step-warn" role="status">{deviceStorageFullNotice(recentSavedRecording)}</p> : null}
          {recentSavedRecording.captureIncomplete ? <p>已保存的录音片段可回听，完整录音仍待核对。</p> : null}
          {companionTranscriptUnmappedEdges(recentSavedRecording).length > 0 ? <p className="ct-step-warn">部分原音尚无对应文字，可打开核对。</p> : null}
        </div>
        <button type="button" className="ct-action ct-action-primary" disabled={controlsBusy}
          onClick={openRecentSavedRecording}><FileText size={16} />{companionSessionHasFinalTranscript(recentSavedRecording)?'查看文字结果':'查看录音进度'}</button>
      </section> : null}

      </div>

      {error ? (
        <section className="ct-pending-banner" role="alert">{error} <button type="button" className="ct-text-button" onClick={openQuickGuide}>查看恢复方法</button></section>
      ) : null}
      {!error && snapshot?.lastControl?.accepted === false ? (
        <section className="ct-pending-banner" role="alert">{operationErrorText(snapshot.lastControl.message,'device')} <button type="button" className="ct-text-button" onClick={openQuickGuide}>查看恢复方法</button></section>
      ) : null}

      {processingNotice ? <p className="ct-recording-notice ct-step-ok" role="status">{processingNotice}</p> : null}
      {gapPreview && selectedSession?.id!==gapPreview.sessionId ? <p className="ct-recording-notice" role="status">另一场录音有未保存的单段转写结果。
        <button type="button" className="ct-text-button" onClick={()=>{setOpenSavedRecordingId(gapPreview.sessionId);onControl({action:'meetingSelectSession',sessionId:gapPreview.sessionId});}}>返回核对</button>
        <button type="button" className="ct-text-button" onClick={()=>setGapPreview(null)}>关闭结果</button>
      </p>:null}
      {(transcriptionRunning || minutesRunning) && processingSessionId && onCancelMeetingProcessing ?
        <section className="ct-recording-notice" role="status">
          <span>{minutesRunning ? (cancelProcessingPending ? '正在停止整理，等待当前请求结束；原始文字保留。' : '正在整理会议，原始文字会保留。')
            : (cancelProcessingPending ? '正在停止转写，等待当前请求或音频片段结束；原录音保留。' : '正在转写，原录音会保留。')}</span>{' '}
          <button type="button" className="ct-action" disabled={cancelProcessingPending}
            onClick={() => onCancelMeetingProcessing(processingSessionId)}>{cancelProcessingPending ? '停止中…' : minutesRunning ? '停止整理' : '停止转写'}</button>
        </section> : null}
      {surface !== 'windows' ? renderRecordingSync() : recordingSync?.phase === 'blocked' ?
        <p className="ct-recording-notice" role="alert">录音收取需要处理。{' '}
          <button type="button" className="ct-text-button" onClick={()=>{navigatePage('device');setSyncDetailsOpen(true);}}>查看同步详情</button>
        </p> : null}

      {!boardLiveActive ? <CompanionRecorderControl session={controlledRecorder} busy={recordingControlBusy} onControl={onControl} /> : null}

      {boardLiveActive && boardOnlineLive ? <section className="ct-recording-activity" aria-label="当前记录">
        <div><strong role="status">{boardOnlineLive.state === 'starting' ? '正在准备录音'
          : boardOnlineLive.state === 'recording' ? '正在录音'
            : boardOnlineLive.state === 'stopping' ? '正在收齐录音' : '录音已结束，正在整理'}</strong>
          <p>{boardOnlineLive.state === 'recording' ? '声音正在由 Companion 采集，结束后继续转写与整理。'
            : '请保持设备在附近，当前录音还在处理中。'}
            {boardOnlineLive.durationMs > 0 ? ` · ${formatDuration(boardOnlineLive.durationMs)}` : ''}
            {nearRecordingLimit ? ` · 距本次设定结束约 ${formatDuration(recordingRemainingMs)}` : ''}</p></div>
        <button type="button" className="ct-action" disabled={recordingControlBusy || boardOnlineLive.state !== 'recording' || !onStopBoardOnlineLive}
          onClick={() => onStopBoardOnlineLive?.()}><Square size={15} />结束录音并整理</button>
      </section> : null}

      {!boardLiveActive && !controlledRecorder && oobeBlockedByRecording ? <section className="ct-recording-activity" aria-label="当前记录">
        <div><strong>{device?.recording ? '设备录音中 · 上次读取' : '正在录音'}</strong>
          {activeHostCaptureError ? <p role="alert">本机录音保存遇到问题，可能没有继续录到声音。请结束录音并检查已保存内容。</p>
            : <p>{device?.recording && !snapshot?.meeting.active ? '在 Companion 上结束录音后，读取设备状态，再同步到电脑。' : '结束当前录音后，再整理文字与纪要。'}设备检查、提示音和更新暂时停用。</p>}
          {snapshot?.host.sessions.find(s=>s.id===snapshot.host.activeSessionId && s.source==='hostMeeting')?.meetingTracks?.issue
            ? <p role="alert">电脑会议录音已中断，正在结束并保留已录内容；如未完成，请点击结束录音后恢复。</p> : null}</div>
        {snapshot?.meeting.active ? <button type="button" className="ct-action" disabled={recordingControlBusy}
          onClick={() => onControl({ action: 'meetingStop', sessionId: snapshot.host.activeSessionId ?? undefined })}><Square size={15} />结束录音</button>
          : <button type="button" className="ct-action" disabled={controlsBusy}
            onClick={() => onControl({ action: 'deviceConnect', deviceId: device?.deviceId ?? undefined })}><RefreshCw size={15} />读取设备状态</button>}
      </section> : null}

      <div className="ct-page-panel ct-notebook-content" hidden={pageView !== 'library'}>
      {snapshot ? <CompanionRecoveryCenter snapshot={snapshot} blocked={controlsBusy || oobeBlockedByRecording}
        savingBusy={controlsBusy} asrReady={asrConfigured}
        minutesReady={Boolean(productSettings?.deepseekMinutesEnabled && productSettings.deepseekApiKeySet)}
        onSelectSession={sessionId=>{setOpenSavedRecordingId(sessionId);onControl({action:'meetingSelectSession',sessionId});}}
        onControl={runOrganizationControl} onSettings={openSettings} onWorkflow={openWorkflow} /> : null}
      <div className="ct-notebook-library-column">
      <CompanionCard ref={recordingLibraryRegion} className="ct-library" aria-label="录音历史" tabIndex={-1} hidden={surface!=='windows'&&savedDetailOpen}>
        <div className="ct-library-head">
          <div>
            <strong>{libraryFilters.trash?'回收站':libraryQuery?'搜索结果':libraryFilters.favorites?'收藏的录音':onlyPendingSessions?'待整理的录音':'我的录音'}</strong>
            <p>{visibleLibrary.length} 条{libraryFilters.trash?' · 可恢复':libraryQuery?'匹配的录音':''}</p>
          </div>
          <div className="ct-button-row">
          {surface!=='windows'&&recordingLibrary.length>0?<button type="button" className="ct-action ct-action-primary" onClick={openDeviceRecording}>
            <Mic size={15} />{devicePageConnected?'用卡片录音':'连接录音卡'}</button>:null}
          {surface==='windows' && onImportAudio ? <button type="button" className="ct-action" onClick={openAudioImport} aria-label="导入已有音频">＋ 导入</button> : null}

          </div>
        </div>
        <label className="ct-library-search"><Search size={15} /><span className="ct-sr-only">搜索录音全文</span>
          <input value={libraryQuery} onChange={(event) => setLibraryQuery(event.target.value)}
            placeholder="搜标题、录音文字或笔记" aria-label="搜索标题、转写、补充或整理结果" />
          {libraryQuery ? <button type="button" onClick={() => setLibraryQuery('')}>清除</button> : null}
        </label>
        <div className="ct-library-toolbar" aria-label="录音列表工具">
          <div className="ct-library-view-switch" aria-label="录音范围">
            <button type="button" aria-pressed={!onlyPendingSessions} onClick={()=>setOnlyPendingSessions(false)}>全部</button>
            <button type="button" aria-pressed={onlyPendingSessions} onClick={()=>setOnlyPendingSessions(true)}>待整理</button>
          </div>
          <button type="button" id="ct-library-filter-button" className="ct-action ct-library-icon" aria-label="筛选" title="筛选录音" data-active={libraryActiveChips.length>0} onClick={()=>setLibraryPanel('filter')}><ListFilter size={15}/></button>
          <button type="button" className="ct-action ct-library-icon" aria-label={libraryToolsOpen?'取消选择':'选择'} title={libraryToolsOpen?'取消选择':'选择录音'} aria-pressed={libraryToolsOpen} disabled={libraryBusy||libraryUnsaved} onClick={()=>libraryToolsOpen?cancelLibrarySelection():setLibraryToolsOpen(true)}><SquareCheck size={15}/></button>
          <button type="button" className="ct-action ct-library-icon" aria-label="管理" title={Object.keys(librarySelection).length?`管理已选的 ${Object.keys(librarySelection).length} 条录音`:'管理录音'} onClick={()=>setLibraryPanel('manage')}><Ellipsis size={15}/></button>
        </div>
        <LibraryScopeChips className="ct-library-active-filters" chips={libraryActiveChips} onClear={clearLibraryFilters} onEmptyFocus={()=>document.getElementById('ct-library-filter-button')?.focus()}/>
        {libraryFilters.from&&libraryFilters.to&&libraryFilters.from>libraryFilters.to?<p className="ct-library-scope-warning" role="alert">日期范围有误：开始日期晚于结束日期。</p>:null}
        {libraryToolsOpen?<div className="ct-library-selection-context" role="group" aria-label="当前录音选择"><strong>{Object.keys(librarySelection).length?`已选 ${Object.keys(librarySelection).length} 条`:'勾选要整理的录音'}</strong>
          {Object.keys(librarySelection).length>0?<button type="button" className="ct-text-button" onClick={()=>setLibraryPanel('manage')}>整理所选</button>:null}
          <button type="button" className="ct-text-button" disabled={libraryBusy||libraryUnsaved} onClick={cancelLibrarySelection}>取消</button>
        </div>:null}
        {Object.keys(librarySelection).some(id=>!visibleLibrary.some(s=>s.id===id))?<p className="ct-library-scope-warning">已选录音中有 {Object.keys(librarySelection).filter(id=>!visibleLibrary.some(s=>s.id===id)).length} 条不在当前范围。</p>:null}
        <LibraryPanel open={libraryPanel!==null} title={libraryPanel==='filter'?'筛选录音':'管理录音'} blocked={libraryUnsaved||libraryBusy} onClose={()=>setLibraryPanel(null)}>
        <CompanionLibraryTools mode={libraryPanel==='filter'?'filter':'manage'} sessions={allLibrarySessions} visible={visibleLibrary} selection={librarySelection} setSelection={setLibrarySelection}
          onChoose={chooseLibraryRecordings}
          filters={libraryFilters} setFilters={setLibraryFilters} blocked={controlsBusy||oobeBlockedByRecording||storageBlocked}
          restoreBlocked={controlsBusy||oobeBlockedByRecording||snapshot?.host.persistence?.status==='unsaved'}
          onSave={onSaveLibraryOrganization} onExport={onExportLibrary} onBackup={onBackupLibrary?()=>onBackupLibrary(customTemplate):undefined} onRestore={onRestoreLibrary} onSaveLifecycle={onSaveLibraryLifecycle} onPurge={onPurgeLibrary} onBusyChange={setLibraryBusy} onUnsavedChange={setLibraryUnsaved}/>
        </LibraryPanel>
        {libraryCurrentMessage?<p role="status">{libraryCurrentMessage}</p>:null}
        {visibleLibrary.length===0&&(libraryFilters.folder!=='*'||libraryFilters.tag||libraryFilters.favorites||libraryFilters.from||libraryFilters.to)?<div className="ct-library-empty">
          <strong>当前筛选没有录音</strong><p>文件夹、标签、收藏、日期与搜索会同时筛选。清除筛选后可查看已有录音。</p>
          <button type="button" className="ct-action" onClick={clearLibraryFilters}>清除分类筛选</button>
        </div>:visibleLibrary.length === 0 ? (
          <div className="ct-library-empty"><FileText size={26} /><strong>{libraryQuery ? '没有找到相关录音或补充' : libraryFilters.trash?'回收站为空':onlyPendingSessions && recordingLibrary.length ? '暂时没有待整理的录音' : '暂无录音'}</strong>
            <p>{libraryQuery ? '搜索会检查标题、完整转写、已保存的补充和整理结果。' : libraryFilters.trash?'移入回收站的录音会保留原音和资料，直到你恢复或明确永久清除。':onlyPendingSessions && recordingLibrary.length ? '切回全部录音，可以查看已完成的内容。' : '先连接录音卡。用卡片实体键录音，结束后会在这里接收；转文字可在接收后进行。'}</p>
            {libraryQuery||libraryFilters.trash||onlyPendingSessions&&recordingLibrary.length||surface!=='windows'||devicePageConnected?<button type="button" className="ct-action ct-action-primary" onClick={libraryQuery ? () => setLibraryQuery('') : libraryFilters.trash?()=>setLibraryFilters({folder:'*',tag:'',favorites:false}):onlyPendingSessions && recordingLibrary.length ? () => setOnlyPendingSessions(false) : openDeviceRecording}>{libraryQuery ? '清除搜索' : libraryFilters.trash?'回到记录库':onlyPendingSessions && recordingLibrary.length ? '查看全部记录' : devicePageConnected?'用卡片录音':'连接录音卡'}</button>:null}</div>
        ) : (
          <div className="ct-library-list">
            {renderedLibrary.map((session,index) => {
              const selected = session.id === snapshot?.host.selectedSessionId;
              const boardId = session.deviceRecordingId;
              // Preview only saved text. Bound work per row and preserve the full original.
              const preview = libraryPreview(session,libraryQuery);
              const textState=meetingHasFinalMinutes(session)?null:recordingTextState(session,{automatic:productSettings?.autoLocalCardTranscription!==false,localReady:productSettings?.localAsrAvailable===true});
              const day=recordingDateGroup(session);
              const showDay=index===0||day!==recordingDateGroup(renderedLibrary[index-1]);
              const statusLabel = session.organization?.trashedAt ? '回收站'
                : session.status === 'recording' ? '录制中'
                : session.pendingReason === 'needs_device_sync' ? '待同步'
                : session.pendingReason === 'needs_segments' ? '同步未完成'
                : !localSaveConfirmed ? '保存待确认'
                : cardRecordingStatus(session,{saved:localSaveConfirmed,modelReady:Boolean(productSettings?.localAsrAvailable),automatic:productSettings?.autoLocalCardTranscription===true}) ?? describeCompanionMeetingRecovery(session)?.label ?? (meetingHasFinalMinutes(session)
                ? ((session.minutesByMode?.[session.meetingMode ?? 'offlineStore'] ?? session.minutes)?.source === 'userAuthored' ? '手写清单已保存' : '纪要完成')
                : session.minutes?.markdown || session.minutesByMode?.offlineStore || session.minutesByMode?.onlineLive ? '纪要草稿'
                : session.status === 'transcribed'
                  ? session.source === 'importedTranscript' ? '已导入' : '已转写'
                  : session.pendingReason === 'needs_transcription'
                     ? '可回听'
                    : '已保存');
              return (
                <Fragment key={session.id}>
                {showDay?<div className="ct-library-day" role="heading" aria-level={3}>{day}</div>:null}
                <div className="ct-library-entry">
                {libraryToolsOpen&&(onSaveLibraryOrganization||onExportLibrary||onSaveLibraryLifecycle)?<input type="checkbox" aria-label={`选择整理 ${meetingTitle(session)} ${isTextOnlyImport(session)?'导入文字':formatDuration(session.durationMs)}`}
                  checked={Object.hasOwn(librarySelection,session.id)} disabled={controlsBusy||oobeBlockedByRecording||storageBlocked}
                  onChange={e=>setLibrarySelection(old=>{const next={...old};if(e.target.checked)next[session.id]=session.organization?.revision??0;else delete next[session.id];return next;})}/>:null}
                <button
                  type="button"
                  key={session.id}
                  className={`ct-library-card ${selected ? 'selected' : ''}`}
                  onClick={() => {
                    if(selectedSession?.id!==session.id&&(titleDirty||minutesDirty||transcriptReviewUnsaved||bookmarkUnsaved||noteUnsaved||libraryUnsaved||audioEditUnsaved)){
                      setLibraryCurrentMessage('当前录音有未保存的修改，请先保存或取消，再打开另一条。');savedRecordingWorkspace.current?.focus({preventScroll:true});return;
                    }
                    setLibraryCurrentMessage('');rememberRecordingOpener();setReferenceView('notes');setOpenSavedRecordingTarget(preview.target??null);setOpenSavedRecordingId(session.id);
                    if(selectedSession?.id===session.id)setDetailSessionId(session.id);else onControl({action:'meetingSelectSession',sessionId:session.id});
                  }}
                  disabled={busyAction !== null||Boolean(libraryFilters.trash)}
                  aria-pressed={selected}
                  title={session.sourceDeviceId ? `来源设备：${session.sourceDeviceId}` : undefined}
                >
                  <span className="ct-library-icon">{isTextOnlyImport(session)?<FileText size={19} />:<Headphones size={19}/>}</span>
                  <span className="ct-library-card-main">
                    <strong>{meetingTitle(session)}</strong>
                    <small className="ct-library-recording-meta"><time dateTime={session.startedAt ?? undefined}>{recordingTimeLabel(session.startedAt)}</time><span>· {isTextOnlyImport(session)?'导入文字':formatDuration(session.durationMs)}</span></small>
                    {preview.text ? <span className="ct-library-text-preview">
                      {preview.label ? <span className="ct-library-text-partial">{preview.label} · </span> : null}{preview.text}
                    </span> : textState?<span className="ct-library-text-preview">{textState.hint}</span>:null}
                    {deviceStorageFullNotice(session) ? <small className="ct-step-warn">设备空间已满，录音提前停止</small> : null}
                    {session.organization?.protected?<small>已保护</small>:null}
                    {session.organization?.trashedAt?<small>移入时间：{trashTimeLabel(session.organization.trashedAt)}</small>:null}
                    {session.organization&&(session.organization.favorite||session.organization.folder||session.organization.tags.length)?<small>
                      {session.organization.favorite?'★ 收藏 · ':''}{session.organization.folder||'未分类'}{session.organization.tags.length?' · '+session.organization.tags.join(' · '):''}
                    </small>:null}
                  </span>
                  <span className="ct-library-card-end" hidden={localSaveConfirmed&&!session.captureIncomplete&&!['recording'].includes(session.status)&&(!textState||textState.tone==='neutral')&&!session.organization?.trashedAt}><span className={`ct-library-status ct-library-status-${session.status}${textState?' ct-state-'+textState.tone:''}`}>{!localSaveConfirmed?'保存待确认':textState?.label??statusLabel}</span></span>
                    {companionTranscriptUnmappedEdges(session).length > 0 ? <small className="ct-step-warn">部分原音尚无对应文字</small> : null}
                </button>
                </div>
                </Fragment>
              );
            })}
            {visibleLibrary.length > 50 ? <div className="ct-library-window">
              <p role="status">已显示 {renderedLibrary.length} / {visibleLibrary.length} 条</p>
              {renderedLibrary.length < visibleLibrary.length ? <button type="button" className="ct-action"
                onClick={() => setLibraryWindow({ scope: libraryWindowScope, count: libraryVisibleCount + 50 })}>
                再显示 {Math.min(50, visibleLibrary.length - renderedLibrary.length)} 条
              </button> : null}
            </div> : null}
          </div>
        )}
      </CompanionCard>

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
      </div>
      {surface==='windows'&&!savedDetailOpen?<section className="ct-notebook-placeholder" aria-label="打开录音">
        <Headphones size={27} aria-hidden="true"/><h2>{recordingLibrary.length?'打开一条录音':'把声音留在这里'}</h2>
        <p>{recordingLibrary.length?'从左侧选择录音，在这里回听、读文字和整理纪要。':'连接录音卡后，录音会自动收进资料库。也可以导入已有音频。'}</p>
        {!recordingLibrary.length?<button type="button" className="ct-action ct-action-primary" onClick={openDeviceRecording}>连接录音卡</button>:null}
      </section>:null}
      {selectedSession ? (
        <section ref={savedRecordingWorkspace} id="ct-saved-recording-workspace" className="ct-meeting-workspace" aria-label="当前记录" tabIndex={-1} hidden={!savedDetailOpen}>
          <button type="button" className="ct-text-button ct-recording-back" disabled={controlsBusy}
            onClick={returnToRecordingLibrary}>← 返回记录库</button>
          <header className="ct-meeting-hero">
            <div>

              <label className="ct-title-editor"><span className="ct-sr-only">记录标题</span><Pencil size={15} />
                <input value={titleDirty?titleDraft:meetingTitle(selectedSession)} maxLength={120} aria-label="记录标题" aria-invalid={!titleDraft.trim()} aria-describedby={!titleDraft.trim() ? "ct-title-error" : undefined}
                  readOnly={!onSaveMeeting || saveMeetingBusy || selectedRecordingBeingCaptured} title={!onSaveMeeting ? '请在桌面版编辑标题' : '点击名称可改名'}
                  onChange={(event) => updateTitleDraft(event.target.value)} /></label>
              {!titleDraft.trim() ? <p id="ct-title-error" className="ct-step-warn" role="alert">标题不能为空，请填写后保存。</p> : null}
              <p>{recordingTimeLabel(selectedSession.startedAt)}{!textOnlyImport ? ` · ${formatDuration(selectedSession.durationMs)}` : ''}</p>
              {titleDirty ? <div className="ct-inline-edit-actions">
                <button type="button" className="ct-text-button" disabled={saveMeetingBusy || selectedRecordingBeingCaptured || !titleDraft.trim()} onClick={() => void saveMeetingDraft()} aria-busy={saveMeetingBusy}>{saveMeetingBusy ? '正在保存…' : '保存标题'}</button>
                <button type="button" className="ct-text-button" disabled={saveMeetingBusy} onClick={() => cancelMeetingDraft('title')}>取消</button>
              </div> : null}
            </div>
            {!textOnlyImport && !(surface==='windows'&&finalTranscript&&hasMinutes) ? <div className="ct-meeting-badges">
              {finalTranscript ? <span className="ct-pill ct-pill-good">{selectedSession.source === 'importedTranscript' ? '已导入文字' : '文字已生成'}</span>
                : <span className="ct-pill">{selectedSession.transcriptText ? '片段转写'
                  : selectedSession.processingPolicy === 'manual' && savedOriginalReady ? '原音已保存' : '尚未转写'}</span>}
              {offlineMinutes ? <span className="ct-pill">{offlineMinutes.source === 'userAuthored' ? '手写清单' : isTextOnlyImport(selectedSession) ? (offlineReady ? '文字整理' : '整理草稿') : offlineReady ? '先录后整理' : '整理草稿'}</span> : null}
              {onlineMinutes ? <span className="ct-pill">{onlineReady ? '在线纪要' : '在线草稿'}</span> : null}
            </div> : null}
            {surface==='windows'?<div className="ct-reader-header-actions">
              {!textOnlyImport&&!playbackOpen?<button type="button" className="ct-action ct-reader-replay" aria-expanded={playbackOpen} aria-controls="ct-recording-playback"
                disabled={Boolean(audioBlockedReason)||audioBusy} title={audioBlockedReason??undefined} onClick={toggleRecordingPlayback}><Headphones size={16}/>{audioBusy?'正在准备…':'回听'}</button>:null}
              <button type="button" className="ct-action ct-reader-export" onClick={()=>{setNoteExportTarget(null);revealMeetingTool('ct-meeting-export');}}><Download size={16}/>导出</button>
            </div>:null}
          </header>
          {deviceStorageFullNotice(selectedSession) ? <p className="ct-recording-notice ct-step-warn" role="status">{deviceStorageFullNotice(selectedSession)}</p> : null}
          {saveMeetingResult?.sessionId === selectedSession.id && saveMeetingResult.part !== 'minutes' ? <p className={saveMeetingResult.kind === 'error' ? 'ct-recording-notice ct-step-warn ct-save-result' : 'ct-recording-notice ct-step-ok ct-save-result'} role="status">{saveMeetingResult.message}</p> : null}
          {!savedOriginalReady ? <RecordingSafetyCard session={selectedSession} persistence={snapshot?.host.persistence} recoveryProcessing={Boolean(recoveryView?.isProcessing)} /> : null}
          <div className="ct-recording-primary-actions">
            {!finalTranscript && !journey?.handlesFailure && !(journey?.destination==='settings') ? <button type="button" className="ct-action ct-action-primary"
              disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !canTranscribe || transcriptReviewUnsaved || minutesDirty || transcriptEditor.current.dirty}
              onClick={() => {
                if (!canTranscribe || controlsBusy || oobeBlockedByRecording || storageBlocked || transcriptReviewUnsaved || minutesDirty || transcriptEditor.current.dirty) return;
                if (!asrConfigured) {setTranscribePromptSession(selectedSession.id); return;}
                setTranscribePromptSession(null);
                onControl({action:'meetingTranscribeAudio',sessionId:selectedSession.id});
              }}><FileText size={16}/>{transcriptionRunning?'正在转文字…':recoveryView?.isProcessing?'正在处理…':selectedSession.captureIncomplete?'片段转文字':'转文字'}</button> : null}
            {surface!=='windows'&&!textOnlyImport&&!playbackOpen ? <button type="button" className="ct-action ct-reader-replay" aria-expanded={playbackOpen} aria-controls="ct-recording-playback"
              disabled={Boolean(audioBlockedReason) || audioBusy} title={audioBlockedReason ?? undefined}
              onClick={toggleRecordingPlayback}><Headphones size={16}/>{audioBusy?'正在准备…':playbackOpen?'收起回听':'回听'}</button> : null}
          </div>
          {transcribePromptSession===selectedSession.id && !asrConfigured ? <p className="ct-recording-notice" role="status">
            转文字需要先配置转写服务，原音已保留。<button type="button" className="ct-text-button" onClick={openSettings}>去配置</button>
          </p> : null}
          {transcriptionRunning ? <p className="ct-recording-notice" role="status">正在转文字，完成后会显示在这里。原音会保留。</p> : recoveryView?.isProcessing ? <p className="ct-recording-notice" role="status">{recoveryView.label}，完成后文字会显示在这里。</p> : null}
          {journey && (!journey.optional||!finalTranscript) && !recoveryView?.isProcessing ? <CompanionJourney journey={journey} hideAction={journeyRepeatsPrimaryTranscription}
            blocked={controlsBusy || oobeBlockedByRecording || storageBlocked} onControl={runOrganizationControl} onSettings={openSettings} onWorkflow={openWorkflow}/> : null}
          {selectedSession.recovery?.lastError && !journey?.handlesFailure ? <p className="ct-recording-notice ct-step-warn" role="status">处理未完成：{operationErrorText(selectedSession.recovery.lastError)}</p> : null}
          {audioResult?.sessionId===selectedSession.id ? <div className="ct-recording-notice ct-step-warn" role="status">
            <span>{audioResult.message}</span>
            {audioResult.playbackFailure && selectedSession.source==='boardDevice' && selectedSession.deviceRecordingKey ? <>
              <span> 如果电脑中保留了设备原始分段，可以尝试恢复回听文件。</span>{' '}
              <button type="button" className="ct-text-button" disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || audioBusy}
                onClick={()=>{setAudioResult({sessionId:selectedSession.id,message:'已请求恢复，完成后请重试回听。'});onControl({action:'meetingRestoreAudio',sessionId:selectedSession.id});}}>尝试恢复回听文件</button>
            </> : null}
          </div> : null}
          <div id="ct-recording-playback" hidden={!playbackOpen}>
          <section className="ct-audio-card" aria-label="本机原音回听">
            <div className="ct-player-heading"><span>录音回听</span><button type="button" className="ct-text-button" onClick={()=>{audioElement.current?.pause();meetingAudioControl.current?.pause();setPlaybackOpen(false);}}>收起回听</button></div>
            {selectedSession.source === 'hostMeeting' && selectedSession.meetingTracks?.state === 'captured' && selectedSession.meetingTracks.issue
              ? <p role="status">{selectedSession.meetingTracks.issue}</p> : null}
            {preparedAudio?.meetingTracks ? <CompanionMeetingAudioPlayer key={`${preparedAudio.identity}:${preparedAudio.sourceIdentity}:${listeningEpoch}`}
              tracks={preparedAudio.meetingTracks} controlRef={meetingAudioControl}
              sourceIdentity={preparedAudio.sourceIdentity} sessionId={selectedSession.id}
              autoPlay={listeningQueue.active?.phase==='playing'&&listeningQueue.active.entry.id===selectedSession.id}
              onFinished={()=>listeningQueue.finished(preparedAudio.sourceIdentity)} />
                        : preparedAudio ? (preparedAudio.parts && preparedAudio.parts.length>1 ? <CompanionSegmentedAudioPlayer
              key={`${preparedAudio.identity}:${preparedAudio.sourceIdentity}:${listeningEpoch}`} playerRef={audioElement} controlRef={segmentedAudio}
              parts={preparedAudio.parts} pauseTimeline={preparedAudio.pauseTimeline} sourceIdentity={preparedAudio.sourceIdentity} sessionId={selectedSession.id}
              autoPlay={listeningQueue.active?.phase==='playing'&&listeningQueue.active.entry.id===selectedSession.id}
              onFinished={()=>listeningQueue.finished(preparedAudio.sourceIdentity)} onError={()=>{
                if(audioContext.current.sessionId!==selectedSession.id || audioContext.current.identity!==preparedAudio.identity)return;
                if(listeningQueue.active)listeningQueue.stop('原音无法播放，连续播放已停止。');
                setAudioSources(current=>{const next={...current};delete next[selectedSession.id];return next;});
                setAudioResult({sessionId:selectedSession.id,message:'无法回听：音频可能已移动、删除或损坏，请刷新后重试。'});
              }} /> : <CompanionAudioPlayer key={`${preparedAudio.identity}:${preparedAudio.url}:${listeningEpoch}`} playerRef={audioElement} src={preparedAudio.url} pauseTimeline={preparedAudio.pauseTimeline}
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
                setAudioResult({ sessionId: selectedSession.id, message: '无法回听：音频可能已移动、删除或损坏，请刷新后重试。', playbackFailure: true });
              }} />)
              : <button type="button" className="ct-action" disabled={Boolean(audioBlockedReason) || audioBusy}
                title={audioBlockedReason ?? undefined} onClick={() => void prepareAudio()}>{audioBusy ? '正在准备…' : '重试回听'}</button>}
            {onPreviewGap && !finalTranscript && selectedSession.source!=='hostMeeting' && preparedAudio
              && !(preparedAudio.parts && preparedAudio.parts.length>1) ? <div className="ct-audio-tools">
              <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||storageBlocked||!canTranscribe||!hasOriginalAudio||Boolean(gapPreview)}
                onClick={async()=>{
                  const player=audioElement.current, sessionId=selectedSession.id;
                  if(!player || player.readyState<1 || !Number.isFinite(player.currentTime) || !Number.isFinite(player.duration)) {
                    setGapMessage({sessionId,text:'请先等原音加载完成，再定位要重试的位置。'});return;
                  }
                  const startMs=Math.max(0,Math.floor(player.currentTime*1000));
                  const endMs=Math.min(startMs+15_000,Math.floor(player.duration*1000));
                  if(endMs<=startMs){setGapMessage({sessionId,text:'已到录音末尾，请先移动回听位置。'});return;}
                  const sourceText=selectedSession.transcriptText,sourceReview=JSON.stringify(selectedSession.transcriptReview??null);
                  setGapMessage(null);
                  try {const result=await onPreviewGap(sessionId,{startMs,endMs});
                    setGapPreview({sessionId,startMs,endMs,text:result.text,partial:result.unrecognized.length>0,sourceText,sourceReview});}
                  catch(error){setGapMessage({sessionId,text:`单段转写未完成：${operationErrorText(error,'general')}`});}
                }}>转写当前位置起最多 15 秒</button>
              <p className="ct-step-meta">{productSettings?.asrProvider==='local-paraformer'
                ? '使用当前本地模型，不上传录音。相同音频可能得到相同结果。'
                : '使用当前转写服务，仅发送所选片段，可能产生费用。'}结果供回听核对，不覆盖原文字。</p>
              {gapMessage?.sessionId===selectedSession.id?<p role="status">{gapMessage.text}</p>:null}
            </div>:null}
          </section>
          </div>
          {surface==='windows'?<MeetingWorkspaceNav value={meetingPane} onChange={pane=>{
            setMeetingPane(pane);
            if(pane==='result')setRecordingResultOpen(true);
            if(pane==='handoff')setNoteExportTarget(null);
          }} dirty={{result:minutesDirty,source:transcriptReviewUnsaved,materials:noteUnsaved}}
            notesCount={selectedSession.meetingNotes?.length??0}/>:<nav className="ct-meeting-dock" aria-label="这场会议的工具">
            {onExportAudio&&hasOriginalAudio?<button type="button" disabled={controlsBusy||oobeBlockedByRecording} onClick={()=>{setRecordingToolsOpen(true);revealMeetingTool('ct-recording-audio-export');}}><Download size={16}/>导出录音</button>:null}
            {hasMinutes?<button type="button" onClick={()=>{setRecordingResultOpen(true);revealMeetingTool('ct-recording-result');}}><FileText size={16}/>会议纪要</button>:null}
            {finalTranscript?<button type="button" onClick={()=>{setTranscriptReviewOpen(true);revealMeetingTool('ct-recording-text-review');}}><Headphones size={16}/>转写原文</button>:null}
            {!readingPreview?<button type="button" onClick={()=>revealMeetingTool('ct-recording-references')}><FileText size={16}/>便签与文档</button>:null}
            {onAskMeetings&&finalTranscript?<button type="button" disabled={controlsBusy||qaBusy} onClick={()=>{setQaSelected([selectedSession.id]);revealMeetingTool('ct-meeting-qa');}}><Search size={16}/>问这场会议</button>:null}
            {finalTranscript&&!readingPreview?<button type="button" disabled={controlsBusy} onClick={()=>revealMeetingTool('ct-meeting-templates')}><Pencil size={16}/>整理方式：{templateId==='custom'?(customTemplate.name||'自定义'):({meeting:'会议',interview:'访谈',lecture:'课堂'}[templateId])}</button>:null}
            {hasMinutes||finalTranscript||hasPdfHighlights||selectedSession.meetingNotes?.length?<button type="button" onClick={()=>revealMeetingTool('ct-meeting-export')}><Download size={16}/>导出分享</button>:null}
          </nav>}
          <div id="ct-meeting-result-pane" className="ct-meeting-pane" hidden={surface==='windows'&&meetingPane!=='result'}>
          {surface==='windows'&&!hasMinutes&&!editingMinutes&&busyAction!=='meetingGenerateMinutes'?<section className="ct-result-empty" aria-label="纪要与待办">
            <FileText size={24} aria-hidden="true"/><h3>{finalTranscript?'把这场会议整理清楚':'等待会议文字'}</h3>
            <p>{finalTranscript?'整理会议重点、结论和需要跟进的事。原话与补充资料保留，生成后可以逐项核对和修改。':'原音和接收进度保留在这条记录中。文字就绪后，可在这里生成纪要和待办。'}</p>
            {finalTranscript?<div className="ct-button-row"><button type="button" className="ct-action ct-action-primary"
              disabled={controlsBusy||oobeBlockedByRecording||storageBlocked||!canGenerate||noteUnsaved||minutesDirty||titleDirty||transcriptReviewUnsaved}
              onClick={()=>runOrganizationControl({action:'meetingGenerateMinutes',sessionId:selectedSession.id})}>生成会议纪要</button>
              {onSaveMeeting?<button type="button" className="ct-action" disabled={recordingControlBusy||selectedRecordingBeingCaptured||storageBlocked||transcriptReviewUnsaved||noteUnsaved||unimportedTranscriptDraft}
                onClick={()=>{setRecordingResultOpen(true);startManualChecklist();}}>自己写清单</button>:null}
              <button type="button" className="ct-text-button" onClick={()=>revealMeetingTool('ct-recording-text')}>先读转写原文</button></div>:null}
          </section>:null}
          {hasMinutes || editingMinutes || busyAction === 'meetingGenerateMinutes' ? <details ref={savedMinutesHeading} id="ct-recording-result" className="ct-recording-result"
            open={recordingResultOpen} onToggle={event=>setRecordingResultOpen(event.currentTarget.open)}>
            <summary hidden={surface==='windows'}>{manualMinutes ? '手写清单' : '会议纪要'}{minutesDirty ? ' · 有未保存的修改' : manualMinutes ? storageBlocked ? ' · 保存待确认' : ' · 已保存' : ''}</summary>
            {selectedUnrecognized.length ? <p className="ct-step-warn" role="status">{selectedUnrecognized.some(part=>part.source?.includes('转写失败'))
              ? '部分音轨转写失败，整理只依据已有文字；可在下方查看音轨并重新转写。'
              : '部分原音没有识别出文字，整理只依据识别到的内容；可在下方查看时段并回听核对。'}</p> : null}
            <MinutesModeTabs value={minutesViewMode} onChange={setMinutesViewMode} dualMode={Boolean(offlineMinutes && onlineMinutes)}
              labels={{offlineStore:{visible:`${offlineMinutes?.source === 'userAuthored' ? '手写清单' : selectedSession && isTextOnlyImport(selectedSession) ? '文字整理' : '先录后整理'} ${offlineReady ? '✓' : offlineMinutes ? '草稿' : ''}`,accessible:`${offlineMinutes?.source === 'userAuthored' ? '手写清单' : selectedSession && isTextOnlyImport(selectedSession) ? '文字整理' : '先录后整理纪要'} ${offlineReady ? '✓' : offlineMinutes ? '草稿' : '未生成'}`},
                onlineLive:{visible:`在线速记 ${onlineReady ? `✓ · ${onlineMinutes?.partialCount} 段` : onlineMinutes ? '草稿' : ''}`,accessible:`在线纪要 ${onlineReady ? `✓ · ${onlineMinutes?.partialCount} 次片段` : onlineMinutes ? '草稿' : '未生成'}`}}}>
              {minutesDisplayContext?<p className="ct-minutes-mode-meta">{(selectedMinutesVariant??legacyMinutes)?.source==='rules_l0'&&(selectedMinutesVariant??legacyMinutes)?.quality==='draft'
                ? '整理未完成。下方是基础草稿，尚未应用本次补充；原话和补充均已保存。'
                : '本次依据原话＋你选择的补充整理；补充不是录音识别。'}</p>:null}
              {minutesProcessing && !companionMinutesProcessingComplete(minutesProcessing) ? <div className="ct-step-warn" role="status">
                {`部分纪要：已整理 ${minutesProcessing.completedChunks}/${minutesProcessing.totalChunks} 段，原文与已完成分段都已保留。`}
                {<button type="button" className="ct-action"
                  disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !finalTranscript || transcriptReviewUnsaved || editingMinutes || selectedMinutesStale}
                  onClick={() => runOrganizationControl({ action: 'meetingGenerateMinutes', sessionId: selectedSession.id, meetingMode: minutesViewMode })}>继续整理当前纪要</button>}
              </div> : null}
              {selectedMinutesStale ? <div className="ct-step-warn" role="status">转写或本次使用的补充已变化。这版结果已保留，请重新整理后使用。
                <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || transcriptReviewUnsaved || editingMinutes}
                  onClick={() => runOrganizationControl({ action: 'meetingGenerateMinutes', sessionId: selectedSession.id, meetingMode: minutesViewMode })}>重新选择内容并整理</button>
              </div> : null}
              {selectedMinutesVariant?.source === 'rules_l0' ? <p className="ct-step-meta">仅摘录已有原句，需你核对并补充；原音和文字已保留。</p> : null}
              {!editingMinutes?<div className="ct-result-reading-toolbar"><span>{manualMinutes?'手写内容':selectedMinutesVariant?.source==='userEdited'?'含人工修订':selectedMinutesVariant?.source==='rules_l0'?'原句摘录草稿':selectedMinutesVariant?.quality==='draft'?'速记草稿':'AI 整理 · 请核对'}{!manualMinutes&&companionTranscriptReviewRevision(selectedSession)!==null?' · 基于修订文字':''}</span><button type="button" className="ct-text-button" disabled={!hasMinutes||!onSaveMeeting||selectedRecordingBeingCaptured} onClick={()=>{setCalendarEditAll(false);setCalendarEditLine(undefined);setCalendarEditRequest(null);setEditingMinutes(true);}}>编辑纪要</button></div>:null}
              {!editingMinutes&&hasMinutes?renderSavedReading():null}
              {(selectedSession.minutesByMode?.history ?? []).some(item=>item.mode===minutesViewMode) ? <details className="ct-minutes-history">
                <summary>查看以前的整理结果</summary>
                <p className="ct-step-meta">重新整理前的内容保存在这里。切换版本不会删除当前内容；旧版本可能基于之前的转写。</p>
                {(selectedSession.minutesByMode?.history ?? []).map((item,index)=>({item,index})).reverse().filter(({item})=>item.mode===minutesViewMode).map(({item,index})=><details key={`${item.archivedAt}-${index}`}>
                  <summary>{item.variant.template?.name || (item.variant.source==='userEdited'||item.variant.source==='userAuthored'?'人工修改':'整理结果')} · {item.variant.generatedAt || item.archivedAt}</summary>
                  <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{item.variant.markdown}</pre>
                  <button type="button" className="ct-action" disabled={!onSaveMeeting||saveMeetingBusy||recordingControlBusy||selectedRecordingBeingCaptured||storageBlocked||minutesDirty||titleDirty||noteUnsaved||transcriptReviewUnsaved||editingMinutes}
                    onClick={()=>void restoreMinutesHistory(index,item.archivedAt,item.variant.markdown)}>使用这个版本</button>
                </details>)}
              </details> : null}
              <details className="ct-result-secondary-actions" hidden={editingMinutes}><summary>清单与日历工具</summary>
              <div className="ct-inline-edit-actions ct-minutes-export-actions">
                {!editingMinutes && hasMinutes && savedActions(minutesMarkdown).length>0 && onPreviewMeetingExport ? <button type="button" className="ct-action"
                  disabled={controlsBusy||oobeBlockedByRecording||phoneBusy||copyBusy||exportBusy||selectedMinutesStale||minutesIncomplete}
                  onClick={()=>void showPhoneChecklist()}>{phoneBusy?'正在准备…':'显示文字二维码'}</button> : null}
                {!editingMinutes&&hasMinutes&&savedActions(minutesMarkdown).length>0&&onPreviewMeetingExport?<span className="ct-step-meta">不会自动同步到手机；也可导出 TXT 自行传送。</span>:null}
                {!editingMinutes && hasMinutes && savedActions(minutesMarkdown).length>0 && onPreviewMeetingExport ? <button type="button" className="ct-action"
                  disabled={controlsBusy||oobeBlockedByRecording||phoneBusy||copyBusy||exportBusy||selectedMinutesStale||minutesIncomplete}
                  onClick={()=>void copyChecklist()}>{copyBusy?'正在准备…':'复制清单'}</button> : null}

                {!editingMinutes && hasMinutes ? <button type="button" className="ct-action"
                  disabled={controlsBusy||oobeBlockedByRecording||!onExportMeeting||selectedMinutesStale}
                  onClick={()=>void exportMeeting(!minutesIncomplete && savedActions(minutesMarkdown).length>0?'todotxt':'markdown')}><Download size={15}/>
                  {minutesIncomplete?'保存部分纪要':savedActions(minutesMarkdown).length>0?'导出待办 TXT':'导出整理'}</button> : null}
                {!editingMinutes && hasMinutes && savedActions(minutesMarkdown).length>0 ? <button type="button" className="ct-text-button" disabled={controlsBusy||oobeBlockedByRecording} onClick={openContentExport}>预览并导出完整内容</button> : null}
                {!editingMinutes && hasMinutes && savedActions(minutesMarkdown).length>0 ? <button type="button" className="ct-action"
                  disabled={controlsBusy||oobeBlockedByRecording||!onExportMeeting||selectedMinutesStale||minutesIncomplete}
                  title={minutesIncomplete ? '整理完成后才能导出整场待办' : '把未完成事项和已确认时间写成日程文件，导入常用日历后核对提醒'}
                  onClick={()=>void exportMeeting('calendar')}>导出到日历</button> : null}

              </div>
              {!editingMinutes && hasMinutes && savedActions(minutesMarkdown).length>0 ? <p className="ct-step-meta">{minutesIncomplete ? '可先保存已整理的部分；整场待办和日历导出需等待整理完成。' : '待办 TXT 只包含清单事项。要带上摘要、讨论安排、待确认内容或 AI 材料，可选择“预览并导出完整内容”。清单不自动提醒；需要时导出到日历。'}</p> : null}
              </details>
              {phoneResult?.sessionId===selectedSession.id&&phoneResult.sourceKey===copySourceKey&&!editingMinutes
                ? <CompanionChecklistPhone result={phoneResult} onClose={closePhoneChecklist}/> : null}

              {!editingMinutes ? <CompanionCalendarCopies key={`${selectedSession.id}:${minutesViewMode}:${selectedSession.calendarCopyRevision??0}:${copySourceKey}`} session={selectedSession} mode={minutesViewMode} markdown={minutesMarkdown}/> : null}
              {calendarReviewVisible&&calendarExportReview?<div ref={calendarReviewElement} className="ct-calendar-export-review" role="region" aria-label="日历导出预览" tabIndex={-1}>
                <h3>确认日历日程与提醒</h3>
                <p>{calendarExportReview.format==='calendar'?((calendarReminderKey&&calendarReminderReady?calendarReminderPreview?.warning:calendarExportReview.warning)||'把已确认的日期和时间带到常用日历；后续修改不会自动同步。'):'还有时间说明未确认为日历截止时间。可以先核对，也可将时间按文字说明导出。'}</p>
                {calendarExportReview.reminderCarryover?<p className="ct-step-meta">已从“{calendarExportReview.reminderCarryover.fileName}”的最近保存记录带入{calendarExportReview.reminderCarryover.retained}项逐项设置。只沿用未变事项，下面仍可修改；不读取接收日历里的后续改动。</p>:null}
                {calendarExportReview.reminderSourceNote?<p className="ct-step-warn" role="status">{calendarExportReview.reminderSourceNote}</p>:null}
                {calendarExportReview.format==='calendar'?<>
                  <label className="ct-step-meta"><input type="checkbox" aria-label="统一设置提醒" checked={!!calendarExportReview.remindAtTime}
                    disabled={controlsBusy||oobeBlockedByRecording||!calendarExportReview.reminderContentHash}
                    onChange={event=>{const checked=event.currentTarget.checked;setCalendarExportReview(current=>current?{...current,remindAtTime:checked}:null);}}/> 统一设置提醒</label>
                  {calendarExportReview.remindAtTime?<label className="ct-step-meta" style={{display:'block',marginTop:8}}>提醒时间
                    <select aria-label="日历提醒时间" value={calendarExportReview.reminderFormat??'calendarreminder30'} disabled={controlsBusy||oobeBlockedByRecording}
                      onChange={event=>{const selected=event.currentTarget.value;if(!['calendarreminder','calendarreminder30','calendarreminder60'].includes(selected))return;
                        setCalendarExportReview(current=>current?{...current,reminderFormat:selected as 'calendarreminder'|'calendarreminder30'|'calendarreminder60'}:null);}}>
                      <option value="calendarreminder30">提前30分钟</option><option value="calendarreminder60">提前1小时</option><option value="calendarreminder">在已确认的时刻</option>
                    </select>
                  </label>:null}
                  <details><summary>统一提醒的应用范围</summary><p className="ct-step-meta">例如选择“提前30分钟”，有具体时刻且未单独设置提醒的事项，就会提前30分钟提醒。每项下方会显示实际设置；全天事项可在下方一次明确当天提醒时刻，仍可逐项覆盖。</p></details>
                </>:null}
                {calendarExportReview.items?<CalendarExportItems items={calendarExportReview.items} choice={calendarExportReview}
                  disabled={controlsBusy||oobeBlockedByRecording||!onSaveMeeting||selectedMinutesStale}
                  onPending={changeCalendarReminderPending}
                  suggestedAbsolute={calendarExportReview.suggestedAbsolute}
                  onReminders={selections=>setCalendarExportReview(current=>current?{...current,suggestedAbsolute:selections.some(s=>s.uid===current.suggestedAbsolute?.uid)?undefined:current.suggestedAbsolute,calendarReminders:[...(current.calendarReminders??[]).filter(existing=>!selections.some(selection=>selection.uid===existing.uid)),...selections]}:null)}
                  onReminder={(uid,reminder)=>setCalendarExportReview(current=>current?{...current,suggestedAbsolute:current.suggestedAbsolute?.uid===uid?undefined:current.suggestedAbsolute,calendarReminders:[...(current.calendarReminders??[]).filter(s=>s.uid!==uid),...(reminder?[{uid,reminder}]:[])]}:null)}
                  onSlot={(uid,slot)=>setCalendarExportReview(current=>current?{...current,calendarSlots:[...(current.calendarSlots??[]).filter(s=>s.uid!==uid),...(slot?[{uid,slot}]:[])]}:null)}
                  onEdit={basicMinutesFields(minutesMarkdown,minutesDisplayContext,manualMinutes)&&savedActions(minutesMarkdown).length===calendarExportReview.items.length&&savedActions(minutesMarkdown).every((a,n)=>a.text===calendarExportReview.items![n].text)?editCalendarItem:undefined}/>:null}
                {calendarSaveTargets[JSON.stringify([selectedSession.id,minutesViewMode,selectedSession.calendarCopyEpoch??0])]&&calendarExportReview.format==='calendar'?<div className="ct-calendar-save-again">
                  <p className="ct-step-meta">已关联本地文件的日历可在同一文件保存后读取更新。只有导入过的副本仍需另行修改；覆盖前先核对日历端是否改过内容。</p>
                  <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||calendarPendingCount>0||calendarReminderPending>0||!calendarReminderReady}
                    onClick={()=>void exportMeeting(calendarExportReview.remindAtTime?(calendarExportReview.reminderFormat??'calendarreminder30'):calendarExportReview.format,calendarExportReview.origin,calendarReminderKey?calendarReminderPreview?.hash:calendarExportReview.remindAtTime?calendarExportReview.reminderHashes?.[calendarExportReview.reminderFormat??'calendarreminder30']:calendarExportReview.contentHash,calendarExportReview,calendarSaveTargets[JSON.stringify([selectedSession.id,minutesViewMode,selectedSession.calendarCopyEpoch??0])].token)}>
                    保存到上次文件…（{calendarSaveTargets[JSON.stringify([selectedSession.id,minutesViewMode,selectedSession.calendarCopyEpoch??0])].name}）
                  </button><p className="ct-step-meta">将打开保存窗口，仍可取消或另存；位置记忆仅限本次打开 Type 期间。</p>
                </div>:null}
                {!calendarSaveTargets[JSON.stringify([selectedSession.id,minutesViewMode,selectedSession.calendarCopyEpoch??0])]&&calendarExportReview.format==='calendar'&&selectedSession.calendarCopies?.some(copy=>copy.meetingMode===minutesViewMode && copy.privacyEpoch===(selectedSession.calendarCopyEpoch??0))?<div className="ct-calendar-save-again">
                  <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||calendarPendingCount>0||calendarReminderPending>0||!calendarReminderReady}
                    onClick={()=>void exportMeeting(calendarExportReview.remindAtTime?(calendarExportReview.reminderFormat??'calendarreminder30'):calendarExportReview.format,calendarExportReview.origin,calendarReminderKey?calendarReminderPreview?.hash:calendarExportReview.remindAtTime?calendarExportReview.reminderHashes?.[calendarExportReview.reminderFormat??'calendarreminder30']:calendarExportReview.contentHash,calendarExportReview,undefined,true)}>按上次文件名保存…</button>
                  <p className="ct-step-meta">只填写上次文件名，请自行核对文件夹和目标文件，也可改名另存；重启后不会记住文件夹。</p>
                </div>:null}
                {calendarExportReview.items?<CalendarCopyComparison key={`${selectedSession.id}:${minutesViewMode}:${selectedSession.calendarCopyRevision??0}:${copySourceKey}`}
                  copies={(selectedSession.calendarCopies??[]).filter(copy=>copy.meetingMode===minutesViewMode&&copy.privacyEpoch===(selectedSession.calendarCopyEpoch??0))} slotCopies={selectedSession.calendarSlotCopies} items={calendarExportReview.items} choice={calendarExportReview}
                  disabled={controlsBusy||oobeBlockedByRecording||calendarReminderPending>0}
                  onUseReminder={(uid,reminder)=>setCalendarExportReview(current=>current&&current.sourceKey===copySourceKey&&current.items?.some(item=>item.uid===uid&&(item.status==='timed'||item.status==='allDay'))?{...current,suggestedAbsolute:current.suggestedAbsolute?.uid===uid?undefined:current.suggestedAbsolute,calendarReminders:[...(current.calendarReminders??[]).filter(selection=>selection.uid!==uid),{uid,reminder}]}:current)}/>:null}
                {calendarReminderKey&&calendarReminderPreview?.key===calendarReminderKey&&calendarReminderPreview.error?<button type="button" className="ct-text-button" disabled={controlsBusy||oobeBlockedByRecording} onClick={()=>setCalendarReminderRetry(n=>n+1)}>重新核对提醒</button>:null}
                {calendarReminderKey&&!calendarReminderReady?<p role="status">{calendarReminderPreview?.key===calendarReminderKey&&calendarReminderPreview.error?`提醒尚未核对：${calendarReminderPreview.error}`:'正在核对本次逐项提醒…'}</p>:null}
                <div className="ct-button-row">
                  <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||!onSaveMeeting||selectedMinutesStale||calendarReminderPending>0}
                    onClick={()=>editCalendarItem()}>{basicMinutesFields(minutesMarkdown,minutesDisplayContext,manualMinutes)?'核对各项截止时间':'编辑完整清单（含时间）'}</button>
                  <span className="ct-step-meta">只改一项截止时间，可用该事项下方的时间按钮。</span>
                  <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||selectedMinutesStale||minutesIncomplete||calendarReminderPending>0||!calendarReminderReady}
                    onClick={()=>void exportMeeting(calendarExportReview.remindAtTime?(calendarExportReview.reminderFormat??'calendarreminder30'):calendarExportReview.format,calendarExportReview.origin,calendarReminderKey?calendarReminderPreview?.hash:calendarExportReview.remindAtTime?calendarExportReview.reminderHashes?.[calendarExportReview.reminderFormat??'calendarreminder30']:calendarExportReview.contentHash,calendarExportReview)}>{calendarExportReview.format==='calendar'?(calendarExportReview.items?.some(item=>(item.status==='timed'||item.status==='allDay')&&effectiveCalendarAlarm(item,calendarExportReview).kind!=='none')?'保存日历文件（含提醒）':'保存日历文件'):'按文字说明导出'}</button>
                  <button type="button" className="ct-text-button" disabled={exportBusy} onClick={()=>setCalendarExportReview(null)}>取消导出</button>
                </div>
              </div>:null}
              {copyResult?.sessionId===selectedSession.id&&copyResult.sourceKey===copySourceKey&&!editingMinutes?<div className="ct-checklist-copy-result" role={copyResult.kind==='error'?'alert':'status'}>
                <p>{copyResult.message}</p>
                {copyResult.text?<details open={copyResult.kind==='ready'||undefined}><summary>查看清单文字</summary><textarea aria-label="已保存的清单文字" readOnly value={copyResult.text} onFocus={event=>event.currentTarget.select()} style={{width:'100%',minHeight:90,boxSizing:'border-box'}}/></details>:null}
              </div>:null}
              {renderExportFeedback('document', exportResult?.kind === 'error' ? 'ct-document-export-result ct-step-warn' : 'ct-document-export-result ct-step-ok')}
              {editingMinutes ? <div id="ct-active-minutes-editor" className="ct-minutes-editor">

                <div className="ct-minutes-savebar" aria-label="整理内容保存">
                  <span>{calendarEditAll?`核对各项截止时间${minutesDirty?' · 尚未保存':''}`:calendarEditLine!==undefined?`修改这一项的截止时间${minutesDirty?' · 尚未保存':''}`:selectedDraft?.minutes?.[minutesViewMode]?.createManual?'自己写清单 · 尚未保存':minutesDirty ? '修改尚未保存' : '编辑整理内容'}</span>
                <div className="ct-button-row"><button type="button" className="ct-action ct-action-primary"
                  disabled={!minutesDirty || saveMeetingBusy || selectedRecordingBeingCaptured || calendarPendingCount>0 || !minutesDraft.trim() || (!!selectedDraft?.minutes?.[minutesViewMode]?.createManual && !savedActions(minutesDraft).length)} onClick={() => void saveMeetingDraft()}>{saveMeetingBusy ? '正在保存…' : selectedDraft?.minutes?.[minutesViewMode]?.createManual?'保存清单':calendarReturn?'保存修改并返回日历预览':'保存修改'}</button>
                  <button type="button" className="ct-action" disabled={saveMeetingBusy} onClick={() => cancelMeetingDraft('minutes')}>{calendarReturn?.fromPreview?'取消修改并返回日历预览':'取消'}</button></div>
                  {saveMeetingResult?.sessionId === selectedSession.id && saveMeetingResult.part === 'minutes' ?
                    <p className={saveMeetingResult.kind === 'error' ? 'ct-step-warn' : 'ct-step-ok'}
                      role={saveMeetingResult.kind === 'error' ? 'alert' : 'status'}>{saveMeetingResult.message}</p> : null}
                </div>
                {manualMinutes||selectedDraft?.minutes?.[minutesViewMode]?.createManual?<details className="ct-checklist-source" open={!calendarEditAll&&calendarEditLine===undefined}>
                  <summary>对照原话</summary><p className="ct-step-meta" style={{maxHeight:100,overflow:'auto',whiteSpace:'pre-wrap'}}>{companionReviewedTranscript(selectedSession)}</p>
                </details>:null}
                <MinutesContentEditor sourceSegments={selectedMinutesStale||transcriptReviewUnsaved?[]:transcriptSources} recordingTime={selectedSession.startedAt?recordingTimeLabel(selectedSession.startedAt):undefined} calendarOnly={calendarEditAll||calendarEditLine!==undefined} calendarAll={calendarEditAll} calendarLineIndex={calendarEditLine} calendarRequestTimed={calendarEditTimed} calendarRequestKey={calendarEditRequest??undefined} onCalendarPending={changeCalendarPending} manual={manualMinutes || !!selectedDraft?.minutes?.[minutesViewMode]?.createManual} markdown={minutesDraft} onChange={updateMinutesDraft} noteContext={calendarPendingCount>0 && minutesEntry && 'calendarContext'in minutesEntry?minutesEntry.calendarContext:minutesDisplayContext}
                  label={selectedDraft?.minutes?.[minutesViewMode]?.createManual?'自己写清单':`编辑${minutesViewMode === 'offlineStore' ? '先录后整理' : '在线速记'}纪要`} disabled={saveMeetingBusy} />

                {offlineMinutes && onlineMinutes ? <p className="ct-step-meta">只修改当前版本，另一份整理结果保持不变。</p> : null}
              </div> : !hasMinutes ? <p className="ct-step-meta" role="status">{busyAction === 'meetingGenerateMinutes' || recoveryView?.isProcessing
                  ? '正在整理已保存的文字…' : '点“整理重点”整理录音文字，原话保留。'}</p> : null}
              {!editingMinutes && saveMeetingResult?.sessionId === selectedSession.id && saveMeetingResult.part === 'minutes' ?
                <p className={saveMeetingResult.kind === 'error' ? 'ct-step-warn ct-editor-save-result' : 'ct-step-ok ct-editor-save-result'}
                  role={saveMeetingResult.kind === 'error' ? 'alert' : 'status'}>{saveMeetingResult.message}</p> : null}
              <textarea className="ct-minutes-output ct-machine-minutes" value={minutesMarkdown} readOnly aria-hidden="true" tabIndex={-1} />
            </MinutesModeTabs>
          </details> : null}
          </div>
          <div id="ct-meeting-handoff-pane" className="ct-meeting-pane" hidden={surface==='windows'&&meetingPane!=='handoff'}>
          {surface==='windows'?<header className="ct-pane-intro"><h3>导出文件</h3><p>选择要保存的纪要、文字或笔记。</p></header>:null}
          {hasMinutes||finalTranscript||hasPdfHighlights||selectedSession.meetingNotes?.length?<ContentExportPanel
            key={`${selectedSession.id}:${minutesViewMode}`}
            target={noteExportTarget?.sessionId===selectedSession.id?noteExportTarget:null} onClearTarget={()=>setNoteExportTarget(null)}
            standalone={surface==='windows'} sessionId={selectedSession.id} meetingMode={minutesViewMode}
            sourceVersion={JSON.stringify([copySourceKey,selectedSession.transcriptText,selectedSession.noteRevision,selectedSession.bookmarkRevision,selectedSession.transcriptReview?.revision,bookmarkUnsaved])}
            minutes={hasMinutes} transcript={finalTranscript} highlights={Boolean(selectedSession.bookmarks?.length)} timing={hasReviewedTiming}
            exactTiming={Boolean(finalTranscript&&companionReviewedUtterances(selectedSession).length&&!companionReviewedUtterances(selectedSession).some(row=>row.approximateTiming||row.endMs<=row.startMs))}
            notes={selectedSession.meetingNotes??[]} blocked={controlsBusy||oobeBlockedByRecording} desktopFileSharing={surface==='windows'}
            unsaved={{title:titleDirty,minutes:minutesDirty,transcript:transcriptReviewUnsaved,highlights:bookmarkUnsaved,notes:noteUnsaved}}
            onPreview={onPreviewMeetingExport} onSave={onExportMeeting} onCopy={onCopyMeetingContent} onShare={onShareMeetingContent}/>:null}
          {hasMinutes?<details id="ct-meeting-other-export" className="ct-result-tools">
              <summary>其它导出选项</summary>
          <div className="ct-document-actions">
            <span>导出其它内容</span>
            {savedActions(minutesMarkdown).length>0?<button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !hasMinutes || !onExportMeeting || selectedMinutesStale}
              title={!onExportMeeting ? '请在 Windows Companion Type 中保存文件' : undefined}
              onClick={() => void exportMeeting('markdown','documentTools')}><Download size={15} />{exportBusy ? '正在导出…' : '导出整理全文'}</button>:null}

            <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||!hasMinutes||!onExportMeeting}
              onClick={()=>void exportMeeting('docx','documentTools')}>导出 Word 文档</button>
            <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||!hasMinutes||!onExportMeeting}
              title="生成可由 FreeMind、Freeplane 等兼容软件打开的 .mm 文件" onClick={()=>void exportMeeting('mindmap','documentTools')}>导出思维导图（.mm）</button>

            {savedActions(minutesMarkdown).length>0?<button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !hasMinutes || !onExportMeeting || selectedMinutesStale || minutesIncomplete}
              title="导出文件后需导入日历，再核对日期与提醒" onClick={() => void exportMeeting('ics','documentTools')}>导出日历待办</button>:null}
            <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||!hasMinutes||!onExportMeeting}
              onClick={()=>void exportMeeting('txt','documentTools')}>{selectedSession.meetingNotes?.length?'导出原话与补充':'导出原话'}</button>
            <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||!hasMinutes||!onExportMeeting}
              onClick={()=>void exportMeeting('json','documentTools')}>保存完整数据（JSON）</button>
          </div>
          {renderExportFeedback('documentTools')}


            </details>:null}
          {!hasMinutes&&!finalTranscript&&!selectedSession.meetingNotes?.length&&surface==='windows'?<p className="ct-empty-state">文字或补充资料保存后，可以在这里选择并带走。原音可从下方录音工具保存。</p>:null}
          </div>
          <section id="ct-recording-text" className="ct-recording-text ct-meeting-pane" aria-label="录音文字" hidden={surface==='windows'&&meetingPane!=='source'}>
            {selectedUnrecognized.length ? <div className="ct-step-warn">
              <p role="status">{selectedUnrecognized.some(part=>part.source?.includes('转写失败'))
                ? '部分音轨转写失败，已有文字可以继续整理；原音已保留，可回听或重新转写。'
                : '部分时段未识别出文字，可能是安静或声音不清晰。已有文字可以继续整理；建议回听原音核对。'}</p>
              <details>
                <summary>查看全部 {selectedUnrecognized.length} 处未识别时段</summary>
                <div className="ct-button-row" aria-label="未识别时段">
                  {selectedUnrecognized.map((part,index)=><span key={`${part.startMs}:${part.endMs}:${part.source??''}:${index}`}>
                    <button type="button" className="ct-text-button"
                      aria-label={`定位第 ${index+1} 处未识别原音：${part.source ? `${part.source} ` : ''}${formatDuration(part.startMs)}至${formatDuration(part.endMs)}`}
                      disabled={Boolean(audioBlockedReason)||audioBusy||controlsBusy||storageBlocked}
                      title={audioBlockedReason??'定位原音后点击播放回听'} onClick={()=>void seekUnrecognized(part)}>
                      {part.source ? `${part.source} ` : ''}{formatDuration(part.startMs)}–{formatDuration(part.endMs)}
                    </button>
                    {onPreviewGap && part.source == null && selectedSession.source!=='hostMeeting' ?
                      <button type="button" className="ct-text-button" aria-label={`重新转写第 ${index+1} 处未识别时段`}
                        disabled={controlsBusy||oobeBlockedByRecording||storageBlocked||!canTranscribe||!hasOriginalAudio||Boolean(gapPreview)}
                        onClick={async()=>{
                          const sessionId=selectedSession.id,sourceText=selectedSession.transcriptText,sourceReview=JSON.stringify(selectedSession.transcriptReview??null);
                          setGapMessage(null);
                          try {const result=await onPreviewGap(sessionId,{startMs:part.startMs,endMs:part.endMs});
                            setGapPreview({sessionId,startMs:part.startMs,endMs:part.endMs,text:result.text,partial:result.unrecognized.length>0,sourceText,sourceReview});}
                          catch(error){setGapMessage({sessionId,text:`单段转写未完成：${operationErrorText(error,'general')}`});}
                        }}>重试这段</button>:null}
                  </span>)}
                </div>
                {onPreviewGap && selectedSession.source!=='hostMeeting' ? <p className="ct-step-meta">
                  {productSettings?.asrProvider==='local-paraformer'?'重试使用当前本地模型，只处理所选时段，不上传录音。相同模型和音频可能得到相同结果；可在设置中切换已配置的转写方式。':'重试使用当前转写服务，仅发送所选音频时段，可能产生费用。'}结果供核对，不会自动覆盖原文字。
                </p>:null}
              </details>
            </div> : null}
              {gapMessage?.sessionId===selectedSession.id?<p role="status">{gapMessage.text}</p>:null}
              {gapPreview?.sessionId===selectedSession.id ? <section id="ct-gap-preview" aria-label="单段重新转写结果">
                <p>{formatDuration(gapPreview.startMs)}–{formatDuration(gapPreview.endMs)} 的新结果，请回听核对后保存为备注。{finalTranscript
                  ? '重新整理时可选择一并参考已保存的补充；原始转写不会自动改变。'
                  : '这只是所选片段的参考，并非整场转写；原音和已有文字不会改变。'}</p>
                {gapPreview.partial?<p>这一时段仍有部分音频未识别出文字，请回听核对。</p>:null}
                <textarea className="ct-textarea ct-step-textarea" aria-label="单段转写文字" value={gapPreview.text}
                  onChange={event=>setGapPreview(current=>current?{...current,text:event.target.value}:current)}/>
                {gapPreview.sourceText!==selectedSession.transcriptText || gapPreview.sourceReview!==JSON.stringify(selectedSession.transcriptReview??null)
                  ? <p>原转写已变化；这是先前版本的参考结果，请重新核对。</p> : null}
                <div className="ct-button-row">
                  {onSaveNote?<button type="button" className="ct-text-button" disabled={gapSaving||controlsBusy||storageBlocked||!gapPreview.text.trim()
                    ||gapPreview.sourceText!==selectedSession.transcriptText||gapPreview.sourceReview!==JSON.stringify(selectedSession.transcriptReview??null)}
                    onClick={async()=>{
                      const text=normalizeCompanionNoteText(`单段重新转写参考（请回听核对） ${formatDuration(gapPreview.startMs)}–${formatDuration(gapPreview.endMs)}\n${gapPreview.text}`);
                      if([...text].length>4000){setGapMessage({sessionId:selectedSession.id,text:'内容超过备注长度，请复制需要的部分保存。'});return;}
                      const noteId=crypto.randomUUID();setGapSaving(true);setGapMessage(null);
                      try {const saved=await onSaveNote({sessionId:selectedSession.id,noteId,expectedRevision:selectedSession.noteRevision??0,action:'add',text,bookmarkId:null});
                        if(!saved.host.sessions.find(row=>row.id===selectedSession.id)?.meetingNotes?.some(row=>row.id===noteId&&row.text===text))throw new Error('尚未确认备注保存，请重试。');
                        setGapMessage({sessionId:selectedSession.id,text:'已保存为本机备注，原文字保持不变。'});setGapPreview(null);
                      } catch(error){setGapMessage({sessionId:selectedSession.id,text:operationErrorText(error,'save')});}finally{setGapSaving(false);}
                    }}>保存为备注</button>:null}
                  <button type="button" className="ct-text-button" onClick={()=>setGapPreview(null)}>关闭结果</button>
                </div>
              </section>:null}
            <div className="ct-recording-text-heading"><h3>{hasMinutes?'原话与补充':'文字'}</h3>
              <div className="ct-button-row">
                {companionReviewedTranscript(selectedSession).trim() || selectedSession.transcriptReview ? <button type="button" className="ct-text-button"
                  aria-expanded={transcriptReviewOpen} aria-controls="ct-recording-text-review"
                  onClick={()=>{setSourceSelection(null);setTranscriptReviewOpen(value=>!value);}}>{transcriptReviewOpen?'收起核对':'核对文字'}</button> : null}
              {onPreviewRetranscription && finalTranscript ? <button type="button" className="ct-text-button"
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !canTranscribe || Boolean(retranscriptionPreview)}
                title="使用当前选择的转写方式生成另一份文字；云端方式会发送录音。"
                onClick={async()=>{
                  if (!selectedSession) return;
                  const sessionId=selectedSession.id;setSaveMeetingResult(null);
                  const sourceText=selectedSession.transcriptText, sourceUtterances=structuredClone(selectedSession.utterances ?? []), revision=selectedSession.transcriptReview?.revision ?? 0;
                  try {const result=await onPreviewRetranscription(sessionId);setRetranscriptionPreview({sessionId,...result,sourceText,sourceUtterances,revision});}
                  catch(e) {setSaveMeetingResult({sessionId,kind:'error',message:`重新转写未完成：${operationErrorText(e,'general')}`});}
                }}>重新转写并对比</button>:null}
                {finalTranscript ? <button type="button" className="ct-text-button"
                  disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || (!hasMinutes && !canGenerate)}
                  title={hasMinutes?'重新整理，已有结果保留':'整理已保存的文字'}
                  onClick={() => {
                    if(snapshot?.minutesContextSupported && selectedSession.meetingNotes?.length){setPendingMinutesTemplate(undefined);setOrganizationChoiceId(selectedSession.id);}
                    else runOrganizationControl({action:'meetingGenerateMinutes',sessionId:selectedSession.id});
                  }}>{hasMinutes?'重新整理':'整理重点'}</button> : null}
                {finalTranscript && !hasMinutes && onSaveMeeting ? <button type="button" className="ct-text-button"
                  disabled={recordingControlBusy||selectedRecordingBeingCaptured||storageBlocked||!!selectedSession.captureIncomplete||!!selectedSession.recorderControlUncertain||transcriptReviewUnsaved||noteUnsaved||unimportedTranscriptDraft}
                  onClick={startManualChecklist}><Pencil size={14}/>自己写清单</button> : null}
                {finalTranscript && !hasMinutes ? <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !onExportMeeting || transcriptReviewUnsaved}
                  onClick={() => void exportMeeting('txt','text')}><Download size={15} />{exportBusy ? '正在导出…' : '导出文字'}</button> : null}
              </div>
            </div>

            {finalTranscript&&!readingPreview ? <details id="ct-meeting-templates" className="ct-library-more ct-template-picker" aria-label="选择整理视角">
              <summary>整理方式 · {templateId==='custom'?(customTemplate.name||'自定义'):({meeting:'会议',interview:'访谈',lecture:'课堂'}[templateId])} <span>切换模板</span></summary>
              <p className="ct-step-meta">选择整理侧重点；新结果会保留在这场录音中，已有结果可在历史里切回。</p>
              <label>整理视角 <select aria-label="整理视角" value={templateId} onChange={event=>{
                const value=event.target.value;
                if(value.startsWith('saved:')) {
                  const saved=savedCustomTemplates[Number(value.slice(6))];
                  if(saved){setCustomTemplate(saved);setTemplateId('custom');}
                } else if(value==='meeting'||value==='interview'||value==='lecture'||value==='custom') setTemplateId(value);
              }}>
                <option value="meeting">会议</option><option value="interview">访谈</option><option value="lecture">课堂</option><option value="custom">自定义</option>
                {savedCustomTemplates.length ? <optgroup label="已保存或恢复的自定义模板">{savedCustomTemplates.map((saved,index)=>
                  <option key={JSON.stringify([saved.name,saved.instructions])} value={`saved:${index}`}>{saved.name||'未命名模板'}{savedCustomTemplates.filter(item=>item.name===saved.name).length>1?` · 同名 ${savedCustomTemplates.slice(0,index+1).filter(item=>item.name===saved.name).length}`:''}</option>)}</optgroup> : null}
              </select></label>
              {templateId==='custom' ? <div className="ct-field">
                <label>模板名称<input aria-label="模板名称" value={customTemplate.name} onChange={event=>updateCustomTemplate({...customTemplate,name:event.target.value})}/></label>
                <label>整理要求<textarea aria-label="整理要求" value={customTemplate.instructions} onChange={event=>updateCustomTemplate({...customTemplate,instructions:event.target.value})}/></label>
                <p className="ct-step-meta">最近填写的模板保存在这台电脑，并随会议资料备份；已保存或恢复的模板版本可在此选择。</p>
                {templateSaveError ? <p role="status">模板未能保存到本机，本次整理仍可继续。</p> : null}
              </div> : null}
              <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||storageBlocked||!canGenerate||noteUnsaved||minutesDirty||titleDirty||transcriptReviewUnsaved||(templateId==='custom'&&(!customTemplate.name.trim()||!customTemplate.instructions.trim()))}
                onClick={()=>{
                  const template=templateId==='custom'?{id:templateId,name:customTemplate.name.trim(),instructions:customTemplate.instructions.trim()}:{id:templateId};
                  if(templateId==='custom') {try {localStorage.setItem('companion.minutes.customTemplate.v1',JSON.stringify(customTemplate));setTemplateSaveError(false);} catch {setTemplateSaveError(true);}}
                  runOrganizationControl({action:'meetingGenerateMinutes',sessionId:selectedSession.id,meetingMode:minutesViewMode,minutesTemplate:template});
                }}>按这个视角整理</button>
            </details> : null}
            {onPreviewRetranscription && finalTranscript ? <p className="ct-step-meta">{productSettings?.asrProvider === 'local-paraformer' ? '重新转写使用当前电脑本地模型，录音不会上传。' : '重新转写使用当前选定的云端服务，会发送录音并可能产生费用。'}</p> : null}
            {retranscriptionPreview && retranscriptionPreview.sessionId===selectedSession?.id ? <section aria-label="重新转写结果">
              <p>这是新生成的文字，尚未替换已保存的转写。采用后保留原始转写、原录音和备注；旧纪要保留，可按新文字重新整理。新文字暂时没有对应的分段时间。</p>
              {retranscriptionPreview.unrecognized.length ? <p className="ct-step-warn">{retranscriptionPreview.unrecognized.some(part=>part.source?.includes('转写失败'))
                ? '新转写有音轨处理失败；采用后仅保存已有文字，原音保留，可以再重试。'
                : '新转写有部分时段没有识别出文字，可能是安静或声音不清晰；采用后可继续整理，请回听核对。'}</p> : null}
              <textarea className="ct-textarea ct-step-textarea" readOnly aria-label="新转写结果" value={retranscriptionPreview.text} />
              <div className="ct-button-row">
                <button type="button" className="ct-action" disabled={!onSaveMeeting || controlsBusy || transcriptEditor.current.dirty || transcriptReviewUnsaved || Boolean(selectedSession?.transcriptReview && (selectedSession.transcriptReview.text || selectedSession.transcriptReview.utteranceEdits.length || selectedSession.transcriptReview.speakerNames.length))}
                  onClick={async()=>{
                    if(!onSaveMeeting || !selectedSession || !retranscriptionPreview) return;
                    const p=retranscriptionPreview;setSaveMeetingBusy(true);setSaveMeetingResult(null);
                    try {
                      const saved=await onSaveMeeting({sessionId:p.sessionId,transcriptReview:{expectedTranscriptText:p.sourceText,expectedUtterances:p.sourceUtterances ?? [],expectedRevision:p.revision,restoreOriginal:false,text:p.text,utteranceEdits:[],speakerNames:[],unrecognized:p.unrecognized}});
                      if(saved.host.persistence?.status && saved.host.persistence.status!=='ready') throw new Error('新文字尚未保存到磁盘，请重试。');
                      setRetranscriptionPreview(null);setSaveMeetingResult({sessionId:p.sessionId,kind:'saved',message:'新文字已保存为修订；原始转写和旧纪要保留，可按需重新整理。'});
                    } catch(e) {setSaveMeetingResult({sessionId:p.sessionId,kind:'error',message:`新文字未保存：${operationErrorText(e,'save')}`});}
                    finally {setSaveMeetingBusy(false);}
                  }}>采用新文字</button>
                <button type="button" className="ct-text-button" disabled={controlsBusy} onClick={()=>setRetranscriptionPreview(null)}>关闭结果</button>
              </div>
              {selectedSession?.transcriptReview && (selectedSession.transcriptReview.text || selectedSession.transcriptReview.utteranceEdits.length || selectedSession.transcriptReview.speakerNames.length) ? <p>这场录音已有人工修订，先保留原修订；新结果可复制出来比较。</p> : null}
            </section>:null}
            {organizationChoiceId===selectedSession.id?<div id="ct-organization-source-choice" className="ct-organization-choice" role="group" aria-label="本次整理内容">
              <strong>这次整理用哪些内容？</strong>
              <p>原话和补充仍分开保留。选择补充时，将当前已保存的内容一起用于这次整理。</p>
              <div className="ct-button-row">
                <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||storageBlocked||noteUnsaved||minutesDirty||transcriptReviewUnsaved}
                  onClick={()=>{setOrganizationChoiceId(null);runOrganizationControl({action:'meetingGenerateMinutes',sessionId:selectedSession.id,meetingMode:minutesViewMode,minutesTemplate:pendingMinutesTemplate},'original');setPendingMinutesTemplate(undefined);}}>仅原话</button>
                <button type="button" className="ct-action ct-action-primary" disabled={controlsBusy||oobeBlockedByRecording||storageBlocked||noteUnsaved||minutesDirty||transcriptReviewUnsaved||!selectedSession.meetingNotes?.length}
                  onClick={()=>{setOrganizationChoiceId(null);runOrganizationControl({action:'meetingGenerateMinutes',sessionId:selectedSession.id,meetingMode:minutesViewMode,
                    contextNoteRevision:selectedSession.noteRevision??0,minutesTemplate:pendingMinutesTemplate});setPendingMinutesTemplate(undefined);}}>原话＋已保存补充</button>
                <button type="button" className="ct-text-button" disabled={controlsBusy} onClick={()=>{setOrganizationChoiceId(null);setPendingMinutesTemplate(undefined);}}>取消</button>
              </div>
            </div>:null}
            {renderExportFeedback('text')}
            {transcriptDraftSessions.map(sessionId=>{
              const draftSession=readableLibrary.find(session=>session.id===sessionId);
              const current=sessionId===selectedSession.id;
              return <p className="ct-step-warn" role="status" key={sessionId}>
                {current?'有尚未保存的文字修订。':`“${draftSession?meetingTitle(draftSession):'另一条录音'}”有尚未保存的文字修订。`}
                {(!current||!transcriptReviewOpen)&&draftSession?<button type="button" className="ct-text-button" disabled={controlsBusy}
                  onClick={()=>resumeTranscriptDraft(sessionId)}>继续修正</button>:null}
              </p>;
            })}
            {selectedSession.status === 'recording' && selectedSession.meetingMode === 'onlineLive' && selectedSession.pendingReason === 'needs_transcription' ?
              <p className="ct-step-warn" role="status">实时转写已中断，录音会继续保存。结束后可以用完整录音重新转文字。</p> : null}
            {companionReviewedTranscript(selectedSession).trim() ? <>
              {!finalTranscript ? <p className="ct-step-warn">当前为片段文字，尚未完成整条转写。</p> : null}
              {companionTranscriptReviewIsStale(selectedSession) ? <p className="ct-step-warn">原始转写已更新，当前显示新文字；旧修订保留在“核对文字”中供查看。</p> : null}
              <div hidden={transcriptReviewOpen} className="ct-transcript-reading-tools" role="group" aria-label="转写阅读方式"><button type="button" className="ct-text-button" aria-pressed={transcriptCleanView} onClick={()=>setTranscriptCleanView(true)}>流畅阅读</button><button type="button" className="ct-text-button" aria-pressed={!transcriptCleanView} onClick={()=>setTranscriptCleanView(false)}>原始转写</button><details><summary>阅读说明</summary><span>流畅阅读略去长句中的停顿和重复起头，保留简短回应、引号内原话及数字条件。原始转写和导出仍完整保留。</span></details></div><div className="ct-recording-transcript" role="region" aria-label="录音转写文字" tabIndex={0} hidden={transcriptReviewOpen}>{transcriptParagraphs(transcriptCleanView?cleanHesitations(companionReviewedTranscript(selectedSession)).text:companionReviewedTranscript(selectedSession)).map((paragraph,index)=><p className="ct-transcript-paragraph" key={index}>{paragraph}</p>)}</div>{!readingPreview&&onSaveNote&&!transcriptReviewOpen&&<TranscriptQuoteCapture key={'manual-quote:'+selectedSession.id} contextId={selectedSession.id} text={companionReviewedTranscript(selectedSession)} busy={recordingControlBusy||storageBlocked||oobeBlockedByRecording} onQuote={draft=>{setManualEvidence(draft);revealMeetingTool('ct-recording-notes');}}/>}
            </> : <p className="ct-recording-text-empty">{transcriptionRunning||recoveryView?.isProcessing?'正在转成文字，请稍候。':selectedSession.status==='recording'?'正在录音，结束并保存后可以转成文字。':selectedSession.pendingReason==='needs_local_audio'?'原音已收齐。先生成回听文件，再回听或转文字。':['needs_device_sync','needs_segments','needs_pull'].includes(selectedSession.pendingReason??'')?'录音尚未收齐，先从来源设备同步，再回听或转文字。':!hasSyncedAudio?'还没有可回听的本机录音，请先确认录音已保存。':selectedSession.pendingReason==='no_speech_detected'?'这次没有识别出文字。原录音仍在，可回听后决定是否重试。':'原音已保留，可以先回听。点“转文字”后，可整理纪要、提取待办或向这场会议提问。'}</p>}
          {transcriptUnmappedEdges.length > 0 ? <div className="ct-step-warn" role="status" aria-label="原音与文字的时间对应">
            {transcriptUnmappedEdges.map(edge => <p key={edge.edge}>
              {edge.edge === 'start' ? '开头' : '结尾'}约 {Math.ceil(edge.durationMs / 1000)} 秒原音没有对应的识别时间标记，可能也有停顿。原音已保留，可回听核对。
            </p>)}
            <button type="button" className="ct-text-button" disabled={Boolean(audioBlockedReason) || audioBusy || controlsBusy || storageBlocked}
              onClick={() => { setPlaybackOpen(true); if (!preparedAudio) void prepareAudio(); }}>核对原音</button>
          </div> : null}
          <div id="ct-recording-text-review" tabIndex={-1} hidden={!transcriptReviewOpen}>
          <CompanionTranscriptReview session={selectedSession} visible={transcriptReviewOpen}
            blocked={recordingControlBusy || selectedRecordingBeingCaptured || storageBlocked}
            sourceSelection={sourceSelection} onSeekSource={seekTranscriptSource}
            lookupKind={transcriptLookup?.returnId==='ct-recording-notes'?'note':'minutes'}
            lookup={transcriptLookup?.sessionId===selectedSession.id?transcriptLookup:null}
            onReturnLookup={()=>{if(transcriptLookup?.returnId==='ct-recording-notes'){revealMeetingTool('ct-recording-notes');return;}setMeetingPane('result');setRecordingResultOpen(true);window.requestAnimationFrame(()=>{const target=transcriptLookup?.returnId?document.getElementById(transcriptLookup.returnId):document.getElementById('ct-recording-result');target?.scrollIntoView({block:'center'});target?.focus({preventScroll:true});});}}
            audioSeekBlocked={Boolean(audioBlockedReason) || audioBusy}
            onSave={onSaveMeeting} onUnsavedChange={setTranscriptReviewUnsaved} onDraftSessionsChange={setTranscriptDraftSessions} />
          </div>
          </section>
          <div id="ct-meeting-materials-pane" className="ct-meeting-pane" hidden={surface==='windows'&&meetingPane!=='materials'}>
          <MeetingReferenceWorkspace id="ct-recording-references" view={referenceView} onViewChange={setReferenceView} notes={<CompanionMeetingNotes incoming={manualEvidence} onIncomingConsumed={()=>setManualEvidence(undefined)} onOpenEvidence={onCheckNoteEvidence?async(noteId,reference,revision)=>{
              await onCheckNoteEvidence(selectedSession.id,noteId,reference.id,revision);
              if(reference.kind==='document'){setDocumentSource({id:reference.documentId,contextId:selectedSession.id,quote:reference.quote,nonce:crypto.randomUUID(),evidence:reference});revealMeetingTool('ct-document-context');}
              else{setMeetingPane('source');setTranscriptReviewOpen(true);setTranscriptLookup({id:crypto.randomUUID(),text:reference.quote,sessionId:selectedSession.id,returnId:'ct-recording-notes'});window.requestAnimationFrame(()=>document.getElementById('ct-recording-text-review')?.scrollIntoView({block:'start'}));}
            }:undefined} searchTerm={libraryQuery} resultEditLabel={hasMinutes?(savedActions(minutesMarkdown).length?'编辑清单':'编辑整理内容'):undefined} compact session={selectedSession} blocked={recordingControlBusy} anyRecording={oobeBlockedByRecording} onHelp={openQuickGuide}
            persistenceReady={!storageBlocked} onSave={onSaveNote} onAddImage={onAddImageNote} onPreviewImage={onPreviewNoteImage} onBusyChange={setNoteBusy} onUnsavedChange={setNoteUnsaved}
            onSaveAnchor={onSaveBookmark} playbackPosition={readBookmarkPosition}
            onOrganizeSaved={snapshot?.minutesContextSupported && finalTranscript && Number.isFinite(selectedSession.durationMs)
              && selectedSession.durationMs>=0 && selectedSession.durationMs<=120000 ? ()=>runOrganizationControl({
                action:'meetingGenerateMinutes',sessionId:selectedSession.id,meetingMode:minutesViewMode,
                contextNoteRevision:selectedSession.noteRevision??0}) : undefined}
            organizeSavedBlocked={controlsBusy||oobeBlockedByRecording||storageBlocked||noteUnsaved||minutesDirty||titleDirty
              ||transcriptReviewUnsaved||unimportedTranscriptDraft}
            onExportNote={onPreviewMeetingExport?noteId=>{setMeetingPane('handoff');setNoteExportTarget({requestId:crypto.randomUUID(),sessionId:selectedSession.id,noteId});}:undefined}
            onSeek={seekBookmark} onExport={onExportMeeting&&!hasMinutes?(format)=>exportMeeting(format,'notes'):undefined}
            exportFeedback={exportResult?.sessionId===selectedSession.id&&exportResult.origin==='notes'?exportResult:null}/>} documents={documentAdapter&&!readingPreview?<div id="ct-document-context"><DocumentContextPanel key={'documents:'+selectedSession.id} contextId={selectedSession.id} adapter={documentAdapter(selectedSession.id)} busy={controlsBusy||storageBlocked||oobeBlockedByRecording} onQuote={draft=>{setManualEvidence(draft);revealMeetingTool('ct-recording-notes');}} openSource={documentSource} onChanged={onRefresh}/></div>:null} assistant={onAskMeetings&&selectedSession&&(finalTranscript||documentScopes.length>0) ? <div id="ct-meeting-qa"><MeetingAiWorkbench key={selectedSession.id}
              contextId={selectedSession.id} contextVersion={selectedSession.id} title={meetingTitle(selectedSession)}
              scopes={[...qaEligibleSessions.map(row=>({id:row.id,title:meetingTitle(row),binding:qaIdentity([row.id])})),...documentScopes]}
              serviceReady={!!productSettings?.deepseekMinutesEnabled&&!!productSettings?.deepseekApiKeySet} busy={controlsBusy||storageBlocked} preview={readingPreview}
              onSetup={()=>{setShowAdvanced(true);setSettingsReturn('recording');navigatePage('settings','ct-service-settings');}}
              onAsk={async(question,ids,jobId,resume)=>{const source=qaIdentity(ids);setQaBusy(true);try{const result=await onAskMeetings(question,ids,jobId,resume?.resume?{...resume.resume,items:resume.items}:undefined);
                if(ids.some(id=>id.startsWith('document:')?!qaSessionsRef.current.some(row=>!row.organization?.trashedAt&&(row.documentContext?.rows??[]).some(doc=>'document:'+row.id+':'+doc.id===id&&!!doc.extraction)):!qaSessionsRef.current.some(row=>row.id===id&&!row.organization?.trashedAt&&companionSessionHasFinalTranscript(row))))throw Error('来源会议或材料已移除，请重新选择。');
                return {...result,jobId};}finally{setQaBusy(false);}}}
              onCancel={onCancelMeetingQuestion}
              onOpenDocuments={documentAdapter&&!readingPreview?()=>revealMeetingTool('ct-document-context'):undefined}
              onOpenNotes={()=>revealMeetingTool('ct-recording-notes')}
              onOpenSource={(id,quote)=>{if(id.startsWith('document:')){setDocumentSource({id:id.slice(id.lastIndexOf(':')+1),quote,nonce:crypto.randomUUID()});revealMeetingTool('ct-document-context');return;}setQaPendingCitation({sessionId:id,title:meetingTitle(allLibrarySessions.find(row=>row.id===id)??selectedSession),quote});setOpenSavedRecordingId(id);setOpenSavedRecordingTarget('source');if(selectedSession.id!==id)onControl({action:'meetingSelectSession',sessionId:id});}}
              onLoadSaved={async()=> (selectedSession.meetingNotes??[]).map(readMaterialNote).filter((value):value is NonNullable<typeof value>=>value!==null)}
              onSave={async value=>{if(!onSaveNote)throw Error('当前环境未提供材料保存，请复制文字保留。');const source=qaSessionsRef.current.find(row=>row.id===selectedSession.id&&!row.organization?.trashedAt);if(!source)throw Error('当前会议已移除，未保存到其他会议。');
                const note=materialNote(value),saved=await onSaveNote({sessionId:source.id,noteId:value.id,expectedRevision:source.noteRevision??0,action:'add',text:note,bookmarkId:null});
                const row=saved.host.sessions.find(row=>row.id===source.id)?.meetingNotes?.find(n=>n.id===value.id&&n.text===note);if(!row)throw Error('材料尚未确认保存，请保留输入后重试。');return readMaterialNote(row)??undefined;}}
            /></div>:null}/>


          {finalTranscript && selectedSession.meetingNotes?.length ? <p className="ct-step-meta">
            {snapshot?.minutesContextSupported?'补充单独保存；整理时可选择仅用原话，或一起参考已保存补充。':'补充已单独保存；当前整理程序仅使用原话。'}
          </p> : null}
          </div>
          <details className="ct-meeting-audio-edit" hidden={surface==='windows'&&meetingPane!=='source'}><summary>剪辑与音频处理{audioEditUnsaved?' · 有未保存的修改':''}</summary>
          {renderAudioEditor&&!readingPreview&&(hasOriginalAudio||selectedSession.source==='derivedAudio')&&!selectedSession.captureIncomplete&&!selectedSession.recorderControlUncertain?
            renderAudioEditor({contextId:selectedSession.id,title:selectedSession.title,canEdit:hasOriginalAudio,rows:recordingLibrary.map(row=>({key:row.id,title:row.title,state:row.audioStored&&row.retention.audioCached&&!row.captureIncomplete&&!row.recorderControlUncertain&&row.status!=='recording'&&!['needs_device_sync','needs_local_audio','needs_segments'].includes(row.pendingReason??'')?'COMPLETE':'INCOMPLETE'})),
              busy:controlsBusy||storageBlocked||oobeBlockedByRecording||noteUnsaved||minutesDirty||titleDirty||transcriptReviewUnsaved,
              onChanged:onRefresh,onLibrary:()=>{setDetailSessionId(null);navigatePage('library');},onDirty:setAudioEditUnsaved,onSource:openEditSource}):null}
          </details>
          <details className="ct-recording-more" open={recordingToolsOpen} onToggle={event=>setRecordingToolsOpen(event.currentTarget.open)}>
            <summary>录音与高级工具{titleDirty||minutesDirty||bookmarkUnsaved||noteUnsaved?' · 有未保存的修改':''}</summary>
            {journey?.optional && finalTranscript ? <CompanionJourney journey={journey} hideAction={journeyRepeatsPrimaryTranscription} blocked={controlsBusy || oobeBlockedByRecording || storageBlocked}
            onControl={runOrganizationControl} onSettings={openSettings} onWorkflow={openWorkflow} /> : null}
            {savedOriginalReady ? <RecordingSafetyCard session={selectedSession} persistence={snapshot?.host.persistence} recoveryProcessing={Boolean(recoveryView?.isProcessing)} /> : null}
            <div id="ct-recording-audio-export" className="ct-recording-audio-export" tabIndex={-1}>
            <label>音频格式 <select aria-label="音频副本格式" value={audioExportFormat} disabled={controlsBusy||oobeBlockedByRecording} onChange={e=>setAudioExportFormat(e.currentTarget.value as 'original'|'mp3')}><option value="original">原文件 / WAV / 分段ZIP</option><option value="mp3">MP3 兼容副本（有损）</option></select></label>
            <button type="button" className="ct-action" disabled={!onExportAudio || !hasOriginalAudio || controlsBusy || oobeBlockedByRecording}
              onClick={() => void exportAudio(audioExportFormat)}><Download size={15} />{audioExportFormat==='mp3'?'保存 MP3 副本':selectedSession.source === 'hostMeeting' ? '保存会议录音' : '保存原音'}</button>
            <button type="button" className="ct-action" disabled={!onShareAudio||!hasOriginalAudio||controlsBusy||oobeBlockedByRecording} onClick={()=>void shareAudio(surface==='windows'?'clipboard':'system')}>{surface==='windows'?'复制录音文件':'分享录音…'}</button>
            {onShareAudio?<details><summary>其他录音分享方式</summary>
              <button type="button" className="ct-action" disabled={!hasOriginalAudio||controlsBusy||oobeBlockedByRecording} onClick={()=>void shareAudio(surface==='windows'?'system':'clipboard')}>{surface==='windows'?'系统分享录音…':'复制录音文件'}</button>
              <button type="button" className="ct-action" disabled={!hasOriginalAudio||controlsBusy||oobeBlockedByRecording} onClick={()=>void shareAudio('folder')}>在文件夹中分享录音…</button>
            </details>:null}
            {renderExportFeedback('audio')}
            <p>{selectedSession.source === 'hostMeeting' ? '保存电脑声音与麦克风的混合录音；超出 WAV 格式容量时保存为包含两路分段原音的 ZIP。' : '保存整场原音到你选择的位置，可单独备份或使用其他播放器打开。超出 WAV 格式容量时会保存为包含分段原音的 ZIP。'}此副本由你自行保管，删除录音不会删除它。</p>
            </div>
          <CompanionBookmarks session={selectedSession} blocked={controlsBusy} anyRecording={oobeBlockedByRecording}
            persistenceReady={!storageBlocked} onSave={onSaveBookmark} onBusyChange={setBookmarkBusy} onUnsavedChange={setBookmarkUnsaved}
            playbackPosition={readBookmarkPosition}
            onSeek={seekBookmark} onShowOriginal={()=>setRecordingToolsOpen(true)}
            onExport={onExportMeeting?()=>exportMeeting('json','bookmarks'):undefined}/>
          {renderExportFeedback('bookmarks')}
          {selectedSession.recovery?.lastError ? <details className="ct-recovery-detail">
            <summary>查看处理失败的说明</summary><p>{operationErrorText(selectedSession.recovery.lastError)}</p>
            <small>已尝试 {selectedSession.recovery.attemptCount} / {selectedSession.recovery.maxAttempts} 次；已有内容仍保留在本机。</small>
          </details> : null}
          <div className="ct-document-actions">
            <span>保存当前转写；完整记录包含原始识别结果</span>
            <button type="button" className="ct-action" title={selectedSession.utterances?.some(u=>u.approximateTiming)?'本地转写只有近似分段位置，不能生成精确字幕。':undefined} disabled={controlsBusy || oobeBlockedByRecording || !finalTranscript || !companionReviewedUtterances(selectedSession).length || companionReviewedUtterances(selectedSession).some(u=>u.approximateTiming) || !onExportMeeting || transcriptReviewUnsaved}
              onClick={() => void exportMeeting('srt','recordingTools')}>保存字幕</button>
            <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !finalTranscript || !onExportMeeting || transcriptReviewUnsaved}
              onClick={() => void exportMeeting('json','recordingTools')}>保存完整记录</button>
          </div>
          {renderExportFeedback('recordingTools')}

          </details>
        </section>
      ) : null}

      </div>

      <section id="ct-device-recording-page" tabIndex={-1} className="ct-page-panel" hidden={pageView !== 'device'} aria-label="设备与同步内容">
      <header className="ct-page-heading"><h2>录音卡</h2><p>连接卡片，录下声音。已收到的内容保存在“录音”中。</p></header>
      {renderRecordingReadiness()}
      <div className={surface === 'windows' ? 'ct-device-actions' : undefined}>
      {!oobeBlockedByRecording ? <section className="ct-recording-activity" aria-label="在卡片上录音">
        <div><strong>在卡片上录音</strong>
          <p>{recorderKeyGuide(device).start} {recorderKeyGuide(device).stop}</p>
          <p>离线也能录。连接后录音会自动保存到本机，可在“我的记录”回听和整理。</p>
        </div>
        <div className="ct-button-row">
          {surface !== 'windows' && devicePageConnected ? <button type="button" className="ct-action ct-action-primary"
            disabled={controlsBusy || storageBlocked || !device?.deviceId}
            onClick={() => onControl({action:'deviceSyncRecordings',deviceId:device?.deviceId??undefined})}>
            <Download size={16} /><span>接收设备录音</span>
          </button> : null}
          {surface!=='windows'||!devicePageConnected?<button type="button" className="ct-action" onClick={()=>{setDetailSessionId(null);navigatePage('library');}}>查看我的记录</button>:null}
        </div>
        <details className="ct-setup-details">
          <summary>远程控制卡片录音</summary>
          <p>需要从电脑或手机控制卡片时，可在这里远程开录。平时直接使用卡片按键。</p>
          {!durationValid && !unlimitedDeviceRecording ? <p role="alert">请输入有效的远程录音时长。</p> : null}
          <button type="button" className="ct-action"
            disabled={controlsBusy || storageBlocked || !devicePageConnected || !device?.deviceId || (!unlimitedDeviceRecording && !durationValid)}
            onClick={() => onControl({ action: 'meetingStart', meetingMode: 'offlineStore',
              promptId: COMPANION_CAPTURE_ONLY_PROMPT,
              deviceId: device?.deviceId ?? undefined, title: newMeetingTitle.trim() || 'Companion 录音', durationMs: unlimitedDeviceRecording ? 0 : requestedDurationMs })}>
            <Mic size={16} /><span>远程开始录音</span>
          </button>
        </details>
      </section> : null}

      {surface === 'windows' ? <details className="ct-alternative-recording" open={recordingAlternativesOpen}
        onToggle={event=>setRecordingAlternativesOpen(event.currentTarget.open)}><summary>电脑录音与文件导入</summary>
      {!oobeBlockedByRecording ? <section className="ct-recording-activity" aria-label="录制电脑会议">
        <div><strong>录制电脑会议</strong>
          <p>同时保存电脑播放的声音和本机麦克风，结束后可回听、转文字和整理纪要。电脑播放的其他声音也会录进去。</p></div>
        <div className="ct-button-row"><button type="button" className="ct-action" disabled={controlsBusy || storageBlocked}
          onClick={() => onControl({action:'meetingStart',recordingSource:'hostMeeting',meetingMode:'offlineStore',
            promptId:COMPANION_CAPTURE_ONLY_PROMPT,title:newMeetingTitle.trim() || '电脑会议录音',durationMs:0})}>
          <Mic size={16}/><span>开始录电脑会议</span></button></div>
      </section> : null}

      {surface === 'windows' && onImportAudio ? <section id="ct-audio-import" tabIndex={-1} className="ct-recording-activity" aria-label="导入已有音频">
        <div><strong>导入已有音频</strong><p>选择 WAV、MP3、M4A、AAC、FLAC 或 OGG（Vorbis），保存后可回听、转写并整理纪要。原文件保留，回听与转写使用本机生成的单声道副本；可单独保存原文件。</p>
          {importAudioMessage ? <p role="status">{importAudioMessage}</p> : null}</div>
        <button type="button" className="ct-action" disabled={importingAudio || storageBlocked}
          onClick={() => { if (importingAudio) return; setImportingAudio(true); setImportAudioMessage('正在保存并准备音频…');
            void onImportAudio().then(result => setImportAudioMessage(result ? '音频已保存，可在录音资料中回听和转写。' : '')).
              catch(error => setImportAudioMessage(`导入未完成：${operationErrorText(error,'save')}`)).finally(() => setImportingAudio(false)); }}>
          {importingAudio ? '正在导入…' : '选择音频文件'}</button>
        {importingAudio && onCancelImportAudio ? <button type="button" className="ct-action" onClick={() => { void onCancelImportAudio().then(ok => {if(ok)setImportAudioMessage('正在取消，原文件会保留。');}).catch(() => setImportAudioMessage('暂时无法取消，请稍候。')); }}>取消导入</button> : null}
      </section> : null}

      </details> : null}
      </div>

      {surface === 'windows' ? <details className="ct-device-options ct-sync-details" open={syncDetailsOpen}
        onToggle={event=>setSyncDetailsOpen(event.currentTarget.open)}>
        <summary>查看同步详情</summary>
        {syncDetailsOpen && pageView === 'device' ? <>
          {renderRecordingSync()}
          {!recordingSync || recordingSync.phase === 'idle' ? <p>{recordingSync?.phase === 'idle' ? '当前没有正在收取的录音。' : '连接后会自动收取录音。'}</p> : null}
          {devicePageConnected && device?.deviceId ? <button type="button" className="ct-text-button"
            disabled={controlsBusy || storageBlocked || oobeBlockedByRecording}
            onClick={()=>onControl({action:'deviceSyncRecordings',deviceId:device.deviceId??undefined})}>检查设备录音</button> : null}
        </> : null}
      </details> : null}

      <details className="ct-device-options" open={device?.connectionPhase==='pairingRequired'}><summary>配对与设备设置</summary>
      <CompanionSetup snapshot={snapshot} settings={productSettings} busy={controlsBusy}
        recording={oobeBlockedByRecording} checking={busyAction === 'oobeRunChecks'} onControl={onControl}
        onSettings={openSettings} onLibrary={() => {setDetailSessionId(null);navigatePage('library');}} />
      {deviceExtra}
      {onFindPet && connected && device?.deviceId ? <CompanionPetFind
        deviceId={device.deviceId} supported={snapshot?.source==='firmware' && snapshot.speaker.findSupported===true}
        blocked={controlsBusy||oobeBlockedByRecording} muted={snapshot?.speaker.muted!==false||snapshot.speaker.volume===0}
        onFind={onFindPet} /> : null}
      </details>

      <button type="button" className="ct-workflow-toggle" onClick={() => setShowWorkflow((value) => !value)}>
        <span><HardDrive size={16} />更多录音与处理操作</span><span>{showWorkflow ? '收起' : '录音 · 同步 · 整理'}</span>
      </button>

      {showWorkflow ? <section className="ct-steps" id="ct-workflow" tabIndex={-1} aria-label="主路径步骤">
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
            <strong>录音与同步</strong>
            <p>
              使用 Companion 录音，电脑同步显示转写。停止后自动收齐录音并整理纪要；也可以先在设备上录好，再同步到电脑。
            </p>
            <div className="ct-meeting-grid">
              <label className="ct-field"><span>这次会议的名称（可选）</span><input value={newMeetingTitle}
                placeholder="例如：周会、一次灵感" maxLength={120} disabled={oobeBlockedByRecording || controlsBusy}
                onChange={(event) => setNewMeetingTitle(event.target.value)} /></label>
              {!unlimitedDeviceRecording ? <label className="ct-field ct-duration-field"><span>最长录制时间（分钟）</span><input value={draftMinutes}
                inputMode="numeric" disabled={oobeBlockedByRecording || controlsBusy} aria-invalid={Boolean(durationError)} aria-describedby={durationError ? "ct-workflow-duration-error" : undefined}
                onChange={(event) => setDraftMinutes(event.target.value.replace(/[^0-9]/g, ''))} /></label> : null}
            </div>
            <p className="ct-step-meta">{unlimitedDeviceRecording ? '不预设录音结束时间；空间不足时设备会结束录音并保留已有内容。' : '当前设备在线转写单次最多 43 分钟，另预留 2 分钟收尾空间。'}支持分段的设备会把片段放在同一条录音里；电脑保存并核对完整后，设备才复用这些已同步的空间。</p>
            {captureBudgetBytes !== null ? <p className="ct-step-meta" role={capacityInsufficient && (!capacity?.segmentFrames || capacitySeconds <= 0) ? 'alert' : undefined}>
              {capacity?.segmentFrames && capacity.segmentExtentBytes ? <>
                设备上次报告{fragmentedCapacity ? '一块连续空间' : '本地'}可录约 {formatDuration(capacitySeconds * 1000)}，本次计划 {formatDuration(requestedDurationMs)}。
                {fragmentedCapacity ? '分散空间能否合用由开始时核对。' : ''}
                保持连接并开启同步可边录边上传；断开或暂停同步后使用本地空间，满时安全停录。
                开始前会按当前同步状态重新核对空间，不会覆盖未上传录音。
              </> : <>
                本次需预留约 {formatBytes(captureBudgetBytes)}{meetingMode === 'onlineLive' ? '（含收尾空间）' : ''}；
                设备上次报告连续可录约 {formatDuration(capacitySeconds * 1000)}。
                {capacityInsufficient ? '当前容量不足，请先同步已有录音或缩短时长；不会自动缩短或覆盖录音。' : '开始前会重新核对容量。'}
              </>}
            </p> : null}
            {durationError ? <p id="ct-workflow-duration-error" className="ct-step-meta" role="alert">{durationError}</p> : null}
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !connected || !cloudAsrConfigured || productSettings?.asrProvider === 'local-paraformer' || !onStartBoardOnlineLive || !onlineDurationValid}
                onClick={() => onStartBoardOnlineLive?.({
                  title: newMeetingTitle.trim() || 'Companion 会议',
                  deviceId: device?.deviceId,
                  maxDurationSeconds: unlimitedDeviceRecording ? 0 : boardMaxDurationSeconds,
                  partialIntervalMs: 8_000,
                })}
                title={!connected ? '请先连接 Companion' : productSettings?.asrProvider === 'local-paraformer' ? '本地转写在录音结束后处理' : !cloudAsrConfigured ? '请先配置转写服务；也可以直接在设备上录音' : '使用 Companion 麦克风开始在线会议'}
              >
                <Mic size={16} />
                <span>开始在线会议</span>
              </button>
              <button
                type="button"
                className="ct-action"
                disabled={recordingControlBusy || boardOnlineLive?.state !== 'recording' || !onStopBoardOnlineLive}
                onClick={() => onStopBoardOnlineLive?.()}
              >
                <Square size={16} />
                <span>停止并生成纪要</span>
              </button>
            </div>
            {productSettings?.asrProvider === 'local-paraformer' ? <p className="ct-step-meta">本地转写在录音结束后处理。你可以先在设备上录音，稍后同步。</p>
              : !cloudAsrConfigured ? <p className="ct-step-meta">在线转写需要服务配置。你也可以先在设备上录音，稍后同步。<button type="button" className="ct-text-button" onClick={openSettings}>配置转写服务</button></p> : null}
            {boardOnlineLive && boardOnlineLive.state !== 'idle' ? (
              <div className="ct-live-box" aria-label="板端在线会议状态">
                <strong role="status">
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
                  {boardOnlineLive.error ? ` · ${operationErrorText(boardOnlineLive.error,'recording')}` : ''}
                </div>
              </div>
            ) : null}
            <p className="ct-step-meta">{unlimitedDeviceRecording ? '实时转写随录音持续，手动停止或空间不足时结束。' : `这次实时转写上限 ${Math.ceil(boardMaxDurationSeconds / 60)} 分钟；可以提前停止，设备设置或空间不足也可能更早结束。`}已有板端录音仍可单独同步：</p>
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
              const utterances = (selectedSession ? companionReviewedUtterances(selectedSession) : []).filter(u=>!u.approximateTiming);
              const taggedLines = (selectedSession ? companionReviewedTranscript(selectedSession) : transcriptDraft || '')
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
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !canTranscribe || finalTranscript}
                onClick={() => onControl({ action: 'meetingTranscribeAudio', sessionId: selectedSession?.id })}
              >
                <FileText size={16} />
              <span>{selectedSession?.captureIncomplete ? '转写已保存的片段' : '转写'}</span>
              </button>
              {onRefineSpeakers ? <button type="button" className="ct-action"
                title={selectedSession?.utterances?.some(u=>u.approximateTiming)?'本地转写只有近似分段位置，暂不能据此区分说话人。':'只用已保存原音在电脑本地区分，不重新转写或上传；旧纪要保留为待更新草稿。'}
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked || !selectedSession?.audioStored
                  || !selectedSession.transcriptFinal || !selectedSession.utterances?.length || selectedSession.utterances.some(u=>u.approximateTiming)
                  || companionTranscriptReviewRevision(selectedSession)!==null || titleDirty || minutesDirty || transcriptEditor.current.dirty}
                onClick={async()=>{
                  if (!selectedSession) return;
                  const sessionId=selectedSession.id;setSaveMeetingBusy(true);setSaveMeetingResult(null);
                  try {await onRefineSpeakers(sessionId);setSaveMeetingResult({sessionId,kind:'saved',message:'已在本机重新区分说话人；原音、文字和时间轴保留，之前的纪要可按需重新生成。'});}
                  catch (e) {setSaveMeetingResult({sessionId,kind:'error',message:`本地分组未完成：${operationErrorText(e,'save')}`});}
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
                onClick={() => void exportMeeting('markdown','workflow')}
              >
                <Download size={16} />
                <span>导出 Markdown</span>
              </button>
            </div>
            {renderExportFeedback('workflow')}
            {recordingMinutesUserEdited ? <p className="ct-step-warn">录制模式（{recordingModeLabel}）纪要含人工修改。重新整理后可在“以前的整理结果”中查看原内容。</p> : null}
          </div>
        </div>
      </section> : null}

      </section>

      <section className="ct-page-panel" hidden={pageView !== 'settings'} aria-label="设置与工具内容"><header className="ct-page-heading"><h2>设置</h2><p>管理这台电脑的转写、纪要服务与设备选项。</p></header>
      {surface !== 'windows' ? <button
        type="button"
        className="ct-advanced-toggle"
        onClick={() => setShowAdvanced((value) => !value)}
      >
        {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        <span>{showAdvanced ? '收起高级功能' : '展开设置与工具'}</span>
      </button> : null}

      {showAdvanced ? (
        <div className="ct-advanced">
          <section className="ct-panel" id="ct-service-settings" tabIndex={-1} aria-label="转写与纪要服务">
            {surface !== 'windows' || settingsReturn ? <button type="button" className="ct-text-button ct-return-recording"
              onClick={surface === 'windows' && settingsReturn === 'device' ? openDeviceRecording : returnToRecording}>
              ← {surface === 'windows' && settingsReturn === 'device' ? '返回设备与同步' : '返回录音'}
            </button> : null}
            <div className="ct-panel-title">
              <Shield size={18} />
              <span>转写与纪要服务</span>
            </div>
            {productSettings?.storageWarning ? <p className="ct-step-warn" role="alert">
              {operationErrorText(productSettings.storageWarning,'settings')}
            </p> : null}
            {surface === 'windows' ? <>
              <div className="ct-service-guide"><strong>选择适合你的整理方式</strong><p>本地中文转写不上传录音、无需服务密钥，首次需要下载模型。云端转写会发送录音；智能纪要会发送转写文字，所选服务可能产生费用。</p></div>
              <details className="ct-service-privacy"><summary>数据与密钥如何使用</summary><p>正式桌面版使用系统凭据管理器保存密钥。使用自备或兼容服务时，数据会离开 Companion Type，交给你填写的服务地址；保留期限、访问控制与可用性由服务提供者或你的部署负责。空密钥保存不会覆盖已有值。</p></details>
            </> : <><p className="ct-secret-hint">
              正式桌面版使用系统凭据管理器保存密钥。本地转写不会上传录音；选择云端转写时录音会发送到所选服务，智能纪要会把转写文字发送到 DeepSeek。空密钥保存不会覆盖已有值。
            </p><p className="ct-service-boundary">使用自备或兼容服务时，数据会离开 Companion Type 并交给你填写的服务地址；该服务的保留期限、访问控制与可用性由服务提供者或你的部署负责。</p></>}
            {surface==='windows'?<><label className="ct-field-check">
              <input type="checkbox" checked={formAutoLocalCard} onChange={e=>setFormAutoLocalCard(e.target.checked)} />
              接收卡片录音后，自动在这台电脑转写
            </label>
            <p className="ct-step-meta">仅使用本机中文模型，不上传录音，也不自动生成云端纪要。首次准备模型后，新接收的卡片录音会自动生成文字；已选择手动处理的记录保持原选择。</p></>:null}
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
                <span>{surface === 'windows' ? '转写方式' : 'ASR 提供商'}</span>
                <select value={formAsrProvider} onChange={(e) => setFormAsrProvider(e.target.value)}>
                  <option value="volcengine">火山 Volcengine</option>
                  <option value="openai-compatible">OpenAI 兼容</option>
                  <option value="local-paraformer">电脑本地转写（中文）</option>
                </select>
              </label>
              {formAsrProvider === 'local-paraformer' || (surface==='windows' && formAutoLocalCard) ? <div className="ct-field">
                <span>{productSettings?.localAsrAvailable ? '本地模型已准备' : '需要准备本地模型'}</span>
                <button type="button" className="ct-text-button" disabled={controlsBusy || settingsBusy || oobeBlockedByRecording || !onPrepareLocalAsr}
                  onClick={() => { if (!onPrepareLocalAsr) return; setSettingsBusy(true); setSettingsMsg(null);
                    void onPrepareLocalAsr().then(() => setSettingsMsg('本地中文转写模型已准备。'))
                      .catch(() => setSettingsMsg('本地模型准备未完成，请检查网络和存储空间后重试；已有录音会保留。')).finally(() => setSettingsBusy(false)); }}>
                  {settingsBusy ? '正在准备，请稍候…' : '准备本地转写模型'}
                </button>
                <p className="ct-step-meta">准备时下载约 240 MB 的 FunASR 中文模型；官方站点不可用时会尝试镜像，下载文件均会校验。录音不会上传；如果下载失败，已有可用的本地模型仍可继续使用。<a href="https://huggingface.co/funasr/Paraformer-large/tree/6843c899b177f325d4bbdad8c08d85d5b1321f00" target="_blank" rel="noreferrer">模型来源与许可</a></p>
              </div> : null}
              {formAsrProvider === 'local-paraformer' ? null : formAsrProvider === 'volcengine' ? <>
                <label className="ct-field"><span>火山 Resource ID</span><input value={formVolcResource} onChange={(e) => setFormVolcResource(e.target.value)} spellCheck={false} /></label>
                {credentialField('volcAppKey', '火山 App Key', formVolcApp, setFormVolcApp, productSettings?.volcAppKeySet)}
                {credentialField('volcAccessKey', '火山 Access Key', formVolcAccess, setFormVolcAccess, productSettings?.volcAccessKeySet)}
              </> : <>
                <label className="ct-field"><span>兼容服务 Endpoint</span><input value={formOpenAiEndpoint} onChange={(e) => setFormOpenAiEndpoint(e.target.value)} spellCheck={false} /></label>
                {credentialField('openaiAsrApiKey', '兼容服务 Key', formOpenAiKey, setFormOpenAiKey, productSettings?.openaiAsrApiKeySet)}
                <label className="ct-field"><span>兼容服务模型</span><input value={formOpenAiModel} onChange={(e) => setFormOpenAiModel(e.target.value)} spellCheck={false} /></label>
              </>}
              <details className="ct-ai-service-fields"><summary>AI文字服务 · {formDeepseekEnabled&&productSettings?.deepseekApiKeySet?'已配置':formDeepseekKey?'待保存':'尚未配置'}</summary>
                <p className="ct-step-meta">纪要、AI 助手与材料整理共用此服务。密钥由系统凭据管理器保存，服务连接参数集中在这里。</p>
                {credentialField('deepseekApiKey', '服务密钥', formDeepseekKey, value=>{setFormDeepseekKey(value);if(value.trim())setFormDeepseekEnabled(true);}, productSettings?.deepseekApiKeySet)}
                <label className="ct-field"><span>DeepSeek Base URL</span><input value={formDeepseekBase} onChange={(e) => setFormDeepseekBase(e.target.value)} spellCheck={false} /></label>
                <label className="ct-field"><span>DeepSeek 模型</span><input value={formDeepseekModel} onChange={(e) => setFormDeepseekModel(e.target.value)} spellCheck={false} /></label>
                <div className="ct-button-row"><button type="button" className="ct-text-button" onClick={()=>setFormDeepseekEnabled(true)} disabled={controlsBusy||settingsBusy||formDeepseekEnabled}>使用已配置的AI服务</button><button type="button" className="ct-text-button" onClick={()=>setFormDeepseekEnabled(false)} disabled={controlsBusy||settingsBusy||!formDeepseekEnabled}>暂不使用AI服务</button></div>
              </details>
            </div>
            <p className="ct-step-meta" role="status">{formDeepseekEnabled?(productSettings?.deepseekApiKeySet?'AI文字服务已配置；实际连接状态见下方服务检查。':'保存服务密钥后，可回到会议生成纪要或提问。'):'当前暂不使用AI文字服务；原音、转写和已有材料仍可使用。'}</p>
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
                    ...(surface==='windows'?{autoLocalCardTranscription:formAutoLocalCard}:{}),
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
                    setSettingsMsg(operationErrorText(err,'settings'));
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
                disabled={controlsBusy || settingsBusy || serviceBusy !== null || oobeBlockedByRecording || productSettings?.storageSaveBlocked || serviceConfigDirty || !onCheckService || (service === 'minutes' && !formDeepseekEnabled)}
                onClick={() => void checkService(service)}>{serviceBusy === service ? '正在测试…' : service === 'asr' ? '测试转写服务' : '测试纪要服务'}</button>)}
            </div>
            <p className="ct-step-meta">本地转写测试只加载本机模型；云端测试会发送一秒静音或固定测试文字，可能计费。测试不读取会议或麦克风，也不能代表识别或纪要准确率。{serviceConfigDirty ? '设置有修改，请先保存再测试。' : ''}</p>
            {(['asr', 'minutes'] as const).map(service => serviceResults[service] ? <p key={service} className="ct-step-meta" role="status">{service === 'asr' ? '转写' : '纪要'}：{serviceResults[service]}</p> : null)}
          </section>

          <details className="ct-panel ct-secondary-settings">
            <summary>陪伴模式预览</summary>
            <CompanionBehaviorPreview recording={oobeBlockedByRecording} />
          </details>
          <details className="ct-panel ct-secondary-settings">
            <summary>电脑录音与其他录音选项</summary>
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
              {!(unlimitedOffline || unlimitedOnline) ? <label className="ct-field ct-duration-field">
                <span>{connected ? '最长录音(分)' : '预计时长(分)'}</span>
                <input
                  value={draftMinutes} aria-invalid={Boolean(durationError)} aria-describedby={durationError ? "ct-advanced-duration-error" : undefined}
                  onChange={(event) => setDraftMinutes(event.target.value.replace(/[^0-9]/g, ''))}
                  inputMode="numeric"
                />
              </label> : <p className="ct-step-meta">录音持续到手动停止或设备空间用完。</p>}
            </div>
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={controlsBusy || oobeBlockedByRecording || storageBlocked
                  || (!(unlimitedOffline || unlimitedOnline) && !durationValid) || (connected && meetingMode === 'onlineLive' && !onlineDurationValid)
                  || (connected && meetingMode === 'onlineLive' && (!cloudAsrConfigured || productSettings?.asrProvider === 'local-paraformer' || !onStartBoardOnlineLive))}
                onClick={() => {
                  if (connected && meetingMode === 'onlineLive') {
                    void onStartBoardOnlineLive?.({
                      title: draftTitle.trim() || 'Companion 会议',
                      deviceId: device?.deviceId,
                      maxDurationSeconds: unlimitedOnline ? 0 : boardMaxDurationSeconds,
                      partialIntervalMs: 8_000,
                    });
                  } else {
                    onControl({
                      action: 'meetingStart',
                      title: draftTitle,
                      meetingMode,
                      durationMs: unlimitedOffline ? 0 : requestedDurationMs,
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
              {snapshot?.source === 'fixture' && snapshot.device.mode === 'fixture' ? <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording} onClick={() => onControl({ action: 'meetingLoadDemo', title: '调试演示纪要' })}>
                <FileText size={16} /><span>调试：无板演示</span>
              </button> : null}
            </div>
            <p className="ct-step-meta">{connected
              ? `${meetingMode === 'onlineLive' ? unlimitedOnline ? '不预设结束时间；手动停止或设备空间用完时结束。' : `当前设备实时转写单次最多 43 分钟，另预留 2 分钟收尾空间。${nearRecordingLimit ? ` 距本次设定结束约 ${formatDuration(recordingRemainingMs)}。` : ''}` : unlimitedOffline ? '不预设结束时间；设备空间用完时会保存已有录音并结束。' : '当前设备按填写时长录音，可升级后取消预设限时。'} 在线模式需要配置转写服务。`
              : '本机录音需要手动停止，保存后按实际音频长度显示时长。'}</p>
            {(!(unlimitedOffline || unlimitedOnline) && !durationValid) || (connected && meetingMode === 'onlineLive' && !onlineDurationValid)
              ? <p id="ct-advanced-duration-error" className="ct-step-meta" role="alert">{durationError}</p> : null}
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
          </details>

          <section className="ct-panel" aria-label="更新资源">
            <div className="ct-panel-title">
              <Upload size={18} />
              <span>设备更新</span>
            </div>
            <p className="ct-meeting-hint">
              填写更新包清单路径，程序和屏幕资源会一起更新。更新前会先将设备中未同步的录音保存到电脑；确认保存后，设备上的对应副本可能被回收，不会自动转文字。下载中断后可重新开始；设备正常启动并确认新版本后才显示成功。录音期间无法更新。
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
                      setResourceMsg(operationErrorText(err,'update'));
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
                      setResourceMsg(operationErrorText(err,'update'));
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
            <div className="ct-section-title" id="ct-log-support" tabIndex={-1} role="region" aria-label="日志与诊断"><FileText size={18} /><span>日志与诊断</span></div>
            <CompanionDiagnosticsPreview blocked={controlsBusy||oobeBlockedByRecording} onPreview={onPreviewDiagnostics}/>
            <p className="ct-meeting-hint">保存连接、升级和音频处理的阶段、电脑时间、程序指纹及本机录音关联标识，方便排查问题。不包含密钥、会议正文或原始录音。设备日志只保留最近的运行事件，重启会清空；本机日志按大小轮换。</p>
            <div className="ct-button-row">
              {[false, true].map((includeDevice) => <button key={String(includeDevice)} type="button" className="ct-action"
                disabled={controlsBusy || oobeBlockedByRecording || !onExportDiagnostics || (includeDevice && !connected)}
                onClick={() => {
                  if (diagnosticActive.current || !onExportDiagnostics) return;
                  diagnosticActive.current=true; setDiagnosticBusy(true); setDiagnosticMsg(null);
                  void onExportDiagnostics(includeDevice).then((result) => {
                    setDiagnosticMsg(result ? `已保存：${result.path}${result.warning ? `。${result.warning}` : ''}` : '已取消，未导出日志。');
                  }).catch((error) => setDiagnosticMsg(operationErrorText(error,'diagnostics'))).finally(() => { diagnosticActive.current=false; setDiagnosticBusy(false); });
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
                  .catch((error) => setDiagnosticMsg(operationErrorText(error,'components'))).finally(() => {diagnosticActive.current=false;setDiagnosticBusy(false);});
              }}>准备说话人区分组件</button>
          </section>

          <section className="ct-panel">
            <div className="ct-panel-title">
              <Download size={18} />
              <span>多格式导出</span>
            </div>
            <div className="ct-button-row">
              {(['markdown', 'docx', 'mindmap', 'txt', 'json', 'srt', 'todo', 'todotxt', 'ics'] as const).map((format) => <button key={format} type="button" className="ct-action"
                disabled={controlsBusy || oobeBlockedByRecording || !onExportMeeting || (['markdown', 'docx', 'mindmap', 'todo', 'todotxt', 'ics'].includes(format) ? !hasMinutes : !finalTranscript)
                  || (format==='srt' && (!selectedSession || !companionReviewedUtterances(selectedSession).length || companionReviewedUtterances(selectedSession).some(u=>u.approximateTiming)))}
                onClick={() => void exportMeeting(format,'settings')}>{format === 'markdown' ? 'Markdown' : format === 'docx' ? 'Word 文档' : format === 'mindmap' ? '思维导图' : format === 'todo' ? '清单 Markdown' : format === 'todotxt' ? '清单 TXT' : format === 'ics' ? '日历待办 (.ics)' : format.toUpperCase()}</button>)}
            </div>
            {renderExportFeedback('settings')}
            <p className="ct-step-meta">选择保存位置；导出只使用已保存的内容，不会重新调用转写或纪要服务。SRT 需要真实时间戳。</p>
            <p className="ct-step-meta">待办取自当前纪要的“行动项 / Action Items”列表；修改后请先保存。日历文件使用 VTODO，需支持待办的日历应用；仅明确的日期或带时区时间设为截止时间，“周五”等保留原文供核对，不自动猜日期。</p>
          </section>

          <section className="ct-ops-grid" style={{ gridTemplateColumns: 'minmax(0, 1fr)' }}>
            <section className="ct-panel" id="ct-privacy">
              <div className="ct-panel-title"><Shield size={18} /><span>隐私</span></div>
              <div className="ct-metric-grid">
                <InfoMetric label="音频（按记录）" value={privacy && !storageBlocked ? formatBytes(privacy.audioCacheBytes) : '未确认'} />
                <InfoMetric label="文本（按记录）" value={privacy && !storageBlocked ? formatBytes(privacy.transcriptBytes + privacy.minutesBytes) : '未确认'} />
                <InfoMetric label="自动删除" value="未启用" />
              </div>
              <p className="ct-step-meta">这里处理本机会议资料；设备、另存副本和远端资料分别管理。</p>
              <CompanionPrivacyCleanup result={privacy?.lastCleanup} />
              {!privacySelectionConfirmed && allLibrarySessions.length ? <p className="ct-step-meta">逐条清理前，请先在“我的记录”打开要处理的那条。<button type="button" className="ct-text-button" onClick={()=>navigatePage('library')}>选择一条录音</button></p> : null}
              <details className="ct-step-meta"><summary>清理范围与统计说明</summary>
                <p>数值按本机会议记录中的字节信息累计；共享原音可能重复计入，不含所有缓存或另存副本，不等于磁盘占用。</p>
                <p>本机清理不清除设备录音、宠物档案与记忆、其它电脑或远端资料。共享文件和无法确认归属的旧缓存会保留；完整历史资料擦除仍未提供。</p>
                <p>普通删除先移入本机回收站，可恢复；永久清除需单独确认。保护防误删，不是加密。</p>
              </details>
              {selectedSession?.organization?.protected ? <p className="ct-step-meta">当前录音已受保护，解除后才可清理。</p> : null}
              <div className="ct-button-row">
                <button type="button" className="ct-action" disabled={controlsBusy||oobeBlockedByRecording||!privacySelectionConfirmed||!onSaveLibraryLifecycle||libraryUnsaved} onClick={()=>void changeCurrentLibraryState(selectedSession?.organization?.protected?'unprotect':'protect')}>{selectedSession?.organization?.protected?'解除当前录音保护':'保护当前录音'}</button>
                <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !canEraseAudio} onClick={() => requestErase('privacyEraseAudio', '清理这场会议的本机音频？', '保留已有文字和纪要，取消尚未完成的自动处理。仅删除可确认归属的受管文件；共享或外部另存的文件会保留。设备原录音不受影响。')}>
                  <Eraser size={16} /><span>删音频</span>
                </button>
                <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !canEraseTranscript} onClick={() => requestErase('privacyEraseTranscript', '删除这场会议的文字、纪要和备注？', '保留录音，取消尚未完成的自动处理。用户备注也会删除，重新转写不会恢复这些备注；请先保存需要的内容。')}>
                  <FileText size={16} /><span>删文本</span>
                </button>
                <button
                  type="button"
                  className="ct-action ct-action-danger"
                  disabled={controlsBusy || oobeBlockedByRecording || !privacySelectionConfirmed||!onSaveLibraryLifecycle||Boolean(selectedSession?.organization?.protected)||libraryUnsaved}
                  onClick={() => void changeCurrentLibraryState('trash')}
                  title="移入本机回收站，可恢复；不删除或确认消费设备录音"
                >
                  <Trash2 size={16} /><span>移入回收站</span>
                </button>
                <button type="button" className="ct-action ct-action-danger" disabled={controlsBusy || oobeBlockedByRecording || allLibrarySessions.length === 0||allLibrarySessions.some(s=>s.organization?.protected)} onClick={() => requestErase('privacyEraseAll', '永久清除全部本机会议与回收站？', `将清除 ${allLibrarySessions.length} 场本机会议记录（含回收站的文字、纪要、备注与重点）及可确认归属的受管文件，并取消自动处理，不能恢复。共享文件、无法确认归属的旧缓存及另存副本会保留。设备录音、宠物档案与记忆、其它电脑和远端资料不受影响。`)}>
                  <Trash2 size={17} />清除全部本机会议
                </button>
              </div>
              {pendingDelete && deleteContextValid ? <DeleteConfirmation title={pendingDelete.title} detail={pendingDelete.detail}
                targetTitle={pendingDelete.request.action === 'privacyEraseAll' ? undefined : pendingDelete.targetTitle}
                blocked={controlsBusy || oobeBlockedByRecording} onCancel={()=>setPendingDelete(null)} onConfirm={confirmPendingDelete} /> : null}
            </section>
          </section>

          <section className="ct-panel">
            <div className="ct-panel-title"><Bluetooth size={18} /><span>设备名称</span></div>
            <div className="ct-name-row">
              <input aria-label="Companion 设备名称" aria-invalid={!draftName.trim() || Boolean(nameError)} aria-describedby="ct-ble-name-help" value={draftName} onChange={(event) => setDraftName(event.target.value)} spellCheck={false} />
              <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !connected || !draftName.trim() || Boolean(nameError)} onClick={() => onControl({ action: 'applyBleName', bleName: draftName })}>保存到设备</button>
              <button type="button" className="ct-action" disabled={controlsBusy || oobeBlockedByRecording || !connected} onClick={() => onControl({ action: 'resetBleName' })}>恢复默认名称</button>
            </div>
            <p id="ct-ble-name-help" className="ct-step-meta">{!draftName.trim() ? '请填写设备名称后保存。' : nameError ? '名称不符合设备要求，请缩短名称，并避免中文、引号、分号等字符。' : `当前名称：${snapshot?.bleName.activeName ?? '尚未读取'}。保存后会读取设备确认结果。`}</p>
          </section>
        </div>
      ) : null}

      </section>

      {surface === 'windows' && petPanel ? <section className="ct-page-panel ct-pet-chat-disclosure ct-pet-workspace"
        hidden={pageView !== 'pet'} aria-label="宠物与互动">{petPanel}</section> : null}
      <div className="ct-page-panel" hidden={pageView !== 'settings'}>{settingsFooter}</div>
      <footer className="ct-footer" hidden={!(error||nameError||titleDirty||minutesDirty||transcriptReviewUnsaved||bookmarkUnsaved||noteUnsaved||libraryUnsaved)}>{titleDirty || minutesDirty || transcriptReviewUnsaved || bookmarkUnsaved || noteUnsaved || libraryUnsaved ? '有尚未保存的修改。' : pageView === 'pet' ? connected ? '聊天与档案中的内容以当前连接的宠物为准。' : '连接后可以查看这只宠物的档案。' : footer}</footer>
      </div></div>
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

export function RecordingSafetyCard({ session, persistence, recoveryProcessing }: {
  session: CompanionV1HostSession;
  persistence: CompanionV1Snapshot['host']['persistence'];
  recoveryProcessing: boolean;
}) {
  if (isTextOnlyImport(session)) {
    const saved = persistence?.status === 'ready';
    const failed = persistence?.status === 'blocked' || persistence?.status === 'unsaved';
    // Confirmed text imports have no device/audio saving stages. Show one
    // compact provenance/status line; preserve the complete card for uncertain,
    // failed, ongoing or partial states instead of silently hiding their risk.
    if(saved && session.transcriptFinal && session.transcriptText.trim() && !recoveryProcessing
        && session.status!=='recording' && !session.captureIncomplete) {
      return <p className="ct-imported-save-status" aria-label="文字保存状态">导入文字已保存在本机 · 无原录音</p>;
    }
    return <section className="ct-safety-card" aria-label="文字保存状态">
      <header><strong>文字保存状态</strong><span>{saved ? '文字已保存在本机'
        : failed ? '文字保存失败' : '保存状态待确认'}</span></header>
      <p>这条记录来自导入文字，没有原录音；无需等待设备同步或转写。</p>
      {!saved ? <p role="alert">{persistence?.message
        ? operationErrorText(persistence.message,'save') : '本机保存尚未确认，请先在保存提示中重试。'}</p> : null}
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
    && !captureOngoing && (session.source === 'hostMicrophone' || session.source === 'hostMeeting'
      ? hostRecordingAudioConfirmed(session)
      : session.deviceRecordingKey
        ? Boolean(session.audioStored && session.audioPath && session.audioBytes > 0)
        : Boolean(session.audioPath || (session.audioStored && session.audioBytes > 0)));
  const hostAudioUnconfirmed = (session.source === 'hostMicrophone' || session.source === 'hostMeeting') && !captureOngoing && !localAudio;
  const partialAudio = !localAudio && (savedSegments > 0 || cachedAudio);
  const deviceCopy = Boolean(session.sourceDeviceId && (session.deviceRecordingId != null||session.deviceRecordingKey) && !wholeReclaimed);
  const growingDeviceCapture = captureOngoing && deviceCopy;
  const exactDeviceCopy = Boolean(deviceCopy && session.deviceTotalLength
    && /^[0-9a-f]{64}$/i.test(session.deviceSha256 ?? ''));
  const saveConfirmed = persistence?.status === 'ready';
  const saveFailed = persistence?.status === 'blocked' || persistence?.status === 'unsaved';
  const localCopyVerified = exactDeviceCopy && localAudio && saveConfirmed
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
        : localCopyVerified ? '尚无设备回收确认' : deviceCopy ? '暂不回收' : '无需回收',
      kind: wholeReclaimed ? 'done' : growingDeviceCapture ? 'active' : 'idle',
    },
  ];
  return <section className="ct-safety-card" aria-label="录音安全状态">
    <header><strong>录音安全状态</strong><span>{saveFailed ? '需要处理'
      : !saveConfirmed && (localAudio || partialAudio || rawComplete) ? '保存状态待确认'
      : rawComplete ? '原音已收齐，回听待生成' : localAudio ? '电脑已有副本' : partialAudio ? '本机已有片段，仍待收齐' : '内容仍在流转'}</span></header>
    {session.processingPolicy === 'manual' ? <p>这是一份普通录音。转写和纪要由你手动启动，同步原音后不会自动提交云端处理。</p> : null}
    <ol>{steps.map((step) => <li key={step.label} className={`ct-safety-${step.kind}`}><span aria-hidden="true" />
      <div><strong>{step.label}</strong><small>{step.state}</small></div></li>)}</ol>
    {localCopyVerified && !wholeReclaimed ? <p>移入本机回收站会保留电脑原音，不会触发设备录音回收。</p> : null}
    {session.pendingReason === 'needs_device_sync' ? <p>录音仍在来源设备；重连同一台 Companion 后会从断点继续。</p> : null}
    {session.pendingReason === 'needs_segments' ? <p>这场录音尚未收齐。已有片段会保留，连接同一台 Companion 后继续同步。</p> : null}
    {session.deviceRecordingEndReason ? <p>{({user: '你已停止设备录音。', storageFull: '设备空间已满，录音提前停止；停止后的内容没有录到。', durationLimit: '已达到设定时长，设备录音已结束。', lowBattery: '设备因电量低结束了录音。', silence: '已达到设定的静音时长，设备录音已结束。'} as const)[session.deviceRecordingEndReason]} 原音同步和本机保存进度见上方。</p> : null}
    {hostAudioUnconfirmed ? <p role="alert">本机录音未确认保存，暂不能回听或转写。已保留原文件路径，请先保留原文件。</p>
      : session.captureIncomplete ? <p role="alert">这场录音曾意外中断，实际保存 {formatDuration(session.durationMs)}，结尾可能缺失。可以回听或导出原音；转写与纪要只覆盖已保存的片段。{!session.recovery?.captureReviewConfirmed ? '选择整理片段后才会继续处理。' : ''}</p> : null}
    {saveFailed ? <p>{persistence?.message ? operationErrorText(persistence.message,'save') : '本机索引尚未安全保存，当前不会回收设备副本。'}</p> : null}
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

function deviceStorageFullNotice(session: CompanionV1HostSession): string | null {
  return session.deviceRecordingEndReason === 'storageFull'
    ? '设备空间已满，录音提前停止；停止后的内容没有录到。请检查设备剩余空间，腾出空间后再开始新录音。'
    : null;
}

function meetingSearchText(session: CompanionV1HostSession): string {
  return [
    meetingTitle(session),
    session.transcriptText,
    companionReviewedTranscript(session),
    ...(session.meetingNotes ?? []).flatMap(note => [note.text,...(note.references??[]).flatMap(reference=>[reference.name,reference.quote,reference.kind==='document'?reference.sectionLabel:''])]),
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
  return recordingDisplayTitle(session);
}

function meetingSource(session: CompanionV1HostSession): string {
  if (session.source === 'deviceFlash' || session.source === 'boardDevice') return 'Companion 录音';
  if (session.source === 'hostMicrophone') return '本机麦克风';
  if (session.source === 'derivedAudio') return '编辑成品';
  if (session.source === 'importedAudio') return '导入音频';
  if (session.source === 'hostMeeting') return '电脑会议与麦克风';
  if (session.source === 'importedTranscript') return '导入文字';
  return '演示记录';
}

function MinutesReadingView(props:Parameters<typeof MinutesReadingBody>[0]) {
  const reading=props.noteContext?{body:props.markdown,review:''}:meetingReadingSources(props.markdown);
  return <MeetingReadingFrame markdown={props.markdown}>
    <MinutesReadingBody {...props} markdown={reading.body} savedMarkdown={props.savedMarkdown??props.markdown}/>
    {reading.review.trim()?<details className="ct-full-minutes ct-source-review"><summary>原文依据与待核对内容</summary>
      <p className="ct-step-meta">保留原始转写和先前整理中的核对材料；这里的片段不代表已确认的会议结论。</p>
      <MarkdownMinutes markdown={reading.review} sources={props.sources} blocked={props.blocked} onOpenSource={props.onOpenSource} onShowTranscript={props.onShowTranscript}/>
    </details>:null}
  </MeetingReadingFrame>;
}
function MinutesReadingBody({ markdown, savedMarkdown=markdown, transcript, durationMs, compactAllowed, longEvidenceAllowed, noteContext, onToggleAction, actionsBlocked, recordingTitle, recordingTime,actionContextKey='', ...sourceProps }: {
  markdown: string; transcript: string; durationMs: number; compactAllowed: boolean; longEvidenceAllowed?: boolean; noteContext?:CompanionMinutesNoteContext|null;
  recordingTitle?:string;recordingTime?:string;actionContextKey?:string;
  onToggleAction?:(lineIndex:number,completed:boolean)=>void;actionsBlocked?:boolean;savedMarkdown?:string;
  sources?: readonly CompanionTranscriptSource[]; blocked?: boolean;sourceFallbackLabel?:string;
  onOpenSource?: (source: CompanionTranscriptSource) => void;
  onShowTranscript?: (text?:string,returnId?:string) => void;
}) {
  // Only fold the exact native provenance envelope represented by the saved
  // typed source snapshot. Complete saved output remains available below.
  let reading=markdown;
  if(noteContext){
    const envelope = minutesSourceEnvelope(noteContext);
    if(markdown.startsWith(envelope))reading=markdown.slice(envelope.length);
  }
  reading=splitGeneratedMeetingMetadata(reading).body;
  const hideGeneratedNotices=!noteContext&&Boolean(splitGeneratedMeetingMetadata(savedMarkdown).metadata);
  // The detail page already owns the current recording title. Hide only its
  // duplicated leading document heading while reading; saved markdown, editor,
  // exports, source-note provenance and later authored headings remain intact.
  const actionChecklist=onToggleAction?{items:savedActions(savedMarkdown),onToggle:onToggleAction,blocked:actionsBlocked,compactSources:!!noteContext,recordingTime,contextKey:actionContextKey,title:recordingTitle}:undefined;
  const longEvidence=longEvidenceAllowed&&!noteContext?splitLongMinutesEvidence(reading):null;
  if(longEvidence)return <div className="ct-brief-minutes">
    <MarkdownMinutes markdown={longEvidence.overview} hideGeneratedNotices={hideGeneratedNotices} hideDocumentTitle={Boolean(recordingTitle)} actionChecklist={actionChecklist} {...sourceProps}/>
    {longEvidence.detailSummary?<details className="ct-full-minutes"><summary>{longEvidence.detailKeywords?'查看完整摘要和关键词':'查看完整会议摘要'}</summary>
      <MarkdownMinutes markdown={longEvidence.detailSummary} {...sourceProps}/>
      {longEvidence.detailKeywords?<MarkdownMinutes markdown={longEvidence.detailKeywords} {...sourceProps}/>:null}
    </details>:null}
    <details className="ct-full-minutes"><summary>查看各段原文依据</summary>
      <MarkdownMinutes markdown={longEvidence.evidence} {...sourceProps}/>
    </details>
  </div>;
  const shortEvidence=!noteContext?splitShortMinutesEvidence(reading,transcript):null;
  const shortReading=shortEvidence?.overview??reading;
  const shortSource=shortEvidence?<details className="ct-full-minutes"><summary>查看原话依据</summary>
    <p>以下原话由 AI 整理时关联，仅供核对；关联和转写可能有误，编辑后请重新核对。</p><MarkdownMinutes markdown={shortEvidence.evidence} {...sourceProps}/>
  </details>:null;
  const shortOverview=compactAllowed&&!noteContext?splitShortMinutesOverview(shortReading):null;
  if(shortOverview)return <div className="ct-brief-minutes">
    <MarkdownMinutes markdown={shortOverview.overview} hideGeneratedNotices={hideGeneratedNotices} hideDocumentTitle={Boolean(recordingTitle)} actionChecklist={actionChecklist} {...sourceProps}/>
    <details className="ct-full-minutes"><summary>{shortOverview.hasSources?'查看完整摘要和补充原文':'查看完整摘要'}</summary>
      <MarkdownMinutes markdown={shortOverview.detail} {...sourceProps}/>
    </details>
    {shortSource}
  </div>;
  const brief = compactAllowed ? briefMinutes(shortReading, transcript, durationMs, !!noteContext) : null;
  if (!brief) return <div className="ct-brief-minutes">
    
      <MarkdownMinutes markdown={shortReading} hideGeneratedNotices={hideGeneratedNotices} hideDocumentTitle={Boolean(recordingTitle)} actionChecklist={actionChecklist} {...sourceProps} />
    {shortSource}
    {noteContext&&reading!==markdown?<details className="ct-full-minutes"><summary>查看本次补充来源与完整整理</summary>
      
      <MarkdownMinutes markdown={shortReading} hideDocumentTitle={Boolean(recordingTitle)} actionChecklist={actionChecklist} {...sourceProps}/>
      {noteContext?<details className="ct-full-minutes"><summary>核对本次补充来源</summary>
        <MarkdownMinutes markdown={minutesSourceEnvelope(noteContext)} {...sourceProps}/>
      </details>:null}
    </details>:null}
  </div>;
  // Fold only the generated brief's summary section. Actual decisions,
  // questions and attribution remain visible; full saved text stays below.
  const contextStart=brief.startsWith('## 待办\n\n')?brief.indexOf('\n\n## 重点\n\n'):-1;
  const nextSection=contextStart>0?brief.indexOf('\n\n## ',contextStart+5):-1;
  const compactReading=contextStart>0?brief.slice(0,contextStart)+(nextSection<0?'':brief.slice(nextSection)):brief;
  const checklistOnly=compactReading!==brief;
  const hasSourceAttribution = /^## (?:讨论纪要\(按说话人\)|发言归属未确认的原话)\r?$/m.test(reading);
  return <div className="ct-brief-minutes">
    <MarkdownMinutes markdown={compactReading} actionChecklist={actionChecklist} {...sourceProps} />
    <details className="ct-full-minutes"><summary>{hasSourceAttribution ? '查看完整整理与发言归属' : checklistOnly ? '查看重点和完整整理' : '查看完整整理'}</summary>
      
      <MarkdownMinutes markdown={shortReading} hideDocumentTitle={Boolean(recordingTitle)} actionChecklist={actionChecklist} {...sourceProps} />
      {noteContext&&reading!==markdown?<details className="ct-full-minutes"><summary>核对本次补充来源</summary>
        <MarkdownMinutes markdown={minutesSourceEnvelope(noteContext)} {...sourceProps}/>
      </details>:null}
    </details>
    {shortSource}
  </div>;
}

function MarkdownMinutes({ markdown, sources = [], blocked, onOpenSource, onShowTranscript, sourceFallbackLabel="查找原文核对（未定位）", actionChecklist, hideDocumentTitle=false,hideGeneratedNotices=false }: { markdown: string;hideDocumentTitle?:boolean;hideGeneratedNotices?:boolean;
  actionChecklist?:{items:SavedAction[];onToggle:(lineIndex:number,completed:boolean)=>void;blocked?:boolean;compactSources?:boolean;recordingTime?:string;contextKey?:string;title?:string};
  sources?: readonly CompanionTranscriptSource[]; blocked?: boolean;
  onOpenSource?: (source: CompanionTranscriptSource) => void; onShowTranscript?:(text?:string,returnId?:string)=>void;sourceFallbackLabel?:string }) {
  const lookupId=useId();
  const actionRows=new Map(savedActions(markdown).flatMap((row,index)=>{
    const saved=actionChecklist?.items[index];
    return saved&&saved.text===row.text&&saved.completed===row.completed?[[row.lineIndex,saved] as const]:[];
  }));
  const blocks: Array<{ type: 'title' | 'heading' | 'item' | 'text'; text: string;action?:SavedAction }> = [];
  let noticeFence:string|null=null;
  markdown.split(/\r?\n/).forEach((raw,lineIndex) => {
    const line = raw.trim();
    const marker=/^\s*(`{3,}|~{3,})/.exec(raw);
    if(marker){const kind=marker[1][0];noticeFence=noticeFence===kind?null:noticeFence??kind;}
    if(hideGeneratedNotices&&!noticeFence&&isGeneratedReadingNotice(raw))return;
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
  const actionReview=useActionReview(visibleActions.map(action=>savedActionReview(String(action.lineIndex),action.text,action.completed)),actionChecklist?.contextKey??'');
  const shownActionIds=new Set(actionReview.visible.map(action=>action.id));
  const commonSupplement = actionChecklist?.compactSources && visibleActions.length === actionChecklist.items.length
    ? commonActionSupplement(visibleActions) : null;
  const firstActionIndex = visibleBlocks.findIndex(block => block.action);
  // Show the source-date context where it can change the interpretation. A
  // canonical date/time already carries its calendar date and explicit zone.
  // This is a reading projection only, never a relative-date conversion.
  const needsSourceDate=visibleActions.some(action=>{
    const parts=nativeActionParts(action.text);
    return parts.metadata.some(field=>field.key==='due'&&readableCalendarTime(field.value)===field.value)
      || /今[天早晚]|明[天早晚]|后天|昨天|前天|(?:本|这|下|上)(?:周|星期|个?月)|周[一二三四五六日天]|星期[一二三四五六日天]/u.test(parts.body);
  });
  const overviewStart=visibleBlocks.findIndex(block=>block.type==='heading'&&['全会重点','会议概览'].includes(block.text));
  let overviewEnd=overviewStart+1;
  while(overviewEnd<visibleBlocks.length&&visibleBlocks[overviewEnd].type==='item'&&!visibleBlocks[overviewEnd].action)overviewEnd++;
  const overviewCount=overviewStart<0?0:overviewEnd-overviewStart-1;
  const topicOverview=hideGeneratedNotices&&overviewStart>=0&&visibleBlocks[overviewStart].text==='全会重点'&&overviewCount>0;
  if (!markdown.trim()) return <p className="ct-document-empty">这条录音还没有整理结果。</p>;
  return (
    <article className="ct-minutes-article">
      {visibleBlocks.map((block, index) => {
        if (block.type === 'title') return hideDocumentTitle&&index===0?null:<h3 key={index}>{formatMinutesTitle(block.text)}</h3>;
        if (block.type === 'heading') return <h4 key={index} className={block.text==='会议概览'?'ct-note-overview-heading':undefined} data-meeting-heading={block.text}>{translateMinutesHeading(block.text)}</h4>;
        const sourceParts=block.action?nativeActionParts(block.action.text):null;
        const bodyReferences = companionMinutesReferencedSources(sources, sourceParts?.body??block.text);
        const references = bodyReferences.filter(source=>!sourceParts||sourceParts.metadata.every(field=>source.text.includes(field.value.trim())));
        // An edited date/owner must not erase an exact, unique body anchor.
        // Keep it explicitly as a comparison, never attribute new metadata to speech.
        const comparisonOnly = references.length===0 && !!sourceParts?.metadata.length && bodyReferences.length>0;
        const shownReferences = comparisonOnly ? bodyReferences : references;
        const unverifiedMetadata = sourceParts?.metadata.filter(field=>shownReferences.some(source=>!source.text.includes(field.value.trim())))??[];
        const unverifiedNames = [...new Set(unverifiedMetadata.map(field=>field.key==='due'?'时间':'负责人'))].join('、');
        const links = onOpenSource && shownReferences.length ? <span className="ct-minutes-source-links">
          {shownReferences.map((source) => <button type="button" className="ct-text-button" key={source.index}
            disabled={blocked} aria-label={`${comparisonOnly?'对照第':'核对第'}${source.index + 1}段${comparisonOnly?'事项原文':'原文'}`}
            onClick={() => onOpenSource(source)}>{comparisonOnly?'对照事项原文':'核对原文'} · {source.approximateTiming?'约 ':''}{Math.floor(source.startMs / 60000)}:{String(Math.floor(source.startMs / 1000) % 60).padStart(2, '0')}</button>)}
          {comparisonOnly?<small>此处对照事项原话；{unverifiedNames}请按实际安排确认。</small>:null}
        </span> : block.action&&onShowTranscript?<span className="ct-minutes-source-links"><button type="button" className="ct-text-button" disabled={blocked}
          id={`${lookupId}-source-${index}`} title="还没有匹配到可直接跳转的唯一原文片段，点击后可搜索对照。定位状态不等于内容已经核实。" onClick={()=>onShowTranscript(sourceParts?.body??block.text,`${lookupId}-source-${index}`)}>{sourceFallbackLabel}</button></span>:null;
        if(topicOverview&&index>overviewStart&&index<overviewEnd&&block.type==='item'&&!block.action)return <MeetingTopic text={block.text} key={`${index}:${block.text}`}>{links}</MeetingTopic>;
        if(block.action&&actionChecklist){const action=block.action;
          const actionIndex=visibleActions.indexOf(action);
          const shownText=commonSupplement?commonSupplement.displayTexts[actionIndex]:action.text;
          const presentation=actionChecklist.compactSources?compactActionSource(shownText)
            :{title:shownText,conditional:false,supplementary:false};
          const parts=actionChecklist.compactSources?splitActionSupplement(presentation.title):null;
          const shown=actionReadingParts(parts?.title??presentation.title);
          const shownTitle=shown.title;
          return <div key={index}>
          {index===firstActionIndex?<ActionReviewTools key={actionChecklist.contextKey??''} review={actionReview} title={actionChecklist.title} blocked={blocked||actionChecklist.blocked}/>:null}
          {index===firstActionIndex?<p className="ct-action-source-legend">这里只保存事项清单，不会定时通知。
            {needsSourceDate ? (actionChecklist.recordingTime?<><br/>本条记录：{actionChecklist.recordingTime}。相对时间请核对原始来源的日期。</>:<>相对时间请核对原始来源的日期。</>) : null}
          </p>:null}
          {commonSupplement&&index===firstActionIndex?<p className="ct-action-source-legend">{commonSupplement.text.startsWith('共同适用规则：')?'共同适用规则：':'以下事项的共同补充：'}{commonSupplement.text.startsWith('共同适用规则：')?commonSupplement.text.slice('共同适用规则：'.length):commonSupplement.text}</p>:null}
          {shownActionIds.has(String(action.lineIndex))&&<div className="ct-minutes-item ct-minutes-action-item">
          <label className={`ct-saved-action${action.completed?' completed':''}`}><input type="checkbox" checked={action.completed}
            disabled={blocked||actionChecklist.blocked} aria-label={`${action.completed?'恢复为待办':'标记完成'}：${actionMetadataText(action.text)}`}
            onChange={event=>actionChecklist.onToggle(action.lineIndex,event.target.checked)}/><span>
              <span>{presentation.conditional?<small className="ct-action-condition-mark">有条件</small>:null}{shownTitle}{presentation.supplementary?<sup className="ct-action-source-mark" title="来自本次补充" aria-label="来自本次补充">＊</sup>:null}</span>
              {shown.metadata.map(field=><span className="ct-action-supplement" key={field.key}><span className="ct-action-supplement-label">{field.key==='due'?((field.value.endsWith('前')||readableCalendarTime(field.value)!==field.value)?'截止':'注明时间'):'负责人'}</span>{field.key==='due'?readableCalendarTime(field.value):field.value}</span>)}
              {parts?<span className="ct-action-supplement"><span className="ct-action-supplement-label">补充</span>{parts.context}</span>:null}
            </span></label>{links}</div>}</div>;}
        const overviewPoint=!topicOverview&&overviewStart>=0&&index>overviewStart&&index<overviewEnd;
        if(overviewPoint)return <p key={index} className={`ct-note-overview-point${index===overviewEnd-1?' ct-note-overview-last':''}`}>{minutesInlineText(block.text)}{links}</p>;
        if (block.type === 'item') return <div className="ct-minutes-item" key={index}><span className="ct-minutes-bullet" aria-hidden="true">•</span><span>{minutesInlineText(block.text)}{links}</span></div>;
        return <p key={index}>{minutesInlineText(block.text)}{links}</p>;
      })}
      {actionChecklist?.compactSources&&visibleBlocks.some(block=>block.action&&compactActionSource(block.action.text).supplementary)?
        <p className="ct-action-source-legend">＊ 来自本次补充；原话与补充仍分别保留。</p>:null}
    </article>
  );
}

function actionMetadataText(value: string): string {
  const shown=actionReadingParts(value);
  return [shown.title,...shown.metadata.map(field=>`${field.key==='due'?((field.value.endsWith('前')||readableCalendarTime(field.value)!==field.value)?'截止':'注明时间'):'负责人'}：${field.key==='due'?readableCalendarTime(field.value):field.value}`)].join('；');
}

function minutesInlineText(value: string) {
  // Render paired strong markers as React text nodes, never raw HTML/links.
  // All source matching and saved/exported text still use the untouched value.
  return value.split(/(\*\*[^*\r\n]+\*\*)/g).map((part,index)=>
    /^\*\*[^*\r\n]+\*\*$/.test(part)
      ? <strong key={index}>{part.slice(2,-2)}</strong> : part);
}

function translateMinutesHeading(value: string): string {
  const headings: Record<string, string> = {
    Summary: '摘要', 摘要: '摘要', Decisions: '讨论结论（需核对）', 决定: '关键决定', 'Action Items': '行动项', Questions: '会中问题', 'Open Questions': '待确认问题', 问题: '会中问题', Keywords: '关键词', '全会重点':'讨论要点',
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
