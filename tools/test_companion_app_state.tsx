import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { App } from '../apps/windows/src/App';

const timers = new Map<number, () => void>();
let timerId = 0;
(globalThis as any).window = {
  setTimeout: (fn: () => void) => { timers.set(++timerId, fn); return timerId; },
  clearTimeout: (id: number) => timers.delete(id),
  requestAnimationFrame: (fn:()=>void) => {fn();return 0;},
};
(globalThis as any).HTMLButtonElement=class {};
(globalThis as any).document={activeElement:null};
const initial = createCompanionV1Fixture();
initial.connected = true;
initial.device.rememberedDeviceId = 'AABBCCDDEEFF';
initial.device.autoReconnectEnabled = true;
initial.device.manualDisconnect = false;
let pendingRead: ((value: unknown) => void) | undefined;
let pendingControl: ((value: unknown) => void) | undefined;
let snapshotCalls = 0, controlCalls = 0;
(globalThis as any).__companionAppTest = {
  snapshot: async () => {
    snapshotCalls++;
    if (snapshotCalls === 1) return initial;
    return new Promise((resolve) => { pendingRead = resolve; });
  },
  control: () => { controlCalls++; return new Promise((resolve) => { pendingControl = resolve; }); },
};
let renderer: any;
await act(async () => { renderer = create(<App />); });
assert.equal(snapshotCalls, 1);
assert.equal(timers.size, 1, 'one polling chain, not multiple setIntervals');
const [, tick] = [...timers][0]; timers.clear();
await act(async () => { tick(); });
assert.equal(snapshotCalls, 2);
assert.equal(timers.size, 0, 'no new polling until pending response finishes');
const text = (node: any): string => typeof node === 'string' ? node : (node.children ?? []).map(text).join('');
const disconnect = renderer.root.findAllByType('button').find((node: any) => text(node) === '断开');
assert.ok(disconnect);
await act(async () => { disconnect.props.onClick(); disconnect.props.onClick(); });
assert.equal(controlCalls, 1, 'synchronous operation gate must suppress a double click');
const disconnected = structuredClone(initial);
disconnected.connected = false;
disconnected.device.connected = false;
disconnected.device.manualDisconnect = true;
disconnected.device.connectionPhase = 'manualDisconnected';
await act(async () => { pendingControl!(disconnected); });
await act(async () => { pendingRead!(initial); });
assert.equal(renderer.root.findAllByType('button').some((node: any) => text(node) === '断开'), false,
  'stale reconnect snapshot must not undo manual disconnect');
assert.equal(timers.size, 0, 'manual disconnect stops background refresh');
assert.equal(renderer.root.findAllByProps({ role: 'alert' }).length, 0, 'ignored double click must not leave a spurious failure banner');
await act(async () => renderer.unmount());

// A transient status failure must not hide the dedicated board stop control
// for the rest of an online recording. These are IPC stubs, not device proof.
const recording = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {
  action: 'meetingStart', meetingMode: 'onlineLive', sessionId: 'board-status-recovery',
  audioPath: 'board://online/board-status-recovery',
});
let boardReads = 0, recordingReads = 0, boardStops = 0, legacyStops = 0;
(globalThis as any).__companionAppTest = {
  snapshot: async () => {
    recordingReads++;
    if (recordingReads === 2) throw new Error('temporary snapshot IPC failure');
    return structuredClone(recording);
  },
  boardStatus: async () => {
    boardReads++;
    if (boardReads === 1) throw new Error('temporary board status IPC failure');
    if (boardReads === 3) throw new Error('another status IPC failure');
    return { state: 'recording', sessionId: 'board-status-recovery', durationMs: 8000, partialCount: 1 };
  },
  stopBoard: async () => { boardStops++; return { state: 'stopping', sessionId: 'board-status-recovery' }; },
  control: async () => { legacyStops++; return recording; },
};
await act(async () => { renderer = create(<App />); });
assert.equal(boardReads, 1);
assert.equal(timers.size, 1, 'recording snapshot must keep status recovery polling alive');
const tickOnce = async () => {
  assert.equal(timers.size, 1);
  const [, next] = [...timers][0]; timers.clear();
  await act(async () => { next(); });
};
await tickOnce();
assert.equal(boardReads, 2, 'retry board status even when the first read failed');
const boardStop = () => renderer.root.findAllByType('button').find((node: any) => text(node) === '结束录音并整理');
assert.ok(boardStop(), 'board stop must recover even when the simultaneous snapshot read fails');
assert.equal(boardStop().props.disabled, false);
recording.host.sessions[0].transcriptText = '新的录音片段';
await tickOnce();
assert.match(text(renderer.toJSON()), /新的录音片段/, 'a status read failure must not discard a successful transcript refresh');
assert.equal(boardStop().props.disabled, false, 'retain last valid board status during a transient failure');
await act(async () => { boardStop().props.onClick(); boardStop().props.onClick(); });
assert.equal(boardStops, 1);
assert.equal(legacyStops, 0, 'use the native board stop command, not the host recording stop path');
assert.equal(boardStop().props.disabled, true);
await act(async () => renderer.unmount());
assert.equal(timers.size, 0);

// A background refresh started before a rename must not undo the saved title.
const review = applyCompanionV1ControlFixture(createCompanionV1Fixture(), { action: 'meetingLoadDemo' });
review.host.persistence = { status: 'ready' };
review.device.rememberedDeviceId = 'AABBCCDDEEFF';
review.device.autoReconnectEnabled = true;
review.device.manualDisconnect = false;
let reviewReads = 0, reviewSaves = 0;
let oldRead: ((value: unknown) => void) | undefined;
let finishSave: ((value: unknown) => void) | undefined;
let submitted: any;
(globalThis as any).__companionAppTest = {
  snapshot: async () => ++reviewReads === 1 ? review : new Promise((resolve) => { oldRead = resolve; }),
  saveMeeting: async (request: unknown) => {
    reviewSaves++; submitted = request;
    return new Promise((resolve) => { finishSave = resolve; });
  },
  control: async () => review,
};
await act(async () => { renderer = create(<App />); });
await act(async()=>renderer.root.findAllByType('button').find((node:any)=>node.props.className?.includes('ct-library-card')).props.onClick());
await tickOnce();
await act(async () => renderer.root.findByProps({ 'aria-label': '记录标题' }).props.onChange({ target: { value: '核对后保存的标题' } }));
const saveTitle = () => renderer.root.findAllByType('button').find((node: any) => text(node) === '保存标题');
await act(async () => { saveTitle().props.onClick(); });
assert.equal(reviewSaves, 1);
assert.equal(submitted.sessionId, review.host.sessions[0].id);
assert.equal(submitted.expectedTitle, review.host.sessions[0].title);
const savedReview = structuredClone(review);
savedReview.host.sessions[0].title = submitted.title;
await act(async () => { finishSave!(savedReview); });
await act(async () => { oldRead!(review); });
assert.equal(renderer.root.findByProps({ 'aria-label': '记录标题' }).props.value, '核对后保存的标题');
assert.equal(Boolean(saveTitle()), false, 'persisted edit clears only its submitted draft');
await act(async () => renderer.unmount());
assert.equal(timers.size, 0);
console.log('PASS_APP_ASYNC_STATE_ONLY: bounded polling, double-click exclusion, stale response discard including saved meeting edits, manual disconnect, independent status recovery and board stop');

// The live marker uses the native command and epoch just like other edits;
// an older background snapshot cannot erase its durable receipt in the UI.
const bookmarkRecording=structuredClone(recording);
bookmarkRecording.host.persistence={status:'ready'};
const bookmarkSession=bookmarkRecording.host.sessions[0];
bookmarkSession.source='boardDevice';bookmarkSession.sourceDeviceId='AABBCCDDEEFF';bookmarkSession.deviceRecordingId=17;
bookmarkSession.bookmarks=[];bookmarkSession.bookmarkRevision=0;
let bookmarkReads=0,bookmarkSaves=0;let pendingBookmarkRead:any,finishBookmark:any,bookmarkRequest:any;
(globalThis as any).__companionAppTest={
  snapshot:async()=>++bookmarkReads===1?bookmarkRecording:new Promise((resolve)=>{pendingBookmarkRead=resolve;}),
  boardStatus:async()=>({state:'recording',sessionId:bookmarkSession.id,durationMs:2000}),
  saveBookmark:async(request:any)=>{bookmarkSaves++;bookmarkRequest=request;return new Promise((resolve)=>{finishBookmark=resolve;});},
};
await act(async()=>{renderer=create(<App/>);});await tickOnce();
await act(async()=>renderer.root.findByProps({'aria-label':'重点名称'}).props.onChange({target:{value:'讨论预算'}}));
const mark=()=>renderer.root.findAllByType('button').find((node:any)=>text(node)==='标记当前录音');
await act(async()=>{mark().props.onClick();mark().props.onClick();});assert.equal(bookmarkSaves,1);
assert.equal(bookmarkRequest.sessionId,bookmarkSession.id);assert.equal(bookmarkRequest.positionMs,undefined);
const bookmarkSaved=structuredClone(bookmarkRecording);
bookmarkSaved.host.sessions[0].bookmarkRevision=1;
bookmarkSaved.host.sessions[0].bookmarks=[{id:bookmarkRequest.bookmarkId,label:'讨论预算',positionMs:2400,createdAt:'native-time',origin:'boardRecording'}];
await act(async()=>{finishBookmark(bookmarkSaved);});await act(async()=>{pendingBookmarkRead(bookmarkRecording);});
assert.match(text(renderer.toJSON()),/讨论预算/,'stale background read cannot discard the accepted mark');
assert.equal(renderer.root.findByProps({'aria-label':'重点名称'}).props.value,'');
await act(async()=>renderer.unmount());assert.equal(timers.size,0);
console.log('PASS_APP_BOOKMARK_STATE_ONLY: native route, actual session binding, duplicate exclusion and stale read protection; device/GUI NOT_RUN');

// A local-only capture must keep its durable state visible even when automatic
// device reconnect is disabled; it must not start the online ASR manager.
const localRecording=structuredClone(recording);
localRecording.host.sessions[0].meetingMode='offlineStore';
localRecording.host.sessions[0].source='boardDevice';
localRecording.host.sessions[0].sourceDeviceId='C8:92:FF:DD:3B:CA';
localRecording.host.sessions[0].recorderControl={hostSession:localRecording.host.sessions[0].id,
  deviceId:'C8:92:FF:DD:3B:CA',startRequest:100,maxSeconds:1800,
  confirmed:{command:1,sequence:0,state:1,durationMs:4000}};
localRecording.device.autoReconnectEnabled=false;
let localReads=0,localBoardReads=0;
(globalThis as any).__companionAppTest={
  snapshot:async()=>{localReads++;return structuredClone(localRecording);},
  boardStatus:async()=>{localBoardReads++;return {state:'idle'};},
};
await act(async()=>{renderer=create(<App/>);});
assert.equal(timers.size,1,'local-only recording keeps one state refresh chain');
assert.ok(renderer.root.findAllByType('button').some((node:any)=>text(node)==='停止并保存'));
const originalBoardReads=localBoardReads;await tickOnce();
assert.equal(localReads,2);
assert.equal(localBoardReads,originalBoardReads,'pure recording does not poll online ASR status after initial setup');
assert.equal(timers.size,1);
await act(async()=>renderer.unmount());assert.equal(timers.size,0);
console.log('PASS_APP_LOCAL_RECORDING_STATE_ONLY: saved-state polling without reconnect preference or online manager; device/GUI NOT_RUN');
