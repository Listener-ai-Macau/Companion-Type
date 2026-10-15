import assert from 'node:assert/strict';
import {
  COMPANION_CAPTURE_ONLY_PROMPT, applyCompanionV1ControlFixture,
  createCompanionV1Fixture, describeCompanionMeetingRecovery,
} from './companionV1.ts';

const started = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {
  action: 'meetingStart', sessionId: 'manual-policy', meetingMode: 'offlineStore',
  promptId: COMPANION_CAPTURE_ONLY_PROMPT,
});
assert.equal(started.host.sessions[0].processingPolicy, 'manual');
const erased = applyCompanionV1ControlFixture(started, {
  action: 'privacyEraseTranscript', sessionId: 'manual-policy',
});
const row = JSON.parse(JSON.stringify(erased.host.sessions[0]));
assert.equal(row.processingPolicy, 'manual');
row.status = 'captured';
row.recovery = {intent: 'none', requestedMeetingMode: 'offlineStore', stage: 'paused',
  attemptCount: 1, maxAttempts: 3, retryStage: 'transcription', lastError: '本次转写未完成'};
const failure = describeCompanionMeetingRecovery(row);
assert.equal(failure?.retryAction, 'meetingTranscribeAudio');
assert.equal(failure?.isProcessing, false);
assert.match(failure?.message ?? '', /手动重试/);
assert.doesNotMatch(failure?.message ?? '', /自动重试/);

const meeting = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {
  action: 'meetingStart', sessionId: 'ordinary-meeting', meetingMode: 'onlineLive',
});
assert.equal(meeting.host.sessions[0].processingPolicy, 'automatic');
console.log('recording processing policy: manual persistence and explicit retry; ordinary meetings unchanged');
