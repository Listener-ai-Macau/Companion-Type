import type { CompanionRecordingBookmark } from './recordingBookmarks';
import type {CompanionLibraryOrganization} from './libraryOrganization';

export const COMPANION_V1_SCHEMA = 'companion.host.v1' as const;
export const COMPANION_V1_DEFAULT_BLE_NAME = 'companion';
export const COMPANION_V1_BLE_NAME_MAX_BYTES = 29;
export const COMPANION_V1_RAW_PCM_BYTES_PER_SECOND = 32000;
export const COMPANION_V1_DEVICE_FLASH_RECORDING_MAX_SECONDS = 60;
export const COMPANION_V1_LONG_MEETING_TARGET_SECONDS = 3600;
export const COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES =
  COMPANION_V1_RAW_PCM_BYTES_PER_SECOND * COMPANION_V1_LONG_MEETING_TARGET_SECONDS;
export const COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS = 300;
export const COMPANION_V1_ASR_UPLOAD_MAX_BYTES = 25 * 1024 * 1024;
export const COMPANION_V1_ONE_HOUR_CHUNKS = Math.ceil(
  COMPANION_V1_LONG_MEETING_TARGET_SECONDS / COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS,
);
export const COMPANION_V1_HOST_RECORDING_CHANNEL = 'host://companion-type/recording';
export const COMPANION_V1_HOST_MINUTES_CHANNEL = 'host://companion-type/minutes';
export const COMPANION_V1_HOST_DEVICE_CHANNEL = 'host://companion-type/device';
export const COMPANION_V1_HOST_SETUP_CHANNEL = 'host://companion-type/setup';
export const COMPANION_V1_HOST_PRIVACY_CHANNEL = 'host://companion-type/privacy';

export const COMPANION_V1_GATT_BOUNDARY = {
  deviceStatusServiceUuid: '8f7a0001-7b7d-4f3d-9d6f-6c2d1b7c0000',
  deviceStatusUuid: '8f7a1001-7b7d-4f3d-9d6f-6c2d1b7c0000',
  settingsServiceUuid: '8f7a0004-7b7d-4f3d-9d6f-6c2d1b7c0000',
  bleNameConfigUuid: '8f7a4002-7b7d-4f3d-9d6f-6c2d1b7c0000',
  meetingServiceUuid: '8f7a0008-7b7d-4f3d-9d6f-6c2d1b7c0000',
  meetingControlUuid: '8f7a8001-7b7d-4f3d-9d6f-6c2d1b7c0000',
  meetingStatusUuid: '8f7a8002-7b7d-4f3d-9d6f-6c2d1b7c0000',
  sensorsServiceUuid: '8f7a0009-7b7d-4f3d-9d6f-6c2d1b7c0000',
  imuStatusUuid: '8f7a9001-7b7d-4f3d-9d6f-6c2d1b7c0000',
  audioOutputServiceUuid: '8f7a000a-7b7d-4f3d-9d6f-6c2d1b7c0000',
  speakerControlUuid: '8f7aa001-7b7d-4f3d-9d6f-6c2d1b7c0000',
  speakerStatusUuid: '8f7aa002-7b7d-4f3d-9d6f-6c2d1b7c0000',
  wakeWordControlUuid: '8f7aa003-7b7d-4f3d-9d6f-6c2d1b7c0000',
  wakeWordStatusUuid: '8f7aa004-7b7d-4f3d-9d6f-6c2d1b7c0000',
} as const;

export type CompanionV1SnapshotSource = 'fixture' | 'firmware' | 'lastKnown' | 'unavailable';

export type CompanionV1ControlAction =
  | 'hostRetrySave'
  | 'meetingRestoreAudio'
  | 'deviceScan'
  | 'deviceConnect'
  | 'deviceDisconnect'
  | 'deviceEnableAutoReconnect'
  | 'deviceDisableAutoReconnect'
  | 'deviceSyncRecordings'
  | 'stageBleName'
  | 'applyBleName'
  | 'resetBleName'
  | 'oobeRunChecks'
  | 'meetingStart'
  | 'meetingStop'
  | 'meetingFinalize'
  | 'meetingPause'
  | 'meetingResume'
  | 'meetingRecoverControl'
  | 'meetingAppendLiveTranscript'
  | 'meetingImportTranscript'
  | 'meetingTranscribeAudio'
  | 'meetingGenerateMinutes'
  | 'meetingExportMarkdown'
  | 'meetingExportTxt'
  | 'meetingExportJson'
  | 'meetingExportSrt'
  | 'meetingExportActionsTodo'
  | 'meetingExportActionsIcal'
  | 'meetingLoadDemo'
  | 'meetingSelectSession'
  | 'meetingResetSession'
  | 'privacyEraseAudio'
  | 'privacyEraseTranscript'
  | 'privacyEraseAll'
  | 'privacyDeleteSession'
  | 'speakerPrompt'
  | 'speakerStop'
  | 'wakeArm'
  | 'wakeDisable'
  | 'wakeTestDetect';

export type CompanionV1MeetingStatus =
  | 'idle'
  | 'recording'
  | 'paused'
  | 'captured'
  | 'transcribed'
  | 'minutesReady'
  | 'finalized'
  | 'error';

export interface CompanionV1MeetingState {
  supported: boolean;
  active: boolean;
  status: CompanionV1MeetingStatus;
  startedAt: string | null;
  durationMs: number;
  transcriptCount: number;
}

export interface CompanionV1ImuState {
  supported: boolean;
  /**
   * Electronic-pet body sense (pick up / tap / idle). Enabled only after a
   * valid IMU_STATUS read reports populated hardware.
   * Product core identity: pet first; meeting is a skill.
   */
  reserved: boolean;
  online: boolean;
  sampleHz: number;
  motion: 'unknown' | 'still' | 'moving' | 'tilted';
  accel: { x: number; y: number; z: number };
  gyro: { x: number; y: number; z: number };
}

export interface CompanionV1SpeakerState {
  supported: boolean;
  /**
   * Electronic-pet “mouth”: short calls / mood sounds, not long meeting playback.
   * Enabled only after a valid SPEAKER_STATUS read reports populated hardware.
   */
  reserved: boolean;
  online: boolean;
  muted: boolean;
  volume: number;
  status: 'unknown' | 'notPopulated' | 'idle' | 'prompting' | 'streaming' | 'error';
}

export interface CompanionV1WakeWordState {
  supported: boolean;
  armed: boolean;
  engine: 'fixture' | 'local' | 'firmware';
  keyword: string;
  lastDetectedAt: string | null;
  confidence: number;
}

export interface CompanionV1BleNameState {
  activeName: string;
  stagedName: string;
  maxLen: number;
  status: 'clean' | 'staged' | 'applied' | 'pendingRestart' | 'error';
  pendingRestart: boolean;
}

export interface CompanionV1DeviceTransportState {
  supported: boolean;
  providerId: string;
  mode: 'fixture' | 'windowsNative' | 'toolBridge' | 'unavailable';
  scanning: boolean;
  connected: boolean;
  deviceId: string | null;
  lastSeenAt: string | null;
  signalRssi: number | null;
  recordingsAvailable: number;
  /** Last valid board DEVICE_STATUS.active_mode reading. */
  recording: boolean;
  lastSyncAt: string | null;
  firmwareVersion: number | null;
  buildId: number | null;
  boardId: number | null;
  hardwareRevision: string | null;
  /** Optional WBA DEVICE_STATUS extension; absent on legacy 20-byte payloads. */
  mcuUid?: string | null;
  /** Active validated UI resource generation; absent until WBA assets mount. */
  uiGeneration?: number | null;
  /** Last validated device report. Refreshed on connection/sync; START checks again. */
  recordingCapacity?: CompanionV1RecordingCapacity | null;
  /** Transactional BLE readiness; ready means verified and connect-on-demand. */
  connectionPhase: 'idle' | 'discovered' | 'checking' | 'ready' | 'reconnecting' | 'offline' | 'manualDisconnected' | 'busy' | 'pairingRequired';
  rememberedDeviceId: string | null;
  autoReconnectEnabled: boolean;
  manualDisconnect: boolean;
  lastConnectedAt: string | null;
  lastReconnectAttemptAt: string | null;
  reconnectAttemptCount: number;
  message: string;
}

export interface CompanionV1RecordingCapacity {
  /** Explicit user-confirmed single-entry loss protocol; absent on older firmware. */
  confirmedDiscardSupported?: boolean;
  layoutVersion: number;
  busy: boolean;
  usedEntries: number;
  maxEntries: number;
  catalogGeneration: number;
  dataBytes: number;
  freeBytes: number;
  largestFreeExtent: number;
  protectedBytes: number;
  consumedBytes: number;
  bytesPerSecond: number;
  reserveHeadroom: number;
  localLimitSeconds: number;
  unsyncedEntries: number;
  writingEntries: number;
  consumedEntries: number;
}

export type CompanionV1OobeCheckStatus = 'pending' | 'pass' | 'warn' | 'fail';

export interface CompanionV1OobeCheck {
  id: string;
  label: string;
  status: CompanionV1OobeCheckStatus;
  message: string;
}

export interface CompanionV1OobeState {
  complete: boolean;
  lastRunAt: string | null;
  checks: CompanionV1OobeCheck[];
}

export interface CompanionV1PrivacyState {
  localOnly: boolean;
  consentRequired: boolean;
  retentionDays: number;
  audioCacheBytes: number;
  transcriptBytes: number;
  minutesBytes: number;
  lastEraseAt: string | null;
  policyLabel: string;
}

export type CompanionV1HostSessionSource =
  | 'fixture'
  | 'deviceFlash'
  | 'boardDevice'
  | 'hostMicrophone'
  | 'importedTranscript';

export type CompanionV1HostSessionStatus =
  | 'idle'
  | 'recording'
  | 'captured'
  | 'transcribed'
  | 'minutesReady';

/** Why the host cannot finish minutes yet (null when unblocked). */
export type CompanionV1SessionPendingReason =
  | null
  | 'needs_transcription'
  | 'needs_network'
  | 'needs_pull'
  | 'needs_device_sync'
  | 'needs_segments'
  | 'needs_local_audio'
  | 'device_control_pending'
  | 'recovery_processing'
  | 'recovery_retry_wait'
  | 'recovery_paused'
  | 'capture_interrupted'
  | 'no_speech_detected'
  | 'minutes_source_changed';

/**
 * Dual product routes:
 * - offlineStore: record/store first; batch ASR later (no live network required during capture).
 * - onlineLive: real-time partials while recording; audio still stored as backup.
 */
export type CompanionV1MeetingMode = 'offlineStore' | 'onlineLive';

export type CompanionV1AudioChunkStatus = 'open' | 'sealed' | 'synced' | 'erased';

export interface CompanionV1AudioChunk {
  id: string;
  path: string | null;
  startedAt: string | null;
  stoppedAt: string | null;
  durationMs: number;
  bytes: number;
  status: CompanionV1AudioChunkStatus;
}

export interface CompanionV1SessionRetention {
  audioCached: boolean;
  transcriptCached: boolean;
  minutesCached: boolean;
  consentRequired: boolean;
  retentionLabel: string;
  expiresAt: string | null;
}

export interface CompanionV1RecordingPolicy {
  owner: 'host';
  deviceFlashRawCacheSeconds: number;
  targetMeetingSeconds: number;
  rawPcmBytesPerSecond: number;
  oneHourRawPcmBytes: number;
  chunkSeconds: number;
  oneHourChunkCount: number;
  maxAsrUploadBytes: number;
  preferredLongRecordingSource: 'hostMicrophone';
  deviceRole: 'triggerAndShortCache';
  longMeetingStrategy: 'hostChunkedWav';
  asrProviderMode: 'openaiCompatibleOrLocalCommand';
  /** Short offline capture: device flash then Sync/pull. */
  shortCaptureGuide: string;
  /** Long meeting: host owns audio; device is trigger/status only. */
  longMeetingGuide: string;
  /** Supported dual routes. */
  supportedMeetingModes: CompanionV1MeetingMode[];
  /** Default when meetingStart omits meetingMode. */
  defaultMeetingMode: CompanionV1MeetingMode;
  offlineStoreGuide: string;
  onlineLiveGuide: string;
}

export interface CompanionV1ActionItem {
  text: string;
  owner: string | null;
  due: string | null;
}

export interface CompanionV1MeetingMinutes {
  processing?: CompanionV1MinutesProcessing | null;
  sourceReviewRevision?: number | null;
  generatedAt: string;
  /** rules_l0 = deterministic host extractor; llm later. */
  source: 'rules_l0' | 'fixture';
  quality: 'draft' | 'final';
  summary: string[];
  decisions: string[];
  actionItems: CompanionV1ActionItem[];
  questions: string[];
  keywords: string[];
  markdown: string;
  /**
   * LLM downgrade reason. Present when L1 (DeepSeek) failed and we fell back
   * to the L0 rule draft, so the UI can surface *why* final minutes weren't
   * produced. undefined in normal operation.
   */
  llmNote?: string;
}

/** Submission coverage, independent of transcript/minutes accuracy. */
export interface CompanionV1MinutesProcessing {
  strategy: 'chunkedSourceBacked';
  sourceBytes: number;
  processedSourceBytes: number;
  totalChunks: number;
  completedChunks: number;
  resumedChunks: number;
  complete: boolean;
}

function cacheMinutesForMode(
  session: CompanionV1HostSession,
  minutes: CompanionV1MeetingMinutes,
  partialCount = 0,
): CompanionV1MinutesByMode {
  const next: CompanionV1MinutesByMode = {
    offlineStore: session.minutesByMode?.offlineStore ?? null,
    onlineLive: session.minutesByMode?.onlineLive ?? null,
  };
  const variant: CompanionV1MinutesVariant = {
    processing: minutes.processing,
    status: 'minutesReady',
    markdown: minutes.markdown,
    source: minutes.source,
    quality: minutes.quality,
    generatedAt: minutes.generatedAt,
    partialCount,
    sourceReviewRevision: minutes.sourceReviewRevision,
  };
  if (session.meetingMode === 'onlineLive') next.onlineLive = variant;
  else next.offlineStore = variant;
  return next;
}

/** Timed, optionally speaker-attributed ASR segment (product diarization path). */
export interface CompanionV1UtteranceSegment {
  text: string;
  startMs: number;
  endMs: number;
  /** 0-based speaker id when diarization succeeds. */
  speaker?: number | null;
}

export interface CompanionSpeakerName { speaker: number; name: string; }
export interface CompanionUtteranceEdit { index: number; text: string; speakerName?: string | null; }
export interface CompanionTranscriptReview {
  revision: number;
  editedAt: string;
  sourceTranscriptText: string;
  sourceUtterances: CompanionV1UtteranceSegment[];
  text?: string | null;
  utteranceEdits: CompanionUtteranceEdit[];
  speakerNames: CompanionSpeakerName[];
}
export interface CompanionTranscriptReviewEdit {
  expectedTranscriptText: string;
  expectedUtterances: CompanionV1UtteranceSegment[];
  expectedRevision: number;
  restoreOriginal?: boolean;
  text?: string | null;
  utteranceEdits?: CompanionUtteranceEdit[];
  speakerNames?: CompanionSpeakerName[];
}

export const COMPANION_CAPTURE_ONLY_PROMPT = '__companion_capture_only__';

export interface CompanionV1HostSession {
  id: string;
  title: string;
  source: CompanionV1HostSessionSource;
  status: CompanionV1HostSessionStatus;
  /** offlineStore = store-first; onlineLive = live partials during capture. */
  meetingMode: CompanionV1MeetingMode;
  /** Persisted choice; older rows keep automatic meeting processing. */
  processingPolicy?: 'automatic' | 'manual';
  /** Blocker after capture (needs ASR, network, or device pull). */
  pendingReason: CompanionV1SessionPendingReason;
  startedAt: string | null;
  stoppedAt: string | null;
  durationMs: number;
  audioPath: string | null;
  audioBytes: number;
  /** True once audio is sealed/synced on disk (offline always stores; online also stores backup). */
  audioStored: boolean;
  /** Durable WB55 journal identity; absent for host/imported sessions. */
  deviceRecordingId?: number | null;
  /** Durable segmented identity supplied by the native verified receiver. */
  deviceRecordingKey?: { deviceUid: string; formatEpoch: string; sessionId: string } | null;
  deviceTotalLength?: number | null;
  deviceSha256?: string | null;
  deviceReclaimed?: boolean;
  /** Interrupted capture: only the verified complete packet prefix survived. */
  captureIncomplete?: boolean;
  deviceRecordingEndReason?: 'user' | 'storageFull' | 'durationLimit' | 'lowBattery' | 'silence' | null;
  sourceDeviceId?: string | null;
  recorderControl?: {
    hostSession: string;
    deviceId: string;
    startRequest: number;
    maxSeconds: number;
    confirmed: { command: number; sequence: number; state: number; durationMs: number; finishedLocally?: boolean } | null;
    pending: { command: number; request: number; sequence: number } | null;
  } | null;
  recorderControlUncertain?: boolean;
  chunks: CompanionV1AudioChunk[];
  transcriptText: string;
  /** False for online-live prefixes; true only after final ASR/import commit. */
  transcriptFinal?: boolean;
  /** Cumulative live partials for onlineLive (mirrors into transcriptText while recording). */
  liveTranscriptText: string;
  transcriptPreview: string;
  transcriptSegments: number;
  /** Speaker-attributed utterances when diarization ran (Volc + models). */
  utterances?: CompanionV1UtteranceSegment[];
  transcriptReview?: CompanionTranscriptReview | null;
  bookmarkRevision?: number;
  bookmarks?: CompanionRecordingBookmark[];
  organization?: CompanionLibraryOrganization;
  deviceBookmarkImports?: string[];
  noteRevision?: number;
  meetingNotes?: import('./meetingNotes').CompanionMeetingNote[];
  minutes: CompanionV1MeetingMinutes | null;
  /** Independently persisted minutes products for the same durable recording. */
  minutesByMode?: CompanionV1MinutesByMode;
  /** Durable per-session authorization and retry checkpoint for automatic recovery. */
  recovery?: CompanionV1MeetingRecovery;
  exportMarkdown: string;
  exportedAt: string | null;
  retention: CompanionV1SessionRetention;
}

export interface CompanionV1MinutesVariant {
  processing?: CompanionV1MinutesProcessing | null;
  sourceReviewRevision?: number | null;
  status: 'minutesReady' | 'retryPending';
  markdown: string;
  source: string;
  quality: string;
  generatedAt: string | null;
  /** onlineLive only: durable-prefix ASR results observed before STOP. */
  partialCount: number;
}

export interface CompanionV1MeetingRecovery {
  intent: 'none' | 'processMeeting' | 'petChat';
  requestedMeetingMode: string;
  stage: 'idle' | 'pendingTranscription' | 'transcribing' | 'pendingMinutes'
    | 'generatingMinutes' | 'retryBackoff' | 'paused' | 'complete';
  attemptCount: number;
  maxAttempts: number;
  retryStage?: 'transcription' | 'minutes' | '';
  nextRetryAtUnixMs?: number | null;
  lastError?: string | null;
  /** Explicit choice to process this saved, interrupted original. */
  captureReviewConfirmed?: boolean;
}

export interface CompanionV1MinutesByMode {
  offlineStore: CompanionV1MinutesVariant | null;
  onlineLive: CompanionV1MinutesVariant | null;
}

export interface CompanionV1HostState {
  persistence?: {
    status: 'ready' | 'recovered' | 'blocked' | 'unsaved';
    message?: string | null;
    recoveryPath?: string | null;
  };
  recordingPolicy: CompanionV1RecordingPolicy;
  activeSessionId: string | null;
  selectedSessionId: string | null;
  sessions: CompanionV1HostSession[];
}

export interface CompanionV1ControlEcho {
  action: CompanionV1ControlAction;
  characteristicUuid: string;
  payloadHex: string;
  accepted: boolean;
  message: string;
}

export interface CompanionV1Snapshot {
  schema: typeof COMPANION_V1_SCHEMA;
  source: CompanionV1SnapshotSource;
  deviceId: string | null;
  connected: boolean;
  updatedAt: string;
  gatt: typeof COMPANION_V1_GATT_BOUNDARY;
  meeting: CompanionV1MeetingState;
  imu: CompanionV1ImuState;
  speaker: CompanionV1SpeakerState;
  wakeWord: CompanionV1WakeWordState;
  bleName: CompanionV1BleNameState;
  device: CompanionV1DeviceTransportState;
  oobe: CompanionV1OobeState;
  privacy: CompanionV1PrivacyState;
  host: CompanionV1HostState;
  lastControl: CompanionV1ControlEcho | null;
}

export interface CompanionV1ControlRequest {
  action: CompanionV1ControlAction;
  bleName?: string;
  sessionId?: string;
  promptId?: string;
  title?: string;
  transcriptText?: string;
  /** Select offlineStore | onlineLive on meetingStart (default from policy). */
  meetingMode?: CompanionV1MeetingMode;
  audioPath?: string;
  audioBytes?: number;
  deviceId?: string;
  durationMs?: number;
}

export function companionBleNameIsValid(value: string): boolean {
  const bytes = new TextEncoder().encode(value);
  if (bytes.length < 1 || bytes.length > COMPANION_V1_BLE_NAME_MAX_BYTES) return false;
  for (const char of value) {
    const code = char.charCodeAt(0);
    if (code < 0x20 || code > 0x7e) return false;
    if (char === '"' || char === "'" || char === ';' || char === '=' || char === '\\') return false;
  }
  return true;
}

export function createCompanionV1Fixture(
  overrides: Partial<CompanionV1Snapshot> = {},
): CompanionV1Snapshot {
  const now = new Date().toISOString();
  const base: CompanionV1Snapshot = {
    schema: COMPANION_V1_SCHEMA,
    source: 'fixture',
    deviceId: 'fixture-companion-v1',
    connected: false,
    updatedAt: now,
    gatt: COMPANION_V1_GATT_BOUNDARY,
    meeting: {
      supported: true,
      active: false,
      status: 'idle',
      startedAt: null,
      durationMs: 0,
      transcriptCount: 0,
    },
    imu: {
      supported: false,
      reserved: true,
      online: false,
      sampleHz: 0,
      motion: 'unknown',
      accel: { x: 0, y: 0, z: 1 },
      gyro: { x: 0, y: 0, z: 0 },
    },
    speaker: {
      supported: false,
      reserved: true,
      online: false,
      muted: false,
      volume: 65,
      status: 'idle',
    },
    wakeWord: {
      supported: false,
      armed: false,
      engine: 'fixture',
      keyword: 'hey companion',
      lastDetectedAt: null,
      confidence: 0,
    },
    bleName: {
      activeName: COMPANION_V1_DEFAULT_BLE_NAME,
      stagedName: COMPANION_V1_DEFAULT_BLE_NAME,
      maxLen: COMPANION_V1_BLE_NAME_MAX_BYTES,
      status: 'clean',
      pendingRestart: false,
    },
    device: createDefaultDeviceState(),
    oobe: createDefaultOobeState(),
    privacy: createDefaultPrivacyState(),
    host: createDefaultHostState(),
    lastControl: null,
  };
  return deepMergeCompanionSnapshot(base, overrides);
}

export function normalizeCompanionV1Snapshot(snapshot: CompanionV1Snapshot): CompanionV1Snapshot {
  return deepMergeCompanionSnapshot(createCompanionV1Fixture(), snapshot);
}

export function createDefaultHostState(): CompanionV1HostState {
  return {
    recordingPolicy: {
      owner: 'host',
      deviceFlashRawCacheSeconds: COMPANION_V1_DEVICE_FLASH_RECORDING_MAX_SECONDS,
      targetMeetingSeconds: COMPANION_V1_LONG_MEETING_TARGET_SECONDS,
      rawPcmBytesPerSecond: COMPANION_V1_RAW_PCM_BYTES_PER_SECOND,
      oneHourRawPcmBytes: COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
      chunkSeconds: COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS,
      oneHourChunkCount: COMPANION_V1_ONE_HOUR_CHUNKS,
      maxAsrUploadBytes: COMPANION_V1_ASR_UPLOAD_MAX_BYTES,
      preferredLongRecordingSource: 'hostMicrophone',
      deviceRole: 'triggerAndShortCache',
      longMeetingStrategy: 'hostChunkedWav',
      asrProviderMode: 'openaiCompatibleOrLocalCommand',
      shortCaptureGuide:
        'Short: device flash cache (≤60s) → Sync/pull → host ASR → minutes',
      longMeetingGuide:
        'Long meeting: host microphone (5 min chunks); device is trigger/status only — not full-hour BLE pull',
      supportedMeetingModes: ['offlineStore', 'onlineLive'],
      defaultMeetingMode: 'offlineStore',
      offlineStoreGuide:
        'Offline: store WAV/chunks first (no live ASR); later batch transcribe → L0/L1 minutes',
      onlineLiveGuide:
        'Online: live partial transcript while recording; audio still stored as backup; stop → minutes',
    },
    activeSessionId: null,
    selectedSessionId: null,
    sessions: [],
  };
}

export function createDefaultDeviceState(): CompanionV1DeviceTransportState {
  return {
    supported: true,
    providerId: 'companion-type-windows-ble',
    mode: 'windowsNative',
    scanning: false,
    connected: false,
    deviceId: null,
    lastSeenAt: null,
    signalRssi: null,
    recordingsAvailable: 0,
    recording: false,
    lastSyncAt: null,
    firmwareVersion: null,
    buildId: null,
    boardId: null,
    hardwareRevision: null,
    mcuUid: null,
    uiGeneration: null,
    recordingCapacity: null,
    connectionPhase: 'idle',
    rememberedDeviceId: null,
    autoReconnectEnabled: true,
    manualDisconnect: false,
    lastConnectedAt: null,
    lastReconnectAttemptAt: null,
    reconnectAttemptCount: 0,
    message: 'Not scanned',
  };
}

export function createDefaultOobeState(): CompanionV1OobeState {
  return {
    complete: false,
    lastRunAt: null,
    checks: [
      { id: 'bluetooth', label: '蓝牙连接', status: 'pending', message: '等待实板检查' },
      { id: 'firmware', label: '固件与板卡身份', status: 'pending', message: '等待实板检查' },
      { id: 'gatt', label: '核心 GATT', status: 'pending', message: '等待实板检查' },
      { id: 'boardMicrophone', label: '板端录音链路', status: 'pending', message: '等待实板检查' },
      { id: 'clock', label: '自动校时', status: 'pending', message: '等待实板检查' },
      { id: 'imu', label: 'IMU', status: 'pending', message: '等待实板检查' },
      { id: 'speaker', label: '扬声器', status: 'pending', message: '等待实板检查' },
      { id: 'display', label: '墨水屏', status: 'pending', message: '等待实板观察' },
      { id: 'touch', label: '触摸', status: 'pending', message: '等待实板操作' },
      { id: 'power', label: '电源与充电', status: 'pending', message: '等待实板测量' },
      { id: 'remoteServices', label: 'ASR / 纪要服务', status: 'pending', message: '不在硬件检查中调用' },
    ],
  };
}

export function createDefaultPrivacyState(): CompanionV1PrivacyState {
  return {
    localOnly: true,
    consentRequired: true,
    retentionDays: 7,
    audioCacheBytes: 0,
    transcriptBytes: 0,
    minutesBytes: 0,
    lastEraseAt: null,
    policyLabel: 'Local cache',
  };
}

export function applyCompanionV1ControlFixture(
  snapshot: CompanionV1Snapshot,
  request: CompanionV1ControlRequest,
): CompanionV1Snapshot {
  const next = structuredClone(normalizeCompanionV1Snapshot(snapshot)) as CompanionV1Snapshot;
  const now = new Date().toISOString();
  next.updatedAt = now;

  if (
    request.action === 'oobeRunChecks'
    && (next.meeting.active || next.host.sessions.some((session) => session.status === 'recording'))
  ) {
    throw new Error('正在录音或在线转写，不能运行首次使用检查；请先停止并完成当前会议');
  }

  if (
    (request.action === 'speakerPrompt' || request.action === 'speakerStop')
    && (!next.speaker.supported || !next.device.connected)
  ) {
    throw new Error('Companion speaker is not populated on this hardware.');
  }
  if (
    (request.action === 'wakeArm' || request.action === 'wakeDisable' || request.action === 'wakeTestDetect')
    && !next.wakeWord.supported
  ) {
    throw new Error('Companion wake-word engine is not populated on this hardware.');
  }

  switch (request.action) {
    case 'hostRetrySave':
      throw new Error('本地会议库恢复需要 Companion Type 桌面程序；浏览器演示不能验证磁盘保存。');
    case 'deviceScan':
      next.device = {
        ...next.device,
        scanning: false,
        connected: false,
        deviceId: request.deviceId ?? next.device.deviceId ?? 'companion-nucleo-wb55rg',
        lastSeenAt: now,
        signalRssi: -48,
        recordingsAvailable: Math.max(next.device.recordingsAvailable, 1),
        connectionPhase: 'discovered',
        message: 'Companion device discovered',
      };
      next.connected = false;
      break;
    case 'meetingRestoreAudio':
      throw new Error('回听文件恢复需要本机原音与校验记录；演示模式不会生成替代音频。');
    case 'deviceConnect':
      next.device = {
        ...next.device,
        connected: true,
        deviceId: request.deviceId ?? next.device.deviceId ?? 'companion-nucleo-wb55rg',
        lastSeenAt: now,
        signalRssi: next.device.signalRssi ?? -48,
        message: 'Companion device connected',
        connectionPhase: 'ready',
      };
      next.connected = true;
      break;
    case 'deviceDisconnect':
      next.device = {
        ...next.device,
        recordingCapacity: null,
        connected: false,
        message: 'Companion device disconnected',
        connectionPhase: 'manualDisconnected',
        manualDisconnect: Boolean(next.device.rememberedDeviceId),
      };
      next.connected = false;
      break;
    case 'deviceEnableAutoReconnect':
      next.device = {
        ...next.device,
        autoReconnectEnabled: true,
        manualDisconnect: false,
        connectionPhase: next.device.rememberedDeviceId ? 'offline' : 'idle',
      };
      break;
    case 'deviceDisableAutoReconnect':
      next.device = { ...next.device, autoReconnectEnabled: false };
      break;
    case 'deviceSyncRecordings': {
      const session = createSyncedDeviceSession(next, request, now);
      next.host.sessions = [session, ...next.host.sessions.filter((item) => item.id !== session.id)];
      next.host.selectedSessionId = session.id;
      next.host.activeSessionId = null;
      next.device = {
        ...next.device,
        connected: true,
        lastSyncAt: now,
        recordingsAvailable: Math.max(0, next.device.recordingsAvailable - 1),
        message: session.pendingReason === 'needs_transcription'
          ? 'Device recording synced; session captured — needs transcription before minutes'
          : 'Device recording synced to host cache',
      };
      next.connected = true;
      next.meeting = {
        ...next.meeting,
        active: false,
        status: 'captured',
        startedAt: null,
        durationMs: session.durationMs,
      };
      break;
    }
    case 'stageBleName': {
      const name = request.bleName ?? '';
      if (!companionBleNameIsValid(name)) {
        throw new Error('Companion BLE name must be 1-29 printable ASCII bytes and cannot contain quotes, semicolons, equals signs, or backslashes.');
      }
      next.bleName = { ...next.bleName, stagedName: name, status: 'staged', pendingRestart: true };
      break;
    }
    case 'applyBleName': {
      const requested = request.bleName?.trim();
      if (requested && !companionBleNameIsValid(requested)) {
        throw new Error('Companion BLE name must be 1-29 printable ASCII bytes and cannot contain quotes, semicolons, equals signs, or backslashes.');
      }
      const activeName = requested || next.bleName.stagedName;
      next.bleName = {
        ...next.bleName,
        stagedName: activeName,
        activeName,
        status: 'pendingRestart',
        pendingRestart: true,
      };
      break;
    }
    case 'resetBleName':
      next.bleName = {
        ...next.bleName,
        stagedName: COMPANION_V1_DEFAULT_BLE_NAME,
        status: 'staged',
        pendingRestart: true,
      };
      break;
    case 'oobeRunChecks':
      next.oobe = {
        complete: true,
        lastRunAt: now,
        checks: [
          { id: 'bluetooth', label: '蓝牙连接', status: 'warn', message: 'Fixture only：未执行物理扫描、配对或连接' },
          { id: 'firmware', label: '固件与板卡身份', status: 'warn', message: 'Fixture only：未连接实板，未读取 DEVICE_STATUS' },
          { id: 'gatt', label: '核心 GATT', status: 'warn', message: 'Fixture only：未发现或读取实板 GATT' },
          { id: 'boardMicrophone', label: '板端录音链路', status: 'warn', message: '未实测；主机麦克风不能作为板端通过证据' },
          { id: 'clock', label: '自动校时', status: 'warn', message: '未执行写后读回' },
          { id: 'imu', label: 'IMU', status: 'warn', message: '未读取 IMU_STATUS' },
          { id: 'speaker', label: '扬声器', status: 'warn', message: '未读取 SPEAKER_STATUS；未播放测试音' },
          { id: 'display', label: '墨水屏', status: 'warn', message: '未检查；无屏幕自检 GATT' },
          { id: 'touch', label: '触摸', status: 'warn', message: '未检查；无触摸自检 GATT' },
          { id: 'power', label: '电源与充电', status: 'warn', message: '未检查；无电源/充电自检 GATT' },
          { id: 'remoteServices', label: 'ASR / 纪要服务', status: 'warn', message: 'Fixture 检查不会调用外部服务' },
        ],
      };
      break;
    case 'meetingPause':
    case 'meetingResume':
    case 'meetingRecoverControl':
      throw new Error('设备暂停控制需要正式后端确认，不能用演示状态代替。');
    case 'meetingStart': {
      const session = createHostSession(next, request, now);
      next.host.sessions = [session, ...next.host.sessions.filter((item) => item.id !== session.id)];
      next.host.activeSessionId = session.id;
      next.host.selectedSessionId = session.id;
      next.meeting = {
        ...next.meeting,
        active: true,
        status: 'recording',
        startedAt: now,
        durationMs: 0,
      };
      break;
    }
    case 'meetingStop': {
      const session = requireSelectedSession(next, now, request);
      const durationMs = request.durationMs ?? Math.max(session.durationMs, 60000);
      const audioBytes = request.audioBytes ?? estimatePcmBytes(durationMs);
      const hasTranscript = session.transcriptText.trim().length > 0
        || session.liveTranscriptText.trim().length > 0;
      const finalTranscript = session.transcriptText.trim()
        || session.liveTranscriptText.trim();
      // Offline: always store-first; empty transcript → needs_transcription.
      // Online: live text already present → transcribed; still keep audioStored.
      const isOnline = session.meetingMode === 'onlineLive';
      const status: CompanionV1HostSessionStatus = hasTranscript && isOnline
        ? 'transcribed'
        : 'captured';
      const pendingReason: CompanionV1SessionPendingReason = hasTranscript
        ? null
        : 'needs_transcription';
      updateHostSession(next, session.id, {
        status,
        pendingReason,
        stoppedAt: now,
        durationMs,
        chunks: sealSessionChunks(session, now, durationMs, request.audioBytes),
        audioBytes,
        audioStored: true,
        transcriptText: finalTranscript || session.transcriptText,
        transcriptPreview: previewText(finalTranscript || session.transcriptText),
        transcriptSegments: splitTranscriptSegments(finalTranscript || session.transcriptText).length,
        retention: {
          ...session.retention,
          audioCached: true,
          transcriptCached: hasTranscript,
        },
      });
      next.host.activeSessionId = null;
      next.meeting = {
        ...next.meeting,
        active: false,
        status: status === 'transcribed' ? 'transcribed' : 'captured',
        durationMs,
        transcriptCount: countTranscriptSessions(next),
      };
      break;
    }
    case 'meetingAppendLiveTranscript': {
      const session = requireSelectedSession(next, now, request);
      if (session.meetingMode !== 'onlineLive') {
        throw new Error('Live transcript append requires meetingMode=onlineLive.');
      }
      if (session.status !== 'recording') {
        throw new Error('Live transcript append requires an active recording session.');
      }
      const delta = normalizeTranscript(request.transcriptText ?? '');
      if (!delta) {
        throw new Error('Live transcript append requires non-empty transcriptText.');
      }
      const live = normalizeTranscript(
        session.liveTranscriptText ? `${session.liveTranscriptText} ${delta}` : delta,
      );
      updateHostSession(next, session.id, {
        liveTranscriptText: live,
        transcriptText: live,
        transcriptPreview: previewText(live),
        transcriptSegments: splitTranscriptSegments(live).length,
        pendingReason: null,
        retention: {
          ...session.retention,
          transcriptCached: true,
        },
      });
      // Keep meeting.active while recording; surface partial progress in echo only.
      break;
    }
    case 'meetingFinalize': {
      const session = requireSelectedSession(next, now, request);
      if (session.transcriptText.trim()) {
        const minutes = buildCompanionMeetingMinutes(session, now);
        updateHostSession(next, session.id, {
          status: 'minutesReady',
          pendingReason: null,
          minutes,
          minutesByMode: cacheMinutesForMode(session, minutes),
          exportMarkdown: minutes.markdown,
          exportedAt: now,
          retention: {
            ...session.retention,
            minutesCached: true,
          },
        });
        next.meeting.status = 'minutesReady';
      } else {
        updateHostSession(next, session.id, {
          status: session.status === 'recording' ? 'captured' : session.status,
          pendingReason: 'needs_transcription',
          stoppedAt: session.stoppedAt ?? now,
        });
        next.meeting.status = 'finalized';
      }
      next.meeting.active = false;
      next.host.activeSessionId = null;
      next.meeting.transcriptCount = countTranscriptSessions(next);
      break;
    }
    case 'meetingImportTranscript': {
      const session = requireSelectedSession(next, now, request);
      const transcriptText = normalizeTranscript(request.transcriptText ?? '');
      if (!transcriptText) {
        throw new Error('Import requires non-empty transcript text.');
      }
      applyTranscriptToSession(next, session, transcriptText, true);
      break;
    }
    case 'meetingTranscribeAudio': {
      const session = requireSelectedSession(next, now, request);
      const transcriptText = normalizeTranscript(request.transcriptText ?? '');
      if (!transcriptText) {
        // Soft path: audio is captured but no ASR provider/result yet.
        const pending: CompanionV1SessionPendingReason = next.privacy.localOnly
          ? 'needs_transcription'
          : 'needs_network';
        updateHostSession(next, session.id, {
          status: 'captured',
          pendingReason: pending,
        });
        next.meeting = {
          ...next.meeting,
          active: false,
          status: 'captured',
        };
        break;
      }
      applyTranscriptToSession(next, session, transcriptText, false);
      break;
    }
    case 'meetingGenerateMinutes': {
      const session = requireSelectedSession(next, now, request);
      if (!session.transcriptText.trim()) {
        updateHostSession(next, session.id, {
          status: 'captured',
          pendingReason: 'needs_transcription',
        });
        next.meeting.status = 'captured';
        throw new Error(
          'Generate minutes requires a transcript. Import text or run Transcribe after configuring ASR.',
        );
      }
      const minutes = buildCompanionMeetingMinutes(session, now);
      updateHostSession(next, session.id, {
        status: 'minutesReady',
        pendingReason: null,
        minutes,
        minutesByMode: cacheMinutesForMode(session, minutes),
        exportMarkdown: minutes.markdown,
        retention: {
          ...session.retention,
          minutesCached: true,
        },
      });
      next.meeting = {
        ...next.meeting,
        active: false,
        status: 'minutesReady',
        transcriptCount: countTranscriptSessions(next),
      };
      break;
    }
    case 'meetingExportMarkdown':
    case 'meetingExportTxt':
    case 'meetingExportJson':
    case 'meetingExportSrt':
    case 'meetingExportActionsTodo':
    case 'meetingExportActionsIcal': {
      const session = requireSelectedSession(next, now, request);
      const minutes = session.minutes ?? buildCompanionMeetingMinutes(session, now);
      let exportBody = minutes.markdown;
      if (request.action === 'meetingExportTxt') {
        exportBody = [session.title, '', session.transcriptText, '', minutes.markdown].join('\n');
      } else if (request.action === 'meetingExportJson') {
        exportBody = JSON.stringify({ title: session.title, transcript: session.transcriptText, minutes }, null, 2);
      } else if (request.action === 'meetingExportSrt') {
        exportBody = session.transcriptText
          .split(/\n+/)
          .filter(Boolean)
          .map((line, index) => `${index + 1}\n00:00:${String(index).padStart(2, '0')},000 --> 00:00:${String(index + 1).padStart(2, '0')},000\n${line}\n`)
          .join('\n') || minutes.markdown;
      } else if (request.action === 'meetingExportActionsTodo') {
        exportBody = (minutes.actionItems ?? []).map((item) => `- [ ] ${item.text}`).join('\n') || '- [ ] (none)';
      } else if (request.action === 'meetingExportActionsIcal') {
        exportBody = ['BEGIN:VCALENDAR', 'VERSION:2.0', ...(minutes.actionItems ?? []).flatMap((item) => ['BEGIN:VTODO', `SUMMARY:${item.text}`, 'END:VTODO']), 'END:VCALENDAR'].join('\r\n');
      }
      updateHostSession(next, session.id, {
        status: 'minutesReady',
        minutes,
        minutesByMode: cacheMinutesForMode(session, minutes),
        exportMarkdown: exportBody,
        exportedAt: now,
        retention: {
          ...session.retention,
          minutesCached: true,
        },
      });
      next.meeting = {
        ...next.meeting,
        active: false,
        status: 'minutesReady',
        transcriptCount: countTranscriptSessions(next),
      };
      break;
    }
    case 'meetingLoadDemo': {
      // One-click owner demo: skip mic/ASR complexity, land on minutesReady.
      const demoText = normalizeTranscript(
        request.transcriptText
          ?? [
            'Decision: Companion host owns long meeting recordings.',
            'Action owner: Chen due: Friday validates minutes export.',
            'Question: should offline show needs_transcription?',
          ].join('\n'),
      );
      const durationMs = request.durationMs ?? 15_000;
      const session = createHostSession(
        next,
        {
          action: 'meetingStart',
          title: request.title ?? '一键演示纪要',
          sessionId: request.sessionId,
          audioPath: request.audioPath ?? 'demo://companion-type/mechanical-voice.wav',
          audioBytes: request.audioBytes ?? estimatePcmBytes(durationMs),
          durationMs,
        },
        now,
      );
      session.source = 'hostMicrophone';
      session.meetingMode = request.meetingMode === 'onlineLive' ? 'onlineLive' : 'offlineStore';
      session.status = 'minutesReady';
      session.pendingReason = null;
      session.startedAt = now;
      session.stoppedAt = now;
      session.durationMs = durationMs;
      session.audioStored = true;
      session.transcriptText = demoText;
      session.liveTranscriptText = demoText;
      session.transcriptPreview = previewText(demoText);
      session.transcriptSegments = splitTranscriptSegments(demoText).length;
      session.chunks = [
        createAudioChunk(
          `${session.id}-demo`,
          session.audioPath,
          now,
          now,
          durationMs,
          session.audioBytes,
          'sealed',
        ),
      ];
      const minutes = buildCompanionMeetingMinutes(session, now);
      session.minutes = minutes;
      session.minutesByMode = cacheMinutesForMode(session, minutes);
      session.exportMarkdown = minutes.markdown;
      session.exportedAt = now;
      session.retention = createSessionRetention(true, true, true);
      next.host.sessions = [session, ...next.host.sessions.filter((item) => item.id !== session.id)];
      next.host.selectedSessionId = session.id;
      next.host.activeSessionId = null;
      next.meeting = {
        ...next.meeting,
        active: false,
        status: 'minutesReady',
        startedAt: null,
        durationMs,
        transcriptCount: countTranscriptSessions(next),
      };
      break;
    }
    case 'meetingSelectSession': {
      if (!request.sessionId || !next.host.sessions.some((session) => session.id === request.sessionId)) {
        throw new Error('A valid sessionId is required.');
      }
      next.host.selectedSessionId = request.sessionId;
      break;
    }
    case 'meetingResetSession':
      next.host.selectedSessionId = null;
      next.host.activeSessionId = null;
      next.meeting = {
        ...next.meeting,
        active: false,
        status: 'idle',
        startedAt: null,
        durationMs: 0,
        transcriptCount: 0,
      };
      break;
    case 'privacyEraseAudio': {
      const session = requireSelectedSession(next, now, request);
      updateHostSession(next, session.id, {
        audioPath: null,
        audioBytes: 0,
        audioStored: false,
        recovery: undefined,
        pendingReason: null,
        chunks: session.chunks.map((chunk) => ({ ...chunk, path: null, bytes: 0, status: 'erased' })),
        retention: {
          ...session.retention,
          audioCached: false,
        },
      });
      next.privacy.lastEraseAt = now;
      break;
    }
    case 'privacyEraseTranscript': {
      const session = requireSelectedSession(next, now, request);
      updateHostSession(next, session.id, {
        status: session.audioPath || session.audioBytes ? 'captured' : 'idle',
        pendingReason: session.audioPath || session.audioBytes ? 'needs_transcription' : null,
        transcriptText: '',
        transcriptFinal: false,
        recovery: undefined,
        liveTranscriptText: '',
        transcriptPreview: '',
        transcriptSegments: 0,
        utterances: [],
        transcriptReview: null,
        noteRevision: (session.noteRevision ?? 0) + 1,
        meetingNotes: [],
        minutes: null,
        minutesByMode: { offlineStore: null, onlineLive: null },
        exportMarkdown: '',
        exportedAt: null,
        retention: {
          ...session.retention,
          transcriptCached: false,
          minutesCached: false,
        },
      });
      next.meeting.status = session.audioPath || session.audioBytes ? 'captured' : 'idle';
      next.meeting.transcriptCount = countTranscriptSessions(next);
      next.privacy.lastEraseAt = now;
      break;
    }
    case 'privacyEraseAll':
      next.host = createDefaultHostState();
      next.meeting = {
        ...next.meeting,
        active: false,
        status: 'idle',
        startedAt: null,
        durationMs: 0,
        transcriptCount: 0,
      };
      next.privacy = {
        ...createDefaultPrivacyState(),
        lastEraseAt: now,
      };
      break;
    case 'privacyDeleteSession': {
      const session = requireSelectedSession(next, now, request);
      next.host.sessions = next.host.sessions.filter((item) => item.id !== session.id);
      next.host.selectedSessionId = next.host.sessions[0]?.id ?? null;
      if (next.host.activeSessionId === session.id) next.host.activeSessionId = null;
      next.meeting.transcriptCount = countTranscriptSessions(next);
      next.privacy.lastEraseAt = now;
      break;
    }
    case 'speakerPrompt':
      next.speaker = { ...next.speaker, online: true, status: 'prompting' };
      break;
    case 'speakerStop':
      next.speaker = { ...next.speaker, status: 'idle' };
      break;
    case 'wakeArm':
      next.wakeWord = { ...next.wakeWord, armed: true, confidence: 0 };
      break;
    case 'wakeDisable':
      next.wakeWord = { ...next.wakeWord, armed: false, confidence: 0 };
      break;
    case 'wakeTestDetect':
      next.wakeWord = {
        ...next.wakeWord,
        armed: true,
        lastDetectedAt: now,
        confidence: 0.92,
      };
      break;
  }

  next.privacy = refreshPrivacyState(next, next.privacy.lastEraseAt);

  next.lastControl = {
    action: request.action,
    characteristicUuid: characteristicForCompanionAction(request.action),
    payloadHex: companionActionPayloadHex(request),
    accepted: true,
    message: hostOnlyAction(request.action) ? 'host workflow accepted' : 'fixture accepted',
  };
  return next;
}

export function selectedCompanionHostSession(snapshot: CompanionV1Snapshot): CompanionV1HostSession | null {
  const normalized = normalizeCompanionV1Snapshot(snapshot);
  const selectedId = normalized.host.selectedSessionId ?? normalized.host.activeSessionId;
  if (selectedId) {
    return normalized.host.sessions.find((session) => session.id === selectedId) ?? null;
  }
  return normalized.host.sessions[0] ?? null;
}

export function companionSessionHasFinalTranscript(session: CompanionV1HostSession): boolean {
  if (!session.transcriptText.trim() || session.status === 'recording') return false;
  if (session.transcriptFinal !== undefined) return session.transcriptFinal;
  // Older saved sessions did not carry the flag. Keep completed legacy text
  // readable, but never promote an armed recovery job's unknown prefix.
  return session.recovery?.intent !== 'processMeeting'
    && (session.status === 'transcribed' || session.status === 'minutesReady');
}

export function describeCompanionMeetingRecovery(session: CompanionV1HostSession): {
  label: string;
  message: string;
  retryAction: 'meetingTranscribeAudio' | 'meetingGenerateMinutes' | null;
  isProcessing: boolean;
} | null {
  const recovery = session.recovery;
  if (session.pendingReason === 'needs_local_audio') return {
    label: '原音已收齐，回听待生成', message: '原音已保存在电脑，生成本机回听文件后即可继续处理。',
    retryAction: null, isProcessing: false,
  };
  if (session.captureIncomplete && !recovery?.captureReviewConfirmed && session.audioStored
    && session.status !== 'recording' && recovery?.stage !== 'complete') {
    return { label: '录音中断，片段已保存',
      message: `已保存 ${Math.floor(session.durationMs / 1000)} 秒。可以先回听或导出；整理结果只覆盖已保存的片段。`,
      retryAction: companionSessionHasFinalTranscript(session) ? 'meetingGenerateMinutes' : 'meetingTranscribeAudio',
      isProcessing: false };
  }
  if (session.processingPolicy === 'manual' && recovery?.lastError && recovery.stage === 'paused') {
    return { label: session.pendingReason === 'no_speech_detected' ? '未识别到人声' : '处理未完成',
      message: `${recovery.lastError} 原音已保留，选择转写或生成纪要可手动重试。`,
      retryAction: companionSessionHasFinalTranscript(session) ? 'meetingGenerateMinutes' : 'meetingTranscribeAudio',
      isProcessing: false };
  }
  if (!recovery || recovery.intent !== 'processMeeting' || session.status === 'recording'
    || recovery.stage === 'idle' || recovery.stage === 'complete') return null;
  if (recovery.requestedMeetingMode !== session.meetingMode) {
    return { label: '恢复暂停', message: '会议模式已改变，请检查这场会议的原始处理模式。', retryAction: null, isProcessing: false };
  }
  if (session.pendingReason === 'needs_device_sync') {
    return { label: '等待设备同步', message: '录音仍在设备端。连接 Companion 后同步录音，再继续处理。', retryAction: null, isProcessing: false };
  }
  const isProcessing = recovery.stage === 'transcribing' || recovery.stage === 'generatingMinutes';
  const label = session.pendingReason === 'no_speech_detected' ? '未识别到人声'
    : recovery.stage === 'paused' ? '恢复暂停'
    : recovery.stage === 'retryBackoff' ? '等待重试'
      : recovery.stage === 'generatingMinutes' ? '正在整理纪要'
        : recovery.stage === 'transcribing' ? '正在转写' : '等待处理';
  const retryable = recovery.stage === 'paused' || recovery.stage === 'retryBackoff';
  // A live prefix must go through final ASR, even if a stale checkpoint says
  // minutes. Always address the same session when the user resumes it.
  const retryAction = !retryable ? null : companionSessionHasFinalTranscript(session)
    ? 'meetingGenerateMinutes' : 'meetingTranscribeAudio';
  return {
    label,
    message: describeSessionPendingReason(session.pendingReason)
      ?? (recovery.stage === 'pendingMinutes' ? '转写已保存，正在等待整理纪要。' : '录音已保存，正在等待转写。'),
    retryAction,
    isProcessing,
  };
}

export function buildCompanionMeetingMinutes(
  session: CompanionV1HostSession,
  generatedAt = new Date().toISOString(),
): CompanionV1MeetingMinutes {
  const segments = splitTranscriptSegments(session.transcriptText);
  const summaryPriority = [
    /主持人|参会人|attendees?|facilitator/i,
    /压缩同步|先压(?:缩)?再传|录音.*压缩|compressed?\s+sync/i,
    /(?:空中|wire).*(?:压缩比|等效|真速)|(?:压缩比|等效).*(?:空中|wire)/i,
    /(?:八千|8000).*(?:七点八|7[.。]?8|压缩)|(?:七点八|7[.。]?8).*(?:八千|8000)/i,
    /解压.*上采样|上采样.*解压|(?:解压|上采样).*(?:一万六|16000)|(?:一万六|16000).*(?:解压|上采样)/i,
    /会议纪要.*(?:音质|识别|关键词|决策)|(?:识别|关键词).*(?:会议纪要|决策)/i,
    /(?:连续\s*(?:10|十)分钟|(?:10|十)分钟\s*连续)/i,
    /离线先存|在线停会|offline\s*store|online\s*live/i,
    /fail(?:ure)?\s*close|失败.*重录/i,
  ];
  const summaryLimit = 6;
  // Keep the opening context, then spend the remaining bounded slots on
  // salient facts. Taking the first two unconditionally often wastes a slot
  // on markers such as "第一轮" and drops the actual offline meeting content.
  const summary = [...segments.slice(0, 1)];
  for (const pattern of summaryPriority) {
    const candidate = segments.find((segment) => pattern.test(segment) && !summary.includes(segment));
    if (candidate) summary.push(candidate);
    if (summary.length >= summaryLimit) break;
  }
  for (const segment of segments) {
    if (summary.length >= summaryLimit) break;
    if (!summary.includes(segment)) summary.push(segment);
  }
  const decisions = extractMatchingSegments(segments, DECISION_PATTERNS).slice(0, 5);
  const actionItems = extractActionItems(segments).slice(0, 8);
  const questions = segments.filter((segment) => segment.includes('?') || segment.includes('\uff1f')).slice(0, 5);
  const keywords = extractKeywords(session.transcriptText).slice(0, 10);
  const minutes: Omit<CompanionV1MeetingMinutes, 'markdown'> = {
    generatedAt,
    source: 'rules_l0',
    quality: 'draft',
    summary: summary.length ? summary : ['No transcript content was available.'],
    decisions,
    actionItems,
    questions,
    keywords,
  };
  return {
    ...minutes,
    markdown: renderMinutesMarkdown(session, minutes),
  };
}

export function describeSessionPendingReason(
  reason: CompanionV1SessionPendingReason,
): string | null {
  switch (reason) {
    case 'needs_transcription':
      return 'Audio captured. Configure ASR or import a transcript, then generate minutes.';
    case 'needs_network':
      return 'Cloud ASR/minutes need network (or switch to local-only ASR).';
    case 'needs_pull':
      return 'Device has recordings that still need Sync/pull into the host.';
    case 'needs_device_sync':
      return '录音仍在设备端，重新连接 Companion 后会继续同步。';
    case 'needs_segments':
      return '原音分段尚未收齐，请连接来源设备继续同步。';
    case 'needs_local_audio':
      return '原音已收齐，等待生成本机回听文件，无需再次从设备收取。';
    case 'recovery_processing':
      return '正在自动恢复这场会议的转写或纪要。';
    case 'recovery_retry_wait':
      return '处理暂时失败，已保留录音并将在短暂退避后自动重试。';
    case 'recovery_paused':
      return '自动恢复已暂停，录音和已有文本仍保留；请检查错误后手动重试。';
    case 'capture_interrupted':
      return '录音曾意外中断，已保存的原音可以回听或导出；选择整理片段后才继续转写和纪要。';
    case 'minutes_source_changed':
      return '转写已修订。已有纪要仍保留，请重新生成或核对后使用。';
    case 'no_speech_detected':
      return '转写服务未识别到人声，原录音已保留。请先回听并检查拾音和音量，再手动重试；不会自动反复上传。';
    default:
      return null;
  }
}

function applyTranscriptToSession(
  snapshot: CompanionV1Snapshot,
  session: CompanionV1HostSession,
  transcriptText: string,
  fromImport: boolean,
): void {
  updateHostSession(snapshot, session.id, {
    source: fromImport && session.source === 'fixture' ? 'importedTranscript' : session.source,
    status: 'transcribed',
    pendingReason: null,
    transcriptText,
    transcriptPreview: previewText(transcriptText),
    transcriptSegments: splitTranscriptSegments(transcriptText).length,
    retention: {
      ...session.retention,
      transcriptCached: true,
    },
  });
  snapshot.meeting = {
    ...snapshot.meeting,
    active: false,
    status: 'transcribed',
    transcriptCount: countTranscriptSessions(snapshot),
  };
}

export function characteristicForCompanionAction(action: CompanionV1ControlAction): string {
  if (action === 'hostRetrySave' || action === 'meetingRestoreAudio') return COMPANION_V1_HOST_RECORDING_CHANNEL;
  if (action === 'deviceScan' || action === 'deviceConnect' || action === 'deviceDisconnect'
    || action === 'deviceEnableAutoReconnect' || action === 'deviceDisableAutoReconnect'
    || action === 'deviceSyncRecordings') {
    return COMPANION_V1_HOST_DEVICE_CHANNEL;
  }
  if (action === 'stageBleName') return COMPANION_V1_HOST_DEVICE_CHANNEL;
  if (action === 'applyBleName' || action === 'resetBleName') {
    return COMPANION_V1_GATT_BOUNDARY.bleNameConfigUuid;
  }
  if (action === 'oobeRunChecks') {
    return COMPANION_V1_HOST_SETUP_CHANNEL;
  }
  if (action === 'meetingStart' || action === 'meetingStop' || action === 'meetingFinalize'
      || action === 'meetingPause' || action === 'meetingResume' || action === 'meetingRecoverControl') {
    return COMPANION_V1_GATT_BOUNDARY.meetingControlUuid;
  }
  if (
    action === 'meetingImportTranscript'
    || action === 'meetingAppendLiveTranscript'
    || action === 'meetingTranscribeAudio'
    || action === 'meetingGenerateMinutes'
    || action === 'meetingExportMarkdown'
    || action === 'meetingExportTxt'
    || action === 'meetingExportJson'
    || action === 'meetingExportSrt'
    || action === 'meetingExportActionsTodo'
    || action === 'meetingExportActionsIcal'
    || action === 'meetingLoadDemo'
    || action === 'meetingSelectSession'
    || action === 'meetingResetSession'
  ) {
    return action === 'meetingGenerateMinutes'
      || action === 'meetingExportMarkdown'
      || action === 'meetingExportTxt'
      || action === 'meetingExportJson'
      || action === 'meetingExportSrt'
      || action === 'meetingExportActionsTodo'
      || action === 'meetingExportActionsIcal'
      || action === 'meetingLoadDemo'
      ? COMPANION_V1_HOST_MINUTES_CHANNEL
      : COMPANION_V1_HOST_RECORDING_CHANNEL;
  }
  if (action === 'speakerPrompt' || action === 'speakerStop') {
    return COMPANION_V1_GATT_BOUNDARY.speakerControlUuid;
  }
  if (action === 'privacyEraseAudio' || action === 'privacyEraseTranscript' || action === 'privacyEraseAll' || action === 'privacyDeleteSession') {
    return COMPANION_V1_HOST_PRIVACY_CHANNEL;
  }
  return COMPANION_V1_GATT_BOUNDARY.wakeWordControlUuid;
}

export function companionActionPayloadHex(request: CompanionV1ControlRequest): string {
  if (hostOnlyAction(request.action)) {
    const hostPayload = `${request.action}:${request.sessionId ?? ''}:${request.title ?? ''}`;
    return bytesToHex(new TextEncoder().encode(hostPayload).slice(0, 48));
  }

  const bytes = [actionCommand(request.action)];
  if (request.action === 'stageBleName' || request.action === 'applyBleName' || request.action === 'resetBleName') {
    bytes.push(COMPANION_V1_BLE_NAME_MAX_BYTES);
    bytes.push(...new TextEncoder().encode(request.bleName ?? '').slice(0, COMPANION_V1_BLE_NAME_MAX_BYTES));
  }
  return bytes.map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function normalizeMeetingMode(
  value: CompanionV1MeetingMode | string | undefined | null,
  fallback: CompanionV1MeetingMode = 'offlineStore',
): CompanionV1MeetingMode {
  if (value === 'onlineLive' || value === 'offlineStore') return value;
  return fallback;
}

function createHostSession(
  snapshot: CompanionV1Snapshot,
  request: CompanionV1ControlRequest,
  now: string,
): CompanionV1HostSession {
  const id = request.sessionId ?? nextSessionId(snapshot, now);
  const durationMs = request.durationMs ?? 0;
  const suppliedAudioPath = request.audioPath ?? null;
  const audioPath = suppliedAudioPath ?? defaultHostAudioPath(id);
  const audioBytes = request.audioBytes ?? (durationMs ? estimatePcmBytes(durationMs) : 0);
  const meetingMode = normalizeMeetingMode(
    request.meetingMode,
    snapshot.host.recordingPolicy.defaultMeetingMode ?? 'offlineStore',
  );
  return {
    id,
    title: (request.title ?? 'Companion meeting').trim() || 'Companion meeting',
    source: suppliedAudioPath ? 'deviceFlash' : 'hostMicrophone',
    status: 'recording',
    meetingMode,
    processingPolicy: request.promptId === COMPANION_CAPTURE_ONLY_PROMPT ? 'manual' : 'automatic',
    pendingReason: null,
    startedAt: now,
    stoppedAt: null,
    durationMs,
    audioPath,
    audioBytes,
    audioStored: false,
    sourceDeviceId: request.deviceId ?? null,
    chunks: [createAudioChunk(`${id}-chunk-1`, audioPath, now, null, durationMs, audioBytes, 'open')],
    transcriptText: '',
    liveTranscriptText: '',
    transcriptPreview: '',
    transcriptSegments: 0,
    minutes: null,
    minutesByMode: { offlineStore: null, onlineLive: null },
    exportMarkdown: '',
    exportedAt: null,
    retention: createSessionRetention(true, false, false),
  };
}

function createSyncedDeviceSession(
  snapshot: CompanionV1Snapshot,
  request: CompanionV1ControlRequest,
  now: string,
): CompanionV1HostSession {
  const durationMs = request.durationMs ?? COMPANION_V1_DEVICE_FLASH_RECORDING_MAX_SECONDS * 1000;
  const audioBytes = request.audioBytes ?? estimatePcmBytes(durationMs);
  const audioPath = request.audioPath ?? 'device://companion/flash/latest.wav';
  const session = createHostSession(
    snapshot,
    {
      ...request,
      action: 'meetingStart',
      title: request.title ?? 'Companion device recording',
      audioPath,
      audioBytes,
      durationMs,
    },
    now,
  );
  session.source = 'deviceFlash';
  session.meetingMode = 'offlineStore';
  session.status = 'captured';
  session.pendingReason = 'needs_transcription';
  session.startedAt = null;
  session.stoppedAt = now;
  session.durationMs = durationMs;
  session.audioBytes = audioBytes;
  session.audioStored = true;
  session.chunks = [createAudioChunk(`${session.id}-flash-cache`, audioPath, null, now, durationMs, audioBytes, 'synced')];
  session.retention = createSessionRetention(true, false, false);
  return session;
}

function requireSelectedSession(
  snapshot: CompanionV1Snapshot,
  now: string,
  request: CompanionV1ControlRequest,
): CompanionV1HostSession {
  const requested = request.sessionId
    ? snapshot.host.sessions.find((session) => session.id === request.sessionId)
    : null;
  const selected = requested ?? selectedCompanionHostSession(snapshot);
  if (selected) {
    snapshot.host.selectedSessionId = selected.id;
    return selected;
  }
  const session = createHostSession(snapshot, { ...request, action: 'meetingStart' }, now);
  session.status = 'captured';
  session.pendingReason = 'needs_transcription';
  session.startedAt = null;
  session.stoppedAt = now;
  snapshot.host.sessions = [session, ...snapshot.host.sessions];
  snapshot.host.selectedSessionId = session.id;
  return session;
}

function updateHostSession(
  snapshot: CompanionV1Snapshot,
  sessionId: string,
  patch: Partial<CompanionV1HostSession>,
) {
  snapshot.host.sessions = snapshot.host.sessions.map((session) => (
    session.id === sessionId ? { ...session, ...patch } : session
  ));
}

function createAudioChunk(
  id: string,
  path: string | null,
  startedAt: string | null,
  stoppedAt: string | null,
  durationMs: number,
  bytes: number,
  status: CompanionV1AudioChunkStatus,
): CompanionV1AudioChunk {
  return { id, path, startedAt, stoppedAt, durationMs, bytes, status };
}

function sealSessionChunks(
  session: CompanionV1HostSession,
  now: string,
  durationMs: number,
  audioBytes?: number,
): CompanionV1AudioChunk[] {
  const totalBytes = audioBytes ?? estimatePcmBytes(durationMs);
  if (!session.audioPath) return session.chunks;
  const chunkDurationMs = COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS * 1000;
  const chunkCount = Math.max(1, Math.ceil(Math.max(durationMs, 1) / chunkDurationMs));
  let remainingBytes = totalBytes;

  return Array.from({ length: chunkCount }, (_, index) => {
    const elapsedBefore = index * chunkDurationMs;
    const chunkMs = index === chunkCount - 1
      ? Math.max(0, durationMs - elapsedBefore)
      : Math.min(chunkDurationMs, Math.max(0, durationMs - elapsedBefore));
    const bytes = index === chunkCount - 1
      ? remainingBytes
      : durationMs > 0
        ? Math.round(totalBytes * (chunkMs / durationMs))
        : 0;
    remainingBytes = Math.max(0, remainingBytes - bytes);
    return createAudioChunk(
      `${session.id}-chunk-${index + 1}`,
      chunkPath(session.audioPath!, index, chunkCount),
      index === 0 ? session.startedAt : null,
      now,
      chunkMs,
      bytes,
      'sealed',
    );
  });
}

function defaultHostAudioPath(sessionId: string): string {
  return `host://companion-type/recordings/${sessionId}.wav`;
}

function chunkPath(basePath: string, index: number, total: number): string {
  if (total <= 1 || !basePath.startsWith('host://')) {
    return basePath;
  }
  return `${basePath}#chunk-${String(index + 1).padStart(3, '0')}`;
}

function createSessionRetention(
  audioCached: boolean,
  transcriptCached: boolean,
  minutesCached: boolean,
): CompanionV1SessionRetention {
  return {
    audioCached,
    transcriptCached,
    minutesCached,
    consentRequired: true,
    retentionLabel: 'Local until manually deleted',
    expiresAt: null,
  };
}

function estimatePcmBytes(durationMs: number): number {
  return Math.max(0, Math.round((durationMs / 1000) * COMPANION_V1_RAW_PCM_BYTES_PER_SECOND));
}

function refreshPrivacyState(
  snapshot: CompanionV1Snapshot,
  lastEraseAt: string | null,
): CompanionV1PrivacyState {
  const encoder = new TextEncoder();
  const audioCacheBytes = snapshot.host.sessions.reduce((sum, session) => sum + session.audioBytes, 0);
  const transcriptBytes = snapshot.host.sessions.reduce(
    (sum, session) => sum + encoder.encode(session.transcriptText).length,
    0,
  );
  const minutesBytes = snapshot.host.sessions.reduce(
    (sum, session) => sum + encoder.encode(session.exportMarkdown).length,
    0,
  );
  return {
    ...snapshot.privacy,
    audioCacheBytes,
    transcriptBytes,
    minutesBytes,
    lastEraseAt,
  };
}

function nextSessionId(snapshot: CompanionV1Snapshot, now: string): string {
  const stamp = now.replace(/[-:.TZ]/g, '').slice(0, 14);
  return `meeting-${stamp}-${snapshot.host.sessions.length + 1}`;
}

function normalizeTranscript(text: string): string {
  return text
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .join('\n');
}

function splitTranscriptSegments(text: string): string[] {
  const normalized = normalizeTranscript(text);
  if (!normalized) return [];
  // Split on Latin and Chinese sentence boundaries so 决定/行动项 can multi-match.
  return normalized
    .split(/\n+/)
    .flatMap((line) => line.split(/(?<=[.!?;。！？])\s*/))
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function previewText(text: string): string {
  const normalized = normalizeTranscript(text);
  return normalized.length > 220 ? `${normalized.slice(0, 217)}...` : normalized;
}

const DECISION_PATTERNS = [
  /\bdecid(?:e|ed|es|ing)\b/i,
  /\bdecision\b/i,
  /\bagreed?\b/i,
  /\bapproved?\b/i,
  /\bconclusion\b/i,
  /\u51b3\u5b9a/,
  /\u7ed3\u8bba/,
  /\u540c\u610f/,
];

const ACTION_PATTERNS = [
  /\baction\b/i,
  /\btodo\b/i,
  /\bfollow up\b/i,
  /\bowner\b/i,
  /\bdue\b/i,
  /\bassign(?:ed)?\b/i,
  /\bneed(?:s|ed)? to\b/i,
  /\u8d1f\u8d23/,
  /\u8ddf\u8fdb/,
  /\u5f85\u529e/,
  /\u9700\u8981/,
  /\u5b89\u6392/,
];

const NON_NEED_ACTION_PATTERNS = [
  /\baction\b/i,
  /\btodo\b/i,
  /\bfollow up\b/i,
  /\bowner\b/i,
  /\bdue\b/i,
  /\bassign(?:ed)?\b/i,
  /\u8d1f\u8d23/,
  /\u8ddf\u8fdb/,
  /\u5f85\u529e/,
  /\u5b89\u6392/,
];

const NEGATED_NEED_PATTERNS = [
  /\b(?:do(?:es)?\s+not|don't|doesn't)\s+need(?:s|ed)?\s+to\b/i,
  /\u4e0d\u9700\u8981|\u65e0\u9700|\u65e0\u987b|\u4e0d\u7528/,
];

function extractMatchingSegments(segments: string[], patterns: RegExp[]): string[] {
  return segments.filter((segment) => patterns.some((pattern) => pattern.test(segment)));
}

function extractActionItems(segments: string[]): CompanionV1ActionItem[] {
  return extractMatchingSegments(segments, ACTION_PATTERNS)
    .filter((segment) => (
      !NEGATED_NEED_PATTERNS.some((pattern) => pattern.test(segment))
      || NON_NEED_ACTION_PATTERNS.some((pattern) => pattern.test(segment))
    ))
    .map((segment) => ({
    text: segment,
    owner: extractOwner(segment),
    due: extractDue(segment),
    }));
}

function extractOwner(segment: string): string | null {
  const ownerMatch = segment.match(/\bowner\s*[:=-]\s*([A-Za-z0-9 _.-]{2,32})/i)
    ?? segment.match(/\b([A-Z][A-Za-z0-9 _.-]{1,24})\s+(?:will|to)\s+/);
  return ownerMatch?.[1]?.trim() ?? null;
}

function extractDue(segment: string): string | null {
  const dueMatch = segment.match(/\bdue\s*[:=-]\s*([A-Za-z0-9 ,./-]{2,32})/i)
    ?? segment.match(/\b(?:by|before)\s+([A-Za-z0-9 ,./-]{2,32})/i);
  return dueMatch?.[1]?.trim() ?? null;
}

function extractKeywords(text: string): string[] {
  const stopWords = new Set([
    'about',
    'after',
    'again',
    'also',
    'and',
    'are',
    'but',
    'for',
    'from',
    'have',
    'into',
    'meeting',
    'need',
    'next',
    'that',
    'the',
    'this',
    'will',
    'with',
  ]);
  const counts = new Map<string, number>();
  for (const token of text.toLowerCase().match(/[a-z0-9][a-z0-9_-]{2,}/g) ?? []) {
    if (stopWords.has(token)) continue;
    counts.set(token, (counts.get(token) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([token]) => token);
}

function renderMinutesMarkdown(
  session: CompanionV1HostSession,
  minutes: Omit<CompanionV1MeetingMinutes, 'markdown'>,
): string {
  const lines = [
    `# ${session.title}`,
    '',
    `Generated: ${minutes.generatedAt}`,
    `Duration: ${formatDuration(session.durationMs)}`,
    `Source: ${session.source}`,
    `Minutes engine: ${minutes.source} (${minutes.quality})`,
    '',
    '## Summary',
    ...minutes.summary.map((item) => `- ${item}`),
    '',
    '## Decisions',
    ...(minutes.decisions.length ? minutes.decisions.map((item) => `- ${item}`) : ['- None captured']),
    '',
    '## Action Items',
    ...(minutes.actionItems.length
      ? minutes.actionItems.map((item) => {
        const meta = [item.owner ? `owner: ${item.owner}` : null, item.due ? `due: ${item.due}` : null]
          .filter(Boolean)
          .join(', ');
        return `- ${item.text}${meta ? ` (${meta})` : ''}`;
      })
      : ['- None captured']),
    '',
    '## Questions',
    ...(minutes.questions.length ? minutes.questions.map((item) => `- ${item}`) : ['- None captured']),
    '',
    '## Keywords',
    minutes.keywords.length ? minutes.keywords.join(', ') : 'None captured',
    '',
  ];
  return `${lines.join('\n')}\n`;
}

function formatDuration(durationMs: number): string {
  const totalSeconds = Math.max(0, Math.round(durationMs / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function countTranscriptSessions(snapshot: CompanionV1Snapshot): number {
  return snapshot.host.sessions.filter((session) => session.transcriptText.trim()).length;
}

function hostOnlyAction(action: CompanionV1ControlAction): boolean {
  return action === 'hostRetrySave'
    || action === 'meetingRestoreAudio'
    || action === 'deviceScan'
    || action === 'deviceConnect'
    || action === 'deviceDisconnect'
    || action === 'deviceEnableAutoReconnect'
    || action === 'deviceDisableAutoReconnect'
    || action === 'deviceSyncRecordings'
    || action === 'stageBleName'
    || action === 'oobeRunChecks'
    || action === 'meetingImportTranscript'
    || action === 'meetingAppendLiveTranscript'
    || action === 'meetingTranscribeAudio'
    || action === 'meetingGenerateMinutes'
    || action === 'meetingExportMarkdown'
    || action === 'meetingExportTxt'
    || action === 'meetingExportJson'
    || action === 'meetingExportSrt'
    || action === 'meetingExportActionsTodo'
    || action === 'meetingExportActionsIcal'
    || action === 'meetingLoadDemo'
    || action === 'meetingSelectSession'
    || action === 'meetingResetSession'
    || action === 'privacyEraseAudio'
    || action === 'privacyEraseTranscript'
    || action === 'privacyEraseAll'
    || action === 'privacyDeleteSession';
}

function bytesToHex(bytes: Uint8Array): string {
  return [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function actionCommand(action: CompanionV1ControlAction): number {
  const table: Record<CompanionV1ControlAction, number> = {
    hostRetrySave: 0x8e,
    meetingRestoreAudio: 0x8f,
    deviceScan: 0x10,
    deviceConnect: 0x11,
    deviceDisconnect: 0x12,
    deviceEnableAutoReconnect: 0x14,
    deviceDisableAutoReconnect: 0x15,
    deviceSyncRecordings: 0x13,
    stageBleName: 1,
    applyBleName: 2,
    resetBleName: 3,
    oobeRunChecks: 0x20,
    meetingStart: 1,
    meetingStop: 2,
    meetingFinalize: 3,
    meetingPause: 4,
    meetingResume: 5,
    meetingRecoverControl: 0,
    meetingImportTranscript: 0x81,
    meetingGenerateMinutes: 0x82,
    meetingExportMarkdown: 0x83,
    meetingResetSession: 0x84,
    meetingTranscribeAudio: 0x85,
    meetingLoadDemo: 0x86,
    meetingExportTxt: 0x87,
    meetingExportJson: 0x88,
    meetingExportSrt: 0x89,
    meetingExportActionsTodo: 0x8a,
    meetingExportActionsIcal: 0x8b,
    meetingAppendLiveTranscript: 0x8c,
    meetingSelectSession: 0x8d,
    privacyEraseAudio: 0x90,
    privacyEraseTranscript: 0x91,
    privacyEraseAll: 0x92,
    privacyDeleteSession: 0x93,
    speakerPrompt: 1,
    speakerStop: 2,
    wakeArm: 1,
    wakeDisable: 2,
    wakeTestDetect: 3,
  };
  return table[action];
}

function deepMergeCompanionSnapshot(
  base: CompanionV1Snapshot,
  overrides: Partial<CompanionV1Snapshot>,
): CompanionV1Snapshot {
  const host = overrides.host
    ? {
      ...base.host,
      ...overrides.host,
      recordingPolicy: { ...base.host.recordingPolicy, ...overrides.host.recordingPolicy },
      sessions: overrides.host.sessions?.map((session) => ({
        ...createHostSession(
          base,
          { action: 'meetingStart', sessionId: session.id, title: session.title, audioPath: session.audioPath ?? undefined },
          new Date().toISOString(),
        ),
        ...session,
        meetingMode: normalizeMeetingMode(session.meetingMode, base.host.recordingPolicy.defaultMeetingMode),
        minutesByMode: session.minutesByMode ?? { offlineStore: null, onlineLive: null },
        audioStored: session.audioStored ?? Boolean(session.audioPath || session.audioBytes),
        liveTranscriptText: session.liveTranscriptText ?? '',
        audioBytes: session.audioBytes ?? 0,
        chunks: session.chunks ?? [],
        retention: {
          ...createSessionRetention(Boolean(session.audioPath), Boolean(session.transcriptText), Boolean(session.minutes)),
          ...session.retention,
        },
      })) ?? base.host.sessions,
    }
    : base.host;

  return {
    ...base,
    ...overrides,
    meeting: { ...base.meeting, ...overrides.meeting },
    imu: {
      ...base.imu,
      ...overrides.imu,
      reserved: overrides.imu?.reserved ?? base.imu.reserved ?? true,
      accel: { ...base.imu.accel, ...overrides.imu?.accel },
      gyro: { ...base.imu.gyro, ...overrides.imu?.gyro },
    },
    speaker: {
      ...base.speaker,
      ...overrides.speaker,
      reserved: overrides.speaker?.reserved ?? base.speaker.reserved ?? true,
    },
    wakeWord: { ...base.wakeWord, ...overrides.wakeWord },
    bleName: { ...base.bleName, ...overrides.bleName },
    device: { ...base.device, ...overrides.device },
    oobe: {
      ...base.oobe,
      ...overrides.oobe,
      checks: overrides.oobe?.checks ?? base.oobe.checks,
    },
    privacy: { ...base.privacy, ...overrides.privacy },
    host,
  };
}
