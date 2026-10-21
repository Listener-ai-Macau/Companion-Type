import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { App } from '../apps/windows/src/App';

const timers = new Map<number, () => void>();
let nextTimer = 0;
(globalThis as any).window = {
  setTimeout: (fn: () => void) => { timers.set(++nextTimer, fn); return nextTimer; },
  clearTimeout: (id: number) => timers.delete(id),
};
const snapshot = createCompanionV1Fixture();
snapshot.connected = true;
snapshot.device.connected = true;
snapshot.device.rememberedDeviceId = 'AABBCCDDEEFF';
snapshot.device.autoReconnectEnabled = false;
let listener: (status: unknown) => void;
let initialStatus: (status: unknown) => void;
let finishControl: (snapshot: unknown) => void;
let finishPause: (accepted: boolean) => void;
let released = false;
const controls: any[] = [], pauses: string[] = [];
(globalThis as any).__companionAppTest = {
  snapshot: async () => structuredClone(snapshot),
  watchSync: (handler: (status: unknown) => void) => { listener = handler; return () => { released = true; }; },
  syncStatus: () => new Promise(resolve => { initialStatus = resolve; }),
  control: (request: unknown) => { controls.push(request); return new Promise(resolve => { finishControl = resolve; }); },
  pauseSync: (jobId: string) => { pauses.push(jobId); return new Promise(resolve => { finishPause = resolve; }); },
};
const text = (node: any): string => typeof node === 'string' ? node : (node.children ?? []).map(text).join('');
let renderer: any;
await act(async () => { renderer = create(<App />); });
const button = (label: string) => renderer.root.findAllByType('button').find((node: any) => text(node) === label);
const connect = button('重新连接') ?? button('连接 Companion');
assert.ok(connect);
await act(async () => { connect.props.onClick(); });
assert.equal(controls.length, 1);
const active = { jobId: 'job-a', deviceId: 'AABBCCDDEEFF', phase: 'receiving', recordingId: 7,
  receivedBytes: 65_632, totalBytes: 631_104, pauseRequested: false };
await act(async () => { listener!(active); });
await act(async () => { initialStatus!({ ...active, jobId: null, phase: 'idle' }); });
assert.ok(button('暂停同步'), 'a stale initial status cannot hide a newer receive job');
assert.equal(button('暂停同步').props.disabled, false, 'pause bypasses the pending ordinary control gate');
await act(async () => { button('暂停同步').props.onClick(); button('暂停同步').props.onClick(); });
assert.deepEqual(pauses, ['job-a'], 'duplicate clicks issue one job-bound pause IPC');
assert.equal(controls.length, 1, 'pause must not dispatch microphone STOP or destructive controls');
await act(async () => {
  listener!({ ...active, jobId: null, phase: 'paused' });
  finishControl!(structuredClone(snapshot));
});
assert.ok(button('继续同步'));
assert.equal(button('继续同步').props.disabled, false);
await act(async () => { button('继续同步').props.onClick(); });
assert.equal(controls[1].action, 'deviceSyncRecordings');
assert.equal(controls[1].deviceId, active.deviceId);
await act(async () => { listener!({ ...active, jobId: 'job-b', phase: 'saving' }); });
await act(async () => { finishPause!(true); });
assert.ok(button('暂停同步'), 'a late old pause ACK cannot mark the new sync paused');
assert.match(text(renderer.toJSON()), /本条|安全位置/, 'saving describes the safe pause boundary');
await act(async () => { listener!({ ...active, jobId: 'job-b', phase: 'reclaiming', pauseRequested: true }); });
assert.equal(button('正在暂停…').props.disabled, true);
assert.match(text(renderer.toJSON()), /保存和回收完成后/);
await act(async () => { listener!({ ...active, jobId: null, phase: 'paused' }); });
assert.match(text(renderer.toJSON()), /重开软件仍保持暂停/);
await act(async () => { listener!({ ...active, jobId: null, phase: 'blocked', error: '录音同步设置暂时不可读取，自动同步已暂停；设备原录音保留。' }); });
assert.match(text(renderer.toJSON()), /设置暂时不可读取/);
assert.equal(button('继续同步'), undefined, 'unreadable settings cannot offer a false resume');
assert.equal(button('暂停同步'), undefined);
await act(async () => { renderer.unmount(); });
assert.equal(released, true);
console.log('PASS_LOCAL_SYNC_PAUSE_UI_ONLY: pending-operation pause, duplicate click, stale status/ACK, source-bound resume, safe saving/reclaim boundary, listener cleanup');
