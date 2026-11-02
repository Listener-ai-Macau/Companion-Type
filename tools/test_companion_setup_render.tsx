import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { CompanionSetup } from '../packages/ui/src/CompanionSetup';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';

const fixture = createCompanionV1Fixture();
const props = { snapshot: fixture, settings: null, busy: false, recording: false,
  checking: false, onControl: () => {}, onSettings: () => {}, onWorkflow: () => {} };
const button = (html: string, label: string) => {
  const match = [...html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)]
    .find((m) => m[2].replace(/<[^>]+>/g, '').includes(label));
  assert.ok(match, `missing ${label}`);
  return match[1];
};

let html = renderToStaticMarkup(<CompanionSetup {...props} />);
assert.match(html, /浏览器演示/);
assert.match(html, /不代表真实设备/);
assert.match(html, /第一次使用/);
assert.match(html, /浏览器演示不能完成这一步/);
assert.match(button(html, '我已看到记录'), /disabled/);
assert.match(button(html, '听一声回应'), /disabled/);
assert.doesNotMatch(html, /已装配|未装配|全部通过/);
assert.doesNotMatch(button(html, '连接 Companion'), /disabled/);

html = renderToStaticMarkup(<CompanionSetup {...props} recording />);
for (const label of ['扫描设备', '连接 Companion', '检查设备', '听一声回应']) {
  assert.match(button(html, label), /disabled/, `${label} must not interrupt capture`);
}

const real = structuredClone(fixture);
real.source = 'firmware';
real.connected = true;
real.device.mode = 'windowsNative';
real.device.hardwareRevision = 'WBA55 V1.1';
real.device.firmwareVersion = 0x1010f;
real.device.rememberedDeviceId = 'AABBCCDDEEFF';
real.device.autoReconnectEnabled = true;
real.device.manualDisconnect = true;
real.device.connectionPhase = 'manualDisconnected';
real.speaker.supported = true;
real.speaker.online = true;
real.speaker.muted = true;
html = renderToStaticMarkup(<CompanionSetup {...props} snapshot={real} />);
assert.match(html, /你已主动断开/);
assert.match(html, /自动连接我的 Companion/);
assert.doesNotMatch(html, /浏览器演示/);
assert.match(html, /固件 1.1.15/);
assert.match(html, /已识别真实设备/);
assert.match(html, /不会开始录音/);
assert.match(button(html, '设备已静音'), /disabled/);

real.speaker.muted = false;
html = renderToStaticMarkup(<CompanionSetup {...props} snapshot={real} busy />);
assert.match(button(html, '听一声回应'), /disabled/);
html = renderToStaticMarkup(<CompanionSetup {...props} snapshot={real} />);
assert.doesNotMatch(button(html, '听一声回应'), /disabled/);

const settings = { asrProvider: 'volcengine', volcAppKeySet: true, volcAccessKeySet: false } as any;
html = renderToStaticMarkup(<CompanionSetup {...props} settings={settings} />);
assert.match(html, /准备转写方式后/);
assert.doesNotMatch(html, /实际调用待验证/);
settings.volcAccessKeySet = true;
settings.deepseekMinutesEnabled = true;
settings.deepseekApiKeySet = true;
html = renderToStaticMarkup(<CompanionSetup {...props} settings={settings} />);
assert.match(html, /实际调用待验证/);
assert.doesNotMatch(html, /服务已验证|服务检查通过/);
settings.storageWarning = '设置文件损坏且没有有效备份；原文件已保留。';
settings.storageSaveBlocked = true;
html = renderToStaticMarkup(<CompanionSetup {...props} settings={settings} />);
assert.match(html, /role="alert"/);
assert.match(html, /没有有效备份/);
assert.match(html, /服务设置暂不可用/);
assert.doesNotMatch(html, /凭据已保存/);

html = renderToStaticMarkup(<CompanionDashboard snapshot={fixture} busyAction={null} error={null}
  surface="windows" onRefresh={() => {}} onControl={() => {}} />);
assert.match(html, /Companion 连接与准备/);
assert.match(html, /设备不在身边也能查看本机内容/);
assert.doesNotMatch(html, /主路径必须连接板子|WB55|Decision: Companion host/);

const storage = new Map<string, string>();
(globalThis as any).window = {
  localStorage: { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) },
};
const guided = applyCompanionV1ControlFixture(real, { action: 'meetingLoadDemo' });
guided.device.deviceId = 'AA:BB:CC:DD:EE:FF';
let renderer: any;
act(() => { renderer = create(<CompanionSetup {...props} snapshot={guided} />); });
const nodeText = (node: any): string => typeof node === 'string' ? node : (node.children ?? []).map(nodeText).join('');
const clickGuide = (label: string) => act(() => {
  const node = renderer.root.findAllByType('button').find((item: any) => nodeText(item).includes(label));
  assert.ok(node, `missing guide button ${label}`); node.props.onClick();
});
clickGuide('我已听到'); clickGuide('我已完成试录'); clickGuide('我已看到记录');
assert.equal(renderer.root.findAllByProps({ 'aria-label': '第一次使用向导' })[0].findAllByType('ol').length, 0,
  'completed guide collapses for the current device');
assert.match([...storage.values()][0], /"sawRecording":true/);
act(() => renderer.unmount());
act(() => { renderer = create(<CompanionSetup {...props} snapshot={guided} />); });
assert.equal(renderer.root.findAllByProps({ 'aria-label': '第一次使用向导' })[0].findAllByType('ol').length, 0,
  'the same device restores its collapsed user-confirmed progress');
const otherDevice = structuredClone(guided); otherDevice.device.deviceId = '11:22:33:44:55:66'; otherDevice.device.rememberedDeviceId = '112233445566';
act(() => renderer.update(<CompanionSetup {...props} snapshot={otherDevice} />));
assert.equal(renderer.root.findAllByProps({ 'aria-label': '第一次使用向导' })[0].findAllByType('ol').length, 1,
  'a different device receives independent onboarding progress');
act(() => renderer.unmount());
act(() => { renderer = create(<CompanionSetup {...props} snapshot={fixture} />); });
clickGuide('第一次使用');
assert.equal(renderer.root.findAllByProps({ 'aria-label': '第一次使用向导' })[0].findAllByType('ol').length, 0,
  'demo or disconnected users may collapse the guide without persisting completion');
act(() => renderer.unmount());
console.log('PASS_UI_RENDER_CONTRACT_ONLY: first-use visibility, truthful state, recording/update locks, mute, service readiness');
