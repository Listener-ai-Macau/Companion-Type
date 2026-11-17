import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { CompanionDashboard, type CompanionProductSettingsPublic, type CompanionProductSettingsPatch } from '../packages/ui/src/CompanionDashboard';

void (async () => {
  let snapshot = createCompanionV1Fixture();
  let settings: CompanionProductSettingsPublic = { defaultMeetingMode: 'offlineStore', asrProvider: 'volcengine',
    volcAppKeySet: true, volcAccessKeySet: true, volcResourceId: 'resource', openaiAsrEndpoint: 'https://example.invalid/asr',
    openaiAsrApiKeySet: true, openaiAsrModel: 'model', deepseekApiKeySet: true, deepseekBaseUrl: 'https://example.invalid/v1',
    deepseekModel: 'model', deepseekMinutesEnabled: true, bleCompress: false, settingsPath: 'fixture-only.json' };
  const saves: CompanionProductSettingsPatch[] = [];
  let finish: () => void = () => {}; let fail: (error: Error) => void = () => {};
  let throwSynchronously = false;
  const props = () => ({ snapshot, surface: 'windows' as const, busyAction: null, error: null, productSettings: settings,
    onRefresh: () => {}, onControl: () => {}, onCheckService: async () => {},
    onSaveProductSettings: (patch: CompanionProductSettingsPatch) => {
      saves.push(structuredClone(patch));
      if (throwSynchronously) throw new Error('fixture save failed synchronously');
      return new Promise<void>((resolve, reject) => { finish = resolve; fail = reject; });
    } });
  let renderer: any; act(() => { renderer = create(<CompanionDashboard {...props()} />); });
  const text = (node: any): string => typeof node === 'string' ? node : (node?.children ?? []).map(text).join('');
  const button = (label: string) => {
    const node = renderer.root.findAllByType('button').find((node: any) => node.props['aria-label'] === label || text(node) === label);
    assert.ok(node, label); return node;
  };
  const key = (kind: string) => renderer.root.findByProps({id: `ct-key-${kind}`});
  act(() => button('设置').props.onClick());
  assert.equal(key('deepseekApiKey').props.value, '', 'stored secrets are never echoed');
  act(() => key('deepseekApiKey').props.onChange({target: {value: 'draft-private'}}));
  act(() => button('清空服务密钥').props.onClick());
  assert.equal(key('deepseekApiKey').props.value, ''); assert.equal(key('deepseekApiKey').props.disabled, true);
  assert.match(text(renderer.toJSON()), /保存后将清空所选密钥/);
  assert.match(text(renderer.toJSON()), /还缺：DeepSeek Key/);
  assert.equal(button('测试云端纪要').props.disabled, true);
  act(() => button('撤销清空服务密钥').props.onClick());
  assert.equal(key('deepseekApiKey').props.value, 'draft-private', 'undo retains an unsaved replacement');
  act(() => button('清空服务密钥').props.onClick());
  await act(async () => { const save = button('保存设置'); save.props.onClick(); save.props.onClick(); });
  assert.equal(saves.length, 1, 'one save for two clicks');
  assert.deepEqual(saves[0].clearCredentials, ['deepseekApiKey']); assert.equal(saves[0].deepseekApiKey, '');
  assert.equal(saves[0].volcAccessKey, ''); assert.equal(button('撤销清空服务密钥').props.disabled, true);
  await act(async () => fail(new Error('fixture occupied settings')));
  assert.match(text(renderer.toJSON()), /设置尚未确认保存/);
  assert.doesNotMatch(text(renderer.toJSON()), /fixture occupied settings/);
  assert.equal(button('撤销清空服务密钥').props.disabled, false);
  assert.equal(button('保存设置').props.disabled, false);
  await act(async () => button('保存设置').props.onClick());
  assert.equal(saves.length, 2); assert.deepEqual(saves[1].clearCredentials, ['deepseekApiKey']);
  await act(async () => { settings = {...settings, deepseekApiKeySet: false}; renderer.update(<CompanionDashboard {...props()} />); finish(); });
  assert.equal(key('deepseekApiKey').props.value, ''); assert.equal(key('deepseekApiKey').props.disabled, false);
  assert.equal(button('清空服务密钥').props.disabled, true);
  act(() => key('deepseekApiKey').props.onChange({target: {value: 'replacement-private'}}));
  throwSynchronously = true;
  await act(async () => button('保存设置').props.onClick());
  assert.match(text(renderer.toJSON()), /设置尚未确认保存/);
  assert.doesNotMatch(text(renderer.toJSON()), /fixture save failed synchronously/);
  assert.equal(key('deepseekApiKey').props.value, 'replacement-private');
  assert.equal(button('保存设置').props.disabled, false);
  snapshot = structuredClone(snapshot); snapshot.meeting.active = true;
  act(() => renderer.update(<CompanionDashboard {...props()} />));
  const previous = saves.length;
  assert.equal(button('清空服务密钥').props.disabled, true); assert.equal(button('保存设置').props.disabled, true);
  await act(async () => { button('清空服务密钥').props.onClick(); button('保存设置').props.onClick(); });
  assert.equal(saves.length, previous, 'recording guard also protects direct callback invocation');
  act(() => renderer.unmount());
  snapshot=createCompanionV1Fixture();settings={...settings,asrProvider:'local-paraformer',localAsrAvailable:true,
    minutesProvider:'cloud',localMinutesSupported:true,localMinutesAvailable:true,deepseekApiKeySet:false,deepseekMinutesEnabled:false};
  const checks:string[]=[];let localSaved:CompanionProductSettingsPatch|undefined;
  const localView=():React.ReactElement=><CompanionDashboard {...props()} onPrepareLocalMinutes={async()=>{}}
    onCheckService={async service=>{checks.push(service);return{service,status:'available',message:'fixture local check',elapsedMs:0,checkedAtUnixMs:0};}}
    onSaveProductSettings={async patch=>{localSaved=patch;settings={...settings,minutesProvider:patch.minutesProvider};renderer.update(localView());}}/>;
  act(()=>{renderer=create(localView());});act(()=>button('设置').props.onClick());
  act(()=>renderer.root.findByProps({'aria-label':'会议纪要整理方式'}).props.onChange({target:{value:'local'}}));
  assert.equal(button('检查本地纪要').props.disabled,true,'unsaved route cannot check the old cloud route');
  await act(async()=>button('检查本地纪要').props.onClick());assert.equal(checks.length,0);
  await act(async()=>button('保存设置').props.onClick());assert.equal(localSaved?.minutesProvider,'local');
  assert.equal(localSaved?.deepseekApiKey,'');assert.deepEqual(localSaved?.clearCredentials,[]);
  assert.equal(button('检查本地纪要').props.disabled,false,'local minutes do not require a cloud key or cloud enablement');
  await act(async()=>button('检查本地纪要').props.onClick());assert.deepEqual(checks,['minutes']);
  assert.equal(renderer.root.findAllByProps({'aria-label':'服务配置缺项'}).length,0,'ready local modes do not ask for DeepSeek credentials');
  act(()=>renderer.unmount());
  console.log('PASS credential UI state: redaction, explicit clear/undo, pending requirements, duplicate save, async/sync failure retry, replacement and recording exclusion (fixtures only)');
  console.log('PASS minutes provider UI: unsaved route guard, persisted local choice, cloud key retention intent, and local readiness without cloud credentials (fixtures only)');
})().catch(error => { console.error(error); process.exitCode = 1; });
