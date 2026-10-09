import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';

import {
  COMPANION_V1_DEVICE_FLASH_RECORDING_MAX_SECONDS,
  COMPANION_V1_GATT_BOUNDARY,
  COMPANION_V1_HOST_MINUTES_CHANNEL,
  COMPANION_V1_HOST_RECORDING_CHANNEL,
  COMPANION_V1_LONG_MEETING_TARGET_SECONDS,
  COMPANION_V1_ONE_HOUR_CHUNKS,
  COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
  COMPANION_V1_ASR_UPLOAD_MAX_BYTES,
  applyCompanionV1ControlFixture,
  characteristicForCompanionAction,
  companionActionPayloadHex,
  companionBleNameIsValid,
  companionSessionHasFinalTranscript,
  describeCompanionMeetingRecovery,
  createCompanionV1Fixture,
  selectedCompanionHostSession,
} from './companionV1.ts';

assert.equal(companionBleNameIsValid('companion-v1'), true);
assert.equal(companionBleNameIsValid('companion lab'), true);
assert.equal(companionBleNameIsValid(''), false);
assert.equal(companionBleNameIsValid('companion=lab'), false);
assert.equal(companionBleNameIsValid('companion-123456789012345678901'), false);

const initial = createCompanionV1Fixture();
assert.equal(initial.schema, 'companion.host.v1');
assert.equal(initial.connected, false);
assert.equal(initial.gatt.meetingControlUuid, COMPANION_V1_GATT_BOUNDARY.meetingControlUuid);
assert.equal(initial.host.recordingPolicy.deviceFlashRawCacheSeconds, COMPANION_V1_DEVICE_FLASH_RECORDING_MAX_SECONDS);
assert.equal(initial.host.recordingPolicy.targetMeetingSeconds, COMPANION_V1_LONG_MEETING_TARGET_SECONDS);
assert.equal(initial.host.recordingPolicy.oneHourRawPcmBytes, COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES);
assert.equal(initial.host.recordingPolicy.oneHourChunkCount, COMPANION_V1_ONE_HOUR_CHUNKS);
assert.equal(initial.host.recordingPolicy.maxAsrUploadBytes, COMPANION_V1_ASR_UPLOAD_MAX_BYTES);
assert.equal(initial.oobe.complete, false);
assert.equal(initial.privacy.localOnly, true);
assert.equal(initial.imu.supported, false);
assert.equal(initial.speaker.supported, false);
assert.equal(initial.wakeWord.supported, false);
assert.throws(
  () => applyCompanionV1ControlFixture(initial, { action: 'speakerPrompt' }),
  /not populated/,
);
assert.throws(
  () => applyCompanionV1ControlFixture(initial, { action: 'wakeArm' }),
  /not populated/,
);

const named = applyCompanionV1ControlFixture(initial, {
  action: 'stageBleName',
  bleName: 'companion-v1',
});
assert.equal(named.bleName.stagedName, 'companion-v1');
assert.equal(named.bleName.pendingRestart, true);
assert.equal(named.lastControl?.characteristicUuid, 'host://companion-type/device');
const directlyNamed = applyCompanionV1ControlFixture(named, { action: 'applyBleName', bleName: 'Companion Two' });
assert.equal(directlyNamed.bleName.activeName, 'Companion Two');
assert.equal(directlyNamed.lastControl?.characteristicUuid, COMPANION_V1_GATT_BOUNDARY.bleNameConfigUuid);

const finalized = applyCompanionV1ControlFixture(initial, { action: 'meetingFinalize' });
assert.equal(finalized.meeting.status, 'finalized');
assert.equal(finalized.meeting.transcriptCount, 0);
assert.equal(finalized.lastControl?.characteristicUuid, COMPANION_V1_GATT_BOUNDARY.meetingControlUuid);

const wakeDetected = applyCompanionV1ControlFixture(
  createCompanionV1Fixture({ wakeWord: { ...initial.wakeWord, supported: true } }),
  { action: 'wakeTestDetect' },
);
assert.equal(wakeDetected.wakeWord.armed, true);
assert.equal(wakeDetected.wakeWord.confidence, 0.92);
assert.equal(wakeDetected.lastControl?.characteristicUuid, COMPANION_V1_GATT_BOUNDARY.wakeWordControlUuid);

const setupReady = applyCompanionV1ControlFixture(initial, { action: 'oobeRunChecks' });
assert.equal(setupReady.oobe.complete, true);
assert.equal(setupReady.oobe.checks.every((check) => check.status === 'warn'), true);
assert.match(
  setupReady.oobe.checks.find((check) => check.id === 'boardMicrophone')?.message ?? '',
  /主机麦克风不能作为板端通过证据/,
);
assert.match(
  setupReady.oobe.checks.find((check) => check.id === 'remoteServices')?.message ?? '',
  /不会调用外部服务/,
);
for (const id of ['display', 'touch', 'power']) {
  const check = setupReady.oobe.checks.find((item) => item.id === id);
  assert.equal(check?.status, 'warn');
  assert.match(check?.message ?? '', /未检查/);
}
const recordingDuringOobe = applyCompanionV1ControlFixture(initial, {
  action: 'meetingStart',
  sessionId: 'oobe-busy-recording',
  title: 'busy',
});
assert.throws(
  () => applyCompanionV1ControlFixture(recordingDuringOobe, { action: 'oobeRunChecks' }),
  /正在录音或在线转写/,
);

const deviceConnected = applyCompanionV1ControlFixture(
  applyCompanionV1ControlFixture(initial, { action: 'deviceScan' }),
  { action: 'deviceConnect', deviceId: 'companion-test' },
);
assert.equal(deviceConnected.device.connected, true);
assert.equal(deviceConnected.device.deviceId, 'companion-test');

const measuredWba = createCompanionV1Fixture({
  connected: true,
  device: {
    ...deviceConnected.device,
    firmwareVersion: 0x00010101,
    buildId: 0x20261003,
    boardId: 0x57424155,
    hardwareRevision: 'COMPANION-WBA55-V1.1',
  },
  speaker: {
    ...initial.speaker,
    supported: true,
    reserved: false,
    online: true,
    muted: false,
    volume: 65,
  },
});
const promptedWba = applyCompanionV1ControlFixture(measuredWba, {
  action: 'speakerPrompt',
  promptId: 'confirm',
});
assert.equal(promptedWba.speaker.status, 'prompting');
assert.equal(promptedWba.device.firmwareVersion, 0x00010101);
assert.equal(promptedWba.device.hardwareRevision, 'COMPANION-WBA55-V1.1');
assert.equal(
  promptedWba.gatt.deviceStatusUuid,
  '8f7a1001-7b7d-4f3d-9d6f-6c2d1b7c0000',
);

const synced = applyCompanionV1ControlFixture(deviceConnected, {
  action: 'deviceSyncRecordings',
  audioPath: 'device://companion/flash/latest.wav',
  audioBytes: 1920000,
  durationMs: 60000,
});
assert.equal(selectedCompanionHostSession(synced)?.source, 'deviceFlash');
assert.equal(selectedCompanionHostSession(synced)?.status, 'captured');
assert.equal(selectedCompanionHostSession(synced)?.meetingMode, 'offlineStore');
assert.equal(selectedCompanionHostSession(synced)?.audioStored, true);
assert.equal(selectedCompanionHostSession(synced)?.pendingReason, 'needs_transcription');
assert.equal(selectedCompanionHostSession(synced)?.chunks[0]?.status, 'synced');
assert.match(synced.host.recordingPolicy.shortCaptureGuide, /Sync/);
assert.match(synced.host.recordingPolicy.longMeetingGuide, /host microphone/i);
assert.equal(initial.host.recordingPolicy.defaultMeetingMode, 'offlineStore');
assert.deepEqual(initial.host.recordingPolicy.supportedMeetingModes, ['offlineStore', 'onlineLive']);

const threeDeviceSessions = [31, 32, 33].reduce((state, id) => applyCompanionV1ControlFixture(state, {
  action: 'deviceSyncRecordings',
  sessionId: `device-recording-${id}`,
  title: `设备录音 #${id}`,
  audioPath: `device://companion/flash/${id}.wav`,
  audioBytes: 90000 + id,
  durationMs: 45000 + id,
}), deviceConnected);
assert.deepEqual(
  threeDeviceSessions.host.sessions.map((session) => session.id),
  ['device-recording-33', 'device-recording-32', 'device-recording-31'],
);
const selectedMiddle = applyCompanionV1ControlFixture(threeDeviceSessions, {
  action: 'meetingSelectSession',
  sessionId: 'device-recording-32',
});
assert.equal(selectedMiddle.host.selectedSessionId, 'device-recording-32');
const deletedMiddle = applyCompanionV1ControlFixture(selectedMiddle, {
  action: 'privacyDeleteSession',
  sessionId: 'device-recording-32',
});
assert.deepEqual(
  deletedMiddle.host.sessions.map((session) => session.id),
  ['device-recording-33', 'device-recording-31'],
);

assert.equal(characteristicForCompanionAction('speakerPrompt'), COMPANION_V1_GATT_BOUNDARY.speakerControlUuid);
assert.equal(characteristicForCompanionAction('meetingImportTranscript'), COMPANION_V1_HOST_RECORDING_CHANNEL);
assert.equal(characteristicForCompanionAction('meetingTranscribeAudio'), COMPANION_V1_HOST_RECORDING_CHANNEL);
assert.equal(characteristicForCompanionAction('meetingGenerateMinutes'), COMPANION_V1_HOST_MINUTES_CHANNEL);
assert.equal(companionActionPayloadHex({ action: 'speakerPrompt' }), '01');
assert.throws(() => applyCompanionV1ControlFixture(initial, { action: 'stageBleName', bleName: 'bad=name' }));

const fixtureTranscript = [
  'Alex opened the weekly product meeting and reviewed Companion recording status.',
  'Decision: Companion keeps the STM32 flash as a short cache while the host app owns one hour meeting recordings.',
  'Action: Maya will wire the BLE recording trigger into the Windows app before Friday.',
  'Action owner: Chen due: July 5 should validate imported transcripts and exported Markdown.',
  'Question: do we need local wake word before the first hardware beta?',
].join('\n');

const started = applyCompanionV1ControlFixture(initial, {
  action: 'meetingStart',
  title: 'Companion host workflow',
});
assert.equal(started.meeting.status, 'recording');
assert.equal(started.host.sessions.length, 1);
assert.equal(selectedCompanionHostSession(started)?.meetingMode, 'offlineStore');

const stopped = applyCompanionV1ControlFixture(started, {
  action: 'meetingStop',
  durationMs: COMPANION_V1_LONG_MEETING_TARGET_SECONDS * 1000,
});
assert.equal(stopped.meeting.status, 'captured');
assert.equal(selectedCompanionHostSession(stopped)?.pendingReason, 'needs_transcription');
assert.equal(selectedCompanionHostSession(stopped)?.audioStored, true);

// Online live route: partials during capture → stop transcribed-ready.
let live = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {
  action: 'meetingStart',
  title: 'Live meeting',
  meetingMode: 'onlineLive',
});
live = applyCompanionV1ControlFixture(live, {
  action: 'meetingAppendLiveTranscript',
  transcriptText: 'Decision: onlineLive streams partials.',
});
live = applyCompanionV1ControlFixture(live, {
  action: 'meetingStop',
  durationMs: 5000,
});
assert.equal(selectedCompanionHostSession(live)?.status, 'transcribed');
assert.equal(selectedCompanionHostSession(live)?.pendingReason, null);
assert.match(selectedCompanionHostSession(live)?.transcriptText ?? '', /onlineLive/);
assert.equal(selectedCompanionHostSession(stopped)?.durationMs, 3600000);
assert.equal(selectedCompanionHostSession(stopped)?.chunks.length, COMPANION_V1_ONE_HOUR_CHUNKS);
assert.equal(
  selectedCompanionHostSession(stopped)?.chunks.reduce((sum, chunk) => sum + chunk.bytes, 0),
  COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
);
assert.ok(selectedCompanionHostSession(stopped)?.chunks.every((chunk) => chunk.durationMs <= 300000));
assert.ok(selectedCompanionHostSession(stopped)?.chunks.every((chunk) => chunk.bytes < COMPANION_V1_ASR_UPLOAD_MAX_BYTES));

const pendingTranscribe = applyCompanionV1ControlFixture(stopped, {
  action: 'meetingTranscribeAudio',
});
assert.equal(selectedCompanionHostSession(pendingTranscribe)?.pendingReason, 'needs_transcription');
assert.equal(pendingTranscribe.meeting.status, 'captured');

const transcribed = applyCompanionV1ControlFixture(stopped, {
  action: 'meetingTranscribeAudio',
  transcriptText: fixtureTranscript,
});
assert.equal(transcribed.meeting.status, 'transcribed');
assert.equal(transcribed.meeting.transcriptCount, 1);
assert.equal(selectedCompanionHostSession(transcribed)?.transcriptSegments, 5);
assert.equal(selectedCompanionHostSession(transcribed)?.pendingReason, null);
assert.equal(transcribed.lastControl?.action, 'meetingTranscribeAudio');

const minutesReady = applyCompanionV1ControlFixture(transcribed, { action: 'meetingGenerateMinutes' });
const minutesSession = selectedCompanionHostSession(minutesReady);
assert.equal(minutesReady.meeting.status, 'minutesReady');
assert.equal(minutesSession?.pendingReason, null);
assert.equal(minutesSession?.minutes?.source, 'rules_l0');
assert.equal(minutesSession?.minutes?.quality, 'draft');
assert.equal(minutesSession?.minutesByMode?.offlineStore?.status, 'minutesReady');
assert.equal(minutesSession?.minutesByMode?.onlineLive, null);
assert.ok(minutesSession?.minutes?.summary[0].includes('weekly product meeting'));
assert.equal(minutesSession?.minutes?.decisions.length, 1);
assert.equal(minutesSession?.minutes?.actionItems.length, 2);
assert.equal(minutesSession?.minutes?.questions.length, 1);

// Offline-store minutes must not collapse to only the greeting when a real
// transcript starts with several short introductory sentences. Preserve
// salient recording/transport facts from later segments as deterministic L0
// coverage; onlineLive already tends to arrive in larger transcript chunks.
let offlineSalience = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {
  action: 'meetingStart',
  title: '离线关键事实回归',
  meetingMode: 'offlineStore',
});
offlineSalience = applyCompanionV1ControlFixture(offlineSalience, {
  action: 'meetingStop',
  durationMs: 107000,
});
offlineSalience = applyCompanionV1ControlFixture(offlineSalience, {
  action: 'meetingTranscribeAudio',
  transcriptText: [
    '主题录音同步压缩与会议总结可行性。',
    '第一轮。',
    '大家好，现在开始产品周会。',
    '我是主持人小陈。',
    '上周我们把录音改成了先压缩再传输。',
    '空中wire和压缩比必须分开报，等效PCM可以过五百。',
    '八千赫兹加IMA后压缩比约七点八倍。',
    '解压后再上采样回一万六。',
    '会议纪要不需要CD音质，但要保留关键词和决策。',
  ].join(' '),
});
offlineSalience = applyCompanionV1ControlFixture(offlineSalience, { action: 'meetingGenerateMinutes' });
const offlineSalienceSummary = selectedCompanionHostSession(offlineSalience)?.minutes?.summary.join('\n') ?? '';
assert.match(offlineSalienceSummary, /先压缩再传输/);
assert.match(offlineSalienceSummary, /空中wire.*等效PCM/);
assert.match(offlineSalienceSummary, /八千赫兹.*七点八倍/);
assert.match(offlineSalienceSummary, /上采样回一万六/);
assert.equal(selectedCompanionHostSession(offlineSalience)?.minutes?.actionItems.length, 0);

const deviceMinutes = applyCompanionV1ControlFixture(
  applyCompanionV1ControlFixture(synced, {
    action: 'meetingImportTranscript',
    transcriptText: fixtureTranscript,
  }),
  { action: 'meetingGenerateMinutes' },
);
assert.equal(selectedCompanionHostSession(deviceMinutes)?.source, 'deviceFlash');
assert.equal(selectedCompanionHostSession(deviceMinutes)?.status, 'minutesReady');

const demo = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {
  action: 'meetingLoadDemo',
  title: '一键演示纪要',
});
assert.equal(demo.meeting.status, 'minutesReady');
assert.equal(selectedCompanionHostSession(demo)?.status, 'minutesReady');
assert.equal(selectedCompanionHostSession(demo)?.minutes?.source, 'rules_l0');
assert.ok(selectedCompanionHostSession(demo)?.exportMarkdown.includes('## Action Items'));

const exported = applyCompanionV1ControlFixture(minutesReady, { action: 'meetingExportMarkdown' });
const exportedSession = selectedCompanionHostSession(exported);
assert.ok(exportedSession?.exportMarkdown.includes('# Companion host workflow'));
assert.ok(exportedSession?.exportMarkdown.includes('## Action Items'));
assert.ok(exported.lastControl?.payloadHex.startsWith('6d656574696e674578706f72744d61726b646f776e'));

const audioErased = applyCompanionV1ControlFixture(exported, { action: 'privacyEraseAudio' });
assert.equal(selectedCompanionHostSession(audioErased)?.audioBytes, 0);
assert.equal(selectedCompanionHostSession(audioErased)?.retention.audioCached, false);
const textErased = applyCompanionV1ControlFixture(exported, { action: 'privacyEraseTranscript' });
assert.equal(selectedCompanionHostSession(textErased)?.transcriptText, '');
assert.equal(selectedCompanionHostSession(textErased)?.minutes, null);

// Recovery controls must resume the failed stage without mistaking an online
// prefix or a service-failure draft for completed processing.
const recoverySession = structuredClone(minutesSession!);
recoverySession.transcriptFinal = true;
recoverySession.pendingReason = 'recovery_paused';
recoverySession.recovery = {
  intent: 'processMeeting', requestedMeetingMode: recoverySession.meetingMode,
  stage: 'paused', attemptCount: 3, maxAttempts: 3, retryStage: 'minutes',
  lastError: 'service timeout',
};
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.label, '恢复暂停');
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.retryAction, 'meetingGenerateMinutes');
const cancellationFixture = structuredClone(minutesReady);
cancellationFixture.host.sessions = [structuredClone(recoverySession)];
cancellationFixture.host.selectedSessionId = recoverySession.id;
for (const action of ['privacyEraseAudio', 'privacyEraseTranscript'] as const) {
  const erasedRecovery = applyCompanionV1ControlFixture(cancellationFixture, { action, sessionId: recoverySession.id });
  const erasedSession = selectedCompanionHostSession(erasedRecovery)!;
  assert.equal(erasedSession.recovery?.intent ?? 'none', 'none');
  assert.equal(describeCompanionMeetingRecovery(erasedSession), null);
  if (action === 'privacyEraseTranscript') {
    assert.equal(erasedSession.transcriptFinal, false);
    assert.equal(erasedSession.liveTranscriptText, '');
    assert.deepEqual(erasedSession.utterances, []);
  }
}
recoverySession.transcriptFinal = false;
assert.equal(companionSessionHasFinalTranscript(recoverySession), false);
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.retryAction, 'meetingTranscribeAudio');
recoverySession.pendingReason = 'no_speech_detected';
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.label, '未识别到人声');
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.retryAction, 'meetingTranscribeAudio');
assert.match(describeCompanionMeetingRecovery(recoverySession)!.message, /原录音已保留.*不会自动反复上传/);
recoverySession.pendingReason = 'needs_device_sync';
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.retryAction, null);
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.label, '等待设备同步');
recoverySession.pendingReason = 'recovery_processing';
recoverySession.recovery.stage = 'generatingMinutes';
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.isProcessing, true);
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.retryAction, null);
recoverySession.recovery.stage = 'paused';
recoverySession.recovery.requestedMeetingMode = 'a-different-mode';
assert.equal(describeCompanionMeetingRecovery(recoverySession)?.retryAction, null);
delete recoverySession.recovery;
delete recoverySession.transcriptFinal;
assert.equal(companionSessionHasFinalTranscript(recoverySession), true);
assert.equal(describeCompanionMeetingRecovery(recoverySession), null);
recoverySession.status = 'recording';
assert.equal(companionSessionHasFinalTranscript(recoverySession), false);

if (process.argv.includes('--write-docs')) {
  const artifact = {
    schema: 'companion_type.core_fixture.v1',
    generatedAt: new Date().toISOString(),
    gatt: COMPANION_V1_GATT_BOUNDARY,
    snapshots: {
      initial,
      named,
      finalized,
      wakeDetected,
      userChain: {
        started,
        stopped,
        transcribed,
        minutesReady,
        exported,
      },
    },
  };
  mkdirSync('docs/validation', { recursive: true });
  writeFileSync('docs/validation/companion-type-core-fixture.json', `${JSON.stringify(artifact, null, 2)}\n`);
  console.log('companion-type: wrote docs/validation/companion-type-core-fixture.json');
} else {
  console.log('companion-type: core assertions passed');
}
