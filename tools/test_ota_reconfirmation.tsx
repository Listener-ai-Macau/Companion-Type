import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

void(async()=>{
  const snapshot=createCompanionV1Fixture();snapshot.device.connected=true;
  snapshot.device.deviceId='C8:ED:45:EB:95:B4';snapshot.device.recording=false;
  const transfers:any[]=[];let installed=true;
  const props={snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
    onTransferOtaPackage:async(request:any)=>{
      transfers.push(request);return {packageType:'companion-system-ota',alreadyInstalled:installed,
        firmwareBytes:installed?0:123456,elapsedMs:1200,deviceId:snapshot.device.deviceId!};
    }};
  let renderer:any;act(()=>{renderer=create(<CompanionDashboard {...props}/>)});
  const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
  const button=(label:string)=>{const b=renderer.root.findAllByType('button').find((n:any)=>text(n)===label);assert.ok(b,label);return b;};
  act(()=>button('设置').props.onClick());
  const manifest=renderer.root.findAllByType('input').find((n:any)=>String(n.props.placeholder).includes('ota_manifest.json'));
  assert.ok(manifest);act(()=>manifest.props.onChange({target:{value:'C:/public/ota_manifest.json'}}));
  assert.equal(button('传输到设备').props.disabled,false);
  await act(async()=>button('传输到设备').props.onClick());
  assert.equal(transfers.length,1);assert.equal(transfers[0].deviceId,snapshot.device.deviceId);
  assert.match(text(renderer.toJSON()),/设备已运行这份固件与资源，完整校验已核对，无需重新传输/);
  assert.doesNotMatch(text(renderer.toJSON()),/设备重启确认成功/);
  installed=false;await act(async()=>button('传输到设备').props.onClick());
  assert.match(text(renderer.toJSON()),/固件与资源已更新，设备重启确认成功 · 123456 B/);
  assert.doesNotMatch(text(renderer.toJSON()),/无需重新传输/);
  act(()=>renderer.unmount());console.log('PASS exact installed-package recovery and new-upgrade messages stay distinct; component only');
})().catch(error=>{console.error(error);process.exitCode=1;});
