import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';

// Component tests in memory: no browser, device, microphone or remote service.
const demo = applyCompanionV1ControlFixture(createCompanionV1Fixture(), { action: 'meetingLoadDemo' });
const first = structuredClone(demo.host.sessions[0]);
first.id = 'meeting-a'; first.title = '会议 A'; first.transcriptText = 'A 的转写';
const second = structuredClone(first);
second.id = 'meeting-b'; second.title = '会议 B'; second.transcriptText = '';
second.minutes = null; second.exportMarkdown = ''; second.minutesByMode = { offlineStore: null, onlineLive: null };
second.status = 'recorded'; second.pendingReason = 'needs_transcription';
second.recovery = { intent: 'none', requestedMeetingMode: 'offlineStore', stage: 'idle', attemptCount: 0, maxAttempts: 3 };
let snapshot = createCompanionV1Fixture();
snapshot.host.sessions = [first, second]; snapshot.host.selectedSessionId = first.id;
const calls: any[] = [];
const props = () => ({ snapshot, surface: 'windows' as const, busyAction: null,
  error: null, onRefresh: () => {}, onControl: (request: unknown) => { calls.push(request); } });
let renderer: any;
act(() => { renderer = create(<CompanionDashboard {...props()} />); });
const text = (node: any): string => typeof node === 'string' ? node : (node.children ?? []).map(text).join('');
const button = (label: string) => {
  const node = renderer.root.findAllByType('button').find((n: any) => text(n).includes(label));
  assert.ok(node, `button not found: ${label}`); return node;
};
const click = (label: string) => act(() => button(label).props.onClick());
const editor = () => renderer.root.findAllByType('textarea').find((n: any) => n.props.className?.includes('ct-step-textarea'));
click('更多录音与处理操作');
assert.equal(editor().props.value, 'A 的转写');
act(() => editor().props.onChange({ target: { value: 'A 的手动修改，尚未导入' } }));
snapshot = structuredClone(snapshot); snapshot.host.sessions[0].transcriptText = '后台更新';
act(() => renderer.update(<CompanionDashboard {...props()} />));
assert.equal(editor().props.value, 'A 的手动修改，尚未导入', 'background refresh must preserve manual edits');

snapshot = structuredClone(snapshot); snapshot.host.selectedSessionId = second.id;
act(() => renderer.update(<CompanionDashboard {...props()} />));
assert.equal(editor().props.value, '', 'switching to untranscribed meeting must clear unrelated text');
assert.equal(button('导入到这条录音').props.disabled, true);
assert.equal(calls.some((call) => call.action === 'meetingSelectSession'), false, 'must not auto-select a different readable meeting');
assert.ok(button('会议 B'), 'explicitly selected unprocessed meeting stays visible');

click('展开设置与工具');
click('删当前录音');
assert.equal(calls.length, 0, 'opening confirmation must not delete anything');
assert.equal(renderer.root.findAllByProps({ role: 'alertdialog' }).length, 1);
assert.match(text(renderer.root.findByProps({ role: 'alertdialog' })), /设备上的录音保持不变/);
snapshot = structuredClone(snapshot); snapshot.host.selectedSessionId = first.id;
snapshot.host.sessions[0].sourceDeviceId = 'AA:BB:CC:DD:EE:FF';
snapshot.host.sessions[0].deviceRecordingId = 7;
snapshot.host.sessions[0].deviceTotalLength = 128;
snapshot.host.sessions[0].deviceSha256 = 'a'.repeat(64);
snapshot.host.sessions[0].deviceReclaimed = false;
act(() => renderer.update(<CompanionDashboard {...props()} />));
assert.equal(renderer.root.findAllByProps({ role: 'alertdialog' }).length, 0, 'switching meeting invalidates old confirmation');
click('删当前录音');
assert.match(text(renderer.root.findByProps({ role: 'alertdialog' })), /精确回收设备/);
click('保留内容');
assert.equal(calls.length, 0);
click('删当前录音'); click('确认删除');
assert.equal(calls.at(-1).action, 'privacyDeleteSession');
assert.equal(calls.at(-1).sessionId, first.id, 'confirmed request is bound to displayed meeting');
const callsBeforePreview = calls.length;
click('开始 10 秒预览');
assert.match(text(renderer.root.findByProps({ 'aria-label': '陪伴模式预览' })), /10 秒/);
click('停止预览');
assert.equal(calls.length, callsBeforePreview, 'silent behavior preview must not send a device or audio command');

snapshot = structuredClone(snapshot); snapshot.meeting.active = true;
act(() => renderer.update(<CompanionDashboard {...props()} />));
for (const label of ['扫描设备', '检查设备', '删当前录音', '清除全部本机会议', '导入到这条录音', '保存到设备', '恢复默认名称', '开始 10 秒预览']) {
  assert.equal(button(label).props.disabled, true, `${label} must not interrupt recording`);
}
act(() => renderer.unmount());
console.log('PASS_COMPONENT_STATE_ONLY: meeting selection, draft isolation, refresh preservation, scoped deletion confirmation, recording locks');

// Online recordings can finish transcription before their minutes arrive. The
// displayed mode and export request must follow that session throughout recovery.
snapshot = createCompanionV1Fixture();
const online = structuredClone(second);
online.meetingMode = 'onlineLive'; online.transcriptText = '在线会议最终文字';
online.transcriptFinal = true; online.status = 'transcribed';
snapshot.host.sessions = [online]; snapshot.host.selectedSessionId = online.id;
const exports: any[] = [];
const exportProps = () => ({ ...props(), onExportMeeting: async (request: unknown) => { exports.push(request); return null; } });
act(() => { renderer = create(<CompanionDashboard {...exportProps()} />); });
click('展开设置与工具');
click('TXT');
assert.equal(exports.at(-1).meetingMode, 'onlineLive', 'transcript export must use the captured mode before minutes exist');
snapshot = structuredClone(snapshot);
snapshot.host.sessions[0].minutesByMode.onlineLive = {
  ...first.minutesByMode.offlineStore!, meetingMode: 'onlineLive', markdown: '# 在线结果', status: 'minutesReady', quality: 'final',
};
act(() => renderer.update(<CompanionDashboard {...exportProps()} />));
click('智能纪要');
assert.equal(button('在线速记').props['aria-selected'], true, 'newly completed online minutes must select the available mode');
assert.match(text(renderer.root.findByProps({ className: 'ct-minutes-article' })), /在线结果/);
snapshot = structuredClone(snapshot);
snapshot.host.sessions[0].minutesByMode.offlineStore = { ...snapshot.host.sessions[0].minutesByMode.onlineLive!, meetingMode: 'offlineStore', markdown: '# 离线结果' };
snapshot.host.sessions[0].transcriptText += '，后台补齐';
act(() => renderer.update(<CompanionDashboard {...exportProps()} />));
assert.equal(button('在线速记').props['aria-selected'], true, 'background completion must preserve the viewed mode');
click('完整转写');
snapshot = structuredClone(snapshot); snapshot.host.sessions[0].title = '后台同步标题';
act(() => renderer.update(<CompanionDashboard {...exportProps()} />));
assert.ok(button('完整转写').props.className.includes('active'), 'background updates must preserve the current reading tab');
act(() => renderer.unmount());
console.log('PASS_COMPONENT_RECOVERY_MODE_ONLY: online transcript export, arriving minutes, stable reading mode');

snapshot = structuredClone(snapshot);
snapshot.host.persistence = { status: 'unsaved', message: '磁盘写入失败，最新内容尚未保存。请保留当前窗口。' };
act(() => { renderer = create(<CompanionDashboard {...props()} />); });
assert.match(text(renderer.root.findByProps({ 'aria-label': '会议保存状态' })), /尚未保存/);
click('重试保存');
assert.equal(calls.at(-1).action, 'hostRetrySave');
snapshot = structuredClone(snapshot); snapshot.host.persistence.status = 'blocked';
act(() => renderer.update(<CompanionDashboard {...props()} />));
click('重试恢复');
assert.equal(calls.at(-1).action, 'hostRetrySave');
snapshot = structuredClone(snapshot); snapshot.host.persistence.status = 'ready';
act(() => renderer.update(<CompanionDashboard {...props()} />));
assert.equal(renderer.root.findAllByProps({ 'aria-label': '会议保存状态' }).length, 0);
act(() => renderer.unmount());
console.log('PASS_COMPONENT_STORAGE_ONLY: persistent save/recovery warning and explicit retry');

const settings: any = { defaultMeetingMode: 'offlineStore', asrProvider: 'volcengine',
  volcResourceId: 'volc.bigasr.sauc.duration', openaiAsrEndpoint: 'https://example.test/asr',
  openaiAsrModel: 'existing-model', deepseekBaseUrl: 'https://example.test/minutes',
  deepseekModel: 'existing-model', deepseekMinutesEnabled: true, bleCompress: false };
act(() => { renderer = create(<CompanionDashboard {...props()} productSettings={settings} />); });
click('展开设置与工具');
const providerSelect = renderer.root.findAllByType('label').find((label: any) => text(label).includes('ASR 提供商'))!.findByType('select');
assert.equal(renderer.root.findAllByType('label').some((label: any) => text(label).includes('兼容服务 Endpoint')), false,
  'inactive provider fields must stay hidden');
act(() => providerSelect.props.onChange({ target: { value: 'openai-compatible' } }));
const modelInput = () => renderer.root.findAllByType('label').find((label: any) => text(label) === '兼容服务模型')!.findByType('input');
assert.match(text(renderer.root.findByProps({ 'aria-label': '服务配置缺项' })), /兼容服务 Key.*DeepSeek Key/,
  'provider-specific missing credentials must be explained without claiming a service check');
act(() => modelInput().props.onChange({ target: { value: 'unsaved-model' } }));
act(() => renderer.update(<CompanionDashboard {...props()} productSettings={{ ...settings }} />));
assert.equal(modelInput().props.value, 'unsaved-model', 'refreshing unchanged settings must not erase unsaved edits');
assert.match(text(renderer.toJSON()), /数据会离开 Companion Type/);
act(() => renderer.unmount());
console.log('PASS_COMPONENT_SETTINGS_DRAFT_ONLY: unchanged refresh preserves service edits');

snapshot = createCompanionV1Fixture(); snapshot.connected = true; snapshot.device.connected = true;
act(() => { renderer = create(<CompanionDashboard {...props()} />); });
click('展开设置与工具');
click('板端开始录音');
assert.equal(calls.at(-1).action, 'meetingStart');
assert.equal(calls.at(-1).durationMs, 30 * 60 * 1000,
  'the displayed thirty-minute board limit must reach the backend start request');
const offlineDuration = () => renderer.root.findAllByType('label').find((n: any) => text(n) === '最长录音(分)')!.findByType('input');
assert.match(text(renderer.root.findByProps({'aria-label':'设备录音容量'})),/尚未取得设备容量/);
assert.doesNotMatch(text(renderer.root.findByProps({'aria-label':'设备录音容量'})),/14.*MB/);
act(() => offlineDuration().props.onChange({target:{value:'60'}}));
click('板端开始录音');assert.equal(calls.at(-1).durationMs,3600000,'offline must not inherit 43-minute live cap');
act(() => offlineDuration().props.onChange({target:{value:''}}));
assert.equal(button('板端开始录音').props.disabled,true,'blank duration cannot silently become thirty minutes');
act(() => renderer.unmount());
console.log('PASS_COMPONENT_RECORDING_LIMIT_ONLY: board start carries the displayed limit');

const onlineStarts: any[] = [];
snapshot.device.deviceId = 'AA:BB:CC:DD:EE:FF';
const connectedOnlineProps = () => ({ ...props(), productSettings: {
  ...settings, volcAppKeySet: true, volcAccessKeySet: true,
}, onStartBoardOnlineLive: async (request: unknown) => { onlineStarts.push(request); } });
act(() => { renderer = create(<CompanionDashboard {...connectedOnlineProps()} />); });
click('展开设置与工具'); click('在线转写');
const callCount = calls.length;
assert.equal(button('板端开始录音').props.disabled, false);
click('板端开始录音');
assert.equal(calls.length, callCount, 'online board recording must not enter the offline meeting-control path');
assert.equal(onlineStarts.at(-1).deviceId, snapshot.device.deviceId);
assert.equal(onlineStarts.at(-1).maxDurationSeconds, 1800);
const liveDuration = () => renderer.root.findAllByType('label').find((n: any) => text(n) === '最长录音(分)')!.findByType('input');
act(() => liveDuration().props.onChange({target:{value:'60'}}));
assert.equal(button('板端开始录音').props.disabled,true);
assert.match(text(renderer.toJSON()),/请修改时长；不会自动截短/);
act(() => liveDuration().props.onChange({target:{value:'30'}}));
snapshot.device.recordingCapacity={layoutVersion:1,busy:false,usedEntries:3,maxEntries:7,
  catalogGeneration:9,dataBytes:57344,freeBytes:32768,largestFreeExtent:24576,
  protectedBytes:16384,consumedBytes:8192,bytesPerSecond:2100,reserveHeadroom:4096,localLimitSeconds:1800,
  unsyncedEntries:1,writingEntries:1,consumedEntries:1};
act(() => renderer.update(<CompanionDashboard {...connectedOnlineProps()} boardOnlineLive={{
  state:'recording',sessionId:'limit-test',deviceId:snapshot.device.deviceId,recordingId:1,
  partialCount:1,durationMs:1200000,maxDurationSeconds:1500,disconnectResume:false,finalRecordingPath:null,error:null,
}} />));
assert.match(text(renderer.root.findByProps({'aria-label':'设备录音容量'})),/目录 3\/7/);
assert.match(text(renderer.root.findByProps({'aria-label':'当前录音'})),/距本次设定结束约 5:00/);
assert.doesNotMatch(text(renderer.root.findByProps({'aria-label':'当前录音'})),/距 43 分钟/);
act(() => renderer.update(<CompanionDashboard {...connectedOnlineProps()} productSettings={settings} />));
assert.equal(button('板端开始录音').props.disabled, true, 'online board capture requires a configured ASR service');
act(() => renderer.unmount());
console.log('PASS_COMPONENT_ADVANCED_ONLINE_ROUTE_ONLY: online board start uses streaming coordinator');

async function testProductPolish() {
  snapshot = applyCompanionV1ControlFixture(createCompanionV1Fixture(), { action: 'meetingLoadDemo' });
  snapshot.host.persistence = { status: 'ready' };
  const session = snapshot.host.sessions[0];
  session.sourceDeviceId = 'AA:BB:CC:DD:EE:FF'; session.deviceRecordingId = 9;
  session.deviceTotalLength = Math.max(session.audioBytes, 16000); session.deviceSha256 = 'b'.repeat(64);
  session.deviceReclaimed = false; session.audioStored = true; session.audioBytes = Math.max(session.audioBytes, 16000);
  session.minutesByMode!.onlineLive = { ...session.minutesByMode!.offlineStore!, markdown: '# 在线原稿', partialCount: 2 };
  session.minutesByMode!.offlineStore!.source = 'userEdited';
  const otherSession = structuredClone(session); otherSession.id = 'other-audio-session'; otherSession.title = '另一场会议';
  snapshot.host.sessions.push(otherSession);
  const saveCalls: any[] = [];
  let saveStatus: 'ready' | 'unsaved' = 'unsaved';
  const polishedProps = () => ({ ...props(),
    onPrepareAudio: async (sessionId: string) => ({ sessionId, url: `asset://meeting/${sessionId}` }),
    onSaveMeeting: async (request: any) => {
      saveCalls.push(request);
      const next = structuredClone(snapshot);
      const saved = next.host.sessions.find((item: any) => item.id === request.sessionId);
      if (saved && request.title !== undefined) saved.title = request.title;
      if (saved && request.markdown !== undefined && request.meetingMode) {
        saved.minutesByMode[request.meetingMode].markdown = request.markdown;
      }
      next.host.persistence = saveStatus === 'ready' ? { status: 'ready' } : { status: 'unsaved', message: '写入失败，草稿保留' };
      return next;
    },
  });
  const audioNodes: any[] = [];
  act(() => { renderer = create(<CompanionDashboard {...polishedProps()} />, { createNodeMock: (element: any) => {
    if (element.type !== 'audio') return {};
    const node = { paused: false, removed: false, loaded: 0, pause() { this.paused = true; },
      removeAttribute(name: string) { if (name === 'src') this.removed = true; }, load() { this.loaded += 1; } };
    audioNodes.push(node); return node;
  } }); });
  click('更多录音与处理操作');
  assert.match(text(renderer.toJSON()), /录制模式（先录后整理）纪要含人工修改。再次生成会替换这一版，建议先导出保存/);
  const titleInput = () => renderer.root.findByProps({ 'aria-label': '会议标题' });
  act(() => titleInput().props.onChange({ target: { value: '  用户标题草稿  ' } }));
  snapshot = structuredClone(snapshot); snapshot.host.sessions[0].title = '后台标题';
  act(() => renderer.update(<CompanionDashboard {...polishedProps()} />));
  assert.equal(titleInput().props.value, '  用户标题草稿  ', 'background refresh must not replace a title draft');
  await act(async () => { await button('保存标题').props.onClick(); });
  assert.equal(saveCalls.at(-1).title, '用户标题草稿', 'host receives the trimmed title it persists');
  assert.notEqual(saveCalls.at(-1).expectedTitle, '后台标题', 'optimistic save keeps the edit baseline');
  assert.match(text(renderer.toJSON()), /写入失败，草稿保留/);
  assert.equal(titleInput().props.value, '  用户标题草稿  ', 'failed persistence must keep the exact title draft');
  await act(async () => { await button('保存标题').props.onClick(); });
  assert.equal(saveCalls.at(-1).expectedTitle, '用户标题草稿', 'retry rebases an identical trimmed in-memory edit after persistence failure');

  click('编辑当前纪要');
  const minutesEditor = () => renderer.root.findAllByType('textarea').find((node: any) => String(node.props['aria-label'] ?? '').startsWith('编辑'));
  act(() => minutesEditor().props.onChange({ target: { value: '  \n# 用户离线草稿\n\n- 保留这项\n  ' } }));
  click('在线速记');
  assert.match(text(renderer.toJSON()), /录制模式（先录后整理）纪要含人工修改/,
    'generation warning follows the capture mode instead of the viewed minutes variant');
  click('编辑当前纪要');
  assert.equal(minutesEditor().props.value, '# 在线原稿', 'minutes drafts are isolated by mode');
  click('取消'); click('先录后整理'); click('编辑当前纪要');
  assert.match(minutesEditor().props.value, /用户离线草稿/, 'switching modes must preserve the first mode draft');
  await act(async () => { await button('保存修改').props.onClick(); });
  assert.equal(saveCalls.at(-1).markdown, '# 用户离线草稿\n\n- 保留这项', 'host receives the trimmed markdown it persists');
  assert.match(minutesEditor().props.value, /\s# 用户离线草稿/, 'failed persistence keeps the exact markdown draft');

  await act(async () => { await button('准备回听').props.onClick(); });
  assert.equal(renderer.root.findByType('audio').props.src, `asset://meeting/${session.id}`);
  snapshot = structuredClone(snapshot); snapshot.host.selectedSessionId = otherSession.id;
  act(() => renderer.update(<CompanionDashboard {...polishedProps()} />));
  assert.equal(audioNodes[0].paused, true, 'switching meetings pauses the exact old player node');
  assert.equal(audioNodes[0].removed, true, 'switching meetings removes the old player source');
  assert.equal(renderer.root.findAllByType('audio').length, 0);
  snapshot = structuredClone(snapshot); snapshot.host.selectedSessionId = session.id;
  act(() => renderer.update(<CompanionDashboard {...polishedProps()} />));
  assert.equal(renderer.root.findByType('audio').props.src, `asset://meeting/${session.id}`,
    'returning to an unchanged session may reuse its identity-bound authorization');
  snapshot = structuredClone(snapshot); snapshot.meeting.active = true;
  act(() => renderer.update(<CompanionDashboard {...polishedProps()} />));
  assert.equal(renderer.root.findAllByType('audio').length, 0, 'starting any recording must remove the prepared audio player');
  assert.match(text(renderer.root.findByProps({ 'aria-label': '本机原音回听' })), /录音进行中/);
  snapshot = structuredClone(snapshot); snapshot.meeting.active = false;
  act(() => renderer.update(<CompanionDashboard {...polishedProps()} />));
  await act(async () => { await button('准备回听').props.onClick(); });
  act(() => renderer.root.findByType('audio').props.onError());
  assert.equal(renderer.root.findAllByType('audio').length, 0);
  assert.match(text(renderer.root.findByProps({ 'aria-label': '本机原音回听' })), /移动、删除或损坏/);
  await act(async () => { await button('准备回听').props.onClick(); });
  const playerAtUnmount = audioNodes.at(-1);
  let safety = text(renderer.root.findByProps({ 'aria-label': '录音安全状态' }));
  assert.match(safety, /可在删除会议时精确回收/);
  assert.doesNotMatch(safety, /设备副本已回收/);
  snapshot = structuredClone(snapshot); snapshot.host.sessions[0].deviceReclaimed = true;
  act(() => renderer.update(<CompanionDashboard {...polishedProps()} />));
  safety = text(renderer.root.findByProps({ 'aria-label': '录音安全状态' }));
  assert.match(safety, /设备副本已回收/);

  const search = renderer.root.findByProps({ 'aria-label': '搜索标题、转写或纪要' });
  act(() => search.props.onChange({ target: { value: '绝对不存在的全文' } }));
  assert.match(text(renderer.toJSON()), /没有找到相关会议/);
  act(() => renderer.unmount());
  assert.equal(playerAtUnmount.paused, true, 'unmount pauses the captured player node');
  assert.equal(playerAtUnmount.removed, true, 'unmount removes the captured player source');

  let resolveAudio: (value: { sessionId: string; url: string }) => void = () => {};
  snapshot = applyCompanionV1ControlFixture(createCompanionV1Fixture(), { action: 'meetingLoadDemo' });
  const staleId = snapshot.host.sessions[0].id;
  const deferredProps = () => ({ ...props(), onPrepareAudio: (sessionId: string) => new Promise<{ sessionId: string; url: string }>((resolve) => { resolveAudio = resolve; }) });
  act(() => { renderer = create(<CompanionDashboard {...deferredProps()} />); });
  act(() => button('准备回听').props.onClick());
  snapshot = structuredClone(snapshot); snapshot.meeting.active = true;
  act(() => renderer.update(<CompanionDashboard {...deferredProps()} />));
  await act(async () => { resolveAudio({ sessionId: staleId, url: 'asset://stale-result' }); });
  assert.equal(renderer.root.findAllByType('audio').length, 0, 'late audio authorization must be discarded after capture starts');
  act(() => renderer.unmount());
  console.log('PASS_COMPONENT_PRODUCT_POLISH_ONLY: search, conflict drafts, mode isolation, authorized audio, truthful reclaim');

  // This is a component callback test, not a native dialog/device acceptance.
  snapshot = createCompanionV1Fixture(); snapshot.connected = true;
  snapshot.device.connected = true; snapshot.device.deviceId = 'loss-device-a';
  snapshot.device.recordingCapacity = {layoutVersion:1,busy:false,confirmedDiscardSupported:true,
    usedEntries:3,maxEntries:7,catalogGeneration:9,dataBytes:8380416,freeBytes:16384,largestFreeExtent:16384,
    protectedBytes:8364032,consumedBytes:0,bytesPerSecond:2100,reserveHeadroom:4096,localLimitSeconds:1800,
    unsyncedEntries:3,writingEntries:0,consumedEntries:0};
  const lossCalls: number[] = [];
  let resolveLoss: (value: {status:'deleted'|'cancelled'|'noCandidate';message:string}) => void = () => {};
  const lossProps = () => ({...props(),onDiscardOldestRecording:(seconds:number) => {
    lossCalls.push(seconds);
    return new Promise<{status:'deleted'|'cancelled'|'noCandidate';message:string}>(resolve => {resolveLoss=resolve;});
  }});
  act(() => {renderer=create(<CompanionDashboard {...lossProps()} />);});
  const controlsBeforeLoss=calls.length;
  const inspectButton=button('查看可释放的最旧录音');
  act(() => {inspectButton.props.onClick();inspectButton.props.onClick();});
  assert.deepEqual(lossCalls,[1800],'double-click asks for one concrete loss proposal');
  assert.equal(button('重新读取设备容量').props.disabled,true,'pending native decision holds device controls');
  await act(async () => {resolveLoss({status:'cancelled',message:'已取消，未发送删除确认。'});});
  assert.match(text(renderer.root.findByProps({'aria-label':'设备录音容量'})),/已取消，未发送删除确认/);
  assert.equal(calls.length,controlsBeforeLoss,'preview/cancel must not dispatch clear-all, ACK or recording START');
  act(() => button('查看可释放的最旧录音').props.onClick());
  snapshot=structuredClone(snapshot);snapshot.device.deviceId='loss-device-b';
  act(() => renderer.update(<CompanionDashboard {...lossProps()} />));
  await act(async () => {resolveLoss({status:'deleted',message:'OLD_DEVICE_DELETE_RESULT'});});
  assert.doesNotMatch(text(renderer.toJSON()),/OLD_DEVICE_DELETE_RESULT/,'old-device result must not be shown as new-device success');
  snapshot=structuredClone(snapshot);snapshot.device.recordingCapacity!.confirmedDiscardSupported=false;
  act(() => renderer.update(<CompanionDashboard {...lossProps()} />));
  assert.equal(renderer.root.findAllByType('button').filter(n=>text(n)==='查看可释放的最旧录音').length,0,
    'legacy/unknown device cannot invent the loss approval capability');
  act(() => renderer.unmount());
  console.log('PASS_COMPONENT_RECORDING_LOSS_ONLY: request budget, duplicate protection, cancel, stale device and capability gating');
}

testProductPolish().catch((testError) => { console.error(testError); process.exitCode = 1; });
