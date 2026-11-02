import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { CompanionDesktopUpdate, type CompanionDesktopUpdateStatus } from '../packages/ui/src/CompanionDesktopUpdate';

const ready: CompanionDesktopUpdateStatus = {
  phase: 'ready', message: '本机更新已验证', currentVersion: '0.1.0',
  availableVersion: '0.2.0', downloadedBytes: 42, totalBytes: 42,
};
let state = ready;
let checks = 0, downloads = 0, cancels = 0, installs = 0;
let releaseCheck: ((value: CompanionDesktopUpdateStatus) => void) | undefined;
const props = {
  blocked: false, unsaved: false,
  onStatus: async () => state,
  onCheck: () => { checks++; return new Promise<CompanionDesktopUpdateStatus>(resolve => { releaseCheck = resolve; }); },
  onDownload: async () => { downloads++; return ready; },
  onCancel: async () => { cancels++; },
  onInstall: async () => { installs++; },
};
const text = (node: any): string => typeof node === 'string' ? node : (node.children ?? []).map(text).join('');
async function main() {
  let renderer: any;
  await act(async () => { renderer = create(<CompanionDesktopUpdate {...props} />); });
  const button = (label: string) => {
    const node = renderer.root.findAllByType('button').find((n: any) => text(n) === label);
    assert.ok(node, label); return node;
  };
  const confirm = () => renderer.root.findByType('input');
  assert.equal(button('安装更新').props.disabled, true);
  act(() => confirm().props.onChange({ target: { checked: true } }));
  assert.equal(button('安装更新').props.disabled, false);
  await act(async () => { renderer.update(<CompanionDesktopUpdate {...props} unsaved />); });
  assert.equal(button('安装更新').props.disabled, true);
  assert.equal(confirm().props.checked, false, 'new unsaved edits invalidate prior install confirmation');
  await act(async () => { renderer.update(<CompanionDesktopUpdate {...props} blocked />); });
  assert.equal(confirm().props.disabled, true);
  await act(async () => { renderer.update(<CompanionDesktopUpdate {...props} />); });
  act(() => confirm().props.onChange({ target: { checked: true } }));
  await act(async () => { button('安装更新').props.onClick(); });
  assert.equal(installs, 1);
  act(() => { button('检查软件更新').props.onClick(); button('检查软件更新').props.onClick(); });
  assert.equal(checks, 1, 'two rapid clicks start one operation');
  assert.equal(button('检查软件更新').props.disabled, true);
  state = { ...ready, phase: 'downloading', downloadedBytes: 21 };
  await act(async () => { releaseCheck!(state); });
  assert.ok(text(renderer.toJSON()).includes('50%'));
  await act(async () => { button('取消下载').props.onClick(); });
  assert.equal(cancels, 1, 'cancel remains usable while native transfer is busy');
  act(() => renderer.unmount());
  state = { ...ready, phase: 'available', downloadedBytes: 0 };
  await act(async () => { renderer = create(<CompanionDesktopUpdate {...props} blocked />); });
  assert.equal(button('下载更新').props.disabled, true);
  await act(async () => { renderer.update(<CompanionDesktopUpdate {...props} />); });
  await act(async () => { button('下载更新').props.onClick(); });
  assert.equal(downloads, 1);
  act(() => renderer.unmount());
  console.log('PASS React desktop update guards, single operation and cancellation; installer/network/GUI NOT_RUN');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
