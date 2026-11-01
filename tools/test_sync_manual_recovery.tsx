import assert from 'node:assert/strict';
import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';
import { CompanionRecordingSync, type RecordingSyncStatus } from '../packages/ui/src/CompanionRecordingSync';

const base: RecordingSyncStatus = {
  jobId: null, deviceId: null, phase: 'blocked', recordingId: 0,
  receivedBytes: 0, totalBytes: 0, pauseRequested: false,
  error: '录音同步设置暂时不可读取，自动同步已暂停；可以手动同步当前设备，原录音保留。',
};
let selected = '';
const show = (status: RecordingSyncStatus, recoveryDeviceId?: string, resumeBlocked = false) =>
  TestRenderer.create(<CompanionRecordingSync status={status} pauseBusy={false}
    resumeBlocked={resumeBlocked} recoveryDeviceId={recoveryDeviceId} onResume={id => { selected = id; }} />);

const blocked = show({ ...base, deviceId: 'old-device' }, 'current-device');
assert.match(JSON.stringify(blocked.toJSON()), /可以手动同步当前设备/);
const manual = blocked.root.findByType('button');
assert.ok(manual.children.includes('手动同步录音'));
act(() => manual.props.onClick());
assert.equal(selected, 'current-device', 'manual sync uses the connected device, not a stale one');

const paused = show({ ...base, phase: 'paused', deviceId: 'paused-device', error: undefined }, 'current-device');
act(() => paused.root.findByType('button').props.onClick());
assert.equal(selected, 'paused-device', 'an ordinary pause keeps its own device');
assert.equal(show(base).root.findAllByType('button').length, 0, 'unknown device is not guessed');
assert.equal(show(base, 'current-device', true).root.findByType('button').props.disabled, true);
console.log('PASS manual recovery button uses the intended device and preserves pause behavior');
