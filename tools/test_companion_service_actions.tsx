import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { createCompanionV1Fixture, applyCompanionV1ControlFixture } from '../packages/core/src/companionV1';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';

void (async () => {
  let snapshot = createCompanionV1Fixture();
  const settings = {defaultMeetingMode:'offlineStore',asrProvider:'volcengine',volcAppKeySet:true,volcAccessKeySet:true,
    volcResourceId:'volc.bigasr.sauc.duration',openaiAsrEndpoint:'https://example.invalid/asr',openaiAsrApiKeySet:false,
    openaiAsrModel:'model',deepseekApiKeySet:true,deepseekBaseUrl:'https://example.invalid/v1',deepseekModel:'model',deepseekMinutesEnabled:true,bleCompress:false};
  let complete: (result: any) => void = () => {};
  const checks: string[] = [], exports: any[] = [], audioExports: string[] = [];
  let finishAudio: (result: any) => void = () => {};
  let settingsSaves = 0;
  const props = () => ({snapshot,surface:'windows' as const,busyAction:null,error:null,productSettings:settings,
    onRefresh:()=>{},onControl:()=>{},onSaveProductSettings:async()=>{settingsSaves++;},
    onCheckService:(service:'asr'|'minutes')=>{checks.push(service);return new Promise<any>(resolve=>complete=resolve);},
    onExportMeeting:async(request:any)=>{exports.push(request);return {path:'actions.ics',bytes:1};},
    onExportAudio:(id:string)=>{audioExports.push(id);return new Promise<any>(resolve=>finishAudio=resolve);}});
  let renderer:any; act(()=>{renderer=create(<CompanionDashboard {...props()}/>);});
  const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
  const button=(label:string)=>{const n=renderer.root.findAllByType('button').find((n:any)=>text(n).includes(label));assert.ok(n,label);return n;};
  act(()=>button('展开设置与工具').props.onClick());
  const check=button('测试转写服务'); assert.equal(check.props.disabled,false);
  act(()=>{check.props.onClick();check.props.onClick();}); assert.deepEqual(checks,['asr']);
  assert.equal(button('测试纪要服务').props.disabled,true);
  await act(async()=>{complete({service:'asr',status:'authenticationFailed',message:'服务拒绝鉴权',elapsedMs:4,checkedAtUnixMs:1});});
  assert.match(text(renderer.toJSON()),/服务拒绝鉴权/);
  const resource = renderer.root.findAllByType('input').find((n:any)=>n.props.value==='volc.bigasr.sauc.duration');
  act(()=>resource.props.onChange({target:{value:'changed'}}));
  assert.equal(button('测试转写服务').props.disabled,true); assert.doesNotMatch(text(renderer.toJSON()),/服务拒绝鉴权/);
  act(()=>resource.props.onChange({target:{value:'volc.bigasr.sauc.duration'}}));
  act(()=>button('测试转写服务').props.onClick());
  act(()=>resource.props.onChange({target:{value:'new-resource'}}));
  await act(async()=>{complete({service:'asr',status:'available',message:'旧配置测试成功',elapsedMs:2,checkedAtUnixMs:1});});
  assert.doesNotMatch(text(renderer.toJSON()),/旧配置测试成功/);
  snapshot=structuredClone(snapshot); snapshot.meeting.active=true;
  act(()=>renderer.update(<CompanionDashboard {...props()}/>));
  assert.equal(button('测试转写服务').props.disabled,true);
  assert.equal(button('日历待办 (.ics)').props.disabled,true);
  snapshot.meeting.active=false;
  act(()=>renderer.update(<CompanionDashboard {...props()} onCheckService={undefined}/>));
  assert.equal(button('测试纪要服务').props.disabled,true);
  snapshot = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {action:'meetingLoadDemo'});
  act(()=>renderer.update(<CompanionDashboard {...props()}/>));
  assert.equal(button('清单 Markdown').props.disabled,false);
  await act(async()=>{button('清单 Markdown').props.onClick();});
  await act(async()=>{button('日历待办 (.ics)').props.onClick();});
  assert.deepEqual(exports.map(request=>request.format),['todo','ics']);
  assert.ok(exports.every(request=>request.sessionId===snapshot.host.selectedSessionId));
  const first = snapshot.host.sessions.find(session=>session.id===snapshot.host.selectedSessionId)!;
  first.audioPath='C:/test-only/retained.wav'; first.audioStored=true; first.retention.audioCached=true;
  act(()=>renderer.update(<CompanionDashboard {...props()}/>));
  assert.equal(button('保存原音').props.disabled,false);
  const saveAudio=button('保存原音');
  act(()=>{saveAudio.props.onClick();saveAudio.props.onClick();});
  assert.deepEqual(audioExports,[first.id]);
  await act(async()=>{finishAudio(null);});
  assert.match(text(renderer.toJSON()),/已取消保存，原音保持不变/);
  snapshot.meeting.active=true; act(()=>renderer.update(<CompanionDashboard {...props()}/>));
  assert.equal(button('保存原音').props.disabled,true);
  snapshot.meeting.active=false;
  act(()=>renderer.update(<CompanionDashboard {...props()} onExportAudio={undefined}/>));
  assert.equal(button('保存原音').props.disabled,true);
  act(()=>renderer.update(<CompanionDashboard {...props()}/>));
  act(()=>button('保存原音').props.onClick());
  const second={...structuredClone(first),id:'different-meeting',title:'Second meeting'};
  snapshot={...snapshot,host:{...snapshot.host,sessions:[...snapshot.host.sessions,second],selectedSessionId:second.id}};
  act(()=>renderer.update(<CompanionDashboard {...props()}/>));
  await act(async()=>{finishAudio({path:'C:/backup/first.wav',bytes:48});});
  assert.doesNotMatch(text(renderer.toJSON()),/原音已保存：C:\/backup/);
  snapshot=structuredClone(snapshot); snapshot.host.sessions.find(session=>session.id===second.id)!.retention.audioCached=false;
  act(()=>renderer.update(<CompanionDashboard {...props()}/>));
  assert.equal(button('保存原音').props.disabled,true);
  const warningSettings = {...settings, settingsPath:'isolated-test.json',
    storageWarning:'设置文件损坏，正在使用上次保存的备份。',storageSaveBlocked:false};
  act(()=>renderer.update(<CompanionDashboard {...props()} productSettings={warningSettings}/>));
  assert.match(text(renderer.toJSON()),/正在使用上次保存的备份/);
  assert.equal(button('保存设置').props.disabled,false);
  await act(async()=>button('保存设置').props.onClick());
  assert.equal(settingsSaves,1,'explicitly saving a valid backup remains available');
  const draft = renderer.root.findAllByType('input').find((n:any)=>n.props.value==='new-resource');
  assert.ok(draft);
  const protectedSettings = {...warningSettings,asrProvider:'openai-compatible',openaiAsrModel:'fallback-model',
    storageWarning:'设置文件损坏且没有有效备份；原文件已保留。',storageSaveBlocked:true};
  act(()=>renderer.update(<CompanionDashboard {...props()} productSettings={protectedSettings}/>));
  assert.match(text(renderer.toJSON()),/没有有效备份/);
  assert.equal(draft.props.value,'new-resource','unreadable fallback must not reset the user draft');
  assert.equal(button('保存设置').props.disabled,true);
  assert.equal(button('测试转写服务').props.disabled,true);
  const checksBefore = checks.length;
  await act(async()=>{button('保存设置').props.onClick();button('测试转写服务').props.onClick();});
  assert.equal(settingsSaves,1); assert.equal(checks.length,checksBefore);
  act(()=>renderer.unmount());
  console.log('PASS service/action UI: duplicate, auth failure, unsaved/stale settings, recording exclusion, fixture boundary');
})().catch(error=>{console.error(error);process.exitCode=1;});
