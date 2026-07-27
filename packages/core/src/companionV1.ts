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
  | 'deviceScan'
  | 'deviceConnect'
  | 'deviceDisconnect'
  | 'deviceSyncRecordings'
  | 'stageBleName'
  | 'applyBleName'
  | 'resetBleName'
  | 'oobeRunChecks'
  | 'meetingStart'
  | 'meetingStop'
  | 'meetingFinalize'
  | 'meetingImportTranscript'
  | 'meetingTranscribeAudio'
  | 'meetingGenerateMinutes'
  | 'meetingExportMarkdown'
  | 'meetingLoadDemo'
  | 'meetingResetSession'
  | 'privacyEraseAudio'
  | 'privacyEraseTranscript'
  | 'privacyEraseAll'
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
  online: boolean;
  sampleHz: number;
  motion: 'unknown' | 'still' | 'moving' | 'tilted';
  accel: { x: number; y: number; z: number };
  gyro: { x: number; y: number; z: number };
}

export interface CompanionV1SpeakerState {
  supported: boolean;
  online: boolean;
  muted: boolean;
  volume: number;
  status: 'idle' | 'prompting' | 'streaming' | 'error';
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
  lastSyncAt: string | null;
  message: string;
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
  | 'needs_pull';

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
}

export interface CompanionV1ActionItem {
  text: string;
  owner: string | null;
  due: string | null;
}

export interface CompanionV1MeetingMinutes {
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
}

export interface CompanionV1HostSession {
  id: string;
  title: string;
  source: CompanionV1HostSessionSource;
  status: CompanionV1HostSessionStatus;
  /** Blocker after capture (needs ASR, network, or device pull). */
  pendingReason: CompanionV1SessionPendingReason;
  startedAt: string | null;
  stoppedAt: string | null;
  durationMs: number;
  audioPath: string | null;
  audioBytes: number;
  chunks: CompanionV1AudioChunk[];
  transcriptText: string;
  transcriptPreview: string;
  transcriptSegments: number;
  minutes: CompanionV1MeetingMinutes | null;
  exportMarkdown: string;
  exportedAt: string | null;
  retention: CompanionV1SessionRetention;
}

export interface CompanionV1HostState {
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
      supported: true,
      online: false,
      sampleHz: 0,
      motion: 'unknown',
      accel: { x: 0, y: 0, z: 1 },
      gyro: { x: 0, y: 0, z: 0 },
    },
    speaker: {
      supported: true,
      online: false,
      muted: false,
      volume: 65,
      status: 'idle',
    },
    wakeWord: {
      supported: true,
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
    lastSyncAt: null,
    message: 'Not scanned',
  };
}

export function createDefaultOobeState(): CompanionV1OobeState {
  return {
    complete: false,
    lastRunAt: null,
    checks: [
      { id: 'firmware', label: 'Firmware', status: 'pending', message: 'Waiting' },
      { id: 'bluetooth', label: 'Bluetooth', status: 'pending', message: 'Waiting' },
      { id: 'microphone', label: 'Microphone', status: 'pending', message: 'Waiting' },
      { id: 'asr', label: 'ASR', status: 'pending', message: 'Waiting' },
      { id: 'privacy', label: 'Privacy', status: 'pending', message: 'Waiting' },
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

  switch (request.action) {
    case 'deviceScan':
      next.device = {
        ...next.device,
        scanning: false,
        connected: false,
        deviceId: request.deviceId ?? next.device.deviceId ?? 'companion-nucleo-wb55rg',
        lastSeenAt: now,
        signalRssi: -48,
        recordingsAvailable: Math.max(next.device.recordingsAvailable, 1),
        message: 'Companion device discovered',
      };
      next.connected = false;
      break;
    case 'deviceConnect':
      next.device = {
        ...next.device,
        connected: true,
        deviceId: request.deviceId ?? next.device.deviceId ?? 'companion-nucleo-wb55rg',
        lastSeenAt: now,
        signalRssi: next.device.signalRssi ?? -48,
        message: 'Companion device connected',
      };
      next.connected = true;
      break;
    case 'deviceDisconnect':
      next.device = {
        ...next.device,
        connected: false,
        message: 'Companion device disconnected',
      };
      next.connected = false;
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
    case 'applyBleName':
      next.bleName = {
        ...next.bleName,
        activeName: next.bleName.stagedName,
        status: 'pendingRestart',
        pendingRestart: true,
      };
      break;
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
          { id: 'firmware', label: 'Firmware', status: 'pass', message: 'STM32CubeProgrammer or firmware helper ready' },
          { id: 'bluetooth', label: 'Bluetooth', status: next.device.supported ? 'pass' : 'warn', message: next.device.providerId },
          { id: 'microphone', label: 'Microphone', status: 'pass', message: 'Host WAV recorder ready' },
          {
            id: 'asr',
            label: 'ASR',
            status: 'pass',
            message: `${next.host.recordingPolicy.asrProviderMode} (configure cloud/local before auto-transcribe)`,
          },
          { id: 'privacy', label: 'Privacy', status: 'pass', message: next.privacy.policyLabel },
        ],
      };
      break;
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
      updateHostSession(next, session.id, {
        status: 'captured',
        pendingReason: session.transcriptText.trim() ? null : 'needs_transcription',
        stoppedAt: now,
        durationMs,
        chunks: sealSessionChunks(session, now, durationMs, request.audioBytes),
        audioBytes: request.audioBytes ?? estimatePcmBytes(durationMs),
      });
      next.host.activeSessionId = null;
      next.meeting = {
        ...next.meeting,
        active: false,
        status: 'captured',
        durationMs,
      };
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
    case 'meetingExportMarkdown': {
      const session = requireSelectedSession(next, now, request);
      const minutes = session.minutes ?? buildCompanionMeetingMinutes(session, now);
      updateHostSession(next, session.id, {
        status: 'minutesReady',
        minutes,
        exportMarkdown: minutes.markdown,
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
      session.status = 'minutesReady';
      session.pendingReason = null;
      session.startedAt = now;
      session.stoppedAt = now;
      session.durationMs = durationMs;
      session.transcriptText = demoText;
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
    case 'meetingResetSession':
      next.host = createDefaultHostState();
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
        transcriptPreview: '',
        transcriptSegments: 0,
        minutes: null,
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

export function buildCompanionMeetingMinutes(
  session: CompanionV1HostSession,
  generatedAt = new Date().toISOString(),
): CompanionV1MeetingMinutes {
  const segments = splitTranscriptSegments(session.transcriptText);
  const summary = segments.slice(0, 4);
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
  if (action === 'deviceScan' || action === 'deviceConnect' || action === 'deviceDisconnect' || action === 'deviceSyncRecordings') {
    return COMPANION_V1_HOST_DEVICE_CHANNEL;
  }
  if (action === 'stageBleName' || action === 'applyBleName' || action === 'resetBleName') {
    return COMPANION_V1_GATT_BOUNDARY.bleNameConfigUuid;
  }
  if (action === 'oobeRunChecks') {
    return COMPANION_V1_HOST_SETUP_CHANNEL;
  }
  if (action === 'meetingStart' || action === 'meetingStop' || action === 'meetingFinalize') {
    return COMPANION_V1_GATT_BOUNDARY.meetingControlUuid;
  }
  if (
    action === 'meetingImportTranscript'
    || action === 'meetingTranscribeAudio'
    || action === 'meetingGenerateMinutes'
    || action === 'meetingExportMarkdown'
    || action === 'meetingLoadDemo'
    || action === 'meetingResetSession'
  ) {
    return action === 'meetingGenerateMinutes'
      || action === 'meetingExportMarkdown'
      || action === 'meetingLoadDemo'
      ? COMPANION_V1_HOST_MINUTES_CHANNEL
      : COMPANION_V1_HOST_RECORDING_CHANNEL;
  }
  if (action === 'speakerPrompt' || action === 'speakerStop') {
    return COMPANION_V1_GATT_BOUNDARY.speakerControlUuid;
  }
  if (action === 'privacyEraseAudio' || action === 'privacyEraseTranscript' || action === 'privacyEraseAll') {
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
  return {
    id,
    title: (request.title ?? 'Companion meeting').trim() || 'Companion meeting',
    source: suppliedAudioPath ? 'deviceFlash' : 'hostMicrophone',
    status: 'recording',
    pendingReason: null,
    startedAt: now,
    stoppedAt: null,
    durationMs,
    audioPath,
    audioBytes,
    chunks: [createAudioChunk(`${id}-chunk-1`, audioPath, now, null, durationMs, audioBytes, 'open')],
    transcriptText: '',
    transcriptPreview: '',
    transcriptSegments: 0,
    minutes: null,
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
  session.status = 'captured';
  session.pendingReason = 'needs_transcription';
  session.startedAt = null;
  session.stoppedAt = now;
  session.durationMs = durationMs;
  session.audioBytes = audioBytes;
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
    retentionLabel: '7 days local',
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
  return normalized
    .split(/\n+/)
    .flatMap((line) => line.split(/(?<=[.!?;])\s+/))
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

function extractMatchingSegments(segments: string[], patterns: RegExp[]): string[] {
  return segments.filter((segment) => patterns.some((pattern) => pattern.test(segment)));
}

function extractActionItems(segments: string[]): CompanionV1ActionItem[] {
  return extractMatchingSegments(segments, ACTION_PATTERNS).map((segment) => ({
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
  return action === 'deviceScan'
    || action === 'deviceConnect'
    || action === 'deviceDisconnect'
    || action === 'deviceSyncRecordings'
    || action === 'oobeRunChecks'
    || action === 'meetingImportTranscript'
    || action === 'meetingTranscribeAudio'
    || action === 'meetingGenerateMinutes'
    || action === 'meetingExportMarkdown'
    || action === 'meetingLoadDemo'
    || action === 'meetingResetSession'
    || action === 'privacyEraseAudio'
    || action === 'privacyEraseTranscript'
    || action === 'privacyEraseAll';
}

function bytesToHex(bytes: Uint8Array): string {
  return [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function actionCommand(action: CompanionV1ControlAction): number {
  const table: Record<CompanionV1ControlAction, number> = {
    deviceScan: 0x10,
    deviceConnect: 0x11,
    deviceDisconnect: 0x12,
    deviceSyncRecordings: 0x13,
    stageBleName: 1,
    applyBleName: 2,
    resetBleName: 3,
    oobeRunChecks: 0x20,
    meetingStart: 1,
    meetingStop: 2,
    meetingFinalize: 3,
    meetingImportTranscript: 0x81,
    meetingGenerateMinutes: 0x82,
    meetingExportMarkdown: 0x83,
    meetingResetSession: 0x84,
    meetingTranscribeAudio: 0x85,
    meetingLoadDemo: 0x86,
    privacyEraseAudio: 0x90,
    privacyEraseTranscript: 0x91,
    privacyEraseAll: 0x92,
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
      accel: { ...base.imu.accel, ...overrides.imu?.accel },
      gyro: { ...base.imu.gyro, ...overrides.imu?.gyro },
    },
    speaker: { ...base.speaker, ...overrides.speaker },
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
