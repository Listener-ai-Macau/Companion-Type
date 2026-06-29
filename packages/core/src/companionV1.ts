export const COMPANION_V1_SCHEMA = 'companion.host.v1' as const;
export const COMPANION_V1_DEFAULT_BLE_NAME = 'companion';
export const COMPANION_V1_BLE_NAME_MAX_BYTES = 29;

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
  | 'stageBleName'
  | 'applyBleName'
  | 'resetBleName'
  | 'meetingStart'
  | 'meetingStop'
  | 'meetingFinalize'
  | 'speakerPrompt'
  | 'speakerStop'
  | 'wakeArm'
  | 'wakeDisable'
  | 'wakeTestDetect';

export interface CompanionV1MeetingState {
  supported: boolean;
  active: boolean;
  status: 'idle' | 'recording' | 'paused' | 'finalized' | 'error';
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
  lastControl: CompanionV1ControlEcho | null;
}

export interface CompanionV1ControlRequest {
  action: CompanionV1ControlAction;
  bleName?: string;
  sessionId?: string;
  promptId?: string;
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
    lastControl: null,
  };
  return deepMergeCompanionSnapshot(base, overrides);
}

export function applyCompanionV1ControlFixture(
  snapshot: CompanionV1Snapshot,
  request: CompanionV1ControlRequest,
): CompanionV1Snapshot {
  const next = structuredClone(snapshot) as CompanionV1Snapshot;
  const now = new Date().toISOString();
  next.updatedAt = now;

  switch (request.action) {
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
    case 'meetingStart':
      next.meeting = {
        ...next.meeting,
        active: true,
        status: 'recording',
        startedAt: now,
        durationMs: 0,
      };
      break;
    case 'meetingStop':
      next.meeting = {
        ...next.meeting,
        active: false,
        status: 'idle',
        durationMs: next.meeting.durationMs || 1,
      };
      break;
    case 'meetingFinalize':
      next.meeting = {
        ...next.meeting,
        active: false,
        status: 'finalized',
        transcriptCount: Math.max(1, next.meeting.transcriptCount + 1),
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

  next.lastControl = {
    action: request.action,
    characteristicUuid: characteristicForCompanionAction(request.action),
    payloadHex: companionActionPayloadHex(request),
    accepted: true,
    message: 'fixture accepted',
  };
  return next;
}

export function characteristicForCompanionAction(action: CompanionV1ControlAction): string {
  if (action === 'stageBleName' || action === 'applyBleName' || action === 'resetBleName') {
    return COMPANION_V1_GATT_BOUNDARY.bleNameConfigUuid;
  }
  if (action === 'meetingStart' || action === 'meetingStop' || action === 'meetingFinalize') {
    return COMPANION_V1_GATT_BOUNDARY.meetingControlUuid;
  }
  if (action === 'speakerPrompt' || action === 'speakerStop') {
    return COMPANION_V1_GATT_BOUNDARY.speakerControlUuid;
  }
  return COMPANION_V1_GATT_BOUNDARY.wakeWordControlUuid;
}

export function companionActionPayloadHex(request: CompanionV1ControlRequest): string {
  const bytes = [actionCommand(request.action)];
  if (request.action === 'stageBleName' || request.action === 'applyBleName' || request.action === 'resetBleName') {
    bytes.push(COMPANION_V1_BLE_NAME_MAX_BYTES);
    bytes.push(...new TextEncoder().encode(request.bleName ?? '').slice(0, COMPANION_V1_BLE_NAME_MAX_BYTES));
  }
  return bytes.map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function actionCommand(action: CompanionV1ControlAction): number {
  const table: Record<CompanionV1ControlAction, number> = {
    stageBleName: 1,
    applyBleName: 2,
    resetBleName: 3,
    meetingStart: 1,
    meetingStop: 2,
    meetingFinalize: 3,
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
  };
}

