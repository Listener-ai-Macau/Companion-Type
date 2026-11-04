import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';

void (async () => {
  let snapshot=createCompanionV1Fixture(); snapshot.device.connected=true;
  let resolveExport:(value:any)=>void=()=>{}; const calls:boolean[]=[];
  const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
    onExportDiagnostics:(include:boolean)=>{calls.push(include);return new Promise<any>(resolve=>{resolveExport=resolve;});},
    onPrepareAudioComponents:async()=>{throw new Error('下载校验失败，未安装');}});
  let renderer:any; act(()=>{renderer=create(<CompanionDashboard {...props()}/>);});
  const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
  const button=(label:string)=>{const node=renderer.root.findAllByType('button').find((n:any)=>text(n).includes(label));assert.ok(node,label);return node;};
  act(()=>button('设置与工具').props.onClick());
  const exportButton=button('读取设备并导出日志');
  act(()=>{exportButton.props.onClick();exportButton.props.onClick();});
  assert.deepEqual(calls,[true], 'double click must create one device request');
  assert.equal(button('准备说话人区分组件').props.disabled,true);
  await act(async()=>{resolveExport({path:'test.json',bytes:10,warning:'设备日志读取未成功'});});
  assert.match(text(renderer.toJSON()),/设备日志读取未成功/);
  await act(async()=>{button('准备说话人区分组件').props.onClick();});
  assert.match(text(renderer.toJSON()),/说话人区分组件尚未准备完成/);
  assert.doesNotMatch(text(renderer.toJSON()),/下载校验失败，未安装/);
  snapshot=structuredClone(snapshot);snapshot.meeting.active=true;
  act(()=>renderer.update(<CompanionDashboard {...props()}/>));
  assert.equal(button('读取设备并导出日志').props.disabled,true);
  assert.equal(button('导出本机日志').props.disabled,true);
  assert.equal(button('准备说话人区分组件').props.disabled,true);
  snapshot.meeting.active=false;
  act(()=>renderer.update(<CompanionDashboard {...props()} onExportDiagnostics={undefined} onPrepareAudioComponents={undefined}/>));
  assert.equal(button('导出本机日志').props.disabled,true);
  act(()=>renderer.unmount());
  console.log('PASS diagnostics UI: busy, duplicate, partial export, model failure, fixture capability boundary');
})().catch(error=>{console.error(error);process.exitCode=1;});
