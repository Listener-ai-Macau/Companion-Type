import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { App } from '../apps/windows/src/App';

// Only the IPC boundary is simulated. This checks the actual App/Dashboard
// after STOP rejects; it is not a board, Bluetooth, or visual acceptance.
const timers = new Map<number, () => void>();
let timerId = 0;
(globalThis as any).window = {
  setTimeout: (fn: () => void) => { timers.set(++timerId, fn); return timerId; },
  clearTimeout: (id: number) => timers.delete(id),
};
const text = (node: any): string => typeof node === 'string' ? node : (node.children ?? []).map(text).join('');
const recording = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {
  action: 'meetingStart', meetingMode: 'offlineStore', sessionId: 'original-device-meeting',
});
recording.connected = true;
recording.device.connected = true;
recording.device.autoReconnectEnabled = false;
recording.device.rememberedDeviceId = null;
recording.host.persistence = { status: 'ready' };
const original = recording.host.sessions.find(session => session.id === 'original-device-meeting')!;
original.source = 'boardDevice';
original.sourceDeviceId = 'C8:92:FF:DD:3B:CA';
original.deviceRecordingId = 18;
const stopped = structuredClone(recording);
stopped.host.activeSessionId = null;
stopped.device.recording = false;
stopped.meeting.active = false;
stopped.meeting.status = 'captured';
const confirmed = stopped.host.sessions.find(session => session.id === original.id)!;
confirmed.status = 'captured';
confirmed.pendingReason = 'needs_device_sync';
confirmed.stoppedAt = '2026-10-08T08:45:00.000Z';
confirmed.audioStored = false;
confirmed.recovery = { intent: 'processMeeting', requestedMeetingMode: 'offlineStore',
  stage: 'paused', attemptCount: 0, maxAttempts: 3, nextRetryAtUnixMs: null };

let renderer: any;
const stopButton = () => renderer.root.findAllByType('button').find((node: any) => text(node) === '结束录音');
let reads = 0, controls = 0;
let finishRead: ((snapshot: unknown) => void) | undefined;
const submitted: any[] = [];
(globalThis as any).__companionAppTest = {
  snapshot: () => ++reads === 1 ? Promise.resolve(structuredClone(recording))
    : new Promise(resolve => { finishRead = resolve; }),
  control: async (request: unknown) => {
    controls++;
    submitted.push(request);
    throw new Error('STOP confirmed; recording upload interrupted');
  },
};
await act(async () => { renderer = create(<App />); });
assert.equal(timers.size, 0, 'offline failure must recover without background polling');
const originalStop = stopButton();
assert.ok(originalStop);
await act(async () => { originalStop.props.onClick(); originalStop.props.onClick(); });
assert.equal(controls, 1);
assert.equal(submitted[0].action, 'meetingStop');
assert.equal(submitted[0].sessionId, original.id);
assert.equal(reads, 2, 'a rejected STOP must read the actual checkpoint before releasing the operation');
assert.equal(stopButton().props.disabled, true, 'keep STOP excluded while its checkpoint read is pending');
await act(async () => { originalStop.props.onClick(); });
assert.equal(controls, 1, 'a pending refresh cannot replay STOP or START');
await act(async () => { finishRead!(structuredClone(stopped)); });
assert.equal(Boolean(stopButton()), false, 'a real STOP ACK must remove the obsolete recording control');
assert.match(text(renderer.toJSON()), /STOP confirmed; recording upload interrupted/, 'retain the original transfer error');
assert.match(text(renderer.toJSON()), /连接后继续同步|等待来源设备|来源设备/, 'surface the original pending recording');
assert.equal(timers.size, 0, 'do not restart background recovery to hide the failed transfer');
await act(async () => { renderer.unmount(); });

for (const unreadable of [false, true]) {
  let failedReads = 0;
  (globalThis as any).__companionAppTest = {
    snapshot: async () => {
      if (++failedReads > 1 && unreadable) throw new Error('checkpoint read unavailable');
      return structuredClone(recording);
    },
    control: async () => { throw new Error('no STOP acknowledgement'); },
  };
  await act(async () => { renderer = create(<App />); });
  await act(async () => { stopButton().props.onClick(); });
  assert.equal(failedReads, 2);
  assert.ok(stopButton(), 'without a confirmed STOP, retain the last real recording state');
  assert.equal(stopButton().props.disabled, false);
  assert.match(text(renderer.toJSON()), /no STOP acknowledgement/);
  assert.doesNotMatch(text(renderer.toJSON()), /checkpoint read unavailable/, 'do not replace the actionable original error');
  await act(async () => { renderer.unmount(); });
}

// A retry can also save this exact original before another backlog item fails.
// Refresh its real receipt without starting another recording or claiming an ACK.
const received = structuredClone(stopped);
const local = received.host.sessions.find(session => session.id === original.id)!;
local.audioPath = 'received-original.wav';
local.audioBytes = 9_600_044;
local.audioStored = true;
local.deviceReclaimed = false;
local.pendingReason = 'needs_transcription';
local.retention.audioCached = true;
let syncReads = 0;
const retries: any[] = [];
(globalThis as any).__companionAppTest = {
  snapshot: async () => structuredClone(++syncReads === 1 ? stopped : received),
  syncStatus: async () => ({ phase: 'paused', jobId: null, deviceId: original.sourceDeviceId,
    recordingId: 18, receivedBytes: 65_536, totalBytes: 630_894, pauseRequested: false }),
  control: async (request: unknown) => { retries.push(request); throw new Error('next backlog item unavailable'); },
};
await act(async () => { renderer = create(<App />); });
const resume = renderer.root.findAllByType('button').find((node: any) => text(node) === '继续同步');
assert.ok(resume);
await act(async () => { resume.props.onClick(); });
assert.equal(syncReads, 2);
assert.equal(retries.length, 1);
assert.equal(retries[0].action, 'deviceSyncRecordings');
assert.equal(retries[0].deviceId, original.sourceDeviceId);
assert.match(text(renderer.toJSON()), /音频已收齐/);
assert.match(text(renderer.toJSON()), /原录音仍保留/, 'a host receipt is not a device consume ACK');
assert.match(text(renderer.toJSON()), /next backlog item unavailable/);
assert.equal(Boolean(stopButton()), false);
await act(async () => { renderer.unmount(); });
assert.equal(timers.size, 0);
console.log('PASS_STOP_ERROR_REFRESH_COMPONENT_ONLY: STOP checkpoint refresh, duplicate exclusion, pending original, missing ACK/read protection, partial-sync receipt with source-bound retry and no inferred consume; hardware/GUI NOT_RUN');
