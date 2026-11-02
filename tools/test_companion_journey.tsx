import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture, describeCompanionMeetingRecovery } from '../packages/core/src/companionV1';
import { meetingJourney } from '../packages/ui/src/CompanionJourney';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';

// Pure component/state checks. No browser, device, file dialog or remote service.
async function main() {
  const snapshot = applyCompanionV1ControlFixture(createCompanionV1Fixture(), { action: 'meetingLoadDemo' });
  const session = snapshot.host.sessions[0];
  session.minutesByMode!.onlineLive = { ...session.minutesByMode!.offlineStore!, markdown: '# 在线版本', partialCount: 3 };
  const raw = structuredClone(session);
  raw.id = 'new-device-recording'; raw.title = '刚同步的录音'; raw.status = 'captured'; raw.source = 'boardDevice';
  raw.transcriptText = ''; raw.transcriptFinal = false;
  raw.minutes = null; raw.minutesByMode = { offlineStore: null, onlineLive: null }; raw.exportMarkdown = '';
  raw.audioPath = 'C:/recordings/new.wav'; raw.audioStored = true; raw.audioBytes = 16000;
  raw.pendingReason = 'needs_transcription';
  raw.recovery = { intent: 'none', stage: 'idle', requestedMeetingMode: 'offlineStore', attemptCount: 0, maxAttempts: 3 };
  const offline = { connected: false, deviceId: null, asrReady: true, minutesReady: true };
  let next = meetingJourney(raw, offline);
  assert.equal(next.stage, 1, 'a disconnected device must not reset saved audio progress');
  assert.deepEqual(next.request, { action: 'meetingTranscribeAudio', sessionId: raw.id });
  assert.match(next.detail, /本机转写.*云端服务/);
  assert.equal(meetingJourney(raw, { ...offline, asrReady: false }).destination, 'settings');
  const awaiting = { ...raw, audioPath: null, audioBytes: 0, audioStored: false, pendingReason: 'needs_device_sync' as const, sourceDeviceId: 'AA:BB:CC:DD:EE:FF' };
  assert.deepEqual(meetingJourney(awaiting, { ...offline, connected: true, deviceId: '112233445566' }).request,
    { action: 'deviceConnect', deviceId: awaiting.sourceDeviceId });
  assert.equal(meetingJourney(awaiting, { ...offline, connected: true, deviceId: 'AABBCCDDEEFF' }).request?.action, 'deviceSyncRecordings');
  assert.equal(meetingJourney({ ...awaiting, sourceDeviceId: null }, offline).request, undefined, 'unknown origin must not pick a nearby device silently');
  const transcribed = { ...raw, transcriptText: '完整文字', transcriptFinal: true, status: 'transcribed' as const };
  assert.equal(meetingJourney(transcribed, offline).stage, 2);
  assert.equal(meetingJourney(transcribed, offline).request?.action, 'meetingGenerateMinutes');
  const waiting = { ...transcribed, recovery: { ...raw.recovery!, intent: 'processMeeting' as const, stage: 'pendingMinutes' as const } };
  assert.equal(meetingJourney(waiting, offline).request?.action, 'meetingGenerateMinutes', 'saved text can be organized when processing has not started');
  const active = { ...waiting, recovery: { ...waiting.recovery, stage: 'generatingMinutes' as const } };
  assert.equal(meetingJourney(active, offline).request, undefined, 'active processing must not invite duplicate generation');
  const partial = { ...transcribed, transcriptFinal: false };
  assert.equal(meetingJourney(partial, offline).request?.action, 'meetingTranscribeAudio', 'live prefixes need final ASR');

  const interrupted = { ...raw, id: 'saved-interrupted-original', captureIncomplete: true, durationMs: 27000,
    pendingReason: 'capture_interrupted' as const,
    recovery: { ...raw.recovery!, intent: 'processMeeting' as const, stage: 'paused' as const, captureReviewConfirmed: false } };
  const fragment = meetingJourney(interrupted, offline);
  assert.match(fragment.title, /录音中断/);
  assert.match(fragment.detail, /27 秒/);
  assert.match(fragment.label!, /已保存的片段/);
  assert.deepEqual(fragment.request, { action: 'meetingTranscribeAudio', sessionId: interrupted.id });
  assert.equal(describeCompanionMeetingRecovery(interrupted)?.isProcessing, false);
  assert.equal(meetingJourney(interrupted, { ...offline, asrReady: false }).destination, 'settings');
  const fragmentText = { ...interrupted, transcriptText: '只覆盖已保存的内容', transcriptFinal: true };
  assert.deepEqual(meetingJourney(fragmentText, offline).request,
    { action: 'meetingGenerateMinutes', sessionId: interrupted.id });
  const confirmed = { ...interrupted, pendingReason: 'recovery_processing' as const,
    recovery: { ...interrupted.recovery, captureReviewConfirmed: true, stage: 'pendingTranscription' as const } };
  assert.equal(meetingJourney(confirmed, offline).request, undefined, 'confirmed queued fragment must not offer duplicate work');
  const oldComplete = { ...session, captureIncomplete: true,
    recovery: { ...interrupted.recovery, stage: 'complete' as const } };
  assert.equal(describeCompanionMeetingRecovery(oldComplete), null, 'a committed product is not retroactively resubmitted');

  snapshot.host.sessions.push(raw); snapshot.host.selectedSessionId = session.id;
  snapshot.connected = false; snapshot.device.connected = false;
  let resolveExport: (value: any) => void = () => {};
  const exports: any[] = []; const controls: any[] = [];
  const props: any = { snapshot, busyAction: null, error: null, surface: 'windows',
    onRefresh: () => {}, onControl: (request: unknown) => controls.push(request),
    onExportMeeting: (request: unknown) => { exports.push(request); return new Promise((resolve) => { resolveExport = resolve; }); } };
  let renderer: any;
  act(() => { renderer = create(<CompanionDashboard {...props} />); });
  const text = (node: any): string => typeof node === 'string' ? node : (node.children ?? []).map(text).join('');
  const button = (label: string) => {
    const found = renderer.root.findAllByType('button').find((node: any) => text(node).includes(label));
    assert.ok(found, `missing button ${label}`); return found;
  };
  assert.ok(button(raw.title), 'new untranscribed audio must remain visible without expanding an archive');
  act(() => button('更多录音与处理操作').props.onClick());
  act(() => button('在线速记').props.onClick());
  act(() => { const save = button('导出 Markdown').props.onClick; save(); save(); });
  assert.equal(exports.length, 1);
  assert.equal(exports[0].sessionId, session.id);
  assert.equal(exports[0].format, 'markdown');
  assert.equal(exports[0].meetingMode, 'onlineLive', 'export the visible minutes variant, even when capture used another mode');
  assert.equal(controls.length, 0, 'saving must not dispatch legacy AI generation/export actions');
  snapshot.host.selectedSessionId = raw.id;
  act(() => renderer.update(<CompanionDashboard {...props} snapshot={structuredClone(snapshot)} />));
  await act(async () => { resolveExport({ path: 'C:/exports/previous.md', bytes: 10 }); });
  assert.ok(!text(renderer.toJSON()).includes('previous.md'), 'previous meeting export feedback must not attach to another meeting');
  act(() => button('更多录音与处理操作').props.onClick());

  const live = { state: 'recording', durationMs: 18000, partialCount: 2, sessionId: 'active-other', deviceId: 'AABBCCDDEEFF' };
  let stopped = 0;
  act(() => renderer.update(<CompanionDashboard {...props} snapshot={structuredClone(snapshot)}
    boardOnlineLive={live as any} onStopBoardOnlineLive={() => { stopped++; }} />));
  assert.equal(renderer.root.findAllByProps({ 'aria-label': '主路径步骤' }).length, 0);
  assert.equal(button('结束录音并整理').props.disabled, false, 'stop must be reachable while workflow is collapsed and another meeting selected');
  act(() => button('结束录音并整理').props.onClick());
  assert.equal(stopped, 1);
  act(() => renderer.update(<CompanionDashboard {...props} boardOnlineLive={{ ...live, state: 'finalizing' } as any}
    onStopBoardOnlineLive={() => { stopped++; }} />));
  assert.equal(button('结束录音并整理').props.disabled, true, 'finalization is no longer a stoppable recording');
  snapshot.device.recording = true; snapshot.device.deviceId = 'AABBCCDDEEFF'; snapshot.meeting.active = false;
  act(() => renderer.update(<CompanionDashboard {...props} snapshot={structuredClone(snapshot)} />));
  assert.equal(button('扫描设备').props.disabled, true);
  assert.equal(button('检查设备').props.disabled, true);
  assert.equal(button('读取设备状态').props.disabled, false, 'read-only refresh must remain possible to observe locally stopped recording');
  act(() => button('读取设备状态').props.onClick());
  assert.deepEqual(controls.at(-1), { action: 'deviceConnect', deviceId: 'AABBCCDDEEFF' });
  snapshot.device.recording = false; snapshot.host.selectedSessionId = session.id;
  act(() => renderer.update(<CompanionDashboard {...props} snapshot={structuredClone(snapshot)} />));
  act(() => button('更多录音与处理操作').props.onClick());
  act(() => button('导出 Markdown').props.onClick());
  await act(async () => { resolveExport(null); });
  assert.match(text(renderer.toJSON()), /已取消保存/);
  act(() => button('导出 Markdown').props.onClick());
  await act(async () => { resolveExport({ path: 'C:/exports/saved.md', bytes: 32, warning: '导出记录未能更新' }); });
  assert.match(text(renderer.toJSON()), /已保存：saved.md（导出记录未能更新）/);
  assert.equal(controls.filter((request) => request.action.startsWith('meetingExport')).length, 0);
  act(() => renderer.unmount());
  const fragmentSnapshot = structuredClone(snapshot);
  fragmentSnapshot.host.sessions = [interrupted]; fragmentSnapshot.host.selectedSessionId = interrupted.id;
  const fragmentControls: any[] = [];
  act(() => { renderer = create(<CompanionDashboard {...props} snapshot={fragmentSnapshot}
    productSettings={{ asrProvider: 'volcengine', volcAppKeySet: true, volcAccessKeySet: true,
      volcResourceId: 'fixture-resource' } as any}
    onControl={(request: unknown) => fragmentControls.push(request)} />); });
  assert.match(text(renderer.toJSON()), /录音中断/);
  assert.match(text(renderer.toJSON()), /27 秒/);
  assert.deepEqual(fragmentControls, [], 'rendering a saved fragment must not start processing or playback');
  act(() => button('转写已保存的片段').props.onClick());
  assert.deepEqual(fragmentControls, [{ action: 'meetingTranscribeAudio', sessionId: interrupted.id }]);
  act(() => renderer.unmount());
  console.log('PASS_MEETING_JOURNEY_COMPONENTS_ONLY: offline progress, source-bound resume, global stop, local export and explicit interrupted-fragment routing; no browser or hardware');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
