import assert from 'node:assert/strict';
import { PNG } from 'pngjs';
import jsQR from 'jsqr';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { checklistPhoneCode, CHECKLIST_QR_MAX_BYTES } from '../packages/ui/src/checklistPhone';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';
import { createCompanionV1Fixture, applyCompanionV1ControlFixture } from '../packages/core/src/companionV1';

const message = '周末购物\n[ ] 买咖啡豆（不要深烘）\n[ ] 买牛奶；礼物暂不购买，预算200元待确认\n[ ] Email Alex 🐱';
const encoded = await checklistPhoneCode(message);
assert.equal(encoded.kind, 'ready');
if (encoded.kind !== 'ready') throw Error('Expected a complete code');
const png = PNG.sync.read(Buffer.from(encoded.dataUrl.split(',')[1], 'base64'));
const decoded = jsQR(new Uint8ClampedArray(png.data), png.width, png.height);
assert.equal(decoded?.data, message, 'Independent decoder retains full Chinese/English/emoji, negation, budget and completion marks');
assert.equal(png.width, encoded.pixels);
assert.ok(png.width <= 420);
const long = '不购买'.repeat(CHECKLIST_QR_MAX_BYTES);
const oversized = await checklistPhoneCode(long);
assert.equal(oversized.kind, 'tooLong');
assert.equal(oversized.text, long, 'No shortened code that loses conditions');
await assert.rejects(checklistPhoneCode('  '));

let snapshot = applyCompanionV1ControlFixture(createCompanionV1Fixture(), {action:'meetingLoadDemo'});
snapshot.host.persistence = {status:'ready'};
const row = snapshot.host.sessions[0];
row.minutesByMode.offlineStore!.quality='final';row.minutesByMode.offlineStore!.status='minutesReady';
const original = JSON.stringify(snapshot);
const requests:any[]=[];
let release:((v:any)=>void)|null=null, defer=false, tree:any;
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
 onSaveMeeting:async()=>snapshot,
 onPreviewMeetingExport:async(request:any)=>{
   requests.push(request);
   if(defer)return new Promise<any>(resolve=>{release=resolve;});
   return {contentHash:'a'.repeat(64),textContent:message};
 }});
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label);
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});
assert.equal(requests.length,0,'Opening a record does not prepare or disclose a QR automatically');
await act(async()=>{button('带到手机').props.onClick();for(let i=0;i<50&&!tree.root.findAllByProps({alt:'当前已保存清单的文字二维码'}).length;i++)await new Promise(resolve=>setTimeout(resolve,10));});
assert.deepEqual(requests[0],{sessionId:row.id,meetingMode:'offlineStore',format:'todo'});
assert.equal(tree.root.findByProps({alt:'当前已保存清单的文字二维码'}).props.src,encoded.dataUrl);
assert.match(text(tree.toJSON()),/没有上传或自动发送/);
assert.match(text(tree.toJSON()),/不会自动设置提醒/);
await act(async()=>button('收起').props.onClick());
assert.equal(tree.root.findAllByProps({alt:'当前已保存清单的文字二维码'}).length,0);

defer=true;
await act(async()=>{button('带到手机').props.onClick();button('带到手机').props.onClick();});
assert.equal(requests.length,2,'Only one read-only preview per click while pending');
await act(async()=>button('收起').props.onClick());
await act(async()=>release!({contentHash:'a'.repeat(64),textContent:message}));
assert.equal(tree.root.findAllByProps({alt:'当前已保存清单的文字二维码'}).length,0,'Closing before a late IPC reply cannot reveal the text/code');
assert.equal(button('带到手机').props.disabled,false);

await act(async()=>{button('带到手机').props.onClick();});
const pending=release!;
snapshot=structuredClone(snapshot);snapshot.host.sessions[0].title='另一个已保存标题';
await act(async()=>tree.update(<CompanionDashboard {...props()}/>));
await act(async()=>pending({contentHash:'a'.repeat(64),textContent:message}));
assert.equal(tree.root.findAllByProps({alt:'当前已保存清单的文字二维码'}).length,0,'A title/source change invalidates pending QR data');
snapshot=JSON.parse(original);defer=false;
await act(async()=>tree.update(<CompanionDashboard {...props()}/>));
await act(async()=>button('编辑清单').props.onClick());
assert.equal(button('带到手机'),undefined,'Editing cannot disclose a previous saved/draft mixture');
act(()=>tree.unmount());
assert.equal(JSON.stringify(snapshot),original);
console.log('PASS full saved checklist QR decode, byte limit without truncation, ordinary UI intent, native preview source, cancel/late/stale/edit guards; no device/cloud/phone claim');
