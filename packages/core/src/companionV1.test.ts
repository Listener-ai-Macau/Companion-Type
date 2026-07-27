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

const named = applyCompanionV1ControlFixture(initial, {
  action: 'stageBleName',
  bleName: 'companion-v1',
});
assert.equal(named.bleName.stagedName, 'companion-v1');
assert.equal(named.bleName.pendingRestart, true);
assert.equal(named.lastControl?.characteristicUuid, COMPANION_V1_GATT_BOUNDARY.bleNameConfigUuid);
assert.equal(named.lastControl?.payloadHex.startsWith('011d'), true);

const finalized = applyCompanionV1ControlFixture(initial, { action: 'meetingFinalize' });
assert.equal(finalized.meeting.status, 'finalized');
assert.equal(finalized.meeting.transcriptCount, 0);
assert.equal(finalized.lastControl?.characteristicUuid, COMPANION_V1_GATT_BOUNDARY.meetingControlUuid);

const wakeDetected = applyCompanionV1ControlFixture(initial, { action: 'wakeTestDetect' });
assert.equal(wakeDetected.wakeWord.armed, true);
assert.equal(wakeDetected.wakeWord.confidence, 0.92);
assert.equal(wakeDetected.lastControl?.characteristicUuid, COMPANION_V1_GATT_BOUNDARY.wakeWordControlUuid);

const setupReady = applyCompanionV1ControlFixture(initial, { action: 'oobeRunChecks' });
assert.equal(setupReady.oobe.complete, true);
assert.equal(setupReady.oobe.checks.every((check) => check.status === 'pass'), true);

const deviceConnected = applyCompanionV1ControlFixture(
  applyCompanionV1ControlFixture(initial, { action: 'deviceScan' }),
  { action: 'deviceConnect', deviceId: 'companion-test' },
);
assert.equal(deviceConnected.device.connected, true);
assert.equal(deviceConnected.device.deviceId, 'companion-test');

const synced = applyCompanionV1ControlFixture(deviceConnected, {
  action: 'deviceSyncRecordings',
  audioPath: 'device://companion/flash/latest.wav',
  audioBytes: 1920000,
  durationMs: 60000,
});
assert.equal(selectedCompanionHostSession(synced)?.source, 'deviceFlash');
assert.equal(selectedCompanionHostSession(synced)?.status, 'captured');
assert.equal(selectedCompanionHostSession(synced)?.pendingReason, 'needs_transcription');
assert.equal(selectedCompanionHostSession(synced)?.chunks[0]?.status, 'synced');
assert.match(synced.host.recordingPolicy.shortCaptureGuide, /Sync/);
assert.match(synced.host.recordingPolicy.longMeetingGuide, /host microphone/i);

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

const stopped = applyCompanionV1ControlFixture(started, {
  action: 'meetingStop',
  durationMs: COMPANION_V1_LONG_MEETING_TARGET_SECONDS * 1000,
});
assert.equal(stopped.meeting.status, 'captured');
assert.equal(selectedCompanionHostSession(stopped)?.pendingReason, 'needs_transcription');
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
assert.ok(minutesSession?.minutes?.summary[0].includes('weekly product meeting'));
assert.equal(minutesSession?.minutes?.decisions.length, 1);
assert.equal(minutesSession?.minutes?.actionItems.length, 2);
assert.equal(minutesSession?.minutes?.questions.length, 1);

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
